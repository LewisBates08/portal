# Client Portal Project Summary

## Purpose and current implementation

Searchroom is a recruitment client portal with local development and a managed UK pilot deployment target. Each project represents one retained search for one role. Recruiters and invited clients share a search brief, agreement terms, candidates, updates, messages and a manual milestone timeline.

The initial application is implemented in `frontend/` and `backend/`. See `README.md` for setup, demo accounts, workflows and verification commands. This summary reflects the approved three-role MVP, replacing the earlier four-role proposal.

## Users and permissions

- **Agency admin:** access every search in their own agency, create searches, add client organisations, invite recruiters/clients, and grant or remove project access.
- **Recruiter:** view and edit assigned projects, including search details, candidates, shared document links and milestones.
- **Client:** view explicitly authorised projects and shared candidates; add candidate feedback, updates, comments and messages. Cannot edit agreement terms, candidate stages or milestones.

Each user belongs to one organisation. Client organisations belong to an agency for this prototype. Users may participate in multiple authorised projects; another user's membership in the same client organisation never grants project access automatically.

Project assignment grants editing permission to recruiters. All API requests check the current database membership and organisation. Nested resource IDs must belong to the authorised project. Frontend visibility is a convenience, not the security boundary.

## Project features

### Overview

Role title, client organisation, search description, ideal candidate profile, start/end dates and agreement terms. Optional external document links support agreements, CVs and related material. Terms are informational; no electronic signing.

### Candidates

Recruiters manage names, current roles/companies, summaries, CV links and stages: Identified, Shortlisted, Interviewing, Offered, Hired and Rejected. Client visibility is explicit and independent of stage. Clients see only shared candidates, grouped by stage, and may add timestamped feedback. Hidden candidates and their feedback are not returned to clients.

### Updates

Chronological shared posts for ideas and search notes, with timestamped comments and optional external attachment links. Everyone authorised for the project can contribute. This is a shared feed, not a Kanban board.

### Messages

One persisted conversation per project. Messages load on entry, after sending or on manual refresh. Unread indicators track other users' messages beyond the last viewed message. Entries are append-only; no real-time sockets or push notifications.

### Timeline

A date-ordered list of milestones with title, description, target date and pending/completed status. Admins and assigned recruiters create, edit, delete, complete or reopen milestones; clients view them. Pending dates before today are overdue. Progress is manually maintained, including targets referring to candidate or interview counts.

## Authentication and invitations

Agency signup queues email verification and creates a separate agency/admin only after verification. Invited new users verify email ownership before receiving project membership. Existing users must sign in with the matching account. Links are email-bound, single-use and expire; invitations cannot change roles or organisations.

Opaque PostgreSQL-backed sessions replace JWT/localStorage. Production cookies are Secure, HttpOnly, host-only and SameSite=Lax; unsafe requests require a CSRF token and matching Origin. Sessions expire after 30 minutes idle or seven days absolute and are immediately revoked by logout, password reset or suspension. Administrators must enrol TOTP MFA and save single-use recovery codes. Argon2 hashes passwords; encrypted secrets support MFA and queued mail. Registration expires after 24 hours, reset links after 30 minutes and invitations after seven days.

## Deployment readiness

Production serves compiled React and FastAPI from one HTTPS origin in a non-root container. Managed PostgreSQL and the app target London/private networking. Alembic runs as a separate locked pre-deployment job. Shared rate limiting, bounded connections, pagination, record versions, submission deduplication and transactional access changes support a small pilot.

Administration includes account suspension, retention settings, project archiving, export and confirmed deletion. Structured audit events, cleanup/email/backup jobs, CI and operational runbooks are included. Cloud resources, secret values, verified email delivery and platform recovery/monitoring must still be configured and validated; see `docs/DEPLOYMENT.md` and `docs/DEPLOYMENT_CHECKPOINTS.md`.

## Technical structure

- **Frontend:** React, TypeScript, Vite, React Router, a shared typed fetch client and responsive CSS.
- **Backend:** FastAPI, Pydantic request/response contracts, pwdlib, encrypted TOTP secrets and cookie sessions, synchronous SQLAlchemy with psycopg.
- **Database:** PostgreSQL stores agencies, client organisations, users, memberships, projects, invitations, sessions, candidates/feedback, document links, posts/comments, messages/read markers and milestones. Alembic versions the schema.
- **Local development:** Docker Compose configuration, environment-based secrets, an interactive admin bootstrap command, isolated test fixtures and a local launcher.
- **Verification:** PostgreSQL integration tests and frontend component tests plus TypeScript/build checks. Includes three-browser HTTPS smoke tests, concurrent PostgreSQL tests and isolated load/restore scripts. Docker verification runs in CI because Docker is unavailable locally.

## Acceptance criteria

1. An admin creates a project, assigns a recruiter and sends or manually shares an email-bound client invitation.
2. Users sign in and see only authorised projects.
3. Recruiters maintain the brief, agreement terms, pipeline, document links and manual timeline.
4. Clients review shared information, leave candidate feedback and collaborate through updates/messages.
5. Hidden candidates, other organisations and unauthorised projects remain inaccessible through direct API requests.
6. Invitations expire and cannot be reused; email ownership is verified and logout revokes the session.
7. Project information and collaboration persist across page reloads; message read markers reflect displayed messages.

## Deferred

File uploads, real-time messaging, automatic milestone calculations, Kanban/task workflows, electronic signatures, cross-agency users and detailed permission configuration. Actual cloud launch is gated on account configuration and staging validation described in the deployment runbook.
