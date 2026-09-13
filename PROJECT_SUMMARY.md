# Client Portal Project Summary

## Purpose and current implementation

Searchroom is a local recruitment client portal. Each project represents one retained search for one role. Recruiters and invited clients share a search brief, agreement terms, candidates, updates, messages and a manual milestone timeline.

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

New agency administrators can use **Create account** on the login page. The signup form collects their name, agency name, email, password and password confirmation, then signs them into a new, empty agency workspace. Existing emails are rejected, roles are assigned by the server, and matching agency names or email domains never grant access to another workspace. No schema migration is needed.

Recruiters and clients join existing workspaces by invitation; there is no email delivery or email verification. Admins create an email-bound link and share it manually. Links expire after seven days, are single-use and can be revoked. Existing users sign in with the invited account to accept additional project access. Invitations cannot replace existing passwords, roles or organisations.

Passwords use Argon2 hashing. JWT access tokens expire after 15 minutes; seven-day refresh tokens rotate and can be revoked. Tokens live in localStorage as explicitly agreed. Database-backed sessions allow immediate logout/replay revocation, and membership removal takes effect on the next project request.

LocalStorage remains an XSS trade-off. Plain-text rendering, HTTP(S)-only external links, a Content Security Policy, short access lifetimes and server-side refresh revocation reduce risk. A move to HttpOnly cookies is deferred. The simple authentication limiter is intended for a single development worker.

## Technical structure

- **Frontend:** React, TypeScript, Vite, React Router, a shared typed fetch client and responsive CSS.
- **Backend:** FastAPI, Pydantic request/response contracts, PyJWT and pwdlib, synchronous SQLAlchemy with psycopg.
- **Database:** PostgreSQL stores agencies, client organisations, users, memberships, projects, invitations, sessions, candidates/feedback, document links, posts/comments, messages/read markers and milestones. Alembic versions the schema.
- **Local development:** Docker Compose configuration, environment-based secrets, an interactive admin bootstrap command, optional fictional demo data and a local launcher.
- **Verification:** PostgreSQL integration tests and frontend component tests plus TypeScript/build checks. Real-browser smoke testing is still unverified because no browser surface was available; Docker execution was also unavailable in the implementation environment.

## Acceptance criteria

1. An admin creates a project, assigns a recruiter and manually shares a client invitation.
2. Users sign in and see only authorised projects.
3. Recruiters maintain the brief, agreement terms, pipeline, document links and manual timeline.
4. Clients review shared information, leave candidate feedback and collaborate through updates/messages.
5. Hidden candidates, other organisations and unauthorised projects remain inaccessible through direct API requests.
6. Invitations expire and cannot be reused; refresh tokens rotate and logout revokes the session.
7. Project information and collaboration persist across page reloads; message read markers reflect displayed messages.

## Deferred

File uploads/object storage, email invitations or password resets, real-time messaging, automated milestone calculations, Kanban/task workflows, electronic signatures, detailed permission configuration, production hosting, monitoring and cloud infrastructure.
