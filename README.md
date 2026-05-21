# homelab-receipt-printer

A Docker container that prints a daily homelab health report on a thermal receipt printer.  
All settings configurable through a dark web UI — no file editing required.

![Web UI](https://img.shields.io/badge/Web_UI-port_8085-2d7ef7)
![ESC/POS](https://img.shields.io/badge/Printer-ESC%2FPOS-green)
![Python](https://img.shields.io/badge/Python-3.12-blue)

---

## What gets printed

| Section | Content |
|---|---|
| **System** | Uptime, CPU load, RAM usage |
| **Docker** | Every managed container: name + status (running / stopped / unhealthy) |
| **ZFS** | Pool status via TrueNAS REST API (ONLINE / degraded) |
| **Disk** | Mount point usage, configurable WARN %, FAIL at 95% |
| **Backups** | Age of backup directories, WARN after configurable hours |
| **Network** | DNS resolution, reverse proxy reachability |
| **Websites** | HTTP status + response time for any URL |
| **AdGuard Home** | DNS queries today, blocked count + block rate |
| **Tip / Trinkgeld** | Optional: custom message + QR code for donations (Ko-fi, PayPal, …) |

All sections can be individually enabled or disabled. Values are right-aligned for easy scanning:

```
  Uptime             3d 12h
  CPU                    2%
  RAM        4.1/16.0GB 26%
!! jellyfin       unreachable
```

## Web UI

Available at `http://<server-ip>:8085` after startup.

- Printer backend: USB or Network/LAN (ESC/POS port 9100)
- Upload a logo — printed at the top of every receipt
- Enable/disable individual sections
- Configure TrueNAS API, AdGuard Home, Pangolin, websites, backup paths, disk mounts
- Schedule toggle with cron expression (automatic daily print)
- **Only print on issues** — skip receipt when all checks pass, print only on WARN/FAIL
- **Status Preview** — run all checks live in the browser without printing
- **Print Now** — trigger a receipt manually at any time
- **Export / Import** config as JSON
- **Tip / Trinkgeld** — optional donation prompt with QR code at the bottom of each receipt (Ko-fi, PayPal, GitHub Sponsors, …)

Configuration is stored in `./config/config.json` and survives container rebuilds.

## Hardware

Any ESC/POS thermal printer works. Tested with:

- **NetumScan 80mm** ([Amazon](https://www.amazon.de/dp/B0CJ6V4TYP)) — ~35 €, USB + Ethernet, recommended
- Any other 80mm ESC/POS printer (Epson TM series, Xprinter, etc.)

**Network/LAN printers are recommended** — no USB passthrough needed, works from any host.

## Installation

```bash
git clone https://github.com/brummilab/homelab-receipt-printer.git
cd homelab-receipt-printer
docker compose up -d --build
```

Open `http://<server-ip>:8085` and configure everything through the web UI.

### TrueNAS / automatic updates

```bash
# Clone to your config directory
cd /mnt/tank/configs
git clone https://github.com/brummilab/homelab-receipt-printer.git

# Auto-update via cron (TrueNAS: System → Advanced → Cron Jobs)
0 3 * * * cd /mnt/tank/configs/homelab-receipt-printer && git pull && docker compose up -d --build
```

### Printer setup

**Network (recommended):** Enter IP + port `9100` in the web UI — nothing else needed.

**USB:** Uncomment the `devices:` block in `docker-compose.yml`, then:
```bash
sudo chmod a+rw /dev/usb/lp0
```

### Useful commands

```bash
docker logs -f receipt-printer                          # live logs
docker exec receipt-printer python /app/healthcheck.py  # trigger manually
```

## Configuration

Everything is managed through the web UI. The only environment variable is `TZ` (timezone).

Use **Export** in the action bar to back up your config as JSON, and **Import** to restore it.

## Project structure

```
.
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh      # Cron setup, starts web UI
├── config.py          # Config load/save (./config/c