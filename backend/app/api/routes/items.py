"""Item report endpoints under /api/items. All require a signed-in user."""

from typing import Annotated

from fastapi import APIRouter, Query, UploadFile, status
from pydantic import AwareDatetime

from app.api.deps import AppSettings, CurrentUser, DbSession
from app.db.enums import ItemStatus, ReportType
from app.schemas.items import MAX_PAGE_SIZE, ItemCreate, ItemImageResponse, ItemPage, ItemResponse, ItemSort, ItemUpdate
from app.services import images as image_service
from app.services import items as item_service

router = APIRouter(prefix="/items", tags=["items"])


@router.get("")
def search_items(
    user: CurrentUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    report_type: ReportType | None = None,
    item_status: Annotated[list[ItemStatus] | None, Query(alias="status")] = None,
    category_id: int | None = None,
    location_id: int | None = None,
    occurred_from: AwareDatetime | None = None,
    occurred_to: AwareDatetime | None = None,
    mine: bool = False,
    sort: ItemSort = ItemSort.NEWEST,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> ItemPage:
    filters = item_service.ItemFilters(
        q=(q.strip() or None) if q else None,
        report_type=report_type,
        statuses=tuple(item_status or ()),
        category_id=category_id,
        location_id=location_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        mine=mine,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    rows, total = item_service.search_items(db, user, filters)
    return ItemPage(
        items=[item_service.to_response(i, user) for i in rows], total=total, page=page, page_size=page_size
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_item(body: ItemCreate, user: CurrentUser, db: DbSession, settings: AppSettings) -> ItemResponse:
    return item_service.to_response(item_service.create_item(db, settings, user, body), user)


@router.get("/{item_id}")
def get_item(item_id: int, user: CurrentUser, db: DbSession) -> ItemResponse:
    return item_service.to_response(item_service.get_viewable(db, user, item_id), user)


@router.patch("/{item_id}")
def update_item(item_id: int, body: ItemUpdate, user: CurrentUser, db: DbSession,
                settings: AppSettings) -> ItemResponse:
    item = item_service.update_item(db, settings, user, item_id, body.model_dump(exclude_unset=True))
    return item_service.to_response(item, user)


@router.post("/{item_id}/close")
def close_item(item_id: int, user: CurrentUser, db: DbSession) -> ItemResponse:
    return item_service.to_response(item_service.close_item(db, user, item_id), user)


@router.post("/{item_id}/images", status_code=status.HTTP_201_CREATED)
def upload_image(item_id: int, file: UploadFile, user: CurrentUser, db: DbSession,
                 settings: AppSettings) -> ItemImageResponse:
    image = image_service.add_image(db, settings, user, item_id, file)
    return image_service.to_response(image)


@router.delete("/{item_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(item_id: int, image_id: int, user: CurrentUser, db: DbSession, settings: AppSettings) -> None:
    image_service.delete_image(db, settings, user, item_id, image_id)

