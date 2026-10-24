"""Housekeeping: remove dead sessions and tokens, expired QR hashes and orphaned upload files."""

from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.enums import HandoverStatus
from app.db.models import HandoverRecord, PasswordResetToken, ReportImage, UserSession
from app.db.types import utcnow
from app.services import audit

# An upload writes its file before its database row commits; skip files younger than this.
ORPHAN_GRACE = timedelta(hours=1)


def _orphan_files(db: Session, settings: Settings, now: datetime) -> list[Path]:
    folder = Path(settings.upload_dir) / "items"
    if not folder.is_dir():
        return []
    known = set(db.scalars(select(ReportImage.stored_filename)))
    cutoff = now.timestamp() - ORPHAN_GRACE.total_seconds()
    return [p for p in folder.iterdir() if p.is_file() and p.name not in known and p.stat().st_mtime < cutoff]


def cleanup(db: Session, settings: Settings, dry_run: bool = False) -> dict[str, int]:
    """Returns counts of what was (or, with dry_run, would be) removed."""
    now = utcnow()
    dead_sessions = or_(UserSession.expires_at <= now, UserSession.revoked_at.is_not(None))
    stale_qr = (HandoverRecord.status == HandoverStatus.SCHEDULED, HandoverRecord.qr_expires_at <= now)

    def dead_tokens(model):
        return or_(model.expires_at <= now, model.consumed_at.is_not(None))

    def count(model, *conditions) -> int:
        return db.scalar(select(func.count(model.id)).where(*conditions)) or 0

    orphans = _orphan_files(db, settings, now)
    result = {
        "sessions": count(UserSession, dead_sessions),
        "password_reset_tokens": count(PasswordResetToken, dead_tokens(PasswordResetToken)),
        "expired_qr_codes": count(HandoverRecord, *stale_qr),
        "orphaned_files": len(orphans),
    }
    if dry_run:
        return result

    db.execute(delete(UserSession).where(dead_sessions))
    db.execute(delete(PasswordResetToken).where(dead_tokens(PasswordResetToken)))
    # Clearing an expired hash keeps the handover SCHEDULED; the claimant simply generates a new code.
    db.execute(update(HandoverRecord).where(*stale_qr).values(qr_token_hash=None, qr_expires_at=None,
                                                                updated_at=now))
    audit.record(db, "cli.cleanup", "system", details=result)
    db.commit()
    for path in orphans:
        path.unlink(missing_ok=True)
    return result

