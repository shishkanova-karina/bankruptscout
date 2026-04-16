#!/bin/sh
set -e
mkdir -p /app/data /app/logs
export PYTHONPATH="${PYTHONPATH:-/app}"
python -c "from storage.session import initialize_tables; initialize_tables()"
exec "$@"
