# Web UI

## Start

```bash
source .venv/bin/activate
.venv/bin/python web/server.py
```

Open:
- `http://127.0.0.1:8000`

## Tabs

### Home
- Video auswählen
- Run starten oder stoppen
- Step-Status der Pipeline sehen
- Terminal-Log als Popup öffnen
- neuesten Run und dessen aktuell verfügbaren Artefaktstand sehen

### All Runs
- ältere Runs durchsuchen
- Final-Slides, Base Events, CSV-Vorschau und Export-Artefakte ansehen

### ROI
- ROI-Werte bearbeiten
- ROI-Overlay erzeugen und aktualisieren

### Settings
- Pipeline Schritt für Schritt konfigurieren
- Health-Checks für:
  - Google Speech
  - Slide Edit
  - Slide Translate
  - Slide Upscale
  - Text Translate
  - TTS

### Image Lab
- einzelne Final-Slides testen
- Slide Edit / Slide Translate / Slide Upscale auf einem Einzelbild ausführen
- Original und Ergebnis direkt vergleichen

## Wichtige Funktionen

- pro Run Live-Step-Status mit Spinner/Häkchen
- `Stop Run` für laufende Jobs
- direkte Download-Links für:
  - übersetzten Text
  - TTS-Manifest
  - Timeline
  - Untertitel
  - exportiertes MP4
- Compare-Ansichten für:
  - native vs. x4
  - raw vs. processed vs. translated
- per-Slide Anzeige:
  - ROI oder Fullframe
  - automatische oder manuelle Quelle

## Hinweise

- `Latest Output` bezieht sich auf den neuesten Run und zeigt auch partielle Ergebnisse bei späteren Pipeline-Fehlern.
- Viele Buttons nutzen ein kurzes Success-Feedback direkt in der UI.
- Änderungen in `Settings` und `ROI` müssen gespeichert werden, bevor sie für neue Runs gelten.
