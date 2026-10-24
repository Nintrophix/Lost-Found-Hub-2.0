"""Categories and campus locations share one shape, so one service handles both."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import CampusLocation, Category, User
from app.services import audit
from app.services.errors import ServiceError

ReferenceModel = type[Category] | type[CampusLocation]

ENTITY_NAMES: dict[ReferenceModel, str] = {Category: "category", CampusLocation: "location"}


def list_active(db: Session, model: ReferenceModel) -> list[Category | CampusLocation]:
    return list(db.scalars(select(model).where(model.is_active.is_(True)).order_by(model.name)))


def list_all(db: Session, model: ReferenceModel) -> list[Category | CampusLocation]:
    return list(db.scalars(select(model).order_by(model.name)))


def get_active(db: Session, model: ReferenceModel, row_id: int) -> Category | CampusLocation:
    row = db.get(model, row_id)
    if row is None or not row.is_active:
        raise ServiceError(422, f"Choose an available {ENTITY_NAMES[model]}.")
    return row


def _commit_unique(db: Session, model: ReferenceModel) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ServiceError(409, f"A {ENTITY_NAMES[model]} with this name already exists.") from None


def create(db: Session, actor: User, model: ReferenceModel, name: str, description: str | None):
    row = model(name=name, description=description or None)
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ServiceError(409, f"A {ENTITY_NAMES[model]} with this name already exists.") from None
    audit.record(db, f"{ENTITY_NAMES[model]}.created", ENTITY_NAMES[model], row.id, actor_id=actor.id,
                 details={"name": name})
    _commit_unique(db, model)
    return row


def update(db: Session, actor: User, model: ReferenceModel, row_id: int, changes: dict):
    row = db.get(model, row_id)
    if row is None:
        raise ServiceError(404, f"{ENTITY_NAMES[model].capitalize()} not found.")
    if "description" in changes and not changes["description"]:
        changes["description"] = None
    for field, value in changes.items():
        if field in ("name", "is_active") and value is None:
            continue
        setattr(row, field, value)
    audit.record(db, f"{ENTITY_NAMES[model]}.updated", ENTITY_NAMES[model], row.id, actor_id=actor.id,
                 details={k: v for k, v in changes.items() if k != "description"})
    _commit_unique(db, model)
    return row
