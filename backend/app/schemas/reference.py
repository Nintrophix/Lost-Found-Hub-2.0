"""Contracts for categories and campus locations."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.auth import StrictModel

ReferenceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
ReferenceDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class ReferenceCreate(StrictModel):
    name: ReferenceName
    description: ReferenceDescription | None = None


class ReferenceUpdate(StrictModel):
    name: ReferenceName | None = None
    description: ReferenceDescription | None = None
    is_active: bool | None = None


class ReferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    is_active: bool


class ReferenceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
