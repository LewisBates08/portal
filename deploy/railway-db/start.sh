#!/bin/bash
set -euo pipefail
: "${SEARCHROOM_TLS_CERT:?Set the database server certificate}"
: "${SEARCHROOM_TLS_KEY:?Set the database server private key}"
: "${SEARCHROOM_DB_PASSWORD:?Set the dedicated application role password}"
install -d -m 700 -o postgres -g postgres /tmp/searchroom-tls
umask 077
printf '%s\n' "$SEARCHROOM_TLS_CERT" > /tmp/searchroom-tls/server.crt
printf '%s\n' "$SEARCHROOM_TLS_KEY" > /tmp/searchroom-tls/server.key
chown postgres:postgres /tmp/searchroom-tls/server.crt /tmp/searchroom-tls/server.key
# Preserve Railway's volume checks and PostgreSQL startup/recovery wrapper.
exec /usr/local/bin/wrapper.sh "$@"
