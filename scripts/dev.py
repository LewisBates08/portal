"""Run the local API and Vite together. Ctrl+C cleanly stops both.

Run with .venv/bin/python scripts/dev.py from any directory.
An existing project-local PostgreSQL cluster is started when present; other
PostgreSQL setups (including Docker) are managed separately.
"""

import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time

from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

root = Path(__file__).resolve().parents[1]
os.chdir(root)
if not (root / ".env").exists():
    sys.exit("Create .env using .env.example and set JWT_SECRET first.")
if not (root / "frontend/node_modules").exists():
    sys.exit("Install frontend dependencies first: cd frontend && npm ci")
sys.path.insert(0, str(root / "backend"))
from app.config import get_settings

settings = get_settings()
if settings.production:
    sys.exit(
        "This launcher is for development. Use the production container for deployment."
    )
database = make_url(settings.database_url)
if not database.database:
    sys.exit(
        "DATABASE_URL needs a database name after the hostname and port (for example, /portal)."
    )
use_local_cluster = (
    database.host in {"127.0.0.1", "localhost", "::1"} and database.port == 55432
)
processes = []
pg_ctl = None
started_postgres = False
stopping = False


def stop(*_):
    global stopping
    stopping = True


signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)
try:
    cluster = root / ".local/pgdata"
    if cluster.exists() and use_local_cluster:
        pg_config = shutil.which("pg_config")
        if not pg_config:
            sys.exit(
                "PostgreSQL tools are not on PATH. Start your database separately."
            )
        pg_ctl = (
            Path(subprocess.check_output([pg_config, "--bindir"], text=True).strip())
            / "pg_ctl"
        )
        if subprocess.run(
            [str(pg_ctl), "-D", str(cluster), "status"], stdout=subprocess.DEVNULL
        ).returncode:
            sockets = root / ".local/pgsocket"
            sockets.mkdir(exist_ok=True)
            subprocess.run(
                [
                    str(pg_ctl),
                    "-D",
                    str(cluster),
                    "-l",
                    str(root / ".local/postgres.log"),
                    "-o",
                    f"-p 55432 -h 127.0.0.1 -k {sockets}",
                    "start",
                ],
                check=True,
            )
            started_postgres = True
    from app.database import engine

    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
    except SQLAlchemyError:
        sys.exit(
            "Cannot connect to the configured database. Check DATABASE_URL in .env "
            "and any shell override. For this workspace's local database, use "
            "postgresql+psycopg://portal@127.0.0.1:55432/portal. "
            "For a remote database, check its network access and credentials."
        )
    finally:
        engine.dispose()
    env = {**os.environ, "PYTHONPATH": str(root / "backend")}
    migration = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "backend/alembic.ini",
            "upgrade",
            "head",
        ],
        env=env,
        check=False,
    )
    if migration.returncode:
        sys.exit("Database migration failed. Check the migration error above.")
    local_mail = (
        settings.smtp_host in {"localhost", "127.0.0.1"}
        and settings.smtp_port == 1025
        and not settings.smtp_user
    )
    if local_mail:

        def smtp_ready():
            try:
                with socket.create_connection((settings.smtp_host, 1025), timeout=1):
                    return True
            except OSError:
                return False

        if not smtp_ready():
            mailpit = shutil.which("mailpit")
            if not mailpit:
                sys.exit(
                    "Local email needs Mailpit. On macOS run: brew install mailpit. "
                    "Then restart this launcher, or configure an SMTP provider in .env."
                )
            processes.append(
                subprocess.Popen(
                    [mailpit, "--smtp", "127.0.0.1:1025", "--listen", "127.0.0.1:8025"],
                    start_new_session=True,
                )
            )
            for _ in range(30):
                if smtp_ready():
                    break
                if stopping or processes[-1].poll() is not None:
                    sys.exit(
                        "Local email service could not start. Check the output above."
                    )
                time.sleep(0.1)
            else:
                sys.exit("Local email service did not become ready.")
        print(
            "Development email inbox: http://localhost:8025 (no external delivery)",
            flush=True,
        )
    processes.append(
        subprocess.Popen(
            [sys.executable, "-m", "app.operations", "mail-loop"],
            env=env,
            start_new_session=True,
        )
    )
    processes.append(
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--reload",
                "--reload-dir",
                str(root / "backend"),
            ],
            env=env,
            start_new_session=True,
        )
    )
    processes.append(
        subprocess.Popen(
            ["npm", "run", "dev"], cwd=root / "frontend", start_new_session=True
        )
    )
    print(
        "\nSearchroom: http://localhost:5173\nAPI documentation: http://127.0.0.1:8000/docs\nPress Ctrl+C to stop.\n",
        flush=True,
    )
    while not stopping:
        if any(process.poll() is not None for process in processes):
            raise SystemExit("A development server stopped. Check the output above.")
        time.sleep(0.3)
finally:
    for process in processes:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
    if started_postgres:
        subprocess.run(
            [str(pg_ctl), "-D", str(root / ".local/pgdata"), "stop", "-m", "fast"],
            check=False,
        )
