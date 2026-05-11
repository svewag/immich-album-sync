# immich-alben

Erstellt automatisch Immich-Alben aus der Ordnerstruktur einer External Library.
Nur ergänzend, niemals löschend. Idempotent (kann beliebig oft laufen).

## Funktionsweise

1. Holt alle Assets aus Immich per API.
2. Matched den `originalPath` jedes Assets gegen ein konfigurierbares Template-Pattern (z.B. `{root}/{year}/{album}`).
3. Gruppiert pro `(Jahr, Albumname)` und legt fehlende Alben an / fügt fehlende Assets hinzu.
4. Speichert das Mapping `(Jahr, Album) → Album-UUID` in einer State-Datei, damit die Zuordnung über Läufe stabil bleibt.

## Was das Tool kann — und was nicht

**Kann:**
- Neue Alben in Immich anlegen
- Bestehenden Alben fehlende Assets hinzufügen

**Kann strukturell nicht** (im API-Client als Whitelist verdrahtet, durch Tests abgesichert):
- Alben löschen, umbenennen oder verändern
- Assets löschen, in den Papierkorb verschieben oder modifizieren
- Assets aus Alben entfernen
- Dateien auf dem NAS-Filesystem ändern (das NAS ist im Container gar nicht eingebunden)

Selbst eine versehentliche Code-Änderung würde einen schreibenden API-Call gegen einen nicht-whitelisteten Endpoint **bevor** der HTTP-Request rausgeht abbrechen. Bei `--dry-run` sind zusätzlich auch alle erlaubten Writes blockiert.

## Voraussetzungen

- Immich >= v1.106 (API-Pfade — bei abweichender Version siehe `src/immich_alben/immich.py`).
- Fotos in Immich liegen als **External Library**, d.h. `originalPath` enthält den echten NAS-Pfad.
- Ein Immich API-Key (Profil → API Keys).
- Netzwerk-Zugriff vom Host (z.B. Synology) auf die Immich-Instanz.

## Konfiguration

`config.yaml`:

```yaml
immich:
  base_url: "http://192.168.1.50:2283"   # IP des HAOS-NUC im LAN

library_roots:
  - "/mnt/photos"

patterns:
  - "{root}/{year}/{album}"
  - "{root}/{year}/{album}/{*}"

state_file: "/data/state.json"

logging:
  level: "INFO"
```

### Pattern-Platzhalter

| Platzhalter | Bedeutung |
|---|---|
| `{root}` | Wird durch jeden `library_roots`-Eintrag ersetzt |
| `{year}` | Genau 4 Ziffern (z.B. 2026) |
| `{album}` | Verzeichnis-Segment, wird als Album-Name benutzt |
| `{*}` | 1+ Pfad-Segmente (für tiefere Verschachtelungen) |

Wichtig: `{album}` ist **immer** ein Verzeichnis-Segment; danach folgt entweder direkt der Dateiname oder ein `{*}` (oder weitere Literale).

### API-Key

Wird als Env-Var `IMMICH_API_KEY` übergeben (nicht in `config.yaml`).

## Synology Setup

> Hinweis: Synology nennt das Docker-Tool **Container Manager** (DSM 7.2+), früher hieß es nur "Docker". Beide bieten eine UI für docker-compose-"Projekte". Im Folgenden wird der UI-Weg beschrieben; eine SSH-Variante folgt am Ende.

### 1. Verzeichnis und Dateien

In **File Station** (DSM):

1. Verzeichnis anlegen: `/docker/immich-alben/` (vollständiger Pfad i.d.R. `/volume1/docker/immich-alben/`)
2. Unter-Verzeichnis `state/` anlegen
3. Inhalt dieses Repos in das Verzeichnis hochladen:

```
/volume1/docker/immich-alben/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── src/                  (gesamter src-Ordner)
├── config.yaml           (selbst aus config.example.yaml erstellen, mit echten Werten)
└── state/                (leer, wird automatisch befüllt)
```

`config.yaml` mit der echten Immich-URL und dem echten Mount-Pfad der External Library füllen.

### 2. API-Key als Env-Var-Datei

Im selben Verzeichnis eine Datei `.env` anlegen mit Inhalt:
```
IMMICH_API_KEY=dein-immich-api-key
```

> Falls Synology File Station versteckte Dateien (mit Punkt vorne) ausblendet: in den File-Station-Einstellungen "Versteckte Dateien anzeigen" aktivieren, oder die Datei als `env.txt` anlegen und im Container Manager beim Project-Setup als `.env`-Pfad explizit auswählen.

### 3. Projekt im Container Manager anlegen

**Container Manager** öffnen → linke Leiste **Projekt** → **Erstellen**:

- **Projektname:** `immich-alben`
- **Pfad:** `/volume1/docker/immich-alben` (per "Festlegen"-Button auswählen)
- **Quelle:** "Vorhandene docker-compose.yml verwenden" (die liegt schon dort)
- **Bearbeitungsschritte:** *Weiter* — der Inhalt der `docker-compose.yml` wird angezeigt, keine Änderung nötig
- **Web Portal:** überspringen (das Tool hat keine Web-UI)
- **Aktion nach Build:** "Container nicht starten" wählen (wir wollen run-once, kein Dauerbetrieb)
- **Bauen:** *Fertig* → Synology baut das Image. Beim ersten Mal dauert das ~1 Minute.

> Die `docker-compose.yml` nutzt den Default-Bridge-Netzwerk-Modus. Der Container erreicht Immich über die LAN-IP des HAOS-NUC (steht in `config.yaml` als `immich.base_url`). Vor dem ersten Lauf testen, dass die Synology das HAOS erreicht: per SSH `curl http://<haos-ip>:2283/api/server/ping` — sollte `{"res":"pong"}` o.ä. liefern.

### 4. Test-Lauf (Stufe 1 — Dry-Run mit Path-Filter)

Run-once-Ausführungen mit Argumenten gehen am einfachsten via SSH. In DSM SSH-Zugang aktivieren (Systemsteuerung → Terminal & SNMP), dann:

```bash
ssh admin@<synology-ip>
cd /volume1/docker/immich-alben
sudo docker compose run --rm immich-alben-sync --dry-run --only-path "2026/Geburtstagsfeier"
```

Output prüfen: Pre-flight OK? Sieht der geplante Album-Inhalt plausibel aus?

> Alternativ ohne SSH über Container Manager: Beim Projekt-Container das Image anwählen → **Aktion** → **Ausführen** → in den erweiterten Einstellungen den Befehl-Override eintragen: `--dry-run --only-path "2026/Geburtstagsfeier"`. Nach dem Lauf das Container-Log einsehen.

### 5. Echt-Lauf für einen Ordner (Stufe 2)

```bash
sudo docker compose run --rm immich-alben-sync --only-path "2026/Geburtstagsfeier"
```

In der Immich-UI verifizieren: stimmt das Album?

### 6. Voller Dry-Run (Stufe 3)

```bash
sudo docker compose run --rm immich-alben-sync --dry-run
```

### 7. Voller Echt-Lauf (Stufe 4)

```bash
sudo docker compose run --rm immich-alben-sync
```

### 8. Automatisch täglich laufen lassen (DSM Task Scheduler)

**Systemsteuerung** → **Aufgabenplaner** → **Erstellen** → **Geplante Aufgabe** → **Benutzerdefiniertes Skript**:

- **Aufgabe:** `Immich-Alben-Sync`
- **Benutzer:** `root` (damit `docker compose` ohne sudo läuft)
- **Zeitplan:** z.B. täglich 03:30 (nach dem Immich-Library-Scan)
- **Aufgabeneinstellungen → Benutzerdefinierter Skript:**
  ```bash
  cd /volume1/docker/immich-alben && /usr/local/bin/docker compose run --rm immich-alben-sync
  ```
- **Benachrichtigung per E-Mail** bei Fehler aktivieren (oben in der Aufgabe), damit du mitkriegst, falls API-Key abläuft o.ä.

> Der Pfad zur `docker`-Binary kann je nach DSM-Version variieren: `/usr/local/bin/docker` (DSM 7.2+) oder `/usr/bin/docker`. Mit `which docker` per SSH den richtigen Pfad ermitteln.

### Update auf neue Version

Wenn der Quellcode aktualisiert wird (z.B. neue Immich-API-Pfade):

1. Dateien per File Station überschreiben
2. Container Manager → Projekt `immich-alben` → **Bauen** (rebuilt das Image)
3. State-Datei bleibt erhalten (liegt in `state/`)

## CLI

```
immich-alben [--config CONFIG] [--dry-run] [--only-path SUBSTRING]
```

- `--config PATH` — Pfad zur config.yaml (Default: `/config/config.yaml` oder `$IMMICH_ALBEN_CONFIG`)
- `--dry-run` — Zeigt geplante Aktionen, schreibt nichts.
- `--only-path SUBSTRING` — Nur Assets, deren `originalPath` den Substring enthält.

## Entwicklung

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

## State-Datei

JSON-Format (`state.json`):
```json
{
  "version": 1,
  "albums": [
    {"year": "2026", "album": "Geburtstagsfeier", "uuid": "abc-123"}
  ]
}
```

Wenn die Datei gelöscht wird, legt der nächste Lauf alle Alben **neu** an — auch wenn sie in Immich schon existieren. Datei deshalb sichern (Synology-Backup-Verzeichnis nutzen).

## Troubleshooting

### Pre-flight: `Immich reachable: NO`

Der Container kann die Immich-Instanz nicht erreichen.

- **IP prüfen:** Stimmt `immich.base_url` in der `config.yaml`? Die IP ist die des HAOS-NUC im LAN, nicht die der Synology.
- **Erreichbarkeit testen:** Per SSH auf der Synology: `curl -v http://<haos-ip>:2283/api/server/ping` — sollte HTTP 200 mit JSON liefern. Falls Timeout → Firewall oder falsche IP.
- **Port prüfen:** Standard ist `2283`. Bei HAOS-Addons sieht man den exponierten Port in den Addon-Einstellungen.
- **HTTP vs HTTPS:** Wenn Immich via Reverse Proxy mit HTTPS läuft, in der Config `https://...` schreiben (und ein gültiges Zertifikat haben).

### Pre-flight: `API key valid: NO`

- **Key kopieren:** Achte beim Kopieren des API-Keys aus der Immich-UI auf führende/abschließende Leerzeichen.
- **Key neu erzeugen:** In Immich → Account Settings → API Keys → ggf. alten Key löschen und neuen erzeugen.
- **Env-Var-Datei:** Die `.env`-Datei muss exakt `IMMICH_API_KEY=...` enthalten, ohne Anführungszeichen, ohne Leerzeichen um `=`.

### Pre-flight: `Pattern sample: 0/50 matched`

Das Tool sieht Assets, aber keiner matched die Pattern — meistens stimmt der konfigurierte `library_root` nicht mit dem echten Mount-Pfad in Immich überein.

- **Echten Pfad finden:** In Immich → Administration → External Libraries → die Library öffnen → die unter "Import Paths" eingetragenen Pfade sind die `library_roots`-Werte für die `config.yaml`.
- **Sample im Output anschauen:** Pre-flight zeigt 5 Beispiel-Pfade von Assets, die nicht matchen. Vergleiche mit deinem `library_roots`-Eintrag — meist sieht man den Unterschied sofort.
- **Pattern-Tiefe prüfen:** Wenn deine Ordner tiefer verschachtelt sind als `{root}/{year}/{album}`, ergänze ein zweites Pattern mit `{*}`.

### `docker compose: command not found` im Task Scheduler

Der Task Scheduler nutzt eine minimale Shell-Umgebung ohne `PATH`-Defaults.
- Vollständigen Pfad zur Binary nutzen: per SSH `which docker` ausführen und das Ergebnis (z.B. `/usr/local/bin/docker`) im Skript verwenden.

### Container Manager: Image baut, aber Container schlägt sofort fehl

- Im Container Manager das **Container-Log** öffnen — der Fehler ist meist die letzte Zeile.
- Häufige Ursachen: `.env`-Datei fehlt oder leer, `config.yaml` mit Syntax-Fehler, falsche Volume-Pfade.

### Alben werden doppelt angelegt

Die State-Datei wurde zwischen den Läufen gelöscht oder ist nicht mountbar.
- Prüfen: `ls -la /volume1/docker/immich-alben/state/` muss `state.json` zeigen, nachdem ein Echt-Lauf durchgelaufen ist.
- Volume in `docker-compose.yml` zeigt auf `./state` — relativ zum Compose-Verzeichnis. Falls die Synology das Project an anderer Stelle verarbeitet, absoluten Pfad eintragen.

### State-Datei sichern

Damit nach einem Datenverlust keine Duplikat-Alben entstehen, die State-Datei in eine gesicherte Lokation legen:
- **Hyper Backup** auf `/volume1/docker/immich-alben/state/` einrichten, **oder**
- Snapshot-Ordner mit `Btrfs Snapshots` aktiviert (in DSM unter Speicher-Manager → Shared Folder → Snapshots).

## Bekannte Einschränkungen

- API-Pfade in `src/immich_alben/immich.py` sind auf Immich >= v1.106 ausgelegt. Bei größeren API-Brüchen müssen die Konstanten am Modulanfang angepasst werden.
- Bei sehr großen Bibliotheken (>50k Assets) wird jeder Lauf alle Assets durchlaufen — das ist Absicht (idempotent), kann aber dauern.
