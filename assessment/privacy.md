# Privacy Review: Searchroom Client Portal

**Review date:** 27 October 2026  
**Review type:** Read-only static code and configuration review  
**Intended report path:** `assements/privacy_review.md`  
**Legal framework:** UK GDPR, Data Protection Act 2018, and relevant amendments made by the Data (Use and Access) Act 2025  
**Overall status:** **Not ready to be represented as Data Protection Act compliant**

## 1. Executive summary

Searchroom has a comparatively strong technical security foundation for a small recruitment portal. It implements project-scoped access control, explicit candidate sharing, secure cookie sessions, CSRF protection, administrator MFA, encrypted email content, restricted production logging, encrypted backups, audit records, and controlled whole-project deletion.

However, the codebase alone does not demonstrate compliance with the Data Protection Act 2018 and UK GDPR. Several essential privacy controls are absent or incomplete:

1. There is no privacy notice or evidence that candidates are informed when their information is collected indirectly.
2. Lawful bases, processing purposes, data sources, recipients, special-category conditions and criminal-offence conditions are not recorded.
3. There is no candidate-level deletion, export or rights-management workflow.
4. The retention setting only indicates when an archived project is due for review. It does not automatically flag administrators or delete/anonymise expired information.
5. User accounts can be suspended but cannot be deleted or anonymised.
6. Deleting a document or project removes only externally stored file links. It does not delete the corresponding CV or document from its external provider.
7. Free-text fields and linked CVs can contain special-category and criminal-offence data without restrictions, warnings, classification or additional safeguards.
8. The controller/processor roles, Article 28 agreements, subprocessors, international transfers and external document-provider arrangements have not been established in the repository.
9. The project export is an administrative project export, not a candidate or user subject access response.
10. The repository explicitly says that the cloud environment and important production controls remain unverified.

These issues mean the platform should not receive real candidate information until the critical actions in section 10 have been completed.

## 2. Scope and limitations

This review covered:

- SQLAlchemy database models and migrations;
- authentication, MFA, session and security controls;
- administrator and project API routes;
- frontend and API data contracts;
- retention cleanup and project-deletion logic;
- email delivery and operational logging;
- deployment, backup and infrastructure definitions;
- relevant tests and project documentation.

This was a read-only review. No files were edited and no tests, database operations, deployments or live cloud checks were performed. Existing test files were inspected as evidence of intended behaviour, but their presence is not evidence that the current production environment has passed those tests.

This is a technical compliance assessment, not formal legal advice. Organisational compliance also requires policies, contracts, staff procedures, records of processing and evidence of actual operation.

## 3. Roles and responsibilities

The expected privacy roles should be confirmed in contracts:

- **Recruitment agency:** likely controller for its recruitment sourcing, assessment and candidate-sharing activities.
- **Client company:** may be an independent controller or joint controller for candidate assessment and hiring decisions. This depends on who determines the purposes and means of processing.
- **Searchroom operator:** likely processor when hosting and operating the portal on an agency’s instructions. It may be a controller for limited purposes such as its own security, account administration or legal obligations.
- **Hosting, database, email, backup and external-document providers:** likely subprocessors or separate processors, depending on their services and terms.

The repository does not establish these roles or contain the required contractual framework. Whenever a controller uses a processor, the written contract must cover documented instructions, confidentiality, security, subprocessors, rights assistance, breach/DPIA assistance, deletion or return, and audit rights. See the [ICO’s Article 28 contract guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/accountability-and-governance/contracts-and-liabilities-between-controllers-and-processors-multi/what-needs-to-be-included-in-the-contract).

## 4. Personal data inventory

| Data subject/category | Data stored | Location | Sensitivity and observations |
|---|---|---|---|
| Candidates | Name, current role, current company, profile summary, CV URL, recruitment stage, client-visibility status | `Candidate` | Directly identifies candidates and records employment-seeking activity. A summary or linked CV may include contact, education, employment, compensation, immigration, disability, health, diversity, criminal-record or other sensitive information. |
| Candidate feedback | Free-text feedback, author identity and timestamp | `Feedback` | May contain opinions, interview assessments, inferred characteristics and potentially special-category data. |
| Portal users | Name, email, agency, client organisation, role, active/verified status and MFA status | `User` | Includes staff and client contact information. |
| Authentication data | Password hash, encrypted TOTP secret, hashed recovery codes, MFA replay-control value | `User` | Security credentials. Passwords are hashed; MFA secrets are reversibly encrypted. |
| Session data | Hashed session token, user ID, expiry times, MFA-completion status and delivered-message cursors | `WebSession` and legacy `AuthSession` | Online identifiers and account activity metadata. |
| Registration/reset data | Email address, action type, expiry and JSON payload | `EmailAction` | A pending registration payload can contain name, agency name and a password hash. |
| Invitations | Invitee email, role, agency, client organisation, project, expiry, used/revoked status | `Invitation` | Reveals professional relationships and project access. |
| Email delivery data | Recipient and encrypted account-email content, retry state and creation time | `MailOutbox` | Email content can contain single-use account links. |
| Client organisations | Organisation name and agency association | `ClientOrg` | Usually corporate data, but sole-trader or named-company data can identify a person. |
| Projects/searches | Title, description, ideal profile, agreement terms, client organisation, dates and archive timestamp | `Project` | Free text may identify candidates, client contacts, hiring managers or other individuals. |
| Memberships | User-to-project assignments | `Membership` | Shows which people work on or can access a search. |
| Documents | Document title and external HTTPS URL | `Document` | The database stores a link, not the file. Linked files may contain extensive personal data. |
| Updates/comments | Free-text post/comment, author identity, attachment URL and timestamps | `Post`, `Comment` | May contain candidate details, internal opinions and linked files. |
| Messages | Free-text message, author and timestamp | `Message` | Potentially unstructured candidate and client data. |
| Read state | User, project and last-read message ID | `ReadMarker` | User activity metadata. |
| Milestones | Title, description, target date and completion status | `Milestone` | Free text can contain personal data. |
| Audit data | Agency, actor ID, action, resource identifier and timestamp | `AuditEvent` | Records user actions but generally not before-and-after values or reads of candidate records. |
| Rate limiting | Keyed HMAC value, count and expiry | `RateBucket` | Derived from IP/account identifiers. HMAC reduces direct identifiability but does not necessarily make it anonymous. |
| Submission deduplication | User, project, fingerprint, JSON result and timestamp | `Submission` | The stored JSON result may duplicate personal data returned by write operations. |
| Operational logs | Request ID, method, route template, status, duration | Application logs | Designed to omit bodies, query strings, cookies and email links. Database/provider logs may contain further metadata and require separate review. |
| Backups | Complete database dump | Native database backups and S3 exports | Contains all database-held categories present at backup time. |

The application does not intentionally define fields for health, ethnicity, religion, trade-union membership, sexual orientation, biometric identifiers or criminal records. Nevertheless, the 10,000-character summary, feedback, project, message, post and comment fields, plus linked CVs, allow all of these to be entered. Data protection classification must therefore be based on actual content, not only column names.

## 5. Who can access the information

### Application users

| Role | Access |
|---|---|
| Agency administrator | Can access every project belonging to the administrator’s agency, regardless of project membership. Can list agency users and invitations, configure retention, manage memberships, export projects, inspect deletion counts, archive and delete projects, and inspect agency audit events. |
| Recruiter | Can access only projects for which an explicit membership exists. Within those projects, a recruiter can see all candidates, including candidates not shared with the client, and associated feedback. Recruiters can edit candidate/search data and manage document links and milestones. |
| Client user | Can access only explicitly assigned projects for the matching client organisation. Users in the same client organisation do not automatically receive access. A client sees only candidates marked `client_visible`, plus those candidates’ feedback. |
| Client user, general project content | Once assigned to a project, a client can see project documents, updates, comments, messages and milestones. These resources do not have an equivalent per-item “client visible” flag. Agency users must therefore avoid placing internal-only or unapproved candidate information in them. |
| Suspended user | Cannot authenticate, and suspension revokes current sessions. The account and historical authored content remain stored. |

The core project checks correctly require the project to belong to the same agency and require membership for non-administrators. Nested candidate checks verify the real project relationship, and hidden candidates return a not-found response to client users.

### Infrastructure and third parties

Depending on the deployed environment, access may also be available to:

- database owners, maintainers and hosting-provider personnel;
- application operators with production database or backup credentials;
- AWS personnel or approved support subprocessors for SES, S3, KMS and related infrastructure;
- the external provider hosting each CV, attachment or project document;
- client and agency personnel receiving exported NDJSON files;
- incident responders and authorised support personnel.

The deployment documentation requires UK regions and private database networking, but it correctly notes that selecting a UK region does not prove that all support or processing remains in the UK. Provider terms, subprocessors, remote support access and international transfer mechanisms still require review.

## 6. Retention periods

| Category | Implemented retention |
|---|---|
| Authenticated web session | Seven-day absolute limit and configurable idle timeout, documented as 30 minutes. |
| Pre-login session | 15 minutes. |
| Password reset action | 30 minutes. |
| Registration/verification action | 24 hours. |
| Invitation | Valid for seven days; cleanup deletes expired invitation rows only after an additional 30 days. |
| Rate-limit, session and email-action rows | Deleted by the cleanup job after expiry. |
| Email outbox | Deleted following successful delivery; failed/undelivered rows are deleted after seven days. |
| Submission deduplication | 30 days. |
| Audit event | 180 days. |
| Application logs | Documentation specifies 30 days, but the AWS Terraform log groups use 14 days. The active deployment must establish which value applies. |
| Native database backup | Seven days in the AWS RDS definition and deployment documentation. |
| Independent S3 database dump | 30-day lifecycle. |
| Project/candidate/collaboration data | No fixed automatic deletion. An agency selects 1 to 3,650 retention days. The period is calculated from `archived_at` and only sets `review_due` in a deletion preview. |
| User accounts and client organisations | No retention period or automated deletion. |
| External CVs/documents | Controlled by the external provider, not by this application. No retention enforcement is implemented. |
| Final database snapshots | No explicit expiry is shown. `skip_final_snapshot = false` can create a final snapshot on database destruction that persists until separately deleted. |

The project retention control is better described as a **review interval**, not an enforced retention period. Nothing in the cleanup operation finds or deletes projects that have passed the interval, and there is no evidence of notifications or a scheduled review report.

UK GDPR does not prescribe one universal candidate retention period. The controller must determine and document periods based on each purpose and relevant recruitment-law obligations. A single agency-wide value for every project record is unlikely to be sufficient because candidate files, messages, audit evidence, contracts, account data and security records serve different purposes.

The ICO says organisations must justify retention, establish standard periods where possible, review data regularly, and erase or anonymise information that is no longer needed. See the [ICO’s storage-limitation guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-protection-principles/a-guide-to-the-data-protection-principles/storage-limitation/).

## 7. Can personal data be deleted?

### Supported deletion

- An agency administrator can archive a project and permanently purge all project-scoped candidates, feedback, documents, posts, comments, messages, milestones, memberships, invitations, read markers and submission records.
- Purging requires the current project version and exact title, reducing accidental deletion risk.
- Recruiters can delete individual document-link records and milestones.
- Expired operational records are deleted by the scheduled cleanup command.
- Removing a membership revokes project access and pending invitations associated with that user and project.

### Unsupported or incomplete deletion

- There is no individual candidate deletion endpoint.
- There is no candidate anonymisation function.
- There is no candidate-wide search covering every project and free-text mention.
- Feedback, messages, posts and comments cannot be individually deleted through the API.
- User accounts cannot be deleted or anonymised; suspension only disables access.
- Client organisations and agencies cannot be deleted through the API.
- Project deletion retains the project-deletion audit event, including the acting user ID and deleted project ID. This may be justified for accountability, but its necessity and 180-day retention should be documented.
- Deleting a database link does not delete the corresponding external CV, attachment or document.
- Live deletion does not immediately remove data from seven-day native backups or 30-day database exports.
- Final snapshots may outlive those periods.
- Restoring an old backup can resurrect erased data unless deletions are reapplied. The deployment instructions identify this issue, but no persistent deletion ledger or automated restore reconciliation is implemented.

The ICO accepts that backup data may remain until it is overwritten if it is put beyond use, not restored into normal processing, and the individual is told what will happen. See the [ICO’s erasure and backups guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/individual-rights/right-to-erasure/).

## 8. Positive privacy and security controls

The following controls materially improve compliance readiness:

- server-side, project-scoped authorisation;
- explicit candidate sharing with client users;
- no automatic access based only on organisation membership or email domain;
- generic not-found responses for inaccessible projects and candidates;
- secure, HttpOnly, host-only, SameSite cookies in production;
- exact-origin and CSRF validation for state-changing requests;
- seven-day absolute and idle session expiry;
- immediate session revocation on logout, password reset and suspension;
- mandatory TOTP MFA for agency administrators;
- Argon2 password hashing;
- hashed session, action, invitation and recovery tokens;
- encrypted TOTP secrets and encrypted queued email bodies;
- production TLS validation for database connections;
- same-origin frontend/API design and restrictive security headers;
- application logging that deliberately excludes request bodies, cookies, query strings and token-bearing email links;
- private database networking in the AWS design;
- encrypted database storage and SSE-KMS backup exports;
- backup lifecycle rules;
- project deletion preview and confirmation;
- audit events for important administrative and mutation operations;
- no file uploads into the application itself, reducing direct file-storage exposure.

These controls support, but do not by themselves prove, compliance with the security principle. The ICO requires security proportionate to risk and treats encryption, resilience, restoration and regular effectiveness testing as relevant measures. See the [ICO’s encryption and security guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/security/encryption/encryption-and-data-protection/).

## 9. Compliance findings

### Critical

#### P-01: No demonstrated transparency to candidates

No candidate privacy notice, privacy route or just-in-time notice was found. Candidates may be sourced indirectly and entered into the portal without an account, so account-registration text cannot satisfy their transparency rights.

The notice must identify the controller, purposes, lawful bases, legitimate interests where applicable, data categories, sources, recipients, retention, rights, ICO complaint route, transfers and any automated decision-making. Where data is obtained indirectly, the notice normally needs to be provided within the applicable Article 14 timeframe, subject to documented exceptions.

ICO recruitment guidance states that privacy information should explain purposes, lawful basis, sensitive-data conditions, retention, sharing, rights and the source of indirectly obtained information. See [ICO employment records guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/employment/employment-practices-and-data-protection-keeping-employment-records/collecting-and-keeping-employment-records/).

#### P-02: No lawful-basis or purpose governance

The application accepts candidate data without recording or enforcing:

- the recruitment purpose;
- source and collection date;
- lawful basis;
- legitimate-interests assessment reference;
- whether the candidate has been informed;
- special-category Article 9 condition;
- criminal-offence Article 10/DPA 2018 Schedule 1 condition;
- consent and withdrawal where consent is genuinely appropriate.

This is principally an organisational issue, but the system provides no fields or workflow to support it.

#### P-03: Candidate rights cannot be fulfilled reliably

The only export is a whole-project administrator export. There is no candidate-centric search/export across projects, external documents, free text, backups or audit material. There is likewise no candidate-level erasure, restriction, objection or correction workflow and no request log or deadline tracking.

A subject access request requires a copy of the individual’s personal information plus supplementary information, generally within one month. See the [ICO right-of-access guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/right-of-access/what-is-the-right-of-access/).

#### P-04: Retention is not enforced

The agency retention value only makes `review_due` true after a project has been archived long enough. Active projects can remain open indefinitely, expired projects are not automatically surfaced, and project content is not erased or anonymised automatically.

A manual review model can be lawful, but only if a documented and demonstrably operated process ensures that reviews happen. No such evidence is present.

### High

#### P-05: Special-category and criminal-offence information is uncontrolled

Candidate summaries, feedback, messages and linked CVs may contain health, disability, ethnicity, religion, political opinion, sexual orientation, union membership or criminal-record data. The platform neither prohibits these entries nor applies heightened access, classification, retention or audit controls.

Until appropriate conditions and safeguards are documented, the service should expressly prohibit unnecessary special-category and criminal-offence data.

#### P-06: External document deletion and access are outside portal control

Only URLs are stored. Portal RBAC protects discovery of those URLs, but possession of a URL may bypass the portal if the external provider uses public or long-lived links. Removing the link does not remove the document.

The controller must approve the document provider, ensure appropriate access expiry and logging, establish an Article 28 agreement where required, and coordinate deletion at the source.

#### P-07: User erasure and offboarding are incomplete

Suspended users retain their identity, credentials, memberships unless separately removed, and historical authored content. There is no account deletion or pseudonymisation process. Retaining authorship may be necessary for business records, but indefinite retention of credentials and unnecessary profile data is not justified by the code.

#### P-08: Accountability documents and supplier controls are missing

The repository does not demonstrate:

- a record of processing activities;
- controller/processor and joint-controller determinations;
- Article 28 data-processing agreements;
- a subprocessor inventory;
- international-transfer assessments and safeguards;
- an approved retention schedule;
- legitimate-interests assessments;
- an appropriate-policy document for relevant DPA 2018 Schedule 1 processing;
- staff confidentiality/training controls;
- a breach-response policy;
- a documented DPIA decision.

### Medium

#### P-09: Broad project collaboration surfaces can expose hidden candidates

Candidate visibility is enforced on candidate and feedback routes. Documents, posts, comments and messages are visible to every assigned project member, including client users. Internal users can therefore accidentally disclose a hidden candidate through ordinary free text or an attachment link.

Introduce clear internal/client classifications or separate client-visible and internal channels.

#### P-10: Audit coverage is incomplete for privacy investigations

Important mutations and exports are audited, but routine reads of candidate records, documents and messages are not. Audit events also contain limited context. This may hinder investigations into suspected inappropriate access.

A proportionate solution should record access to particularly sensitive exports and external documents without creating excessive surveillance data.

#### P-11: Retention documentation conflicts

Deployment documentation says operational logs should be retained for 30 days, while the AWS Terraform configuration sets 14 days. The active policy and deployed configuration must agree.

#### P-12: Public self-registration increases governance risk

Public registration can create a new isolated agency after email verification. Although this does not grant access to an existing agency, it allows unapproved organisations to create a tenant capable of storing recruitment data. Production use should require contractual onboarding or explicit tenant approval.

#### P-13: Deletion does not cover restored backups automatically

Documentation instructs operators to reapply deletions after a restore, but there is no technical deletion ledger. This creates a foreseeable risk that erased information returns to active use.

## 10. Required remediation

### Before processing real candidate data

1. **Publish and operationalise privacy information**
   - Provide candidate, client-user and agency-user privacy notices.
   - Add notice links at registration and within the authenticated application.
   - Establish an Article 14 notification workflow for indirectly sourced candidates.
   - Record the notice version and date supplied.

2. **Document the processing**
   - Complete a data map and record of processing activities.
   - Determine controller, joint-controller and processor roles.
   - Document purposes and lawful bases per processing activity.
   - Complete legitimate-interests assessments where legitimate interests are used.
   - Define conditions and safeguards for special-category or criminal-offence data.

3. **Create a category-specific retention schedule**
   - Use separate justified periods for candidate profiles, unsuccessful recruitment records, successful placements, communications, contractual records, accounts, audit data, logs and backups.
   - Treat the existing setting as a review period unless automatic deletion is introduced.
   - Generate scheduled overdue-retention reports and require recorded review outcomes.
   - Prevent projects from remaining active solely to avoid the retention clock.

4. **Implement individual-rights procedures**
   - Candidate search across projects and structured/free-text records.
   - Candidate-level export.
   - Candidate correction, restriction and objection flags.
   - Candidate-level deletion or anonymisation with documented exemptions.
   - User account deletion or pseudonymisation.
   - Request intake, identity verification, deadline and decision records.
   - Recipient-notification workflow following correction, restriction or erasure.

5. **Control external documents**
   - Use an approved private document provider with authenticated, expiring access.
   - Store a provider object identifier rather than relying only on an arbitrary URL.
   - Delete or restrict the source object when the portal record is erased.
   - Include external objects in exports, rights searches and retention reviews.
   - Ensure client users cannot reuse long-lived links after project access is removed.

6. **Complete supplier and transfer governance**
   - Put compliant Article 28 contracts in place.
   - Document subprocessors, support locations and remote-access arrangements.
   - Record UK adequacy or transfer safeguards where processing can occur overseas.
   - Establish end-of-contract return/deletion and verification procedures.

7. **Complete a DPIA screening**
   - Recruitment profiling, confidential assessments, sharing between agency and clients, large free-text fields and potentially sensitive CV information create meaningful risks.
   - Complete a full DPIA if the screening shows likely high risk, and resolve high residual risks before launch.

8. **Verify the real production environment**
   - Confirm the exact deployment, region, TLS, private database networking, credentials, log retention, backup lifecycle, restoration controls and external document provider.
   - Exercise all roles against the real HTTPS service with fictional information.
   - Verify deletion in the live database, exports, backups and document provider.
   - Do not treat Terraform or documentation as proof that controls are deployed.

### Subsequent improvements

- Add internal-only and client-visible classifications to documents, posts and messages.
- Require administrator MFA immediately and consider MFA for recruiters and client users.
- Add periodic access recertification for project memberships.
- Add data-quality/source fields and candidate last-verified dates.
- Add warnings and validation discouraging unnecessary sensitive information.
- Produce a privacy-safe activity report for suspicious access and bulk exports.
- Reconcile the 14-day and 30-day log-retention settings.
- Add a deletion ledger used during backup restoration.
- Restrict tenant creation to contractually approved agencies.
- Test incident response and retain a breach register. Certain personal data breaches must be reported to the ICO within 72 hours where required; see the [ICO breach guide](https://ico.org.uk/for-organisations/report-a-breach/personal-data-breach/personal-data-breaches-a-guide/).

## 11. Compliance conclusion

The application has credible security and tenant-isolation controls, and its whole-project purge is a useful foundation. Nevertheless, it cannot currently demonstrate compliance with the Data Protection Act 2018 and UK GDPR.

The principal blockers are transparency, lawful-basis governance, candidate rights, enforceable retention, sensitive-data controls, external-document lifecycle management, supplier agreements and unverified production operation.

**Release decision:** Do not use the platform for real candidate data until findings P-01 through P-08 are resolved and evidenced. A restricted acceptance test using fictional data is appropriate. After remediation, conduct a focused privacy retest covering candidate notification, subject access, rectification, restriction, erasure, external-document deletion, backup behaviour, access recertification and production supplier arrangements.

