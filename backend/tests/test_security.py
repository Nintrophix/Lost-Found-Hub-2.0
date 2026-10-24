"""Cross-cutting security checks: route authorisation matrix, CSRF, headers, body limits, races and leaks."""

import os
import re
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.api.deps import CSRF_HEADER
from app.core.config import BACKEND_DIR
from app.db.enums import ClaimStatus, UserRole
from app.db.models import Claim, User
from app.main import app
from app.services import auth as auth_service
from app.services import claims as claim_service
from app.services.concurrency import lock_status
from app.services.errors import ServiceError
from tests.test_claims import flow, submit  # noqa: F401  (flow is a fixture)
from tests.test_items import api, create, image_bytes, upload  # noqa: F401  (api is a fixture)

PUBLIC = {
    ("GET", "/api/health"),
    ("GET", "/api/categories"),
    ("GET", "/api/locations"),
    ("GET", "/api/public-stats"),
    ("GET", "/api/auth/session"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/verify-email"),
    ("POST", "/api/auth/resend-verification"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/password/forgot"),
    ("POST", "/api/auth/password/reset"),
}
SAFE = {"GET", "HEAD", "OPTIONS"}


def all_routes() -> list[tuple[str, str]]:
    # The OpenAPI schema lists every route, including those of included routers.
    return sorted((method.upper(), path) for path, ops in app.openapi()["paths"].items() for method in ops)


def concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", path)


def call(client, method: str, path: str):
    return client.request(method, concrete(path), json={} if method not in SAFE else None)


PROTECTED = [r for r in all_routes() if r not in PUBLIC]


def test_route_inventory_is_complete():
    # Fails when a route is added, so its protection is a deliberate decision recorded here.
    assert len(all_routes()) == 56
    assert PUBLIC <= set(all_routes())


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_every_non_public_route_requires_a_session(api, client, method, path):  # noqa: F811
    assert call(client, method, path).status_code == 401


def test_every_write_requires_csrf(api):  # noqa: F811
    user = api.user()
    del user.headers[CSRF_HEADER]
    unsafe = [(m, p) for m, p in PROTECTED if m not in SAFE]
    assert unsafe
    for method, path in unsafe:
        response = call(user, method, path)
        assert response.status_code == 403, (method, path, response.status_code)
        assert response.json()["detail"] == "Missing or invalid CSRF token."


def test_staff_and_admin_routes_enforce_roles(api):  # noqa: F811
    user, staff = api.user(), api.user(UserRole.STAFF)
    for method, path in PROTECTED:
        if path.startswith(("/api/staff/", "/api/admin/")):
            assert call(user, method, path).status_code == 403, (method, path)
        if path.startswith("/api/admin/"):
            assert call(staff, method, path).status_code == 403, (method, path)


# Headers and limits

def test_security_headers(api, client):  # noqa: F811
    headers = client.get("/api/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in headers  # HSTS only in production
    assert "content-security-policy" not in client.get("/api/docs").headers  # docs page needs its scripts
    assert client.post("/api/auth/login", json={}).headers["x-frame-options"] == "DENY"  # errors too


def test_image_responses_keep_their_own_cache_policy(api):  # noqa: F811
    owner = api.user()
    item = create(owner, api.db)
    image = upload(owner, item["id"], image_bytes()).json()
    headers = owner.get(image["url"]).headers
    assert headers["cache-control"].startswith("private")
    assert headers["content-security-policy"] == "default-src 'none'; sandbox"


def test_oversized_bodies_rejected(api, client):  # noqa: F811
    limit = 5 * 1024 * 1024 + 1024 * 1024
    too_big = b"x" * (limit + 1)
    declared = client.post("/api/auth/login", content=too_big, headers={"Content-Type": "application/json"})
    assert declared.status_code == 413 and declared.json() == {"detail": "Request body is too large."}

    def chunks():  # no Content-Length: sent with chunked transfer encoding
        for _ in range(7):
            yield b"x" * (1024 * 1024)

    streamed = client.post("/api/auth/login", content=chunks(), headers={"Content-Type": "application/json"})
    assert streamed.status_code == 413
    assert client.post("/api/auth/login", json={"email": "a@example.edu", "password": "x"}).status_code == 401


def test_production_disables_api_docs():
    env = os.environ | {"ENVIRONMENT": "production", "COOKIE_SECURE": "true", "EMAIL_BACKEND": "smtp",
                        "SMTP_HOST": "smtp.example.edu", "ALLOWED_EMAIL_DOMAINS": "example.edu"}
    code = ("from app.main import app, is_production; "
            "assert is_production and app.docs_url is None and app.openapi_url is None; print('ok')")
    result = subprocess.run([sys.executable, "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_unhandled_errors_do_not_leak_details(api, monkeypatch):  # noqa: F811
    def boom(*args, **kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(auth_service, "login", boom)
    with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as raw:
        response = raw.post("/api/auth/login", json={"email": "a@example.edu", "password": "whatever"})
    assert response.status_code == 500
    assert "secret internal detail" not in response.text and "Traceback" not in response.text


# Authentication hardening

def test_successful_logins_do_not_count_towards_account_lockout(api):  # noqa: F811
    api.user()
    client = api._make_client()
    for _ in range(12):
        assert client.post("/api/auth/login", json={"email": "user1@example.edu",
                                                    "password": "correct horse battery"}).status_code == 200


def test_duplicate_registration_spends_the_same_hashing_work(api, client, monkeypatch):  # noqa: F811
    api.user()
    calls = []
    real = auth_service.hash_password
    monkeypatch.setattr(auth_service, "hash_password", lambda p: calls.append(p) or real(p))
    body = {"name": "Someone", "email": "user1@example.edu", "password": "some other password",
            "campus_id": "RA2111003010999", "department": "Physics"}
    assert client.post("/api/auth/register", json=body).status_code == 202
    assert len(calls) == 1


def test_email_delivery_failure_does_not_break_the_request(api, client, outbox, monkeypatch, caplog):  # noqa: F811
    def broken(email):
        raise OSError("SMTP down")

    monkeypatch.setattr(outbox, "send", broken)
    body = {"name": "New Person", "email": "new@example.edu", "password": "correct horse battery",
            "campus_id": "RA2111003010998", "department": "Physics"}
    assert client.post("/api/auth/register", json=body).status_code == 202
    assert "Failed to deliver email" in caplog.text


# Concurrency

def test_status_guard_blocks_lost_updates(flow):  # noqa: F811
    """Staff load a pending claim; before they write, the claimant withdraws it. The approval must fail."""
    f = flow
    cid = submit(f.owner, f.found["id"]).json()["id"]
    staff_session = sessionmaker(bind=f.db.get_bind(), autoflush=False, expire_on_commit=False)()
    try:
        staff = staff_session.scalar(select(User).where(User.role == UserRole.STAFF))
        stale = claim_service.get_for_review(staff_session, staff, cid)
        assert stale.status == ClaimStatus.PENDING
        staff_session.commit()  # end the read transaction, as a separate request would

        assert f.owner.post(f"/api/claims/{cid}/withdraw").status_code == 200

        with pytest.raises(ServiceError) as exc:
            lock_status(staff_session, Claim, cid, (ClaimStatus.PENDING,), "Only pending claims can be approved.")
        assert exc.value.status_code == 409
    finally:
        staff_session.close()
    f.db.expire_all()
    assert f.db.get(Claim, cid).status == ClaimStatus.WITHDRAWN
