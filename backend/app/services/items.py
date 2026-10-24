"""Item report business logic: create, edit, close, view and search."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import Settings
from app.core.rate_limit import allow_for_key
from app.db.enums import ClaimStatus, ItemStatus, ReportType, UserRole
from app.db.models import CampusLocation, Category, Claim, Item, User
from app.db.types import utcnow
from app.schemas.items import ItemCreate, ItemImageResponse, ItemResponse, ItemSort
from app.schemas.reference import ReferenceSummary
from app.services import audit, matching
from app.services import reference as reference_service
from app.services.concurrency import lock_status
from app.services.errors import ServiceError

MATCH_FIELDS = frozenset({"title", "description", "brand", "color", "category_id", "location_id", "occurred_at"})
EDITABLE_STATUSES = frozenset({ItemStatus.OPEN, ItemStatus.MATCHED})
DEFAULT_BROWSE_STATUSES = (ItemStatus.OPEN, ItemStatus.MATCHED)
FUTURE_TOLERANCE = timedelta(minutes=5)
MAX_SEARCH_TERMS = 8

ITEM_NOT_FOUND = "Item not found."


@dataclass(frozen=True)
class ItemFilters:
    q: str | None = None
    report_type: ReportType | None = None
    statuses: tuple[ItemStatus, ...] = ()
    category_id: int | None = None
    location_id: int | None = None
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None
    mine: bool = False
    sort: ItemSort = ItemSort.NEWEST
    page: int = 1
    page_size: int = 20


def is_staff(user: User) -> bool:
    return user.role in (UserRole.STAFF, UserRole.ADMIN)


def can_manage(user: User, item: Item) -> bool:
    return item.reporter_id == user.id or is_staff(user)


def _can_view(user: User, item: Item) -> bool:
    return item.status != ItemStatus.CLOSED or can_manage(user, item)


def item_query() -> Select[tuple[Item]]:
    # populate_existing refreshes relationships (e.g. category after category_id changes) on reload.
    return (
        select(Item)
        .options(joinedload(Item.category), joinedload(Item.location), selectinload(Item.images))
        .execution_options(populate_existing=True)
    )


def _check_occurred_at(value: datetime) -> None:
    if value > utcnow() + FUTURE_TOLERANCE:
        raise ServiceError(422, "The date and time cannot be in the future.")


def get_viewable(db: Session, user: User, item_id: int) -> Item:
    # Flush first: populate_existing would otherwise overwrite unflushed edits with database values.
    db.flush()
    item = db.scalar(item_query().where(Item.id == item_id))
    if item is None or not _can_view(user, item):
        raise ServiceError(404, ITEM_NOT_FOUND)
    return item


def get_manageable(db: Session, user: User, item_id: int) -> Item:
    item = get_viewable(db, user, item_id)
    if not can_manage(user, item):
        raise ServiceError(403, "Only the person who reported this item or campus staff can change it.")
    return item


def create_item(db: Session, settings: Settings, user: User, data: ItemCreate) -> Item:
    if not allow_for_key("create-item", str(user.id), 30, 3600):
        raise ServiceError(429, "You have created many reports recently. Try again later.", {"Retry-After": "3600"})
    _check_occurred_at(data.occurred_at)
    reference_service.get_active(db, Category, data.category_id)
    reference_service.get_active(db, CampusLocation, data.location_id)

    item = Item(reporter_id=user.id, **data.model_dump())
    db.add(item)
    db.flush()
    audit.record(db, "item.created", "item", item.id, actor_id=user.id, details={"report_type": item.report_type.value})
    matching.refresh_matches(db, get_viewable(db, user, item.id), settings, actor_id=user.id)
    db.commit()
    return get_viewable(db, user, item.id)


def update_item(db: Session, settings: Settings, user: User, item_id: int, changes: dict) -> Item:
    item = get_manageable(db, user, item_id)
    if item.status not in EDITABLE_STATUSES:
        raise ServiceError(409, "This report can no longer be edited.")
    lock_status(db, Item, item.id, EDITABLE_STATUSES, "This report can no longer be edited.")

    # Required fields ignore an explicit null; optional ones (color, brand) are cleared by it.
    changes = {k: v for k, v in changes.items() if v is not None or k in ("color", "brand")}
    if "occurred_at" in changes:
        _check_occurred_at(changes["occurred_at"])
    if "category_id" in changes and changes["category_id"] != item.category_id:
        reference_service.get_active(db, Category, changes["category_id"])
    if "location_id" in changes and changes["location_id"] != item.location_id:
        reference_service.get_active(db, CampusLocation, changes["location_id"])

    changed = sorted(field for field, value in changes.items() if getattr(item, field) != value)
    for field in changed:
        setattr(item, field, changes[field])
    if changed:
        audit.record(db, "item.updated", "item", item.id, actor_id=user.id, details={"fields": changed})
        if MATCH_FIELDS.intersection(changed):
            matching.refresh_matches(db, get_viewable(db, user, item.id), settings, actor_id=user.id)
        db.commit()
    return get_viewable(db, user, item.id)


def close_item(db: Session, user: User, item_id: int) -> Item:
    item = get_manageable(db, user, item_id)
    if item.status not in EDITABLE_STATUSES:
        raise ServiceError(409, "This report cannot be closed in its current state.")
    lock_status(db, Item, item.id, EDITABLE_STATUSES, "This report cannot be closed in its current state.")
    open_claim = db.scalar(
        select(Claim.id).where(Claim.item_id == item.id, Claim.status.in_([ClaimStatus.PENDING, ClaimStatus.APPROVED]))
    )
    if open_claim is not None:
        raise ServiceError(409, "This item has open claims. Resolve them before closing the report.")

    item.status = ItemStatus.CLOSED
    item.resolved_at = utcnow()
    matching.dismiss_suggestions_for(db, item.id)
    audit.record(db, "item.closed", "item", item.id, actor_id=user.id)
    db.commit()
    return get_viewable(db, user, item.id)


def escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_items(db: Session, user: User, f: ItemFilters) -> tuple[list[Item], int]:
    if f.occurred_from and f.occurred_to and f.occurred_from > f.occurred_to:
        raise ServiceError(422, "occurred_from must be earlier than occurred_to.")

    conditions = []
    if not is_staff(user):
        conditions.append(or_(Item.status != ItemStatus.CLOSED, Item.reporter_id == user.id))
    if f.mine:
        conditions.append(Item.reporter_id == user.id)
    if f.statuses:
        conditions.append(Item.status.in_(f.statuses))
    elif not f.mine:
        conditions.append(Item.status.in_(DEFAULT_BROWSE_STATUSES))
    if f.report_type:
        conditions.append(Item.report_type == f.report_type)
    if f.category_id:
        conditions.append(Item.category_id == f.category_id)
    if f.location_id:
        conditions.append(Item.location_id == f.location_id)
    if f.occurred_from:
        conditions.append(Item.occurred_at >= f.occurred_from)
    if f.occurred_to:
        conditions.append(Item.occurred_at <= f.occurred_to)
    if f.q:
        for term in f.q.split()[:MAX_SEARCH_TERMS]:
            pattern = f"%{escape_like(term)}%"
            conditions.append(
                or_(*(col.ilike(pattern, escape="\\") for col in (Item.title, Item.description, Item.brand, Item.color)))
            )

    total = db.scalar(select(func.count(Item.id)).where(*conditions)) or 0
    order = {
        ItemSort.NEWEST: (Item.created_at.desc(), Item.id.desc()),
        ItemSort.OLDEST: (Item.created_at.asc(), Item.id.asc()),
        ItemSort.OCCURRED_DESC: (Item.occurred_at.desc(), Item.id.desc()),
        ItemSort.OCCURRED_ASC: (Item.occurred_at.asc(), Item.id.asc()),
    }[f.sort]
    stmt = item_query().where(*conditions).order_by(*order).offset((f.page - 1) * f.page_size).limit(f.page_size)
    return list(db.scalars(stmt).unique()), total


def to_response(item: Item, user: User) -> ItemResponse:
    return ItemResponse(
        id=item.id,
        report_type=item.report_type,
        title=item.title,
        description=item.description,
        category=ReferenceSummary.model_validate(item.category),
        location=ReferenceSummary.model_validate(item.location),
        color=item.color,
        brand=item.brand,
        occurred_at=item.occurred_at,
        status=item.status,
        resolved_at=item.resolved_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
        images=[
            ItemImageResponse(id=i.id, url=f"/api/images/{i.id}", content_type=i.content_type, file_size=i.file_size)
            for i in sorted(item.images, key=lambda i: i.id)
        ],
        is_owner=item.reporter_id == user.id,
    )
