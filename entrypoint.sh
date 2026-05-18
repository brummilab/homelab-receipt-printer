#!/bin/sh
set -e

CONFIG=/config/config.json

if [ -f "$CONFIG" ]; then
    SCHEDULE=$(python3 -c "import json; print(json.load(open('$CONFIG'))['schedule'])" 2>/dev/null || echo "${CRON_SCHEDULE:-0 6 * * *}")
    ENABLED=$(python3 -c "import json; print(json.load(open('$CONFIG')).get('schedule_enabled', False))" 2>/dev/null || echo "False")
else
    SCHEDULE="${CRON_SCHEDULE:-0 6 * * *}"
    ENABLED="False"
fi

mkdir -p /var/spool/cron/crontabs
if [ "$ENABLED" = "True" ]; then
    echo "$SCHEDULE python /app/healthcheck.py >> /var/log/receipt.log 2>&1" > /var/spool/cron/crontabs/root
    chmod 600 /var/spool/cron/crontabs/root
    echo "Receipt printer scheduled: $SCHEDULE"
else
    > /var/spool/cron/crontabs/root
    chmod 600 /var/spool/cron/crontabs/root
    echo "Cron schedule disabled."
fi

echo "Starting web UI on :8080..."
python /app/webui.py &

exec cron -f
