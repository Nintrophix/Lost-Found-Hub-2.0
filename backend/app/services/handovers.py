"""QR-verified handovers of FOUND items to approved claimants.

Lifecycle: staff schedule a handover for an APPROVED claim; the claimant generates a short-lived
QR token (only its SHA-256 hash is stored, and regenerating replaces it); at the desk staff scan it
(single use, marks the handover VERIFIED), check the claimant's identity in person, then complete.
Completion updates the handover, claim and item in one transaction. Possessing a QR code is never
enough on its own: completion requires an explicit identity confirmation by staff.
"""

from datetime import timedelta

import segno
from sqlalchemy import Select, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings
from app.core.rate_limit import allow_for_key
from app.core.security import generate_token, hash_token
from app.db.enums import ClaimStatus, HandoverStatus, ItemStatus, MatchStatus, NotificationType
from app.db.models import Claim, HandoverRecord, Item, Match, User
from app.db.types import utcnow
from app.services import audit, matching
from app.services import claims as claim_service
from app.services.concurrency import lock_status
from app.services.errors import ServiceError

PAYLOAD_PREFIX = "LFH-HANDOVER:"
INVALID_QR = "This QR code is invalid, expired or already used."
HANDOVER_NOT_FOUND = "Handover not found."


def _handover_query() -> Select[tuple[HandoverRecord]]:
    return select(HandoverRecord).options(
        joinedload(HandoverRecord.claim).joinedload(Claim.claimant),
        joinedload(HandoverRecord.item),
    ).execution_options(populate_existing=True)


def _load(db: Session, handover_id: int) -> HandoverRecord | None:
    db.flush()
    return db.scalar(_handover_query().where(HandoverRecord.id == handover_id))


def _get_for_staff(db: Session, staff: User, handover_id: int) -> HandoverRecord:
    handover = _load(db, handover_id)
    if handover is None:
        raise ServiceError(404, HANDOVER_NOT_FOUND)
    if handover.claim.claimant_id == staff.id:
        raise ServiceError(403, "You cannot review or hand over your own claim.")
    return handover


def schedule(db: Session, staff: User, claim_id: int, notes: str | None) -> HandoverRecord:
    claim = claim_service.get_for_review(db, staff, claim_id)
    if claim.status != ClaimStatus.APPROVED:
        raise ServiceError(409, "A handover can only be scheduled for an approved claim.")
    lock_status(db, Claim, claim.id, (ClaimStatus.APPROVED,), "A handover can only be scheduled for an approved claim.")
    handover = HandoverRecord(item_id=claim.item_id, claim_id=claim.id, staff_id=staff.id, notes=notes)
    db.add(handover)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ServiceError(409, "A handover is already in progress for this claim.") from None
    claim_service.notify(db, claim.claimant_id, NotificationType.HANDOVER_SCHEDULED, "Your handover is ready",
                         f'You can now collect "{claim.item.title}". Open your claim to show its QR code at the '
                         "campus lost and found desk, and bring your campus ID.", claim)
    audit.record(db, "handover.scheduled", "handover", handover.id, actor_id=staff.id,
                 details={"claim_id": claim.id})
    db.commit()
    return _load(db, handover.id)


def issue_qr(db: Session, settings: Settings, user: User, claim_id: int) -> tuple[str, HandoverRecord, str]:
    """Create a fresh token for the claimant's scheduled handover. Returns (payload, handover, svg)."""
    claim = claim_service.load(db, claim_id)
    if claim is None or claim.claimant_id != user.id:
        raise ServiceError(404, claim_service.CLAIM_NOT_FOUND)
    if claim.status != ClaimStatus.APPROVED:
        raise ServiceError(409, "This claim is not approved.")
    handover = next((h for h in claim.handovers if h.status == HandoverStatus.SCHEDULED), None)
    if handover is None:
        raise ServiceError(409, "No handover is ready for this claim yet.")
    lock_status(db, HandoverRecord, handover.id, (HandoverStatus.SCHEDULED,),
                "No handover is ready for this claim yet.")
    if not allow_for_key("issue-qr", str(user.id), 10, 3600):
        raise ServiceError(429, "Too many QR codes requested. Try again later.", {"Retry-After": "3600"})

    raw = generate_token()
    # Replacing the hash revokes any earlier code for this handover.
    handover.qr_token_hash = hash_token(raw)
    handover.qr_expires_at = utcnow() + timedelta(minutes=settings.qr_token_ttl_minutes)
    audit.record(db, "handover.qr_issued", "handover", handover.id, actor_id=user.id)
    db.commit()

    payload = PAYLOAD_PREFIX + raw
    svg = segno.make(payload, error="m").svg_inline(scale=6, border=2)
    return payload, _load(db, handover.id), svg


def _reject_scan(db: Session, staff: User, handover: HandoverRecord | None, reason: str) -> ServiceError:
    audit.record(db, "handover.verify_failed", "handover", handover.id if handover else None, actor_id=staff.id,
                 details={"reason": reason})
    db.commit()
    return ServiceError(400, INVALID_QR)


def verify(db: Session, staff: User, payload: str) -> HandoverRecord:
    """Consume a scanned QR token. Succeeds at most once per token, even under concurrent scans."""
    if not payload.startswith(PAYLOAD_PREFIX) or len(payload) == len(PAYLOAD_PREFIX):
        raise _reject_scan(db, staff, None, "malformed")
    token_hash = hash_token(payload[len(PAYLOAD_PREFIX):])
    handover = db.scalar(_handover_query().where(HandoverRecord.qr_token_hash == token_hash))
    now = utcnow()

    if handover is None:
        raise _reject_scan(db, staff, None, "unknown")
    if handover.claim.claimant_id == staff.id:
        raise ServiceError(403, "You cannot review or hand over your own claim.")
    if handover.token_used_at is not None or handover.status != HandoverStatus.SCHEDULED:
        raise _reject_scan(db, staff, handover, "used_or_not_scheduled")
    if handover.qr_expires_at is None or handover.qr_expires_at <= now:
        raise _reject_scan(db, staff, handover, "expired")
    if handover.claim.status != ClaimStatus.APPROVED or handover.item.status != ItemStatus.CLAIMED:
        raise _reject_scan(db, staff, handover, "claim_not_eligible")

    # Conditional update: only one scan can flip SCHEDULED to VERIFIED for this token.
    result = db.execute(
        update(HandoverRecord)
        .where(
            HandoverRecord.id == handover.id,
            HandoverRecord.qr_token_hash == token_hash,
            HandoverRecord.status == HandoverStatus.SCHEDULED,
            HandoverRecord.token_used_at.is_(None),
            HandoverRecord.qr_expires_at > now,
        )
        .values(status=HandoverStatus.VERIFIED, token_used_at=now, verified_at=now, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise _reject_scan(db, staff, handover, "race_lost")
    audit.record(db, "handover.verified", "handover", handover.id, actor_id=staff.id,
                 details={"claim_id": handover.claim_id})
    db.commit()
    return _load(db, handover.id)


def complete(db: Session, staff: User, handover_id: int, notes: str | None) -> HandoverRecord:
    """Finish a verified handover: handover, claim and item change together or not at all."""
    handover = _get_for_staff(db, staff, handover_id)
    claim, item = handover.claim, handover.item
    if handover.status != HandoverStatus.VERIFIED:
        raise ServiceError(409, "Scan the claimant's QR code before completing the handover.")
    if claim.status != ClaimStatus.APPROVED or item.status != ItemStatus.CLAIMED:
        raise ServiceError(409, "This claim is no longer eligible for handover.")
    lock_status(db, Claim, claim.id, (ClaimStatus.APPROVED,), "This claim is no longer eligible for handover.")
    lock_status(db, Item, item.id, (ItemStatus.CLAIMED,), "This claim is no longer eligible for handover.")
    now = utcnow()

    try:
        result = db.execute(
            update(HandoverRecord)
            .where(HandoverRecord.id == handover.id, HandoverRecord.status == HandoverStatus.VERIFIED)
            .values(
                status=HandoverStatus.COMPLETED,
                completed_at=now,
                updated_at=now,
                notes="\n".join(filter(None, (handover.notes, notes))) or None,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise ServiceError(409, "This handover was already completed or cancelled.")

        claim.status = ClaimStatus.COMPLETED
        item.status = ItemStatus.RETURNED
        item.resolved_at = now
        matching.dismiss_suggestions_for(db, item.id)

        # Other pending claims for this item can no longer succeed.
        others = db.scalars(
            select(Claim).where(Claim.item_id == item.id, Claim.id != claim.id, Claim.status == ClaimStatus.PENDING)
        ).all()
        for other in others:
            other.status = ClaimStatus.REJECTED
            other.review_reason = "The item was returned to its verified owner."
            other.reviewer_id = staff.id
            other.reviewed_at = now
            claim_service.notify(db, other.claimant_id, NotificationType.CLAIM_REJECTED,
                                 "Your claim was not approved",
                                 f'"{item.title}" has been returned to its verified owner.', other)

        # The claimant's own LOST reports confirmed as matching this item are resolved too.
        lost_reports = db.scalars(
            select(Item).join(Match, Match.lost_item_id == Item.id).where(
                Match.found_item_id == item.id,
                Match.status == MatchStatus.CONFIRMED,
                Item.reporter_id == claim.claimant_id,
                Item.status.in_(matching.MATCHABLE_STATUSES),
            )
        ).all()
        for lost in lost_reports:
            lost.status = ItemStatus.RETURNED
            lost.resolved_at = now
            matching.dismiss_suggestions_for(db, lost.id)

        claim_service.notify(db, claim.claimant_id, NotificationType.HANDOVER_COMPLETED, "Item returned",
                             f'The handover of "{item.title}" is complete.', claim)
        audit.record(db, "handover.completed", "handover", handover.id, actor_id=staff.id,
                     details={"claim_id": claim.id, "item_id": item.id})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ServiceError(409, "This item has already been handed over.") from None
    except ServiceError:
        db.rollback()
        raise
    return _load(db, handover.id)


def cancel(db: Session, staff: User, handover_id: int, reason: str) -> HandoverRecord:
    handover = _get_for_staff(db, staff, handover_id)
    if handover.status not in claim_service.LIVE_HANDOVER_STATUSES:
        raise ServiceError(409, "Only scheduled or verified handovers can be cancelled.")
    lock_status(db, HandoverRecord, handover.id, claim_service.LIVE_HANDOVER_STATUSES,
                "Only scheduled or verified handovers can be cancelled.")
    handover.status = HandoverStatus.CANCELLED
    handover.notes = "\n".join(filter(None, (handover.notes, f"Cancelled: {reason}")))
    audit.record(db, "handover.cancelled", "handover", handover.id, actor_id=staff.id,
                 details={"claim_id": handover.claim_id})
    db.commit()
    return _load(db, handover.id)


def staff_list(db: Session, status: HandoverStatus | None, page: int,
               page_size: int) -> tuple[list[HandoverRecord], int]:
    conditions = [HandoverRecord.status == status] if status is not None else []
    total = db.scalar(select(func.count(HandoverRecord.id)).where(*conditions)) or 0
    stmt = (
        _handover_query()
        .where(*conditions)
        .order_by(HandoverRecord.created_at.desc(), HandoverRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).unique()), total
