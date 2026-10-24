"""Build claim, handover and match responses. Evidence appears only in claimant and staff views."""

from app.db.models import Claim, HandoverRecord, Item, Match, User
from app.schemas.claims import (
    ClaimResponse,
    HandoverResponse,
    HandoverSummary,
    PersonSummary,
    StaffClaimResponse,
)
from app.schemas.matches import MatchReason, MatchResponse
from app.services import claims as claim_service
from app.services import items as item_service


def handover_summary(handover: HandoverRecord | None) -> HandoverSummary | None:
    if handover is None:
        return None
    return HandoverSummary(
        id=handover.id,
        status=handover.status,
        qr_expires_at=handover.qr_expires_at,
        qr_used=handover.token_used_at is not None,
        verified_at=handover.verified_at,
        completed_at=handover.completed_at,
        created_at=handover.created_at,
    )


def _claim_fields(claim: Claim, viewer: User) -> dict:
    return {
        "id": claim.id,
        "status": claim.status,
        "evidence": claim.evidence,
        "review_reason": claim.review_reason,
        "reviewed_at": claim.reviewed_at,
        "created_at": claim.created_at,
        "updated_at": claim.updated_at,
        "item": item_service.to_response(claim.item, viewer),
        "handover": handover_summary(claim_service.current_handover(claim)),
    }


def claim_response(claim: Claim, viewer: User) -> ClaimResponse:
    return ClaimResponse(**_claim_fields(claim, viewer))


def person(user: User) -> PersonSummary:
    return PersonSummary(id=user.id, name=user.name, email=user.email, campus_id=user.campus_id)


def staff_claim_response(claim: Claim, viewer: User) -> StaffClaimResponse:
    return StaffClaimResponse(**_claim_fields(claim, viewer), claimant=person(claim.claimant),
                              reviewer_id=claim.reviewer_id)


def handover_response(handover: HandoverRecord) -> HandoverResponse:
    return HandoverResponse(
        **handover_summary(handover).model_dump(),
        claim_id=handover.claim_id,
        item_id=handover.item_id,
        item_title=handover.item.title,
        staff_id=handover.staff_id,
        notes=handover.notes,
        claimant=person(handover.claim.claimant),
    )


def match_response(match: Match, counterpart: Item, viewer: User) -> MatchResponse:
    return MatchResponse(
        id=match.id,
        score=match.score,
        status=match.status,
        reasons=[MatchReason.model_validate(r) for r in match.reasons],
        lost_item_id=match.lost_item_id,
        found_item_id=match.found_item_id,
        created_at=match.created_at,
        updated_at=match.updated_at,
        counterpart=item_service.to_response(counterpart, viewer),
    )
