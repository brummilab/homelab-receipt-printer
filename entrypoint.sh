#!/bin/sh
set -e

CONFIG=/config/config.json

# Prefer saved schedule from config over env var
if [ -f "$CONFIG" ]; then
    SCHEDULE=$(python3 -c "import json; print(json.load(open('$CONFIG'))['schedule'])" 2>/dev/null || echo "${CRON_SCHEDULE:-0 6 * * *}")
else
    SCHEDULE="${CRON_SCHEDULE:-0 6 * * *}"
fi

mkdir -p /var/spool/cron/crontabs
echo "$SCHEDULE python /app/healthcheck.py >> /var/log/receipt.log 2>&1" > /var/spool/cron/crontabs/root
chmod 600 /var/spool/cron/crontabs/root

echo "Receipt printer scheduled: $SCHEDULE"
echo "Starting web UI on :8080..."
python /app/webui.py &

INIT_FLAG=/config/.initial_check_done
if [ ! -f "$INIT_FLAG" ]; then
    echo "Running initial check in 10 seconds..."
    sleep 10
    python /app/healthcheck.py || true
    touch "$INIT_FLAG"
fi

exec cron -f
