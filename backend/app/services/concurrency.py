"""Guard against lost updates when two requests change the same row's status.

Services load a row, check its status, then write. Without a guard, two requests can both pass the
check (for example a claimant withdrawing while staff approve) and the later commit silently wins.
`lock_status` re-checks the status with an UPDATE: SQLite grants one writer at a time, so once it
succeeds the status cannot change under the caller until its transaction ends.
"""

from collections.abc import Iterable
from enum import StrEnum

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.services.errors import ServiceError


def lock_status(db: Session, model, row_id: int, allowed: Iterable[StrEnum], message: str) -> None:
    result = db.execute(
        update(model)
        .where(model.id == row_id, model.status.in_(list(allowed)))
        # Writing the same values takes the lock without changing data; pinning updated_at stops onupdate firing.
        .values(status=model.status, updated_at=model.updated_at)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise ServiceError(409, message)
