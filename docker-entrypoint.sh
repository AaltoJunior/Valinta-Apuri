#!/usr/bin/env sh
set -eu

mkdir -p /app/tmp /app/dp /app/static/img_cur

: "${ENV:=production}"
export ENV

python -u /app/bg.py &
bg_pid=$!

python -u /app/scripts/redirector.py &
redirect_pid=$!

wait_for_data() {
  attempts=0
  while [ "$attempts" -lt 180 ]; do
    if [ -f /app/tmp/data.pkl ] && [ -f /app/tmp/categories.pkl ]; then
      return 0
    fi
    attempts=$((attempts + 1))
    sleep 1
  done
  return 1
}

echo "Waiting for initial data files..."
if ! wait_for_data; then
  echo "Initial data files were not created in time."
  kill "$bg_pid" 2>/dev/null || true
  kill "$redirect_pid" 2>/dev/null || true
  exit 1
fi

exec gunicorn \
  --worker-class gthread \
  --threads 4 \
  --workers 2 \
  --bind 0.0.0.0:8443 \
  --certfile "${TLS_CERT_FILE:-/certs/cert.pem}" \
  --keyfile "${TLS_KEY_FILE:-/certs/key.pem}" \
  --error-logfile - \
  --http-protocols h2,h1 \
  app:app