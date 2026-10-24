"""Audit log helper. Callers commit; never pass secrets, tokens, passwords or claim evidence."""

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def record(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    actor_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, details=details))
