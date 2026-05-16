import json
import os
from pathlib import Path

CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "/config/config.json"))


def _defaults():
    return {
        "printer": {
            "device":  os.environ.get("PRINTER_DEVICE", "/dev/usb/lp0"),
            "backend": "usb",
            "host":    "",
            "port":    9100,
        },
        "schedule": os.environ.get("CRON_SCHEDULE", "0 6 * * *"),
        "checks": {
            "system":    True,
            "docker":    True,
            "zfs":       True,
            "disk":      True,
            "backups":   True,
            "network":   True,
            "services":  True,
            "websites":  True,
            "adguard":   True,
        },
        "services": {
            "jellyfin_url":     os.environ.get("JELLYFIN_URL", ""),
            "jellyfin_api_key": os.environ.get("JELLYFIN_API_KEY", ""),
            "immich_url":       os.environ.get("IMMICH_URL", ""),
            "immich_api_key":   os.environ.get("IMMICH_API_KEY", ""),
            "pangolin_url":     os.environ.get("PANGOLIN_URL", ""),
        },
        "adguard": {
            "url":      os.environ.get("ADGUARD_URL", ""),
            "username": os.environ.get("ADGUARD_USER", ""),
            "password": os.environ.get("ADGUARD_PASS", ""),
        },
        "truenas": {
            "url":     os.environ.get("TRUENAS_URL", "http://192.168.1.50"),
            "api_key": os.environ.get("TRUENAS_API_KEY", ""),
        },
        "backups": {
            "paths":        [p.strip() for p in os.environ.get("BACKUP_PATHS", "").split(",") if p.strip()],
            "max_age_hours": 48,
        },
        "disk": {
            "paths":        [],
            "warn_percent": 85,
        },
        "websites": {
            "urls": [],
        },
        "docker": {
            "exclude": ["postgres", "redis", "mysql", "mariadb", "mongo"],
        },
    }


def load():
    defaults = _defaults()
    if not CONFIG_PATH.exists():
        return defaults
    with open(CONFIG_PATH) as f:
        saved = json.load(f)
    for key, default_val in defaults.items():
        if key not in saved:
            saved[key] = default_val
        elif isinstance(default_val, dict):
            saved[key] = {**default_val, **saved[key]}
    return saved


def save(cfg):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
