# Deploy Searchroom to a UK pilot

The repository contains deployment code, not a provisioned cloud environment. Complete the account-specific steps below and pass staging checks before adding real candidate data. One app instance and a database without standby capacity permit maintenance/recovery outages.

## Infrastructure and configuration

1. Create a managed PostgreSQL 17 cluster in London (`lon1`) and an App Platform app in London (`lon`) in the same VPC. Configure trusted database sources for the app and maintenance jobs only. Do not use App Platform's development database.
2. Create a database owner/migrator and a separate runtime login. Use interactive password entry or the provider's secret controls; never put passwords in shell history. Migrate as the owner, then grant the runtime role `CONNECT`, schema `USAGE`, table `SELECT/INSERT/UPDATE/DELETE`, and sequence `USAGE/SELECT`. Apply equivalent default privileges for future owner-created tables. Runtime must not own tables or have `CREATE`, `CREATEDB`, `CREATEROLE` or superuser privileges. Revoke runtime UPDATE/DELETE on `audit_events`; use a separate maintenance credential for retention cleanup. Keep migration credentials exclusive to the migration job.
3. Build the root `Dockerfile` in CI for Linux. This builds React and serves it from FastAPI on the same origin. Publish the image only after readiness checks pass, then reference its immutable digest in `deploy/app.yaml`. Registry credentials are runtime platform secrets. Do not deploy an untested rebuild.
4. Supply settings from `deploy/production.env.example` through App Platform's encrypted runtime configuration. Generate independent signing and Fernet encryption keys. `JWT_SECRET` is retained as a compatible environment name but now signs CSRF tokens; it does not enable JWT authentication. `DATABASE_CA_CERT` contains the public database CA; bootstrap materializes it at `/tmp/postgres-ca.crt`. Use `sslmode=verify-full` and that CA path in each database URL.
5. Connect the configured `portal.radiumsearch.com` domain, with `TRUSTED_HOSTS=portal.radiumsearch.com`, `FRONTEND_URL=https://portal.radiumsearch.com`, and your VPC ID to the app spec/platform settings. Configure managed HTTPS redirection. Set trusted proxy addresses using `FORWARDED_ALLOW_IPS` after inspecting the platform ingress; never trust arbitrary forwarded headers when direct ingress is possible. Confirm real remote-IP throttling with two external clients. Health probes must send an allowed Host header.
6. Start with the 2 GB app instance, one Uvicorn worker, five connections and zero overflow. Budget five connections for each overlapping deployment instance plus two per maintenance/email job; retain at least 25% of database connections for recovery/administration. Set `POOL_SIZE=2` for jobs. Increase database size/connection capacity before exceeding this budget; do not simply add workers.
7. Keep public static assets cacheable and private HTML/API responses uncached. CSP and other security headers are emitted by the production app. Do not configure a CDN cache for authenticated responses.

Official references: [VPC networking](https://docs.digitalocean.com/products/app-platform/how-to/enable-vpc/), [App spec](https://docs.digitalocean.com/products/app-platform/reference/app-spec/), [deployment jobs](https://docs.digitalocean.com/products/app-platform/how-to/manage-jobs/).

## Account email and backup storage

Configure an Amazon SES verified sending identity in `eu-west-2`, enable DKIM and SPF/DMARC, and obtain production sending access. Supply regional SMTP credentials, port 587 and `MAIL_FROM`. Configure delivery/bounce/complaint notifications and suppression handling in SES; route operational alerts to the responsible operator. Never add candidate details to account emails.

Account emails are encrypted in the database outbox. The small email worker claims locked rows, sends over STARTTLS, deletes accepted messages and retries failures with backoff, up to eight attempts. SMTP acceptance is not proof of delivery. At-least-once delivery can produce a duplicate email if the worker fails after SMTP accepts it; the link remains single-use. The operations check exits non-zero when attempts are exhausted. Investigate and redeliver only after resolving the cause. Scheduled App Platform jobs have a minimum 15-minute interval, so the email worker runs every ten seconds to avoid making users wait fifteen minutes for verification/reset links.

Create a private S3 bucket in London (`eu-west-2`) with public access blocked, default SSE-KMS encryption, and a 30-day expiration policy. If versioning is enabled, expire noncurrent versions and delete markers as well. Give the backup job write-only access to its prefix and KMS encryption permission; keep restore/read credentials separate. Store the KMS identifier and AWS credentials only on the backup job. The app has no upload feature.

Verify native database backup, bucket, encryption-key and retained-log locations. Record provider agreements, subprocessors and international support/processing before real data. UK hosting/storage is the agreed constraint; region selection alone does not establish all processing residency.

## Container image selection

Use the `runtime` image for web, email, migrations and cleanup; use the separate `operations` image for database backups and restore tools. Both must pass the image security gate. The older App Platform template requires its backup image reference to be set to the operations digest. See [CONTAINER_RELEASE.md](CONTAINER_RELEASE.md) for build targets and release evidence.

## Release and migration

The first readiness migration is an authentication cutover: existing JWT sessions are revoked, existing users must verify their addresses, and admins must enrol MFA. Existing agencies must set retention settings. Stop the legacy app before this migration and deploy the new frontend/backend together. No automatic schema downgrade is supplied because reactivating legacy authentication would reintroduce the old risks.

The migration job uses a PostgreSQL advisory lock and runs before app instances start. API readiness requires the expected schema revision. Back up before migration. Use additive schema changes compatible with the previous readiness image for subsequent releases; only roll back to a tested image that supports the current schema. For a failed first cutover, keep maintenance mode active and fix forward or restore an isolated pre-cutover copy while reviewing its security implications. Do not expose the old JWT app to real clients as a rollback shortcut.

Create the first administrator with `python -m app.cli create-admin`; the command queues verification mail. Public signup also creates a new isolated agency after verification. Neither names nor email domains grant existing-agency access. The production backend no longer includes `seed-demo` or default passwords. Browser fixtures live outside the runtime image and refuse non-test databases. Production startup refuses legacy demo addresses in the target database; migrate only reviewed real data into a clean production database.

## Monitoring and incident handling

- `/api/v1/health/live` checks the process; `/api/v1/health/ready` checks database access and schema. Only expose their minimal status responses.
- Structured logs include generated request IDs, route templates, status and latency. Bodies, query strings, cookies and email links are excluded. Retain operational logs for 30 days in a reviewed UK destination; confirm the provider's own diagnostic-log retention separately.
- Configure alerts for failed readiness/deployments, 5xx above 1% for five minutes, p95 read latency above 500 ms, memory/CPU above 80%, database connection use above 75%, storage above 80%, failed jobs, an email queue older than five minutes, and backup age above 26 hours. Validate alert delivery in staging. App-level resource/deploy alerts are in the template; configure database, log-derived and backup-age alerts in the platform/monitoring account.
- Check `python -m app.operations check`; use `cleanup` daily. Audit metadata expires after 180 days. Session/action/rate rows expire; submissions are deduplicated for 30 days. Project content is deleted only after an administrator previews counts and confirms the exact archived project title/version.
- For compromise: suspend the account immediately, revoke related invitations/memberships, preserve restricted incident evidence, rotate affected credentials and assess exposed data. Session rows are checked on each request; cookie or signing-key changes alone are not a replacement for revoking sessions.
- Signing-key rotation invalidates CSRF values; clear sessions for a forced global sign-out. Encryption-key rotation requires decrypting/re-encrypting MFA secrets and pending outbox contents before retiring the old key; retain access to the backup encryption keys for the backup retention period.

## Recovery drill

Native backups provide point-in-time recovery; independent exports protect against deletion of the original cluster and its provider-held backups. Native backup retention is seven days and deleting the cluster also deletes those backups. [Provider recovery documentation](https://docs.digitalocean.com/products/databases/postgresql/how-to/restore-from-backups/).

At least monthly, and before first launch:

1. Restore a native backup or independent encrypted dump into a new UK database using a separate recovery credential. Never restore over the active database during a drill.
2. Verify schema revision, counts, project permissions, hidden candidates and sample collaboration contents. Invalidate restored sessions and queued email actions before enabling user traffic; a restore must not resurrect access or send old mail.
3. Use the tested application image against the restored database, test all three roles, then switch the database runtime setting during a controlled cutover.
4. Record source timestamp, lost-data window and elapsed recovery time. Target recovery within four hours. Independent daily exports alone can lose up to 24 hours; measure native PITR's achievable recovery point rather than promising zero loss.
5. Delete the isolated drill database after verification and record the result without candidate content.

`scripts/restore_check.py` automates the local isolated-database dump/restore and row-count check; it does not validate cloud IAM, KMS or provider PITR. Deleted content remains in backups until backup expiration; document this and reapply deletion/offboarding records after restoring.

## Launch gates that require your cloud account

Supply domain, region/VPC, managed database, separate credentials, SES sender and private backup bucket. Run the full CI suite, verify the production image, TLS/cookies/security headers, database CA verification, proxy handling, email delivery/bounces, backup upload/decryption, real alerts, native restore and previous-image rollback in staging. Obtain the agency's retention policy and document-provider access arrangements. These gates are not satisfied merely by generating configuration files or passing local tests.

## Production security checkpoints

See [the checkpoint audit](DEPLOYMENT_CHECKPOINTS.md). The production image and app spec default to production mode, same-origin requests do not require cross-origin CORS grants, and all write origins must exactly match the configured HTTPS origin. Generic 500 responses include a request ID without exception text. Verbose application/database/access logging is disabled; redacted operational request metrics remain enabled.
