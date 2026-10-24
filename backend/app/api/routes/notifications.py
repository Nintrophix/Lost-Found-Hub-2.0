"""The signed-in user's notifications under /api/notifications."""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.items import MAX_PAGE_SIZE
from app.schemas.matches import NotificationPage, NotificationResponse
from app.services import notifications as notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    user: CurrentUser,
    db: DbSession,
    unread_only: bool = False,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> NotificationPage:
    rows, total, unread = notification_service.list_for_user(db, user, unread_only, page, page_size)
    return NotificationPage(
        items=[NotificationResponse.model_validate(n) for n in rows],
        total=total,
        unread=unread,
        page=page,
        page_size=page_size,
    )


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, user: CurrentUser, db: DbSession) -> NotificationResponse:
    return NotificationResponse.model_validate(notification_service.mark_read(db, user, notification_id))


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(user: CurrentUser, db: DbSession) -> None:
    notification_service.mark_all_read(db, user)
