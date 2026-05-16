#!/usr/bin/env python3
"""
Homelab Daily Health Receipt Printer
Prints a thermal receipt with server status to ESC/POS USB printer.
"""

import os
import sys
import time
import socket
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
IMMICH_KEY      = _cfg["services"]["immich_api_key"]
PANGOLIN_URL    = _cfg["services"]["pangolin_url"]
BACKUP_PATHS    = _cfg["backups"]["paths"]
BACKUP_MAX_AGE  = _cfg["backups"]["max_age_hours"]
DISK_PATHS      = _cfg["disk"]["paths"]
DISK_WARN_PCT   = _cfg["disk"]["warn_percent"]
ADGUARD_URL     = _cfg["adguard"]["url"].rstrip("/")
ADGUARD_USER    = _cfg["adguard"]["username"]
ADGUARD_PASS    = _cfg["adguard"]["password"]
TRUENAS_URL     = _cfg["truenas"]["url"].rstrip("/")
TRUENAS_KEY     = _cfg["truenas"]["api_key"]
WEBSITE_URLS       = _cfg["websites"]["urls"]
DOCKER_EXCLUDE     = [p.lower() for p in _cfg["docker"]["exclude"]]

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
        all_containers = client.containers.list(all=True)

        managed = sorted(
            [c for c in all_containers
             if c.attrs.get("HostConfig", {}).get("RestartPolicy", {}).get("Name", "no")
             in ("always", "unless-stopped")
             and not any(pat in c.name.lower() for pat in DOCKER_EXCLUDE)],
            key=lambda c: c.name,
        )

        running_count = sum(1 for c in managed if c.status == "running")
        results.append(ok("Running", f"{running_count}/{len(managed)}"))

        for c in managed:
            name = c.name[:16]
            health = c.attrs.get("State", {}).get("Health", {}).get("Status", "")
            if c.status == "running":
                if health == "unhealthy":
                    results.append(warn(name, "unhealthy"))
                else:
                    results.append(ok(name, "running"))
            else:
                results.append(warn(name, "stopped!"))
    except Exception as e:
        results.append(fail("Docker", str(e)[:30]))
    return results


def check_zfs():
    results = []
    if not TRUENAS_URL or not TRUENAS_KEY:
        results.append(warn("TrueNAS", "URL/API key not configured"))
        return results
    try:
        r = requests.get(
            f"{TRUENAS_URL}/api/v2.0/pool",
            headers={"Authorization": f"Bearer {TRUENAS_KEY}"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            for pool in r.json():
                name = pool.get("name", "?")
                status = pool.get("status", "UNKNOWN")
                if status == "ONLINE":
                    results.append(ok(f"ZFS {name}", status))
                else:
                    results.append(fail(f"ZFS {name}", status))
        else:
            results.append(warn("TrueNAS", f"HTTP {r.status_code}"))
    except Exception:
        results.append(fail("TrueNAS", "unreachable"))
    return results


def check_disk():
    results = []
    for path in DISK_PATHS:
        path = path.strip()
        if not path:
            continue
        try:
            usage = psutil.disk_usage(path)
            used_gb = usage.used / 1e9
            total_gb = usage.total / 1e9
            pct = usage.percent
            name = path if path == "/" else path.rstrip("/").split("/")[-1]
            detail = f"{used_gb:.0f}/{total_gb:.0f}GB ({pct:.0f}%)"
            if pct >= 95:
                results.append(fail(f"Disk/{name}", detail))
            elif pct >= DISK_WARN_PCT:
                results.append(warn(f"Disk/{name}", detail))
            else:
                results.append(ok(f"Disk/{name}", detail))
        except Exception as e:
            results.append(fail(f"Disk/{path[-12:]}", str(e)[:20]))
    if not results:
        results.append(warn("Disk", "No paths configured"))
    return results


def check_websites():
    results = []
    for url in WEBSITE_URLS:
        url = url.strip()
        if not url:
            continue
        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc or url
            label = host[:18]
            t0 = time.time()
            r = requests.get(url, timeout=TIMEOUT, allow_redirects=True)
            ms = int((time.time() - t0) * 1000)
            if r.status_code < 400:
                results.append(ok(label, f"{r.status_code} ({ms}ms)"))
            elif r.status_code < 500:
                results.append(warn(label, f"{r.status_code} ({ms}ms)"))
            else:
                results.append(fail(label, f"{r.status_code}"))
        except requests.Timeout:
            results.append(fail(label, "timeout"))
        except Exception:
            results.append(fail(label, "unreachable"))
    if not results:
        results.append(warn("Websites", "No URLs configured"))
    return results


def check_adguard():
    results = []
    if not ADGUARD_URL:
        results.append(warn("AdGuard", "URL not configured"))
        return results
    try:
        auth = (ADGUARD_USER, ADGUARD_PASS) if ADGUARD_USER else None
        r = requests.get(f"{ADGUARD_URL}/control/stats", auth=auth, timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            queries = data.get("num_dns_queries", 0)
            blocked = data.get("num_blocked_filtering", 0)
            pct = (blocked / queries * 100) if queries > 0 else 0
            results.append(ok("Queries", f"{queries:,}"))
            results.append(ok("Blocked", f"{blocked:,} ({pct:.0f}%)"))
        else:
            results.append(warn("AdGuard", f"HTTP {r.status_code}"))
    except Exception:
        results.append(fail("AdGuard", "unreachable"))
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
        headers = {"x-api-key": IMMICH_KEY} if IMMICH_KEY else {}
        r = requests.get(
            f"{IMMICH_URL}/api/server/ping",
            headers=headers,
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            results.append(ok("Immich", "pong"))
        elif r.status_code == 401:
            results.append(warn("Immich", "invalid API key"))
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

    backend = _cfg["printer"].get("backend", "usb")
    try:
        if backend == "network":
            from escpos.printer import Network
            host = _cfg["printer"].get("host", "")
            if not host:
                raise ValueError("Printer host is empty")
            port = int(_cfg["printer"].get("port", 9100))
            p = Network(host, port)
        else:
            p = EscFile(PRINTER_DEVICE)
    except Exception as e:
        label = f"{_cfg['printer'].get('host')}:{_cfg['printer'].get('port', 9100)}" if backend == "network" else PRINTER_DEVICE
        print(f"ERROR: Cannot open printer {label}: {e}", file=sys.stderr)
        print_to_stdout(now, date_str, time_str, overall, attention, sections)
        return

    try:
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
            "disk":     "Disk",
            "backups":  "Backups",
            "network":  "Network",
            "services": "Services",
            "websites": "Websites",
            "adguard":  "AdGuard Home",
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

    except Exception as e:
        print(f"ERROR: Printing failed: {e}", file=sys.stderr)
        print_to_stdout(now, date_str, time_str, overall, attention, sections)


def print_to_stdout(now, date_str, time_str, overall, attention, sections):
    """Fallback: print formatted report to stdout."""
    section_labels = {
        "system":   "System",
        "docker":   "Docker",
        "zfs":      "Storage / ZFS",
        "disk":     "Disk",
        "backups":  "Backups",
        "network":  "Network",
        "services": "Services",
        "websites": "Websites",
        "adguard":  "AdGuard Home",
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
def _run_checks():
    checks = _cfg.get("checks", {})
    section_fns = {
        "system":   check_system,
        "docker":   check_docker,
        "zfs":      check_zfs,
        "disk":     check_disk,
        "backups":  check_backups,
        "network":  check_network,
        "services": check_services,
        "websites": check_websites,
        "adguard":  check_adguard,
    }
    return {
        key: fn()
        for key, fn in section_fns.items()
        if checks.get(key, True)
    }


if __name__ == "__main__":
    import argparse
    import json as _json

    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    if not args.json:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Running healthcheck...")

    sections = _run_checks()

    if args.json:
        all_results = [item for items in sections.values() for item in items]
        has_fail = any(r[0] == "FAIL" for r in all_results)
        has_warn = any(r[0] == "WARN" for r in all_results)
        overall = "FAIL" if has_fail else ("WARN" if has_warn else "OK")
        print(_json.dumps({
            "overall": overall,
            "sections": {k: [list(r) for r in v] for k, v in sections.items()},
        }))
    else:
        print_report(sections)
