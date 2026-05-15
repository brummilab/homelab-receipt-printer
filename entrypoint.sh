#!/bin/sh
set -e

SCHEDULE="${CRON_SCHEDULE:-0 6 * * *}"

echo "$SCHEDULE python /app/healthcheck.py >> /var/log/receipt.log 2>&1" > /etc/crontabs/root

echo "Receipt printer scheduled: $SCHEDULE"
echo "Running initial check in 10 seconds..."
sleep 10
python /app/healthcheck.py || true

exec crond -f -l 2
