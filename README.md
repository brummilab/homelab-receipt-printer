# homelab-receipt-printer

Prints a daily thermal receipt with homelab status on an ESC/POS thermal printer.  
All settings configurable through a web UI — no file editing required.

## What is checked

| Section | Content |
|---|---|
| **System** | Uptime, CPU load, RAM usage |
| **Docker** | Each container individually: name + status (running / stopped / unhealthy) |
| **ZFS** | Pool status via TrueNAS REST API (ONLINE / degraded) |
| **Disk** | Usage of configured mount points, WARN at configurable %, FAIL at 95% |
| **Backups** | Age of backup directories, WARN after configurable hours |
| **Network** | DNS resolution, Pangolin reverse proxy reachability |
| **Websites** | HTTP status + response time for arbitrary URLs |
| **AdGuard Home** | DNS queries today, blocked queries + block rate |

All sections can be individually enabled or disabled.

## Web UI

Available at `http://<server-ip>:8085` after startup.

- Choose printer backend (USB or Network/LAN)
- Upload logo (printed at the top of the receipt)
- Enable/disable sections
- Configure TrueNAS, AdGuard Home, Pangolin URLs and credentials
- Add websites to monitor
- Manage backup paths and disk mount points
- Set cron schedule (with enable/disable toggle)
- **Status Preview** — run all checks live without printing
- **Print Receipt** — trigger manually at any time
- **Export / Import** config as JSON (action bar)

Configuration is stored at `./config/config.json` (bind mount, survives stack removal).

## Installation

```bash
cd /mnt/tank/configs
git clone https://github.com/brummilab/homelab-receipt-printer.git
cd homelab-receipt-printer
docker compose up -d --build
```

Open the web UI at `http://<server-ip>:8085` and configure everything there.

### Automatic updates via cron

```bash
# crontab -e on TrueNAS
0 3 * * * cd /mnt/tank/configs/homelab-receipt-printer && git pull && docker compose up -d --build >> /var/log/receipt-update.log 2>&1
```

### Printer connection

**Network (LAN/Ethernet) — recommended:**  
No host setup needed. Enter the printer IP and port `9100` in the web UI.

**USB:**  
Uncomment the `devices:` block in `docker-compose.yml`, then set permissions:

```bash
sudo chmod a+rw /dev/usb/lp0
```

### Useful commands

```bash
docker logs -f receipt-printer                    # live logs
docker exec receipt-printer python /app/healthcheck.py  # manual print
```

## Configuration

All settings are managed through the web UI. The only environment variable needed is `TZ`.

Use **Export** in the action bar to back up your config, and **Import** to restore it.

| Variable | Default | Description |
|---|---|---|
| `TZ` | `Europe/Vienna` | Timezone |

## Project structure

```
.
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh      # Cron setup, starts web UI
├── config.py          # Config load/save (./config/config.json)
├── webui.py           # Flask web UI (port 8080 → exposed as 8085)
├── healthcheck.py     # Health checks + receipt printing
└── templates/
    └── index.html     # Web UI frontend
```
