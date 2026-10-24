"""Public reference data: active categories and campus locations."""

from fastapi import APIRouter

from app.api.deps import DbSession
from app.db.models import CampusLocation, Category
from app.schemas.reference import ReferenceResponse
from app.services import reference as reference_service

router = APIRouter(tags=["reference"])


@router.get("/categories")
def list_categories(db: DbSession) -> list[ReferenceResponse]:
    return [ReferenceResponse.model_validate(r) for r in reference_service.list_active(db, Category)]


@router.get("/locations")
def list_locations(db: DbSession) -> list[ReferenceResponse]:
    return [ReferenceResponse.model_validate(r) for r in reference_service.list_active(db, CampusLocation)]
