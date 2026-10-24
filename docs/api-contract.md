# API Contract

Base path: `/api`. JSON in and out. Interactive docs at `/api/docs` when `ENVIRONMENT` is not `production`.

Only implemented endpoints are listed. Add each endpoint here when it ships.

## Authentication model

- **Session:** `POST /api/auth/login` sets two cookies, both `Secure` (when `COOKIE_SECURE=true`), `SameSite=Lax`, `Path=/`, lifetime `SESSION_TTL_HOURS`:
  - `lf_session`: `HttpOnly`, opaque random token. Only its SHA-256 hash is stored (`user_sessions`).
  - `XSRF-TOKEN`: readable by JavaScript, opaque random token bound to the session (hash stored).
- **CSRF:** every authenticated request that is not `GET`/`HEAD`/`OPTIONS` must send header `X-XSRF-TOKEN` equal to the `XSRF-TOKEN` cookie, otherwise `403`. Angular's `HttpClient` does this automatically for same-origin relative URLs, so serve the API through the Angular dev-server proxy (`/api` to `http://localhost:8000`) rather than calling another origin.
- **Session validity:** a session is rejected (`401`) if unknown, expired, revoked, or if its user is no longer `ACTIVE` and verified. Roles are read from the database on every request, so role changes apply immediately.
- **Roles:** `USER` (default for every registration), `STAFF`, `ADMIN`. Elevated roles come only from an existing `ADMIN` (`PATCH /api/admin/users/{id}`) or the server CLI (`python -m app.cli`).
- **Rate limits** (in memory, per process): per client IP on each endpoint, plus silent per-email limits on register, resend, and forgot-password emails, and a per-account login limit (10 failed attempts per 15 minutes, `429` with `Retry-After`). Successful sign-ins do not count.
- **Email** is sent after the response, so response time does not reveal whether an account exists, and nothing is sent if the request fails.
- **Response headers** on every response: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy` and `Cross-Origin-Resource-Policy: same-origin`, and `Cache-Control: no-store` unless a route sets its own (images). `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` applies everywhere except `/api/docs`. `Strict-Transport-Security` is added in production.
- **Request size:** bodies larger than `MAX_UPLOAD_BYTES` + 1 MiB are rejected with `413`, whether sent with `Content-Length` or chunked.
- **Concurrent changes:** status transitions re-check the row's status at write time. If another request changed it first, the later one gets `409` instead of overwriting it.

## Errors

`{ "detail": "message" }` for handled errors. `422` returns `{ "detail": [ ...field errors ] }`. Unknown request fields are rejected with `422`.

| Status | Meaning |
|---|---|
| 400 | Invalid or expired link token or QR code; wrong current password; admin changing own account |
| 401 | Not signed in, or incorrect email or password |
| 403 | Missing or invalid CSRF token; insufficient role; acting on your own claim as staff; account not active; email not confirmed |
| 404 | Resource not found, or not visible to you |
| 409 | Conflict with the current state (already reviewed, not open, duplicate, changed by another request) |
| 413 | Request body or image too large |
| 415 | Upload is not a valid JPEG, PNG or WebP image |
| 422 | Validation failed (including a non-campus email domain on registration) |
| 429 | Rate limit exceeded; see `Retry-After` |
| 500 | Unexpected error; the body is a generic message with no internal details |

## Shared shapes

`UserResponse`
```json
{ "id": 1, "name": "Alex Doe", "email": "alex@example.edu", "role": "USER",
  "email_verified": true, "account_status": "ACTIVE", "created_at": "2026-10-24T05:30:38.214450Z" }
```

`MessageResponse`: `{ "message": "..." }`

Passwords: 12 to 128 characters, not only whitespace.

## System

### `GET /api/health`
Auth: none. `200 { "status": "ok", "database": "ok", "foreign_keys": "on" }`.

## Auth (`/api/auth`)

| Method and path | Auth | Body | Success |
|---|---|---|---|
| `POST /register` | none | `{ name, email, password }` | `202 MessageResponse` |
| `POST /verify-email` | none | `{ token }` | `200 MessageResponse` |
| `POST /resend-verification` | none | `{ email }` | `202 MessageResponse` |
| `POST /login` | none | `{ email, password }` | `200 UserResponse` + cookies |
| `POST /logout` | session + CSRF | none | `204`, cookies cleared |
| `GET /me` | session | none | `200 UserResponse` |
| `POST /password/forgot` | none | `{ email }` | `202 MessageResponse` |
| `POST /password/reset` | none | `{ token, new_password }` | `200 MessageResponse` |
| `POST /password/change` | session + CSRF | `{ current_password, new_password }` | `200 MessageResponse` |

Behaviour notes:
- **register:** email domain must be in `ALLOWED_EMAIL_DOMAINS` (exact match), else `422`. The response is identical whether or not the email already exists. A new account gets a verification email; an existing unverified account gets a fresh verification email; a verified account gets an "account already exists" notice. Existing accounts are never modified.
- **Email links** point to `FRONTEND_BASE_URL/verify-email#token=...` and `/reset-password#token=...`. The token is in the URL fragment so it is not sent to servers or logged. The frontend posts it to the matching endpoint.
- **verify-email / password/reset:** tokens are single use. Verification tokens last `EMAIL_VERIFICATION_TTL_HOURS`, reset tokens `PASSWORD_RESET_TTL_MINUTES`. Issuing a new token invalidates earlier unused ones. Failure: `400 "This link is invalid or has expired."`
- **login:** unknown email and wrong password both return `401 "Incorrect email or password."` Account status and verification (`403`) are only reported after the correct password. A new session is created on every login.
- **resend-verification / password/forgot:** always `202` with the same message; nothing is revealed about the account.
- **password/reset:** sets the new password, confirms the email if it was unconfirmed, and revokes every session for the user.
- **password/change:** revokes all other sessions; the current one stays signed in.

## Admin (`/api/admin`)

### `PATCH /api/admin/users/{user_id}`
Auth: session + CSRF, role `ADMIN`. Body: `{ "role"?: "USER"|"STAFF"|"ADMIN", "account_status"?: "ACTIVE"|"SUSPENDED"|"DEACTIVATED" }`.
`200 UserResponse`. `400` if targeting yourself, `404` if no such user. Setting a non-active status revokes the user's sessions. Changes are audit-logged as `admin.user_updated` with before and after values.

### Reference data administration
Auth: session + CSRF, role `ADMIN`. Same shape for `categories` and `locations`.

| Method and path | Body | Success |
|---|---|---|
| `GET /api/admin/categories`, `GET /api/admin/locations` | none | `200 [ReferenceResponse]`, including inactive rows |
| `POST /api/admin/categories`, `POST /api/admin/locations` | `{ name, description? }` | `201 ReferenceResponse` |
| `PATCH /api/admin/categories/{id}`, `PATCH /api/admin/locations/{id}` | `{ name?, description?, is_active? }` | `200 ReferenceResponse` |

Duplicate name: `409`. Unknown id: `404`. Deactivating hides a row from new reports but keeps it on existing ones. Rows are never deleted.

## Reference data

| Method and path | Auth | Success |
|---|---|---|
| `GET /api/categories` | none | `200 [ReferenceResponse]`, active only, sorted by name |
| `GET /api/locations` | none | `200 [ReferenceResponse]`, active only, sorted by name |

`ReferenceResponse`: `{ "id": 5, "name": "Clothing", "description": "...", "is_active": true }`

## Items (`/api/items`)

Every item endpoint requires a signed-in user. Item data is campus-only and never public.

`ItemResponse` (the reporter's identity is never included):
```json
{ "id": 1, "report_type": "FOUND", "title": "Grey hoodie", "description": "Grey zip hoodie left on a chair",
  "category": { "id": 5, "name": "Clothing" }, "location": { "id": 1, "name": "Main Library" },
  "color": "Grey", "brand": null, "occurred_at": "2026-10-20T09:00:00Z", "status": "OPEN",
  "resolved_at": null, "created_at": "...", "updated_at": "...",
  "images": [ { "id": 1, "url": "/api/images/1", "content_type": "image/png", "file_size": 99 } ],
  "is_owner": true }
```

| Method and path | Auth | Body | Success |
|---|---|---|---|
| `GET /api/items` | session | query, see below | `200 { items: [ItemResponse], total, page, page_size }` |
| `POST /api/items` | session + CSRF | `ItemCreate` | `201 ItemResponse` |
| `GET /api/items/{id}` | session | none | `200 ItemResponse` |
| `PATCH /api/items/{id}` | session + CSRF, reporter or staff | `ItemUpdate` | `200 ItemResponse` |
| `POST /api/items/{id}/close` | session + CSRF, reporter or staff | none | `200 ItemResponse` |
| `POST /api/items/{id}/images` | session + CSRF, reporter or staff | multipart field `file` | `201 ItemImageResponse` |
| `DELETE /api/items/{id}/images/{image_id}` | session + CSRF, reporter or staff | none | `204` |
| `GET /api/images/{image_id}` | session | none | `200` image bytes |

`ItemCreate`: `report_type` (`LOST`/`FOUND`), `title` (3 to 150 chars), `description` (10 to 2000), `category_id` and `location_id` (both must be active), `occurred_at` (ISO 8601 with timezone, stored as UTC, at most 5 minutes in the future), `color?` (40), `brand?` (80). Blank optional strings become `null`. Clients cannot set `status`. Limit: 30 reports per user per hour (`429`).

`ItemUpdate`: any `ItemCreate` field except `report_type`. `null` clears `color` or `brand` and is ignored for required fields. Allowed only while status is `OPEN` or `MATCHED` (`409` otherwise).

**Close:** `OPEN`/`MATCHED` to `CLOSED`, sets `resolved_at`. `409` if already closed or claimed, or while a `PENDING`/`APPROVED` claim exists.

**Visibility:** `CLOSED` reports return `404` to everyone except their reporter and `STAFF`/`ADMIN`. Their images follow the same rule.

**Search parameters** for `GET /api/items`:

| Parameter | Notes |
|---|---|
| `q` | Up to 100 chars, split on spaces (max 8 terms). Every term must appear in title, description, brand or color. Case-insensitive; `%` and `_` are literal. |
| `report_type` | `LOST` or `FOUND` |
| `status` | Repeatable (`status=OPEN&status=MATCHED`). Default `OPEN` and `MATCHED`, or every status when `mine=true`. |
| `category_id`, `location_id` | Exact match |
| `occurred_from`, `occurred_to` | ISO 8601 with timezone, inclusive. `from` after `to` returns `422`. |
| `mine` | `true` limits results to the caller's own reports |
| `sort` | `newest` (default), `oldest`, `occurred_desc`, `occurred_asc` |
| `page`, `page_size` | `page` starts at 1; `page_size` 1 to 50, default 20 |

**Images:**
- JPEG, PNG or WebP only, identified from the file bytes. The client filename and content type are ignored.
- Limits: `MAX_UPLOAD_BYTES` before and after processing (`413`), 5 per report (`409`), 60 uploads per user per hour (`429`).
- Every image is fully decoded and re-encoded. EXIF metadata, including GPS location, is removed after orientation is applied. Anything that fails to decode, or is over 40 megapixels, returns `415`.
- Stored as `UPLOAD_DIR/items/<random>.<ext>`, never in a public static directory.
- Downloads send `Cache-Control: private`, `X-Content-Type-Options: nosniff` and a sandboxing `Content-Security-Policy`.

## Matches

Suggestions are computed automatically whenever a report is created, or edited in a field that affects matching (title, description, brand, colour, category, location, date). Scores are recommendations only. Confirming a match never approves a claim or transfers an item.

**How a pair is found:** one `LOST` and one `FOUND` report, both `OPEN` or `MATCHED`, by different people, where the found date is between 1 day before the lost date and `MATCH_DATE_WINDOW_DAYS` after it. Pairs scoring at least `MATCH_THRESHOLD` are stored.

**Scoring** (weights from settings, default 30/25/15/15/15). Each signal gives a value from 0 to 1, or `null` when it cannot be judged. Weights of `null` signals are left out, and the rest are rescaled to a 0 to 100 score.

| Signal | Value |
|---|---|
| `category` | 1 if same category, else 0 |
| `description` | Cosine similarity of words from title, description and brand (lowercased, stopwords removed, simple plural stripping); `null` if either side has no usable words |
| `color` | 1 for the same colour (`grey` = `gray`), 0.6 for the same colour family (`navy` and `blue`), else 0; `null` if either is missing |
| `location` | 1 if same campus location, else 0 |
| `date` | 1 within a day; falls linearly to 0 at the window; 0 if found more than a day before it was lost |

`MatchReason`: `{ "signal": "color", "weight": 15, "value": 0.6, "points": 9.0, "detail": "Similar colours: Navy and Blue." }`. Points add up to the score (give or take rounding).

`MatchResponse`
```json
{ "id": 1, "score": 88.3, "status": "SUGGESTED", "reasons": [MatchReason],
  "lost_item_id": 1, "found_item_id": 2, "created_at": "...", "updated_at": "...",
  "counterpart": ItemResponse }
```
`counterpart` is the report on the other side from the caller's item (for staff acting on a match, the found report).

| Method and path | Auth | Success |
|---|---|---|
| `GET /api/items/{id}/matches?include_dismissed=false` | session; reporter of the item or staff | `200 [MatchResponse]`, best score first |
| `POST /api/matches/{id}/confirm` | session + CSRF; reporter of the LOST item or staff | `200 MatchResponse` |
| `POST /api/matches/{id}/dismiss` | session + CSRF; either reporter or staff | `200 MatchResponse` |
| `GET /api/staff/matches` | session; `STAFF` or `ADMIN` | `200 { items: [StaffMatchResponse], total, page, page_size }` |

- **Confirm:** `SUGGESTED` to `CONFIRMED`. Both reports move from `OPEN` to `MATCHED`. `409` if already reviewed or either report is no longer open. `403` for the finder.
- **Dismiss:** `SUGGESTED` to `DISMISSED`. Dismissed pairs are never suggested again.
- **Staying current:** `CONFIRMED` and `DISMISSED` are human decisions and later edits never change them. `SUGGESTED` rows are rescored on edit and removed if they drop below the threshold. Closing a report dismisses its open suggestions. Counterparts that are `CLOSED` are hidden from non-staff.
- **Unknown or unrelated match:** `404`, so match ids reveal nothing to other users.
- **Staff queue** query: `status` (default `SUGGESTED`; any `MatchStatus`), `min_score` (0 to 100), `page`, `page_size` (max 50). `StaffMatchResponse` has `lost_item` and `found_item` in place of `counterpart`.

## Notifications (`/api/notifications`)

When a new suggestion is created, the LOST report's owner gets a `MATCH_SUGGESTED` notification, unless they made the change that created it. The finder is not notified. Messages never include the other person's identity.

| Method and path | Auth | Success |
|---|---|---|
| `GET /api/notifications?unread_only=false&page=1&page_size=20` | session | `200 { items: [NotificationResponse], total, unread, page, page_size }`, newest first |
| `POST /api/notifications/{id}/read` | session + CSRF | `200 NotificationResponse`; `404` if not yours |
| `POST /api/notifications/read-all` | session + CSRF | `204` |

`NotificationResponse`: `{ "id", "type", "title", "message", "item_id", "claim_id", "read_at", "created_at" }`.

Other notification types: `CLAIM_SUBMITTED` (to every active staff and admin user except the claimant), `CLAIM_APPROVED`, `CLAIM_REJECTED` (includes the reason), `HANDOVER_SCHEDULED` and `HANDOVER_COMPLETED` (to the claimant). Claim evidence is never included.

## Claims

Only `FOUND` reports can be claimed. Evidence is private: it is returned only to the claimant and to staff, never in item responses, audit logs or notifications. A match score never approves a claim; only a staff decision does.

`ClaimResponse` (claimant view)
```json
{ "id": 1, "status": "PENDING", "evidence": "...", "review_reason": null, "reviewed_at": null,
  "created_at": "...", "updated_at": "...", "item": ItemResponse,
  "handover": { "id": 1, "status": "SCHEDULED", "qr_expires_at": null, "qr_used": false,
                "verified_at": null, "completed_at": null, "created_at": "..." } }
```
`StaffClaimResponse` adds `claimant: { id, name, email }` and `reviewer_id`. `handover` is the live or completed handover, or the most recent one, or `null`.

| Method and path | Auth | Body | Success |
|---|---|---|---|
| `POST /api/items/{id}/claims` | session + CSRF | `{ evidence }` (20 to 2000 chars) | `201 ClaimResponse` |
| `GET /api/claims/mine` | session | none | `200 [ClaimResponse]`, newest first |
| `GET /api/claims/{id}` | session; claimant or staff | none | `200 ClaimResponse` (staff get `StaffClaimResponse`) |
| `POST /api/claims/{id}/withdraw` | session + CSRF; claimant | none | `200 ClaimResponse` |
| `POST /api/claims/{id}/handover/qr` | session + CSRF; claimant | none | `200 QrTokenResponse` |

- **Submit:** `422` for a LOST report; `403` if you reported finding it; `404` if it is hidden (closed); `409` if the item is not `OPEN`/`MATCHED` or you already have an open claim on it; `429` after 10 claims per hour.
- **Withdraw:** allowed from `PENDING` or `APPROVED` (`409` otherwise). Withdrawing an approved claim cancels its live handover and returns the item to `MATCHED` (if a confirmed match exists) or `OPEN`. You can claim again afterwards.
- **Visibility:** other users, including the finder, get `404` for a claim.

## Staff workspace (`/api/staff`)

Auth: session + CSRF for writes, role `STAFF` or `ADMIN`. Staff cannot review, schedule, verify or complete their own claims (`403`).

| Method and path | Body | Success |
|---|---|---|
| `GET /api/staff/claims?status=PENDING&page&page_size` | none | `200 { items: [StaffClaimResponse], total, page, page_size }`, oldest first |
| `GET /api/staff/claims/{id}` | none | `200 StaffClaimResponse` |
| `POST /api/staff/claims/{id}/approve` | `{ reason? }` | `200 StaffClaimResponse` |
| `POST /api/staff/claims/{id}/reject` | `{ reason }` (5 to 1000 chars, required) | `200 StaffClaimResponse` |
| `POST /api/staff/claims/{id}/handover` | `{ notes? }` | `201 HandoverResponse` |
| `GET /api/staff/handovers?status&page&page_size` | none | `200 { items: [HandoverResponse], total, page, page_size }`, newest first |
| `POST /api/staff/handovers/verify` | `{ payload }` (the scanned QR text) | `200 HandoverResponse` |
| `POST /api/staff/handovers/{id}/complete` | `{ identity_confirmed: true, notes? }` | `200 HandoverResponse` |
| `POST /api/staff/handovers/{id}/cancel` | `{ reason }` | `200 HandoverResponse` |

`HandoverResponse` is the handover summary plus `claim_id`, `item_id`, `item_title`, `staff_id` (who scheduled it), `notes` and `claimant: { id, name, email }`, so staff can check the claimant's campus ID at the desk.

- **Approve:** `PENDING` only. Item moves to `CLAIMED`. `409` if another claim on the item is already approved (also enforced by a database index). Other pending claims stay pending until the handover completes.
- **Reject:** from `PENDING` or `APPROVED`. Rejecting an approved claim cancels its live handover and releases the item, as for withdraw.

## QR handover

1. **Schedule:** staff create a handover for an `APPROVED` claim. `409` if one is already live (`SCHEDULED` or `VERIFIED`) or completed.
2. **Issue:** the claimant calls `POST /api/claims/{id}/handover/qr`. It works only while the handover is `SCHEDULED` (`409` otherwise), with at most 10 calls per hour. Response:
   ```json
   { "payload": "LFH-HANDOVER:<random token>", "expires_at": "...", "svg": "<svg ...>" }
   ```
   The token is 256 random bits, valid for `QR_TOKEN_TTL_MINUTES` (default 15). Only its SHA-256 hash is stored, so the raw token cannot be fetched again. Calling again issues a new token and revokes the old one.
3. **Verify:** staff scan the code and post its text. The scan succeeds only if the token hash matches, the handover is `SCHEDULED`, the token is unused and unexpired, the claim is `APPROVED` and the item is `CLAIMED`. Success marks the token used and the handover `VERIFIED`. A conditional update makes this single use, even if two scans race. Every failure returns the same `400 "This QR code is invalid, expired or already used."`, and the specific reason is audit-logged.
4. **Complete:** after checking the claimant's identity in person, staff post `identity_confirmed: true`. Anything else returns `422`, because holding the QR code is not proof of ownership on its own. One transaction then:
   - sets the handover to `COMPLETED`, the claim to `COMPLETED`, and the item to `RETURNED` with `resolved_at`
   - rejects other pending claims on the item, with a reason, and notifies those claimants
   - dismisses open suggestions for the item
   - sets the claimant's own LOST reports that have a confirmed match to this item to `RETURNED`
   - notifies the claimant and writes the audit entry

   If any step fails, nothing changes. `409` if the handover is not `VERIFIED` or was already completed.
5. **Cancel:** a `SCHEDULED` or `VERIFIED` handover can be cancelled with a reason. The claim stays `APPROVED`, so a new handover (and a new QR code) can be scheduled.

## Dashboards

Every figure is computed from the database on request. Count maps always list every status, with `0` where there are none.

### `GET /api/dashboard`
Auth: session. The caller's own data only.
```json
{ "reports": { "LOST": { "OPEN": 1, "MATCHED": 0, "CLAIMED": 0, "RETURNED": 0, "CLOSED": 0 }, "FOUND": { ... } },
  "recent_reports": [ItemResponse],
  "claims": { "PENDING": 1, "APPROVED": 0, "REJECTED": 0, "WITHDRAWN": 0, "COMPLETED": 0 },
  "active_claims": [ClaimResponse],
  "suggestion_count": 1,
  "top_suggestions": [MatchResponse],
  "unread_notifications": 2 }
```
`recent_reports` holds the 5 newest. `active_claims` lists `PENDING` and `APPROVED` claims. `top_suggestions` holds the 5 best `SUGGESTED` matches on any of the caller's reports.

### `GET /api/staff/dashboard`
Auth: session, `STAFF` or `ADMIN`.
```json
{ "pending_claims": 3, "oldest_pending_claim_at": "...", "approved_awaiting_handover": 1,
  "handovers": { "SCHEDULED": 1, "VERIFIED": 0, "COMPLETED": 4, "CANCELLED": 0 },
  "completed_last_7_days": 2, "open_found_reports": 12, "high_score_suggestions": 5, "high_score_threshold": 80.0 }
```
`approved_awaiting_handover` counts approved claims with no live or completed handover.

### `GET /api/admin/stats?created_from&created_to`
Auth: session, `ADMIN`. Optional ISO 8601 bounds with timezone, applied to the `created_at` of reports, claims, handovers and matches. User totals are never date-filtered. `422` if `from` is after `to` or a bound has no timezone.

Response fields:
- `generated_at`, `created_from`, `created_to`
- `users`: `{ total, by_role, by_status, verified }`
- `reports`: counts by type, then status
- `claims`, `handovers`, `matches`: counts by status
- `by_category`, `by_location`: `[{ id, name, lost, found }]`, busiest first
- `monthly`: `[{ month: "YYYY-MM", lost, found }]` by UTC creation month
- `found_return_rate`: returned FOUND reports divided by FOUND reports, or `null` when there are none
- `median_hours_to_return`: from FOUND report creation to `resolved_at`, or `null` when nothing has been returned

### Admin listings

| Method and path | Query | Success |
|---|---|---|
| `GET /api/admin/users` | `q` (name or email contains; literal `%` and `_`), `role`, `account_status`, `verified`, `page`, `page_size` | `200 { items: [UserResponse], total, page, page_size }`, newest first |
| `GET /api/admin/audit-logs` | `actor_id`, `action` (exact, or a prefix when it ends with `.`, e.g. `claim.`), `entity_type`, `entity_id`, `created_from`, `created_to`, `page`, `page_size` (default 50) | `200 { items: [AuditLogResponse], total, page, page_size }`, newest first |

`AuditLogResponse`: `{ id, actor_id, actor_email, action, entity_type, entity_id, details, created_at }`. Audit details are written without secrets or evidence. As an extra safeguard, keys such as `token`, `password` and `evidence` are always shown as `[redacted]`.
