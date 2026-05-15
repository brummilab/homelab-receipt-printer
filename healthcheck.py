#!/usr/bin/env python3
"""
Homelab Daily Health Receipt Printer
Prints a thermal receipt with server status to ESC/POS USB printer.
"""

import os
import sys
import time
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import psutil
import requests
import docker
from escpos.printer import File as EscFile

import config as _config

# ── Config ────────────────────────────────────────────────────────────────────
_cfg = _config.load()

PRINTER_DEVICE  = _cfg["printer"]["device"]
JELLYFIN_URL    = _cfg["services"]["jellyfin_url"]
JELLYFIN_KEY    = _cfg["services"]["jellyfin_api_key"]
IMMICH_URL      = _cfg["services"]["immich_url"]
PANGOLIN_URL    = _cfg["services"]["pangolin_url"]
BACKUP_PATHS    = _cfg["backups"]["paths"]
BACKUP_MAX_AGE  = _cfg["backups"]["max_age_hours"]

TIMEOUT = 5  # seconds for HTTP checks

# ── Helpers ───────────────────────────────────────────────────────────────────
def ok(label, detail=""):
    return ("OK", label, detail)

def warn(label, detail=""):
    return ("WARN", label, detail)

def fail(label, detail=""):
    return ("FAIL", label, detail)


# ── Checks ────────────────────────────────────────────────────────────────────
def check_system():
    results = []
    # Uptime
    boot = psutil.boot_time()
    uptime_s = time.time() - boot
    days = int(uptime_s // 86400)
    hours = int((uptime_s % 86400) // 3600)
    results.append(ok("Uptime", f"{days}d {hours}h"))

    # CPU (1s sample)
    cpu = psutil.cpu_percent(interval=1)
    level = ok if cpu < 80 else warn
    results.append(level("CPU", f"{cpu:.0f}%"))

    # RAM
    mem = psutil.virtual_memory()
    used_gb = mem.used / 1e9
    total_gb = mem.total / 1e9
    pct = mem.percent
    level = ok if pct < 85 else warn
    results.append(level("RAM", f"{used_gb:.1f}/{total_gb:.1f}GB ({pct:.0f}%)"))

    return results


def check_docker():
    results = []
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)
        running = [c for c in containers if c.status == "running"]
        stopped = [c for c in containers if c.status not in ("running", "exited") or
                   (c.status == "exited" and c.attrs.get("HostConfig", {}).get("RestartPolicy", {}).get("Name") not in ("no", ""))]

        # Find unhealthy / unexpected stops
        bad = [c for c in containers
               if c.status == "exited"
               and c.attrs.get("HostConfig", {}).get("RestartPolicy", {}).get("Name", "no") != "no"]

        results.append(ok("Running", f"{len(running)}/{len(containers)}"))

        if bad:
            for c in bad[:3]:
                results.append(warn("Stopped", c.name[:20]))
        else:
            results.append(ok("All containers", "healthy"))

    except Exception as e:
        results.append(fail("Docker", str(e)[:30]))
    return results


def check_zfs():
    results = []
    try:
        out = subprocess.check_output(
            ["zpool", "status", "-x"], text=True, timeout=10
        )
        if "all pools are healthy" in out.lower():
            results.append(ok("ZFS Pool", "all healthy"))
        else:
            # Parse pool names and states
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("pool:"):
                    pool = line.split(":", 1)[1].strip()
                elif line.startswith("state:"):
                    state = line.split(":", 1)[1].strip()
                    level = ok if state == "ONLINE" else fail
                    results.append(level(f"ZFS {pool}", state))
    except FileNotFoundError:
        # zpool not in container — read from /proc or skip
        results.append(warn("ZFS", "zpool not available in container"))
    except Exception as e:
        results.append(fail("ZFS", str(e)[:30]))
    return results


def check_backups():
    results = []
    now = time.time()

    for path in BACKUP_PATHS:
        path = path.strip()
        if not path:
            continue
        try:
            stat = os.stat(path)
            age_h = (now - stat.st_mtime) / 3600
            name = os.path.basename(path) or path
            if age_h < BACKUP_MAX_AGE:
                results.append(ok(f"Backup/{name}", f"{age_h:.0f}h ago"))
            else:
                results.append(warn(f"Backup/{name}", f"{age_h:.0f}h ago!"))
        except Exception as e:
            results.append(fail(f"Backup/{path[-15:]}", str(e)[:20]))

    if not results:
        results.append(warn("Backups", "No paths configured"))
    return results


def check_network():
    results = []

    # Pangolin reverse proxy
    try:
        r = requests.get(PANGOLIN_URL, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code < 500:
            results.append(ok("Pangolin", f"HTTP {r.status_code}"))
        else:
            results.append(warn("Pangolin", f"HTTP {r.status_code}"))
    except Exception as e:
        results.append(fail("Pangolin", "unreachable"))

    # DNS check
    try:
        socket.getaddrinfo("google.com", 80, proto=socket.IPPROTO_TCP)
        results.append(ok("DNS", "resolving"))
    except Exception:
        results.append(fail("DNS", "failed"))

    return results


def check_services():
    results = []

    # Jellyfin
    try:
        r = requests.get(
            f"{JELLYFIN_URL}/health",
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            results.append(ok("Jellyfin", "healthy"))
        else:
            results.append(warn("Jellyfin", f"HTTP {r.status_code}"))
    except Exception:
        results.append(fail("Jellyfin", "unreachable"))

    # Immich
    try:
        r = requests.get(
            f"{IMMICH_URL}/api/server-info/ping",
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            results.append(ok("Immich", "pong"))
        else:
            results.append(warn("Immich", f"HTTP {r.status_code}"))
    except Exception:
        results.append(fail("Immich", "unreachable"))

    return results


# ── Print ─────────────────────────────────────────────────────────────────────
def print_report(sections: dict):
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")
    time_str = now.strftime("%H:%M")

    # Flatten all results for overall status
    all_results = [item for items in sections.values() for item in items]
    has_fail = any(r[0] == "FAIL" for r in all_results)
    has_warn = any(r[0] == "WARN" for r in all_results)
    overall = "FAIL" if has_fail else ("WARN" if has_warn else "OK")

    attention = [r for r in all_results if r[0] in ("FAIL", "WARN")]

    try:
        p = EscFile(PRINTER_DEVICE)
    except Exception as e:
        print(f"ERROR: Cannot open printer {PRINTER_DEVICE}: {e}", file=sys.stderr)
        # Print to stdout as fallback
        print_to_stdout(now, date_str, time_str, overall, attention, sections)
        return

    # Logo
    logo = Path("/config/logo.png")
    if logo.exists():
        try:
            p.set(align="center")
            p.image(str(logo))
            p.text("\n")
        except Exception as e:
            print(f"Warning: logo print failed: {e}", file=sys.stderr)

    # Header
    p.set(align="center", bold=True, double_height=False, double_width=False)
    p.text("Homelab Daily Health\n")
    p.set(align="center", bold=False)
    p.text(f"{date_str}\n")
    p.text(f"Generated: {time_str}\n")
    p.text("-" * 32 + "\n")

    # Overall
    p.set(align="center", bold=True)
    status_line = f"Overall: {overall}"
    p.text(status_line + "\n")
    p.set(align="left", bold=False)
    p.text("-" * 32 + "\n")

    # Needs attention
    p.set(bold=True)
    p.text("Needs attention\n")
    p.set(bold=False)
    if attention:
        for status, label, detail in attention:
            marker = "!!" if status == "FAIL" else " !"
            line = f"{marker} {label}"
            if detail:
                line += f": {detail}"
            p.text(line[:32] + "\n")
    else:
        p.text("- None\n")

    p.text("-" * 32 + "\n")

    # Sections
    section_labels = {
        "system":   "System",
        "docker":   "Docker",
        "zfs":      "Storage / ZFS",
        "backups":  "Backups",
        "network":  "Network",
        "services": "Services",
    }

    for key, items in sections.items():
        p.set(bold=True)
        p.text(section_labels.get(key, key) + "\n")
        p.set(bold=False)
        for status, label, detail in items:
            marker = "OK" if status == "OK" else ("!!" if status == "FAIL" else " !")
            line = f"[{marker}] {label}"
            if detail:
                line += f": {detail}"
            p.text(line[:32] + "\n")

    # Footer
    p.text("-" * 32 + "\n")
    p.set(align="center")
    p.text("brummilab\n")
    p.text("\n\n\n")
    p.cut()
    print(f"[{time_str}] Receipt printed. Overall: {overall}")


def print_to_stdout(now, date_str, time_str, overall, attention, sections):
    """Fallback: print formatted report to stdout."""
    section_labels = {
        "system":   "System",
        "docker":   "Docker",
        "zfs":      "Storage / ZFS",
        "backups":  "Backups",
        "network":  "Network",
        "services": "Services",
    }
    print("=" * 32)
    print("Homelab Daily Health")
    print(date_str)
    print(f"Generated: {time_str}")
    print("-" * 32)
    print(f"Overall: {overall}")
    print("-" * 32)
    print("Needs attention")
    if attention:
        for status, label, detail in attention:
            marker = "!!" if status == "FAIL" else " !"
            print(f"{marker} {label}: {detail}")
    else:
        print("- None")
    print("-" * 32)
    for key, items in sections.items():
        print(section_labels.get(key, key))
        for status, label, detail in items:
            marker = "OK" if status == "OK" else ("!!" if status == "FAIL" else " !")
            print(f"[{marker}] {label}: {detail}")
    print("=" * 32)


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Running healthcheck...")

    checks = _cfg.get("checks", {})
    section_fns = {
        "system":   check_system,
        "docker":   check_docker,
        "zfs":      check_zfs,
        "backups":  check_backups,
        "network":  check_network,
        "services": check_services,
    }
    sections = {
        key: fn()
        for key, fn in section_fns.items()
        if checks.get(key, True)
    }

    print_report(sections)
