#!/bin/bash
set -euo pipefail
# Runs only on a new volume. psql reads the password from the environment,
# quotes it as a SQL literal, and never echoes it to the deployment log.
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --no-psqlrc --set ON_ERROR_STOP=1 <<'SQL'
\getenv app_password SEARCHROOM_DB_PASSWORD
CREATE ROLE searchroom_app LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE DATABASE searchroom OWNER searchroom_app;
REVOKE ALL ON DATABASE searchroom FROM PUBLIC;
SQL
# Require TLS for remote connections, including the administrative account.
cat > "$PGDATA/pg_hba.conf" <<'HBA'
local all all trust
hostssl all all all scram-sha-256
hostnossl all all all reject
HBA
