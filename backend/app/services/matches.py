"""Reviewing match suggestions: list, confirm and dismiss. Confirming never approves a claim."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.enums import ItemStatus, MatchStatus
from app.db.models import Item, Match, User
from app.services import audit
from app.services import items as item_service
from app.services.concurrency import lock_status
from app.services.errors import ServiceError
from app.services.matching import MATCHABLE_STATUSES

MATCH_NOT_FOUND = "Match not found."


def match_query():
    item_options = (joinedload(Item.category), joinedload(Item.location), selectinload(Item.images))
    return select(Match).options(
        joinedload(Match.lost_item).options(*item_options), joinedload(Match.found_item).options(*item_options)
    )


def list_for_item(db: Session, user: User, item_id: int, include_dismissed: bool) -> list[tuple[Match, Item]]:
    """Matches for a report, best first, paired with the report on the other side."""
    item = item_service.get_manageable(db, user, item_id)
    stmt = match_query().where(or_(Match.lost_item_id == item.id, Match.found_item_id == item.id))
    if not include_dismissed:
        stmt = stmt.where(Match.status != MatchStatus.DISMISSED)
    rows = []
    for match in db.scalars(stmt.order_by(Match.score.desc(), Match.id)).unique():
        counterpart = match.found_item if match.lost_item_id == item.id else match.lost_item
        if counterpart.status == ItemStatus.CLOSED and not item_service.is_staff(user):
            continue
        rows.append((match, counterpart))
    return rows


def _get_for_action(db: Session, user: User, match_id: int) -> Match:
    match = db.scalar(match_query().where(Match.id == match_id))
    involved = match is not None and user.id in (match.lost_item.reporter_id, match.found_item.reporter_id)
    if match is None or not (involved or item_service.is_staff(user)):
        raise ServiceError(404, MATCH_NOT_FOUND)
    if match.status != MatchStatus.SUGGESTED:
        raise ServiceError(409, "This suggestion has already been reviewed.")
    lock_status(db, Match, match.id, (MatchStatus.SUGGESTED,), "This suggestion has already been reviewed.")
    return match


def confirm(db: Session, user: User, match_id: int) -> Match:
    """The owner of the lost report (or staff) agrees the found report looks like theirs."""
    match = _get_for_action(db, user, match_id)
    if user.id != match.lost_item.reporter_id and not item_service.is_staff(user):
        raise ServiceError(403, "Only the person who lost the item or campus staff can confirm a match.")
    if match.lost_item.status not in MATCHABLE_STATUSES or match.found_item.status not in MATCHABLE_STATUSES:
        raise ServiceError(409, "One of these reports is no longer open.")
    for item in (match.lost_item, match.found_item):
        lock_status(db, Item, item.id, MATCHABLE_STATUSES, "One of these reports is no longer open.")

    match.status = MatchStatus.CONFIRMED
    for item in (match.lost_item, match.found_item):
        if item.status == ItemStatus.OPEN:
            item.status = ItemStatus.MATCHED
    audit.record(db, "match.confirmed", "match", match.id, actor_id=user.id, details={"score": match.score})
    db.commit()
    return match


def dismiss(db: Session, user: User, match_id: int) -> Match:
    match = _get_for_action(db, user, match_id)
    match.status = MatchStatus.DISMISSED
    audit.record(db, "match.dismissed", "match", match.id, actor_id=user.id, details={"score": match.score})
    db.commit()
    return match


def staff_list(
    db: Session, status: MatchStatus | None, min_score: float, page: int, page_size: int
) -> tuple[list[Match], int]:
    conditions = [Match.score >= min_score]
    if status is not None:
        conditions.append(Match.status == status)
    total = db.scalar(select(func.count(Match.id)).where(*conditions)) or 0
    stmt = (
        match_query()
        .where(*conditions)
        .order_by(Match.score.desc(), Match.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).unique()), total
