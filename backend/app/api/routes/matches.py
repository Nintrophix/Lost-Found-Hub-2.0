"""Match suggestion endpoints. Scores are recommendations only."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api import presenters
from app.api.deps import CurrentUser, DbSession, StaffUser
from app.db.enums import MatchStatus
from app.db.models import Item, Match, User
from app.schemas.items import MAX_PAGE_SIZE
from app.schemas.matches import MatchReason, MatchResponse, StaffMatchPage, StaffMatchResponse
from app.services import items as item_service
from app.services import matches as match_service

router = APIRouter(tags=["matches"])


def _counterpart_for(match: Match, user: User) -> Item:
    return match.lost_item if user.id == match.found_item.reporter_id else match.found_item


@router.get("/items/{item_id}/matches")
def list_item_matches(item_id: int, user: CurrentUser, db: DbSession,
                      include_dismissed: bool = False) -> list[MatchResponse]:
    rows = match_service.list_for_item(db, user, item_id, include_dismissed)
    return [presenters.match_response(match, counterpart, user) for match, counterpart in rows]


@router.post("/matches/{match_id}/confirm")
def confirm_match(match_id: int, user: CurrentUser, db: DbSession) -> MatchResponse:
    match = match_service.confirm(db, user, match_id)
    return presenters.match_response(match, _counterpart_for(match, user), user)


@router.post("/matches/{match_id}/dismiss")
def dismiss_match(match_id: int, user: CurrentUser, db: DbSession) -> MatchResponse:
    match = match_service.dismiss(db, user, match_id)
    return presenters.match_response(match, _counterpart_for(match, user), user)


@router.get("/staff/matches")
def staff_list_matches(
    staff: StaffUser,
    db: DbSession,
    match_status: Annotated[MatchStatus | None, Query(alias="status")] = MatchStatus.SUGGESTED,
    min_score: Annotated[float, Query(ge=0, le=100)] = 0,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> StaffMatchPage:
    rows, total = match_service.staff_list(db, match_status, min_score, page, page_size)
    return StaffMatchPage(
        items=[
            StaffMatchResponse(
                id=m.id,
                score=m.score,
                status=m.status,
                reasons=[MatchReason.model_validate(r) for r in m.reasons],
                lost_item=item_service.to_response(m.lost_item, staff),
                found_item=item_service.to_response(m.found_item, staff),
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
