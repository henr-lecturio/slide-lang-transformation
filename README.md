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
- `faster-whisper` in `.venv` (wird durch `scripts/setup_venv.sh` installiert)

## ROI einstellen

ROI direkt in `config/slitranet.env` setzen:
- `ROI_X0`, `ROI_Y0`, `ROI_X1`, `ROI_Y1`
- `KEYFRAME_SETTLE_FRAMES`
- `KEYFRAME_STABLE_END_GUARD_FRAMES`
- `KEYFRAME_STABLE_LOOKAHEAD_FRAMES`
- `WHISPER_MODEL` (z. B. `medium`)
- `SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO`
- `SPEAKER_FILTER_MAX_EDGE_DENSITY`
- `SPEAKER_FILTER_MAX_LAPLACIAN_VAR`
- `SPEAKER_FILTER_MAX_DURATION_SEC`
- `FINAL_SLIDE_POSTPROCESS_MODE` (`none`, `local`, `gemini`)
- `GEMINI_EDIT_MODEL` (wenn `FINAL_SLIDE_POSTPROCESS_MODE=gemini`)
- `config/gemini_edit_prompt.txt` (Gemini-Edit-Prompt; auch über die Web-UI bearbeitbar)
- `FINAL_SLIDE_TRANSLATION_MODE` (`none`, `gemini`)
- `FINAL_SLIDE_TARGET_LANGUAGE`
- `GEMINI_TRANSLATE_MODEL` (wenn `FINAL_SLIDE_TRANSLATION_MODE=gemini`)
- `config/gemini_translate_prompt.txt` (Gemini-Übersetzungsprompt; auch über die Web-UI bearbeitbar)
- `FINAL_SLIDE_UPSCALE_MODE` (`none`, `swin2sr`, `replicate_nightmare_realesrgan`)
- `FINAL_SLIDE_UPSCALE_MODEL` (standardmäßig `caidas/swin2SR-classical-sr-x4-64`)
- `FINAL_SLIDE_UPSCALE_DEVICE` (`auto`, `cuda`, `cpu`)
- `FINAL_SLIDE_UPSCALE_TILE_SIZE`
- `FINAL_SLIDE_UPSCALE_TILE_OVERLAP`
- `REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF`
- `REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID`
- `REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND`
- `REPLICATE_UPSCALE_CONCURRENCY`

Für Gemini liegt der API-Key lokal in `.env.local` im Projektroot:

```bash
GEMINI_API_KEY="..."
REPLICATE_API_TOKEN="..."
```

`.env.local` ist gitignoriert und wird von `scripts/run_slitranet.sh`,
`scripts/edit_final_slides_gemini.py`, `scripts/upscale_final_slides_replicate.py`,
und `web/server.py` automatisch geladen.

Overlay zur Kontrolle erzeugen:

```bash
source .venv/bin/activate
python scripts/export_roi_overlay.py --video "videos/example.mp4" --time-sec 30
```

Output:
- `output/roi_tuning/roi_overlay.png`

## Run starten

Per CLI mit explizitem Video:

```bash
source .venv/bin/activate
bash scripts/run_slitranet.sh --video "videos/example.mp4"
```

Oder über die Web-UI:
- Video auswählen
- ROI/Parameter speichern
- Run starten

Hinweis: Beim ersten Transkriptionslauf wird das Whisper-Modell ggf. aus dem Hub geladen und lokal gecacht.

Der Run erzeugt einen neuen Ordner:
- `output/runs/<timestamp>/dataset/...` (temporäres SliTraNet-Layout)
- `output/runs/<timestamp>/slitranet/slide_changes.csv`
- `output/runs/<timestamp>/slitranet/keyframes/{slide,full}`
- `output/runs/<timestamp>/slitranet/transcript_segments.{json,csv}`
- `output/runs/<timestamp>/slitranet/slide_text_map.{json,csv}`
- `output/runs/<timestamp>/slitranet/slide_text_map_final.{json,csv}`
- `output/runs/<timestamp>/slitranet/slides_final_manifest.csv`
- `output/runs/<timestamp>/slitranet/keyframes/final/{slide,full}`
- `output/runs/<timestamp>/slitranet/keyframes/final/slide_raw`
- `output/runs/<timestamp>/slitranet/keyframes/final/slide_translated` (wenn Übersetzung aktiv ist)
- `output/runs/<timestamp>/slitranet/keyframes/final/slide_upscaled` (wenn Upscaling aktiv ist)
- `output/runs/<timestamp>/slitranet/keyframes/final/slide_translated_upscaled` (wenn Übersetzung + Upscaling aktiv sind)
- `output/runs/<timestamp>/slitranet/keyframes/final/upscale_manifest.json` (bei API-Upscaling)

Hinweis: Beim ersten Upscale-Run lädt `transformers` das Swin2SR-Modell von Hugging Face und cached es lokal.

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
