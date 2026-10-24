"""Schema-level guarantees: migrations, foreign keys, constraints and UTC handling."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, StatementError

from app.db.base import Base
from app.db.enums import ClaimStatus, HandoverStatus, ItemStatus, ReportType
from app.db.models import Claim, HandoverRecord, Item, Match, ReportImage, User
from app.db.seed import CATEGORIES, LOCATIONS, seed
from tests.conftest import alembic_config

EXPECTED_TABLES = {
    "users",
    "categories",
    "campus_locations",
    "items",
    "report_images",
    "matches",
    "claims",
    "handover_records",
    "notifications",
    "audit_logs",
    "email_verification_tokens",
    "password_reset_tokens",
}


def test_migration_creates_all_tables(engine):
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())


def test_migration_matches_models(engine):
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"render_as_batch": True}), Base.metadata)
    assert diff == []


def test_downgrade_and_upgrade_round_trip(engine, database_url):
    cfg = alembic_config(database_url)
    command.downgrade(cfg, "base")
    assert EXPECTED_TABLES.isdisjoint(inspect(engine).get_table_names())
    command.upgrade(cfg, "head")
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())


def test_foreign_keys_enforced_on_every_connection(engine):
    for _ in range(3):
        with engine.connect() as conn:
            assert conn.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_item_rejects_unknown_reporter(db, reference_data):
    category, location = reference_data
    db.add(
        Item(
            reporter_id=9999,
            report_type=ReportType.LOST,
            title="Keys",
            description="Silver keys",
            category_id=category.id,
            location_id=location.id,
            occurred_at=datetime.now(UTC),
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_user_email_must_be_unique_and_lowercase(db, make_user):
    make_user(email="dup@example.edu")
    with pytest.raises(IntegrityError):
        make_user(email="dup@example.edu")
    db.rollback()
    with pytest.raises(IntegrityError):
        make_user(email="Upper@example.edu")


def test_enum_check_constraint_blocks_invalid_raw_value(db, make_user):
    user = make_user()
    db.commit()
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE users SET role = 'SUPERUSER' WHERE id = :id"), {"id": user.id})


def test_utc_round_trip_and_naive_rejection(db, make_item):
    ist = timezone(timedelta(hours=5, minutes=30))
    item = make_item(occurred_at=datetime(2026, 10, 1, 17, 30, tzinfo=ist))
    db.commit()
    db.expire_all()
    loaded = db.get(Item, item.id)
    assert loaded.occurred_at == datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    assert loaded.occurred_at.tzinfo is UTC
    assert loaded.created_at.tzinfo is UTC

    with pytest.raises(StatementError):
        make_item(occurred_at=datetime(2026, 10, 1, 12, 0))


def test_resolved_at_requires_terminal_status(db, make_item):
    with pytest.raises(IntegrityError):
        make_item(status=ItemStatus.OPEN, resolved_at=datetime.now(UTC))


def test_report_image_constraints(db, make_item):
    item = make_item()
    db.add(ReportImage(item=item, stored_filename="a.gif", content_type="image/gif", file_size=10))
    with pytest.raises(IntegrityError):
        db.flush()


def test_duplicate_and_self_matches_rejected(db, make_item):
    lost, found = make_item(ReportType.LOST), make_item(ReportType.FOUND)
    db.add(Match(lost_item=lost, found_item=found, score=72.5, reasons=[]))
    db.flush()

    db.add(Match(lost_item_id=lost.id, found_item_id=found.id, score=50, reasons=[]))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()

    lost = make_item(ReportType.LOST)
    db.add(Match(lost_item_id=lost.id, found_item_id=lost.id, score=50, reasons=[]))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()

    lost, found = make_item(ReportType.LOST), make_item(ReportType.FOUND)
    db.add(Match(lost_item=lost, found_item=found, score=101, reasons=[]))
    with pytest.raises(IntegrityError):
        db.flush()


def _approved_claim(db, item: Item, claimant: User, reviewer: User) -> Claim:
    claim = Claim(
        item=item,
        claimant=claimant,
        evidence="Lock screen shows my photo",
        status=ClaimStatus.APPROVED,
        reviewer=reviewer,
        reviewed_at=datetime.now(UTC),
    )
    db.add(claim)
    return claim


def _assert_rejected(db, obj, match: str) -> None:
    """Flush a single invalid object, assert the database rejects it, and roll back."""
    db.add(obj)
    with pytest.raises(IntegrityError, match=match):
        db.flush()
    db.rollback()


def test_claim_rules(db, make_item, make_user):
    item, claimant, staff = make_item(ReportType.FOUND), make_user(), make_user()
    db.add(Claim(item=item, claimant=claimant, evidence="Sticker on back"))
    db.commit()

    _assert_rejected(db, Claim(item=item, claimant=claimant, evidence="Second open claim"),
                     "claims.item_id, claims.claimant_id")
    _assert_rejected(db, Claim(item=item, claimant=make_user(), evidence="No reason", status=ClaimStatus.REJECTED,
                               reviewed_at=datetime.now(UTC)), "rejection_has_reason")
    _assert_rejected(db, Claim(item=item, claimant=make_user(), evidence="Unreviewed", status=ClaimStatus.APPROVED),
                     "review_recorded")

    _approved_claim(db, item, make_user(), staff)
    db.commit()
    _approved_claim(db, item, make_user(), staff)
    with pytest.raises(IntegrityError, match=r"UNIQUE constraint failed: claims\.item_id\n"):
        db.flush()


def test_handover_item_must_match_claim_item(db, make_item, make_user):
    staff = make_user()
    claim = _approved_claim(db, make_item(ReportType.FOUND), make_user(), staff)
    other_item = make_item(ReportType.FOUND)
    db.commit()

    _assert_rejected(db, HandoverRecord(item_id=other_item.id, claim_id=claim.id, staff_id=staff.id), "FOREIGN KEY")


def test_handover_completion_rules(db, make_item, make_user):
    staff = make_user()
    item = make_item(ReportType.FOUND)
    claim = _approved_claim(db, item, make_user(), staff)
    db.commit()
    now = datetime.now(UTC)

    def handover(**fields) -> HandoverRecord:
        return HandoverRecord(item_id=item.id, claim_id=claim.id, staff_id=staff.id, **fields)

    _assert_rejected(db, handover(status=HandoverStatus.COMPLETED), "completed_is_verified")
    _assert_rejected(db, handover(qr_token_hash="a" * 64), "qr_token_has_expiry")

    db.add(handover(status=HandoverStatus.COMPLETED, verified_at=now, completed_at=now))
    db.commit()

    _assert_rejected(db, handover(), "handover_records.claim_id")
    db.add(handover(status=HandoverStatus.CANCELLED))
    db.flush()


def test_second_completed_handover_for_item_rejected(db, make_item, make_user):
    staff = make_user()
    item = make_item(ReportType.FOUND)
    first = _approved_claim(db, item, make_user(), staff)
    db.commit()
    now = datetime.now(UTC)
    db.add(HandoverRecord(item_id=item.id, claim_id=first.id, staff_id=staff.id,
                          status=HandoverStatus.COMPLETED, verified_at=now, completed_at=now))
    first.status = ClaimStatus.COMPLETED
    db.commit()

    # A second claim on the same item cannot even be approved while one is completed...
    _assert_rejected(db, Claim(item_id=item.id, claimant_id=make_user().id, evidence="Mine too",
                               status=ClaimStatus.APPROVED, reviewed_at=now), "claims.item_id")

    # ...and even a pending claim cannot reach a second completed handover.
    other = Claim(item_id=item.id, claimant_id=make_user().id, evidence="Mine too")
    db.add(other)
    db.commit()
    _assert_rejected(db, HandoverRecord(item_id=item.id, claim_id=other.id, staff_id=staff.id,
                                        status=HandoverStatus.COMPLETED, verified_at=now, completed_at=now),
                     "handover_records.item_id")


def test_seed_is_idempotent(db):
    assert seed(db) == (len(CATEGORIES), len(LOCATIONS))
    assert seed(db) == (0, 0)
