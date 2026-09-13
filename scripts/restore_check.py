"""Restore an isolated test DB into a disposable DB, verify counts and remove it."""

import os
import secrets
import subprocess
import tempfile
from pathlib import Path
import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

url = make_url(os.environ["TEST_DATABASE_URL"])
if not url.database.endswith("_test"):
    raise SystemExit("Only an isolated _test database may be backed up by this drill.")
params = {
    "host": url.host,
    "port": url.port or 5432,
    "user": url.username,
    "password": url.password or "",
}
env = {
    **os.environ,
    "PGHOST": params["host"],
    "PGPORT": str(params["port"]),
    "PGUSER": params["user"],
    "PGPASSWORD": params["password"],
    "PGDATABASE": url.database,
}
target = "restore_" + secrets.token_hex(6) + "_test"
with psycopg.connect(dbname="postgres", autocommit=True, **params) as control:
    control.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target)))
    try:
        with tempfile.TemporaryDirectory() as folder:
            dump = str(Path(folder) / "backup.dump")
            subprocess.run(
                [
                    "pg_dump",
                    "--format=custom",
                    "--no-owner",
                    "--no-acl",
                    "--file",
                    dump,
                ],
                env=env,
                check=True,
            )
            subprocess.run(
                [
                    "pg_restore",
                    "--exit-on-error",
                    "--no-owner",
                    "--no-acl",
                    "--dbname",
                    target,
                    dump,
                ],
                env=env,
                check=True,
            )
        with (
            psycopg.connect(dbname=url.database, **params) as original,
            psycopg.connect(dbname=target, **params) as restored,
        ):
            for table in (
                "users",
                "projects",
                "messages",
                "candidates",
                "milestones",
                "audit_events",
            ):
                query = sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
                assert (
                    original.execute(query).fetchone()
                    == restored.execute(query).fetchone()
                ), table
            assert (
                restored.execute("SELECT version_num FROM alembic_version").fetchone()[
                    0
                ]
                == "readiness_20260913"
            )
        print("Restore verified: schema revision and six table counts match.")
    finally:
        control.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(target)))
