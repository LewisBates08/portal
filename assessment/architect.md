# Architecture Assessment

## Scope

This review covers the current Python/FastAPI backend in `backend/app`, its SQLAlchemy models and migrations, and the backend test/CI structure. It is a read-only assessment; no files were created or modified.

Impact ratings:

- **High:** likely to affect correctness, scalability, security, deployment reliability, or the cost of future changes.
- **Medium:** material maintainability or operational weakness that should be addressed after high-impact issues.
- **Low:** cleanup that reduces confusion or future drift.

## Executive summary

The application has stronger security and data-isolation foundations than many projects at this stage. Particularly good choices include:

- Server-side, revocable sessions rather than browser-stored bearer tokens.
- Explicit project-membership and agency checks.
- Protection of hidden candidates.
- CSRF and Origin validation.
- Optimistic version checks.
- Idempotency handling for collaboration writes.
- Bounded pagination.
- PostgreSQL concurrency tests.
- Explicit Pydantic response models for most project resources.
- Separate migrations and operational jobs.

The main weakness is not missing functionality. It is that security, concurrency, rate limiting, persistence, and HTTP concerns are tightly interwoven inside routers and shared dependencies. A normal authenticated request can perform several commits and acquire locks before the endpoint’s actual business operation begins. That raises complexity and reduces the application’s safe concurrency.

The best direction is a **modular monolith with feature-oriented services**, not microservices and not a generic repository framework. Keep FastAPI, SQLAlchemy and PostgreSQL, but make transaction ownership explicit and reduce cross-cutting database mutations.

## Priority summary

| Priority | Finding | Impact |
|---|---|---|
| 1 | Hidden commits split one request across multiple transactions | High |
| 2 | Agency and project locks over-serialize unrelated operations | High |
| 3 | Tenant invariants exist mainly in application code, not the database | High |
| 4 | Large routers mix transport, permissions, transactions and domain workflows | High |
| 5 | Production exception handling removes the evidence needed to diagnose failures | High |
| 6 | Readiness is coupled to one hard-coded Alembic revision | High |
| 7 | Import-time settings, engine and application construction impede testing | Medium |
| 8 | Generic serialization and incomplete response contracts are fragile | Medium |
| 9 | Request-size middleware relies on private framework state | Medium |
| 10 | Message delivery/read tracking is disproportionately complex and write-heavy | Medium |
| 11 | Project deletion depends on a manually maintained table list | Medium |
| 12 | Configuration combines unrelated policy and provider validation | Medium |
| 13 | Pending registration password hashes are stored in general-purpose JSON | Medium |
| 14 | Dead authentication structures and legacy names obscure the active design | Low |
| 15 | CI lacks static quality and migration-drift checks | Medium |

---

## Findings

### 1. Hidden commits split requests across multiple transactions

**Evidence**

- `signed_in_user()` updates session activity and commits during authentication: `backend/app/security.py:117-127`.
- `throttle()` commits internally: `backend/app/security.py:154-169`.
- `write_limit()` invokes `throttle()` once for reads and twice for writes: `backend/app/resources.py:74-82`.
- Route handlers then perform their own commits throughout `auth.py`, `admin.py`, and `projects.py`.

**What is done badly**

Transaction boundaries are owned by low-level helpers and dependencies rather than by the application operation. An authenticated write can involve:

1. A commit for extending the session idle deadline.
2. A commit for the per-user rate bucket.
3. A commit for the agency rate bucket.
4. A final commit for the actual operation.

The endpoint cannot tell from its own code where its transaction begins or ends.

**Why this is bad**

- Business operations are not represented by one clear unit of work.
- Reusing `throttle()` after making other changes could accidentally commit those changes.
- Every request creates extra PostgreSQL round trips and WAL activity.
- Failure behaviour is difficult to reason about because earlier side effects may already be committed.
- Tests must know about internal commits and use savepoint-specific fixture behaviour.
- Future service-layer refactoring becomes riskier because helpers have surprising persistence effects.

**How to improve it**

- Establish one explicit transaction boundary for each business command.
- Remove `commit()` from reusable domain helpers.
- Give rate limiting a separate, narrowly scoped session or connection so its independent commit is explicit.
- Avoid updating session activity on every request. Update it only when the stored expiry is approaching a threshold, such as once every five minutes.
- Use a pattern such as:

```python
def update_candidate(...):
    with db.begin():
        user = authentication_service.require_user(...)
        candidate = candidate_service.update(...)
        audit_service.record(...)
    return candidate
```

- Keep intentionally independent operations, such as rate-limit counters, clearly separated from the endpoint’s business transaction.

**Impact:** **High**. This would improve correctness, performance and comprehensibility across almost every authenticated endpoint.

---

### 2. Locking is much coarser than the business invariants require

**Evidence**

- Every unsafe project request locks the agency and then the project: `backend/app/access.py:9-27`.
- Several endpoints call `lock_project()` again after `project_access()` has already locked it: for example `backend/app/projects.py:165`, `242`, `331`, `356`, and `418`.
- `owned_project()` locks both the agency and project, even when used by read endpoints: `backend/app/admin.py:88-95`.
- Invitation creation locks the agency directly and then calls `owned_project()`, which requests the agency lock again: `backend/app/admin.py:165-170`.

**What is done badly**

A broad lock-order convention has been used as the default solution for many concurrency risks. Consequently, writes to different projects in the same agency can block each other.

Some GET operations, including project member lists, deletion previews and exports, also acquire row locks through `owned_project()`.

**Why this is bad**

- One slow write can delay unrelated work across an entire agency.
- Long-running exports can hold locks while a streamed response is produced.
- Redundant lock calls make it difficult to know which lock protects which invariant.
- Increasing Uvicorn workers or application replicas would expose this contention more clearly.
- PostgreSQL lock timeouts may turn ordinary contention into user-facing 503 responses.

**How to improve it**

Create separate accessors with distinct semantics:

- `get_owned_project()` for an unlocked read.
- `lock_project_for_update()` for operations modifying one project.
- `lock_agency_for_quota()` only for agency-wide quotas or last-administrator invariants.
- An invitation-specific lock for invitation consumption.

Document the invariant next to each lock. For example, candidate-count enforcement needs a project-scoped serialization mechanism, while the last-active-administrator rule needs an agency-scoped lock.

Remove repeated `lock_project()` calls where the dependency already returned a locked row.

**Impact:** **High**. This would materially improve concurrency while making the locking design easier to validate.

---

### 3. Core tenant invariants are not enforced by the database

**Evidence**

The schema uses independent foreign keys:

- `Project.agency_id` and `Project.client_org_id`: `backend/app/models.py:65-83`.
- `Membership.project_id` and `Membership.user_id`: `backend/app/models.py:86-90`.
- Invitation agency, organisation and project references: `backend/app/models.py:92-103`.

Application code checks that these records belong together, but the database can still represent:

- A project whose client organisation belongs to another agency.
- A membership connecting a user from one agency to another agency’s project.
- A client membership for a project belonging to a different client organisation.
- An invitation whose project, agency and client organisation conflict.

**What is done badly**

Tenant consistency depends almost entirely on every write path remembering the same validation rules.

**Why this is bad**

- A new administrative script, migration, import process, or future endpoint can create invalid cross-tenant data.
- Once invalid data exists, otherwise correct permission queries may behave unpredictably.
- Security boundaries are stronger when structural impossibilities are rejected by PostgreSQL, not only by FastAPI code.
- Unit tests cannot protect write paths that do not exist yet.

**How to improve it**

Where practical, enforce invariants structurally:

- Add composite unique constraints such as `(id, agency_id)` on organisations, projects and users.
- Reference `(client_org_id, agency_id)` from projects to client organisations.
- Consider carrying `agency_id` on memberships and referencing matching composite keys.
- Add invitation check constraints for role-specific combinations.
- If the client-organisation membership invariant cannot be expressed cleanly through foreign keys, use a narrowly scoped constraint trigger.
- Retain application validation to provide helpful error messages.

Avoid duplicating every tenant identifier without purpose; add only the columns needed to make key security invariants enforceable.

**Impact:** **High**. This is defence in depth for the application’s most important security boundary.

---

### 4. Router modules contain too many responsibilities

**Evidence**

- `projects.py` is approximately 587 lines.
- `admin.py` is approximately 471 lines.
- `auth.py` is approximately 435 lines.
- Endpoints directly perform validation, authorization, locking, queries, mutation, audit creation, serialization and commits.
- `admin.py` imports `lock_invite` from the authentication router module: `backend/app/admin.py:37`.

**What is done badly**

HTTP route modules also act as application services, repositories, transaction managers and serializers. Business workflows are therefore difficult to reuse or test without invoking FastAPI.

The `admin -> auth` import is a symptom: invitation locking is domain behaviour, but its ownership is currently whichever router first needed it.

**Why this is bad**

- Changes to one workflow require understanding several cross-cutting helpers.
- Authorization and transaction behaviour can diverge between endpoints.
- Unit testing domain behaviour without a TestClient and PostgreSQL is difficult.
- Large files make reviews less reliable.
- Shared behaviour accumulates in generic helper modules such as `resources.py`, which eventually become another form of coupling.

**How to improve it**

Use feature-oriented modules within the existing monolith:

```text
app/
  api/
    auth_routes.py
    project_routes.py
    admin_routes.py
  services/
    authentication.py
    invitations.py
    projects.py
    collaboration.py
    administration.py
  policies/
    project_access.py
  persistence/
    sessions.py
    rate_limits.py
  models.py
  schemas/
```

Each route should generally:

1. Parse HTTP input.
2. Resolve the actor.
3. Call one application service.
4. Return a declared response.

Do not introduce a generic repository abstraction for every table. SQLAlchemy queries are appropriate inside focused feature services.

**Impact:** **High** for maintainability and future feature development. This can be done incrementally, one workflow at a time.

---

### 5. Production error handling removes useful diagnostic evidence

**Evidence**

- The top-level middleware catches every unexpected exception in production: `backend/app/main.py:125-140`.
- It logs only `request_failed` and a request ID, without the exception class, category, stack or sanitized cause.
- Database `OperationalError` and `TimeoutError` are both mapped to the same response: `backend/app/main.py:83-92`.
- `IntegrityError` is always described as a concurrent conflict: `backend/app/main.py:73-80`.

**What is done badly**

The application intentionally avoids logging sensitive exception data, but goes so far that production failures become almost impossible to diagnose.

It also treats all integrity errors as expected user conflicts, although they may represent a programming error, invalid migration state, or missing invariant handling.

**Why this is bad**

- A request ID cannot help if no corresponding cause is recorded.
- Programming failures may be presented as recoverable conflicts.
- Operators cannot distinguish connection failure, lock timeout, statement timeout and database restart.
- Mean time to recovery will be high during a real incident.

**How to improve it**

Record structured, sanitized failure information:

- Exception class.
- Stable error category.
- Route template and request ID.
- PostgreSQL SQLSTATE where available.
- A stack trace sent to a restricted error-monitoring system.
- No request body, token, SQL parameters or connection string.

Handle known integrity constraints close to the operation that can violate them. Reserve the global handler for genuinely unexpected failures.

**Impact:** **High** operationally.

---

### 6. Readiness is hard-coded to one migration revision

**Evidence**

`backend/app/main.py:179-184` requires:

```python
revision == "readiness_20260913"
```

**What is done badly**

Application readiness is coupled to a literal migration identifier in source code.

**Why this is bad**

- Adding any new Alembic migration makes the new database revision fail readiness until this line is manually updated.
- A code deployment and migration deployment can become unnecessarily brittle.
- Multiple Alembic heads cannot be represented.
- It checks an identifier rather than the schema capabilities needed by the running version.

**How to improve it**

At minimum, ask Alembic’s `ScriptDirectory` for the repository head or heads and compare them with the database’s applied heads.

For even safer deployment, combine that check with a lightweight capability query for the tables or columns required by the running release. Cache repository-head discovery because the migration scripts do not change during a process lifetime.

Add a test that creates a new temporary migration head or mocks the expected head, demonstrating that readiness follows the migration graph instead of a copied string.

**Impact:** **High** because the current implementation can break an otherwise correct future release.

---

### 7. Application construction and database configuration happen at import time

**Evidence**

- `settings = get_settings()` is evaluated while importing `main.py`: `backend/app/main.py:20`.
- The engine and session factory are constructed while importing `database.py`: `backend/app/database.py:10-21`.
- Routers are attached to a single global `app` object.

**What is done badly**

Importing application modules requires valid environment configuration and permanently establishes global settings, engine and middleware state.

**Why this is bad**

- Tests must mutate environment variables before imports.
- Testing multiple configurations within one process is difficult because settings are cached.
- CLI and operational imports may initialize components they do not need.
- It is harder to inject a test engine, alternate session factory or fake external service.
- Import ordering becomes part of application behaviour.

**How to improve it**

Introduce an application factory:

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    app = FastAPI(...)
    ...
    return app
```

Store durable resources in `app.state`, initialize/dispose them in lifespan, and expose session dependencies through a small dependency provider.

A module-level `app = create_app()` can remain for Uvicorn compatibility.

**Impact:** **Medium**. The current design works, but this would significantly improve testability and configuration clarity.

---

### 8. Serialization mixes explicit contracts with unrestricted column copying

**Evidence**

- `record()` returns every mapped column: `backend/app/serializers.py:5-6`.
- Some endpoints use explicit `response_model` declarations, but numerous auth and admin endpoints do not.
- `project_view()` and `authored()` manually add related data through further queries: `backend/app/serializers.py:26-45`.
- `PostView.comments` uses a mutable-looking class default: `backend/app/responses.py:89-94`.

**What is done badly**

The application has good response schemas, but their use is inconsistent. Generic column copying makes internal schema changes implicitly affect application dictionaries.

Pydantic currently protects many declared endpoints by filtering fields, but routes without response models do not receive that protection.

**Why this is bad**

- Adding a sensitive column to a model may expose it from an untyped endpoint or export path.
- OpenAPI contracts are incomplete.
- Response construction is scattered across dictionaries, model instances and serializer functions.
- Query behaviour is hidden inside serialization functions.
- Contract drift becomes likely as models change.

**How to improve it**

- Give every JSON endpoint a response model, including authentication and administration.
- Create explicit mapping functions for externally returned resources.
- Keep raw database export serialization separate and clearly named.
- Replace `comments: list[...] = []` with `Field(default_factory=list)`, even though Pydantic currently copies defaults safely.
- Have service/query functions fetch all required related data, then let serialization remain a pure transformation.

**Impact:** **Medium**, with a security benefit from making accidental field exposure less likely.

---

### 9. Request-size enforcement relies on a private `Request` attribute

**Evidence**

The middleware consumes the body and assigns it to `request._body`: `backend/app/main.py:109-124`.

**What is done badly**

The implementation uses Starlette’s private `_body` field to make a consumed request body available downstream.

**Why this is bad**

- Private framework internals are not a stable compatibility contract.
- A Starlette/FastAPI upgrade could subtly break downstream body parsing.
- Every unsafe request is fully buffered in application memory.
- Security headers, body limiting, exception conversion, timing and logging are all combined into one middleware function.

**How to improve it**

Implement request-size limiting as a small ASGI middleware that wraps the `receive` callable and counts incoming bytes without mutating private `Request` state. Also enforce a corresponding ingress/server body limit.

Split the current middleware into focused components:

- Request ID and access logging.
- Response security headers.
- Body-size limiting.
- Unexpected-error handling.

**Impact:** **Medium**. The current cap is sensible, but the mechanism is brittle.

---

### 10. Message delivery and read tracking are overcomplicated

**Evidence**

- `WebSession.delivered` stores a mutable JSON map per project: `backend/app/models.py:197-205`.
- `GET /messages` locks and updates the session row, then commits: `backend/app/projects.py:367-406`.
- Cursor progression depends on both `ReadMarker` and session-local delivered IDs.
- Marking messages read verifies IDs against that session JSON: `backend/app/projects.py:429-457`.
- `/messages/history` uses a separate pagination mode: `backend/app/projects.py:577-587`.

**What is done badly**

A read request mutates shared session state so the server can prove which message IDs were delivered. This combines pagination, unread status, delivery acknowledgement and session security.

**Why this is bad**

- GET requests perform writes and can contend on the session row.
- Two tabs using the same session can interfere with the delivery map.
- The JSON map grows with the number of viewed projects.
- The dual cursor/history behaviour is difficult for clients and maintainers to reason about.
- A comparatively ordinary unread-message feature carries significant state-machine complexity.

**How to improve it**

For this portal’s stated manual-refresh MVP, simplify to:

- Stable keyset pagination using `before_id` or `after_id`.
- A `ReadMarker(project_id, user_id, last_read_message_id)` as the sole persisted read state.
- Mark-read accepts the greatest existing message ID for that project, using the current monotonic upsert.
- If proof of delivery is a strict requirement, issue a short-lived signed acknowledgement token containing the project, user and maximum returned message ID instead of mutating the session on GET.

Document one pagination direction and use it consistently.

**Impact:** **Medium**. Simplification would remove several queries, writes and edge cases.

---

### 11. Project deletion is a manually maintained dependency graph

**Evidence**

- `project_contents()` enumerates related tables manually: `backend/app/admin.py:334-355`.
- `purge_project()` deletes each model in the listed order: `backend/app/admin.py:423-447`.
- Foreign keys do not define cascading behaviour.

**What is done badly**

Correct deletion depends on developers remembering to update `project_contents()` whenever a new project-owned table is added.

The same list is reused for preview, export and deletion even though those operations have different inclusion rules.

**Why this is bad**

- A new child table can make deletion fail in production.
- A table accidentally omitted from preview can make the confirmation count misleading.
- Export explicitly skips selected internal tables, creating another manual policy list.
- Ownership and retention rules are not represented in the schema.

**How to improve it**

Define ownership deliberately:

- Use `ON DELETE CASCADE` for records that have no meaning outside a project.
- Use `ON DELETE SET NULL` or independent retention for audit records that must survive.
- Keep a dedicated export policy rather than deriving it from deletion order.
- Add a migration/schema test that inserts one row for every project-owned table and verifies complete deletion.
- If manual deletion is retained for compliance reasons, describe it as a named deletion plan with explicit tests rather than a generic model list.

**Impact:** **Medium**.

---

### 12. Configuration validation combines unrelated deployment policies

**Evidence**

`Settings.production_safe()` validates database TLS, database usernames, frontend hostnames, trusted hosts, signing keys, Lambda URL shape, SES region, SMTP credentials, static assets and sender configuration in one method: `backend/app/config.py:88-175`.

**What is done badly**

Configuration parsing and deployment policy for several providers are combined into a large validator. It contains provider-specific assumptions such as:

- London SES hostname.
- London Lambda Function URL suffix.
- No custom HTTPS port.
- One exact trusted host.

**Why this is bad**

- Reusing the application on another managed platform requires changing core application code.
- Validation failures are harder to test and understand.
- Unrelated changes to mail transport can affect application startup validation.
- Local, Railway and prospective AWS deployment rules are not clearly separated.

**How to improve it**

Split settings into nested groups:

```text
DatabaseSettings
SessionSettings
MailSettings
HttpSettings
QuotaSettings
BackupSettings
```

Keep universal safety invariants in those groups. Put provider-specific deployment policies in explicit profiles, such as `RailwayProductionSettings` or deployment validation commands.

Retaining a strict production profile is valuable; the goal is separation, not weakening validation.

**Impact:** **Medium**.

---

### 13. Pending registration password hashes live in general-purpose JSON

**Evidence**

- Registration stores `password_hash` inside `EmailAction.payload`: `backend/app/auth.py:73-91`.
- Invitation acceptance does the same: `backend/app/auth.py:375-385`.
- `EmailAction.payload` is a normal JSON column: `backend/app/models.py:207-214`.

**What is done badly**

Although the password itself is correctly hashed, the pending credential is stored alongside general workflow payload data rather than in a purpose-specific protected structure.

**Why this is bad**

- General-purpose JSON is easy to include accidentally in debugging, exports or administrative tooling.
- The system encrypts mail bodies and MFA secrets, but the pending password-hash lifecycle is less explicit.
- A future generic serializer or database inspection tool may expose it.
- Registration state has no typed schema at the persistence boundary.

**How to improve it**

Prefer one of:

- A typed `PendingRegistration` table with a dedicated `password_hash` column and strict expiry.
- Encrypt the entire sensitive action payload using the existing encryption facility, leaving only lookup metadata unencrypted.
- Defer password creation until after email ownership is verified.

Ensure expired pending credentials are deleted promptly and never included in exports or logs.

**Impact:** **Medium**. This is primarily data minimisation and accidental-exposure prevention; the stored value is already a password hash, not plaintext.

---

### 14. Legacy authentication structures remain in the active model

**Evidence**

- `AuthSession` still represents the superseded refresh-token system: `backend/app/models.py:106-113`.
- It is no longer used by active authentication code.
- Cleanup still imports and deletes expired `AuthSession` records: `backend/app/operations.py:18-27` and `122-140`.
- `JWT_SECRET` now signs CSRF/rate-limit material rather than JWTs: `backend/app/config.py:53-54`.

**What is done badly**

The source model still presents two session concepts, and the primary signing secret is named after an authentication design that no longer exists.

**Why this is bad**

- New contributors can mistakenly reuse the obsolete model.
- Security reviews must determine which session table is authoritative.
- Environment configuration communicates the wrong security model.
- Dead schema accumulates indefinitely.

**How to improve it**

- Migrate away and remove `auth_sessions` after confirming no rollback path requires it.
- Rename `JWT_SECRET` to `SIGNING_SECRET` or `SESSION_SIGNING_SECRET`.
- Support the old environment name temporarily through an explicit compatibility alias and deprecation warning.
- Add a short architecture decision record explaining why opaque sessions replaced JWT refresh sessions.

**Impact:** **Low** immediately, but useful cleanup before further authentication work.

---

### 15. CI is broad operationally but lacks static architecture checks

**Evidence**

The readiness workflow runs integration tests, frontend tests, browser tests, load/restore checks, dependency audits and container scans. It does not visibly run:

- A Python formatter check.
- A linter.
- Static type checking.
- Alembic model-to-migration drift detection.
- Import-cycle checks.
- Coverage reporting.

The backend test suite also depends on PostgreSQL at import/collection time: `backend/tests/conftest.py:13-31`.

**What is done badly**

The suite is strong at system verification but weak at fast feedback for code-level quality. Almost every backend test requires database setup, even when testing pure validation or policy logic.

**Why this is bad**

- Simple defects are discovered later than necessary.
- Large router modules can continue growing without measurable pressure.
- Model changes can drift from migrations.
- Developers cannot run a useful lightweight unit-test subset without PostgreSQL.
- Missing response annotations, unused imports and dead code are not automatically detected.

**How to improve it**

Add inexpensive gates before integration tests:

- Ruff for linting and formatting.
- Pyright or mypy for service boundaries and response construction.
- `alembic check` against the test database.
- A read-only import/syntax check.
- Coverage reporting with attention to permission and failure branches.

Extract pure policy and transformation logic into units that can be tested without FastAPI or PostgreSQL. Retain the existing PostgreSQL concurrency tests because they validate behaviour that mocks cannot.

**Impact:** **Medium**.

---

## Recommended target architecture

The application does not need microservices. A modest modular-monolith structure is sufficient:

```text
backend/app/
  main.py
  config/
    settings.py
    production_validation.py
  api/
    auth.py
    projects.py
    administration.py
    dependencies.py
  services/
    authentication.py
    invitations.py
    project_management.py
    collaboration.py
    account_administration.py
  policies/
    project_access.py
    candidate_visibility.py
  persistence/
    database.py
    sessions.py
    rate_limits.py
    idempotency.py
  domain/
    models.py
    commands.py
  schemas/
    auth.py
    projects.py
    administration.py
    common.py
  operations/
    mail.py
    cleanup.py
    backup.py
```

The important boundary is behavioural:

- **API layer:** HTTP parsing, dependencies and response mapping.
- **Service layer:** business workflow and transaction ownership.
- **Policy layer:** reusable authorization decisions without commits.
- **Persistence layer:** focused database mechanisms such as sessions, rate limits and idempotency.
- **Operations:** background and maintenance commands.

## Recommended implementation order

1. **Make transaction ownership explicit.**  
   Remove hidden commits from authentication and rate-limit helpers, using separate sessions where independence is intentional.

2. **Reduce lock scope.**  
   Split locked and unlocked project lookups, remove redundant locks, and retain agency locks only for agency-wide invariants.

3. **Fix readiness migration detection.**  
   Remove the literal Alembic revision dependency before adding further migrations.

4. **Add database tenant invariants.**  
   Introduce composite constraints and migration tests carefully, after checking existing data for violations.

5. **Extract invitation and collaboration services.**  
   These contain the most complicated locking and idempotency workflows and will provide the greatest architectural benefit.

6. **Simplify message read tracking.**  
   Use one stable pagination contract and one persistent read marker.

7. **Complete response contracts.**  
   Add response models to every JSON endpoint and replace generic external serialization.

8. **Introduce an application factory.**  
   Make settings and database resources injectable once service boundaries are clearer.

9. **Replace manual project deletion ownership.**  
   Introduce explicit cascade/retention behaviour and schema-level deletion tests.

10. **Add static CI gates and small unit tests.**

## Verification performed

- Read-only inspection of all 19 backend application modules, backend tests, migrations, CI configuration and deployment entrypoints.
- All 19 backend application modules passed read-only Python AST parsing.
- The full pytest suite could not be executed in the provided read-only environment because pytest requires a writable temporary directory before test collection.
- Bytecode-based compilation was likewise blocked by the filesystem policy.
- Current runtime behaviour is therefore not claimed as reverified by this review.
- The working tree already contained unrelated changes and untracked files; none were modified.

## Overall assessment

The backend is security-conscious and has unusually good coverage of authentication, tenant access, concurrency and operational concerns for a small portal. Its weakness is that those safeguards have accumulated inside the request path without clean transaction and responsibility boundaries.

The next phase should be simplification, not feature expansion. Explicit transactions, narrower locks, stronger database invariants and feature-oriented services would preserve the existing security properties while making the application substantially easier to operate and extend.

