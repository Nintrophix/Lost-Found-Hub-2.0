"""Authentication, session, CSRF, password and role tests against the real API and a migrated database."""

import re
from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.api.deps import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from app.cli import create_admin, set_role
from app.core.config import Settings
from app.core.security import hash_password, hash_token, verify_password
from app.db.enums import AccountStatus, UserRole
from app.db.models import AuditLog, EmailVerificationToken, User, UserSession
from app.db.types import utcnow

PASSWORD = "correct horse battery"
NEW_PASSWORD = "another long passphrase"
GENERIC_MESSAGE = "If this address can receive one, we have sent an email with the next step."


def token_from(outbox, index: int = -1) -> str:
    match = re.search(r"#token=(\S+)", outbox.outbox[index].body)
    assert match, outbox.outbox[index].body
    return match.group(1)


PROFILE = {"campus_id": "RA2111003010123", "department": "Computer Science and Engineering"}


def register(client, email="alex@example.edu", password=PASSWORD, name="Alex Doe", **profile):
    body = {"name": name, "email": email, "password": password, **PROFILE, **profile}
    return client.post("/api/auth/register", json=body)


def login(client, email="alex@example.edu", password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def csrf(client) -> dict[str, str]:
    return {CSRF_HEADER: client.cookies.get(CSRF_COOKIE)}


@pytest.fixture
def verified_user(client, outbox):
    """Register and verify alex@example.edu, then return the client (not signed in)."""
    assert register(client).status_code == 202
    assert client.post("/api/auth/verify-email", json={"token": token_from(outbox)}).status_code == 200
    return client


@pytest.fixture
def signed_in(verified_user):
    assert login(verified_user).status_code == 200
    return verified_user


def make_verified(db, email: str, role: UserRole = UserRole.USER) -> User:
    user = User(name="Seeded", email=email, password_hash=hash_password(PASSWORD), role=role,
                email_verified_at=utcnow())
    db.add(user)
    db.commit()
    return user


# Registration and verification

def test_full_registration_flow(client, outbox, db):
    response = register(client, email="  Alex@Example.EDU ")
    assert response.status_code == 202
    assert response.json() == {"message": GENERIC_MESSAGE}

    user = db.scalar(select(User).where(User.email == "alex@example.edu"))
    assert user.role == UserRole.USER and user.email_verified_at is None
    assert user.password_hash != PASSWORD and verify_password(user.password_hash, PASSWORD)

    raw = token_from(outbox)
    stored = db.scalar(select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id))
    assert stored.token_hash == hash_token(raw) and raw not in stored.token_hash
    assert outbox.outbox[-1].to == "alex@example.edu"

    assert login(client).status_code == 403  # not verified yet
    assert client.post("/api/auth/verify-email", json={"token": raw}).status_code == 200
    assert client.post("/api/auth/verify-email", json={"token": raw}).status_code == 400  # single use

    response = login(client)
    assert response.status_code == 200
    assert response.json()["email_verified"] is True
    assert "password_hash" not in response.json()

    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["email"] == "alex@example.edu"


def test_registration_rejects_non_campus_domain(client, outbox):
    response = register(client, email="alex@gmail.com")
    assert response.status_code == 422
    assert outbox.outbox == []


def test_registration_cannot_request_elevated_role(client, db):
    response = client.post(
        "/api/auth/register",
        json={"name": "Eve", "email": "eve@example.edu", "password": PASSWORD, "role": "ADMIN", **PROFILE},
    )
    assert response.status_code == 422
    assert db.scalar(select(User).where(User.email == "eve@example.edu")) is None


# Profile fields

def test_registration_stores_profile_details(client, outbox, db):
    response = register(client, campus_id=" ra 2111003010123 ", phone="+91 98765-43210")
    assert response.status_code == 202
    user = db.scalar(select(User).where(User.email == "alex@example.edu"))
    assert (user.campus_id, user.department, user.phone) == (
        "RA2111003010123", "Computer Science and Engineering", "+919876543210",
    )
    client.post("/api/auth/verify-email", json={"token": token_from(outbox)})
    body = login(client).json()
    assert body["campus_id"] == "RA2111003010123" and body["phone"] == "+919876543210"


@pytest.mark.parametrize(
    "profile",
    [{"campus_id": ""}, {"campus_id": "RA-21"}, {"campus_id": "A" * 21}, {"department": "x"},
     {"phone": "12345"}, {"phone": "call me"}, {"campus_id": None}],
)
def test_registration_validates_profile(client, profile):
    assert register(client, **profile).status_code == 422


def test_srm_id_is_unique(client, outbox):
    assert register(client).status_code == 202
    response = register(client, email="someone.else@example.edu")
    assert response.status_code == 409 and "SRM ID" in response.json()["detail"]
    assert len(outbox.outbox) == 1  # nothing was sent for the rejected sign-up


def test_profile_update(signed_in, db):
    url = "/api/auth/me"
    response = signed_in.patch(url, json={"department": "Mechanical Engineering", "phone": "9876543210"},
                               headers=csrf(signed_in))
    assert response.status_code == 200
    assert response.json()["department"] == "Mechanical Engineering" and response.json()["phone"] == "9876543210"
    assert signed_in.patch(url, json={"phone": None}, headers=csrf(signed_in)).json()["phone"] is None
    assert signed_in.patch(url, json={"name": None}, headers=csrf(signed_in)).json()["name"] == "Alex Doe"
    for fixed in ({"email": "new@example.edu"}, {"campus_id": "RA0000000000001"}, {"role": "ADMIN"}):
        assert signed_in.patch(url, json=fixed, headers=csrf(signed_in)).status_code == 422
    assert signed_in.patch(url, json={"department": "Civil"}).status_code == 403  # CSRF
    log = db.scalar(select(AuditLog).where(AuditLog.action == "user.profile_updated"))
    assert log.details == {"fields": ["department", "phone"]} and "9876543210" not in str(log.details)


# Allowed email domain

def test_only_allowed_domain_can_register(client, outbox):
    response = register(client, email="alex@gmail.com")
    assert response.status_code == 422 and "@example.edu" in response.json()["detail"]
    assert register(client, email="alex@sub.example.edu").status_code == 422  # exact match only
    assert outbox.outbox == []


def test_other_domains_blocked_at_login_and_on_every_request(signed_in, make_client, db):
    # An account from a domain that is no longer allowed (e.g. after ALLOWED_EMAIL_DOMAINS changed).
    outsider = make_verified(db, "outsider@gmail.com")
    other = make_client()
    response = login(other, "outsider@gmail.com")
    assert response.status_code == 403 and "@example.edu" in response.json()["detail"]
    assert other.cookies.get(SESSION_COOKIE) is None

    # A live session stops working as soon as its email is outside the allowed domains.
    user = db.scalar(select(User).where(User.email == "alex@example.edu"))
    user.email = "alex@gmail.com"
    db.commit()
    assert signed_in.get("/api/auth/me").status_code == 401
    assert signed_in.get("/api/auth/session").json()["user"] is None
    assert outsider.id


def test_session_reports_allowed_domains(client):
    assert client.get("/api/auth/session").json() == {"user": None, "allowed_email_domains": ["example.edu"]}


def test_eight_character_password_is_accepted(client):
    assert register(client, password="abcd1234").status_code == 202


@pytest.mark.parametrize("password", ["short", "seven77", " " * 20, "x" * 129])
def test_registration_enforces_password_policy(client, password):
    assert register(client, password=password).status_code == 422


def test_duplicate_registration_does_not_reveal_or_overwrite(verified_user, outbox, db):
    response = register(verified_user, password="attacker chosen password", name="Mallory")
    assert response.status_code == 202
    assert response.json() == {"message": GENERIC_MESSAGE}
    assert outbox.outbox[-1].subject == "You already have an account"
    user = db.scalar(select(User).where(User.email == "alex@example.edu"))
    db.refresh(user)
    assert user.name == "Alex Doe" and verify_password(user.password_hash, PASSWORD)


def test_expired_verification_token_rejected(client, outbox, db):
    register(client)
    raw = token_from(outbox)
    token = db.scalar(select(EmailVerificationToken))
    token.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.post("/api/auth/verify-email", json={"token": raw}).status_code == 400


def test_resend_verification_replaces_old_token(client, outbox):
    register(client)
    first = token_from(outbox)
    assert client.post("/api/auth/resend-verification", json={"email": "alex@example.edu"}).status_code == 202
    second = token_from(outbox)
    assert first != second
    assert client.post("/api/auth/verify-email", json={"token": first}).status_code == 400
    assert client.post("/api/auth/verify-email", json={"token": second}).status_code == 200


# Login and sessions

def test_login_failures_are_generic(verified_user):
    wrong = login(verified_user, password="wrong password here")
    unknown = login(verified_user, email="nobody@example.edu")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Incorrect email or password."}


def test_session_cookie_flags_and_hashed_storage(verified_user, db):
    response = login(verified_user)
    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith(f"{SESSION_COOKIE}="))
    csrf_cookie = next(c for c in cookies if c.startswith(f"{CSRF_COOKIE}="))
    for cookie in (session_cookie, csrf_cookie):
        assert "Secure" in cookie and "samesite=lax" in cookie.lower()
    assert "HttpOnly" in session_cookie and "HttpOnly" not in csrf_cookie

    raw = verified_user.cookies.get(SESSION_COOKIE)
    stored = db.scalar(select(UserSession))
    assert stored.token_hash == hash_token(raw)
    assert stored.csrf_token_hash == hash_token(verified_user.cookies.get(CSRF_COOKIE))


def test_session_endpoint_never_errors(signed_in, make_client):
    assert make_client().get("/api/auth/session").json()["user"] is None
    body = signed_in.get("/api/auth/session").json()
    assert body["user"]["email"] == "alex@example.edu" and "password_hash" not in body["user"]


def test_me_requires_session(client):
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set(SESSION_COOKIE, "forged-token")
    assert client.get("/api/auth/me").status_code == 401


def test_logout_requires_csrf_and_revokes_session(signed_in):
    assert signed_in.post("/api/auth/logout").status_code == 403
    assert signed_in.post("/api/auth/logout", headers={CSRF_HEADER: "wrong"}).status_code == 403

    raw = signed_in.cookies.get(SESSION_COOKIE)
    assert signed_in.post("/api/auth/logout", headers=csrf(signed_in)).status_code == 204
    assert signed_in.cookies.get(SESSION_COOKIE) is None

    signed_in.cookies.set(SESSION_COOKIE, raw)  # replaying the old cookie must fail
    assert signed_in.get("/api/auth/me").status_code == 401


def test_expired_session_rejected(signed_in, db):
    session = db.scalar(select(UserSession))
    session.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert signed_in.get("/api/auth/me").status_code == 401


def test_suspended_user_cannot_sign_in(verified_user, db):
    user = db.scalar(select(User))
    user.account_status = AccountStatus.SUSPENDED
    db.commit()
    response = login(verified_user)
    assert response.status_code == 403
    assert verified_user.cookies.get(SESSION_COOKIE) is None


def test_login_events_are_audited_without_secrets(signed_in, db):
    login(signed_in, password="wrong password here")
    actions = [log.action for log in db.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert actions == ["auth.registered", "auth.email_verified", "auth.login", "auth.login_failed"]
    for log in db.scalars(select(AuditLog)):
        assert PASSWORD not in str(log.details)


# Passwords

def test_forgot_password_unknown_email_is_silent(client, outbox):
    response = client.post("/api/auth/password/forgot", json={"email": "ghost@example.edu"})
    assert response.status_code == 202 and response.json() == {"message": GENERIC_MESSAGE}
    assert outbox.outbox == []


def test_password_reset_flow(signed_in, make_client, outbox):
    other_device = make_client()
    assert login(other_device).status_code == 200

    assert signed_in.post("/api/auth/password/forgot", json={"email": "alex@example.edu"}).status_code == 202
    raw = token_from(outbox)
    body = {"token": raw, "new_password": NEW_PASSWORD}
    assert signed_in.post("/api/auth/password/reset", json=body).status_code == 200
    assert signed_in.post("/api/auth/password/reset", json=body).status_code == 400  # single use

    assert signed_in.get("/api/auth/me").status_code == 401  # all sessions revoked
    assert other_device.get("/api/auth/me").status_code == 401
    assert login(signed_in).status_code == 401
    assert login(signed_in, password=NEW_PASSWORD).status_code == 200


def test_password_reset_verifies_unverified_email(client, outbox, db):
    register(client)
    client.post("/api/auth/password/forgot", json={"email": "alex@example.edu"})
    client.post("/api/auth/password/reset", json={"token": token_from(outbox), "new_password": NEW_PASSWORD})
    assert login(client, password=NEW_PASSWORD).status_code == 200


def test_change_password_keeps_current_session_only(signed_in, make_client):
    other_device = make_client()
    login(other_device)

    wrong = {"current_password": "not my password", "new_password": NEW_PASSWORD}
    assert signed_in.post("/api/auth/password/change", json=wrong, headers=csrf(signed_in)).status_code == 400

    body = {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    assert signed_in.post("/api/auth/password/change", json=body).status_code == 403  # CSRF
    assert signed_in.post("/api/auth/password/change", json=body, headers=csrf(signed_in)).status_code == 200
    assert signed_in.get("/api/auth/me").status_code == 200
    assert other_device.get("/api/auth/me").status_code == 401


# Roles

def test_non_admin_cannot_manage_users(signed_in, db):
    target = make_verified(db, "target@example.edu")
    response = signed_in.patch(f"/api/admin/users/{target.id}", json={"role": "ADMIN"}, headers=csrf(signed_in))
    assert response.status_code == 403


def test_admin_manages_roles_and_status(make_client, db):
    make_verified(db, "admin@example.edu", UserRole.ADMIN)
    target = make_verified(db, "target@example.edu")
    admin, target_client = make_client(), make_client()
    login(admin, "admin@example.edu")
    login(target_client, "target@example.edu")

    url = f"/api/admin/users/{target.id}"
    response = admin.patch(url, json={"role": "STAFF"}, headers=csrf(admin))
    assert response.status_code == 200 and response.json()["role"] == "STAFF"
    assert target_client.get("/api/auth/me").json()["role"] == "STAFF"

    response = admin.patch(url, json={"account_status": "SUSPENDED"}, headers=csrf(admin))
    assert response.status_code == 200
    assert target_client.get("/api/auth/me").status_code == 401

    log = db.scalar(select(AuditLog).where(AuditLog.action == "admin.user_updated").order_by(AuditLog.id))
    assert log.details == {"role": ["USER", "STAFF"]}

    admin_id = db.scalar(select(User.id).where(User.email == "admin@example.edu"))
    response = admin.patch(f"/api/admin/users/{admin_id}", json={"role": "USER"}, headers=csrf(admin))
    assert response.status_code == 400
    assert admin.patch("/api/admin/users/99999", json={"role": "USER"}, headers=csrf(admin)).status_code == 404


# Rate limiting

def test_login_rate_limited_per_account(verified_user):
    for _ in range(10):
        assert login(verified_user, password="wrong password here").status_code == 401
    response = login(verified_user)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "900"


def test_login_rate_limited_per_ip(client):
    for n in range(20):
        assert login(client, email=f"user{n}@example.edu").status_code == 401
    response = login(client, email="another@example.edu")
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


# CLI and configuration

def test_cli_creates_verified_admin_and_sets_roles(db):
    admin = create_admin(db, "Head@Example.edu", "Campus Admin", PASSWORD)
    assert admin.email == "head@example.edu" and admin.role == UserRole.ADMIN and admin.is_email_verified
    with pytest.raises(SystemExit):
        create_admin(db, "head@example.edu", "Again", PASSWORD)
    with pytest.raises(SystemExit):
        create_admin(db, "x@gmail.com", "Outsider", PASSWORD)
    with pytest.raises(ValidationError):
        create_admin(db, "weak@example.edu", "Weak", "short")
    assert set_role(db, "head@example.edu", UserRole.STAFF).role == UserRole.STAFF


@pytest.mark.parametrize(
    "overrides",
    [{"email_backend": "console"}, {"email_backend": "smtp", "smtp_host": "smtp.example.edu", "cookie_secure": False}],
)
def test_production_settings_reject_unsafe_values(overrides):
    with pytest.raises(ValidationError):
        Settings(environment="production", allowed_email_domains=["example.edu"], **overrides)


def test_settings_require_email_domains():
    with pytest.raises(ValidationError):
        Settings(allowed_email_domains=[])
