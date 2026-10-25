# Project Updates

## Current status

- **Backend phases 2 to 8 complete:** authentication, reports and search, images, matching, claims, the QR handover, dashboards and administration, plus a security review and a clean-setup check.
- **Basic UI built** (owner asked for a minimal UI matching their reference screenshot): Angular 21 in `frontend/`, connected to the real API for every screen.
- **SRM only:** `ALLOWED_EMAIL_DOMAINS=srmist.edu.in`. Users store SRM ID, department and optional phone.
- **Tests:** backend 214 passing, frontend 3 passing (`npm test` from the root runs both); migrations match the models.
- Last updated: 2026-10-24.

## Persistent decisions

General
- Fixed stack: Angular + FastAPI + SQLite/SQLAlchemy 2.x + Alembic + Pytest. Do not change.
- Frontend: Angular 21 (Angular 22 needs Node 24.15+, the dev machine has 24.14.1), standalone components with inline templates, signals, OnPush, one global `src/styles.css` with tokens. No UI library. The owner's reference screenshot sets the look: white, navy primary, brown-orange for lost, green for found.
- Allowed email domain is enforced at registration, at login and on every request (`resolve_session`), so narrowing `ALLOWED_EMAIL_DOMAINS` also locks out existing accounts and live sessions. The frontend reads the domains from `/api/auth/session` for hints and an early check.
- `users.campus_id` (SRM register number or employee ID) is unique and stored uppercase; email and SRM ID cannot be changed by users. Staff see the claimant's SRM ID (never the phone) at handover.
- On Windows, `npm run backend` restarts uvicorn itself (file watcher plus `taskkill /T`) instead of using `--reload`. Uvicorn's Windows reload sends `CTRL_C_EVENT`, which reaches every process in the console and kills npm. Also, `backend\.venv\Scripts\python.exe` is a launcher with the real interpreter as a child, so restarts must kill the whole tree.
- 21st.dev / shadcn (React + Tailwind) components are ported to Angular, never installed: the dropdown menu became `shared/account-menu.ts` on Angular CDK Menu, the beams background became `shared/beams-background.ts`. No React, Tailwind, `components/ui` folder or `cn()` utility exists or should be added.
- Action results use the alert stack (`Alerts` service); inline alerts remain only for page-load failures and form validation.
- In the Claude preview pane the page reports `visibilityState: hidden`, so requestAnimationFrame runs about twice a second: animations look slow and zoneless re-renders lag there. Judge motion in a normal browser window.
- Passwords need at least 8 characters (was 12; owner request).
- `PRODUCT.md` (impeccable product record) exists at the root: student project for SRMIST Ramapuram, real lost and found office; Ramapuram building names are NOT recorded and must not be invented. DESIGN.md records the visual system.
- Design system: Bricolage Grotesque display + Atkinson Hyperlegible Next body (self-hosted), warm off-white page `#f6f5f1` with the Sliding Ease canvas, dark beams hero, exponential ease-out `cubic-bezier(0.16,1,0.3,1)`. No coloured side stripes on cards, stats or alerts (impeccable ban); item cards keep their coloured top edge because the owner's reference shows it.
- 21st.dev code retrieval is 2 per day on the free tier. Sliding Ease is ported from the component's published preview bundle (the algorithm, mouse influence and click ripples match the original); only its colours are toned down to faint navy for readability.
- Angular logs `InvalidStateError: Transition was aborted` in dev mode only when a navigation happens in a hidden tab (the browser skips the view transition); production builds are silent. The Claude preview pane always reports hidden, so it shows there.
- Run everything from the repo root with `npm run setup|backend|frontend|test|cli` (root `package.json` + `scripts/dev.mjs`, which finds `backend/.venv` itself). Angular CLI analytics is disabled in `frontend/angular.json` so `ng serve` never blocks on a first-run prompt.
- The frontend calls the API same-origin (`/api`) through `proxy.conf.json` in dev and the reverse proxy in production. Never point it at another origin, or cookies and CSRF break.
- `GET /api/auth/session` (returns `{user: null}`) is used at startup instead of `/me` so anonymous page loads produce no 401 console errors. `GET /api/public-stats` feeds the home page counts (aggregates only).
- Sign-in pages (`/items`, `/items/:id`, `/report`, dashboards) are `noindex`; the sitemap lists only `/`, `/login`, `/register` and `/privacy`, generated from `SITE_URL` at build time.
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

Avoid: purple gradients, pill-shaped buttons, fake reviews, fake metrics or customer counters, vague hero text, emoji icons, em dashes in copy, any "Vite" or "React" mentions, default or placeholder content, AI-generated stock photos, "made by AI" tags. (Cursor animation was on this list "at this stage"; the owner asked for one on 2026-10-24, so it now exists, decorative and off for touch and reduced motion.)

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
- **Basic UI:**
  - Pages: home, browse with filters, item detail (private claim form, match suggestions for the reporter, add photos, close), report form with photos, dashboard (claims with handover QR code, suggestions, recent reports, notifications, change password), staff desk (review, schedule, QR verify, complete only after an ID checkbox, cancel), admin (stats, users, categories and places, recent activity), log in, register, confirm email, forgot and reset password, privacy policy, 404.
  - Site norms applied: SVG favicon, privacy policy, custom 404, per-page titles and meta descriptions, canonical links, one `h1` per page, sitemap and robots, breadcrumbs with BreadcrumbList JSON-LD, WebSite JSON-LD with SearchAction on the home page, alt text on every image, no production source maps, no emoji, no pill buttons, no gradients, no invented numbers (the home counts come from the API and the panel hides if the API fails).
  - If a report saves but a photo upload fails, the user lands on the saved report with a note listing the failed photos, so they don't resubmit and create duplicates.
  - Backend additions: `/api/auth/session`, `/api/public-stats`, with tests (route inventory now 55).

- **SRM restriction and profile (latest):**
  - Backend: domain check on login and on every request; `campus_id`, `department` and `phone` on `users` (migration `656d005407df`, with a hand-added uppercase CHECK); sign-up validation and normalisation; `PATCH /api/auth/me`; `/api/auth/session` returns `allowed_email_domains`; claimant SRM ID for staff. Route inventory is 56.
  - Frontend: SRM email hints and checks, SRM ID, department and phone fields on sign-up, a "My details" section on the dashboard, SRM ID in the staff desk and admin user table, privacy policy updated. New favicon: a magnifier over a lost-property box.
  - Fixed: `npm run backend` died on the first backend file change on Windows (see decisions).

- **UI effects (latest):** dismissible alert stack with live notifications, account dropdown menu (ported 21st.dev / shadcn design on Angular CDK Menu), beams background on the home hero (ported 21st.dev "Beams Background", source fetched via the 21st.dev tools), cursor ring. Frontend tests now cover the menu (roles, staff and admin items) and the alert stack. Dependency added: `@angular/cdk`.

- **Interactive Sliding Ease (latest):** background now matches the 21st.dev original exactly, including mouse influence (180px) and click ripples; replaces the earlier lookalike.
- **Cursor and buttons:** cursor and button animation ported from the earlier Campus Lost & Found project (`public/js/cursor.js`, `.btn` rules in `app.css`): magnetic dot and ring with leaning buttons, light sweep, 1px lift, press scale and icon nudge. Off for touch and reduced motion.
- **Redesign pass:** impeccable workflow (PRODUCT.md interview, craft floor, animate guidance, detector). New type pairing; hero headline focus-in entrance; journey timeline port; Sliding Ease page background; Lenis smooth scroll; view transitions card to detail; card hover lift; alert and stat side stripes removed; themed selection, caret, scrollbar, accent colour and tabular numerals; compact phone header; 404 eyebrow removed. Password minimum 8. `send-test-email` CLI command; SMTP path verified against a local test server; default sender fixed.

## Commands run (latest, 2026-10-24)

| Command | Result |
|---|---|
| After cursor and button port: `ng test`, `ng build`; browser check | 6 passed; clean build; ring wraps the header button (its size plus 10px, radius 10px), button leans and settles back after the pointer leaves, cursor turns pale over the hero; no new console errors |
| After redesign: `pytest`, `ng test`, `ng build` | 216 passed; 6 passed; clean build, 0 source maps, fonts bundled (no external font requests) |
| `npm audit --omit=dev` after adding fonts and Lenis | 0 vulnerabilities (2 reported in dev tooling only) |
| SMTP check: `send-test-email` against a local aiosmtpd server | Message received with correct To and Subject |
| impeccable `detect` on changed UI files | 1 deliberate exception (card top border, owner reference) and 3 false positives (Angular `[src]` bindings) |
| Browser at about 800 px and 375 px | Fonts loaded, Lenis on for mouse and off for touch, beams and journey beam animating, no horizontal overflow, Sliding Ease painting behind content, no console errors apart from the dev-only view-transition notice |
| Frontend after UI effects: `ng test`, `ng build`, `npm audit --omit=dev` | 6 passed; clean build, 0 source maps; 0 vulnerabilities |
| Browser: beams, menu, alerts, cursor | Beams canvas animating (pixels change between samples); menu keyboard navigation, Escape and focus return work; success alert and notification alert shown, "Mark as read" cleared it on the server; cursor ring follows the pointer. No console errors. Test account deleted. |
| `python -m pytest` (after SRM and profile changes) | 214 passed |
| `alembic upgrade head` + `alembic check` | Applied `656d005407df`; no drift |
| Windows dev-runner check: two forced backend restarts by touching files, then Ctrl+C | Server answered after each restart, terminal kept running, port 8000 freed on Ctrl+C |
| Browser: Gmail sign-up refused; `@srmist.edu.in` sign-up, verify, log in, edit department on dashboard | Refusal message shown; details stored and normalised (SRM ID uppercased, phone digits only); edit saved; no console errors. Test account deleted. |
| `python -m pytest` (project venv, after UI work) | 200 passed |
| `npx ng build` (frontend) | Clean, no warnings, 0 `.map` files in `dist` |
| `npx ng test --watch=false` (frontend) | 3 passed |
| Browser walkthrough (backend + `ng serve` in the preview pane): register, open verification link from dev log, log in with return URL, file a FOUND report, home, browse search, dashboard, staff desk, admin, privacy, 404 | All rendered with real data; head tags checked (one `h1`, canonical, JSON-LD, no images without alt); no console errors. Test account and its data deleted afterwards. |
| `python -m pytest` (project venv, Phase 8) | 198 passed |
| `alembic check` | No new upgrade operations detected |
| `pip-audit -r requirements-dev.txt` (separate scratch venv) | No known vulnerabilities found |
| Clean copy of `backend/` (no venv, data, `.env` or uploads): new venv, `pip install -r requirements-dev.txt`, `cp .env.example .env`, `alembic upgrade head`, `python -m app.db.seed`, `python -m pytest`, `uvicorn` | Both migrations applied, 10 + 9 seeded, 198 passed, health 200 with `foreign_keys: on`, security headers present, no server errors |

Earlier phases each recorded: tests passing at the time (18, 46, 78, 109, 130, 139), `alembic check` with no drift, and a live curl smoke test of that phase's main flow against uvicorn, with smoke data removed afterwards.

## Known issues and limitations

- Staff verify QR codes by scanning with a keyboard-style scanner or pasting the text; there is no in-browser camera scanner yet.
- Frontend tests cover the app shell only; page flows were checked by hand in the browser, not by automated end-to-end tests.
- Photo upload through the browser UI was not exercised in the walkthrough (the browser tool cannot pick files); the upload API itself is covered by backend tests.
- Single process only: the rate limiter is in memory and SQLite allows one writer. Behind a proxy, start uvicorn with `--proxy-headers --forwarded-allow-ips` so the client IP is correct.
- The SMTP backend is implemented but not tested against a real mail server.
- Search uses SQLite `LIKE` (case-insensitive for ASCII only); FTS5 if volume grows. Matching scans up to 500 candidates in the request; location matching is exact only.
- Animated images keep only their first frame after re-encoding.
- Who verified and completed a handover is in `audit_logs` only (`staff_id` is the scheduler).
- Concurrency guards are tested with two sessions in sequence, not with real parallel threads.
- Cleanup and backups run only when scheduled (see README Deployment).
- Lost/found type correctness on `matches` is a service-layer rule, not a DB constraint.

## Next tasks

1. Owner: set up SMTP in `backend/.env` (see README, "Sending real emails") so verification emails arrive; until then the links are in the backend terminal.
2. Owner or admin: replace the generic campus places with the real SRM Ramapuram buildings on the admin page.
3. Add an in-browser camera QR scanner to the staff desk (a maintained library that works with Angular, loaded only on that page).
4. Frontend tests for the report form, claim form and staff complete flow; consider Playwright end-to-end tests for the full claim-to-return journey.
5. Before going live: test SMTP against the campus mail server, set `SITE_URL` at build, schedule cleanup and off-machine backups.
6. Optional: edit-report form (the API supports PATCH; the UI currently offers add photo and close only).
7. Optional: add `verified_by_id`/`completed_by_id` to `handover_records` if staff reporting needs them.
