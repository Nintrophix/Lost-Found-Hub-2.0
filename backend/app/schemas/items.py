"""Contracts for lost and found item reports."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, BeforeValidator, Field, StringConstraints

from app.db.enums import ItemStatus, ReportType
from app.schemas.auth import StrictModel
from app.schemas.reference import ReferenceSummary

MAX_PAGE_SIZE = 50


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=150)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)]
Color = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None, BeforeValidator(_blank_to_none)
]
Brand = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None, BeforeValidator(_blank_to_none)
]


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


OccurredAt = Annotated[AwareDatetime, AfterValidator(_to_utc)]


class ItemCreate(StrictModel):
    report_type: ReportType
    title: Title
    description: Description
    category_id: int
    location_id: int
    occurred_at: OccurredAt
    color: Color = None
    brand: Brand = None


class ItemUpdate(StrictModel):
    """Partial update. report_type cannot change; create a new report instead."""

    title: Title | None = None
    description: Description | None = None
    category_id: int | None = None
    location_id: int | None = None
    occurred_at: OccurredAt | None = None
    color: Color = None
    brand: Brand = None


class ItemSort(StrEnum):
    NEWEST = "newest"
    OLDEST = "oldest"
    OCCURRED_DESC = "occurred_desc"
    OCCURRED_ASC = "occurred_asc"


class ItemImageResponse(BaseModel):
    id: int
    url: str
    content_type: str
    file_size: int


class ItemResponse(BaseModel):
    """Item as shown to any signed-in user. The reporter's identity is never included."""

    id: int
    report_type: ReportType
    title: str
    description: str
    category: ReferenceSummary
    location: ReferenceSummary
    color: str | None
    brand: str | None
    occurred_at: datetime
    status: ItemStatus
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    images: list[ItemImageResponse]
    is_owner: bool = Field(description="True when the signed-in user reported this item.")


class ItemPage(BaseModel):
    items: list[ItemResponse]
    total: int
    page: int
    page_size: int
