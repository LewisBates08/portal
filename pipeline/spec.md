# Searchroom development roadmap and delivery specification

## 1. Purpose

This specification consolidates the architecture, privacy, security, and test
assessments against the current checkout. It defines:

- the release decision and non-negotiable safety boundaries;
- the ordered roadmap for making Searchroom suitable for a controlled pilot;
- the exact scope for the next developer and tester stages in this pipeline;
- the acceptance evidence required before later roadmap stages begin.

The intended architecture remains a FastAPI, React, SQLAlchemy, and PostgreSQL
modular monolith. This plan does not introduce microservices or a generic
repository abstraction.

## 2. Current state and release decision

Searchroom has a strong baseline: opaque revocable sessions, administrator MFA,
same-origin CSRF protection, project and agency authorization, hidden-candidate
filtering, optimistic versions, idempotent writes, bounded pagination, encrypted
mail content, and PostgreSQL concurrency tests.

The application is not ready for real candidate data. The blocker is not a
confirmed critical code exploit. It is the combination of missing privacy
governance and rights workflows, uncontrolled external documents and free text,
unenforced retention, incomplete production evidence, and several architectural
risks that make future changes harder to prove safe.

Until the release gates in section 9 are met:

- use fictional data only;
- do not describe the service as UK GDPR or Data Protection Act compliant;
- do not treat Terraform, documentation, provider acceptance, or source-level
  tests as proof of a deployed control;
- keep the Searchroom domain, DNS, and email identity separate from Radium;
- do not broaden email delivery beyond the currently verified restrictions
  without a separately verified sender, recipient policy, and production test.

## 3. Planning principles

1. Preserve existing authorization, session, CSRF, candidate-visibility,
   idempotency, and concurrency behaviour while changing internals.
2. Make one business command one explicit transaction. Independently durable
   mechanisms such as rate limiting must use an explicitly separate transaction.
3. Lock only the row that protects the named invariant. Reads must not acquire
   write locks unless their documented contract requires it.
4. Enforce tenant invariants in PostgreSQL as well as in application checks.
5. Keep routes thin and move workflows into feature-oriented services
   incrementally.
6. Treat privacy governance decisions as inputs owned by qualified humans. Code
   may support those decisions but must not invent lawful bases, retention
   periods, controller roles, or exemptions.
7. A feature is complete only when its success, failure, authorization,
   cross-tenant, audit, and recovery behaviour is tested at the appropriate
   layer.
8. Infrastructure is considered available only after deployment and live
   verification in the intended environment.

## 4. Ordered roadmap

### Stage 0: Governance and product decisions

This work starts immediately and can run alongside engineering, but it requires
human privacy, legal, and operational owners.

Deliverables:

- approve candidate, agency-user, and client-user privacy notices;
- determine controller, processor, and any joint-controller roles;
- approve purposes, lawful bases, legitimate-interest assessments, Article 9
  conditions, Article 10/DPA 2018 conditions, and safeguards;
- complete DPIA screening and a full DPIA if required;
- approve a category-specific retention schedule for candidates,
  communications, accounts, audits, logs, database backups, exports, and final
  snapshots;
- establish Article 28 contracts, a subprocessor inventory, international
  transfer safeguards, staff access/training rules, breach response, and
  end-of-contract return/deletion;
- choose an approved private document provider and define its object deletion,
  access expiry, audit, and restore behaviour;
- decide whether tenant creation is invitation/approval-only in production;
- decide whether MFA will become mandatory for recruiters and clients. If it
  remains optional, approve a 15-character minimum password plus local common
  password screening.

Exit criteria:

- each decision has a named owner, approval date, and versioned artefact;
- the engineering team has explicit values and states to encode rather than
  guessing policy;
- no real candidate data is processed while these decisions are unresolved.

### Stage 1: Immediate security and release hygiene

Goals:

- remove the known vulnerable runtime dependency by moving `urllib3` to a
  compatible fixed version at or above 2.8.0 and regenerating the lock through
  the project's dependency process;
- implement the approved authentication decision consistently for registration,
  invitation acceptance, password reset, CLI account creation, frontend hints,
  and tests;
- add local common-password screening if accounts remain single factor;
- enable `includeSubDomains` only after the selected parent domain and every
  subdomain are confirmed HTTPS-only; do not add `preload` in this stage;
- add public privacy-notice routes/links and a production tenant-approval gate
  only after the Stage 0 content and onboarding decision are supplied;
- reconcile the documented 30-day log retention with the Terraform 14-day
  setting using the approved retention schedule.

Exit criteria:

- dependency audit passes with no finding for the shipped `urllib3` version;
- password/MFA rules have positive and negative tests in every account flow;
- security-header tests reflect the approved domain scope;
- documentation, frontend copy, backend validation, and deployment settings do
  not contradict each other.

### Stage 2: Transaction, locking, readiness, and schema foundations

Goals:

- introduce explicit transaction ownership for business commands;
- move rate-limit writes to a dedicated session/connection and stop reusable
  helpers from committing the caller's transaction;
- throttle session idle-expiry persistence to a documented interval rather than
  writing on every authenticated request;
- separate unlocked reads, project-scoped write locks, agency quota locks, and
  invitation-consumption locks; remove redundant lock acquisition;
- make readiness compare the database's Alembic heads with the repository heads
  rather than a copied revision string;
- add composite tenant constraints after a pre-migration consistency audit;
- map known constraint conflicts near the service that can cause them and log
  unexpected failures with a sanitized category, exception class, request ID,
  route template, and SQLSTATE where available;
- retain stack traces only in a restricted error-monitoring destination, never
  in a client response or with request bodies, tokens, SQL parameters, or
  connection strings.

Implementation sequence:

1. Characterize current transaction and concurrency behaviour with regression
   tests.
2. Add a dedicated persistence boundary for rate limits.
3. Remove hidden commits from authentication/access helpers and establish
   service-owned transactions one workflow at a time.
4. Split locked and unlocked accessors and prove unrelated projects in one
   agency no longer serialize.
5. Replace the hard-coded readiness revision.
6. Audit existing rows for cross-tenant inconsistencies, then apply composite
   keys/checks in an Alembic migration.
7. Improve error classification and operational logging.

Exit criteria:

- a forced failure late in a command rolls back its data and success audit
  event;
- rate-limit counters remain durable when the business transaction rolls back;
- read endpoints do not take project or agency `FOR UPDATE` locks;
- concurrent writes to different projects in one agency proceed independently;
- quota, last-administrator, invitation, optimistic-version, and idempotency
  races remain safe;
- PostgreSQL rejects mismatched project, organisation, membership, and
  invitation tenant relationships;
- readiness follows the migration graph, including stale, missing, current, and
  multiple-head cases.

### Stage 3: Privacy data model and individual-rights workflows

This stage begins only when Stage 0 supplies approved policy values.

Add structured support for:

- candidate source, collection date, processing purpose, lawful basis, notice
  version/date/status, and appropriate sensitive-data condition references;
- an Article 14 notification workflow with sent, delivered, exception, failed,
  and completed states;
- rights requests with intake date, identity verification, deadline, request
  types, restriction/objection state, decisions, exemptions, operator, and
  completion evidence;
- candidate-centric discovery across structured records, with an explicit
  manual-review queue for free text, audit records, backups, and provider-held
  objects;
- candidate export, correction, restriction, objection, deletion, or
  anonymisation;
- user offboarding that removes credentials and unnecessary profile data while
  pseudonymising authorship where records must remain;
- recipient notification after correction, restriction, or erasure;
- a deletion ledger that is reapplied before a restored database returns to
  normal service.

Safety requirements:

- rights operations are administrator-only, agency-scoped, fully audited, and
  resumable after partial provider failures;
- duplicate names never determine identity; use stable identifiers and verified
  request matching;
- restriction prevents ordinary processing without destroying records subject
  to a documented hold or exemption;
- exports distinguish directly located data from items requiring human review;
- no automated workflow claims legal completeness without operator sign-off.

Exit criteria:

- cross-project candidate search and export include every applicable structured
  record and external object reference;
- erasure produces delete, anonymise, retained-with-exemption, and provider
  outcomes for every located item;
- a restore drill proves deletion-ledger entries are reapplied before users can
  access restored data;
- privacy-owner acceptance covers access, correction, restriction, objection,
  erasure, notice delivery, and exception handling.

### Stage 4: Retention, document lifecycle, and visibility controls

Goals:

- replace the single agency review interval with category-specific policies and
  triggers approved in Stage 0;
- schedule overdue-review reports, record ownership and decisions, and prevent
  indefinitely active projects from bypassing review;
- store private provider/object identifiers instead of arbitrary long-lived
  document URLs and issue short-lived authenticated access;
- coordinate provider deletion/restriction with portal deletion and expose
  retryable provider failures;
- add `internal` and `client_visible` classifications to documents, posts,
  comments, messages, and attachments, defaulting to the least-visible valid
  choice;
- add a recruiter preview of exactly what clients can see;
- add warnings and controls that discourage unnecessary special-category and
  criminal-offence data.

Exit criteria:

- clients cannot list or retrieve internal collaboration content by direct ID;
- project access removal prevents future document-link issuance;
- provider objects participate in rights requests, exports, and retention;
- cleanup boundary tests cover before, at, and after every cutoff and prove
  transaction rollback on failure;
- scheduled review and deletion jobs produce operator-visible evidence.

### Stage 5: Modular-monolith refactor and contract simplification

Refactor incrementally after transaction semantics are stable:

```text
backend/app/
  api/             # HTTP parsing, dependencies, response mapping
  services/        # feature workflows and transaction ownership
  policies/        # pure authorization and visibility decisions
  persistence/     # sessions, rate limits, idempotency, focused queries
  schemas/         # explicit external contracts
  operations/      # mail, cleanup, backup, restore support
```

Priority extraction order:

1. invitations and membership administration;
2. collaboration and messaging;
3. project/candidate management;
4. account administration and rights requests.

Also:

- introduce `create_app(settings=None)` and initialize database resources through
  lifespan/app state while retaining a module-level Uvicorn app;
- give every JSON endpoint an explicit response model and use explicit external
  mapping rather than copying every mapped column;
- replace request-size handling based on private `request._body` with focused
  ASGI receive middleware plus an ingress limit;
- simplify messaging to one documented keyset-pagination direction and one
  `ReadMarker`, or use a short-lived signed acknowledgement if delivery proof is
  a confirmed requirement;
- encode project-child ownership with deliberate cascades or a named, tested
  deletion plan; keep export inclusion rules separate;
- split settings into database, session, HTTP, mail, quotas, and backup groups,
  with provider-specific production profiles;
- replace pending password hashes in general JSON with a typed pending
  registration record, encrypted payload, or post-verification password setup;
- remove legacy `AuthSession` after rollback requirements are closed and migrate
  `JWT_SECRET` to a correctly named signing secret with a documented compatibility
  period.

Exit criteria:

- routes parse, authorize, call one service, and map a declared response;
- pure policy and mapping tests run without FastAPI or PostgreSQL;
- the OpenAPI contract covers every JSON endpoint in non-production builds;
- message reads no longer mutate a session JSON map;
- adding a project-owned table cannot silently omit it from deletion tests;
- multiple application instances with different injected settings can be
  constructed in one test process.

### Stage 6: Complete assurance and operational evidence

Backend priorities:

1. administrator promotion and membership assignment, including concurrency and
   session revocation;
2. cleanup, category retention, backup, restore, and deletion-ledger behaviour;
3. project, candidate, and user quotas at sequential and concurrent boundaries;
4. invitation list/revoke/expiry and role/organisation contracts;
5. export and permanent deletion completeness;
6. exact-once audit events for sensitive successes and no success event on
   failure;
7. document, update, comment, feedback, milestone, message-history, and summary
   lifecycles and pagination;
8. migration lock, mail worker, operations health, and real database readiness.

Frontend and browser priorities:

- component tests for organisation/project creation, invitation management,
  memberships, user suspension/promotion, candidate conflict handling,
  documents, updates/comments, overview editing, milestones, account actions,
  and pagination;
- isolated Playwright flows for admin onboarding, invitation acceptance,
  recruiter candidate sharing, client visibility/feedback, collaboration,
  access revocation, export, archive, and deletion;
- responsive viewport and automated accessibility checks for critical flows.

CI gates:

- Ruff lint and format checks;
- a selected Python type checker for new service boundaries;
- `alembic check` against PostgreSQL;
- backend branch coverage with an initial measured baseline;
- direct success and denial coverage for every mutating route;
- `terraform fmt -check`, `terraform validate`, and policy/security checks before
  AWS infrastructure is described as releasable;
- PostgreSQL tests on the same major version as production;
- retained artifacts for load, backup/restore, container, dependency, secret,
  and vulnerability checks.

### Stage 7: Fictional-data staging pilot and production decision

Run a three-role pilot on the exact intended HTTPS deployment using fictional
data. Verify configuration, current deployment logs, observed behaviour, and
external provider results.

The pilot must cover:

- domain and TLS status;
- configured hosting/database region and private networking;
- secure cookies, CSRF, trusted hosts, security headers, and MFA/password rules;
- invitation and account-email delivery to several permitted inboxes, plus
  bounce, complaint, retry-exhaustion, and stuck-queue alerts;
- document access expiry and revocation;
- backup creation, decryption, native restore, independent restore, deletion
  reapplication, and previous-image rollback;
- scheduled cleanup and retention-review jobs;
- audit and sanitized error-monitoring visibility;
- admin, recruiter, and client acceptance flows, including removal of access;
- incident response and recovery-account access.

Only after the technical evidence and Stage 0 approvals are complete may the
responsible product/privacy owners authorize real candidate data.

## 5. Scope of this pipeline delivery

The developer stage following this plan must implement a bounded foundation
increment. It must not attempt the policy-dependent privacy product described in
Stages 3 and 4 without approved inputs.

### Required implementation

#### A. Dependency and authentication hygiene

- Update `urllib3` to a compatible non-vulnerable release at or above 2.8.0 and
  update dependency metadata consistently.
- Adopt a 15-character minimum for every password-based account flow because
  recruiter and client MFA is not currently mandatory.
- Add a small, deterministic local blocklist for obvious/common passwords. Do
  not call an external breached-password service from the request path.
- Apply one shared password validator to registration, invitation acceptance,
  reset, and CLI-created accounts.
- Update frontend help/error copy and tests to match. Existing password hashes
  remain valid; the stronger rule applies when setting or changing a password.

#### B. Readiness and production diagnostics

- Replace the literal `readiness_20260913` comparison with repository-head versus
  database-head comparison using Alembic APIs. Support more than one head and
  return only a generic 503 response on mismatch or lookup failure.
- Cache repository head discovery, not database readiness results.
- Classify known integrity conflicts near the responsible operation where
  practical. The global handler must not label every integrity error as a normal
  concurrency conflict.
- In production, log sanitized structured metadata for unexpected failures:
  request ID, route template, exception class, stable category, and SQLSTATE
  when safely available. Continue excluding bodies, cookies, tokens, SQL text,
  SQL parameters, email links, and connection strings.

#### C. Request-size middleware

- Replace `request._body` mutation with a focused ASGI middleware that limits
  streamed request bodies to 1 MiB.
- Preserve the existing 413 contract for unsafe methods and allow downstream
  body parsing to work normally.
- Keep request IDs, response headers, access logging, and unexpected-error
  conversion behaviour separate enough to test independently.

#### D. Transaction and lock characterization, without broad refactoring

- Add regression tests that expose the current hidden transaction boundaries and
  broad-lock behaviour before later refactoring.
- Add a dedicated database-session dependency/factory for rate limiting and make
  its independent commit explicit.
- Remove the rate limiter's ability to commit the business session.
- Do not yet rewrite every route or add tenant composite constraints in this
  increment. Record those as the next Stage 2 slice after the new tests pass.
- Do not weaken quota, idempotency, session revocation, CSRF, or lock ordering to
  make tests pass.

#### E. High-risk test coverage and fast CI gates

Add focused tests for:

- administrator promotion success/rejection and session revocation;
- membership assignment across roles, agencies, organisations, and duplicates;
- project creation prerequisites and project/candidate/user quota boundaries,
  including the final-slot concurrency case;
- cleanup time boundaries and atomic rollback;
- invitation expiry, revocation, listing scope, and role/organisation binding;
- export/deletion completeness and audit behaviour;
- readiness with current, stale, missing, and mocked multiple migration heads;
- request-body limits with content length, chunked input, exact boundary, and a
  downstream JSON parse;
- password acceptance/rejection in all account flows.

Add Ruff lint/format checks and `alembic check` to CI. Add coverage reporting and
publish its artifact, but establish the first threshold from the observed
baseline rather than inventing a percentage. Type checking and Terraform gates
may be added now if they pass without broad unrelated rewrites; otherwise record
their exact blockers for the next increment.

### Explicitly out of scope for this pipeline delivery

- invented privacy/legal text or policy values;
- candidate-rights decisions, automated erasure exemptions, or supplier choices;
- production deployment or changes to live Railway/AWS resources;
- secret retrieval or rotation;
- external document-provider integration;
- full router-to-service reorganization;
- composite tenant-key migrations before a data-consistency audit;
- message read-state redesign;
- mandatory MFA for non-admin roles without product approval;
- HSTS `includeSubDomains` or preload before domain-wide HTTPS verification.

## 6. Required file areas for the next increment

Expected changes are limited primarily to:

- `backend/requirements.lock` and, if needed, `backend/requirements.txt`;
- `backend/app/schemas.py`, `backend/app/security.py`, `backend/app/config.py`,
  `backend/app/database.py`, `backend/app/main.py`, and narrowly affected auth/CLI
  callers;
- a small new middleware or password-policy module where separation improves
  testability;
- `backend/tests/` and frontend account-flow tests;
- `.github/workflows/readiness.yml` and development requirement/config files;
- user/deployment documentation whose commands or stated behaviour changed.

Avoid broad formatting or unrelated cleanup. Preserve existing user changes in
the dirty worktree.

## 7. Verification contract for this pipeline delivery

The developer and tester must report exact commands and results. At minimum:

1. Backend tests against an isolated PostgreSQL database ending in `_test`.
2. New focused tests for each item in section 5.
3. Ruff lint and format checks.
4. Alembic upgrade to head plus `alembic check`.
5. Frontend unit tests, TypeScript build, and account-flow tests.
6. Dependency audit proving the `urllib3` finding is closed.
7. Existing PostgreSQL concurrency tests.
8. Existing Playwright tests if the local environment supports the isolated HTTPS
   fixture; otherwise CI evidence is required before approval.
9. Container build/smoke and vulnerability scan in CI.

Tests must not point at the normal application database. A compile, mocked test,
or source inspection is not a deployment or live-service verification.

## 8. Review checklist for the bounded increment

The reviewer should reject the increment if any of the following is true:

- an account flow bypasses the shared password policy;
- the dependency lock still resolves a vulnerable `urllib3` release;
- readiness contains a copied Alembic revision or accepts a stale/missing head;
- production error logs include secrets or provide no diagnostic category;
- request limiting consumes or corrupts valid downstream request bodies;
- rate limiting commits the business session;
- privilege, membership, deletion, or quota tests lack a cross-tenant or failure
  assertion;
- CI claims coverage, migration, container, or deployment evidence it did not
  actually produce;
- the implementation expands into policy-dependent privacy behaviour using
  invented assumptions.

## 9. Final real-data release gates

All of the following are required, regardless of how many roadmap stages have
been coded:

- Stage 0 governance artefacts are approved;
- privacy notices and indirect-candidate notification operate in production;
- lawful basis, purpose, source, and notice evidence are recorded;
- candidate rights, user offboarding, retention, and restored-data deletion have
  passed focused retests;
- sensitive-data and internal/client visibility controls are active;
- external documents use an approved private lifecycle with verified deletion;
- supplier, transfer, incident, and end-of-contract controls are complete;
- dependency, application, container, infrastructure, and secret checks pass;
- backups and both native and independent restores are proven with retained
  evidence;
- exact hosting/database region, TLS, private networking, log retention, domain,
  email delivery, bounce/complaint handling, monitoring, and scheduled jobs are
  verified live;
- the fictional-data three-role acceptance pilot passes;
- privacy, security, operational, and product owners sign the release decision.

## 10. Run-specific delivery addendum: urllib3 security finding

This addendum defines the immediate delivery slice for the current run. It is
additive to the roadmap above, but it supersedes the broader implementation
scope in section 5 for this run only. Do not implement password-policy,
readiness, middleware, transaction, privacy, infrastructure, or unrelated test
backlog work as part of this slice.

### Observed starting state

- The security assessment identified the shipped `urllib3==2.7.0` lock as
  vulnerable and recommends a compatible fixed release at or above 2.8.0.
- The current working tree already declares `urllib3>=2.8,<3` in
  `backend/requirements.txt` and pins `urllib3==2.8.0` in
  `backend/requirements.lock`. These are uncommitted working-tree changes and
  must be reviewed as the proposed fix, not assumed to be released.
- The lock pins `botocore==1.43.93`. Its installed package metadata declares
  `urllib3!=2.2.0,<3,>=1.25.4`, so `urllib3==2.8.0` satisfies the locked
  botocore constraint.
- A current local `python -m pip check` reports no broken requirements. The
  existing tester report also records a successful `pip-audit -r
  backend/requirements.lock` with no known vulnerabilities, but clean-environment
  and shipped-artifact verification remain release requirements.

### Required change

1. Retain an explicit runtime requirement that excludes affected urllib3
   releases and permits a compatible fixed release at or above 2.8.0. The
   current proposed range is `urllib3>=2.8,<3`.
2. Regenerate or validate the runtime lock through the repository's normal
   dependency-locking process and retain an exact fixed pin. The current
   proposed pin is `urllib3==2.8.0`.
3. Keep `botocore==1.43.93` unless dependency resolution or testing demonstrates
   that it must change. Do not opportunistically upgrade boto3, botocore, or
   unrelated packages.
4. Limit implementation changes to dependency metadata and any strictly
   necessary audit configuration. Do not change application behaviour for this
   finding.

### Verification and acceptance evidence

Run from a clean environment using the committed runtime lock and record the
exact commands, tool versions, and outputs:

1. Install `backend/requirements.lock` successfully with the project's
   supported Python version.
2. Run `python -m pip check` and confirm there are no broken dependency
   relationships.
3. Inspect the resolved versions and botocore metadata, confirming
   `urllib3>=2.8.0`, `urllib3<3`, and compatibility with the exact locked
   botocore version.
4. Run `pip-audit -r backend/requirements.lock`. Acceptance requires no finding
   against the locked urllib3 version. Any finding in another package must be
   reported separately with package, advisory, affected version, fixed version,
   and release impact; it must not silently expand this delivery slice.
5. Run the focused AWS integration/unit tests that exercise the boto3/botocore
   paths, followed by the normal backend test suite against its isolated test
   database. A resolver result alone does not prove runtime compatibility.
6. Build the production backend container from the updated lock and run the
   existing container vulnerability scan. Confirm the image contains the
   intended urllib3 and botocore versions and does not retain urllib3 2.7.0 in
   another Python environment or layer.

### Completion decision and remaining verification

The source-level compatibility check and existing local audit evidence indicate
that the proposed `urllib3==2.8.0` pin is a suitable fix. The finding is closed
for delivery only when the clean lock install, `pip check`, fresh `pip-audit`,
focused AWS-path tests, normal backend tests, and production-container
build/scan all pass against the same committed dependency state.

If PostgreSQL, Docker, registry access, or advisory-database access is
unavailable, record the affected command as unverified and require successful
CI evidence before approval. Do not describe the dependency fix as deployed or
live-verified until the updated production image is actually deployed and its
runtime package versions are checked in the target environment.

