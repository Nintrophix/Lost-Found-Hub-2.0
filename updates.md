# Project Updates

## Current status

- **Phases 2 to 8 complete for the backend.** It provides authentication, reports and search, images, matching, claims, the QR handover, dashboards and administration, and has passed a security review and a clean-setup check.
- **UI:** deferred by the owner, who will add it later. Phase 1 (UI) was skipped on purpose; `frontend/` is still the original stub.
- **Tests:** 198 passing (`python -m pytest` in `backend/`), and migrations match the models.
- Last updated: 2026-10-24.

## Persistent decisions

General
- Fixed stack: Angular + FastAPI + SQLite/SQLAlchemy 2.x + Alembic + Pytest. Do not change.
- Backend first; frontend is untouched until the owner asks for UI work.
- Do not read other chat sessions; use this file for continuity.
- Services raise `ServiceError(status, detail)`; `app/main.py` renders it as `{"detail": ...}`. Each service function is one transaction.
- Status transitions call `concurrency.lock_status` before writing (a same-value UPDATE that re-checks status and takes SQLite's write lock), so concurrent requests get `409` rather than overwriting each other.
- Shared query builders are public (`items.item_query`, `matches.match_query`, `claims.claim_query`, `items.escape_like`); response builders live in `app/api/presenters.py`.
- `tests/conftest.py` pins test settings through environment variables so `backend/.env` cannot change test behaviour. `tests/test_security.py` pins the route inventory (53); update it deliberately when adding routes.

Data
- Datetimes are always timezone-aware UTC (`UTCDateTime`); naive datetimes raise.
- Enums are strings with CHECK constraints; rules that depend on status use partial unique indexes. `handover_records (claim_id, item_id)` is a composite FK to `claims (id, item_id)`.
- Item reloads use `populate_existing`; `get_viewable` flushes first, or the reload discards unflushed edits.
- Alembic migration template imports `app.db.types` so custom column types render.

Security and privacy
- Server-side sessions (`user_sessions`), not JWT: `lf_session` HttpOnly cookie plus a session-bound `XSRF-TOKEN` cookie checked against `X-XSRF-TOKEN` (Angular defaults). The frontend must call the API same-origin via a proxy.
- Raw tokens (session, CSRF, QR, verification, reset) are never stored, only SHA-256 hex digests. No `SECRET_KEY` exists because nothing needs one (removed in Phase 8 as unused).
- Elevated roles only via `python -m app.cli` or an ADMIN through `PATCH /api/admin/users/{id}`. Request schemas use `extra="forbid"`.
- Email links carry tokens in the URL fragment. Emails are sent as background tasks after the response. The console email backend is development only.
- The per-account login limit counts failures only. Duplicate registration does the same hashing work as a new one.
- Item data requires sign-in; only categories and locations are public. CLOSED reports are visible only to the reporter and staff. Responses never include the reporter's identity.
- Claim evidence is visible only to the claimant and staff; never in item responses, audit logs or notifications. Audit output also passes through `admin.redact`.
- Uploads are identified by bytes, re-encoded with Pillow (EXIF and GPS stripped) and served only through `GET /api/images/{id}`.
- Security headers middleware on every response; body size limit `MAX_UPLOAD_BYTES` + 1 MiB (413).
- Rate limiter is in-memory: run one worker or replace it with a shared store before scaling.

Domain
- Match scores are recommendations only and never approve claims. Weights are renormalised over available signals. CONFIRMED and DISMISSED matches are never changed by recomputation.
- Only the LOST reporter (or staff) confirms a match; either side or staff dismisses. Only the LOST reporter is notified of new suggestions, and not when they caused it.
- Handover is two-step: single-use QR scan (`verify`), then `complete` with `identity_confirmed: true`. QR payload `LFH-HANDOVER:<token>`, reissue revokes the old one, SVG via `segno`.
- Staff can never review, schedule, verify or complete their own claims. New claims notify every active STAFF/ADMIN user.
- Dashboards compute every figure from the database per request.

### UI and site norms (owner requirements, apply when the frontend is built)

Avoid: purple gradients, pill-shaped buttons, fake reviews, fake metrics or customer counters, vague hero text, emoji icons, em dashes in copy, any "Vite" or "React" mentions, default or placeholder content, cursor animations, AI-generated stock photos, "made by AI" tags.

Include: site favicon, privacy policy page, custom 404 page, accurate page titles and meta descriptions, canonical tags, exactly one `h1` per page, `sitemap.xml`, internal links, breadcrumbs, structured data (JSON-LD), meaningful alt text, zero console errors, no production source maps (`sourceMap: false` in the Angular production config).

Design direction from the master prompt: midnight navy, electric lime, cool off-white; responsive; minimal animation. 21st.dev components only when explicitly approved, adapted to Angular.

## Completed

- **Phase 2, database:** 12 tables with FKs, CHECKs, indexes and partial unique indexes; Alembic `8596481954a8`; seed; backup/restore CLI.
- **Phase 3, authentication:** registration with domain allowlist, email verification, login/logout, password forgot/reset/change, roles, CSRF, rate limits, admin CLI; migration `56b78d76eb8e` (`user_sessions`).
- **Phase 4, reports:** categories/locations (public lists, admin CRUD); item create, edit, close, detail; search, filters, sort, pagination; secure image upload and download.
- **Phase 5, matching:** pure scoring engine, persistence on create/edit, explanations, confirm/dismiss, staff queue, notifications, `rematch` CLI.
- **Phase 6, claims and QR handover:** private-evidence claims, staff approve/reject, handover schedule, QR issue, single-use verify, atomic completion, cancel.
- **Phase 7, dashboards:** personal, staff and admin statistics; admin user list and audit log viewer; `cleanup` CLI.
- **Phase 8, finalization:**
  - Security review findings fixed:
    1. `SECRET_KEY` was required but unused, so it was removed.
    2. Duplicate registration skipped hashing (timing signal), and email was sent in the request path (SMTP latency signal). Now equal work, and email goes out as a background task.
    3. The per-account login limit counted successful logins. Now failures only.
    4. Status transitions could lose updates under concurrency. `lock_status` guards were added at every transition.
    5. There were no security headers and no request body limit. New middleware adds both. The first version of the body limit returned 400 because FastAPI catches the error; fixed to 413.
  - New tests: `test_security.py` (the route matrix checks every one of the 53 routes for session, CSRF and role, plus headers, body limit, production docs, error leakage, login lockout, timing parity, email failure and the race guard) and `test_transitions.py` (invalid transitions on CLAIMED, rejected and RETURNED states).
  - README gained Security and Deployment sections; the API contract documents headers, limits and every error status.
  - No schema changes.

## Commands run (latest, 2026-10-24)

| Command | Result |
|---|---|
| `python -m pytest` (project venv) | 198 passed |
| `alembic check` | No new upgrade operations detected |
| `pip-audit -r requirements-dev.txt` (separate scratch venv) | No known vulnerabilities found |
| Clean copy of `backend/` (no venv, data, `.env` or uploads): new venv, `pip install -r requirements-dev.txt`, `cp .env.example .env`, `alembic upgrade head`, `python -m app.db.seed`, `python -m pytest`, `uvicorn` | Both migrations applied, 10 + 9 seeded, 198 passed, health 200 with `foreign_keys: on`, security headers present, no server errors |

Earlier phases each recorded: tests passing at the time (18, 46, 78, 109, 130, 139), `alembic check` with no drift, and a live curl smoke test of that phase's main flow against uvicorn, with smoke data removed afterwards.

## Known issues and limitations

- `frontend/` is a stub (empty `angular.json` projects, `@angular/core ^16` only, three one-line placeholder `.ts` files). Regenerate with the current Angular CLI when UI work starts and delete the placeholders.
- Not a git repository yet.
- Single process only: the rate limiter is in memory and SQLite allows one writer. Behind a proxy, start uvicorn with `--proxy-headers --forwarded-allow-ips` so the client IP is correct.
- The SMTP backend is implemented but not tested against a real mail server.
- Search uses SQLite `LIKE` (case-insensitive for ASCII only); FTS5 if volume grows. Matching scans up to 500 candidates in the request; location matching is exact only.
- Animated images keep only their first frame after re-encoding.
- Who verified and completed a handover is in `audit_logs` only (`staff_id` is the scheduler).
- Concurrency guards are tested with two sessions in sequence, not with real parallel threads.
- Cleanup and backups run only when scheduled (see README Deployment).
- Lost/found type correctness on `matches` is a service-layer rule, not a DB constraint.

## Next tasks

1. Frontend: regenerate the Angular project (current CLI) with a dev proxy for `/api`, and build the UI against `docs/api-contract.md`, following the UI and site norms above.
2. Frontend: Angular tests for auth flow, report form validation and the QR scan screen (camera access via a maintained Angular-compatible scanner).
3. Initialise git and make a first commit (`.gitignore` is ready).
4. Before going live: test SMTP against the campus mail server, and set up scheduled cleanup and off-machine backups.
5. Optional: add `verified_by_id`/`completed_by_id` to `handover_records` if staff reporting needs them.
