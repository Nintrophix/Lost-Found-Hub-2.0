# Database Schema

Source of truth: `backend/app/db/models.py` and `backend/migrations/versions/`. Keep this file in sync with both.

## Conventions

- SQLite, SQLAlchemy 2.x, Alembic (batch mode for SQLite `ALTER` support).
- `PRAGMA foreign_keys=ON` and `busy_timeout=5000` are set on every connection (`app/db/session.py`).
- All timestamps use `UTCDateTime`: stored as naive UTC, returned as timezone-aware UTC. Naive input is rejected.
- Enums are stored as `VARCHAR(32)` with a named `CHECK` constraint listing allowed values.
- Constraint names follow the convention in `app/db/base.py` (`pk_`, `fk_`, `uq_`, `ck_`, `ix_`).
- Partial unique indexes (`uq_*` with a `WHERE` clause) enforce rules that depend on status.
- Token columns (`token_hash`, `qr_token_hash`) hold a SHA-256 hex digest. Raw tokens are never stored.

## Tables

### users
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | VARCHAR(120) | not blank |
| email | VARCHAR(254) | unique, must be lowercase |
| password_hash | VARCHAR(255) | |
| campus_id | VARCHAR(20) null | SRM register number or employee ID; unique, must be uppercase. Required by the API at sign-up; null only for older or CLI-created accounts |
| department | VARCHAR(100) null | required by the API at sign-up |
| phone | VARCHAR(20) null | optional; digits with optional leading `+` |
| role | user_role | `USER` (default), `STAFF`, `ADMIN`. Registration always creates `USER`. |
| email_verified_at | DATETIME null | null means unverified |
| account_status | account_status | `ACTIVE` (default), `SUSPENDED`, `DEACTIVATED` |
| created_at, updated_at | DATETIME | |

### categories / campus_locations
`id`, `name` (unique, not blank; 80 / 120 chars), `description` (TEXT null), `is_active` (default true). Inactive rows stay referenced by old items but are hidden from new reports.

### items
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| reporter_id | FK users RESTRICT | indexed |
| report_type | report_type | `LOST`, `FOUND` |
| title | VARCHAR(150) | not blank |
| description | TEXT | |
| category_id | FK categories RESTRICT | indexed |
| color | VARCHAR(40) null | |
| brand | VARCHAR(80) null | |
| location_id | FK campus_locations RESTRICT | indexed |
| occurred_at | DATETIME | when the item was lost or found; indexed |
| status | item_status | `OPEN` (default), `MATCHED`, `CLAIMED`, `RETURNED`, `CLOSED` |
| resolved_at | DATETIME null | only allowed when status is `RETURNED` or `CLOSED` |
| created_at, updated_at | DATETIME | |

Index `ix_items_report_type_status (report_type, status)` serves the explore page filters.

### report_images
`id`, `item_id` (FK items CASCADE, indexed), `stored_filename` (unique, server-generated), `content_type` (`image/jpeg`, `image/png`, `image/webp` only), `file_size` (> 0), `created_at`. Files live in `UPLOAD_DIR`, never in a public static folder.

### matches
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| lost_item_id | FK items CASCADE | |
| found_item_id | FK items CASCADE | indexed |
| score | FLOAT | 0 to 100 |
| reasons | JSON | list of per-signal explanations |
| status | match_status | `SUGGESTED` (default), `CONFIRMED`, `DISMISSED`; indexed |
| created_at, updated_at | DATETIME | |

Constraints: unique `(lost_item_id, found_item_id)`; `lost_item_id <> found_item_id`. The service layer must ensure `lost_item_id` is a `LOST` item and `found_item_id` a `FOUND` item (cross-row rule, not expressible as a CHECK). A score never approves a claim.

### claims
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| item_id | FK items RESTRICT | indexed |
| claimant_id | FK users RESTRICT | indexed |
| evidence | TEXT | private; never in public responses; not blank |
| status | claim_status | `PENDING` (default), `APPROVED`, `REJECTED`, `WITHDRAWN`, `COMPLETED`; indexed |
| review_reason | TEXT null | required when `REJECTED` |
| reviewer_id | FK users SET NULL | |
| reviewed_at | DATETIME null | required when `APPROVED`, `REJECTED` or `COMPLETED` |
| created_at, updated_at | DATETIME | |

Constraints:
- `uq_claims_id_item_id (id, item_id)`: target of the composite FK from handover_records.
- `uq_claims_active_per_claimant (item_id, claimant_id) WHERE status IN ('PENDING','APPROVED')`: one open claim per person per item.
- `uq_claims_one_approved_per_item (item_id) WHERE status IN ('APPROVED','COMPLETED')`: at most one winning claim per item.

### handover_records
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| item_id | FK items RESTRICT | indexed |
| claim_id | INTEGER | with item_id, composite FK to `claims (id, item_id)` RESTRICT |
| staff_id | FK users RESTRICT | staff member coordinating the handover |
| status | handover_status | `SCHEDULED` (default), `VERIFIED`, `COMPLETED`, `CANCELLED`; indexed |
| qr_token_hash | VARCHAR(64) null | unique; SHA-256 of the raw token |
| qr_expires_at | DATETIME null | required when a token hash is set |
| token_used_at | DATETIME null | set once, on the single successful scan |
| verified_at, completed_at | DATETIME null | both required when `COMPLETED` |
| notes | TEXT null | |
| created_at, updated_at | DATETIME | |

Constraints:
- Composite FK guarantees `handover.item_id` equals the claim's `item_id`.
- `uq_handover_records_completed_item (item_id) WHERE status = 'COMPLETED'`: one completed handover per item.
- `uq_handover_records_live_claim (claim_id) WHERE status IN ('SCHEDULED','VERIFIED','COMPLETED')`: one live handover per claim. Cancelled records are kept for history.
- Revoking a QR token: replace `qr_token_hash` (old token stops matching) or set status `CANCELLED`.

### notifications
`id`, `user_id` (FK users CASCADE), `type` (`MATCH_SUGGESTED`, `CLAIM_SUBMITTED`, `CLAIM_APPROVED`, `CLAIM_REJECTED`, `HANDOVER_SCHEDULED`, `HANDOVER_COMPLETED`, `SYSTEM`), `title`, `message`, `item_id` (FK items SET NULL), `claim_id` (FK claims SET NULL), `read_at` (null means unread), `created_at`. Indexes `(user_id, read_at)` and `(user_id, created_at)`.

### audit_logs
`id`, `actor_id` (FK users SET NULL, indexed), `action` (e.g. `claim.approved`), `entity_type`, `entity_id`, `metadata` (JSON; ORM attribute `details`; must never contain secrets, tokens or claim evidence), `created_at` (indexed). Index `(entity_type, entity_id)`.

### email_verification_tokens / password_reset_tokens
`id`, `user_id` (FK users CASCADE, indexed), `token_hash` (unique), `expires_at`, `consumed_at` (null until used; single use), `created_at`. Issuing a new token deletes the user's unconsumed tokens of the same kind.

### user_sessions
Added in Phase 3 for server-side cookie sessions (revocable logout, password-change sign-out).
`id`, `user_id` (FK users CASCADE, indexed), `token_hash` (unique; SHA-256 of the `lf_session` cookie), `csrf_token_hash` (SHA-256 of the `XSRF-TOKEN` cookie), `expires_at`, `last_seen_at` (updated at most every 5 minutes), `revoked_at` (null while live), `created_at`.

## Relationships

```
users 1-* items (reporter)        items 1-* report_images
users 1-* claims (claimant)       items 1-* claims 1-* handover_records
users 1-* notifications           items *-* items via matches (lost x found)
users 1-* audit_logs (actor)      users 1-* *_tokens, user_sessions
```

## Status transitions

Enforced in the service layer (`app/services/items.py`, `matches.py`, `claims.py`, `handovers.py`); the database blocks the invalid end states listed above.

- **Item:** `OPEN -> MATCHED` (match confirmed). FOUND items: `OPEN|MATCHED -> CLAIMED` (claim approved) `-> RETURNED` (handover completed). LOST items: `OPEN|MATCHED -> RETURNED` when the owner's claim on a confirmed-match FOUND item completes. `OPEN|MATCHED -> CLOSED` (closed by reporter or staff; blocked while a claim is open). `CLAIMED -> OPEN|MATCHED` when the approved claim is withdrawn or rejected.
- **Match:** `SUGGESTED -> CONFIRMED | DISMISSED`.
- **Claim:** `PENDING -> APPROVED | REJECTED | WITHDRAWN`; `APPROVED -> COMPLETED` (handover done), `APPROVED -> WITHDRAWN` (claimant) or `APPROVED -> REJECTED` (staff revoke). `PENDING -> REJECTED` automatically when another claim on the item completes.
- **Handover:** `SCHEDULED -> VERIFIED` (valid QR scanned by staff; claim must be `APPROVED`; token unexpired and unused) `-> COMPLETED` (staff confirmed identity in person). `SCHEDULED|VERIFIED -> CANCELLED`. Completion updates handover, claim (`COMPLETED`) and item (`RETURNED`, `resolved_at`) in one transaction, and also rejects other `PENDING` claims on the item and sets the claimant's confirmed-match LOST reports to `RETURNED`.
- **Releasing a claimed item:** when an `APPROVED` claim is withdrawn or rejected, its live handover is `CANCELLED` and the item goes `CLAIMED -> MATCHED` (if a `CONFIRMED` match exists) or `OPEN`.
- `handover_records.staff_id` is the staff member who scheduled the handover. Who verified and completed it is recorded in `audit_logs` (`handover.verified`, `handover.completed`).

## Migrations

| Revision | File | Summary |
|---|---|---|
| 8596481954a8 | `20261024_8596481954a8_initial_schema.py` | All tables except user_sessions |
| 56b78d76eb8e | `20261024_56b78d76eb8e_add_user_sessions.py` | user_sessions |
| 656d005407df | `20261024_656d005407df_add_user_profile_fields.py` | users.campus_id (unique, uppercase check), department, phone |
