"""In-app notifications for the signed-in user."""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.models import Notification, User
from app.db.types import utcnow
from app.services.errors import ServiceError


def list_for_user(
    db: Session, user: User, unread_only: bool, page: int, page_size: int
) -> tuple[list[Notification], int, int]:
    """Returns (page of notifications newest first, total matching, unread count)."""
    conditions = [Notification.user_id == user.id]
    if unread_only:
        conditions.append(Notification.read_at.is_(None))
    total = db.scalar(select(func.count(Notification.id)).where(*conditions)) or 0
    unread = db.scalar(
        select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    ) or 0
    rows = db.scalars(
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total, unread


def mark_read(db: Session, user: User, notification_id: int) -> Notification:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise ServiceError(404, "Notification not found.")
    if notification.read_at is None:
        notification.read_at = utcnow()
        db.commit()
    return notification


def mark_all_read(db: Session, user: User) -> None:
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    db.commit()
