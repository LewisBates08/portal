# Searchroom test assessment

## Scope and method

This review compares the implemented FastAPI routes, operational commands, React screens, browser tests, and deployment checks against the tests currently present in the repository.

Reviewed test assets:

- `backend/tests/`
- `frontend/src/*.test.tsx`
- `frontend/e2e/portal.spec.ts`
- `deploy/mail-relay/test_handler.py`
- `.github/workflows/readiness.yml`
- `scripts/load_check.py`
- `scripts/restore_check.py`

The repository contains 46 Python test functions and 11 frontend/browser test definitions. Parametrisation expands several of these into multiple cases.

This was a read-only inspection. No files were created or edited.

### Execution status

The tests could not be rerun in the present read-only environment:

- Python execution stopped because `pytest` is not installed in the active interpreter.
- Vitest attempted to create a temporary Vite configuration file under `frontend/node_modules/.vite-temp` and was denied by the read-only filesystem.
- PostgreSQL-backed backend and browser tests also require the isolated services and environment variables normally provided by CI.

Consequently, this report describes test presence and assertions in the current source. It does not claim a new passing test run.

## Executive assessment

The portal has unusually strong tests for its most important security boundaries:

- Tenant and project isolation
- Hidden-candidate visibility
- Session expiry and revocation
- CSRF and Origin enforcement
- Email verification and password reset
- MFA replay and recovery-code handling
- Invitation races
- Optimistic locking
- Idempotent message creation
- Concurrent read-marker updates
- Production configuration and trusted-host restrictions
- Mail relay authentication and failure handling

The main weakness is breadth rather than an absence of security testing. Several implemented features have only incidental coverage or no direct behavioural test. The riskiest gaps are:

1. Administrator promotion and membership assignment rules
2. Retention cleanup and backup operations
3. Project creation limits and retention prerequisites
4. Invitation administration edge cases
5. Export and permanent deletion completeness
6. Audit-log completeness
7. Successful document, update, comment, and milestone lifecycle operations
8. Frontend administrative and editing workflows

## Feature coverage matrix

### Authentication and account security

| Feature | Coverage | Evidence and limitations |
|---|---|---|
| Agency registration | Tested | Registration remains pending until email verification; no user is created prematurely. |
| Registration resend | Tested | Replacement token works, original token becomes invalid, and responses do not reveal whether an address exists. |
| Email verification | Tested | Single-use and expired-token behaviour are covered. |
| Login | Tested | Password login, session cookie issuance, MFA requirement, invalid old password after reset, and browser sign-in are covered. |
| Logout | Tested | Confirms the session becomes unusable. |
| Password reset | Tested | Covers generic responses, password replacement, token single use, and revocation of existing sessions. |
| Session idle expiry | Tested | Expired idle session is rejected. |
| Session absolute expiry | Partially tested | The test confirms ordinary requests do not extend the absolute deadline, but does not move the clock beyond the absolute deadline and assert rejection directly. |
| Session revocation on suspension | Tested | Suspended users immediately lose access. |
| CSRF protection | Tested | Bad/missing token and hostile Origin cases are covered. |
| Bearer/JWT rejection | Tested | Obsolete bearer and refresh-token interfaces are rejected. |
| Request body limit | Tested | Oversized login request returns `413`. |
| MFA enrolment | Tested | Setup, verification, recovery-code generation, and frontend acknowledgement are covered. |
| MFA replay prevention | Tested | Reuse of a TOTP code is covered. |
| Recovery-code single use | Tested | A consumed recovery code cannot be reused. |
| Password hashing details | Indirect only | Authentication exercises verification, but there is no focused password-hash upgrade or malformed-hash test. |
| Authentication rate limiting | Partial | Shared database throttling is concurrency-tested, but login/register/reset endpoint-specific thresholds and reset windows are not directly tested. |
| Login behaviour for inactive/unverified users | Partial | Suspension is covered after a session exists; focused login tests for inactive and unverified accounts are absent. |

### Invitations and user administration

| Feature | Coverage | Evidence and limitations |
|---|---|---|
| New-user client invitation | Tested | Membership is withheld until email verification and is limited to the invited project. |
| Existing-user invitation | Tested | Email matching and removed pending access are covered. |
| Invitation single use | Tested | Reuse is rejected. |
| Invitation expiry | Partially tested | Verification-token expiry is direct; invitation expiry is mainly enforced through code paths but lacks a focused expired-invitation test. |
| Invitation/removal race | Tested | Concurrent acceptance and membership removal cannot restore access. |
| Create invitation | Partial | Happy path for a client invitation is covered. Recruiter invitation, organisation mismatch, conflicting existing role, and missing project cases are not. |
| List invitations | Not directly tested | No assertions cover pagination, agency isolation, ordering, or returned status fields. |
| Revoke invitation endpoint | Not directly tested | Membership removal revokes matching pending invitations, but the dedicated `DELETE /invitations/{id}` route is not exercised. |
| List users | Partial | Access control is tested, but successful content, pagination, and agency filtering are not. |
| Suspend/reactivate account | Partial | Suspension, session revocation, foreign-user rejection, and last-admin protection are covered. Reactivation is not. |
| Promote recruiter to administrator | Not tested | No success, invalid-target, cross-agency, session-revocation, or concurrency test exists. |
| User quota | Not directly tested | The invitation acceptance quota enforced by `ensure_user_quota` has no boundary test. |

### Organisations, projects, and access control

| Feature | Coverage | Evidence and limitations |
|---|---|---|
| List client organisations | Not directly tested | Successful agency filtering and pagination are absent. |
| Create client organisation | Not directly tested | No happy path, duplicate/conflict, validation, or non-admin test. |
| List accessible projects | Partial | Used by frontend mocks and browser smoke tests; backend filtering is inferred from project-detail isolation rather than directly asserted on list results. |
| Project summary counts | Frontend only | Dashboard consumes mocked counts; backend project and unread totals are not directly checked. |
| Create project | Not directly tested | No happy path, foreign organisation, active-project quota, or missing-retention-policy test. |
| Read project | Tested | Membership, agency isolation, and removal of access are covered. |
| Update project | Tested | Client denial and concurrent optimistic-lock conflict are covered. Field persistence is only lightly checked. |
| List project members | Not directly tested | No success, pagination, or cross-agency content test. |
| Add member | Not directly tested | No role, agency, client-organisation, duplicate, or inactive-user cases. |
| Remove member | Tested | Immediate loss of access and revocation of pending grants are covered. |
| Cross-agency isolation | Tested | Foreign projects and users are hidden. |
| Nested-resource isolation | Tested | Candidate, update, and milestone IDs from another project are rejected. |
| Archived-project write protection | Partial | Message creation after archive is rejected. Other mutating resource routes are not individually checked. |
| Active project quota | Not tested | Boundary and concurrency behaviour are absent. |

### Candidate management

| Feature | Coverage | Evidence and limitations |
|---|---|---|
| Create candidate | Tested | Recruiter success and client denial are covered. |
| List candidates | Tested | Hidden candidates are excluded from client results. |
| Read candidate | Tested | Clients cannot retrieve hidden candidates directly. |
| Update candidate | Tested | Version required, successful update, stale update rejection, and client denial are covered. |
| Candidate stages | Partial | One transition to `Interviewing` is tested. All accepted stages and invalid values rely on schema validation without focused tests. |
| Candidate quota | Not tested | Maximum count and concurrent boundary behaviour are absent. |
| Candidate feedback creation | Tested | Staff and client creation paths are exercised. |
| Candidate feedback listing | Partial | Hidden-candidate denial is covered, but successful author/timestamp ordering and pagination are not. |
| Feedback idempotency | Indirect only | Generic submission handling is tested through messages, not through feedback itself. |
| CV/external link validation | Partial | Unsafe document URLs are tested, but candidate `cv_url` uses the same contract without a candidate-specific regression test. |

### Documents

| Feature | Coverage | Evidence and limitations |
|---|---|---|
| URL validation | Tested | HTTP, credential-bearing HTTPS, JavaScript, and data URLs are rejected. |
| Client write denial | Tested | Clients cannot create documents. |
| Create valid document | Not directly tested | No successful persistence/response test. |
| List documents | Frontend mock only | The React view requests an empty mocked list, but backend content and pagination are not asserted. |
| Delete document | Not directly tested | No happy path, nested-ID rejection, audit event, or client denial test. |
| Valid HTTPS link variants | Not directly tested | No coverage for query strings, fragments, international domains, or maximum lengths. |

### Updates and comments

| Feature | Coverage | Evidence and limitations |
|---|---|---|
| Create update | Partial | Used when preparing export and nested-ID tests, but the returned content, author, attachment, ordering, and idempotency are not checked. |
| List updates | Frontend mock only | No backend assertion covers newest-first ordering, comment counts, pagination, or author serialization. |
| Create comment | Partial | Cross-project post rejection is tested. A successful comment and retry deduplication are not. |
| List comments | Not directly tested | No successful ordering, author, pagination, or project-isolation assertion. |
| Update attachment URL validation | Not directly tested | The shared URL model may provide validation, but no update-specific regression exists. |

### Messaging

| Feature | Coverage | Evidence and limitations |
|---|---|---|
| Create message | Tested | Happy path, browser persistence, sequential idempotency, conflicting reuse, and concurrent idempotency are covered. |
| List messages | Tested | Pagination, cursor behaviour, delivered-message tracking, and browser display are covered. |
| Mark messages read | Tested | Cannot acknowledge an undelivered message; monotonic sequential and concurrent updates are covered. |
| Unread project count | Tested | Project-detail unread count is asserted after marker changes. |
| Global summary unread count | Not directly tested | `/projects/summary` is mocked in frontend tests but not asserted against the database. |
| Message history endpoint | Not directly tested | `/messages/history` ordering, `before`, pagination, and isolation are absent. |
| Append-only behaviour | Structurally covered | There are no edit/delete routes, but no explicit API contract test asserts that those methods return `404` or `405`. |
| Load behaviour | CI script present | The CI workflow runs a 20-user, 10,000-message latency check. This is valuable but is a threshold script rather than a pytest regression. |

### Milestones

| Feature | Coverage | Evidence and limitations |
|---|---|---|
| Create milestone | Tested incidentally | Used during permission and version tests; response details are not comprehensively checked. |
| List milestones | Browser/UI only | Browser smoke confirms a fixture is displayed. Backend date ordering and cursor boundaries are not tested. |
| Complete/reopen milestone | Tested | Backend and component tests cover both transitions. |
| Overdue display | Frontend tested | A past, incomplete milestone displays as overdue. |
| Delete milestone | Partial | Cross-project deletion is rejected, but successful deletion and client denial are not directly tested. |
| Same-date pagination | Not tested | The `(target_date, id)` ordering boundary is an important untested edge case. |

### Retention, export, deletion, and audit

| Feature | Coverage | Evidence and limitations |
|---|---|---|
| Get retention policy | Not directly tested | No admin/non-admin or agency-isolation test. |
| Set retention policy | Not directly tested | No validation, persistence, or audit assertion. |
| Archive project | Tested | Archive succeeds and at least one subsequent write is rejected. |
| Deletion preview | Partial | Candidate count and returned version/title are exercised. Full resource counts and retention-review calculation are not. |
| Export project | Partial | Candidate content appears in output. Format, all resource types, omission of internal records, agency isolation, headers, and audit entry are not asserted. |
| Permanent deletion | Partial | Requires archive, exact title, and version; project disappears afterward. Cascaded removal of every child type is not verified. |
| Audit log endpoint | Not directly tested | No ordering, pagination, agency isolation, actor/action/resource, or permission test. |
| Audit emission | Mostly unasserted | Many routes call `audit`, but tests generally do not verify that the expected event was committed exactly once. |

### Mail and operational commands

| Feature | Coverage | Evidence and limitations |
|---|---|---|
| Disabled mail behaviour | Tested | Account actions fail closed without leaving token or outbox records. |
| SMTP retry | Tested | Failure schedules a retry and later success removes the message. |
| Relay retry | Tested | Outage preserves the outbox and acceptance removes it. |
| Relay redirect refusal | Tested | Redirects are not followed. |
| Pilot recipient restriction | Tested | Disallowed recipient is rejected before queuing. |
| Relay handler authentication | Tested | Unauthenticated calls are rejected. |
| Relay sender/recipient restriction | Tested | Sender is pinned and recipient allow-list enforced. |
| Relay invalid payload | Tested | Invalid input does not call the provider. |
| Relay provider failure | Tested | Error is retryable and redacted. |
| Old outbox expiry | Not directly tested | Worker deletion after seven days is untested. |
| Retry exhaustion | Not directly tested | Eight-attempt cutoff and health failure are not tested together. |
| Parallel mail workers | Not tested | `FOR UPDATE SKIP LOCKED` is not exercised concurrently. |
| Migration advisory lock | Not tested | Lock acquisition, migration failure, and guaranteed unlock are absent. |
| Cleanup command | Not tested | Expiry boundaries and preservation of live records are absent. |
| Backup command | Not tested | Region/bucket gate, `pg_dump` arguments, database environment mapping, KMS upload settings, and failure propagation are absent. |
| Operations health check | Not tested | Healthy and exhausted-mail exit paths are absent. |
| Operator mail test | Not tested | Missing recipient, accepted delivery, and remaining-queued failure are absent. |
| Restore drill | CI script present | Six table counts and Alembic revision are checked after restoration. It does not compare every retained table or data content. |

### Production and deployment controls

| Feature | Coverage | Evidence and limitations |
|---|---|---|
| Production database launch gate | Partial | Legacy fixture accounts are rejected. Wrong/missing migration revision and connection failure need focused coverage. |
| Secure production cookie | Tested | Secure, HttpOnly, host-only name, SameSite, and no Domain attribute are checked. |
| Security headers | Tested | HSTS, CSP, cache control, and request IDs receive coverage. |
| Generic production errors | Tested | Exception details and tracebacks are hidden. |
| Validation error redaction | Tested | Submitted sensitive values are not echoed. |
| CORS absence | Tested | Hostile preflight receives no credentialed CORS headers. |
| Trusted hosts | Tested | Production host restrictions and narrowly scoped Railway readiness host are covered. |
| Production configuration validation | Tested | Insecure origins, hosts, weak secrets, and unsafe mail configuration are rejected. |
| Health live endpoint | CI smoke only | Successful container response is checked, but response body contract is not unit-tested. |
| Health ready endpoint | Partial | CI checks success and middleware tests use a synthetic unavailable response. Real database failure behaviour is not directly tested. |
| Container properties | CI tested | Runtime user, omitted tools, image build, application startup, and vulnerability scanning are checked. |
| Environment-history and secret scanning | CI tested | Dedicated scripts and Gitleaks are run. |
| AWS Terraform configuration | Not tested | No `terraform fmt`, `terraform validate`, plan assertion, policy test, or module-level test appears in CI. The AWS deployment tree should therefore be treated as unverified infrastructure code. |

### Frontend and browser behaviour

| Feature | Coverage | Evidence and limitations |
|---|---|---|
| Registration form | Tested | Verification state, absence of local-storage tokens, and password mismatch preservation are covered. |
| MFA setup screen | Tested | User cannot leave before acknowledging recovery codes. |
| Role-specific navigation | Tested | Admin, recruiter, and client controls are conditionally displayed. |
| Candidate feedback UI | Tested with mocked API | Submission call is asserted. |
| Client read-only agreement/timeline | Tested | Edit controls are hidden. |
| Message refresh/read acknowledgement | Tested with mocked API | Correct displayed message ID is acknowledged. |
| Milestone completion/reopen UI | Tested with mocked API | Both states are covered. |
| API error display | Tested | Timeline load failure is visibly reported. |
| Login and role smoke | Browser tested | Admin, recruiter, and client sign-in are exercised against the real application. |
| Message persistence after reload | Browser tested | A message survives reload. |
| Admin project creation UI | Not functionally tested | Only the presence of the “New search” control is asserted. |
| Organisation management UI | Not functionally tested | No create/list workflow test. |
| Invitation UI | Not functionally tested | No create, copy, list, revoke, accept, expired-link, or error workflow. |
| User suspension/promotion UI | Not functionally tested | No submission or confirmation tests. |
| Candidate create/edit UI | Not functionally tested | Controls are visible, but form submission and error/version-conflict handling are absent. |
| Document UI | Not functionally tested | Empty mocked load only. |
| Update/comment UI | Not functionally tested | Empty mocked load only. |
| Project overview edit UI | Not functionally tested | Client read-only state is covered, but recruiter/admin editing is not. |
| Milestone create/delete UI | Not functionally tested | Only complete/reopen is covered. |
| Password reset and email verification pages | Not directly tested | Backend behaviour is strong, but browser and component states are absent. |
| Pagination/load-more UI | Not tested | No candidate, update, message-history, invitation, user, or audit pagination workflow. |
| Responsive/mobile and accessibility behaviour | Not tested | No viewport matrix or automated accessibility assertions. |

## Highest-risk untested areas and proposed tests

### 1. Administrator promotion and membership assignment

**Risk: Critical**

These routes change privilege and project access. A defect could create an administrator in the wrong agency, assign a client to another organisation’s project, leave an old privileged session active, or create duplicate memberships.

#### Proposed backend tests

`test_promote_admin_restricts_target_and_revokes_sessions`

1. Create active, verified recruiters in the administrator’s agency and a foreign agency.
2. Create inactive, unverified, client-role, and already-admin targets.
3. Promote the valid same-agency recruiter.
4. Assert:
   - Response is `200` and role is `admin`.
   - Existing sessions for the promoted user are deleted.
   - An `administrator_promoted` audit event is recorded once.
5. Attempt promotion for every invalid target.
6. Assert `400` without revealing foreign-agency existence and no user is changed.

`test_concurrent_admin_promotion_and_last_admin_suspension_preserve_recovery`

1. Start promotion and suspension operations concurrently.
2. Assert the transaction locking always leaves at least one active administrator.
3. Assert no partially promoted user or valid privileged session remains.

`test_add_member_enforces_agency_role_and_client_organisation`

Test:

- Valid recruiter in the same agency
- Valid client belonging to the project’s client organisation
- Client belonging to a different client organisation
- Foreign-agency recruiter
- Administrator target
- Unknown user
- Duplicate addition

Assert only valid targets gain access and duplicate addition remains idempotent.

`test_members_list_is_project_and_agency_scoped`

Assert the member list contains only actual project members, paginates correctly, and a foreign project returns `404`.

### 2. Cleanup and retention operations

**Risk: Critical**

Cleanup deletes authentication, invitation, mail, submission, and audit records. A boundary error could delete live sessions or retain sensitive data beyond policy.

#### Proposed backend tests

`test_cleanup_deletes_only_records_past_each_retention_boundary`

For every cleaned model, create:

- One record one second older than the cutoff
- One record exactly at the cutoff
- One record one second newer than the cutoff

Run `cleanup()` against an isolated schema and assert:

- Expired authentication/session/rate records are deleted.
- Invitations are retained until 30 days after expiry.
- Outbox records are removed only after seven days.
- Submission records are removed only after 30 days.
- Audit events are removed only after 180 days.
- Boundary and live records remain.

`test_cleanup_is_atomic_on_database_failure`

Inject a failure during one delete statement and assert the transaction rolls back all preceding deletions.

`test_retention_policy_is_admin_only_and_agency_scoped`

Assert:

- Admin can read and update its agency’s policy.
- Non-admin receives `403`.
- Invalid values receive `422`.
- Another agency remains unchanged.
- One audit event records the successful change.

### 3. Backup and recovery operations

**Risk: Critical**

A backup command that exits successfully without a restorable encrypted artifact creates false confidence around disaster recovery.

#### Proposed tests

`test_backup_rejects_missing_non_london_or_public_configuration`

Parameterise:

- Missing bucket
- Wrong region
- Missing KMS key identifier

Assert the command exits before calling `pg_dump` or S3.

`test_backup_invokes_pg_dump_and_kms_encrypted_upload`

Mock subprocess and the S3 client. Assert:

- `pg_dump` uses custom format, no owner, and no ACL.
- Host, port, user, password, database, and SSL options map correctly to PostgreSQL environment variables.
- The upload targets the configured bucket in `eu-west-2`.
- The key is under `postgres/YYYY/MM/DD/`.
- `ServerSideEncryption` is `aws:kms`.
- The configured KMS key ID is supplied.
- Database credentials do not appear in command arguments or output.

`test_backup_propagates_dump_and_upload_failures`

Simulate both failures and assert the command does not print a success message.

`test_restore_check_compares_all_required_tables_and_rejects_revision_mismatch`

Extend the restore drill to include authentication, invitations, documents, comments, feedback, policies, submissions, and read markers, then deliberately alter one restored count and the migration revision to prove the drill fails.

### 4. Project creation, quotas, and retention prerequisites

**Risk: High**

This is the starting point for every retained search. Untested limits and prerequisite checks can prevent onboarding or allow uncontrolled data growth.

#### Proposed backend tests

`test_create_project_requires_admin_owned_client_org_and_retention_policy`

Test:

- Valid same-agency organisation
- Foreign organisation
- Missing organisation
- Non-admin caller
- Agency without an accepted retention setting

Assert only the valid request creates a project, and its agency and client organisation are correct.

`test_create_project_enforces_active_limit_but_allows_after_archive`

1. Set a small `max_projects`.
2. Create projects up to the limit.
3. Assert the next request returns `409`.
4. Archive one project.
5. Assert a new project can be created.

`test_concurrent_project_creation_cannot_exceed_limit`

Issue two creations at the final available slot and assert exactly one succeeds.

`test_candidate_limit_and_concurrent_boundary`

Repeat the same boundary and concurrent assertions for `max_candidates`.

`test_user_quota_blocks_invite_acceptance_atomically`

Fill an agency to its user quota, accept an invitation, and assert no user or membership is created. Also race two acceptances for the final slot and assert no over-allocation.

### 5. Invitations administration

**Risk: High**

Invitation links create identities and access. The happy path is covered, but the administrator-facing lifecycle and several role-binding constraints are not.

#### Proposed backend tests

`test_invitation_role_and_organisation_contract`

Cover:

- Client invitation without a project
- Client organisation that does not match the project
- Recruiter invitation with a client organisation
- Existing account with a different role
- Existing account from another agency
- Valid recruiter invitation
- Valid client invitation

Assert exact safe status codes and no invitation/outbox record on rejected requests.

`test_expired_and_revoked_invites_cannot_be_accepted`

Create expired and explicitly revoked invitations and assert both new and existing users receive a generic rejection without membership changes.

`test_invitation_list_is_agency_scoped_and_reports_state`

Create pending, used, expired, and revoked invitations in two agencies. Assert filtering, newest-first ordering, pagination, and state fields.

`test_revoke_invitation_is_scoped_idempotent_and_audited`

Assert:

- Same-agency admin can revoke.
- Foreign admin receives `404`.
- The token cannot subsequently be accepted.
- Repeated revocation has a defined result.
- An audit event is recorded only as intended.

### 6. Export and permanent deletion completeness

**Risk: High**

Export and deletion involve all project data. Partial tests can miss orphaned personal data or incomplete subject-access exports.

#### Proposed backend tests

`test_export_contains_every_exportable_resource_and_no_internal_security_records`

Create a project containing:

- Candidate and feedback
- Document
- Update and comment
- Message
- Milestone

Parse every NDJSON line and assert:

- Exactly one project record is present.
- All expected business records are present.
- Records belong only to the requested project.
- Memberships, invitation tokens, submissions, and read markers are absent.
- The content type and attachment filename are correct.
- An audit event is recorded.

`test_export_is_admin_only_and_agency_scoped`

Assert recruiter/client access is forbidden and foreign projects return `404`.

`test_purge_removes_every_project_child_without_affecting_other_projects`

Populate every model returned by `project_contents`, archive the project, obtain the latest preview, and delete it. Assert:

- Every child record is gone.
- No orphan feedback or comment remains.
- Other projects and their data are unchanged.
- The deletion audit record has the intended retention behaviour.

`test_purge_rejects_stale_preview_after_intervening_change`

Obtain a preview, mutate/archive-version the project, then submit the old version. Assert `409` and no deletion.

`test_deletion_preview_counts_and_retention_due_boundary`

Check every count plus the exact day-before, day-of, and day-after retention-review boundary.

### 7. Audit-log integrity

**Risk: High**

Audit logging is relied upon by many security-sensitive actions but is almost never asserted. A route can work while silently losing its audit trail.

#### Proposed backend tests

`test_security_sensitive_actions_emit_exact_audit_events`

Parameterise successful operations:

- Membership add/remove
- Invitation create/revoke
- User suspend/reactivate
- Admin promotion
- Retention-policy update
- Project update/archive/export/delete
- Candidate/document/milestone create/update/delete

For each, assert actor agency, actor user, action, resource, timestamp, and exactly-once insertion.

`test_failed_actions_do_not_emit_success_audit_events`

Repeat representative validation, permission, stale-version, and cross-agency failures and assert no success event is committed.

`test_audit_endpoint_is_admin_only_agency_scoped_and_newest_first`

Create events in two agencies, paginate through them, and assert isolation and stable ordering.

### 8. Collaboration-resource lifecycles

**Risk: Medium to High**

The access boundary is tested well, but several ordinary successful operations are not. These gaps are likely to produce user-visible regressions.

#### Proposed backend tests

`test_document_lifecycle`

Create a valid HTTPS document, list it, verify persistence, delete it, then verify it is absent. Assert client denial, nested-ID rejection, and audit events.

`test_update_comment_lifecycle_and_ordering`

Create multiple updates and comments with controlled timestamps. Assert:

- Updates are newest first.
- Comment count is correct.
- Comment list contains correct authors.
- Pagination does not duplicate or skip entries.
- Retry with the same idempotency key creates one record.
- Same key with different content returns `409`.

`test_feedback_list_serializes_author_and_paginates`

Create feedback from several users and assert stable ordering, author metadata, pagination, and hidden-candidate denial.

`test_milestone_ordering_same_date_pagination_and_delete`

Create more than one page of milestones, including identical target dates. Assert the `(target_date, id)` cursor produces every milestone exactly once. Then assert successful deletion, client denial, cross-project rejection, and audit emission.

`test_message_history_before_cursor`

Create messages around a chosen ID and assert `/messages/history` returns only older messages, newest first, with correct pagination and project isolation.

`test_project_summary_counts_only_accessible_unread_messages`

Create projects and messages across memberships and agencies, plus messages authored by the current user. Assert `project_count` and `unread_count` include only accessible messages from other users beyond the marker.

### 9. Frontend administrative and edit workflows

**Risk: Medium**

Backend controls reduce security impact, but frontend regressions could make implemented features unusable.

#### Proposed component tests

Add React Testing Library tests for:

- Creating a client organisation
- Creating a project and preserving form values after API failure
- Adding/removing project members
- Creating and revoking invitations
- Suspending/reactivating users
- Promoting an administrator with confirmation
- Creating/editing a candidate and handling `409` version conflict
- Adding/removing a document
- Posting an update and comment
- Editing overview/agreement details
- Creating/deleting a milestone
- Password-reset request and completion states
- Email-verification success, expiry, and reused-link states
- Pagination/load-more with second-page API results

Each test should assert the exact API path, method, payload, visible loading state, success refresh, and visible error state.

#### Proposed browser tests

Add focused Playwright workflows against the real FastAPI/PostgreSQL application:

1. Admin creates an organisation, project, and invitation.
2. Invited client verifies, signs in, and sees only the invited project.
3. Recruiter creates and shares a candidate.
4. Client sees the shared candidate but not a hidden candidate and submits feedback.
5. Recruiter adds a document, update, comment, and milestone.
6. Client sees those resources but cannot find editing controls.
7. Admin removes client access; the client’s next request loses project access.
8. Admin archives and deletes a fully populated project after export.

These tests should use isolated fixtures per test rather than depending on a shared, order-sensitive browser state.

### 10. Operational health and migration gating

**Risk: Medium**

These commands determine whether production starts and whether operators receive truthful health information.

#### Proposed tests

`test_migrate_holds_and_releases_advisory_lock`

Mock the Alembic upgrade and database connection. Assert the lock is acquired before migration and released in `finally`, including when migration fails.

`test_check_reports_healthy_queue_and_fails_on_exhausted_mail`

Assert success with zero exhausted messages and `SystemExit` with the count when attempts reach eight.

`test_mail_worker_discards_expired_and_stops_after_retry_limit`

Create old, current, seven-attempt, and eight-attempt rows. Assert only eligible rows are delivered and expired rows are deleted.

`test_concurrent_mail_workers_deliver_each_outbox_record_once`

Run two worker transactions against PostgreSQL and assert `SKIP LOCKED` prevents duplicate provider calls.

`test_ready_endpoint_reflects_real_database_failure`

Override the database dependency to raise an operational exception. Assert `503`, a generic body, no sensitive connection details, and appropriate cache headers.

`test_production_startup_requires_current_alembic_revision`

Use isolated schemas with missing, stale, and current migration revisions. Assert only the current schema starts.

## Recommended implementation order

1. Privilege promotion and membership tests
2. Cleanup and backup tests
3. Project, candidate, and user quota tests
4. Invitation lifecycle tests
5. Export/deletion completeness tests
6. Audit-log assertions
7. Resource lifecycle and pagination tests
8. Frontend administrative/component tests
9. Expanded browser workflows
10. Migration and operational health tests
11. Terraform formatting, validation, and policy checks

## Suggested test-suite structure

```text
backend/tests/
  test_admin_access.py
  test_admin_users.py
  test_admin_invitations.py
  test_admin_retention.py
  test_project_lifecycle.py
  test_collaboration_resources.py
  test_export_deletion.py
  test_audit.py
  test_operations_cleanup.py
  test_operations_backup.py
  test_operations_health.py
  test_migrations.py

frontend/src/
  admin.test.tsx
  candidate-editor.test.tsx
  collaboration.test.tsx
  account-actions.test.tsx
  pagination.test.tsx

frontend/e2e/
  onboarding.spec.ts
  collaboration.spec.ts
  access-revocation.spec.ts
  retention.spec.ts
```

## Quality gates to add

- Collect backend coverage in CI and publish the report.
- Set an initial branch-coverage baseline rather than imposing an arbitrary high target immediately.
- Require direct coverage for every mutating API route.
- Require at least one permission-denied and one cross-tenant case for every administrative route.
- Require every destructive operation to test its recovery gate and complete affected-record set.
- Run PostgreSQL tests against the same major version used in production.
- Keep browser fixtures isolated and independent of test execution order.
- Add `terraform fmt -check` and `terraform validate` before treating the AWS deployment code as releasable.
- Treat mocked frontend tests as component evidence, not proof that the backend integration works.
- Continue keeping load and restore drills separate from ordinary unit/integration tests, while retaining their CI artifacts as operational evidence.

## Overall verdict

The current suite provides a solid security foundation and covers the portal’s core authentication and isolation contract better than its raw number of tests suggests. It is not yet comprehensive enough to validate the whole application.

The most important missing confidence is around actions that grant privilege, assign access, delete retained data, or claim recoverability. Those should be addressed before expanding lower-risk presentation tests. Afterward, successful resource lifecycles and real browser administration workflows should be added to close the gap between secure backend primitives and a reliably usable portal.

