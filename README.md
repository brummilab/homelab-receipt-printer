# homelab-receipt-printer

Druckt täglich einen Thermobon mit dem Status des Homelabs auf einem ESC/POS USB-Drucker.

## Was wird geprüft

- **System**: Uptime, CPU, RAM
- **Docker**: laufende Container, unerwartete Stopps
- **ZFS**: Pool-Status
- **Backups**: Alter der Backup-Verzeichnisse (Warnung ab 48h)
- **Netzwerk**: Pangolin Reverse Proxy, DNS
- **Services**: Jellyfin, Immich

## Installation

### 1. Repo klonen

```bash
git clone https://github.com/brummilab/homelab-receipt-printer.git
cd homelab-receipt-printer
```

### 2. Drucker prüfen

USB-Drucker anschließen und prüfen, ob das Gerät erkannt wird:

```bash
ls /dev/usb/lp*
```

Berechtigungen setzen (einmalig):

```bash
sudo chmod a+rw /dev/usb/lp0
# oder dauerhaft per udev:
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="04b8", MODE="0666"' | sudo tee /etc/udev/rules.d/99-printer.rules
sudo udevadm control --reload-rules
```

> Epson-Drucker haben meist Vendor-ID `04b8`. Mit `lsusb` nachprüfen.

### 3. `docker-compose.yml` anpassen

URLs, API-Keys und Backup-Pfade eintragen:

```yaml
environment:
  - JELLYFIN_URL=http://<IP>:8096
  - JELLYFIN_API_KEY=<dein-key>
  - IMMICH_URL=http://<IP>:30041
  - PANGOLIN_URL=https://<deine-domain>
  - BACKUP_PATHS=/backups/immich,/backups/musik
```

### 4. Image bauen

```bash
docker build -t receipt-printer:latest .
```

### 5. Container starten

```bash
docker compose up -d
```

Der Container wartet 10 Sekunden, druckt dann einmalig zur Kontrolle und läuft danach per Cron (Standard: täglich 06:00).

### 6. Logs prüfen

```bash
docker logs receipt-printer
# oder dauerhaft mitverfolgen:
docker logs -f receipt-printer
```

### Manuell auslösen

```bash
docker exec receipt-printer python /app/healthcheck.py
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
