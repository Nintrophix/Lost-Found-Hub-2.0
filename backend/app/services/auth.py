"""Authentication business logic: registration, sessions and passwords.

Each public function is one transaction: it commits on success and leaves rollback to the caller
(the request-scoped session is closed, discarding uncommitted work) on error.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.rate_limit import allow_for_key, is_limited_for_key, record_for_key
from app.core.security import (
    burn_password_check,
    generate_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
)
from app.db.enums import AccountStatus, UserRole
from app.db.models import PasswordResetToken, User, UserSession
from app.db.types import utcnow
from app.services import audit
from app.services.email import EmailSender, OutgoingEmail
from app.services.errors import ServiceError

INVALID_CREDENTIALS = "Incorrect email or password."
INVALID_LINK = "This link is invalid or has expired."
EMAIL_TAKEN = "An account with this email already exists. Sign in, or reset your password if you have forgotten it."
LAST_SEEN_RESOLUTION = timedelta(minutes=5)
LOGIN_FAILURE_LIMIT = 10
LOGIN_FAILURE_WINDOW = 900  # seconds

@dataclass(frozen=True)
class IssuedSession:
    user: User
    session_token: str
    csrf_token: str
    expires_at: datetime


def normalise_email(email: str) -> str:
    return email.strip().lower()


def email_domain_allowed(email: str, settings: Settings) -> bool:
    return email.rsplit("@", 1)[-1].lower() in settings.allowed_email_domains


def domain_error(settings: Settings) -> str:
    domains = " or ".join(f"@{d}" for d in settings.allowed_email_domains)
    return f"Only {domains} email addresses can use this service."


def _user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def _issue_user_token(db: Session, model: type[PasswordResetToken], user: User, ttl: timedelta) -> str:
    """Create a single-use token, replacing any unconsumed token of the same kind."""
    db.execute(delete(model).where(model.user_id == user.id, model.consumed_at.is_(None)))
    raw = generate_token()
    db.add(model(user_id=user.id, token_hash=hash_token(raw), expires_at=utcnow() + ttl))
    return raw


def _consume_user_token(db: Session, model: type[PasswordResetToken], raw: str) -> User:
    token = db.scalar(select(model).where(model.token_hash == hash_token(raw)))
    if token is None or token.consumed_at is not None or token.expires_at <= utcnow():
        raise ServiceError(400, INVALID_LINK)
    token.consumed_at = utcnow()
    # Flush now so later bulk deletes of "unconsumed" tokens in the same transaction skip this one.
    db.flush()
    return db.get(User, token.user_id)


def _revoke_sessions(db: Session, user_id: int, keep_session_id: int | None = None) -> None:
    stmt = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if keep_session_id is not None:
        stmt = stmt.where(UserSession.id != keep_session_id)
    db.execute(stmt.values(revoked_at=utcnow()))


def _send_password_reset(db: Session, sender: EmailSender, settings: Settings, user: User) -> None:
    raw = _issue_user_token(db, PasswordResetToken, user, timedelta(minutes=settings.password_reset_ttl_minutes))
    link = f"{settings.frontend_base_url}/reset-password#token={raw}"
    sender.send(
        OutgoingEmail(
            to=user.email,
            subject="Reset your password",
            body=(
                f"Hello {user.name},\n\nUse this link to choose a new password:\n{link}\n\n"
                f"This link expires in {settings.password_reset_ttl_minutes} minutes. If you did not ask for a "
                "reset, you can ignore this email."
            ),
        )
    )


def _issue_session(db: Session, settings: Settings, user: User) -> IssuedSession:
    session_token, csrf_token = generate_token(), generate_token()
    expires_at = utcnow() + timedelta(hours=settings.session_ttl_hours)
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(session_token),
            csrf_token_hash=hash_token(csrf_token),
            expires_at=expires_at,
        )
    )
    return IssuedSession(user=user, session_token=session_token, csrf_token=csrf_token, expires_at=expires_at)


def register(
    db: Session,
    settings: Settings,
    name: str,
    email: str,
    password: str,
    campus_id: str,
    department: str,
    phone: str | None,
) -> IssuedSession:
    """Create a USER account and sign it in. There is no email confirmation step."""
    email = normalise_email(email)
    if not email_domain_allowed(email, settings):
        raise ServiceError(422, domain_error(settings))
    if _user_by_email(db, email) is not None:
        raise ServiceError(409, EMAIL_TAKEN)
    if db.scalar(select(User.id).where(User.campus_id == campus_id)) is not None:
        raise ServiceError(
            409, "This SRM ID is already linked to an account. If it is yours, reset that account's password."
        )
    user = User(name=name, email=email, password_hash=hash_password(password), role=UserRole.USER,
                campus_id=campus_id, department=department, phone=phone)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        # A concurrent registration claimed the email or SRM ID first.
        db.rollback()
        raise ServiceError(409, EMAIL_TAKEN) from None
    audit.record(db, "auth.registered", "user", user.id, actor_id=user.id)
    issued = _issue_session(db, settings, user)
    audit.record(db, "auth.login", "user", user.id, actor_id=user.id)
    db.commit()
    return issued


def login(db: Session, settings: Settings, email: str, password: str) -> IssuedSession:
    email = normalise_email(email)
    # Only failed attempts count towards the per-account limit, so normal sign-ins never lock anyone out.
    if is_limited_for_key("login-failures", email, LOGIN_FAILURE_LIMIT, LOGIN_FAILURE_WINDOW):
        raise ServiceError(429, "Too many sign-in attempts for this account. Try again later.",
                           {"Retry-After": str(LOGIN_FAILURE_WINDOW)})

    user = _user_by_email(db, email)
    if user is None:
        burn_password_check(password)
        record_for_key("login-failures", email)
        raise ServiceError(401, INVALID_CREDENTIALS)
    if not verify_password(user.password_hash, password):
        record_for_key("login-failures", email)
        audit.record(db, "auth.login_failed", "user", user.id)
        db.commit()
        raise ServiceError(401, INVALID_CREDENTIALS)
    # Account state is only disclosed after the password is proven.
    if not email_domain_allowed(user.email, settings):
        raise ServiceError(403, domain_error(settings))
    if user.account_status != AccountStatus.ACTIVE:
        raise ServiceError(403, "This account is not active. Contact campus support.")

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    issued = _issue_session(db, settings, user)
    audit.record(db, "auth.login", "user", user.id, actor_id=user.id)
    db.commit()
    return issued


def resolve_session(db: Session, raw_token: str) -> UserSession | None:
    """Return the live session for a cookie value, or None if it is unknown, expired, revoked or its user is barred."""
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(raw_token)))
    now = utcnow()
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        return None
    user = session.user
    if user.account_status != AccountStatus.ACTIVE:
        return None
    # Checked on every request, so narrowing ALLOWED_EMAIL_DOMAINS takes effect for live sessions too.
    if not email_domain_allowed(user.email, get_settings()):
        return None
    if now - session.last_seen_at >= LAST_SEEN_RESOLUTION:
        session.last_seen_at = now
        db.commit()
    return session


def logout(db: Session, session: UserSession) -> None:
    session.revoked_at = utcnow()
    audit.record(db, "auth.logout", "user", session.user_id, actor_id=session.user_id)
    db.commit()


def forgot_password(db: Session, sender: EmailSender, settings: Settings, email: str) -> None:
    email = normalise_email(email)
    user = _user_by_email(db, email)
    if (
        user is not None
        and user.account_status == AccountStatus.ACTIVE
        and allow_for_key("forgot-password", email, 3, 3600)
    ):
        _send_password_reset(db, sender, settings, user)
        db.commit()


def reset_password(db: Session, raw_token: str, new_password: str) -> None:
    user = _consume_user_token(db, PasswordResetToken, raw_token)
    user.password_hash = hash_password(new_password)
    db.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id, PasswordResetToken.consumed_at.is_(None)
        )
    )
    _revoke_sessions(db, user.id)
    audit.record(db, "auth.password_reset", "user", user.id, actor_id=user.id)
    db.commit()


def change_password(db: Session, session: UserSession, current_password: str, new_password: str) -> None:
    user = session.user
    if not verify_password(user.password_hash, current_password):
        raise ServiceError(400, "Current password is incorrect.")
    user.password_hash = hash_password(new_password)
    _revoke_sessions(db, user.id, keep_session_id=session.id)
    audit.record(db, "auth.password_changed", "user", user.id, actor_id=user.id)
    db.commit()


def update_profile(db: Session, user: User, changes: dict) -> User:
    """Update the signed-in user's own name, department or phone. Email and SRM ID are fixed."""
    changed = sorted(field for field, value in changes.items() if getattr(user, field) != value)
    for field in changed:
        setattr(user, field, changes[field])
    if changed:
        audit.record(db, "user.profile_updated", "user", user.id, actor_id=user.id, details={"fields": changed})
        db.commit()
    return user


def update_user(
    db: Session, actor: User, user_id: int, role: UserRole | None, account_status: AccountStatus | None
) -> User:
    """Admin-only change of another user's role or account status."""
    target = db.get(User, user_id)
    if target is None:
        raise ServiceError(404, "User not found.")
    if target.id == actor.id:
        raise ServiceError(400, "You cannot change your own role or account status.")

    changes: dict[str, list[str]] = {}
    if role is not None and role != target.role:
        changes["role"] = [target.role.value, role.value]
        target.role = role
    if account_status is not None and account_status != target.account_status:
        changes["account_status"] = [target.account_status.value, account_status.value]
        target.account_status = account_status
        if account_status != AccountStatus.ACTIVE:
            _revoke_sessions(db, target.id)

    if changes:
        audit.record(db, "admin.user_updated", "user", target.id, actor_id=actor.id, details=changes)
        db.commit()
    return target
