import re
import subprocess
import sys

from flask import Flask, jsonify, render_template, request

import config

app = Flask(__name__)

_CRON_RE = re.compile(
    r"^(\*|[0-9,\-/]+)\s+(\*|[0-9,\-/]+)\s+(\*|[0-9,\-/]+)\s+(\*|[0-9,\-/]+)\s+(\*|[0-9,\-/]+)$"
)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/config")
def api_get():
    return jsonify(config.load())


@app.post("/api/config")
def api_save():
    cfg = request.get_json(force=True)
    schedule = cfg.get("schedule", "0 6 * * *").strip()
    if not _CRON_RE.match(schedule):
        return jsonify({"ok": False, "error": "Ungültiger Cron-Ausdruck"}), 400
    config.save(cfg)
    _write_cron(schedule)
    return jsonify({"ok": True})


@app.post("/api/print")
def api_print():
    r = subprocess.run(
        [sys.executable, "/app/healthcheck.py"],
        capture_output=True, text=True, timeout=60,
    )
    return jsonify({"ok": r.returncode == 0, "log": r.stdout + r.stderr})


def _write_cron(schedule: str):
    with open("/etc/crontabs/root", "w") as f:
        f.write(f"{schedule} python /app/healthcheck.py >> /var/log/receipt.log 2>&1\n")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
