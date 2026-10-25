"""Dashboard and statistics queries. Read-only; every figure is computed from the database."""

from datetime import datetime, timedelta
from enum import StrEnum
from statistics import median

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.enums import (
    AccountStatus,
    ClaimStatus,
    HandoverStatus,
    ItemStatus,
    MatchStatus,
    ReportType,
    UserRole,
)
from app.db.models import CampusLocation, Category, Claim, HandoverRecord, Item, Match, Notification, User
from app.db.types import utcnow
from app.services import claims as claim_service
from app.services import items as item_service
from app.services import matches as match_service

HIGH_SCORE = 80.0
RECENT_LIMIT = 5


def _counts(db: Session, column, enum_cls: type[StrEnum], *conditions: ColumnElement[bool]) -> dict[str, int]:
    rows = db.execute(select(column, func.count()).where(*conditions).group_by(column)).all()
    found = {value.value if isinstance(value, StrEnum) else value: n for value, n in rows}
    return {member.value: found.get(member.value, 0) for member in enum_cls}


def _report_counts(db: Session, *conditions: ColumnElement[bool]) -> dict[str, dict[str, int]]:
    return {t.value: _counts(db, Item.status, ItemStatus, Item.report_type == t, *conditions) for t in ReportType}


def public_stats(db: Session) -> dict:
    waiting = (ItemStatus.OPEN, ItemStatus.MATCHED)

    def count(*conditions: ColumnElement[bool]) -> int:
        return db.scalar(select(func.count(Item.id)).where(*conditions)) or 0

    return {
        "open_lost_reports": count(Item.report_type == ReportType.LOST, Item.status.in_(waiting)),
        "found_items_waiting": count(Item.report_type == ReportType.FOUND, Item.status.in_(waiting)),
        "items_returned": count(Item.report_type == ReportType.FOUND, Item.status == ItemStatus.RETURNED),
    }


def user_dashboard(db: Session, user: User) -> dict:
    db.flush()
    recent = db.scalars(
        item_service.item_query().where(Item.reporter_id == user.id).order_by(Item.created_at.desc(), Item.id.desc())
        .limit(RECENT_LIMIT)
    ).unique().all()

    active_claims = db.scalars(
        claim_service.claim_query()
        .where(Claim.claimant_id == user.id, Claim.status.in_([ClaimStatus.PENDING, ClaimStatus.APPROVED]))
        .order_by(Claim.created_at.desc())
    ).unique().all()

    on_my_items = or_(
        Match.lost_item_id.in_(select(Item.id).where(Item.reporter_id == user.id)),
        Match.found_item_id.in_(select(Item.id).where(Item.reporter_id == user.id)),
    )
    suggested = and_(Match.status == MatchStatus.SUGGESTED, on_my_items)
    suggestion_count = db.scalar(select(func.count(Match.id)).where(suggested)) or 0
    top = db.scalars(
        match_service.match_query().where(suggested).order_by(Match.score.desc(), Match.id).limit(RECENT_LIMIT)
    ).unique().all()
    top_pairs = [(m, m.found_item if m.lost_item.reporter_id == user.id else m.lost_item) for m in top]

    return {
        "reports": _report_counts(db, Item.reporter_id == user.id),
        "recent_reports": recent,
        "claims": _counts(db, Claim.status, ClaimStatus, Claim.claimant_id == user.id),
        "active_claims": active_claims,
        "suggestion_count": suggestion_count,
        "top_suggestions": top_pairs,
        "unread_notifications": db.scalar(
            select(func.count(Notification.id)).where(Notification.user_id == user.id,
                                                      Notification.read_at.is_(None))
        ) or 0,
    }


def staff_dashboard(db: Session) -> dict:
    live_handover = select(HandoverRecord.id).where(
        HandoverRecord.claim_id == Claim.id,
        HandoverRecord.status.in_([HandoverStatus.SCHEDULED, HandoverStatus.VERIFIED, HandoverStatus.COMPLETED]),
    )
    return {
        "pending_claims": db.scalar(select(func.count(Claim.id)).where(Claim.status == ClaimStatus.PENDING)) or 0,
        "oldest_pending_claim_at": db.scalar(
            select(func.min(Claim.created_at)).where(Claim.status == ClaimStatus.PENDING)
        ),
        "approved_awaiting_handover": db.scalar(
            select(func.count(Claim.id)).where(Claim.status == ClaimStatus.APPROVED, ~live_handover.exists())
        ) or 0,
        "handovers": _counts(db, HandoverRecord.status, HandoverStatus),
        "completed_last_7_days": db.scalar(
            select(func.count(HandoverRecord.id)).where(
                HandoverRecord.status == HandoverStatus.COMPLETED,
                HandoverRecord.completed_at >= utcnow() - timedelta(days=7),
            )
        ) or 0,
        "open_found_reports": db.scalar(
            select(func.count(Item.id)).where(Item.report_type == ReportType.FOUND,
                                              Item.status.in_([ItemStatus.OPEN, ItemStatus.MATCHED]))
        ) or 0,
        "high_score_suggestions": db.scalar(
            select(func.count(Match.id)).where(Match.status == MatchStatus.SUGGESTED, Match.score >= HIGH_SCORE)
        ) or 0,
        "high_score_threshold": HIGH_SCORE,
    }


def _breakdown(db: Session, model, fk_column, in_range: list[ColumnElement[bool]]) -> list[dict]:
    rows = db.execute(
        select(model.id, model.name, Item.report_type, func.count(Item.id))
        .join(Item, fk_column == model.id)
        .where(*in_range)
        .group_by(model.id, model.name, Item.report_type)
    ).all()
    table: dict[int, dict] = {}
    for row_id, name, report_type, n in rows:
        entry = table.setdefault(row_id, {"id": row_id, "name": name, "lost": 0, "found": 0})
        entry["lost" if report_type == ReportType.LOST else "found"] += n
    return sorted(table.values(), key=lambda r: (-(r["lost"] + r["found"]), r["name"]))


def admin_stats(db: Session, created_from: datetime | None, created_to: datetime | None) -> dict:
    def created_between(col) -> list[ColumnElement[bool]]:
        conditions = []
        if created_from:
            conditions.append(col >= created_from)
        if created_to:
            conditions.append(col <= created_to)
        return conditions

    in_range = created_between(Item.created_at)

    month = func.strftime("%Y-%m", Item.created_at)
    monthly_rows = db.execute(
        select(month, Item.report_type, func.count(Item.id)).where(*in_range).group_by(month, Item.report_type)
    ).all()
    months: dict[str, dict] = {}
    for key, report_type, n in monthly_rows:
        entry = months.setdefault(key, {"month": key, "lost": 0, "found": 0})
        entry["lost" if report_type == ReportType.LOST else "found"] += n

    found_in_range = [Item.report_type == ReportType.FOUND, *in_range]
    found_total = db.scalar(select(func.count(Item.id)).where(*found_in_range)) or 0
    returned = db.execute(
        select(Item.created_at, Item.resolved_at).where(*found_in_range, Item.status == ItemStatus.RETURNED)
    ).all()
    # created_at/resolved_at come back timezone-aware via UTCDateTime.
    hours = [(resolved - created).total_seconds() / 3600 for created, resolved in returned if resolved]

    return {
        "generated_at": utcnow(),
        "created_from": created_from,
        "created_to": created_to,
        "users": {
            "total": db.scalar(select(func.count(User.id))) or 0,
            "by_role": _counts(db, User.role, UserRole),
            "by_status": _counts(db, User.account_status, AccountStatus),
            "verified": db.scalar(select(func.count(User.id)).where(User.email_verified_at.is_not(None))) or 0,
        },
        "reports": _report_counts(db, *in_range),
        "claims": _counts(db, Claim.status, ClaimStatus, *created_between(Claim.created_at)),
        "handovers": _counts(db, HandoverRecord.status, HandoverStatus, *created_between(HandoverRecord.created_at)),
        "matches": _counts(db, Match.status, MatchStatus, *created_between(Match.created_at)),
        "by_category": _breakdown(db, Category, Item.category_id, in_range),
        "by_location": _breakdown(db, CampusLocation, Item.location_id, in_range),
        "monthly": [months[k] for k in sorted(months)],
        "found_return_rate": round(len(returned) / found_total, 4) if found_total else None,
        "median_hours_to_return": round(median(hours), 1) if hours else None,
    }
