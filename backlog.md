# Consolidated engineering backlog

Source reports:

- `assessment/architect.md`
- `assessment/privacy.md`
- `assessment/security.md`
- `assessment/tester.md`

## Review interpretation

The reports agree on an important distinction:

- The application has a strong technical security baseline. No confirmed Critical or High application-code vulnerability, SQL injection path, XSS sink, or unprotected customer-data endpoint was found.
- It is not ready for real candidate data because core privacy governance and individual-rights capabilities are absent or unverified.
- Several high-risk architecture issues could cause transaction inconsistency, excessive database contention, cross-tenant data corruption, or operational blind spots.
- The tester’s “Critical” ratings describe missing assurance around sensitive operations, not confirmed Critical vulnerabilities.

Priorities used below:

- **P0 — Release blocker:** complete before real candidate data is processed.
- **P1 — High:** complete before wider production use or significant feature expansion.
- **P2 — Medium:** important reliability, maintainability, or assurance improvement.
- **P3 — Low:** cleanup or conditional hardening.

---

## P0 — Release blockers

### B01. Establish privacy governance and candidate transparency

**Problem**

There is no demonstrated candidate privacy notice, Article 14 notification workflow, processing-purpose record, lawful-basis record, or evidence that indirectly sourced candidates are informed. The system also does not record source, collection date, notice version, special-category condition, or criminal-offence condition.

This is primarily a governance deficiency, but the product currently provides no support for operating the required process.

**Recommended action**

- Obtain legal/privacy-owner decisions on controller, joint-controller and processor roles.
- Publish privacy notices for candidates, agency users and client users.
- Define purposes and lawful bases per processing activity.
- Add structured candidate fields for source, collection date, purpose, lawful basis, notice version/date, and any applicable Article 9 or Article 10 condition.
- Create an Article 14 notification workflow with recorded delivery, exception and outcome states.
- Complete DPIA screening before launch and a full DPIA if required.

**Acceptance criteria**

- Approved privacy notices are publicly accessible and linked from registration and the authenticated application.
- Every newly created candidate record has a documented source, collection date, processing purpose and lawful basis.
- Indirectly sourced candidates enter a tracked notification workflow.
- Notice version and date supplied are recorded.
- Special-category or criminal-offence processing cannot be recorded without an approved condition and safeguard reference.
- Controller/processor decisions, DPIA outcome and any legitimate-interests assessments are approved by the responsible human owner.
- A fictional-data test demonstrates the end-to-end notification workflow.

**Manual verification required:** Legal interpretation, privacy notices, lawful bases, DPIA, and controller/processor determinations require qualified human approval.

---

### B02. Implement candidate rights and case management

**Problem**

The existing project export and whole-project purge cannot reliably satisfy candidate access, correction, restriction, objection or erasure requests. There is no candidate-wide search across projects, free text, linked documents or restored data, and no request/deadline log.

**Recommended action**

Create a rights-request service and administrator workflow covering:

- Request intake, identity verification, due date and decision.
- Candidate-centric search across structured records.
- Candidate export.
- Correction, restriction and objection flags.
- Candidate deletion or anonymisation with documented exemptions.
- Recipient notification following correction, restriction or erasure.
- Restore-time reapplication of deletions.

Free-text and external-document discovery may initially require a clearly documented manual review stage.

**Acceptance criteria**

- An authorised administrator can locate every structured record directly associated with a candidate across projects.
- Candidate export contains the applicable structured data and identifies items requiring manual free-text or external-provider review.
- Restriction prevents ordinary processing while preserving records that must legally remain.
- Erasure either deletes, anonymises, or records an approved exemption for every located item.
- The workflow records identity verification, statutory due date, outcome, operator and completion date.
- Tests cover cross-agency isolation, hidden candidates, duplicate names, exemptions and partial failures.
- A restore drill proves erased data is not silently returned to active processing.

**Manual verification required:** Identity verification, exemptions, free-text review, recipient notification, and the legal completeness of a subject-access response.

---

### B03. Replace the single review interval with enforceable retention controls

**Problem**

The current agency setting is only a project review interval. It does not automatically surface or dispose of overdue projects, active projects can remain open indefinitely, and different data categories are treated as though they share one retention period.

Retention documentation also conflicts: operational logs are described as 30 days while AWS Terraform reportedly configures 14 days.

**Recommended action**

- Approve a category-specific retention schedule for candidate records, communications, account data, audit events, logs and backups.
- Treat project retention as review-based unless automatic disposal is explicitly approved.
- Add scheduled overdue-retention reporting, assigned review ownership and recorded outcomes.
- Prevent indefinite avoidance of retention through permanently active projects.
- Add a deletion ledger that can be reapplied following restoration.
- Reconcile documented and deployed log-retention periods.
- Extend cleanup tests around every time boundary.

Relevant cleanup code is in `backend/app/operations.py`; retention administration is in `backend/app/admin.py`.

**Acceptance criteria**

- Each data category has an approved purpose, retention trigger, period and disposal method.
- A scheduled job identifies all overdue items and alerts an accountable administrator.
- Every review records retain/delete/anonymise, reason, operator and next review date.
- Records one second before, exactly at, and one second after each cutoff behave as specified.
- A simulated cleanup failure rolls back all deletions in that run.
- Restoring a backup automatically or procedurally reapplies outstanding deletion-ledger entries before normal service resumes.
- Documentation, live log groups, database backups and S3 lifecycle rules agree.

**Manual verification required:** Retention periods, review decisions, live scheduler operation, backup expiry, final snapshots and actual log-group configuration.

---

### B04. Control external CVs, documents and attachments

**Problem**

The database stores arbitrary approved HTTPS URLs, not controlled document objects. Portal authorization may protect discovery of a URL, but a public or long-lived link can remain usable after access is revoked. Deleting the database record does not delete the provider object.

Relevant URL validation is in `backend/app/schemas.py:39`; document and attachment handling spans project resources and serializers.

**Recommended action**

- Select an approved private document provider.
- Store provider and object identifiers rather than only arbitrary URLs.
- Generate short-lived authenticated access URLs.
- Coordinate source-object deletion and retention with portal records.
- Include external objects in rights searches, exports and retention reviews.
- Define migration or containment for existing links.

**Acceptance criteria**

- Newly added documents cannot be publicly accessible without authentication or a short-lived signed URL.
- Removing project membership invalidates future document access.
- Deleting or anonymising a candidate or document triggers deletion or restriction at the source provider.
- External objects appear in rights and retention reports.
- Provider deletion failures remain visible and retryable rather than being reported as success.
- Integration tests cover upload/reference, access, expiry, revocation and deletion.

**Manual verification required:** Supplier due diligence, Article 28 terms, link behaviour at the real provider, support locations and international transfers.

---

### B05. Control sensitive information and internal/client disclosure

**Problem**

Candidate summaries, feedback, documents, updates, comments and messages can contain special-category or criminal-offence data. Documents, posts, comments and messages are visible to all assigned client members and do not have the candidate-level `client_visible` protection.

This creates two related risks: uncontrolled sensitive-data collection and accidental disclosure of hidden candidates through collaboration content.

**Recommended action**

- Introduce `internal` and `client_visible` classification for collaboration records and attachments.
- Default new content to the least-visible appropriate classification.
- Add warnings and guidance against entering unnecessary sensitive information.
- Require a recorded condition before intentionally storing classified sensitive data.
- Extend access policies and exports to respect classification.

**Acceptance criteria**

- Client users cannot access internal documents, posts, comments, messages or attachments.
- Recruiters can preview exactly what a client will see before publishing.
- Hidden-candidate identifiers or attachments are not exposed through client-visible APIs in tested scenarios.
- Sensitive-data classification and approved condition are recorded where applicable.
- Tests cover direct access, list filtering, exports, notifications and cross-project identifiers.
- Existing content receives a reviewed classification before real client access.

**Manual verification required:** Classification of migrated content and approval of sensitive-data handling rules.

---

### B06. Complete supplier, transfer and production governance

**Problem**

The repository does not establish Article 28 agreements, subprocessor inventory, international-transfer safeguards, breach procedures, staff controls or end-of-contract deletion. Infrastructure definitions and documentation do not prove the live environment is configured as intended.

**Recommended action**

Complete the organisational controls and verify the exact production deployment:

- Controller/processor and joint-controller agreements.
- Subprocessor and transfer register.
- Breach-response process and breach register.
- Staff confidentiality, access and training controls.
- End-of-contract return/deletion procedure.
- Live checks for region, database networking, TLS, secrets, logs, backups, email and document provider.
- Restrict public tenant registration to approved agencies or add an approval gate.

**Acceptance criteria**

- Required contracts and supplier records are signed and owned.
- Production tenant creation requires explicit approval or contractual onboarding.
- The exact deployment is recorded and checked against an approved configuration baseline.
- A fictional-data, three-role acceptance pilot succeeds on the real HTTPS service.
- Backup, restore, deletion, email failure and access-revocation exercises produce retained evidence.
- An incident tabletop exercise records actions, owners and lessons.
- No claim of compliance or production readiness is made solely from Terraform, documentation or test source.

**Manual verification required:** All contractual and live-environment evidence.

---

## P1 — High-priority engineering work

### B07. Make transaction ownership explicit

**Problem**

Authentication and rate-limiting helpers commit during request processing:

- `backend/app/security.py:117-127`
- `backend/app/security.py:154-169`
- `backend/app/resources.py:74-82`

A normal authenticated write may commit session activity, user rate limits, agency rate limits and the business change in separate transactions. Earlier side effects can therefore survive later business failure, while helper reuse could unexpectedly commit unrelated changes.

**Recommended action**

- Give each business command one explicit transaction boundary.
- Remove `commit()` from reusable domain and authorization helpers.
- Use a separate, explicitly owned session for independent rate-limit persistence.
- Update session activity only when a defined threshold is reached rather than on every request.
- Add rollback and concurrency tests before changing behaviour.

**Acceptance criteria**

- No reusable authentication, policy or domain helper commits the caller’s transaction.
- Every mutating service declares its transaction boundary.
- A forced failure after mutation leaves no partial business data or success audit event.
- Rate-limit counters remain durable when a business transaction rolls back.
- Session activity updates no more frequently than the documented threshold.
- Existing CSRF, session-expiry, rate-limit and concurrent-write tests pass.

---

### B08. Reduce locking scope and document protected invariants

**Problem**

Unsafe project requests generally lock both agency and project rows, some routes lock projects twice, and some GET operations acquire locks:

- `backend/app/access.py:9-27`
- `backend/app/admin.py:88-95`
- `backend/app/admin.py:165-170`
- `backend/app/projects.py:165,242,331,356,418`

This can serialize unrelated projects in the same agency and cause exports or reads to hold unnecessary locks.

**Recommended action**

Introduce distinct accessors:

- Unlocked owned-project read.
- Project row lock for project-local mutations.
- Agency lock only for agency-wide quota or last-administrator invariants.
- Invitation-specific locking for acceptance/revocation.

Document the invariant protected by every lock and remove redundant lock acquisition.

**Acceptance criteria**

- Read-only project, member, preview and export routes do not acquire row locks unless a documented invariant requires one.
- Writes to two unrelated projects in the same agency can proceed concurrently.
- Candidate/project/user quota races cannot exceed their limits.
- Last-active-administrator protections remain correct during concurrent promotion and suspension.
- Lock-timeout tests distinguish genuine contention from database unavailability.
- Each `FOR UPDATE` use has an adjacent explanation or named locking function.

---

### B09. Enforce tenant relationships in PostgreSQL

**Problem**

Tenant consistency is mainly enforced by application checks. Independent foreign keys allow structurally invalid combinations between agencies, client organisations, projects, users, memberships and invitations.

Relevant models include:

- `backend/app/models.py:65-83`
- `backend/app/models.py:86-103`

**Recommended action**

- Audit existing data for violations before migration.
- Add the minimum composite unique keys and composite foreign keys necessary to enforce agency and client-organisation relationships.
- Add role-specific invitation constraints.
- Use a narrowly scoped constraint trigger only where foreign keys cannot express the rule.
- Keep application validation for usable error messages.

**Acceptance criteria**

- PostgreSQL rejects a project linked to another agency’s organisation.
- PostgreSQL rejects cross-agency project memberships.
- Client membership cannot point to a project belonging to a different client organisation.
- Inconsistent invitation combinations are rejected.
- Migration preflight identifies existing invalid rows without modifying them.
- Migration upgrade and downgrade behaviour is tested on representative data.
- Direct SQL tests prove the rules do not depend on FastAPI.

**Manual verification required:** Review any existing violating records and approve their remediation before constraints are applied.

---

### B10. Fix migration-aware readiness

**Problem**

Readiness compares the database revision with the literal `readiness_20260913` at `backend/app/main.py:179-184`. A valid future migration can therefore make a healthy release fail readiness.

**Recommended action**

Use Alembic’s migration graph to discover repository head or heads and compare them with applied database heads. Add capability checks only for schema features required by the running release.

**Acceptance criteria**

- Readiness accepts the actual current Alembic head without a copied revision constant.
- Missing, stale, divergent and multiple-head states have defined test outcomes.
- A newly added test migration changes the expected head without requiring an application-code edit.
- Database connection failure and schema mismatch return sanitized `503` responses.
- Repository-head discovery is cached appropriately.

---

### B11. Restore useful production diagnostics

**Problem**

Global error handling at `backend/app/main.py:73-92` and `backend/app/main.py:125-140` suppresses the information needed to distinguish programming errors, constraint failures, lock timeouts and database outages. Every `IntegrityError` is described as a concurrent conflict.

**Recommended action**

- Log exception class, stable category, route template, request ID and PostgreSQL SQLSTATE where available.
- Send stack traces to a restricted monitoring system.
- Handle known constraint violations near their owning operation.
- Keep bodies, cookies, tokens, SQL parameters and connection strings out of logs.
- Give lock, statement, pool and connection failures distinct operational categories.

**Acceptance criteria**

- Operators can correlate every unexpected `500` with a sanitized cause and stack trace.
- Known uniqueness/version conflicts return their documented client response.
- Unknown integrity errors are not mislabeled as expected concurrency conflicts.
- Tests confirm passwords, tokens, bodies, query strings and database credentials are absent from logs.
- Alerts distinguish database outage, pool exhaustion, lock timeout and application error.

**Manual verification required:** Monitoring-system access controls, retention and redaction in production.

---

### B12. Strengthen password or MFA requirements

**Problem**

Single-factor recruiter and client accounts accept any password of ten or more characters at:

- `backend/app/schemas.py:64`
- `backend/app/schemas.py:81`
- `backend/app/schemas.py:150`
- `backend/app/auth.py:102`

There is no common/breached-password rejection.

**Recommended action**

As the immediate baseline, require at least 15 characters for accounts that can authenticate without MFA and reject known-common passwords locally. Continue allowing long passphrases without arbitrary composition rules. Evaluate mandatory MFA for every role separately.

**Acceptance criteria**

- Registration, invitation acceptance and password reset enforce one shared policy.
- Common values such as `Password1!` are rejected even if length rules are met.
- Long passphrases are accepted.
- Existing password hashes remain usable until the user changes or resets the password.
- Error responses do not expose blocklist internals or account existence.
- Tests cover all three password-entry workflows and boundary lengths.

**Manual verification required:** Product decision on forced reset for existing accounts and whether all roles will require MFA.

---

### B13. Upgrade vulnerable `urllib3`

**Status: Dependency update and advisory audit complete; remaining image verification is outstanding.**

**Problem**

The security report identified `urllib3==2.7.0` in `backend/requirements.lock:39` as affected by published vulnerabilities fixed in 2.8.0. The runtime requirement and lock now specify `urllib3>=2.8,<3` and `urllib3==2.8.0`, respectively.

**Recommended action**

Upgrade to a compatible patched release, confirm the supported range of the pinned `botocore`, regenerate the lock deterministically and rerun the complete dependency and application test suite.

**Acceptance criteria**

- The production lock resolves `urllib3>=2.8.0`.
- `botocore==1.43.93` dependency consistency was checked with `pip check` and no broken requirements were reported.
- Backend, mail-relay and AWS-related tests pass.
- `pip-audit -r backend/requirements.lock` reports no known vulnerabilities.
- The built production image contains the patched version.

---

### B14. Verify privilege, membership and quota operations

**Problem**

Privilege promotion, member assignment and several quotas have little or no direct test coverage. These are high-impact gaps, but no defect has been confirmed.

**Recommended action**

Add focused PostgreSQL-backed tests for:

- Administrator promotion and session revocation.
- Concurrent promotion and last-admin suspension.
- Member agency, role and client-organisation restrictions.
- Active project, candidate and user quotas.
- Concurrent operations at the final available quota slot.
- User reactivation and successful membership listing.

**Acceptance criteria**

- Only eligible same-agency recruiters can be promoted.
- Promotion revokes existing sessions and emits one audit event.
- Concurrent administration operations always leave at least one active administrator.
- Only valid users gain project membership; duplicates have defined idempotent behaviour.
- Project, candidate and user counts cannot exceed configured quotas under concurrency.
- Permission failures reveal no foreign-tenant object existence.
- Every mutating administrative route has success, denial and cross-tenant coverage.

---

### B15. Make export, purge and audit behaviour complete and testable

**Problem**

Project deletion relies on manually maintained lists in:

- `backend/app/admin.py:334-355`
- `backend/app/admin.py:423-447`

Export and deletion tests do not verify every resource, and most security-sensitive actions do not assert their audit record.

**Recommended action**

- Define schema-level ownership using `ON DELETE CASCADE`, `SET NULL`, or explicit retained relationships.
- Separate deletion policy from export policy.
- Add complete populated-project export and deletion fixtures.
- Add exactly-once audit assertions for sensitive successful operations and no-success-event assertions for failed operations.
- Preserve deliberate audit retention after deletion.

**Acceptance criteria**

- A fully populated project can be exported with every approved business record and no session, token, invitation secret, submission or read-marker record.
- Deleting the project removes every project-owned child and does not affect another project.
- Adding a new project-owned table causes a schema/deletion test failure until its policy is defined.
- Stale deletion previews fail without deleting data.
- Export and purge are admin-only and agency-scoped.
- Audit endpoint ordering, pagination and agency isolation are tested.
- Every named security-sensitive mutation writes exactly one intended audit event.

**Manual verification required:** Legal approval of export scope and audit records retained after erasure.

---

## P2 — Reliability, maintainability and assurance

### B16. Simplify message delivery and read tracking

**Problem**

`GET /messages` mutates and commits a JSON delivery map on the session row, while `ReadMarker` stores separate read state:

- `backend/app/models.py:197-205`
- `backend/app/projects.py:367-457`
- `backend/app/projects.py:577-587`

This makes GET requests write-heavy, creates shared-session contention and gives two tabs coupled state.

**Recommended action**

Adopt one documented keyset-pagination direction and use `ReadMarker(project_id, user_id, last_read_message_id)` as the sole durable read state. If proof of delivery is mandatory, use a short-lived signed acknowledgement token rather than session mutation.

**Acceptance criteria**

- Listing messages performs no database write.
- Two tabs can paginate independently without corrupting acknowledgement state.
- Mark-read remains monotonic under concurrent requests.
- History pagination returns every message exactly once in the documented order.
- Global unread summary includes only accessible messages from other users beyond the marker.
- Migration removes or safely ignores the legacy delivered JSON state.

---

### B17. Extract feature services and explicit API contracts

**Problem**

Large router modules combine HTTP parsing, authorization, locking, transactions, querying, audit and serialization. `backend/app/admin.py:37` imports invitation locking from the authentication router, demonstrating misplaced domain ownership.

Generic `record()` serialization at `backend/app/serializers.py:5-6` copies every mapped column, and several endpoints lack explicit response models.

**Recommended action**

Incrementally establish a modular monolith:

- Thin API routes.
- Feature services owning workflows and transactions.
- Pure authorization policies.
- Focused persistence mechanisms.
- Explicit response schemas and pure mapping functions.

Start with invitations and collaboration workflows. Do not introduce a generic repository layer for every table.

**Acceptance criteria**

- Each migrated route parses HTTP input, resolves the actor, calls one service and returns a declared response model.
- Invitation locking is owned outside router modules.
- Every JSON endpoint has an explicit response model.
- External responses never depend on unrestricted mapped-column copying.
- Serialization performs no hidden database query.
- `PostView.comments` uses `Field(default_factory=list)` at `backend/app/responses.py:89-94`.
- Service transaction and policy logic can be unit-tested without `TestClient`.

---

### B18. Introduce an application factory and structured configuration

**Problem**

Settings, engine, session factory and application construction occur at import time:

- `backend/app/main.py:20`
- `backend/app/database.py:10-21`

`Settings.production_safe()` at `backend/app/config.py:88-175` combines universal safeguards with Railway/AWS/provider assumptions.

**Recommended action**

- Add `create_app(settings, session_factory, services)` with lifespan-owned resources.
- Retain a module-level `app = create_app()` for Uvicorn.
- Split settings into database, session, mail, HTTP, quota and backup groups.
- Separate universal safety requirements from explicit deployment profiles.
- Preserve the strict production checks.

**Acceptance criteria**

- Tests can construct two independently configured applications in one process.
- Importing service or schema modules does not create a database engine.
- Engine disposal occurs during lifespan shutdown.
- Railway and AWS profiles can express their different provider policies without weakening common protections.
- Invalid production configurations fail with grouped, actionable messages.
- Current startup and operational commands continue to work.

---

### B19. Replace private request-body handling

**Problem**

Request limiting assigns to Starlette’s private `request._body` at `backend/app/main.py:109-124` after buffering the whole unsafe request.

**Recommended action**

Implement focused ASGI middleware that wraps `receive`, counts bytes and rejects over-limit bodies without private attributes. Keep a matching ingress/server limit. Separate request ID, headers, body limiting and unexpected-error handling.

**Acceptance criteria**

- Oversized fixed-length and streamed/chunked requests return `413`.
- Downstream JSON and form parsing receive the original body unchanged.
- No private `Request` attribute is read or written.
- Tests cover missing or misleading `Content-Length`.
- Reverse proxy and application limits are documented and aligned.

---

### B20. Protect pending registration credentials

**Problem**

Pending registration and invitation acceptance store `password_hash` in general-purpose `EmailAction.payload` JSON:

- `backend/app/auth.py:73-91`
- `backend/app/auth.py:375-385`
- `backend/app/models.py:207-214`

The value is hashed, not plaintext, but the storage boundary makes accidental export or inspection easier.

**Recommended action**

Prefer a typed pending-registration table with a dedicated password-hash column and strict expiry. Alternatively, encrypt the sensitive payload or defer password creation until email ownership is verified.

**Acceptance criteria**

- Password hashes are not present in general-purpose JSON.
- Pending credentials have a documented maximum lifetime and are removed after completion or expiry.
- They are excluded from logs, exports, generic serializers and administrative responses.
- Registration resend, expiry and single-use behaviour remains correct.
- Tests cover cleanup and partial-failure rollback.

---

### B21. Expand operational and lifecycle testing

**Problem**

The existing suite is strong on authentication and isolation but lacks direct coverage for backup, cleanup, migrations, mail-worker concurrency, collaboration lifecycles, frontend administration and several pagination boundaries. The reports could not rerun tests in the read-only environment.

**Recommended action**

Prioritise tests that prove destructive and recoverability claims:

1. Cleanup boundaries and atomicity.
2. Backup command arguments, KMS settings and failure propagation.
3. Restore comparison across all required tables.
4. Mail expiry, retry exhaustion and concurrent workers.
5. Document/update/comment/feedback/milestone lifecycles.
6. Frontend administration and edit workflows.
7. Isolated Playwright onboarding, collaboration, revocation and retention journeys.

**Acceptance criteria**

- Backup cannot report success without a completed dump and encrypted upload.
- Database credentials never appear in process arguments or logs.
- Restore checks fail on any required table-count or migration mismatch.
- Two mail workers never deliver the same outbox item twice.
- Each mutating API has success, denial and cross-tenant coverage.
- Pagination tests prove no duplicate or skipped records at equal sort values.
- Browser tests use independent fixtures and do not rely on test order.
- CI retains restore, load and browser evidence as separate artefacts.

---

### B22. Add fast static and infrastructure CI gates

**Problem**

CI has broad system checks but reportedly lacks Python formatting/linting, type checking, migration drift detection, coverage reporting and Terraform validation.

**Recommended action**

Add early, inexpensive gates before PostgreSQL and browser jobs:

- Ruff formatting and linting.
- Pyright or mypy focused on service boundaries and response construction.
- Syntax/import checks.
- `alembic check`.
- Branch-coverage reporting with an initial measured baseline.
- `terraform fmt -check` and `terraform validate`.
- Appropriate infrastructure policy checks before treating AWS definitions as releasable.

**Acceptance criteria**

- Static jobs run before integration jobs and fail fast.
- Model changes without migrations fail CI.
- Coverage is published and cannot silently decline below the agreed baseline.
- Pure policy tests can run without PostgreSQL.
- PostgreSQL concurrency tests remain in CI against the production major version.
- Terraform formatting and validation pass, while documentation clearly states that validation is not deployment evidence.

---

## P3 — Lower-priority or conditional work

### B23. Remove obsolete authentication structures and rename the signing secret

**Problem**

Unused `AuthSession` remains at `backend/app/models.py:106-113` and is still included in cleanup at `backend/app/operations.py:18-27,122-140`. `JWT_SECRET` now signs non-JWT material.

**Recommended action**

Confirm rollback requirements, migrate away from `auth_sessions`, rename the setting to `SIGNING_SECRET` or `SESSION_SIGNING_SECRET`, and provide a temporary compatibility alias with a deprecation warning. Record the opaque-session decision in an ADR.

**Acceptance criteria**

- No active route, operation or migration depends on `AuthSession`.
- The obsolete table is removed through a reviewed migration.
- New configuration uses the accurate secret name.
- The old name works only during the documented compatibility window.
- Deployment and secret-store configuration are updated without exposing the value.
- The ADR identifies the authoritative session model.

**Manual verification required:** Confirm that no rollback release or external process still uses the old table or environment name.

---

### B24. Strengthen HSTS only after domain-wide verification

**Problem**

Production HSTS at `backend/app/main.py:153` omits `includeSubDomains`. Adding it prematurely could break sibling subdomains that are not fully HTTPS-ready.

**Recommended action**

Inventory the parent domain and every subdomain. If all are HTTPS-only, add `includeSubDomains`. Consider preload only through a separate, deliberate approval.

**Acceptance criteria**

- Every affected subdomain is inventoried and tested over HTTPS.
- HTTP redirects safely to HTTPS where applicable.
- No required subdomain depends on plain HTTP.
- Only after that evidence exists, the header becomes `max-age=31536000; includeSubDomains`.
- Preload is not enabled merely as part of this change.

**Manual verification required:** DNS/subdomain ownership and HTTPS readiness.

---

# Suggested implementation order

1. **Declare a fictional-data-only release gate.**
2. Complete privacy ownership, DPIA screening, lawful-basis, transparency and supplier decisions: **B01, B06**.
3. Approve the category-specific retention and document-provider strategy: **B03, B04, B05**.
4. Fix migration-aware readiness before introducing schema migrations: **B10**.
5. Introduce explicit transactions and narrower locks: **B07, B08**.
6. Add privilege, quota and cleanup tests to protect the refactor: **B14, B21**.
7. Audit existing tenant data, then add database invariants: **B09**.
8. Implement rights management and enforceable retention/deletion workflows: **B02, B03**.
9. Complete export, purge, audit and restore integrity: **B15**.
10. Upgrade `urllib3` and strengthen password policy: **B12, B13**.
11. Simplify message state: **B16**.
12. Extract services and response contracts incrementally: **B17**.
13. Add the application factory, structured settings and ASGI body limiter: **B18, B19**.
14. Protect pending credentials and remove legacy authentication structures: **B20, B23**.
15. Add static/infrastructure gates and broaden frontend/browser evidence: **B21, B22**.
16. Perform the live fictional-data acceptance, backup/restore, erasure and supplier verification required by **B06**.
17. Add HSTS subdomain coverage only after the domain inventory passes: **B24**.
18. Conduct a focused privacy and security retest before authorising real candidate data.

# Manual verification register

The following cannot be closed through code review or automated tests alone:

- Legal bases, privacy notices, Article 9/10 conditions, controller/processor roles and DPIA.
- Article 28 agreements, subprocessor inventory and international-transfer safeguards.
- Appropriate retention periods and erasure exemptions.
- Existing-data review before tenant constraints or visibility classifications are migrated.
- Real production region, TLS, network isolation, secrets, exact deployed revision and log retention.
- Backup lifecycle, final snapshots, restoration and deletion reapplication.
- External document-provider access expiry and source deletion.
- Email-domain authentication, unrestricted-recipient delivery and failure monitoring.
- Parent-domain and subdomain readiness before `includeSubDomains`.
- End-to-end acceptance using fictional data for administrator, recruiter and client roles.

