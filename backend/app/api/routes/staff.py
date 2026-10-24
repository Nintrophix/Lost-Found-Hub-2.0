"""Staff workspace under /api/staff: claim review and QR-verified handovers."""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api import presenters
from app.api.deps import DbSession, StaffUser
from app.db.enums import ClaimStatus, HandoverStatus
from app.schemas.claims import (
    ApproveRequest,
    CompleteRequest,
    HandoverCancel,
    HandoverCreate,
    HandoverPage,
    HandoverResponse,
    RejectRequest,
    StaffClaimPage,
    StaffClaimResponse,
    VerifyRequest,
)
from app.schemas.dashboard import StaffDashboard
from app.schemas.items import MAX_PAGE_SIZE
from app.services import claims as claim_service
from app.services import dashboard as dashboard_service
from app.services import handovers as handover_service

router = APIRouter(prefix="/staff", tags=["staff"])

Page = Annotated[int, Query(ge=1, le=10_000)]
PageSize = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]


@router.get("/dashboard")
def staff_dashboard(staff: StaffUser, db: DbSession) -> StaffDashboard:
    return StaffDashboard(**dashboard_service.staff_dashboard(db))


@router.get("/claims")
def list_claims(
    staff: StaffUser,
    db: DbSession,
    claim_status: Annotated[ClaimStatus | None, Query(alias="status")] = ClaimStatus.PENDING,
    page: Page = 1,
    page_size: PageSize = 20,
) -> StaffClaimPage:
    rows, total = claim_service.staff_list(db, claim_status, page, page_size)
    return StaffClaimPage(items=[presenters.staff_claim_response(c, staff) for c in rows], total=total, page=page,
                          page_size=page_size)


@router.get("/claims/{claim_id}")
def get_claim(claim_id: int, staff: StaffUser, db: DbSession) -> StaffClaimResponse:
    return presenters.staff_claim_response(claim_service.get_for_staff(db, claim_id), staff)


@router.post("/claims/{claim_id}/approve")
def approve_claim(claim_id: int, body: ApproveRequest, staff: StaffUser, db: DbSession) -> StaffClaimResponse:
    return presenters.staff_claim_response(claim_service.approve(db, staff, claim_id, body.reason), staff)


@router.post("/claims/{claim_id}/reject")
def reject_claim(claim_id: int, body: RejectRequest, staff: StaffUser, db: DbSession) -> StaffClaimResponse:
    return presenters.staff_claim_response(claim_service.reject(db, staff, claim_id, body.reason), staff)


@router.post("/claims/{claim_id}/handover", status_code=status.HTTP_201_CREATED)
def schedule_handover(claim_id: int, body: HandoverCreate, staff: StaffUser, db: DbSession) -> HandoverResponse:
    return presenters.handover_response(handover_service.schedule(db, staff, claim_id, body.notes))


@router.get("/handovers")
def list_handovers(
    staff: StaffUser,
    db: DbSession,
    handover_status: Annotated[HandoverStatus | None, Query(alias="status")] = None,
    page: Page = 1,
    page_size: PageSize = 20,
) -> HandoverPage:
    rows, total = handover_service.staff_list(db, handover_status, page, page_size)
    return HandoverPage(items=[presenters.handover_response(h) for h in rows], total=total, page=page,
                        page_size=page_size)


@router.post("/handovers/verify")
def verify_handover(body: VerifyRequest, staff: StaffUser, db: DbSession) -> HandoverResponse:
    return presenters.handover_response(handover_service.verify(db, staff, body.payload))


@router.post("/handovers/{handover_id}/complete")
def complete_handover(handover_id: int, body: CompleteRequest, staff: StaffUser, db: DbSession) -> HandoverResponse:
    return presenters.handover_response(handover_service.complete(db, staff, handover_id, body.notes))


@router.post("/handovers/{handover_id}/cancel")
def cancel_handover(handover_id: int, body: HandoverCancel, staff: StaffUser, db: DbSession) -> HandoverResponse:
    return presenters.handover_response(handover_service.cancel(db, staff, handover_id, body.reason))
