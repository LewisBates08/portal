# Searchroom

Recruitment client collaboration with React/TypeScript/Vite, FastAPI and PostgreSQL. Agency admins manage searches and access; assigned recruiters maintain the search; invited clients review shared candidates and collaborate. The deployment-readiness implementation is included. Cloud resources have not been provisioned; see [deployment and recovery instructions](docs/DEPLOYMENT.md).

## Start locally

On this prepared workspace:

```sh
.venv/bin/python scripts/dev.py
```

Open http://localhost:5173. The launcher applies migrations and starts the API and frontend; Ctrl+C stops them. Existing accounts from the JWT prototype now require email verification. Administrators also enrol an authenticator. You must configure a local mail catcher or SMTP server to complete account flows.

For a fresh Docker setup:

```sh
cp .env.example .env
# Set a random JWT_SECRET in .env before starting.
docker compose up --build
```

Compose includes PostgreSQL, a one-off migration service, the development servers, an email worker and Mailpit. Read development mail at http://localhost:8025. Do not deploy this development Compose stack publicly; production uses the root Dockerfile. Docker execution must be verified in CI or on a Docker-enabled machine.

Without Docker, install Python 3.13/3.14, Node 24 and PostgreSQL, then:

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock
npm --prefix frontend ci
cp .env.example .env
```

Set `DATABASE_URL` and a random `JWT_SECRET` in `.env`. The existing local PostgreSQL cluster uses loopback port 55432; new installations supply their own database. Run a local SMTP catcher on port 1025 and run the email worker in another terminal:

```sh
PYTHONPATH=backend .venv/bin/python -m app.operations mail-loop
```

The signing secret is generated with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`. Keep secrets out of source control. Production additionally requires an independent Fernet key, verified database TLS and a verified London SES sender; the production settings validator rejects incomplete settings.

## Accounts and workflows

- **Agency admin:** select Create account, verify the emailed link, sign in and enrol an authenticator. Save the recovery codes. In Administration set your retention review period, add client organisations, create searches and invite users. Suspend users to revoke all their sessions, or remove only their project membership. Archive/export/review deletion of search data from Administration.
- **Recruiter:** accept an emailed invitation, choose a password and verify your email. Sign in to edit assigned searches, stage candidates, explicitly share selected profiles, and maintain manual milestones. Stale edits produce a conflict rather than overwriting someone else's changes.
- **Client:** accept and verify your invitation, or sign in with the matching existing account to accept additional access. View shared candidates, give feedback and contribute updates/comments/messages. Other users in your client organisation do not automatically share your access.

Forgot-password and verification-resend links are on the login screen. Signup pending actions expire after 24 hours, invitations after seven days and reset links after 30 minutes. The terminal alternative `PYTHONPATH=backend .venv/bin/python -m app.cli create-admin` also queues verification.

The production backend has no demo seeder or default login. Create your own verified account. Fictional browser fixtures are isolated under `scripts/`, require an explicitly named `_test` database and a supplied random `E2E_PASSWORD`, and are excluded from the production image. Production startup refuses a database containing the legacy demo login addresses.

## API and security

`/api/v1` exposes the API. Development documentation is at `/docs`; public production API documentation is disabled.

- Authentication uses a random server-managed cookie, not JWT/localStorage. `GET /auth/csrf` establishes a pre-login session and returns the CSRF token. All writes require an exact Origin and `X-CSRF-Token`. `GET /auth/me` returns `{user, mfa_required, mfa_setup}`. Login rotates the session; logout, password reset and suspension revoke it. Idle expiry is 30 minutes; absolute expiry is seven days. Legacy `/auth/refresh` is removed.
- Production cookies are `__Host-searchroom_session`, Secure, HttpOnly, SameSite=Lax and Path=/ with no Domain. Development uses an insecure-cookie exception only for local HTTP. Passwords use Argon2; TOTP secrets and outbox bodies are encrypted; recovery codes and account/session tokens are hashed.
- Lists return `{items, next_cursor}` with `cursor` and `limit` parameters; default 50, maximum 100. UI Load more controls retrieve subsequent pages. Comments have their own endpoint; message history loads incrementally.
- Project/candidate/milestone updates require the current `version`: missing versions return 428 and stale versions return 409. Collaboration POSTs require a UUID `Idempotency-Key`, reused when retrying the same submission; keys last 30 days.
- Rate limits are PostgreSQL-backed, shared across instances, and bounded by endpoint/account/IP. Pilot quotas default to 100 users, 100 active projects, 1,000 candidates per project and 10,000 collaboration/write requests per agency per day. Operators can configure them after capacity review.
- Project and nested resource permissions are checked in FastAPI. Clients receive only explicitly shared candidates. Content renders as text and external links must use HTTPS without embedded credentials. External file access must be revoked at its provider separately.

## Verification

Use a separate PostgreSQL database ending in `_test`:

```sh
TEST_DATABASE_URL=postgresql+psycopg://portal@127.0.0.1:55432/portal_test .venv/bin/pytest -c backend/pytest.ini -q
npm --prefix frontend run build
npm --prefix frontend test
```

Install test dependencies with `pip install -r backend/requirements-dev.txt`. Browser tests require `npm --prefix frontend exec playwright install`; set the same random `E2E_PASSWORD` in the test-server and Playwright terminals, then start the isolated HTTPS fixture server with `TEST_DATABASE_URL=... PYTHONPATH=backend .venv/bin/python scripts/e2e_server.py`, then run `cd frontend && npx playwright test`. Never point test scripts at the normal application database.

`scripts/load_check.py` exercises 20 users with a 10,000-message fixture. `scripts/restore_check.py` restores a dump into a disposable test database and verifies counts and schema. CI also checks container serving, dependencies and secrets. See [deployment checkpoint results](docs/DEPLOYMENT_CHECKPOINTS.md) for what was actually run and what remains unverified.

File uploads, electronic signing, automatic milestone calculations, WebSockets, cross-agency user accounts and granular permission settings remain outside this release.
