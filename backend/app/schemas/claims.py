"""Contracts for ownership claims and handovers.

Claim evidence is private: it appears only in responses to the claimant and to staff, never in
item responses.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from app.db.enums import ClaimStatus, HandoverStatus
from app.schemas.auth import StrictModel
from app.schemas.items import ItemResponse

Evidence = Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=2000)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1000)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
QrPayload = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ClaimCreate(StrictModel):
    evidence: Evidence


class ApproveRequest(StrictModel):
    reason: Reason | None = None


class RejectRequest(StrictModel):
    reason: Reason


class HandoverCreate(StrictModel):
    notes: Notes | None = None


class HandoverCancel(StrictModel):
    reason: Reason


class VerifyRequest(StrictModel):
    payload: QrPayload


class CompleteRequest(StrictModel):
    # Staff must state they checked the claimant's identity in person; a QR code alone is not proof.
    identity_confirmed: Literal[True]
    notes: Notes | None = None


class PersonSummary(BaseModel):
    id: int
    name: str
    email: str
    campus_id: str | None


class HandoverSummary(BaseModel):
    id: int
    status: HandoverStatus
    qr_expires_at: datetime | None
    qr_used: bool
    verified_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class ClaimResponse(BaseModel):
    """Claim as shown to its claimant."""

    id: int
    status: ClaimStatus
    evidence: str
    review_reason: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    item: ItemResponse
    handover: HandoverSummary | None


class StaffClaimResponse(ClaimResponse):
    claimant: PersonSummary
    reviewer_id: int | None


class StaffClaimPage(BaseModel):
    items: list[StaffClaimResponse]
    total: int
    page: int
    page_size: int


class HandoverResponse(HandoverSummary):
    """Handover as shown to staff, with what they need to check identity at the desk."""

    claim_id: int
    item_id: int
    item_title: str
    staff_id: int
    notes: str | None
    claimant: PersonSummary


class HandoverPage(BaseModel):
    items: list[HandoverResponse]
    total: int
    page: int
    page_size: int


class QrTokenResponse(BaseModel):
    """Returned once to the claimant. The server keeps only a hash of the token."""

    payload: str
    expires_at: datetime
    svg: str
