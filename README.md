# homelab-receipt-printer

Druckt täglich einen Thermobon mit dem Homelab-Status auf einem ESC/POS Thermodrucker.  
Alle Einstellungen über eine Web UI konfigurierbar — kein Editieren von Dateien nötig.

## Was wird geprüft

| Sektion | Inhalt |
|---|---|
| **System** | Uptime, CPU-Last, RAM-Auslastung |
| **Docker** | Jeder Container einzeln: Name + Status (running / stopped / unhealthy) |
| **ZFS** | Pool-Status (ONLINE / degraded) |
| **Disk** | Füllstand konfigurierter Mountpoints, WARN ab einstellbarem %, FAIL ab 95 % |
| **Backups** | Alter der Backup-Verzeichnisse, WARN ab konfigurierbaren Stunden |
| **Netzwerk** | DNS-Auflösung, Pangolin Reverse Proxy |
| **Services** | Jellyfin, Immich (mit API-Key) |
| **Websites** | HTTP-Status + Antwortzeit beliebiger URLs |
| **AdGuard Home** | DNS-Anfragen heute, blockierte Anfragen + Blockierrate |

Alle Sektionen können einzeln ein- oder ausgeschaltet werden.

## Web UI

Erreichbar unter `http://<server-ip>:8080` nach dem Start.

- Drucker-Backend wählen (USB oder Netzwerk/LAN)
- Logo hochladen (wird oben auf dem Bon gedruckt)
- Sektionen ein-/ausschalten
- Service-URLs und API-Keys eintragen (Jellyfin, Immich, AdGuard)
- Websites zur Überwachung hinzufügen
- Backup-Pfade und Disk-Mountpoints verwalten
- Cron-Zeitplan setzen
- **Status Vorschau** — alle Checks live ausführen ohne zu drucken
- „Bon drucken" — sofort manuell auslösen

Die Konfiguration wird in einem Docker-Volume unter `/config/config.json` gespeichert.

## Installation

### 1. Repo klonen

```bash
git clone https://github.com/brummilab/homelab-receipt-printer.git
cd homelab-receipt-printer
```

### 2. Drucker anschließen

**USB:**

```bash
ls /dev/usb/lp*
# Berechtigungen setzen (einmalig):
sudo chmod a+rw /dev/usb/lp0
# oder dauerhaft per udev (Epson Vendor-ID 04b8, mit lsusb prüfen):
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="04b8", MODE="0666"' | sudo tee /etc/udev/rules.d/99-printer.rules
sudo udevadm control --reload-rules
```

**Netzwerk (LAN/Ethernet):**  
Kein Setup nötig — IP-Adresse und Port `9100` werden in der Web UI eingetragen.

### 3. Image bauen

```bash
docker build -t receipt-printer:latest .
```

### 4. Container starten

```bash
docker compose up -d
```

Der Container druckt nach ~10 Sekunden einmalig zur Kontrolle und läuft danach per Cron (Standard: täglich 06:00).

### 5. Web UI öffnen

```
http://<server-ip>:8080
```

Dort alle Einstellungen vornehmen und speichern. Keine weiteren Schritte nötig.

### Logs prüfen

```bash
docker logs receipt-printer
docker logs -f receipt-printer
```

### Manuell auslösen

```bash
docker exec receipt-printer python /app/healthcheck.py
# oder über die Web UI: „Bon drucken"
```

## Konfiguration

Alle Einstellungen sind über die Web UI zugänglich. Als Startkonfiguration können Umgebungsvariablen in der `docker-compose.yml` gesetzt werden — diese werden beim ersten Start übernommen, sofern noch keine gespeicherte Konfiguration existiert.

| Variable | Standard | Beschreibung |
|---|---|---|
| `PRINTER_DEVICE` | `/dev/usb/lp0` | USB-Gerätepfad |
| `CRON_SCHEDULE` | `0 6 * * *` | Cron-Zeitplan |
| `JELLYFIN_URL` | – | Jellyfin-Adresse |
| `JELLYFIN_API_KEY` | – | Jellyfin API-Key |
| `IMMICH_URL` | – | Immich-Adresse |
| `IMMICH_API_KEY` | – | Immich API-Key |
| `PANGOLIN_URL` | – | Pangolin Reverse Proxy URL |
| `BACKUP_PATHS` | – | Kommagetrennte Backup-Pfade |
| `ADGUARD_URL` | – | AdGuard Home URL |
| `ADGUARD_USER` | – | AdGuard Benutzername |
| `ADGUARD_PASS` | – | AdGuard Passwort |
| `TZ` | `Europe/Vienna` | Zeitzone |

## Projektstruktur

```
.
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh      # Cron-Setup, startet Web UI und ersten Bon
├── config.py          # Config laden/speichern (/config/config.json)
├── webui.py           # Flask Web UI (Port 8080)
├── healthcheck.py     # Hauptskript
└── templates/
    └── index.html     # Web UI Frontend
```
