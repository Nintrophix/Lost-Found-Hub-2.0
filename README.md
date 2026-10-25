# Campus Lost & Found Hub

A campus web application for reporting lost and found belongings, finding likely matches, submitting private ownership claims, and returning items through a staff-verified QR handover.

Status and next steps: see [updates.md](updates.md).

## Stack

| Layer | Technology |
|---|---|
| Frontend | Angular 21, TypeScript, HTML, CSS (`frontend/`) |
| Backend | Python 3.12, FastAPI |
| Database | SQLite via SQLAlchemy 2.x |
| Migrations | Alembic |
| Tests | Pytest (backend), Vitest via Angular CLI (frontend) |
| Images | Local filesystem (`backend/uploads/`), metadata in SQLite |

## Prerequisites

- Python 3.12+
- Node.js 20.19+, 22.12+ or 24+ and npm

## Quick start

Run these from the repository root (the folder containing this README). They work in PowerShell, Command Prompt, Git Bash and macOS/Linux shells, and they find the backend's virtual environment themselves, so nothing needs activating.

One-time setup: creates `backend/.venv`, installs everything, creates `backend/.env` from the example, migrates and seeds the database, and installs the frontend packages.

```bash
npm run setup
```

Then start each server in its own terminal:

```bash
npm run backend
```

```bash
npm run frontend
```

Open http://localhost:4200. Only `@srmist.edu.in` email addresses can register and sign in (`ALLOWED_EMAIL_DOMAINS` in `backend/.env`). Sign-up asks for the SRM ID (register number or employee ID) and department; phone is optional. Everyone can update their details on the dashboard.

On Windows, `npm run backend` restarts the backend itself when a file in `backend/app` or `backend/.env` changes. It does not use uvicorn's `--reload`, because uvicorn's Windows reload sends a Ctrl+C to the whole terminal, which closes npm. On macOS and Linux it uses `--reload`.

Other commands from the root:

| Command | What it does |
|---|---|
| `npm test` | Backend and frontend tests |
| `npm run cli -- create-admin --email you@your-campus.edu --name "Your Name"` | Create an admin (prompts for the password) |
| `npm run cli -- set-role --email you@your-campus.edu --role ADMIN` | Change the role of an account that already exists |
| `npm run cli -- cleanup --dry-run` | Preview housekeeping |

Use your real campus address in those commands, and register it on the site (or with `create-admin`) first. `set-role` only works on an existing account.

### Sending real emails

By default (`EMAIL_BACKEND=console`) the backend does not send email: each message, including verification and password reset links, is printed in the backend terminal. To deliver real email:

1. Pick a mail account to send from. For Gmail: turn on 2-Step Verification, then create an App Password at https://myaccount.google.com/apppasswords.
2. In `backend/.env`, set `EMAIL_BACKEND=smtp` and fill in `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USE_TLS=true`, `SMTP_USERNAME`, `SMTP_PASSWORD` (the app password) and `EMAIL_FROM` (the same address as the username). The file has these lines ready, commented out.
3. Restart the backend, then check delivery: `npm run cli -- send-test-email --to you@srmist.edu.in`

Common problems:
- **`uvicorn` or `pip` is not recognized, or `No module named 'app'`:** the command ran outside `backend/` or without its virtual environment. Use the `npm run` commands above from the root.
- **`Could not read package.json`:** `npm start` ran in a folder without one. From the root, `npm start` and `npm run frontend` both start the frontend.
- **Address already in use (port 8000 or 4200):** another copy of the server is still running. Stop it with Ctrl+C in its terminal.

## Backend setup (manual)

`npm run setup` does all of this. To do it by hand, run these from `backend/`:

```bash
python -m venv .venv
```

Activate it (`.venv\Scripts\Activate.ps1` in PowerShell, `source .venv/Scripts/activate` in Git Bash, `source .venv/bin/activate` on macOS/Linux), then:

```bash
pip install -r requirements-dev.txt
```

Create `backend/.env` from `backend/.env.example` and set `ALLOWED_EMAIL_DOMAINS` to your campus email domain(s). The example values work for local HTTP development as they are: `COOKIE_SECURE=false` and `EMAIL_BACKEND=console` (verification and reset links are printed to the server log).

## Database

```bash
alembic upgrade head
```

```bash
python -m app.db.seed
```

The database file defaults to `backend/data/lostfound.db`. Seeding is idempotent and only adds categories and campus locations.

Create a migration after changing `app/db/models.py`, then review the generated file before applying it:

```bash
alembic revision --autogenerate -m "describe change"
```

```bash
alembic check
```

### Backup and restore

Uses SQLite's online backup API, so a backup is consistent even while the server runs. Backups go to `backend/backups/` by default.

```bash
python -m app.db.backup backup
```

Stop the API server before restoring:

```bash
python -m app.db.backup restore backups/lostfound-YYYYMMDDTHHMMSSZ.db
```

### Maintenance

Remove dead sessions and used or expired tokens, clear expired QR codes, and delete upload files with no database row (older than one hour). Use `--dry-run` to see counts without changing anything.

```bash
python -m app.cli cleanup --dry-run
```

```bash
python -m app.cli cleanup
```

### First administrator

Public registration only ever creates `USER` accounts. Create the first admin from the server (the password is prompted, not passed as an argument):

```bash
python -m app.cli create-admin --email admin@example.edu --name "Campus Admin"
```

Change an existing account's role:

```bash
python -m app.cli set-role --email person@example.edu --role STAFF
```

After that, admins can manage roles and account status through `PATCH /api/admin/users/{id}`.

## Run

From the repository root, in two terminals: `npm run backend` and `npm run frontend` (see Quick start). These are the same as running `uvicorn app.main:app --reload` inside `backend/` with its virtual environment activated, and `npm start` inside `frontend/`.

Open http://localhost:4200. The Angular dev server proxies `/api` to the backend on port 8000. Health check: `http://localhost:8000/api/health`. API docs: `http://localhost:8000/api/docs` (disabled when `ENVIRONMENT=production`).

In development, verification and password reset emails are printed in the backend terminal; open the link shown there.

## Test

```bash
python -m pytest
```

Tests build a fresh database per test by running the Alembic migrations, so they also verify that migrations match the models. They pin their own settings, so a local `.env` does not affect them.

Frontend tests, from `frontend/`:

```bash
npm test -- --watch=false
```

## Security

- Cookie sessions stored server-side, Argon2id password hashing, campus-domain allowlisting, email verification, password reset, CSRF protection on every write, and role checks enforced in the backend.
- Rate limits, emails sent after the response, and equal hashing work on duplicate registration, so responses don't reveal whether an account exists.
- Security headers on every response, a request body size limit, uploads re-encoded with metadata stripped, and claim evidence kept private.
- Status changes re-check the current state at write time, so concurrent requests cannot overwrite each other.
- `tests/test_security.py` checks every route: no session gives `401`, a write without CSRF gives `403`, and the wrong role gives `403`. Adding a route makes that test fail until the route list in the test is updated.

Details: [docs/api-contract.md](docs/api-contract.md).

## Deployment

The backend is a single FastAPI process with a local SQLite file. For a campus deployment:

1. Set `ENVIRONMENT=production`, `COOKIE_SECURE=true`, `EMAIL_BACKEND=smtp` with the `SMTP_*` values, `FRONTEND_BASE_URL`, `CORS_ORIGINS` and `ALLOWED_EMAIL_DOMAINS`. The app refuses to start with unsafe production settings, and `/api/docs` is disabled.
2. Run one worker (`uvicorn app.main:app --host 127.0.0.1 --port 8000`). Rate limits are kept in process memory, and SQLite allows one writer at a time.
3. Build the frontend with your public address so the sitemap is correct: `SITE_URL=https://lostfound.university.edu npm run build` in `frontend/`. Put a reverse proxy in front for HTTPS: serve `frontend/dist/lost-found-hub/browser` with a fallback to `index.html` for app routes, and proxy `/api` to uvicorn on the same origin, so cookies and the CSRF header work. Cap request bodies at the proxy as well (for example `client_max_body_size 7m` in nginx). If the proxy should pass client IPs for rate limiting, start uvicorn with `--proxy-headers --forwarded-allow-ips <proxy ip>`.
4. Keep `data/` and `uploads/` outside the web root, writable only by the service account.
5. Schedule `python -m app.cli cleanup` daily and `python -m app.db.backup backup` at least daily, and copy backups (database and `uploads/`) off the machine.
6. Run `alembic upgrade head` on every release before starting the new version.

### Vercel (draft, not deployable yet)

`vercel.json` at the repo root defines one Vercel project with two services on one domain: `backend` (FastAPI, `app.main:app`) receives `/api/*` with the path unchanged, and `frontend` (the Angular build in `dist/lost-found-hub/browser`, with a fallback to `index.html` for app routes) receives everything else. The browser calls `/api/...` on the same origin, so no service bindings are needed. Test locally with `vercel dev`.

Before it can work in production:

- Storage: Vercel Functions have a read-only, short-lived filesystem, so the SQLite file in `backend/data/` and photos in `backend/uploads/` cannot persist there. The database and image storage must move to hosted services (or the backend must run somewhere with a persistent disk).
- Migrations: `alembic upgrade head` must be run against the production database on each release; Vercel does not run it.
- Rate limits are kept in each function instance's memory, so they are weaker across instances.
- Project environment variables: the production values from step 1 (`FRONTEND_BASE_URL` and `CORS_ORIGINS` set to the Vercel domain), plus `SITE_URL` for the frontend build.

## Matching

When a report is created or edited, the backend scores it against opposite-type reports from the same period using category, description words, colour, location and date. Each suggestion stores a per-signal explanation. Weights and the threshold are set with the `MATCH_*` variables in `.env`. After changing them, recompute stored suggestions:

```bash
python -m app.cli rematch
```

A score is only a suggestion. People confirm or dismiss it, and a confirmed match never approves a claim.

## QR handover workflow

1. A user submits a claim on a FOUND report with private evidence. Staff review it and approve or reject it (rejection needs a reason). A high match score never approves a claim on its own.
2. Staff schedule a handover for the approved claim.
3. The claimant opens their claim and generates a QR code. The server creates a random token valid for `QR_TOKEN_TTL_MINUTES`, stores only its SHA-256 hash, and returns the code once (text payload plus SVG). Generating again revokes the previous code.
4. At the desk, staff scan the code. The API accepts it once only, and only if it is unexpired, the claim is still `APPROVED` and the item is `CLAIMED`. The handover becomes `VERIFIED`.
5. Staff check the claimant's campus ID in person and complete the handover with `identity_confirmed: true`. Holding the QR code alone never completes a handover.
6. Completion runs in one transaction: handover `COMPLETED`, claim `COMPLETED`, item `RETURNED`, other pending claims rejected, the claimant's confirmed lost report resolved, notifications and audit log written. Database indexes also block a second completed handover for the same item.

Staff cannot review or hand over their own claims. Endpoint details: [docs/api-contract.md](docs/api-contract.md).

## Documentation

- [docs/database-schema.md](docs/database-schema.md): tables, constraints, status transitions
- [docs/api-contract.md](docs/api-contract.md): implemented endpoints
