# homelab-receipt-printer

Druckt täglich einen Thermobon mit dem Status des Homelabs auf einem ESC/POS USB-Drucker.

## Was wird geprüft

- **System**: Uptime, CPU, RAM
- **Docker**: laufende Container, unerwartete Stopps
- **ZFS**: Pool-Status
- **Backups**: Alter der Backup-Verzeichnisse (Warnung ab 48h)
- **Netzwerk**: Pangolin Reverse Proxy, DNS
- **Services**: Jellyfin, Immich

## Setup

### Voraussetzungen

- Docker & Docker Compose
- ESC/POS Drucker unter `/dev/usb/lp0`

### Image bauen

```bash
docker build -t receipt-printer:latest .
```

### Starten

```bash
docker compose up -d
```

## Konfiguration

Alle Einstellungen werden über Umgebungsvariablen in der `docker-compose.yml` gesetzt:

| Variable | Standard | Beschreibung |
|---|---|---|
| `PRINTER_DEVICE` | `/dev/usb/lp0` | USB-Gerätepfad des Druckers |
| `CRON_SCHEDULE` | `0 6 * * *` | Cron-Zeitplan (täglich 06:00) |
| `JELLYFIN_URL` | – | Jellyfin-Adresse |
| `JELLYFIN_API_KEY` | – | Jellyfin API-Key |
| `IMMICH_URL` | – | Immich-Adresse |
| `PANGOLIN_URL` | – | Pangolin Reverse Proxy URL |
| `BACKUP_PATHS` | – | Kommagetrennte Backup-Pfade |
| `TZ` | `Europe/Vienna` | Zeitzone |

## Projektstruktur

```
.
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh     # Cron-Setup und erster Start
└── healthcheck.py    # Hauptskript
```
