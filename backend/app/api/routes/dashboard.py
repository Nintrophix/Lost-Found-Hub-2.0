"""Signed-in user's personal dashboard under /api/dashboard."""

from fastapi import APIRouter

from app.api import presenters
from app.api.deps import CurrentUser, DbSession
from app.schemas.dashboard import UserDashboard
from app.services import dashboard as dashboard_service
from app.services import items as item_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def my_dashboard(user: CurrentUser, db: DbSession) -> UserDashboard:
    data = dashboard_service.user_dashboard(db, user)
    return UserDashboard(
        reports=data["reports"],
        recent_reports=[item_service.to_response(i, user) for i in data["recent_reports"]],
        claims=data["claims"],
        active_claims=[presenters.claim_response(c, user) for c in data["active_claims"]],
        suggestion_count=data["suggestion_count"],
        top_suggestions=[presenters.match_response(m, other, user) for m, other in data["top_suggestions"]],
        unread_notifications=data["unread_notifications"],
    )
