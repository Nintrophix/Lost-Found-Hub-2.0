"""SQLAlchemy ORM models. Keep in sync with docs/database-schema.md and Alembic migrations."""

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import (
    AccountStatus,
    ClaimStatus,
    HandoverStatus,
    ItemStatus,
    MatchStatus,
    NotificationType,
    ReportType,
    UserRole,
)
from app.db.types import UTCDateTime, utcnow

ALLOWED_IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")


def enum_column(enum_cls: type[Enum], name: str) -> SAEnum:
    """String-backed enum with a named CHECK constraint (portable and Alembic-friendly)."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        enum_column(UserRole, "user_role"), nullable=False, default=UserRole.USER, server_default=UserRole.USER.value
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    account_status: Mapped[AccountStatus] = mapped_column(
        enum_column(AccountStatus, "account_status"),
        nullable=False,
        default=AccountStatus.ACTIVE,
        server_default=AccountStatus.ACTIVE.value,
    )

    items: Mapped[list["Item"]] = relationship(back_populates="reporter")
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("1"))


class CampusLocation(Base):
    __tablename__ = "campus_locations"
    __table_args__ = (CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("1"))


class Item(TimestampMixin, Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="title_not_blank"),
        CheckConstraint("resolved_at IS NULL OR status IN ('RETURNED', 'CLOSED')", name="resolved_at_matches_status"),
        Index("ix_items_report_type_status", "report_type", "status"),
        Index("ix_items_occurred_at", "occurred_at"),
        Index("ix_items_reporter_id", "reporter_id"),
        Index("ix_items_category_id", "category_id"),
        Index("ix_items_location_id", "location_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    report_type: Mapped[ReportType] = mapped_column(enum_column(ReportType, "report_type"), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False)
    color: Mapped[str | None] = mapped_column(String(40))
    brand: Mapped[str | None] = mapped_column(String(80))
    location_id: Mapped[int] = mapped_column(ForeignKey("campus_locations.id", ondelete="RESTRICT"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    status: Mapped[ItemStatus] = mapped_column(
        enum_column(ItemStatus, "item_status"), nullable=False, default=ItemStatus.OPEN, server_default=ItemStatus.OPEN.value
    )
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    reporter: Mapped[User] = relationship(back_populates="items")
    category: Mapped[Category] = relationship()
    location: Mapped[CampusLocation] = relationship()
    images: Mapped[list["ReportImage"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", passive_deletes=True
    )
    claims: Mapped[list["Claim"]] = relationship(back_populates="item")


class ReportImage(CreatedAtMixin, Base):
    __tablename__ = "report_images"
    __table_args__ = (
        CheckConstraint("file_size > 0", name="file_size_positive"),
        CheckConstraint(
            "content_type IN (" + ", ".join(f"'{ct}'" for ct in ALLOWED_IMAGE_TYPES) + ")", name="content_type_allowed"
        ),
        Index("ix_report_images_item_id", "item_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    item: Mapped[Item] = relationship(back_populates="images")


class Match(TimestampMixin, Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("lost_item_id", "found_item_id"),
        CheckConstraint("lost_item_id <> found_item_id", name="distinct_items"),
        CheckConstraint("score >= 0 AND score <= 100", name="score_range"),
        Index("ix_matches_found_item_id", "found_item_id"),
        Index("ix_matches_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lost_item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    found_item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[MatchStatus] = mapped_column(
        enum_column(MatchStatus, "match_status"),
        nullable=False,
        default=MatchStatus.SUGGESTED,
        server_default=MatchStatus.SUGGESTED.value,
    )

    lost_item: Mapped[Item] = relationship(foreign_keys=[lost_item_id])
    found_item: Mapped[Item] = relationship(foreign_keys=[found_item_id])


class Claim(TimestampMixin, Base):
    __tablename__ = "claims"
    __table_args__ = (
        # Target for the composite FK from handover_records, guaranteeing handover.item_id == claim.item_id.
        UniqueConstraint("id", "item_id"),
        CheckConstraint("length(trim(evidence)) > 0", name="evidence_not_blank"),
        CheckConstraint("status <> 'REJECTED' OR review_reason IS NOT NULL", name="rejection_has_reason"),
        CheckConstraint(
            "status NOT IN ('APPROVED', 'REJECTED', 'COMPLETED') OR reviewed_at IS NOT NULL", name="review_recorded"
        ),
        Index("ix_claims_item_id", "item_id"),
        Index("ix_claims_claimant_id", "claimant_id"),
        Index("ix_claims_status", "status"),
        # A claimant may hold only one open claim per item.
        Index(
            "uq_claims_active_per_claimant",
            "item_id",
            "claimant_id",
            unique=True,
            sqlite_where=text("status IN ('PENDING', 'APPROVED')"),
        ),
        # At most one approved (or completed) claim per item.
        Index(
            "uq_claims_one_approved_per_item",
            "item_id",
            unique=True,
            sqlite_where=text("status IN ('APPROVED', 'COMPLETED')"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    claimant_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ClaimStatus] = mapped_column(
        enum_column(ClaimStatus, "claim_status"),
        nullable=False,
        default=ClaimStatus.PENDING,
        server_default=ClaimStatus.PENDING.value,
    )
    review_reason: Mapped[str | None] = mapped_column(Text)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    item: Mapped[Item] = relationship(back_populates="claims")
    claimant: Mapped[User] = relationship(foreign_keys=[claimant_id])
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewer_id])
    handovers: Mapped[list["HandoverRecord"]] = relationship(back_populates="claim", overlaps="item")


class HandoverRecord(TimestampMixin, Base):
    __tablename__ = "handover_records"
    __table_args__ = (
        ForeignKeyConstraint(["claim_id", "item_id"], ["claims.id", "claims.item_id"], ondelete="RESTRICT"),
        CheckConstraint("qr_token_hash IS NULL OR qr_expires_at IS NOT NULL", name="qr_token_has_expiry"),
        CheckConstraint(
            "status <> 'COMPLETED' OR (verified_at IS NOT NULL AND completed_at IS NOT NULL)",
            name="completed_is_verified",
        ),
        Index("ix_handover_records_item_id", "item_id"),
        Index("ix_handover_records_status", "status"),
        # Only one completed handover per item.
        Index(
            "uq_handover_records_completed_item",
            "item_id",
            unique=True,
            sqlite_where=text("status = 'COMPLETED'"),
        ),
        # Only one live (non-cancelled) handover per claim.
        Index(
            "uq_handover_records_live_claim",
            "claim_id",
            unique=True,
            sqlite_where=text("status IN ('SCHEDULED', 'VERIFIED', 'COMPLETED')"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    claim_id: Mapped[int] = mapped_column(Integer, nullable=False)
    staff_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[HandoverStatus] = mapped_column(
        enum_column(HandoverStatus, "handover_status"),
        nullable=False,
        default=HandoverStatus.SCHEDULED,
        server_default=HandoverStatus.SCHEDULED.value,
    )
    # SHA-256 hex digest of the raw QR token. The raw token is never stored.
    qr_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    qr_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    token_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    notes: Mapped[str | None] = mapped_column(Text)

    claim: Mapped[Claim] = relationship(back_populates="handovers", overlaps="item")
    item: Mapped[Item] = relationship(overlaps="claim,handovers")
    staff: Mapped[User] = relationship()


class Notification(CreatedAtMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id_read_at", "user_id", "read_at"),
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[NotificationType] = mapped_column(enum_column(NotificationType, "notification_type"), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id", ondelete="SET NULL"))
    claim_id: Mapped[int | None] = mapped_column(ForeignKey("claims.id", ondelete="SET NULL"))
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    user: Mapped[User] = relationship(back_populates="notifications")


class AuditLog(CreatedAtMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity_type_entity_id", "entity_type", "entity_id"),
        Index("ix_audit_logs_actor_id", "actor_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    # Must never contain secrets, tokens, passwords or private claim evidence.
    details: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)

    actor: Mapped[User | None] = relationship()


class _UserTokenMixin(CreatedAtMixin):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # SHA-256 hex digest of the raw token sent to the user.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class EmailVerificationToken(_UserTokenMixin, Base):
    __tablename__ = "email_verification_tokens"


class PasswordResetToken(_UserTokenMixin, Base):
    __tablename__ = "password_reset_tokens"


class UserSession(CreatedAtMixin, Base):
    """Server-side login session. The browser holds the raw token in an HttpOnly cookie."""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # SHA-256 hex digests of the raw session and CSRF tokens.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    user: Mapped[User] = relationship()
