"""Public data: active categories, campus locations and aggregate report counts."""

from fastapi import APIRouter

from app.api.deps import DbSession
from app.db.models import CampusLocation, Category
from app.schemas.dashboard import PublicStats
from app.schemas.reference import ReferenceResponse
from app.services import dashboard as dashboard_service
from app.services import reference as reference_service

router = APIRouter(tags=["reference"])


@router.get("/categories")
def list_categories(db: DbSession) -> list[ReferenceResponse]:
    return [ReferenceResponse.model_validate(r) for r in reference_service.list_active(db, Category)]


@router.get("/locations")
def list_locations(db: DbSession) -> list[ReferenceResponse]:
    return [ReferenceResponse.model_validate(r) for r in reference_service.list_active(db, CampusLocation)]


@router.get("/public-stats")
def public_stats(db: DbSession) -> PublicStats:
    return PublicStats(**dashboard_service.public_stats(db))
