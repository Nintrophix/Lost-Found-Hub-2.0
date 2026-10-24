"""Claims, staff review and QR handover through the real API, including failure and replay paths."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.security import hash_token
from app.db.enums import ClaimStatus, HandoverStatus, ItemStatus, UserRole
from app.db.models import AuditLog, Claim, HandoverRecord, Item, Notification
from app.db.types import utcnow
from app.services import claims as claim_service
from tests.test_items import api, create  # noqa: F401  (api is a fixture)
from tests.test_matches import MATCHING_FOUND

EVIDENCE = "My lock screen shows a photo of a beagle and there is a sticker inside the case."


@pytest.fixture
def flow(api):  # noqa: F811
    """A finder's FOUND phone, the owner's matching LOST report, and a staff member."""
    finder, owner, staff = api.user(), api.user(), api.user(UserRole.STAFF)
    found = create(finder, api.db, **MATCHING_FOUND)
    lost = create(owner, api.db)
    return SimpleNamespace(api=api, db=api.db, finder=finder, owner=owner, staff=staff, found=found, lost=lost)


def submit(client, item_id: int, evidence: str = EVIDENCE):
    return client.post(f"/api/items/{item_id}/claims", json={"evidence": evidence})


def claim_id_for(f) -> int:
    response = submit(f.owner, f.found["id"])
    assert response.status_code == 201, response.text
    return response.json()["id"]


def approved(f) -> int:
    cid = claim_id_for(f)
    assert f.staff.post(f"/api/staff/claims/{cid}/approve", json={}).status_code == 200
    return cid


def scheduled(f) -> tuple[int, int]:
    cid = approved(f)
    response = f.staff.post(f"/api/staff/claims/{cid}/handover", json={"notes": "Desk B"})
    assert response.status_code == 201, response.text
    return cid, response.json()["id"]


def qr(f, cid: int) -> str:
    response = f.owner.post(f"/api/claims/{cid}/handover/qr")
    assert response.status_code == 200, response.text
    return response.json()["payload"]


def verified(f) -> tuple[int, int]:
    cid, hid = scheduled(f)
    assert f.staff.post("/api/staff/handovers/verify", json={"payload": qr(f, cid)}).status_code == 200
    return cid, hid


def status_of(db, model, row_id: int):
    db.expire_all()
    return db.get(model, row_id).status


# Submitting and viewing

def test_submit_claim_keeps_evidence_private(flow):
    f = flow
    response = submit(f.owner, f.found["id"])
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PENDING" and body["evidence"] == EVIDENCE and body["handover"] is None
    assert "claimant" not in body

    for client in (f.finder, f.owner, f.api.user()):
        assert "beagle" not in client.get(f"/api/items/{f.found['id']}").text
        assert "beagle" not in client.get("/api/items").text
    assert f.finder.get(f"/api/claims/{body['id']}").status_code == 404
    assert f.api.user().get(f"/api/claims/{body['id']}").status_code == 404

    staff_view = f.staff.get(f"/api/staff/claims/{body['id']}").json()
    assert staff_view["evidence"] == EVIDENCE and staff_view["claimant"]["email"].endswith("@example.edu")
    assert f.staff.get(f"/api/claims/{body['id']}").json()["claimant"]["id"] == staff_view["claimant"]["id"]

    staff_notes = f.staff.get("/api/notifications").json()["items"]
    assert [n["type"] for n in staff_notes] == ["CLAIM_SUBMITTED"]
    assert f.finder.get("/api/notifications").json()["total"] == 0
    for log in f.db.scalars(select(AuditLog)):
        assert "beagle" not in str(log.details)
    for note in f.db.scalars(select(Notification)):
        assert "beagle" not in note.message


def test_submit_claim_rules(flow):
    f = flow
    assert submit(f.owner, f.lost["id"]).status_code == 422  # LOST reports cannot be claimed
    assert submit(f.finder, f.found["id"]).status_code == 403  # finder cannot claim their own find
    assert submit(f.owner, f.found["id"], "too short").status_code == 422
    assert f.owner.post(f"/api/items/{f.found['id']}/claims", json={"evidence": EVIDENCE, "status": "APPROVED"}
                        ).status_code == 422
    assert submit(f.owner, 9999).status_code == 404
    assert submit(f.owner, f.found["id"]).status_code == 201
    assert submit(f.owner, f.found["id"]).status_code == 409  # one open claim per person per item
    assert len(f.owner.get("/api/claims/mine").json()) == 1


def test_cannot_claim_closed_or_claimed_items(flow):
    f = flow
    other_found = create(f.finder, f.db, **(MATCHING_FOUND | {"title": "Grey umbrella"}))
    f.finder.post(f"/api/items/{other_found['id']}/close")
    assert submit(f.owner, other_found["id"]).status_code == 404  # closed reports are hidden

    approved(f)
    assert submit(f.api.user(), f.found["id"]).status_code == 409  # item is CLAIMED


# Staff review

def test_staff_queue_requires_staff(flow):
    f = flow
    cid = claim_id_for(f)
    assert f.owner.get("/api/staff/claims").status_code == 403
    assert f.owner.post(f"/api/staff/claims/{cid}/approve", json={}).status_code == 403
    page = f.staff.get("/api/staff/claims").json()
    assert page["total"] == 1 and page["items"][0]["id"] == cid
    assert f.staff.get("/api/staff/claims", params={"status": "APPROVED"}).json()["total"] == 0


def test_approve_claim(flow):
    f = flow
    cid = claim_id_for(f)
    second = submit(f.api.user(), f.found["id"]).json()["id"]
    response = f.staff.post(f"/api/staff/claims/{cid}/approve", json={"reason": "Lock screen photo matches"})
    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED" and response.json()["item"]["status"] == "CLAIMED"
    assert response.json()["reviewer_id"] is not None

    assert f.staff.post(f"/api/staff/claims/{cid}/approve", json={}).status_code == 409
    assert f.staff.post(f"/api/staff/claims/{second}/approve", json={}).status_code == 409  # item already claimed
    assert f.owner.get("/api/notifications", params={"unread_only": True}).json()["items"][0]["type"] == \
        "CLAIM_APPROVED"


def test_staff_cannot_review_own_claim(flow):
    f = flow
    cid = submit(f.staff, f.found["id"]).json()["id"]
    assert f.staff.post(f"/api/staff/claims/{cid}/approve", json={}).status_code == 403
    assert f.staff.post(f"/api/staff/claims/{cid}/reject", json={"reason": "Self review"}).status_code == 403


def test_reject_claim_requires_reason_and_notifies(flow):
    f = flow
    cid = claim_id_for(f)
    assert f.staff.post(f"/api/staff/claims/{cid}/reject", json={}).status_code == 422
    response = f.staff.post(f"/api/staff/claims/{cid}/reject", json={"reason": "Description does not match"})
    assert response.status_code == 200 and response.json()["review_reason"] == "Description does not match"
    note = f.owner.get("/api/notifications").json()["items"][0]
    assert note["type"] == "CLAIM_REJECTED" and "Description does not match" in note["message"]
    assert f.owner.get(f"/api/claims/{cid}").json()["review_reason"] == "Description does not match"
    assert f.staff.post(f"/api/staff/claims/{cid}/reject", json={"reason": "Again please"}).status_code == 409


def test_rejecting_approved_claim_releases_item_and_cancels_handover(flow):
    f = flow
    cid, hid = scheduled(f)
    payload = qr(f, cid)
    assert f.staff.post(f"/api/staff/claims/{cid}/reject", json={"reason": "ID did not match"}).status_code == 200
    assert status_of(f.db, HandoverRecord, hid) == HandoverStatus.CANCELLED
    assert status_of(f.db, Item, f.found["id"]) == ItemStatus.OPEN
    assert f.staff.post("/api/staff/handovers/verify", json={"payload": payload}).status_code == 400


# Withdrawing

def test_withdraw_claim(flow):
    f = flow
    cid = claim_id_for(f)
    assert f.finder.post(f"/api/claims/{cid}/withdraw").status_code == 404
    assert f.owner.post(f"/api/claims/{cid}/withdraw").json()["status"] == "WITHDRAWN"
    assert f.owner.post(f"/api/claims/{cid}/withdraw").status_code == 409
    assert submit(f.owner, f.found["id"]).status_code == 201  # may claim again after withdrawing


def test_withdraw_approved_claim_returns_item_to_matched(flow):
    f = flow
    match_id = f.owner.get(f"/api/items/{f.lost['id']}/matches").json()[0]["id"]
    f.owner.post(f"/api/matches/{match_id}/confirm")
    cid, hid = scheduled(f)
    assert f.owner.post(f"/api/claims/{cid}/withdraw").status_code == 200
    assert status_of(f.db, HandoverRecord, hid) == HandoverStatus.CANCELLED
    assert status_of(f.db, Item, f.found["id"]) == ItemStatus.MATCHED  # a confirmed match still exists


# Handover scheduling and QR codes

def test_schedule_handover_rules(flow):
    f = flow
    cid = claim_id_for(f)
    assert f.staff.post(f"/api/staff/claims/{cid}/handover", json={}).status_code == 409  # not approved yet
    f.staff.post(f"/api/staff/claims/{cid}/approve", json={})
    response = f.staff.post(f"/api/staff/claims/{cid}/handover", json={"notes": "Desk B"})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "SCHEDULED" and body["claimant"]["name"] and body["qr_expires_at"] is None
    assert f.staff.post(f"/api/staff/claims/{cid}/handover", json={}).status_code == 409
    assert f.owner.get("/api/notifications").json()["items"][0]["type"] == "HANDOVER_SCHEDULED"
    assert f.owner.get(f"/api/claims/{cid}").json()["handover"]["status"] == "SCHEDULED"


def test_qr_issue_rules_and_hash_storage(flow):
    f = flow
    cid = approved(f)
    assert f.owner.post(f"/api/claims/{cid}/handover/qr").status_code == 409  # nothing scheduled
    f.staff.post(f"/api/staff/claims/{cid}/handover", json={})
    assert f.finder.post(f"/api/claims/{cid}/handover/qr").status_code == 404
    assert f.staff.post(f"/api/claims/{cid}/handover/qr").status_code == 404

    response = f.owner.post(f"/api/claims/{cid}/handover/qr")
    assert response.status_code == 200
    body = response.json()
    assert body["payload"].startswith("LFH-HANDOVER:") and body["svg"].startswith("<svg")
    raw = body["payload"].removeprefix("LFH-HANDOVER:")
    handover = f.db.scalar(select(HandoverRecord))
    f.db.refresh(handover)
    assert handover.qr_token_hash == hash_token(raw) and raw not in handover.qr_token_hash
    remaining = handover.qr_expires_at - utcnow()
    assert timedelta(minutes=14) < remaining <= timedelta(minutes=15)
    for log in f.db.scalars(select(AuditLog)):
        assert raw not in str(log.details)


# Verification

def test_verify_rejects_bad_payloads(flow):
    f = flow
    cid, _ = scheduled(f)
    for payload in ("hello", "LFH-HANDOVER:", "LFH-HANDOVER:not-a-real-token"):
        assert f.staff.post("/api/staff/handovers/verify", json={"payload": payload}).status_code == 400
    assert f.owner.post("/api/staff/handovers/verify", json={"payload": qr(f, cid)}).status_code == 403
    reasons = [log.details["reason"] for log in f.db.scalars(
        select(AuditLog).where(AuditLog.action == "handover.verify_failed"))]
    assert reasons == ["malformed", "malformed", "unknown"]


def test_verify_once_then_replay_fails(flow):
    f = flow
    cid, hid = scheduled(f)
    payload = qr(f, cid)
    response = f.staff.post("/api/staff/handovers/verify", json={"payload": payload})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "VERIFIED" and body["qr_used"] is True and body["verified_at"] is not None
    assert body["claimant"]["email"]  # so staff can check the claimant's ID card

    assert f.staff.post("/api/staff/handovers/verify", json={"payload": payload}).status_code == 400
    assert f.owner.post(f"/api/claims/{cid}/handover/qr").status_code == 409  # no longer SCHEDULED


def test_regenerated_qr_revokes_previous(flow):
    f = flow
    cid, _ = scheduled(f)
    first, second = qr(f, cid), qr(f, cid)
    assert first != second
    assert f.staff.post("/api/staff/handovers/verify", json={"payload": first}).status_code == 400
    assert f.staff.post("/api/staff/handovers/verify", json={"payload": second}).status_code == 200


def test_expired_qr_rejected(flow):
    f = flow
    cid, hid = scheduled(f)
    payload = qr(f, cid)
    handover = f.db.get(HandoverRecord, hid)
    f.db.refresh(handover)
    handover.qr_expires_at = utcnow() - timedelta(seconds=1)
    f.db.commit()
    assert f.staff.post("/api/staff/handovers/verify", json={"payload": payload}).status_code == 400
    assert status_of(f.db, HandoverRecord, hid) == HandoverStatus.SCHEDULED


def test_staff_cannot_verify_own_claim(flow):
    f = flow
    other_staff = f.api.user(UserRole.STAFF)
    cid = submit(f.staff, f.found["id"]).json()["id"]
    other_staff.post(f"/api/staff/claims/{cid}/approve", json={})
    other_staff.post(f"/api/staff/claims/{cid}/handover", json={})
    payload = f.staff.post(f"/api/claims/{cid}/handover/qr").json()["payload"]
    assert f.staff.post("/api/staff/handovers/verify", json={"payload": payload}).status_code == 403
    assert other_staff.post("/api/staff/handovers/verify", json={"payload": payload}).status_code == 200


# Completion

def test_complete_requires_verification_and_identity_confirmation(flow):
    f = flow
    cid, hid = scheduled(f)
    url = f"/api/staff/handovers/{hid}/complete"
    assert f.staff.post(url, json={"identity_confirmed": True}).status_code == 409  # not scanned yet
    f.staff.post("/api/staff/handovers/verify", json={"payload": qr(f, cid)})
    assert f.staff.post(url, json={}).status_code == 422
    assert f.staff.post(url, json={"identity_confirmed": False}).status_code == 422
    assert f.owner.post(url, json={"identity_confirmed": True}).status_code == 403


def test_complete_handover_updates_everything(flow):
    f = flow
    match_id = f.owner.get(f"/api/items/{f.lost['id']}/matches").json()[0]["id"]
    f.owner.post(f"/api/matches/{match_id}/confirm")
    rival = f.api.user()
    rival_claim = submit(rival, f.found["id"]).json()["id"]
    cid, hid = verified(f)

    response = f.staff.post(f"/api/staff/handovers/{hid}/complete",
                            json={"identity_confirmed": True, "notes": "Checked campus ID"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED" and body["completed_at"] and "Checked campus ID" in body["notes"]

    assert status_of(f.db, Claim, cid) == ClaimStatus.COMPLETED
    found = f.db.get(Item, f.found["id"])
    assert found.status == ItemStatus.RETURNED and found.resolved_at is not None
    assert status_of(f.db, Item, f.lost["id"]) == ItemStatus.RETURNED  # owner's confirmed lost report
    rival_row = f.db.get(Claim, rival_claim)
    assert rival_row.status == ClaimStatus.REJECTED and "returned" in rival_row.review_reason
    assert rival.get("/api/notifications").json()["items"][0]["type"] == "CLAIM_REJECTED"
    assert f.owner.get("/api/notifications").json()["items"][0]["type"] == "HANDOVER_COMPLETED"
    assert f.owner.get(f"/api/claims/{cid}").json()["handover"]["status"] == "COMPLETED"

    assert f.staff.post(f"/api/staff/handovers/{hid}/complete", json={"identity_confirmed": True}).status_code == 409
    assert f.staff.post(f"/api/staff/claims/{cid}/handover", json={}).status_code == 409
    assert f.owner.post(f"/api/claims/{cid}/withdraw").status_code == 409
    assert submit(f.api.user(), f.found["id"]).status_code == 409
    actions = [log.action for log in f.db.scalars(
        select(AuditLog).where(AuditLog.action.like("handover.%")).order_by(AuditLog.id))]
    assert actions == ["handover.scheduled", "handover.qr_issued", "handover.verified", "handover.completed"]


def test_completion_is_atomic(flow, monkeypatch):
    f = flow
    cid, hid = verified(f)

    def fail(*args, **kwargs):
        raise RuntimeError("simulated failure after status changes")

    monkeypatch.setattr(claim_service, "notify", fail)
    with pytest.raises(RuntimeError):
        f.staff.post(f"/api/staff/handovers/{hid}/complete", json={"identity_confirmed": True})
    assert status_of(f.db, HandoverRecord, hid) == HandoverStatus.VERIFIED
    assert status_of(f.db, Claim, cid) == ClaimStatus.APPROVED
    assert status_of(f.db, Item, f.found["id"]) == ItemStatus.CLAIMED

    monkeypatch.undo()
    assert f.staff.post(f"/api/staff/handovers/{hid}/complete", json={"identity_confirmed": True}).status_code == 200


# Cancelling

def test_cancel_and_reschedule(flow):
    f = flow
    cid, hid = verified(f)
    url = f"/api/staff/handovers/{hid}/cancel"
    assert f.staff.post(url, json={}).status_code == 422
    response = f.staff.post(url, json={"reason": "Claimant did not bring ID"})
    assert response.status_code == 200 and response.json()["status"] == "CANCELLED"
    assert f.staff.post(url, json={"reason": "Twice over"}).status_code == 409
    assert status_of(f.db, Claim, cid) == ClaimStatus.APPROVED
    assert f.staff.post(f"/api/staff/handovers/{hid}/complete", json={"identity_confirmed": True}).status_code == 409

    new = f.staff.post(f"/api/staff/claims/{cid}/handover", json={})
    assert new.status_code == 201 and new.json()["id"] != hid
    assert f.staff.post("/api/staff/handovers/verify", json={"payload": qr(f, cid)}).status_code == 200

    page = f.staff.get("/api/staff/handovers").json()
    assert [h["status"] for h in page["items"]] == ["VERIFIED", "CANCELLED"]
    assert f.staff.get("/api/staff/handovers", params={"status": "CANCELLED"}).json()["total"] == 1
    assert f.owner.get("/api/staff/handovers").status_code == 403
