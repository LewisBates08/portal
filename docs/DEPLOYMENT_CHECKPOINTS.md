# Production security checkpoint audit — 19 September 2026

The repository is configured for **https://portal.radiumsearch.com**. This is the intended hostname chosen for this project; ownership, DNS routing, hosting configuration and the live certificate have not been verified. No production cloud deployment was performed during this audit.

| # | Checkpoint | Repository result and evidence |
|---|---|---|
| 1 | No hard-coded secrets | Gitleaks 8.30.1 found no leaks in the current source snapshot or all two reachable commits. Production credentials are runtime-only; the database URL no longer has a default credential. Secret fields are excluded from settings representations and validation errors. Test data is not a production credential. |
| 2 | `.env` ignored | `.env`, `.env.*`, `*.env` and `*.env.*` are ignored at every directory level. Only `.example` templates are exempt. Git ignore behavior was checked directly. |
| 3 | Production `.env` never committed | No actual environment-file paths were found in the index or reachable history. The clone is not shallow and its history covers the advertised remote tip. Only `.env.example` and `deploy/production.env.example` are tracked templates. This cannot prove what existed in deleted remote branches or other clones. CI checks full reachable history. |
| 4 | Demo accounts/passwords removed | The backend no longer includes the demo seeder or default demo password. Fictional browser fixtures are outside the runtime image, require `_test` storage and receive generated credentials. Production startup rejects target databases containing legacy demo login addresses. The contents of a future production database still need verification; local development data was not deleted. |
| 5 | Debug disabled | FastAPI explicitly sets `debug=False`. The production image/app spec set `ENVIRONMENT=production`; the launcher rejects reload mode. |
| 6 | Development logging disabled | Uvicorn access logs and SQL debug logging are disabled, with warning-level server logs. Redacted operational request IDs, route templates, timings and statuses remain enabled. Production exception details and SQL parameters are not logged by the request handler. |
| 7 | Production hostname configured | App Platform domain, `FRONTEND_URL` and `TRUSTED_HOSTS` specify `portal.radiumsearch.com`. Startup rejects placeholder/private/IP/localhost origins, paths and custom ports. DNS and HTTPS activation remain external launch requirements. |
| 8 | CORS restricted | The frontend and API share an origin. No CORS middleware or cross-origin credential grants are enabled. Cross-origin preflight requests receive no allow-origin headers. |
| 9 | Trusted origins production-only | Production accepts only the one exact configured HTTPS origin for writes, plus the session-bound CSRF token. Trusted hosts must exactly match that hostname; wildcards, extra hosts and localhost entries are rejected. |
| 10 | Secure cookies enabled | Production uses the `__Host-` cookie with Secure, HttpOnly, SameSite=Lax, Path=/ and no Domain. Tests verify the actual Set-Cookie response. |
| 11 | No stack traces in error responses | Generic production 500 JSON includes a request ID, never exception text. Validation responses omit submitted input/context, including passwords. Tests inject an exception and verify neither response nor captured log exposes its contents. |

## Validation

- 51 PostgreSQL backend tests passed, including production configuration, cookie flags, cross-origin rejection, error redaction and the demo-database startup gate.
- Frontend type checking/build passed; all 10 frontend component tests passed.
- All nine HTTPS browser smoke tests passed: admin, recruiter and client in Chromium, Firefox and WebKit, using a fresh disposable database and generated credentials.
- Gitleaks found no leaks in both the source snapshot and reachable history. No history rewrite or credential rotation was needed based on these findings.
- Docker is unavailable on this machine. Container execution and cloud settings must pass the CI/staging checks before launch.

## Live release gate

Configure the runtime secrets, London PostgreSQL/VPC, actual domain/DNS/TLS, verified SES sender and backup storage described in [DEPLOYMENT.md](DEPLOYMENT.md). Verify the production target database has no demo accounts, and exercise the actual HTTPS endpoint for cookies, origins, headers and errors. Do not describe the site as live or fully deployment-verified until these external checks pass.
