# Security Review Report

## Executive summary

The portal has a strong security baseline. I found no confirmed Critical or High application-code vulnerability, no SQL injection path, no stored/reflected XSS sink, and no customer-data endpoint missing an authorization boundary.

Three issues warrant remediation:

| Severity | Finding | Confidence |
|---|---|---|
| Medium | Single-factor accounts permit weak/common 10-character passwords | High |
| Medium | Pinned `urllib3==2.7.0` has published vulnerabilities | High |
| Low | HSTS omits `includeSubDomains` | High |

This was a read-only static review. No files were changed.

## Findings

### 1. Single-factor accounts permit weak/common 10-character passwords

- **Severity:** Medium
- **Confidence:** High
- **OWASP category:** A07 Identification and Authentication Failures
- **Locations:** [schemas.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/schemas.py:64), [schemas.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/schemas.py:81), [schemas.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/schemas.py:150), [auth.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/auth.py:102)

Registration, invitation acceptance and password reset accept any password of at least ten characters. There is no common-password or breached-password blocklist. Recruiter and client accounts do not require MFA, so their password is a single authentication factor.

A predictable value such as `Password1!` satisfies the application policy. Per-account throttling reduces online guessing, but it does not protect against credential stuffing or password reuse.

Current NIST guidance calls for at least 15 characters for single-factor passwords and comparison against a blocklist of commonly used or compromised passwords. It discourages arbitrary character-composition rules. [NIST SP 800-63B](https://pages.nist.gov/800-63-4/sp800-63b.html)

**Recommendation:** Raise the minimum to 15 characters for accounts that can authenticate without MFA, permit long passphrases, and reject known-common or compromised passwords locally. Alternatively, require MFA for every role.

### 2. Pinned `urllib3==2.7.0` has published vulnerabilities

- **Severity:** Medium
- **Confidence:** High
- **OWASP category:** A06 Vulnerable and Outdated Components
- **Location:** [requirements.lock](/Users/lewisbates/Documents/Projects/clientportal2/backend/requirements.lock:39)

The runtime lock pins `urllib3==2.7.0`. Version 2.8.0 fixes three subsequent advisories:

- High: HTTPS-proxy TLS settings can be ignored or overridden.
- High: unbounded chunk-size lines can cause excessive buffering.
- Moderate: chunked Deflate streaming can enter an infinite loop.

The fixes are documented in the [urllib3 2.8.0 release](https://github.com/urllib3/urllib3/releases) and its [security advisory list](https://github.com/urllib3/urllib3/security/advisories).

The portal’s visible use is through AWS SDK dependencies against configured AWS endpoints, so exploitability is lower than the upstream ratings unless an attacker can influence the upstream response or proxy configuration. Nevertheless, the vulnerable component ships in the production image.

**Recommendation:** Update the lock to `urllib3>=2.8.0`, confirm compatibility with the pinned `botocore`, and rerun tests and dependency audits before release.

### 3. HSTS does not cover subdomains

- **Severity:** Low
- **Confidence:** High
- **OWASP category:** A05 Security Misconfiguration
- **Location:** [main.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/main.py:153)

Production sends:

```http
Strict-Transport-Security: max-age=31536000
```

It omits `includeSubDomains`. Users are protected on the portal hostname after their first secure visit, but sibling/subdomain coverage is not requested.

**Recommendation:** If every subdomain is HTTPS-ready, use:

```http
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

Only consider `preload` after confirming the entire parent-domain estate meets preload requirements.

## Customer-data endpoint authorization

I found no customer-data endpoint lacking an authentication and authorization check.

- The projects router applies `write_limit`, which depends on `current_user`, to every endpoint at router level: [projects.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/projects.py:57), [resources.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/resources.py:74).
- Project-specific routes additionally use `project_access`, which verifies tenant ownership and membership: [access.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/access.py:9).
- Staff-only changes use `project_editor`: [access.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/access.py:31).
- Candidate visibility is independently enforced for clients: [access.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/access.py:46).
- Administration routes have a router-wide `Depends(admin)` and repeat the dependency on handlers: [admin.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/admin.py:43).
- Administrative object lookups consistently restrict records to the administrator’s agency, for example project ownership at [admin.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/admin.py:88) and account changes at [admin.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/admin.py:255).

The unauthenticated routes are limited to health checks and expected account lifecycle operations such as registration, login, verification, password reset and invitation-token handling. Those routes use opaque high-entropy tokens and do not directly expose existing customer records.

## Login and session assessment

The application uses opaque, server-side, revocable sessions rather than browser-accessible bearer tokens.

What it does well:

- Session tokens are generated with `secrets.token_urlsafe(32)` and only SHA-256 digests are stored: [security.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/security.py:76).
- Login rotates the pre-authentication session, limiting session fixation.
- Cookies are `HttpOnly`, `SameSite=Lax`, path `/`, and `Secure` in production: [security.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/security.py:92).
- Production uses the `__Host-` cookie prefix: [config.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/config.py:84).
- Sessions have a seven-day absolute lifetime and configurable idle timeout.
- Logout and password reset revoke server-side sessions.
- Password verification uses Argon2 through `pwdlib`, with a dummy hash to reduce username-based timing differences.
- Authentication is limited by both client address and normalized account identity: [security.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/security.py:177).
- Administrator access requires completed TOTP MFA: [security.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/security.py:130).
- MFA secrets are encrypted at rest, recovery codes are stored as hashes, and TOTP steps cannot be replayed: [mfa.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/mfa.py:29).

## OWASP-specific observations

### SQL injection

No SQL injection path was found.

Database interaction primarily uses SQLAlchemy expressions. The limited textual SQL uses fixed statements with bound parameters, for example [auth.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/auth.py:41) and [resources.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/resources.py:104). User-controlled values are not interpolated into SQL strings.

### Cross-site scripting

No confirmed XSS sink was found.

- User content is rendered through ordinary React JSX, which escapes text.
- There is no `dangerouslySetInnerHTML`, direct `innerHTML`, or equivalent DOM injection.
- External URLs are restricted to credential-free HTTPS URLs: [schemas.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/schemas.py:39).
- External tabs use `noopener noreferrer`: [ui.tsx](/Users/lewisbates/Documents/Projects/clientportal2/frontend/src/ui.tsx:125).
- Production sends a restrictive CSP with no inline-script allowance: [main.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/main.py:155).

### CORS and CSRF

The same-origin design intentionally installs no CORS middleware and grants no cross-origin origins: [main.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/main.py:67).

Every state-changing API request requires:

1. An exact match against the configured frontend `Origin`.
2. A valid session.
3. A session-derived HMAC CSRF token.

See [security.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/security.py:104). This is stronger than relying on `SameSite` alone.

### Secrets

No committed production secret, AWS key, private key or live credential was found by the source scan.

- Environment examples contain explicit placeholders.
- Secret settings are excluded from object representations: [config.py](/Users/lewisbates/Documents/Projects/clientportal2/backend/app/config.py:47).
- Production startup rejects placeholder signing secrets, unsafe database credentials and incomplete mail credentials.
- Invitation, reset and verification tokens are stored as hashes.
- The mail relay stores and compares a SHA-256 token representation rather than logging or returning the shared credential.

## Additional strengths

- Strict tenant and project-level access checks return 404 for inaccessible resources, reducing enumeration.
- Input models reject unknown fields and impose length limits.
- API response models explicitly avoid password hashes, MFA secrets, recovery hashes and session tokens.
- Error handling avoids echoing invalid password input and suppresses production tracebacks.
- Request bodies are capped at 1 MiB before application processing.
- Trusted-host validation is enabled and production permits only the configured hostname.
- Production requires database TLS with `verify-full` and a CA certificate.
- Security headers include CSP, frame denial, MIME sniffing protection, restrictive permissions policy, no-referrer and `no-store` for non-static responses.
- Database statement, lock and pool timeouts reduce resource-exhaustion risk.
- The production container runs as a non-root user, removes packaging tools and pins its base image digest.
- Destructive project deletion requires administrator access, archival state, the current version and exact-title confirmation.

## Audit limitations

- This was static review, not penetration testing or live deployment verification.
- `pip-audit` could not create its temporary environment under the mandated read-only filesystem.
- `npm audit` could not reach the npm registry. Therefore, frontend dependencies were inspected but not conclusively cleared against the current npm advisory database.
- The confirmed Python dependency finding above was verified directly against upstream urllib3 advisories as of 27 October 2026.
- No tests were run because they would create temporary files and mutate a test database, contrary to the read-only instruction.

