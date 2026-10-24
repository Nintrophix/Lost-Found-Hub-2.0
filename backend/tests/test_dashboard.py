"""Dashboards, admin statistics, user and audit listings, and the cleanup command."""

import os
import time
from datetime import timedelta

from sqlalchemy import select

from app.db.enums import HandoverStatus, UserRole
from app.db.models import HandoverRecord, ReportImage, UserSession
from app.db.types import utcnow
from app.services.admin import redact
from app.services.maintenance import cleanup
from tests.test_claims import EVIDENCE, flow, qr, scheduled, submit, verified  # noqa: F401  (flow is a fixture)
from tests.test_items import api, image_bytes, upload  # noqa: F401  (api is a fixture)


def zeros(**nonzero) -> dict[str, int]:
    base = {s: 0 for s in ("OPEN", "MATCHED", "CLAIMED", "RETURNED", "CLOSED")}
    return base | nonzero


# Personal dashboard

def test_user_dashboard_reflects_real_data(flow):  # noqa: F811
    f = flow
    cid = submit(f.owner, f.found["id"]).json()["id"]
    response = f.owner.get("/api/dashboard")
    assert response.status_code == 200
    d = response.json()
    assert d["reports"] == {"LOST": zeros(OPEN=1), "FOUND": zeros()}
    assert [r["id"] for r in d["recent_reports"]] == [f.lost["id"]]
    assert d["claims"]["PENDING"] == 1 and sum(d["claims"].values()) == 1
    assert [c["id"] for c in d["active_claims"]] == [cid] and d["active_claims"][0]["evidence"] == EVIDENCE
    assert d["suggestion_count"] == 1 and d["top_suggestions"][0]["counterpart"]["id"] == f.found["id"]
    assert d["unread_notifications"] == f.owner.get("/api/notifications").json()["unread"]

    finder = f.finder.get("/api/dashboard").json()
    assert finder["reports"]["FOUND"]["OPEN"] == 1 and finder["active_claims"] == []
    assert finder["top_suggestions"][0]["counterpart"]["id"] == f.lost["id"]

    stranger = f.api.user().get("/api/dashboard").json()
    assert stranger["suggestion_count"] == 0 and stranger["recent_reports"] == []
    assert sum(stranger["reports"]["LOST"].values()) == 0


def test_public_stats_are_counts_only(flow, client):  # noqa: F811
    f = flow
    assert client.get("/api/public-stats").json() == {
        "open_lost_reports": 1, "found_items_waiting": 1, "items_returned": 0,
    }
    cid, hid = verified(f)
    f.staff.post(f"/api/staff/handovers/{hid}/complete", json={"identity_confirmed": True})
    assert client.get("/api/public-stats").json() == {
        "open_lost_reports": 1, "found_items_waiting": 0, "items_returned": 1,
    }


def test_dashboard_requires_sign_in(api, client):  # noqa: F811
    assert client.get("/api/dashboard").status_code == 401


# Staff dashboard

def test_staff_dashboard_tracks_workflow(flow):  # noqa: F811
    f = flow
    assert f.owner.get("/api/staff/dashboard").status_code == 403
    get = lambda: f.staff.get("/api/staff/dashboard").json()  # noqa: E731

    start = get()
    assert start["pending_claims"] == 0 and start["oldest_pending_claim_at"] is None
    assert start["open_found_reports"] == 1 and start["high_score_suggestions"] == 1

    cid = submit(f.owner, f.found["id"]).json()["id"]
    assert get()["pending_claims"] == 1 and get()["oldest_pending_claim_at"] is not None

    f.staff.post(f"/api/staff/claims/{cid}/approve", json={})
    d = get()
    assert d["pending_claims"] == 0 and d["approved_awaiting_handover"] == 1 and d["open_found_reports"] == 0

    hid = f.staff.post(f"/api/staff/claims/{cid}/handover", json={}).json()["id"]
    d = get()
    assert d["approved_awaiting_handover"] == 0 and d["handovers"]["SCHEDULED"] == 1

    f.staff.post("/api/staff/handovers/verify", json={"payload": qr(f, cid)})
    assert get()["handovers"]["VERIFIED"] == 1
    f.staff.post(f"/api/staff/handovers/{hid}/complete", json={"identity_confirmed": True})
    d = get()
    assert d["completed_last_7_days"] == 1 and d["handovers"]["COMPLETED"] == 1
    assert d["high_score_suggestions"] == 0  # suggestions for the returned item were dismissed


# Admin statistics

def test_admin_stats(flow):  # noqa: F811
    f = flow
    admin = f.api.user(UserRole.ADMIN)
    assert f.staff.get("/api/admin/stats").status_code == 403

    cid, hid = verified(f)
    f.staff.post(f"/api/staff/handovers/{hid}/complete", json={"identity_confirmed": True})
    s = admin.get("/api/admin/stats").json()

    assert s["users"]["total"] == 4
    assert s["users"]["by_role"] == {"USER": 2, "STAFF": 1, "ADMIN": 1}
    assert s["reports"]["FOUND"] == zeros(RETURNED=1)
    assert s["reports"]["LOST"] == zeros(OPEN=1)  # the owner never confirmed the match, so it stays open
    assert s["claims"]["COMPLETED"] == 1 and s["handovers"]["COMPLETED"] == 1
    assert s["matches"]["DISMISSED"] == 1
    assert s["by_category"] == [{"id": s["by_category"][0]["id"], "name": "Electronics", "lost": 1, "found": 1}]
    assert s["by_location"][0]["name"] == "Main Library"
    assert s["monthly"] == [{"month": utcnow().strftime("%Y-%m"), "lost": 1, "found": 1}]
    assert s["found_return_rate"] == 1.0
    assert 0 <= s["median_hours_to_return"] < 1


def test_admin_stats_date_range(flow):  # noqa: F811
    f = flow
    admin = f.api.user(UserRole.ADMIN)
    future = (utcnow() + timedelta(days=1)).isoformat()
    s = admin.get("/api/admin/stats", params={"created_from": future}).json()
    assert sum(s["reports"]["LOST"].values()) == 0 and s["by_category"] == [] and s["monthly"] == []
    assert s["found_return_rate"] is None and s["median_hours_to_return"] is None
    assert s["users"]["total"] == 4  # user totals are not date-filtered

    past = (utcnow() - timedelta(days=1)).isoformat()
    assert admin.get("/api/admin/stats", params={"created_from": future, "created_to": past}).status_code == 422
    assert admin.get("/api/admin/stats", params={"created_from": "2026-10-01T00:00:00"}).status_code == 422


# Admin listings

def test_admin_user_list(flow):  # noqa: F811
    f = flow
    admin = f.api.user(UserRole.ADMIN)
    assert f.staff.get("/api/admin/users").status_code == 403

    everyone = admin.get("/api/admin/users").json()
    assert everyone["total"] == 4
    assert "password_hash" not in everyone["items"][0]
    assert [u["role"] for u in admin.get("/api/admin/users", params={"role": "STAFF"}).json()["items"]] == ["STAFF"]
    assert admin.get("/api/admin/users", params={"q": "staff"}).json()["total"] == 1  # matches email
    assert admin.get("/api/admin/users", params={"q": "%"}).json()["total"] == 0  # wildcard escaped
    page = admin.get("/api/admin/users", params={"page_size": 3, "page": 2}).json()
    assert page["total"] == 4 and len(page["items"]) == 1


def test_admin_audit_log(flow):  # noqa: F811
    f = flow
    admin = f.api.user(UserRole.ADMIN)
    assert f.staff.get("/api/admin/audit-logs").status_code == 403
    cid = submit(f.owner, f.found["id"]).json()["id"]
    f.staff.post(f"/api/staff/claims/{cid}/approve", json={})

    claims = admin.get("/api/admin/audit-logs", params={"action": "claim."}).json()
    assert [r["action"] for r in claims["items"]] == ["claim.approved", "claim.submitted"]  # newest first
    assert claims["items"][0]["actor_email"].startswith("staff")
    exact = admin.get("/api/admin/audit-logs", params={"action": "claim.submitted"}).json()
    assert exact["total"] == 1 and exact["items"][0]["entity_id"] == cid
    by_entity = admin.get("/api/admin/audit-logs", params={"entity_type": "claim", "entity_id": cid}).json()
    assert by_entity["total"] == 2
    assert "beagle" not in admin.get("/api/admin/audit-logs", params={"page_size": 50}).text


def test_redact_hides_sensitive_keys():
    assert redact({"role": ["USER", "STAFF"], "token": "abc", "nested": [{"Evidence": "x", "ok": 1}]}) == {
        "role": ["USER", "STAFF"], "token": "[redacted]", "nested": [{"Evidence": "[redacted]", "ok": 1}],
    }
    assert redact(None) is None


# Cleanup

def test_cleanup_command(flow):  # noqa: F811
    f = flow
    db, settings = f.db, f.api.settings

    # A dead session, a live one, an expired QR code and upload files.
    dead = db.scalar(select(UserSession).order_by(UserSession.id))
    dead.revoked_at = utcnow()
    cid, hid = scheduled(f)
    qr(f, cid)
    handover = db.get(HandoverRecord, hid)
    db.refresh(handover)
    handover.qr_expires_at = utcnow() - timedelta(minutes=1)
    db.commit()

    lost_upload = upload(f.owner, f.lost["id"], image_bytes()).json()
    folder = settings.upload_dir / "items"
    kept_name = db.get(ReportImage, lost_upload["id"]).stored_filename
    old_orphan, new_orphan = folder / "orphan-old.jpg", folder / "orphan-new.jpg"
    old_orphan.write_bytes(b"x")
    new_orphan.write_bytes(b"x")
    two_hours_ago = time.time() - 7200
    os.utime(old_orphan, (two_hours_ago, two_hours_ago))
    os.utime(folder / kept_name, (two_hours_ago, two_hours_ago))

    expected = {"sessions": 1, "password_reset_tokens": 0, "expired_qr_codes": 1,
                "orphaned_files": 1}
    assert cleanup(db, settings, dry_run=True) == expected
    assert old_orphan.exists() and db.get(UserSession, dead.id) is not None

    assert cleanup(db, settings) == expected
    db.expire_all()
    assert db.get(UserSession, dead.id) is None
    assert not old_orphan.exists() and new_orphan.exists() and (folder / kept_name).exists()
    handover = db.get(HandoverRecord, hid)
    assert handover.status == HandoverStatus.SCHEDULED and handover.qr_token_hash is None
    assert f.owner.get("/api/auth/me").status_code == 200  # live sessions untouched
    assert f.staff.post("/api/staff/handovers/verify", json={"payload": qr(f, cid)}).status_code == 200
    assert cleanup(db, settings) == dict.fromkeys(expected, 0)
