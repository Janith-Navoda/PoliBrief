"""
PoliBrief Phase 1 — Automated Tests
Tests: auth service, database init, admin CRUD, JWT, API health, setup/login endpoints.

Fixtures (db, client) are provided by conftest.py.
"""
import pytest
from datetime import datetime, timezone

from backend.app.models import Administrator
from backend.app.auth.service import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    create_admin,
    authenticate_admin,
    admin_exists,
)


# ─── Password Hashing ─────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("securepassword123")
        assert hashed != "securepassword123"
        assert len(hashed) > 20

    def test_verify_correct_password(self):
        hashed = hash_password("correct_password_99")
        assert verify_password("correct_password_99", hashed) is True

    def test_reject_wrong_password(self):
        hashed = hash_password("correct_password_99")
        assert verify_password("wrong_password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Argon2id uses random salts — hashes must differ."""
        h1 = hash_password("same_password!")
        h2 = hash_password("same_password!")
        assert h1 != h2

    def test_verify_rejects_empty_string(self):
        hashed = hash_password("somepassword")
        assert verify_password("", hashed) is False


# ─── JWT Tokens ───────────────────────────────────────────────────────────────

class TestJWT:
    def test_create_and_decode_valid_token(self):
        token = create_access_token("admin_user")
        subject = decode_access_token(token)
        assert subject == "admin_user"

    def test_decode_invalid_token_returns_none(self):
        result = decode_access_token("not.a.valid.token")
        assert result is None

    def test_decode_tampered_token_returns_none(self):
        token = create_access_token("admin_user")
        tampered = token[:-5] + "XXXXX"
        result = decode_access_token(tampered)
        assert result is None

    def test_decode_empty_string_returns_none(self):
        assert decode_access_token("") is None


# ─── Administrator CRUD ───────────────────────────────────────────────────────

class TestAdminCRUD:
    def test_create_admin(self, db):
        admin = create_admin(db, "testadmin", "strongpassword1")
        assert admin.id is not None
        assert admin.username == "testadmin"
        assert admin.password_hash != "strongpassword1"

    def test_admin_exists_false_when_empty(self, db):
        assert admin_exists(db) is False

    def test_admin_exists_true_after_creation(self, db):
        create_admin(db, "admin", "password1234567")
        assert admin_exists(db) is True

    def test_authenticate_admin_success(self, db):
        create_admin(db, "admin", "correct_pass_123")
        result = authenticate_admin(db, "admin", "correct_pass_123")
        assert result is not None
        assert result.username == "admin"

    def test_authenticate_admin_wrong_password(self, db):
        create_admin(db, "admin", "correct_pass_123")
        result = authenticate_admin(db, "admin", "wrong_password")
        assert result is None

    def test_authenticate_nonexistent_admin(self, db):
        result = authenticate_admin(db, "ghost_user", "any_password")
        assert result is None

    def test_last_login_updated_on_auth(self, db):
        create_admin(db, "admin", "correct_pass_123")
        before = datetime.now(timezone.utc)
        admin = authenticate_admin(db, "admin", "correct_pass_123")
        assert admin.last_login is not None
        # Ensure both datetimes are timezone-aware for comparison
        last_login = admin.last_login
        if last_login.tzinfo is None:
            last_login = last_login.replace(tzinfo=timezone.utc)
        diff = abs((last_login - before).total_seconds())
        assert diff < 5

    def test_cannot_create_duplicate_username(self, db):
        create_admin(db, "admin", "password1234567")
        with pytest.raises(Exception):  # IntegrityError from unique constraint
            create_admin(db, "admin", "different_password")


# ─── Database Model ───────────────────────────────────────────────────────────

class TestDatabaseModels:
    def test_administrator_table_exists(self, db):
        count = db.query(Administrator).count()
        assert count == 0

    def test_created_at_set_automatically(self, db):
        admin = create_admin(db, "admin", "password1234567")
        assert admin.created_at is not None

    def test_news_source_table_accessible(self, db):
        from backend.app.models import NewsSource
        count = db.query(NewsSource).count()
        assert count == 0

    def test_article_table_accessible(self, db):
        from backend.app.models import Article
        count = db.query(Article).count()
        assert count == 0

    def test_post_draft_table_accessible(self, db):
        from backend.app.models import PostDraft
        count = db.query(PostDraft).count()
        assert count == 0


# ─── FastAPI Integration Tests ────────────────────────────────────────────────


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/api/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_api_root_returns_200(self, client):
        resp = client.get("/api")
        assert resp.status_code == 200
        assert resp.json()["name"] == "PoliBrief API"


class TestAuthEndpoints:
    def test_auth_status_no_admin_setup(self, client):
        resp = client.get("/api/auth/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["setup_complete"] is False
        assert data["authenticated"] is False

    def test_setup_creates_admin(self, client):
        resp = client.post("/api/auth/setup", json={
            "username": "testadmin",
            "password": "securepassword123"
        })
        assert resp.status_code == 201
        assert resp.json()["username"] == "testadmin"

    def test_setup_blocked_after_first_admin(self, client):
        client.post("/api/auth/setup", json={
            "username": "admin1",
            "password": "securepassword123"
        })
        resp = client.post("/api/auth/setup", json={
            "username": "admin2",
            "password": "securepassword456"
        })
        assert resp.status_code == 409

    def test_login_success(self, client):
        client.post("/api/auth/setup", json={
            "username": "admin",
            "password": "securepassword123"
        })
        resp = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "securepassword123"
        })
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"
        assert "pb_access_token" in resp.cookies

    def test_login_wrong_password(self, client):
        client.post("/api/auth/setup", json={
            "username": "admin",
            "password": "securepassword123"
        })
        resp = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "wrongpassword"
        })
        assert resp.status_code == 401

    def test_protected_endpoint_requires_auth(self, client):
        resp = client.get("/api/system/dashboard-stats")
        assert resp.status_code == 401

    def test_protected_endpoint_accessible_after_login(self, client):
        client.post("/api/auth/setup", json={
            "username": "admin",
            "password": "securepassword123"
        })
        client.post("/api/auth/login", json={
            "username": "admin",
            "password": "securepassword123"
        })
        resp = client.get("/api/system/dashboard-stats")
        assert resp.status_code == 200

    def test_logout_clears_session(self, client):
        client.post("/api/auth/setup", json={
            "username": "admin",
            "password": "securepassword123"
        })
        client.post("/api/auth/login", json={
            "username": "admin",
            "password": "securepassword123"
        })
        # Confirm we're authenticated
        assert client.get("/api/system/dashboard-stats").status_code == 200
        # Logout
        client.post("/api/auth/logout")
        # Now should be 401 (cookie cleared)
        resp = client.get("/api/system/dashboard-stats")
        assert resp.status_code == 401

    def test_me_endpoint_returns_user(self, client):
        client.post("/api/auth/setup", json={
            "username": "admin",
            "password": "securepassword123"
        })
        client.post("/api/auth/login", json={
            "username": "admin",
            "password": "securepassword123"
        })
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"

    def test_auth_status_after_login(self, client):
        client.post("/api/auth/setup", json={
            "username": "admin",
            "password": "securepassword123"
        })
        client.post("/api/auth/login", json={
            "username": "admin",
            "password": "securepassword123"
        })
        resp = client.get("/api/auth/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["setup_complete"] is True
        assert data["authenticated"] is True
        assert data["username"] == "admin"

    def test_setup_rejects_short_username(self, client):
        resp = client.post("/api/auth/setup", json={
            "username": "ab",
            "password": "securepassword123"
        })
        assert resp.status_code == 422

    def test_setup_rejects_short_password(self, client):
        resp = client.post("/api/auth/setup", json={
            "username": "admin",
            "password": "short"
        })
        assert resp.status_code == 422
