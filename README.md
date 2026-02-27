# Scene Detection (SliTraNet Wrapper)

Dieses Projekt nutzt das originale SliTraNet (`./slitranet`) und ergänzt einen pragmatischen lokalen Workflow für:
- ROI-Konfiguration
- reproduzierbare Runs mit Zeitstempel-Ordnern
- lokale Web-Oberfläche

## Struktur

- `config/slitranet.env`: zentrale Konfiguration (Video + ROI)
- `videos/`: Input-Videos
- `weights/`: SliTraNet-Modelle (`*.pth`)
- `scripts/`: Run- und Hilfsskripte
- `output/runs/<YYYYmmdd_HHMMSS>/`: Ergebnisse pro Run
- `web/`: minimales Frontend + lokaler API-Server

## Voraussetzungen

- Linux/WSL mit funktionierendem CUDA für PyTorch
- vorhandenes `.venv` im Projekt
- Gewichte in `weights/`

## ROI einstellen

ROI direkt in `config/slitranet.env` setzen:
- `ROI_X0`, `ROI_Y0`, `ROI_X1`, `ROI_Y1`

Overlay zur Kontrolle erzeugen:

```bash
source .venv/bin/activate
python scripts/export_roi_overlay.py --time-sec 30
```

Output:
- `output/roi_tuning/roi_overlay.png`

## Run starten

```bash
source .venv/bin/activate
bash scripts/run_slitranet.sh
```

Der Run erzeugt einen neuen Ordner:
- `output/runs/<timestamp>/dataset/...` (temporäres SliTraNet-Layout)
- `output/runs/<timestamp>/slitranet/slide_changes.csv`
- `output/runs/<timestamp>/slitranet/keyframes/{slide,full}`

Zusätzlich:
- `output/latest` zeigt auf den neuesten Run.

## Web UI

Start:

```bash
source .venv/bin/activate
python web/server.py
```

Dann öffnen:
- `http://127.0.0.1:8000`

Details siehe:
- `web/README.md`
