# Offene Fragen vor dem Setup

Bevor wir das Album-Sync-Tool auf deiner Synology einrichten, brauche ich ein paar Infos von dir. Die Fragen sind nach Wichtigkeit sortiert — die ersten beantworten ist am wichtigsten, der Rest kann auch im Setup-Gespräch geklärt werden.

## Kritisch — ohne die Antworten geht es nicht weiter

### 1. External Library — Import Paths

Geh in Immich auf **Administration → External Libraries**, öffne die Library mit deinen NAS-Fotos und kopier mir die exakten Einträge unter **"Import Paths"** (bitte 1:1 abtippen oder kopieren, damit kein Tippfehler dazwischenkommt).

→ Diese Pfade werden in der Config eingetragen. Wenn sie nicht exakt stimmen, findet das Tool keine Fotos.

### 2. Echte Beispiel-Pfade

Schick mir **5–10 echte Beispiel-Pfade** aus deiner Library. So bekommst du sie:

- In Immich auf ein Foto klicken
- Rechts in der Detail-Ansicht steht unter "Info" der Pfad
- Den kopieren und mir schicken

**Alternativ reicht auch ein Foto / Screenshot vom Library-Browser in Immich, wo man die Ordnerstruktur sieht** — daraus erkenne ich die Struktur meistens genauso gut.

Was ich brauche, sind möglichst unterschiedliche Beispiele — verschiedene Jahre, verschiedene Verschachtelungstiefen, vielleicht auch ein paar Sonderfälle (wenn dir welche einfallen). Beispiel:

- `/photo/2026/Geburtstag-Anna/IMG_4521.jpg`
- `/photo/Familie/2024/Weihnachten/foto.heic`
- `/photo/scans/alt/oma_1972.tif`

### 3. LAN-IP von Home Assistant

Welche IP hat dein HAOS-NUC im LAN? Du erreichst Immich vermutlich über `http://<diese-ip>:2283` oder eine ähnliche URL. Schick mir die komplette URL, unter der du Immich im Browser aufrufst.

### 4. Anzahl Fotos und Videos

Wie viele Assets hat dein Immich insgesamt? (Steht in deinem Konto unter "Storage Usage" oder als Zahl in der Sidebar.) Eine grobe Größenordnung reicht — 5.000? 50.000? 200.000?

→ Bei sehr großen Bibliotheken brauchen wir evtl. einen kleinen Performance-Tweak.

## Wichtig — beeinflusst Verhalten, lässt sich aber nachjustieren

### 5. Bestehende Alben

Hast du schon manuell Alben in Immich angelegt? Wenn ja: ungefähr wie viele, und sollen die unangetastet bleiben?

→ Unser Tool legt nur neue Alben an und respektiert bestehende — ich will das nur sicher bestätigt wissen.

### 6. Ordner, die KEIN Album werden sollen

Gibt es Unterordner auf dem NAS, die du **nicht** als Album in Immich sehen willst? Zum Beispiel `Privat/`, `Backup/`, `Sortieren/`, `unsortiert/`?

→ Falls ja, müssen wir die ausschließen — sonst entstehen ungewollte Alben.

### 7. Sonderfälle in der Ordnerstruktur

Liegen bei dir manche Fotos auch direkt unter dem Jahres-Ordner ohne Album-Unterordner (z.B. `/photo/2026/einzelnes_foto.jpg` ohne Ordner dazwischen)? Falls ja: sollen die ignoriert werden, oder in ein gemeinsames Album wie "Sonstiges 2026" zusammengefasst?

## Nice to have — können wir auch später klären

### 8. HTTPS zu Immich

Läuft Immich rein intern über HTTP, oder hast du einen Reverse Proxy mit HTTPS davor (Caddy, nginx, Cloudflare Tunnel)?

### 9. Mehrere Nutzer

Nutzen mehrere Personen deine Immich-Instanz (z.B. Familie)? Sollen die neu angelegten Alben für alle sichtbar sein oder nur für dich?

→ In Immich sind Alben standardmäßig privat. Wenn andere mitlesen sollen, musst du sie nachträglich teilen.

### 10. Wie oft kommen neue Fotos dazu

Lädst du täglich neue Fotos hoch, wöchentlich, oder nur selten?

→ Das beeinflusst, wie oft das Script automatisch laufen soll (z.B. einmal täglich nachts).

### 11. SSH-Zugang auf der Synology

Hast du SSH auf der Synology aktiviert (Systemsteuerung → Terminal & SNMP), oder möchtest du nur über die DSM-Web-Oberfläche arbeiten?

→ Mit SSH ist Test und Setup deutlich einfacher. Geht aber auch per UI, ist nur etwas umständlicher.

### 12. Backup für `/volume1/docker/`

Sicherst du das `/volume1/docker/`-Verzeichnis schon (z.B. mit Hyper Backup oder Btrfs Snapshots)?

→ Das Tool speichert eine kleine State-Datei. Wenn die verloren geht, riskieren wir bei einem späteren Lauf doppelt angelegte Alben. Eine simple Snapshot-Aktivierung auf dem Shared Folder reicht.

### 13. Geo-Verfeinerung (optional)

Wenn du möchtest, kann das Tool Bilder mit EXIF-GPS zusätzlich anhand einer konfigurierten Liste von Orten in feinere Alben sortieren (z.B. `Italien – Rom` statt nur `Italien`). Dazu brauche ich pro Ort: Name, lat/lon und optional einen Radius (Default 500 m). Details siehe README, Abschnitt „Geo-Verfeinerung".

→ Komplett optional. Ohne `geo:`-Block in der Config bleibt das Verhalten wie zuvor.
