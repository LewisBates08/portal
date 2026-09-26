# Container security and release checks

The production Dockerfile uses a digest-pinned Python 3.13 / Alpine 3.23 base.
Dependencies install from the runtime lock file as binary wheels in a matching
builder. No compiler, pip, setuptools or wheel is shipped in final images.
If an updated dependency lacks a compatible wheel, the build fails explicitly;
review compatibility before changing the build, never disable the security gate.

## Image targets

- `runtime` (the default): web frontend/API, email worker, migrations, cleanup and operational checks.
- `operations`: the same application plus PostgreSQL 17 client tools for database exports/restores.
- `test`: runtime plus isolated test tools; never publish or deploy it.

Build with `docker build --pull --target runtime -t searchroom:runtime .` and
`docker build --target operations -t searchroom:operations .`.
Use the operations image for `python -m app.operations backup` and restore drills.
Other maintenance commands use runtime. The existing bootstrap entrypoint and
configuration contract are preserved. Local development Compose is unchanged.

## CI and evidence

CI uploads the two final images before container tests. Separate matrix jobs load
those exact images and scan both, retaining JSON package inventories and image IDs
even when a scan fails. HIGH/CRITICAL findings block release, including unfixed
findings. Secret scanning runs independently. No global vulnerability exclusions
are configured.

Backend tests run in the Alpine test target. Browser and load checks run against
the final runtime container over HTTPS with short-lived, fictional test fixtures.
Certificates and fixture creation remain outside production images. The test
configuration does not claim to validate a provisioned cloud environment;
production-mode settings and cookie behavior have separate integration tests.
The operations image executes the backup/restore drill against a disposable DB.

Successful main-branch runs publish the saved, tested images without rebuilding:
`ghcr.io/<owner>/<repo>:<commit>-ci` and `:<commit>-operations`. The release-digests
artifact records immutable registry digests. Branch/PR runs retain image artifacts
for seven days but do not publish releases. Configure deployments to use the
recorded digest, never a mutable tag. No AWS deployment happens in this workflow.

To update a base image, verify its official registry digest, change it in both
builder and runtime stages, and run the complete workflow. Retain previous release
digests for investigation; only roll back to schema-compatible images that still
meet the security policy. A clean report is time-specific, not a perpetual guarantee.

If a scan fails, inspect its JSON artifact for installed/fixed versions and vendor
advisories. Update or remove affected packages and rerun. Unfixed findings remain
release blockers; a separately reviewed exception would require explicit approval.
