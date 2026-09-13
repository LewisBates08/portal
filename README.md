# Searchroom

A local recruitment client portal built with React, TypeScript, Vite, FastAPI and PostgreSQL. Each project is one search, with a shared brief, agreement terms, candidates, updates, messages and a manual milestone timeline.

## Try it on this machine

Dependencies, a project-local PostgreSQL database and fictional demo data have been prepared. From the project folder:

```sh
.venv/bin/python scripts/dev.py
```

Open **http://localhost:5173**. Stop with **Ctrl+C**. The launcher starts the local database if needed, applies migrations and starts both development servers. It stops the servers and any database it started when you exit.

| Demo account | Email | Password |
| --- | --- | --- |
| Agency admin | admin@example.com | SearchroomDemo2026! |
| Recruiter | recruiter@example.com | SearchroomDemo2026! |
| Client | client@example.com | SearchroomDemo2026! |

All demo organisations, people, searches and commercial terms are fictional. The example document link points to example.com; no CV or agreement files are included. Demo seeding is optional and does not run automatically during startup.

## Fresh setup with Docker Compose

Requires Docker with Compose. This configuration was supplied but could not be run in the implementation environment because Docker was unavailable.

1. Copy `.env.example` to `.env`.
2. Generate a secret with the command below and replace `JWT_SECRET` in `.env`.
3. Start the application:

```sh
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose up --build
```

Open http://localhost:5173 and choose **Create account** to set up a new agency and its first administrator. Enter your name, agency name, email and matching passwords (10–128 characters). You are signed in automatically to your empty workspace.

The terminal bootstrap command is still available as an alternative:

```sh
docker compose exec backend python -m app.cli create-admin
```

Alternatively, add the fictional demo:

```sh
docker compose exec backend python -m app.cli seed-demo
```

The frontend is at http://localhost:5173 and interactive API documentation is at http://localhost:8000/docs. Database files persist in the `portal_data` volume. `docker compose down` stops the stack without deleting that volume.

The default development ports are 5173 (frontend), 8000 (API), and 5432 (Docker PostgreSQL). If PostgreSQL already occupies 5432, remove or change the database's host port mapping in `compose.yaml`; the containers still connect to `db:5432` internally.

## Fresh setup without Docker

Requires Python 3.13 or 3.14, Node.js 24, and PostgreSQL. Commands below run from the repository root unless specified otherwise.

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock
npm --prefix frontend ci
cp .env.example .env
```

Create a dedicated PostgreSQL user and database using your normal local database tools. Set `DATABASE_URL` in `.env` to that database using the `postgresql+psycopg://` scheme, and set a randomly generated `JWT_SECRET` of at least 32 characters. Keep `.env` private; it is gitignored.

```sh
.venv/bin/alembic -c backend/alembic.ini upgrade head
.venv/bin/python scripts/dev.py
```

Choose **Create account** on the login page to create your agency, or use `PYTHONPATH=backend .venv/bin/python -m app.cli create-admin` as the terminal alternative.

For demo data instead of an empty agency:

```sh
PYTHONPATH=backend .venv/bin/python -m app.cli seed-demo
```

Set `DEMO_PASSWORD` before seeding to override the documented demo password. The seed command refuses to duplicate an existing demo and does not reset existing passwords.

On the implementation machine, the isolated PostgreSQL 15 instance lives in `.local/pgdata` and listens only on `127.0.0.1:55432`. It uses local trust authentication for this demo. The launcher recognises that existing cluster; a fresh clone does not contain it. No existing databases were modified.

## The three workflows

### Agency administrator

1. Choose **Create account** on the login page to create your own agency workspace, then add a client organisation in **Administration**.
2. Choose **New search** on the dashboard; enter the client, brief, dates and agreement terms.
3. In **Administration → Project access**, assign existing recruiters and client users. Client users must belong to the project's client organisation.
4. To onboard someone new, choose their email, role and project under **Invite someone**. Copy and manually share the generated link. Client invitations require a project; recruiter invitations may grant agency membership before project assignment.
5. Remove project access or revoke a pending invitation in Administration. Agency admins retain access to every project in their own agency.

### Recruiter

1. Sign in and open an assigned search.
2. Maintain the overview and external document links.
3. Add candidates, update their stage, and explicitly choose **Share this candidate with the client**. Changing stage never automatically changes visibility.
4. Post updates, respond to feedback and messages, and maintain the timeline. Complete or reopen milestones manually; a target such as “Three candidates shortlisted” does not calculate a candidate count.

### Client

1. Open an invitation link. New users set their name and password; existing users sign in with the invited email to accept additional access.
2. View only explicitly authorised searches and shared candidates, including candidates currently interviewing.
3. Leave candidate feedback, add updates/comments, and exchange messages.
4. View agreement terms and the timeline. Candidate stages, agreement terms and milestones are managed by agency staff.

Messages load when opening the tab, after sending, and when **Refresh** is clicked. The unread indicator counts messages from other people that the user has not viewed. Updates, comments, feedback and messages are append-only. External documents are links, not uploads; their access permissions are managed by the external document provider.

## Structure and API

- `backend/app`: database models, request/response schemas, authentication, reusable project access checks, and route modules.
- `backend/migrations`: versioned Alembic schema migrations; startup applies them without dropping data.
- `frontend/src`: typed API client, authentication, shared form controls, role-aware screens and styles.
- `scripts/dev.py`: local development launcher.

The API is versioned under `/api/v1`. FastAPI publishes request and response contracts at `/docs` and `/openapi.json` while the backend is running.

| Resource | Main routes |
| --- | --- |
| Authentication | `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`; `GET /auth/me` |
| Invitation acceptance | `POST /auth/invitation`, `/auth/accept-invitation` |
| Administration | `/users`, `/client-organisations`, `/invitations`, `/projects/{id}/members` |
| Search information | `/projects`, `/projects/{id}`, `/projects/{id}/documents` |
| Candidate pipeline | `/projects/{id}/candidates`, `/projects/{id}/candidates/{candidate_id}/feedback` |
| Collaboration | `/projects/{id}/updates`, `/projects/{id}/updates/{post_id}/comments`, `/projects/{id}/messages` |
| Read markers | `PUT /projects/{id}/messages/read` |
| Timeline | `/projects/{id}/milestones` |

Responses omit password hashes and token-storage records. Nested resource requests check both project access and the resource's actual project, and hidden candidates are excluded from client responses at the API boundary.

## Authentication choices

- Public account creation always creates a new agency and its admin. It never joins an existing agency by name or email domain, accepts a caller-specified role, or upgrades an existing account. Duplicate emails are rejected. Recruiters and clients still join existing workspaces through invitations. Email verification is not included in this local prototype.
- Argon2 password hashes with pwdlib; JWT signing and verification with PyJWT.
- Access tokens expire after 15 minutes. Refresh tokens expire after seven days and rotate on use; only a hash of the active refresh token is stored.
- JWTs refer to a database session. Logout and refresh-token replay revoke that session, including its access tokens. Current project memberships are checked on every request.
- Tokens are kept in localStorage as agreed. This means an XSS vulnerability could expose them. Content is rendered as plain text, external links are limited to HTTP(S), and script execution is restricted by a Content Security Policy. Development-only inline scripts are authorised by exact hashes rather than enabling arbitrary inline JavaScript. HttpOnly cookies remain a future improvement.
- Invitation links use a URL fragment; inspection and acceptance send the token in a POST body so it is not placed in normal access-log URLs. Only token hashes are stored. Invitations expire after seven days, are single-use, and cannot change an existing account's role or organisation.
- Authentication routes use a simple per-IP, in-memory limiter. Run one backend worker for this prototype. A shared limiter would be needed for multiple workers.

## Verification

Backend integration tests run against a separate PostgreSQL database whose name ends in `_test`. Tests apply the real migrations, then roll back each test's data.

For this machine's prepared database:

```sh
TEST_DATABASE_URL=postgresql+psycopg://portal@127.0.0.1:55432/portal_test \
  .venv/bin/pytest -c backend/pytest.ini -q
npm --prefix frontend test
npm --prefix frontend run build
```

For Docker with the default development credentials:

```sh
docker compose exec db createdb -U portal portal_test
docker compose exec -e TEST_DATABASE_URL=postgresql+psycopg://portal:portal@db:5432/portal_test backend pytest -q
```

Do not point tests at the application database. `createdb` is only needed once.

Automated coverage includes agency signup, duplicate email rejection, signup validation and isolation, onboarding, all three roles, cross-agency/project access, hidden candidate feedback, nested-resource IDs, removed access, invitation expiry/reuse/revocation, role matching, refresh rotation/replay, logout, unread-message watermarks, append-only conversations, stage changes, milestone completion/reopening, URL validation and rate limiting. Frontend component tests exercise role-specific controls, feedback submission, milestones, messages and API error rendering.

**Browser smoke testing remains unverified:** the session did not expose an available browser. Component tests run in jsdom, not a real browser. Before relying on the UI, open each demo account and check:

1. Admin: create a client/search, invite a user, and assign/remove project access.
2. Recruiter: edit a brief and candidate, share/hide the candidate, post an update and complete/reopen a milestone.
3. Client: verify the hidden candidate is absent, add feedback and a message, and confirm editing controls are unavailable.
4. Refresh/reopen each project; confirm persistence and unread state. Try desktop/mobile widths and keyboard navigation.

## Deliberate limits

This is a local learning project. It has no file uploads, transactional email, password-reset workflow, WebSocket chat, automated milestone calculations, electronic signing, audit log, production deployment or infrastructure. Organisations and users use the agreed simple membership model; it does not support multi-agency accounts or fine-grained per-field permissions.
