# homelab-receipt-printer

Prints a daily thermal receipt with homelab status on an ESC/POS thermal printer.  
All settings configurable through a web UI — no file editing required.

## What is checked

| Section | Content |
|---|---|
| **System** | Uptime, CPU load, RAM usage |
| **Docker** | Each container individually: name + status (running / stopped / unhealthy) |
| **ZFS** | Pool status (ONLINE / degraded) |
| **Disk** | Usage of configured mount points, WARN at configurable %, FAIL at 95% |
| **Backups** | Age of backup directories, WARN after configurable hours |
| **Network** | DNS resolution, Pangolin reverse proxy |
| **Services** | Jellyfin, Immich (with API key) |
| **Websites** | HTTP status + response time for arbitrary URLs |
| **AdGuard Home** | DNS queries today, blocked queries + block rate |

All sections can be individually enabled or disabled.

## Web UI

Available at `http://<server-ip>:8080` after startup.

- Choose printer backend (USB or Network/LAN)
- Upload logo (printed at the top of the receipt)
- Enable/disable sections
- Enter service URLs and API keys (Jellyfin, Immich, AdGuard)
- Add websites to monitor
- Manage backup paths and disk mount points
- Set cron schedule
- **Status Preview** — run all checks live without printing
- "Print Receipt" — trigger manually at any time

Configuration is saved in a Docker volume at `/config/config.json`.

## Installation

### Option A — Dockge / TrueNAS (recommended)

The image is published automatically to the GitHub Container Registry on every push to `main`.

1. Open Dockge and create a new stack
2. Paste the contents of [`docker-compose.yml`](docker-compose.yml)
3. Adjust the environment variables (IP addresses, API keys, paths)
4. Deploy — Dockge pulls `ghcr.io/brummilab/homelab-receipt-printer:latest` automatically

No cloning or building required.

### Option B — Manual (self-hosted build)

```bash
git clone https://github.com/brummilab/homelab-receipt-printer.git
cd homelab-receipt-printer
docker build -t ghcr.io/brummilab/homelab-receipt-printer:latest .
docker compose up -d
```

---

### Printer connection

**Network (LAN/Ethernet) — recommended:**  
No host setup needed. Enter the printer IP and port `9100` in the web UI after startup.

**USB:**

```bash
ls /dev/usb/lp*
# Set permissions (once):
sudo chmod a+rw /dev/usb/lp0
# Or permanently via udev (check vendor ID with lsusb):
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="04b8", MODE="0666"' | sudo tee /etc/udev/rules.d/99-printer.rules
sudo udevadm control --reload-rules
```

Uncomment the `devices:` block in `docker-compose.yml` when using USB.

---

The container prints once after ~10 seconds as a test and then runs on a cron schedule (default: daily at 06:00).

### Open the web UI

```
http://<server-ip>:8080
```

Configure and save all settings there. No further steps needed.

### Check logs

```bash
docker logs receipt-printer
docker logs -f receipt-printer
```

### Trigger manually

```bash
docker exec receipt-printer python /app/healthcheck.py
# or via the web UI: "Print Receipt"
```

## Configuration

All settings are accessible through the web UI. Environment variables in `docker-compose.yml` can be used as initial configuration — they are applied on first start if no saved configuration exists yet.

| Variable | Default | Description |
|---|---|---|
| `PRINTER_DEVICE` | `/dev/usb/lp0` | USB device path |
| `CRON_SCHEDULE` | `0 6 * * *` | Cron schedule |
| `JELLYFIN_URL` | – | Jellyfin address |
| `JELLYFIN_API_KEY` | – | Jellyfin API key |
| `IMMICH_URL` | – | Immich address |
| `IMMICH_API_KEY` | – | Immich API key |
| `PANGOLIN_URL` | – | Pangolin reverse proxy URL |
| `BACKUP_PATHS` | – | Comma-separated backup paths |
| `ADGUARD_URL` | – | AdGuard Home URL |
| `ADGUARD_USER` | – | AdGuard username |
| `ADGUARD_PASS` | – | AdGuard password |
| `TZ` | `Europe/Vienna` | Timezone |

## Project structure

```
.
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh      # Cron setup, starts web UI and initial receipt
├── config.py          # Config load/save (/config/config.json)
├── webui.py           # Flask web UI (port 8080)
├── healthcheck.py     # Main script
└── templates/
    └── index.html     # Web UI frontend
```
