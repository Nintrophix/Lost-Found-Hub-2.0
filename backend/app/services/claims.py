"""Ownership claims on FOUND reports and their review by staff.

A high match score never approves a claim: only a staff decision does. Evidence is private to the
claimant and staff and is never written to audit logs or notifications.
"""

from sqlalchemy import Select, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.rate_limit import allow_for_key
from app.db.enums import (
    AccountStatus,
    ClaimStatus,
    HandoverStatus,
    ItemStatus,
    MatchStatus,
    NotificationType,
    ReportType,
    UserRole,
)
from app.db.models import Claim, HandoverRecord, Item, Match, Notification, User
from app.db.types import utcnow
from app.services import audit
from app.services import items as item_service
from app.services.concurrency import lock_status
from app.services.errors import ServiceError

CLAIMABLE_STATUSES = (ItemStatus.OPEN, ItemStatus.MATCHED)
LIVE_HANDOVER_STATUSES = (HandoverStatus.SCHEDULED, HandoverStatus.VERIFIED)
CLAIM_NOT_FOUND = "Claim not found."


def claim_query() -> Select[tuple[Claim]]:
    item_options = (joinedload(Item.category), joinedload(Item.location), selectinload(Item.images))
    return (
        select(Claim)
        .options(
            joinedload(Claim.item).options(*item_options),
            joinedload(Claim.claimant),
            selectinload(Claim.handovers),
        )
        .execution_options(populate_existing=True)
    )


def load(db: Session, claim_id: int) -> Claim | None:
    db.flush()
    return db.scalar(claim_query().where(Claim.id == claim_id))


def get_visible(db: Session, user: User, claim_id: int) -> Claim:
    """The claimant and staff can see a claim; to anyone else it does not exist."""
    claim = load(db, claim_id)
    if claim is None or not (claim.claimant_id == user.id or item_service.is_staff(user)):
        raise ServiceError(404, CLAIM_NOT_FOUND)
    return claim


def get_for_review(db: Session, staff: User, claim_id: int) -> Claim:
    claim = load(db, claim_id)
    if claim is None:
        raise ServiceError(404, CLAIM_NOT_FOUND)
    if claim.claimant_id == staff.id:
        raise ServiceError(403, "You cannot review or hand over your own claim.")
    return claim


def notify(db: Session, user_id: int, type_: NotificationType, title: str, message: str, claim: Claim) -> None:
    db.add(Notification(user_id=user_id, type=type_, title=title, message=message, item_id=claim.item_id,
                        claim_id=claim.id))


def cancel_live_handovers(db: Session, claim: Claim, actor_id: int, reason: str) -> None:
    for handover in claim.handovers:
        if handover.status in LIVE_HANDOVER_STATUSES:
            handover.status = HandoverStatus.CANCELLED
            handover.notes = "\n".join(filter(None, (handover.notes, f"Cancelled: {reason}")))
            audit.record(db, "handover.cancelled", "handover", handover.id, actor_id=actor_id,
                         details={"claim_id": claim.id})


def release_item(db: Session, item: Item) -> None:
    """After an approved claim falls through, the item returns to MATCHED or OPEN."""
    if item.status != ItemStatus.CLAIMED:
        return
    confirmed = db.scalar(
        select(exists().where(Match.found_item_id == item.id, Match.status == MatchStatus.CONFIRMED))
    )
    item.status = ItemStatus.MATCHED if confirmed else ItemStatus.OPEN


def submit(db: Session, user: User, item_id: int, evidence: str) -> Claim:
    item = item_service.get_viewable(db, user, item_id)
    if item.report_type != ReportType.FOUND:
        raise ServiceError(422, "Claims can only be made on found items.")
    if item.reporter_id == user.id:
        raise ServiceError(403, "You cannot claim an item you reported finding.")
    if item.status not in CLAIMABLE_STATUSES:
        raise ServiceError(409, "This item is not accepting claims.")
    lock_status(db, Item, item.id, CLAIMABLE_STATUSES, "This item is not accepting claims.")
    if not allow_for_key("submit-claim", str(user.id), 10, 3600):
        raise ServiceError(429, "You have submitted many claims recently. Try again later.", {"Retry-After": "3600"})

    claim = Claim(item_id=item.id, claimant_id=user.id, evidence=evidence)
    db.add(claim)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ServiceError(409, "You already have an open claim for this item.") from None

    staff_ids = db.scalars(
        select(User.id).where(
            User.role.in_([UserRole.STAFF, UserRole.ADMIN]),
            User.account_status == AccountStatus.ACTIVE,
            User.id != user.id,
        )
    )
    for staff_id in staff_ids:
        notify(db, staff_id, NotificationType.CLAIM_SUBMITTED, "New claim to review",
               f'A claim was submitted for the found item "{item.title}".', claim)
    audit.record(db, "claim.submitted", "claim", claim.id, actor_id=user.id, details={"item_id": item.id})
    db.commit()
    return load(db, claim.id)


def list_mine(db: Session, user: User) -> list[Claim]:
    db.flush()
    stmt = claim_query().where(Claim.claimant_id == user.id).order_by(Claim.created_at.desc(), Claim.id.desc())
    return list(db.scalars(stmt).unique())


def withdraw(db: Session, user: User, claim_id: int) -> Claim:
    claim = load(db, claim_id)
    if claim is None or claim.claimant_id != user.id:
        raise ServiceError(404, CLAIM_NOT_FOUND)
    if claim.status not in (ClaimStatus.PENDING, ClaimStatus.APPROVED):
        raise ServiceError(409, "This claim can no longer be withdrawn.")
    lock_status(db, Claim, claim.id, (ClaimStatus.PENDING, ClaimStatus.APPROVED),
                "This claim can no longer be withdrawn.")
    if claim.status == ClaimStatus.APPROVED:
        cancel_live_handovers(db, claim, user.id, "claim withdrawn")
        release_item(db, claim.item)
    claim.status = ClaimStatus.WITHDRAWN
    audit.record(db, "claim.withdrawn", "claim", claim.id, actor_id=user.id)
    db.commit()
    return load(db, claim.id)


def staff_list(db: Session, status: ClaimStatus | None, page: int, page_size: int) -> tuple[list[Claim], int]:
    conditions = [Claim.status == status] if status is not None else []
    total = db.scalar(select(func.count(Claim.id)).where(*conditions)) or 0
    stmt = (
        claim_query()
        .where(*conditions)
        .order_by(Claim.created_at.asc(), Claim.id.asc())  # oldest first: a fair review queue
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).unique()), total


def get_for_staff(db: Session, claim_id: int) -> Claim:
    claim = load(db, claim_id)
    if claim is None:
        raise ServiceError(404, CLAIM_NOT_FOUND)
    return claim


def approve(db: Session, staff: User, claim_id: int, reason: str | None) -> Claim:
    claim = get_for_review(db, staff, claim_id)
    if claim.status != ClaimStatus.PENDING:
        raise ServiceError(409, "Only pending claims can be approved.")
    item = claim.item
    if item.status not in CLAIMABLE_STATUSES:
        raise ServiceError(409, "This item is not accepting claims.")
    lock_status(db, Claim, claim.id, (ClaimStatus.PENDING,), "Only pending claims can be approved.")
    lock_status(db, Item, item.id, CLAIMABLE_STATUSES, "This item is not accepting claims.")

    claim.status = ClaimStatus.APPROVED
    claim.reviewer_id = staff.id
    claim.reviewed_at = utcnow()
    claim.review_reason = reason
    item.status = ItemStatus.CLAIMED
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ServiceError(409, "Another claim for this item is already approved.") from None

    notify(db, claim.claimant_id, NotificationType.CLAIM_APPROVED, "Your claim was approved",
           f'Campus staff approved your claim for "{item.title}". They will arrange a handover; '
           "bring your campus ID when you collect it.", claim)
    audit.record(db, "claim.approved", "claim", claim.id, actor_id=staff.id, details={"item_id": item.id})
    db.commit()
    return load(db, claim.id)


def reject(db: Session, staff: User, claim_id: int, reason: str) -> Claim:
    claim = get_for_review(db, staff, claim_id)
    if claim.status not in (ClaimStatus.PENDING, ClaimStatus.APPROVED):
        raise ServiceError(409, "This claim can no longer be rejected.")
    lock_status(db, Claim, claim.id, (ClaimStatus.PENDING, ClaimStatus.APPROVED),
                "This claim can no longer be rejected.")
    if claim.status == ClaimStatus.APPROVED:
        cancel_live_handovers(db, claim, staff.id, "claim rejected")
        release_item(db, claim.item)

    claim.status = ClaimStatus.REJECTED
    claim.reviewer_id = staff.id
    claim.reviewed_at = utcnow()
    claim.review_reason = reason
    notify(db, claim.claimant_id, NotificationType.CLAIM_REJECTED, "Your claim was not approved",
           f'Your claim for "{claim.item.title}" was not approved. Reason: {reason}', claim)
    audit.record(db, "claim.rejected", "claim", claim.id, actor_id=staff.id, details={"item_id": claim.item_id})
    db.commit()
    return load(db, claim.id)


def current_handover(claim: Claim) -> HandoverRecord | None:
    """The live or completed handover if there is one, otherwise the most recent."""
    if not claim.handovers:
        return None
    active = [h for h in claim.handovers if h.status != HandoverStatus.CANCELLED]
    return max(active or claim.handovers, key=lambda h: h.id)
