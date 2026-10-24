"""Reference data, item reports, search and image upload tests against the real API."""

from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import select

from app.api.deps import CSRF_COOKIE, CSRF_HEADER
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.enums import ClaimStatus, UserRole
from app.db.models import AuditLog, CampusLocation, Category, Claim, Item, ReportImage, User
from app.db.types import utcnow
from app.main import app

PASSWORD = "correct horse battery"


class Api:
    """Signed-in test clients plus helpers. Every unsafe request carries the CSRF header."""

    def __init__(self, make_client, db, settings):
        self._make_client = make_client
        self.db = db
        self.settings = settings
        self._n = 0

    def user(self, role: UserRole = UserRole.USER):
        self._n += 1
        email = f"{role.value.lower()}{self._n}@example.edu"
        self.db.add(User(name=f"Person {self._n}", email=email, password_hash=hash_password(PASSWORD), role=role,
                         email_verified_at=utcnow()))
        self.db.commit()
        client = self._make_client()
        assert client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200
        client.headers[CSRF_HEADER] = client.cookies.get(CSRF_COOKIE)
        return client


@pytest.fixture
def api(make_client, db, tmp_path):
    settings = get_settings().model_copy(update={"upload_dir": tmp_path / "uploads", "max_upload_bytes": 200_000})
    app.dependency_overrides[get_settings] = lambda: settings
    db.add_all([
        Category(name="Electronics"), Category(name="Keys"), Category(name="Retired", is_active=False),
        CampusLocation(name="Main Library"), CampusLocation(name="Dining Hall"),
    ])
    db.commit()
    return Api(make_client, db, settings)


def ref_id(db, model, name: str) -> int:
    return db.scalar(select(model.id).where(model.name == name))


def item_body(db, **overrides) -> dict:
    body = {
        "report_type": "LOST",
        "title": "Black phone",
        "description": "Black phone with a cracked blue case",
        "category_id": ref_id(db, Category, "Electronics"),
        "location_id": ref_id(db, CampusLocation, "Main Library"),
        "occurred_at": "2026-10-01T10:00:00+05:30",
        "color": "Black",
        "brand": "Pixel",
    }
    return body | overrides


def create(client, db, **overrides) -> dict:
    response = client.post("/api/items", json=item_body(db, **overrides))
    assert response.status_code == 201, response.text
    return response.json()


def image_bytes(fmt: str = "JPEG", size=(32, 24), exif: bool = False) -> bytes:
    out = BytesIO()
    img = Image.new("RGB", size, "red")
    if exif:
        data = Image.Exif()
        data[0x010F] = "TestCameraMaker"  # Make
        data[0x0112] = 6  # Orientation: rotate 90
        img.save(out, fmt, exif=data.tobytes())
    else:
        img.save(out, fmt)
    return out.getvalue()


def upload(client, item_id: int, data: bytes, name="photo.jpg", content_type="image/jpeg"):
    return client.post(f"/api/items/{item_id}/images", files={"file": (name, data, content_type)})


# Reference data

def test_public_reference_lists_only_active(api, client):
    names = [c["name"] for c in client.get("/api/categories").json()]
    assert names == ["Electronics", "Keys"]
    assert [loc["name"] for loc in client.get("/api/locations").json()] == ["Dining Hall", "Main Library"]


def test_admin_manages_reference_data(api, client):
    admin, user = api.user(UserRole.ADMIN), api.user()
    assert user.post("/api/admin/categories", json={"name": "Bags"}).status_code == 403

    created = admin.post("/api/admin/categories", json={"name": " Bags ", "description": "Backpacks"})
    assert created.status_code == 201 and created.json()["name"] == "Bags"
    assert admin.post("/api/admin/categories", json={"name": "Bags"}).status_code == 409

    row_id = created.json()["id"]
    assert admin.patch(f"/api/admin/categories/{row_id}", json={"is_active": False}).json()["is_active"] is False
    assert "Bags" not in [c["name"] for c in client.get("/api/categories").json()]
    assert "Bags" in [c["name"] for c in admin.get("/api/admin/categories").json()]
    assert admin.patch(f"/api/admin/categories/{row_id}", json={"name": "Keys"}).status_code == 409
    assert admin.patch("/api/admin/locations/9999", json={"name": "X"}).status_code == 404
    assert admin.post("/api/admin/locations", json={"name": "Sports Centre"}).status_code == 201


# Creating and viewing reports

def test_create_item(api):
    alex = api.user()
    item = create(alex, api.db)
    assert item["status"] == "OPEN" and item["is_owner"] is True
    assert item["occurred_at"] == "2026-10-01T04:30:00Z"
    assert item["category"]["name"] == "Electronics" and item["images"] == []
    assert not {"reporter_id", "reporter", "email"} & item.keys()
    log = api.db.scalar(select(AuditLog).where(AuditLog.action == "item.created"))
    assert log.entity_id == item["id"]


@pytest.mark.parametrize(
    ("overrides", "status"),
    [
        ({"occurred_at": (datetime.now(UTC) + timedelta(days=1)).isoformat()}, 422),
        ({"occurred_at": "2026-10-01T10:00:00"}, 422),  # naive
        ({"title": "ab"}, 422),
        ({"description": "short"}, 422),
        ({"report_type": "STOLEN"}, 422),
        ({"status": "RETURNED"}, 422),  # clients cannot set status
        ({"category_id": 9999}, 422),
    ],
)
def test_create_item_validation(api, overrides, status):
    assert api.user().post("/api/items", json=item_body(api.db, **overrides)).status_code == status


def test_create_item_rejects_inactive_category(api):
    response = api.user().post("/api/items", json=item_body(api.db, category_id=ref_id(api.db, Category, "Retired")))
    assert response.status_code == 422


def test_create_item_requires_session_and_csrf(api, client):
    assert client.post("/api/items", json=item_body(api.db)).status_code == 401
    alex = api.user()
    del alex.headers[CSRF_HEADER]
    assert alex.post("/api/items", json=item_body(api.db)).status_code == 403


def test_items_require_sign_in(api, client):
    assert client.get("/api/items").status_code == 401
    assert client.get("/api/items/1").status_code == 401


def test_other_users_see_item_without_ownership(api):
    item = create(api.user(), api.db)
    response = api.user().get(f"/api/items/{item['id']}")
    assert response.status_code == 200 and response.json()["is_owner"] is False
    assert api.user().get("/api/items/9999").status_code == 404


# Editing and closing

def test_update_item_permissions_and_fields(api):
    owner, other, staff = api.user(), api.user(), api.user(UserRole.STAFF)
    item = create(owner, api.db)
    url = f"/api/items/{item['id']}"

    assert other.patch(url, json={"title": "Hijacked title"}).status_code == 403

    keys_id = ref_id(api.db, Category, "Keys")
    response = owner.patch(url, json={"title": "Black Pixel phone", "color": None, "category_id": keys_id})
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Black Pixel phone" and body["color"] is None and body["brand"] == "Pixel"
    assert body["category"] == {"id": keys_id, "name": "Keys"}

    assert staff.patch(url, json={"description": "Moderated description text"}).status_code == 200
    assert owner.patch(url, json={"title": None}).json()["title"] == "Black Pixel phone"  # null ignored
    assert owner.patch(url, json={"report_type": "FOUND"}).status_code == 422
    retired = ref_id(api.db, Category, "Retired")
    assert owner.patch(url, json={"category_id": retired}).status_code == 422


def test_close_item_lifecycle(api):
    owner, other, staff = api.user(), api.user(), api.user(UserRole.STAFF)
    item = create(owner, api.db)
    url = f"/api/items/{item['id']}"

    assert other.post(f"{url}/close").status_code == 403
    closed = owner.post(f"{url}/close")
    assert closed.status_code == 200
    assert closed.json()["status"] == "CLOSED" and closed.json()["resolved_at"] is not None

    assert owner.post(f"{url}/close").status_code == 409
    assert owner.patch(url, json={"title": "Too late now"}).status_code == 409

    # Closed reports are hidden from everyone except the reporter and staff.
    assert other.get(url).status_code == 404
    assert staff.get(url).status_code == 200
    assert item["id"] not in [i["id"] for i in other.get("/api/items", params={"status": "CLOSED"}).json()["items"]]
    assert item["id"] in [i["id"] for i in owner.get("/api/items", params={"mine": True}).json()["items"]]


def test_close_blocked_by_open_claim(api):
    owner, claimant = api.user(), api.user()
    item = create(owner, api.db, report_type="FOUND")
    claimant_id = api.db.scalar(select(User.id).where(User.email == "user2@example.edu"))
    api.db.add(Claim(item_id=item["id"], claimant_id=claimant_id, evidence="Sticker on the back", status=ClaimStatus.PENDING))
    api.db.commit()
    assert owner.post(f"/api/items/{item['id']}/close").status_code == 409


# Search

@pytest.fixture
def catalogue(api):
    """Four reports by one user, browsed by another."""
    owner = api.user()
    keys = ref_id(api.db, Category, "Keys")
    dining = ref_id(api.db, CampusLocation, "Dining Hall")
    made = [
        create(owner, api.db, title="Black phone", occurred_at="2026-09-01T10:00:00Z"),
        create(owner, api.db, report_type="FOUND", title="Silver keys", description="Three keys on a red lanyard ring",
               category_id=keys, color="Silver", brand=None, occurred_at="2026-09-10T10:00:00Z"),
        create(owner, api.db, report_type="FOUND", title="Blue water bottle", description="Steel bottle 100% full",
               location_id=dining, color="Blue", brand="Hydro", occurred_at="2026-09-20T10:00:00Z"),
        create(owner, api.db, title="Red umbrella", description="Folding umbrella with wooden handle",
               color="Red", brand=None, occurred_at="2026-09-30T10:00:00Z"),
    ]
    owner.post(f"/api/items/{made[3]['id']}/close")
    return owner, api.user(), made


def titles(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [i["title"] for i in response.json()["items"]]


def test_default_browse_excludes_closed_newest_first(catalogue):
    _, browser, _ = catalogue
    response = browser.get("/api/items")
    assert titles(response) == ["Blue water bottle", "Silver keys", "Black phone"]
    assert response.json()["total"] == 3


def test_search_filters(catalogue, api):
    _, browser, _ = catalogue
    get = lambda **params: titles(browser.get("/api/items", params=params))  # noqa: E731
    assert get(q="keys") == ["Silver keys"]
    assert get(q="BLACK phone") == ["Black phone"]  # case-insensitive, all terms must match
    assert get(q="black keys") == []
    assert get(q="hydro") == ["Blue water bottle"]  # brand
    assert get(q="100%") == ["Blue water bottle"]
    assert get(q="%") == ["Blue water bottle"]  # wildcard is escaped: only the literal "100%" matches
    assert get(q="_") == []
    assert get(report_type="FOUND", sort="occurred_asc") == ["Silver keys", "Blue water bottle"]
    assert get(category_id=ref_id(api.db, Category, "Keys")) == ["Silver keys"]
    assert get(location_id=ref_id(api.db, CampusLocation, "Dining Hall")) == ["Blue water bottle"]
    assert get(occurred_from="2026-09-05T00:00:00Z", occurred_to="2026-09-15T00:00:00Z") == ["Silver keys"]
    assert get(sort="occurred_asc") == ["Black phone", "Silver keys", "Blue water bottle"]


def test_search_validation(catalogue):
    _, browser, _ = catalogue
    assert browser.get("/api/items", params={"page_size": 51}).status_code == 422
    assert browser.get("/api/items", params={"page": 0}).status_code == 422
    assert browser.get("/api/items", params={"occurred_from": "2026-09-05T00:00:00"}).status_code == 422
    params = {"occurred_from": "2026-09-20T00:00:00Z", "occurred_to": "2026-09-01T00:00:00Z"}
    assert browser.get("/api/items", params=params).status_code == 422


def test_pagination_and_mine(catalogue):
    owner, browser, _ = catalogue
    first = browser.get("/api/items", params={"page_size": 2}).json()
    second = browser.get("/api/items", params={"page_size": 2, "page": 2}).json()
    assert first["total"] == second["total"] == 3
    assert len(first["items"]) == 2 and len(second["items"]) == 1
    assert {i["id"] for i in first["items"]}.isdisjoint(i["id"] for i in second["items"])

    assert len(owner.get("/api/items", params={"mine": True}).json()["items"]) == 4  # includes closed
    assert browser.get("/api/items", params={"mine": True}).json()["total"] == 0
    statuses = {"status": ["OPEN", "CLOSED"], "mine": True}
    assert len(owner.get("/api/items", params=statuses).json()["items"]) == 4


def test_staff_can_browse_closed_reports(catalogue, api):
    staff = api.user(UserRole.STAFF)
    assert titles(staff.get("/api/items", params={"status": "CLOSED"})) == ["Red umbrella"]


# Images

def test_upload_reencodes_and_strips_metadata(api):
    owner, other = api.user(), api.user()
    item = create(owner, api.db)
    response = upload(owner, item["id"], image_bytes(exif=True), name="../../evil.png", content_type="text/html")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["content_type"] == "image/jpeg" and body["url"] == f"/api/images/{body['id']}"

    stored = api.db.scalar(select(ReportImage))
    path = api.settings.upload_dir / "items" / stored.stored_filename
    assert path.is_file() and stored.stored_filename.endswith(".jpg") and "evil" not in stored.stored_filename
    with Image.open(path) as img:
        assert dict(img.getexif()) == {}
        assert img.size == (24, 32)  # orientation applied before metadata was dropped
    assert stored.file_size == path.stat().st_size

    download = other.get(body["url"])
    assert download.status_code == 200 and download.content == path.read_bytes()
    assert download.headers["content-type"] == "image/jpeg"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["cache-control"].startswith("private")
    assert [i["id"] for i in other.get(f"/api/items/{item['id']}").json()["images"]] == [body["id"]]


@pytest.mark.parametrize("fmt", ["PNG", "WEBP"])
def test_upload_accepts_png_and_webp(api, fmt):
    owner = api.user()
    item = create(owner, api.db)
    response = upload(owner, item["id"], image_bytes(fmt), name="x.bin", content_type="application/octet-stream")
    assert response.status_code == 201 and response.json()["content_type"] == f"image/{fmt.lower()}"


@pytest.mark.parametrize(
    ("data", "status"),
    [
        (b"<html><script>alert(1)</script></html>", 415),
        (b"\xff\xd8\xff\xe0" + b"not really a jpeg" * 10, 415),  # JPEG magic bytes, garbage body
        (b"GIF89a" + b"\x00" * 50, 415),
        (b"", 422),
    ],
)
def test_upload_rejects_non_images(api, data, status):
    owner = api.user()
    item = create(owner, api.db)
    assert upload(owner, item["id"], data).status_code == status
    assert api.db.scalar(select(ReportImage)) is None


def test_upload_limits(api):
    owner, other = api.user(), api.user()
    item = create(owner, api.db)
    assert upload(owner, item["id"], b"\xff\xd8\xff" + b"\x00" * 200_001).status_code == 413
    assert upload(other, item["id"], image_bytes()).status_code == 403
    for _ in range(5):
        assert upload(owner, item["id"], image_bytes()).status_code == 201
    assert upload(owner, item["id"], image_bytes()).status_code == 409
    assert len(list((api.settings.upload_dir / "items").iterdir())) == 5


def test_image_access_follows_item_visibility(api, client):
    owner, other = api.user(), api.user()
    item = create(owner, api.db)
    image = upload(owner, item["id"], image_bytes()).json()
    assert client.get(image["url"]).status_code == 401
    owner.post(f"/api/items/{item['id']}/close")
    assert other.get(image["url"]).status_code == 404
    assert owner.get(image["url"]).status_code == 200
    assert upload(owner, item["id"], image_bytes()).status_code == 409  # closed report


def test_delete_image(api):
    owner, other = api.user(), api.user()
    item = create(owner, api.db)
    image = upload(owner, item["id"], image_bytes()).json()
    url = f"/api/items/{item['id']}/images/{image['id']}"
    assert other.delete(url).status_code == 403
    assert owner.delete(f"/api/items/{item['id']}/images/9999").status_code == 404
    assert owner.delete(url).status_code == 204
    assert owner.get(image["url"]).status_code == 404
    assert list((api.settings.upload_dir / "items").iterdir()) == []
    assert api.db.scalar(select(Item).where(Item.id == item["id"])) is not None
