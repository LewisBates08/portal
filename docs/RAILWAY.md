# Railway deployment

The initial deployment uses explicit email-disabled mode (`MAIL_ENABLED=false`).
The site can start with production security enabled, but signup, verification
resend and password reset return 503 until email is configured. Invitations cannot
be queued either. No account verification or MFA requirements are bypassed.

Deploy the repository root using `railway.json`. It builds the existing production
Dockerfile, runs the locked Alembic migration before release, listens on Railway's
`PORT`, and checks `/api/v1/health/ready` before routing traffic. Railway supplies
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
- Configure authenticated SES SMTP: `SMTP_HOST=email-smtp.eu-west-2.amazonaws.com`,
  `SMTP_PORT=587`, `SMTP_USER`, `SMTP_PASSWORD`, and a verified `MAIL_FROM`.
  Confirm the selected Railway plan allows outbound SMTP before release.

The database service uses `/deploy/railway-db/railway.json`, extends Railway's
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
or delete a volume to rotate credentials. Backups and email delivery still need
validation before real client use.

After configuring a verified sender and SMTP credentials, set `MAIL_ENABLED=true`
and create a second service from the same repository for email delivery. Set its
config-file path to `/deploy/railway-mail.json` and reference the web service's
database, signing, encryption, origin, and SMTP configuration. Start it after the
web migration succeeds. It has no public domain or HTTP healthcheck. Configure a
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

References: [Railway configuration](https://docs.railway.com/config-as-code/reference),
[pre-deploy commands](https://docs.railway.com/deployments/pre-deploy-command),
[healthchecks](https://docs.railway.com/deployments/healthchecks).
