"""Contracts for match suggestions and notifications."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.enums import MatchStatus, NotificationType
from app.schemas.items import ItemResponse


class MatchReason(BaseModel):
    signal: str
    weight: float
    value: float | None
    points: float
    detail: str


class MatchResponse(BaseModel):
    id: int
    score: float
    status: MatchStatus
    reasons: list[MatchReason]
    lost_item_id: int
    found_item_id: int
    created_at: datetime
    updated_at: datetime
    # The report on the other side of the match from the item being viewed (or the found item for staff lists).
    counterpart: ItemResponse


class StaffMatchResponse(BaseModel):
    id: int
    score: float
    status: MatchStatus
    reasons: list[MatchReason]
    lost_item: ItemResponse
    found_item: ItemResponse
    created_at: datetime
    updated_at: datetime


class StaffMatchPage(BaseModel):
    items: list[StaffMatchResponse]
    total: int
    page: int
    page_size: int


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: NotificationType
    title: str
    message: str
    item_id: int | None
    claim_id: int | None
    read_at: datetime | None
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread: int
    page: int
    page_size: int
