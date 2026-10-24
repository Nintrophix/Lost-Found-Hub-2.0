"""Claimant endpoints: submit, view and withdraw claims, and get the handover QR code."""

from fastapi import APIRouter, status

from app.api import presenters
from app.api.deps import AppSettings, CurrentUser, DbSession
from app.schemas.claims import ClaimCreate, ClaimResponse, QrTokenResponse, StaffClaimResponse
from app.services import claims as claim_service
from app.services import handovers as handover_service
from app.services import items as item_service

router = APIRouter(tags=["claims"])


@router.post("/items/{item_id}/claims", status_code=status.HTTP_201_CREATED)
def submit_claim(item_id: int, body: ClaimCreate, user: CurrentUser, db: DbSession) -> ClaimResponse:
    return presenters.claim_response(claim_service.submit(db, user, item_id, body.evidence), user)


@router.get("/claims/mine")
def my_claims(user: CurrentUser, db: DbSession) -> list[ClaimResponse]:
    return [presenters.claim_response(c, user) for c in claim_service.list_mine(db, user)]


@router.get("/claims/{claim_id}")
def get_claim(claim_id: int, user: CurrentUser, db: DbSession) -> ClaimResponse | StaffClaimResponse:
    claim = claim_service.get_visible(db, user, claim_id)
    if item_service.is_staff(user) and claim.claimant_id != user.id:
        return presenters.staff_claim_response(claim, user)
    return presenters.claim_response(claim, user)


@router.post("/claims/{claim_id}/withdraw")
def withdraw_claim(claim_id: int, user: CurrentUser, db: DbSession) -> ClaimResponse:
    return presenters.claim_response(claim_service.withdraw(db, user, claim_id), user)


@router.post("/claims/{claim_id}/handover/qr")
def issue_handover_qr(claim_id: int, user: CurrentUser, db: DbSession, settings: AppSettings) -> QrTokenResponse:
    payload, handover, svg = handover_service.issue_qr(db, settings, user, claim_id)
    return QrTokenResponse(payload=payload, expires_at=handover.qr_expires_at, svg=svg)
