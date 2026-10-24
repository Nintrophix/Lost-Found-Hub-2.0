"""Domain enumerations. Stored as strings with CHECK constraints (see docs/database-schema.md)."""

from enum import StrEnum


class UserRole(StrEnum):
    USER = "USER"
    STAFF = "STAFF"
    ADMIN = "ADMIN"


class AccountStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DEACTIVATED = "DEACTIVATED"


class ReportType(StrEnum):
    LOST = "LOST"
    FOUND = "FOUND"


class ItemStatus(StrEnum):
    OPEN = "OPEN"
    MATCHED = "MATCHED"
    CLAIMED = "CLAIMED"
    RETURNED = "RETURNED"
    CLOSED = "CLOSED"


class MatchStatus(StrEnum):
    SUGGESTED = "SUGGESTED"
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"


class ClaimStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    COMPLETED = "COMPLETED"


class HandoverStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    VERIFIED = "VERIFIED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class NotificationType(StrEnum):
    MATCH_SUGGESTED = "MATCH_SUGGESTED"
    CLAIM_SUBMITTED = "CLAIM_SUBMITTED"
    CLAIM_APPROVED = "CLAIM_APPROVED"
    CLAIM_REJECTED = "CLAIM_REJECTED"
    HANDOVER_SCHEDULED = "HANDOVER_SCHEDULED"
    HANDOVER_COMPLETED = "HANDOVER_COMPLETED"
    SYSTEM = "SYSTEM"
