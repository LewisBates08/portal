# Railway deployment

## Live verification: 2026-10-03

Public URL: https://portal-production-b3df.up.railway.app

The previously deployed portal version `b7522c39-5967-4d6b-a4d7-8d9c05688673`
(commit `56821789c5b0e5b3c565b7da2cf39cb628782a11`) was already running when
checked. Public HTTPS requests to `/`, `/login`, both referenced JS/CSS assets,
`/api/v1/health/ready`, and `/api/v1/auth/csrf` all returned 200. Readiness
returned `{"status":"ready"}`, confirming the expected database migration
revision. The session cookie had Secure, HttpOnly, SameSite=Lax and Path=/
attributes. The public login page also rendered successfully in a browser.

Earlier crashes belong to superseded deployments: `d0457fcb` lacked
`DATABASE_URL` and `JWT_SECRET`; `9723cdca` reached PostgreSQL but failed because
the `users` table did not yet exist. The current service has the required
variable names and a pre-deploy migration command configured. Service-wide logs
include failures from older deployments, so scope crash investigations to the
specific deployment ID and verify the public endpoint before changing a healthy
service. No redeployment or application-code change was needed for this check.

This verifies public access, assets, database readiness and session establishment.
It does not verify an authenticated account, email delivery, backup restoration
or all role workflows. Email was subsequently configured using the relay
described below; see its separate verification record.

## Configuration

The initial deployment used explicit email-disabled mode (`MAIL_ENABLED=false`).
Email now uses the authenticated London HTTPS relay in `deploy/mail-relay`.
The approved pilot sender and recipient are `batesyboys@outlook.com`; SES remains
in its sandbox and the application and relay enforce that recipient allowlist.
No account verification or MFA requirements are bypassed.

Deploy the repository root using the service settings recorded in
`deploy/railway-settings.json`. This file is a non-secret configuration snapshot,
not an automatically evaluated Railway file. The settings were applied using the
Railway API: build the production Dockerfile, run the locked Alembic migration
before release, listen on Railway's `PORT`, and check `/api/v1/health/ready` before
routing traffic. Railway supplies
`RAILWAY_SERVICE_ID`; this enables its probe hostname only for GET requests to the
readiness endpoint. Normal application routes still require `TRUSTED_HOSTS`.

## Required service configuration

- Set `ENVIRONMENT=production` and `STATIC_DIR=/app/static` (also image defaults).
- Generate the Railway HTTPS domain, then set `FRONTEND_URL` to that exact origin
  and `TRUSTED_HOSTS` to its hostname, without a scheme or trailing slash.
- Supply `DATABASE_URL` using `postgresql+psycopg://`, a dedicated restricted
  application role, `sslmode=verify-full` and `sslrootcert=/tmp/postgres-ca.crt`.
  Store the matching public CA PEM in `DATABASE_CA_CERT`. Bootstrap materializes
  it separately in both the migration and runtime containers.
- Supply independent production `JWT_SECRET` and Fernet `ENCRYPTION_KEY` values
  through private Railway variables. Do not copy the development `.env`.
- For this pilot set `MAIL_TRANSPORT=relay`, `MAIL_RELAY_URL` to the CloudFormation
  output, a private random `MAIL_RELAY_TOKEN`, `MAIL_FROM=Searchroom
  <batesyboys@outlook.com>`, and `MAIL_ALLOWED_RECIPIENTS=batesyboys@outlook.com`.
  Enable `MAIL_ENABLED=true` after the worker test succeeds. The worker references
  these portal variables without copying their values into the repository.
- SMTP remains an alternative transport: `MAIL_TRANSPORT=smtp`,
  `SMTP_HOST=email-smtp.eu-west-2.amazonaws.com`, `SMTP_PORT=587`, `SMTP_USER`,
  `SMTP_PASSWORD` and a verified `MAIL_FROM`. Outbound SMTP requires Railway Pro;
  the HTTPS relay avoids that requirement.

The database service sets `RAILWAY_DOCKERFILE_PATH=deploy/railway-db/Dockerfile`, extends Railway's
PostgreSQL 17 image, and retains its persistent volume and startup wrapper. On a
fresh volume it creates `searchroom`, owned by the non-superuser `searchroom_app`
role, and requires TLS for remote connections. The application does not receive
the PostgreSQL administrator password. The database receives independent
`SEARCHROOM_DB_PASSWORD`, `SEARCHROOM_TLS_CERT` and `SEARCHROOM_TLS_KEY` variables.
The certificate must match `postgres.railway.internal`; the web service receives
only its public CA and the application password via a Railway reference.

Certificates supplied for this deployment expire after one year. Replace the
server certificate/key and corresponding application CA together before expiry;
Railway's default certificate renewal does not rotate these custom certificates.
`SEARCHROOM_DB_PASSWORD` initializes the role only on a fresh volume: changing the
variable later also requires an explicit SQL password rotation. Do not recreate
or delete a volume to rotate credentials. Backup restoration and production email approval still need
validation before real client use.

The `mail` service runs from the same repository with the start command recorded
in `deploy/railway-settings.json`. It references the web service's database,
signing, encryption, origin and relay configuration, has one Amsterdam replica,
and no public domain or HTTP healthcheck. Its `MAIL_ENABLED=true` is independent
of the portal variable. See `deploy/mail-relay/README.md` for testing, retries and
credential rotation. Configure a
scheduled cleanup job (`python /app/bootstrap.py python -m app.operations cleanup`)
and database backups before using real client data.

## Verification after connecting Railway

1. Inspect the existing project, services and failed deployments before creating
   resources. Preserve existing data and variable values.
2. Deploy, inspect build and pre-deploy logs, then runtime logs. Fix each observed
   error and redeploy. Never print resolved service variables or account links.
3. Confirm HTTPS `/`, `/api/v1/health/ready`, and `/api/v1/auth/csrf` return 200;
   the CSRF response must set the Secure, HttpOnly host-only production cookie.
4. Check login and all three roles, the email worker and mail delivery using an
   authorised test account; verify monitoring and backup restoration.

Railway rejected setting a config-file path on this new service because Config as
Code is deprecated. Existing legacy files stop being read on 2026-12-01. The
deployment therefore uses explicit service settings; for a later declarative
import, use `railway config pull` without `--include-variables`, review its plan,
and preserve all existing resources and secrets.

References: [Railway infrastructure configuration](https://docs.railway.com/infrastructure-as-code),
[pre-deploy commands](https://docs.railway.com/deployments/pre-deploy-command),
[healthchecks](https://docs.railway.com/deployments/healthchecks).

## Email verification: 2026-10-03

CloudFormation stack `searchroom-mail-relay` reached `CREATE_COMPLETE` in
`eu-west-2`. Its URL returned 401 for an unauthenticated POST. cfn-lint 1.57.1,
cfn-guard 3.2.1 custom rules and AWS template validation passed. The tested handler
matches the inline Lambda source. Application regression checks passed (38 tests),
and the standalone relay checks passed (4 tests).

Railway worker deployment `da1f99d2-18bd-457c-a1e9-d7231ad4d16b`, built from
`bb00536e25b943669ba0be8061b8d11696e54050`, reached SUCCESS. Its one-time
pre-deploy check logged `Mail test accepted by provider through the application
outbox.` at 20:43:39 UTC, then the continuous worker started. The test recipient
was the approved pilot address. The one-time command was removed afterwards.
This proves the live encrypted outbox, worker, HTTPS authentication, Lambda IAM
role and SES acceptance. Inbox delivery still requires recipient confirmation.
