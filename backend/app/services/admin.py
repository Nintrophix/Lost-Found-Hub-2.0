"""Admin listings: users and audit logs."""

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.db.enums import AccountStatus, UserRole
from app.db.models import AuditLog, User
from app.services.items import escape_like

# Defence in depth: audit details are written without secrets, but never echo these keys if present.
SENSITIVE_KEYS = frozenset({"password", "password_hash", "token", "token_hash", "qr_token", "qr_token_hash",
                            "evidence", "csrf_token", "session_token"})


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: "[redacted]" if k.lower() in SENSITIVE_KEYS else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def list_users(
    db: Session,
    q: str | None,
    role: UserRole | None,
    account_status: AccountStatus | None,
    verified: bool | None,
    page: int,
    page_size: int,
) -> tuple[list[User], int]:
    conditions = []
    if q:
        pattern = f"%{escape_like(q)}%"
        conditions.append(or_(User.name.ilike(pattern, escape="\\"), User.email.ilike(pattern, escape="\\")))
    if role:
        conditions.append(User.role == role)
    if account_status:
        conditions.append(User.account_status == account_status)
    if verified is not None:
        conditions.append(User.email_verified_at.is_not(None) if verified else User.email_verified_at.is_(None))
    total = db.scalar(select(func.count(User.id)).where(*conditions)) or 0
    rows = db.scalars(
        select(User).where(*conditions).order_by(User.created_at.desc(), User.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows), total


def list_audit_logs(
    db: Session,
    actor_id: int | None,
    action: str | None,
    entity_type: str | None,
    entity_id: int | None,
    created_from: datetime | None,
    created_to: datetime | None,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    """Newest first. `action` matches exactly, or as a prefix when it ends with '.' (e.g. 'claim.')."""
    conditions = []
    if actor_id is not None:
        conditions.append(AuditLog.actor_id == actor_id)
    if action:
        conditions.append(
            AuditLog.action.like(f"{escape_like(action)}%", escape="\\") if action.endswith(".")
            else AuditLog.action == action
        )
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        conditions.append(AuditLog.entity_id == entity_id)
    if created_from:
        conditions.append(AuditLog.created_at >= created_from)
    if created_to:
        conditions.append(AuditLog.created_at <= created_to)

    actor = aliased(User)
    total = db.scalar(select(func.count(AuditLog.id)).where(*conditions)) or 0
    rows = db.execute(
        select(AuditLog, actor.email)
        .outerjoin(actor, actor.id == AuditLog.actor_id)
        .where(*conditions)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [
        {
            "id": log.id,
            "actor_id": log.actor_id,
            "actor_email": email,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": redact(log.details),
            "created_at": log.created_at,
        }
        for log, email in rows
    ], total
