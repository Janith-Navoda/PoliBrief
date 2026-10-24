"""
PoliBrief Backend — RSS Feed Ingestion Service
Handles safe HTTP fetching with HTTPX, feed parsing with feedparser,
date normalization to UTC, tracking-parameter stripping, and feed validation.
"""
import hashlib
import html
import ipaddress
import logging
import re
import asyncio
import socket
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import feedparser
import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "PoliBrief/1.0 (+http://localhost; Political News Aggregator)"
DEFAULT_TIMEOUT = 15.0
MAX_FEED_BYTES = 8 * 1024 * 1024
MAX_FETCH_ATTEMPTS = 3

# Tracking query parameters to strip for canonical URL normalization
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "_hsenc",
    "_hsmi",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "ref",
    "source",
}


def sanitize_url(raw_url: str) -> str:
    """Strip tracking parameters and clean trailing slashes/fragments to create a canonical URL."""
    if not raw_url:
        return ""
    try:
        parsed = urlparse(raw_url.strip())
        if not parsed.scheme or not parsed.netloc:
            return raw_url.strip()

        # Filter out tracking parameters
        query_pairs = parse_qsl(parsed.query, keep_blank_values=False)
        filtered_pairs = [
            (k, v) for k, v in query_pairs if k.lower() not in TRACKING_PARAMS
        ]
        # Reconstruct query sorted for canonical consistency
        clean_query = urlencode(sorted(filtered_pairs))

        # Drop fragment and normalize path
        path = parsed.path.rstrip("/")
        if not path and not clean_query:
            path = ""

        canonical = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            clean_query,
            "",
        ))
        return canonical or raw_url.strip()
    except Exception:
        return raw_url.strip()


def compute_fingerprint(canonical_url: str, headline: str = "") -> str:
    """Generate SHA-256 fingerprint for deduplication."""
    content = f"{canonical_url.strip().lower()}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def clean_html_summary(raw_html: Optional[str]) -> Optional[str]:
    """Strip HTML tags and unescape HTML entities for clean plaintext snippet."""
    if not raw_html:
        return None
    # Remove script and style elements
    text = re.sub(r"<(script|style).*?>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Unescape HTML entities (e.g. &amp;, &quot;)
    text = html.unescape(text)
    # Collapse multiple whitespaces
    text = re.sub(r"\s+", " ", text).strip()
    return text[:2000] if text else None


def parse_entry_datetime(entry: dict) -> Optional[datetime]:
    """Extract and normalize publication datetime into a timezone-aware UTC datetime."""
    time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if time_struct:
        try:
            return datetime(*time_struct[:6], tzinfo=timezone.utc)
        except Exception:
            pass

    # Try raw date string parsing if time_struct is missing
    raw_date = entry.get("published") or entry.get("updated")
    if raw_date:
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(raw_date)
            if dt.tzinfo is None:
                return None
            return dt.astimezone(timezone.utc)
        except Exception:
            pass

    # Unknown dates stay unknown. The collector quarantines these entries for
    # review rather than presenting collection time as verified publication time.
    return None


def is_safe_feed_url(url: str) -> bool:
    """Reject malformed URLs and obvious local/private targets before connecting."""
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            return False
        if not parsed.hostname:
            return False

        if parsed.username is not None or parsed.password is not None:
            return False
        hostname = parsed.hostname.rstrip(".").lower()
        if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith((".localhost", ".local", ".internal")):
            return False

        try:
            ip = ipaddress.ip_address(hostname)
            if not ip.is_global:
                return False
        except ValueError:
            pass  # DNS names are resolved and pinned by PublicOnlyNetworkBackend.

        return True
    except Exception:
        return False


class PublicOnlyNetworkBackend:
    """Resolve and pin each new HTTP connection to a public address."""

    def __init__(self):
        import httpcore
        from httpcore._backends.auto import AutoBackend

        self._httpcore = httpcore
        self._backend = AutoBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        try:
            records = await asyncio.to_thread(
                socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM
            )
            addresses = list(dict.fromkeys(record[4][0] for record in records))
            if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
                raise ValueError("Feed host resolved to a non-public address")
            # Connecting to the validated literal IP prevents a second DNS lookup
            # from rebinding the request to a local address.
            return await self._backend.connect_tcp(
                addresses[0], port, timeout=timeout,
                local_address=local_address, socket_options=socket_options,
            )
        except Exception as exc:
            raise self._httpcore.ConnectError("Feed host could not be safely resolved") from exc

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise self._httpcore.ConnectError("Unix sockets are not allowed for RSS feeds")

    async def sleep(self, seconds):
        await self._backend.sleep(seconds)


async def fetch_feed_data(url: str, timeout: float = DEFAULT_TIMEOUT) -> feedparser.FeedParserDict:
    """Fetch raw feed XML via HTTPX and parse with feedparser."""
    if not is_safe_feed_url(url):
        raise ValueError("Invalid or disallowed feed URL")

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    }

    # HTTPX has no public DNS-pinning hook. Its httpcore pool exposes the
    # network backend used for TCP connection creation; replacing only that
    # backend lets TLS retain the original hostname while pinning the socket IP.
    transport = httpx.AsyncHTTPTransport(trust_env=False)
    transport._pool._network_backend = PublicOnlyNetworkBackend()
    current_url = url
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=False, trust_env=False, transport=transport
    ) as client:
        for redirect_count in range(6):
            if not is_safe_feed_url(current_url):
                raise ValueError("Feed redirect target is invalid or disallowed")
            redirect_target = None
            for attempt in range(MAX_FETCH_ATTEMPTS):
                try:
                    async with client.stream("GET", current_url, headers=headers) as response:
                        if response.is_redirect:
                            location = response.headers.get("location")
                            if not location or redirect_count >= 5:
                                raise ValueError("Feed has an invalid or excessive redirect chain")
                            redirect_target = urljoin(current_url, location)
                            break

                        if response.status_code == 429 or response.status_code >= 500:
                            if attempt + 1 < MAX_FETCH_ATTEMPTS:
                                await asyncio.sleep(0.2 * (attempt + 1))
                                continue

                        response.raise_for_status()
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > MAX_FEED_BYTES:
                                raise ValueError("RSS response exceeds the 8 MiB size limit")
                        content = bytes(body)
                        break
                except (httpx.TimeoutException, httpx.NetworkError):
                    if attempt + 1 >= MAX_FETCH_ATTEMPTS:
                        raise
                    await asyncio.sleep(0.2 * (attempt + 1))
            else:
                raise httpx.NetworkError("RSS request failed after bounded retries")

            if redirect_target:
                if not is_safe_feed_url(redirect_target):
                    raise ValueError("Feed redirect target is invalid or disallowed")
                current_url = redirect_target
                continue
            break
        else:
            raise ValueError("Feed has an excessive redirect chain")

    feed = feedparser.parse(content)
    if feed.bozo and not feed.entries:
        exc_msg = str(getattr(feed, "bozo_exception", "Malformed RSS/XML feed"))
        raise ValueError(f"Feed parsing error: {exc_msg}")

    return feed


async def test_feed_url(url: str) -> dict[str, Any]:
    """Test an RSS feed URL and return validation metadata and sample entries."""
    try:
        feed = await fetch_feed_data(url, timeout=10.0)
        title = feed.feed.get("title", "Untitled Feed") if hasattr(feed, "feed") else "Feed"
        description = feed.feed.get("description", "") if hasattr(feed, "feed") else ""
        entries = getattr(feed, "entries", [])
        samples = [e.get("title", "Untitled") for e in entries[:5] if e.get("title")]

        return {
            "valid": True,
            "title": title,
            "description": description,
            "entry_count": len(entries),
            "sample_headlines": samples,
            "message": f"Successfully verified feed '{title}' with {len(entries)} entries.",
        }
    except Exception as exc:
        return {
            "valid": False,
            "title": None,
            "description": None,
            "entry_count": 0,
            "sample_headlines": [],
            "message": f"Feed test failed: {str(exc)}",
        }
