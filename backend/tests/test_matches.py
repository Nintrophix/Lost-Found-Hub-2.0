"""Match persistence, review endpoints and notifications through the real API."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.cli import rematch
from app.db.enums import MatchStatus, NotificationType, ReportType, UserRole
from app.db.models import CampusLocation, Category, Claim, Item, Match, Notification, User
from tests.test_items import api, create, ref_id  # noqa: F401  (api is a fixture)

MATCHING_FOUND = {
    "report_type": "FOUND",
    "title": "Black Pixel phone",
    "description": "Found a black Pixel phone with a cracked case",
    "occurred_at": "2026-10-01T12:00:00Z",
}


def unrelated_found(db) -> dict:
    return {
        "report_type": "FOUND",
        "title": "Silver keys",
        "description": "Three silver keys on a red lanyard ring",
        "category_id": ref_id(db, Category, "Keys"),
        "location_id": ref_id(db, CampusLocation, "Dining Hall"),
        "color": "Silver",
        "brand": None,
        "occurred_at": "2026-10-10T10:00:00Z",
    }


def user_id(db, n: int) -> int:
    return db.scalar(select(User.id).where(User.email.like(f"%{n}@example.edu")))


@pytest.fixture
def pair(api):  # noqa: F811
    """Owner reports a LOST phone, then a finder reports a matching FOUND phone."""
    owner, finder = api.user(), api.user()
    lost = create(owner, api.db)
    found = create(finder, api.db, **MATCHING_FOUND)
    return owner, finder, lost, found


def only_match(client, item_id: int, **params) -> dict:
    matches = client.get(f"/api/items/{item_id}/matches", params=params).json()
    assert len(matches) == 1, matches
    return matches[0]


def test_matching_report_creates_suggestion_and_notifies_owner(pair, api):  # noqa: F811
    owner, finder, lost, found = pair
    match = only_match(owner, lost["id"])
    assert match["status"] == "SUGGESTED" and match["score"] >= 90
    assert match["lost_item_id"] == lost["id"] and match["found_item_id"] == found["id"]
    assert match["counterpart"]["id"] == found["id"] and match["counterpart"]["is_owner"] is False
    assert {r["signal"] for r in match["reasons"]} == {"category", "description", "color", "location", "date"}
    assert only_match(finder, found["id"])["counterpart"]["id"] == lost["id"]

    owner_notes = owner.get("/api/notifications").json()
    assert owner_notes["unread"] == 1
    note = owner_notes["items"][0]
    assert note["type"] == NotificationType.MATCH_SUGGESTED and note["item_id"] == lost["id"]
    assert "Black Pixel phone" in note["message"]
    assert finder.get("/api/notifications").json()["total"] == 0


def test_owner_creating_lost_report_is_not_notified_about_own_action(api):  # noqa: F811
    owner, finder = api.user(), api.user()
    found = create(finder, api.db, **MATCHING_FOUND)
    lost = create(owner, api.db)
    assert only_match(owner, lost["id"])["counterpart"]["id"] == found["id"]
    assert owner.get("/api/notifications").json()["total"] == 0


def test_no_suggestion_for_unrelated_or_same_reporter(api):  # noqa: F811
    owner, finder = api.user(), api.user()
    lost = create(owner, api.db)
    create(finder, api.db, **unrelated_found(api.db))
    own_found = create(owner, api.db, **MATCHING_FOUND)  # never matches the owner's own LOST report
    assert owner.get(f"/api/items/{lost['id']}/matches").json() == []
    assert api.db.scalar(select(func.count(Match.id))) == 0

    # A second, matching LOST report pairs only with the FOUND report, never with the other LOST one.
    other_lost = create(finder, api.db)
    pairs = api.db.execute(select(Match.lost_item_id, Match.found_item_id)).all()
    assert pairs == [(other_lost["id"], own_found["id"])]


def test_match_access_rules(pair, api):  # noqa: F811
    owner, finder, lost, found = pair
    stranger = api.user()
    match_id = only_match(owner, lost["id"])["id"]
    assert stranger.get(f"/api/items/{lost['id']}/matches").status_code == 403
    assert stranger.post(f"/api/matches/{match_id}/confirm").status_code == 404
    assert stranger.post(f"/api/matches/{match_id}/dismiss").status_code == 404
    assert finder.post(f"/api/matches/{match_id}/confirm").status_code == 403
    assert owner.post("/api/matches/9999/confirm").status_code == 404


def test_confirm_marks_reports_matched_without_approving_claims(pair, api):  # noqa: F811
    owner, finder, lost, found = pair
    match_id = only_match(owner, lost["id"])["id"]
    response = owner.post(f"/api/matches/{match_id}/confirm")
    assert response.status_code == 200
    assert response.json()["status"] == "CONFIRMED" and response.json()["counterpart"]["status"] == "MATCHED"
    assert owner.get(f"/api/items/{lost['id']}").json()["status"] == "MATCHED"
    assert owner.post(f"/api/matches/{match_id}/confirm").status_code == 409
    assert owner.post(f"/api/matches/{match_id}/dismiss").status_code == 409
    assert api.db.scalar(select(func.count(Claim.id))) == 0

    # Human decisions survive later edits even if the score would drop.
    owner.patch(f"/api/items/{lost['id']}", json={"category_id": ref_id(api.db, Category, "Keys")})
    assert only_match(owner, lost["id"])["status"] == "CONFIRMED"


def test_finder_can_dismiss_and_dismissal_is_permanent(pair, api):  # noqa: F811
    owner, finder, lost, found = pair
    match_id = only_match(owner, lost["id"])["id"]
    assert finder.post(f"/api/matches/{match_id}/dismiss").json()["status"] == "DISMISSED"
    assert owner.get(f"/api/items/{lost['id']}/matches").json() == []
    assert only_match(owner, lost["id"], include_dismissed=True)["status"] == "DISMISSED"

    owner.patch(f"/api/items/{lost['id']}", json={"description": "Black phone, cracked blue case, Pixel"})
    assert api.db.scalar(select(Match.status).where(Match.id == match_id)) == MatchStatus.DISMISSED
    assert owner.get(f"/api/items/{lost['id']}").json()["status"] == "OPEN"


def test_edit_that_breaks_the_match_removes_suggestion(pair, api):  # noqa: F811
    owner, _, lost, _ = pair
    body = {
        "title": "Brown leather wallet",
        "description": "Brown leather wallet with student card inside",
        "category_id": ref_id(api.db, Category, "Keys"),
        "location_id": ref_id(api.db, CampusLocation, "Dining Hall"),
        "color": "Brown",
    }
    assert owner.patch(f"/api/items/{lost['id']}", json=body).status_code == 200
    assert owner.get(f"/api/items/{lost['id']}/matches", params={"include_dismissed": True}).json() == []


def test_edit_that_creates_a_match(api):  # noqa: F811
    owner, finder = api.user(), api.user()
    lost = create(owner, api.db)
    found = create(finder, api.db, **unrelated_found(api.db))
    assert owner.get(f"/api/items/{lost['id']}/matches").json() == []
    finder.patch(f"/api/items/{found['id']}", json={
        "title": "Black Pixel phone", "description": "Black Pixel phone with a cracked case",
        "category_id": ref_id(api.db, Category, "Electronics"),
        "location_id": ref_id(api.db, CampusLocation, "Main Library"),
        "color": "Black", "occurred_at": "2026-10-01T12:00:00Z",
    })
    assert only_match(owner, lost["id"])["counterpart"]["id"] == found["id"]


def test_closing_a_report_dismisses_its_suggestions(pair, api):  # noqa: F811
    owner, finder, lost, found = pair
    assert finder.post(f"/api/items/{found['id']}/close").status_code == 200
    assert owner.get(f"/api/items/{lost['id']}/matches").json() == []
    assert api.db.scalar(select(Match.status)) == MatchStatus.DISMISSED
    later = create(api.user(), api.db, **(MATCHING_FOUND | {"title": "Pixel phone, black"}))
    assert only_match(owner, lost["id"])["counterpart"]["id"] == later["id"]


def test_staff_match_queue(pair, api):  # noqa: F811
    owner, _, lost, found = pair
    assert owner.get("/api/staff/matches").status_code == 403
    staff = api.user(UserRole.STAFF)
    page = staff.get("/api/staff/matches").json()
    assert page["total"] == 1
    row = page["items"][0]
    assert row["lost_item"]["id"] == lost["id"] and row["found_item"]["id"] == found["id"]
    assert row["score"] < 100
    assert staff.get("/api/staff/matches", params={"min_score": row["score"]}).json()["total"] == 1
    assert staff.get("/api/staff/matches", params={"min_score": 100}).json()["total"] == 0
    assert staff.get("/api/staff/matches", params={"status": "CONFIRMED"}).json()["total"] == 0
    assert staff.post(f"/api/matches/{row['id']}/confirm").status_code == 200


def test_notification_read_state(pair, api):  # noqa: F811
    owner, finder, _, _ = pair
    note_id = owner.get("/api/notifications").json()["items"][0]["id"]
    assert finder.post(f"/api/notifications/{note_id}/read").status_code == 404
    read = owner.post(f"/api/notifications/{note_id}/read")
    assert read.status_code == 200 and read.json()["read_at"] is not None
    assert owner.get("/api/notifications", params={"unread_only": True}).json()["total"] == 0

    api.db.add(Notification(user_id=user_id(api.db, 1), type=NotificationType.SYSTEM, title="Hello", message="Test"))
    api.db.commit()
    assert owner.get("/api/notifications").json()["unread"] == 1
    assert owner.post("/api/notifications/read-all").status_code == 204
    assert owner.get("/api/notifications").json()["unread"] == 0


def test_rematch_command_scores_existing_reports(api):  # noqa: F811
    db = api.db
    owner = User(name="Owner", email="owner@example.edu", password_hash="x")
    finder = User(name="Finder", email="finder@example.edu", password_hash="x")
    db.add_all([owner, finder])
    db.flush()
    common = {"category_id": ref_id(db, Category, "Electronics"), "location_id": ref_id(db, CampusLocation,
              "Main Library"), "color": "Black"}
    db.add_all([
        Item(reporter_id=owner.id, report_type=ReportType.LOST, title="Black phone",
             description="Black Pixel phone, cracked case", occurred_at=datetime(2026, 10, 1, tzinfo=UTC), **common),
        Item(reporter_id=finder.id, report_type=ReportType.FOUND, title="Pixel phone",
             description="Black Pixel phone with cracked case", occurred_at=datetime(2026, 10, 2, tzinfo=UTC),
             **common),
    ])
    db.commit()
    assert rematch(db) == 1
    assert rematch(db) == 0  # idempotent
    assert db.scalar(select(func.count(Notification.id)).where(Notification.user_id == owner.id)) == 1
