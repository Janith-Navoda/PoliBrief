"""
PoliBrief Backend — Facebook Caption Generation Service
Produces factual, source-grounded post captions containing the headline,
concise editorial snippet, publisher attribution, canonical link, and relevant tags.
"""
from typing import Optional


CATEGORY_HASHTAGS = {
    "Parliament": "#Parliament #Legislation #Congress #Politics",
    "Elections": "#Elections #Voting #Democracy #Campaign #Politics",
    "International Politics": "#ForeignAffairs #Diplomacy #Geopolitics #GlobalNews",
    "Economy and Policy": "#Economy #FiscalPolicy #Budget #Trade #BusinessNews",
    "Government and Policy": "#PublicPolicy #Government #WhiteHouse #Governance",
    "Political Analysis": "#PoliticalAnalysis #Insight #Editorial #Politics",
    "Other / Needs Review": "#Politics #News #PoliBrief",
}


def generate_facebook_caption(
    headline: str,
    publisher_name: str,
    original_url: str,
    description: Optional[str] = None,
    category: Optional[str] = None,
) -> str:
    """
    Generate a formatted, professional Facebook post caption.
    Strictly factual and grounded in original source metadata.
    """
    clean_headline = headline.strip()
    category_key = category or "Government and Policy"
    tags = CATEGORY_HASHTAGS.get(category_key, "#Politics #News #PoliBrief")

    parts = []

    # Headline block
    parts.append(f"📌 {clean_headline}\n")

    # Factual body summary if available
    if description and len(description.strip()) > 30:
        desc_clean = description.strip()
        # Truncate clean description to around 280 characters for optimal social engagement
        if len(desc_clean) > 280:
            desc_clean = desc_clean[:277] + "..."
        parts.append(f"{desc_clean}\n")

    # Attribution & Original Link
    parts.append(f"📰 Source: {publisher_name}")
    parts.append(f"🔗 Read full coverage: {original_url}\n")

    # Hashtags
    parts.append(tags)

    return "\n".join(parts)
