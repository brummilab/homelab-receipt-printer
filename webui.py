import re
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from PIL import Image

import config

LOGO_PATH = Path("/config/logo.png")

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


@app.get("/api/logo")
def api_logo_get():
    if not LOGO_PATH.exists():
        return "", 204
    return send_file(LOGO_PATH, mimetype="image/png")


@app.post("/api/logo")
def api_logo_upload():
    f = request.files.get("logo")
    if not f:
        return jsonify({"ok": False, "error": "Keine Datei"}), 400
    try:
        img = Image.open(f).convert("L")  # grayscale — optimal for thermal
        w, h = img.size
        if w > 400:
            img = img.resize((400, int(h * 400 / w)), Image.LANCZOS)
        LOGO_PATH.parent.mkdir(parents=True, exist_ok=True)
        img.save(LOGO_PATH, "PNG")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


def _write_cron(schedule: str):
    with open("/etc/crontabs/root", "w") as f:
        f.write(f"{schedule} python /app/healthcheck.py >> /var/log/receipt.log 2>&1\n")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
