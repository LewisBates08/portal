"""Materialize the public database CA supplied as runtime configuration, then exec."""

import os
import sys
from pathlib import Path

cert = os.environ.get("DATABASE_CA_CERT")
if cert:
    Path("/tmp/postgres-ca.crt").write_text(cert)
if len(sys.argv) < 2:
    raise SystemExit("Supply an application or maintenance command.")
os.execvp(sys.argv[1], sys.argv[1:])
