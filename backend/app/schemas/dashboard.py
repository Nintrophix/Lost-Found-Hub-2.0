"""Contracts for personal, staff and admin dashboards. Every number comes from the database."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.auth import UserResponse
from app.schemas.claims import ClaimResponse
from app.schemas.items import ItemResponse
from app.schemas.matches import MatchResponse

# Status name -> count, with every status present (zero when none).
StatusCounts = dict[str, int]


class PublicStats(BaseModel):
    """Aggregate counts only; never item details, which require sign-in."""

    open_lost_reports: int
    found_items_waiting: int
    items_returned: int


class UserDashboard(BaseModel):
    reports: dict[str, StatusCounts]  # keyed by report type, then item status
    recent_reports: list[ItemResponse]
    claims: StatusCounts
    active_claims: list[ClaimResponse]
    suggestion_count: int
    top_suggestions: list[MatchResponse]
    unread_notifications: int


class StaffDashboard(BaseModel):
    pending_claims: int
    oldest_pending_claim_at: datetime | None
    approved_awaiting_handover: int
    handovers: StatusCounts
    completed_last_7_days: int
    open_found_reports: int
    high_score_suggestions: int
    high_score_threshold: float


class BreakdownRow(BaseModel):
    id: int
    name: str
    lost: int
    found: int


class MonthRow(BaseModel):
    month: str  # YYYY-MM (UTC)
    lost: int
    found: int


class UserStats(BaseModel):
    total: int
    by_role: StatusCounts
    by_status: StatusCounts
    verified: int


class AdminStats(BaseModel):
    generated_at: datetime
    created_from: datetime | None
    created_to: datetime | None
    users: UserStats
    reports: dict[str, StatusCounts]
    claims: StatusCounts
    handovers: StatusCounts
    matches: StatusCounts
    by_category: list[BreakdownRow]
    by_location: list[BreakdownRow]
    monthly: list[MonthRow]
    found_return_rate: float | None  # returned FOUND reports / FOUND reports, in range
    median_hours_to_return: float | None


class UserPage(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int


class AuditLogResponse(BaseModel):
    id: int
    actor_id: int | None
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: int | None
    details: dict[str, Any] | None
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
