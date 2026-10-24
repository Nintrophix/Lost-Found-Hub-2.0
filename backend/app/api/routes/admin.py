"""Administrator endpoints under /api/admin."""

from typing import Annotated

from fastapi import APIRouter, Query, status
from pydantic import AwareDatetime

from app.api.deps import AdminUser, DbSession
from app.db.enums import AccountStatus, UserRole
from app.db.models import CampusLocation, Category
from app.schemas.auth import UserResponse, UserUpdateRequest
from app.schemas.dashboard import AdminStats, AuditLogPage, AuditLogResponse, UserPage
from app.schemas.items import MAX_PAGE_SIZE
from app.schemas.reference import ReferenceCreate, ReferenceResponse, ReferenceUpdate
from app.services import admin as admin_service
from app.services import auth as auth_service
from app.services import dashboard as dashboard_service
from app.services import reference as reference_service
from app.services.errors import ServiceError

router = APIRouter(prefix="/admin", tags=["admin"])

Page = Annotated[int, Query(ge=1, le=10_000)]
PageSize = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]


def _check_range(created_from, created_to) -> None:
    if created_from and created_to and created_from > created_to:
        raise ServiceError(422, "created_from must be earlier than created_to.")


@router.get("/stats")
def stats(admin: AdminUser, db: DbSession, created_from: AwareDatetime | None = None,
          created_to: AwareDatetime | None = None) -> AdminStats:
    _check_range(created_from, created_to)
    return AdminStats(**dashboard_service.admin_stats(db, created_from, created_to))


@router.get("/users")
def list_users(
    admin: AdminUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    role: UserRole | None = None,
    account_status: AccountStatus | None = None,
    page: Page = 1,
    page_size: PageSize = 20,
) -> UserPage:
    rows, total = admin_service.list_users(db, (q or "").strip() or None, role, account_status, page,
                                           page_size)
    return UserPage(items=[UserResponse.model_validate(u) for u in rows], total=total, page=page,
                    page_size=page_size)


@router.get("/audit-logs")
def list_audit_logs(
    admin: AdminUser,
    db: DbSession,
    actor_id: int | None = None,
    action: Annotated[str | None, Query(max_length=64)] = None,
    entity_type: Annotated[str | None, Query(max_length=40)] = None,
    entity_id: int | None = None,
    created_from: AwareDatetime | None = None,
    created_to: AwareDatetime | None = None,
    page: Page = 1,
    page_size: PageSize = 50,
) -> AuditLogPage:
    _check_range(created_from, created_to)
    rows, total = admin_service.list_audit_logs(db, actor_id, action, entity_type, entity_id, created_from,
                                                created_to, page, page_size)
    return AuditLogPage(items=[AuditLogResponse(**r) for r in rows], total=total, page=page, page_size=page_size)


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserUpdateRequest, admin: AdminUser, db: DbSession) -> UserResponse:
    user = auth_service.update_user(db, admin, user_id, body.role, body.account_status)
    return UserResponse.model_validate(user)


def _register_reference_routes(path: str, model: type[Category] | type[CampusLocation]) -> None:
    @router.get(f"/{path}", name=f"admin_list_{path}")
    def list_rows(admin: AdminUser, db: DbSession) -> list[ReferenceResponse]:
        return [ReferenceResponse.model_validate(r) for r in reference_service.list_all(db, model)]

    @router.post(f"/{path}", status_code=status.HTTP_201_CREATED, name=f"admin_create_{path}")
    def create_row(body: ReferenceCreate, admin: AdminUser, db: DbSession) -> ReferenceResponse:
        row = reference_service.create(db, admin, model, body.name, body.description)
        return ReferenceResponse.model_validate(row)

    @router.patch(f"/{path}/{{row_id}}", name=f"admin_update_{path}")
    def update_row(row_id: int, body: ReferenceUpdate, admin: AdminUser, db: DbSession) -> ReferenceResponse:
        row = reference_service.update(db, admin, model, row_id, body.model_dump(exclude_unset=True))
        return ReferenceResponse.model_validate(row)


_register_reference_routes("categories", Category)
_register_reference_routes("locations", CampusLocation)
