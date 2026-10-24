"""Invalid transitions from docs/database-schema.md that other tests do not already cover."""

from app.db.enums import ItemStatus
from app.db.models import Item
from tests.test_claims import approved, flow, scheduled, status_of, submit, verified  # noqa: F401  (flow is a fixture)
from tests.test_items import api, image_bytes, upload  # noqa: F401  (api is a fixture)


def test_claimed_item_is_frozen(flow):  # noqa: F811
    f = flow
    match_id = f.owner.get(f"/api/items/{f.lost['id']}/matches").json()[0]["id"]
    approved(f)
    url = f"/api/items/{f.found['id']}"
    assert f.finder.patch(url, json={"title": "Renamed while claimed"}).status_code == 409
    assert upload(f.finder, f.found["id"], image_bytes()).status_code == 409
    assert f.finder.post(f"{url}/close").status_code == 409
    assert f.owner.post(f"/api/matches/{match_id}/confirm").status_code == 409  # found report no longer open
    assert status_of(f.db, Item, f.found["id"]) == ItemStatus.CLAIMED


def test_qr_and_handover_blocked_after_rejection(flow):  # noqa: F811
    f = flow
    cid, hid = scheduled(f)
    f.staff.post(f"/api/staff/claims/{cid}/reject", json={"reason": "Evidence did not hold up"})
    assert f.owner.post(f"/api/claims/{cid}/handover/qr").status_code == 409
    assert f.staff.post(f"/api/staff/claims/{cid}/handover", json={}).status_code == 409
    assert f.staff.post(f"/api/staff/handovers/{hid}/cancel", json={"reason": "Already cancelled"}).status_code == 409


def test_returned_item_accepts_no_further_changes(flow):  # noqa: F811
    f = flow
    cid, hid = verified(f)
    f.staff.post(f"/api/staff/handovers/{hid}/complete", json={"identity_confirmed": True})
    url = f"/api/items/{f.found['id']}"
    assert f.finder.patch(url, json={"title": "Edited after return"}).status_code == 409
    assert f.finder.post(f"{url}/close").status_code == 409
    assert f.staff.post(f"/api/staff/claims/{cid}/reject", json={"reason": "Too late for this"}).status_code == 409
    assert f.staff.post(f"/api/staff/handovers/{hid}/cancel", json={"reason": "Too late for this"}).status_code == 409
    assert submit(f.api.user(), f.found["id"]).status_code == 409
