"""Run the local API and Vite together. Ctrl+C cleanly stops both.

Run with .venv/bin/python scripts/dev.py from any directory.
An existing project-local PostgreSQL cluster is started when present; other
PostgreSQL setups (including Docker) are managed separately.
"""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
os.chdir(root)
if not (root / '.env').exists():
    sys.exit('Create .env using .env.example and set JWT_SECRET first.')
if not (root / 'frontend/node_modules').exists():
    sys.exit('Install frontend dependencies first: cd frontend && npm ci')
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
    cluster = root / '.local/pgdata'
    if cluster.exists():
        pg_config = shutil.which('pg_config')
        if not pg_config:
            sys.exit('PostgreSQL tools are not on PATH. Start your database separately.')
        pg_ctl = Path(subprocess.check_output([pg_config, '--bindir'], text=True).strip()) / 'pg_ctl'
        if subprocess.run([str(pg_ctl), '-D', str(cluster), 'status'], stdout=subprocess.DEVNULL).returncode:
            sockets = root / '.local/pgsocket'
            sockets.mkdir(exist_ok=True)
            subprocess.run([str(pg_ctl), '-D', str(cluster), '-l', str(root / '.local/postgres.log'), '-o', f'-p 55432 -h 127.0.0.1 -k {sockets}', 'start'], check=True)
            started_postgres = True
    env = {**os.environ, 'PYTHONPATH': str(root / 'backend')}
    subprocess.run([sys.executable, '-m', 'alembic', '-c', 'backend/alembic.ini', 'upgrade', 'head'], env=env, check=True)
    processes.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--reload', '--reload-dir', str(root / 'backend')], env=env, start_new_session=True))
    processes.append(subprocess.Popen(['npm', 'run', 'dev'], cwd=root / 'frontend', start_new_session=True))
    print('\nSearchroom: http://localhost:5173\nAPI documentation: http://127.0.0.1:8000/docs\nPress Ctrl+C to stop.\n', flush=True)
    while not stopping:
        if any(process.poll() is not None for process in processes):
            raise SystemExit('A development server stopped. Check the output above.')
        time.sleep(.3)
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
        subprocess.run([str(pg_ctl), '-D', str(root / '.local/pgdata'), 'stop', '-m', 'fast'], check=False)
