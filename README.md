# Slide Detection (SliTraNet Wrapper)

Dieses Projekt nutzt das originale SliTraNet unter `./slitranet` und ergänzt einen lokalen Workflow für:
- Slide Detection mit festem ROI
- Transkription und Mapping auf Slides
- optionale Slide-Nachbearbeitung, Übersetzung und Upscaling
- Textübersetzung, TTS und Export eines narratierten Slide-Videos
- lokale Web-UI für Runs, Konfiguration und Tests

## Struktur

- `config/slitranet.env`: zentrale Run-Konfiguration
- `config/prompts/`: Prompt-Dateien für Gemini/Text/TTS
- `config/language/`: Sprachkatalog und Termbase
- `videos/`: Input-Videos
- `weights/`: SliTraNet-Gewichte (`*.pth`)
- `scripts/`: Run-Skripte, Pipeline-Stufen, Provider und Tools
- `output/runs/<YYYY-MM-DD_HH-MM-SS>/`: Ergebnisse pro Run
- `output/translation_memory/translation_memory.sqlite`: automatisch gepflegtes Translation Memory
- `web/`: lokaler API-Server und Frontend

## Voraussetzungen

- Linux oder WSL mit funktionierendem CUDA-Stack für die lokale Slide Detection
- `python3` und `python3-venv`
- `ffmpeg` im `PATH`
- Docker nur dann, wenn du zusätzlich den separaten Replicate/Cog-Detection-Pfad testest
- die drei produktiv genutzten Gewichte in `weights/`:
  - `Frame_similarity_ResNet18_gray.pth`
  - `Slide_video_detection_3DResNet50.pth`
  - `Slide_transition_detection_3DResNet50.pth`

## Quickstart

1. Virtualenv und Dependencies aufsetzen:

```bash
bash scripts/setup_venv.sh
```

2. ROI-Overlay für ein Video erzeugen:

```bash
source .venv/bin/activate
python scripts/tools/export_roi_overlay.py --video "videos/example.mp4" --time-sec 30
```

Ergebnis:
- `output/roi_tuning/roi_overlay.png`

3. Run per CLI starten:

```bash
source .venv/bin/activate
bash scripts/run_slitranet.sh --video "videos/example.mp4"
```

4. Web-UI starten:

```bash
source .venv/bin/activate
.venv/bin/python web/server.py
```

Dann öffnen:
- `http://127.0.0.1:8000`

## Konfiguration

Die zentrale Konfiguration liegt in:
- `config/slitranet.env`

Wichtige Blöcke:

### ROI und Keyframes
- `ROI_X0`, `ROI_Y0`, `ROI_X1`, `ROI_Y1`
- `KEYFRAME_SETTLE_FRAMES`
- `KEYFRAME_STABLE_END_GUARD_FRAMES`
- `KEYFRAME_STABLE_LOOKAHEAD_FRAMES`

### Slide Detection
- `PHASE`
- `FINAL_SOURCE_MODE_AUTO`
- `FULLSLIDE_*`

### Transcription
- `TRANSCRIPTION_PROVIDER` (`whisper`, `google_chirp_3`)
- Whisper:
  - `WHISPER_MODEL`
  - `WHISPER_DEVICE`
  - `WHISPER_COMPUTE_TYPE`
  - `WHISPER_LANGUAGE`
- Google Speech:
  - `GOOGLE_SPEECH_PROJECT_ID`
  - `GOOGLE_SPEECH_LOCATION`
  - `GOOGLE_SPEECH_MODEL`
  - `GOOGLE_SPEECH_LANGUAGE_CODES`
  - `GOOGLE_SPEECH_CHUNK_SEC`
  - `GOOGLE_SPEECH_CHUNK_OVERLAP_SEC`

### Finalize Slides / Speaker Filter
- `SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO`
- `SPEAKER_FILTER_MAX_EDGE_DENSITY`
- `SPEAKER_FILTER_MAX_LAPLACIAN_VAR`
- `SPEAKER_FILTER_MAX_DURATION_SEC`

### Slide Edit / Slide Translate
- `FINAL_SLIDE_POSTPROCESS_MODE` (`none`, `local`, `gemini`)
- `GEMINI_EDIT_MODEL`
- `config/prompts/gemini_edit_prompt.txt`
- `FINAL_SLIDE_TRANSLATION_MODE` (`none`, `gemini`)
- `FINAL_SLIDE_TARGET_LANGUAGE`
- `GEMINI_TRANSLATE_MODEL`
- `config/prompts/gemini_translate_prompt.txt`

### Slide Upscale
- `FINAL_SLIDE_UPSCALE_MODE` (`none`, `swin2sr`, `replicate_nightmare_realesrgan`)
- `FINAL_SLIDE_UPSCALE_MODEL`
- `FINAL_SLIDE_UPSCALE_DEVICE`
- `FINAL_SLIDE_UPSCALE_TILE_SIZE`
- `FINAL_SLIDE_UPSCALE_TILE_OVERLAP`
- `REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF`
- `REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID`
- `REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND`
- `REPLICATE_UPSCALE_CONCURRENCY`

### Transcript Translate / TTS / Video Export
- Step-Toggles:
  - `RUN_STEP_TEXT_TRANSLATE`
  - `RUN_STEP_TTS`
  - `RUN_STEP_VIDEO_EXPORT`
- Transcript Translate:
  - `GEMINI_TEXT_TRANSLATE_MODEL`
  - `config/prompts/gemini_text_translate_prompt.txt`
- TTS:
  - `GEMINI_TTS_MODEL`
  - `GEMINI_TTS_VOICE`
  - `GOOGLE_TTS_PROJECT_ID`
  - `GOOGLE_TTS_LANGUAGE_CODE`
  - `config/prompts/gemini_tts_prompt.txt`
- Video Export:
  - `VIDEO_EXPORT_MIN_SLIDE_SEC`
  - `VIDEO_EXPORT_TAIL_PAD_SEC`
  - `VIDEO_EXPORT_WIDTH`
  - `VIDEO_EXPORT_HEIGHT`
  - `VIDEO_EXPORT_FPS`
  - `VIDEO_EXPORT_BG_COLOR`

Hinweis:
- Slide Detection, Transcription und Transcript Mapping laufen immer.
- Die späteren Postprocess-Schritte können für Testläufe deaktiviert werden.

## Provider / Secrets

Lokale Secrets liegen in:
- `.env.local`

Typische Einträge:

```bash
GEMINI_API_KEY="..."
REPLICATE_API_TOKEN="..."
# Optional for Google Cloud ADC:
# GOOGLE_APPLICATION_CREDENTIALS="/abs/path/to/service-account.json"
```

`.env.local` ist gitignoriert und wird von:
- `scripts/run_slitranet.sh`
- `web/server.py`
- den Provider-Skripten

automatisch geladen.

## Google APIs und Auth

### Google Speech (`google_chirp_3`)

Wenn `TRANSCRIPTION_PROVIDER=google_chirp_3` genutzt wird, brauchst du:

1. gültige Application Default Credentials:

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project <PROJECT_ID>
```

2. aktivierte APIs im Google-Cloud-Projekt:
- `speech.googleapis.com`

3. passende Projektkonfiguration:
- `GOOGLE_SPEECH_PROJECT_ID`

### Google Cloud TTS (`gemini-2.5-flash-tts`)

Wenn `RUN_STEP_TTS=1` genutzt wird, brauchst du:

1. gültige Application Default Credentials:

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project <PROJECT_ID>
```

2. aktivierte APIs im Google-Cloud-Projekt:
- `texttospeech.googleapis.com`
- `aiplatform.googleapis.com`

3. die Projekt-ID in der Konfiguration:
- `GOOGLE_TTS_PROJECT_ID`

4. einen Principal mit ausreichenden Rechten auf das Projekt
- mindestens so, dass das Projekt als Quota-/Billing-Projekt genutzt werden darf

Hinweis:
- Der TTS-Health-Check in der Web-UI ist der schnellste Weg, das Setup zu prüfen.

## Translation Memory und Termbase

Das Projekt nutzt zwei getrennte Konzepte:

1. **Termbase**
- Datei: `config/language/translation_termbase.csv`
- manuell gepflegt
- für feste Terminologie und gewünschte Zielbegriffe

2. **Translation Memory**
- Datei: `output/translation_memory/translation_memory.sqlite`
- wird durch Textübersetzungs-Runs automatisch befüllt
- wiederverwendet bereits übersetzte Segmente

Wichtig:
- **Transcript Translate** nutzt echtes Translation Memory + Termbase
- **Slide Translate** nutzt nur die Termbase als Glossarhinweis im Prompt

Bestehende Runs ins TM übernehmen:

```bash
source .venv/bin/activate
python scripts/tools/rebuild_translation_memory.py
```

## Outputs

Ein Run erzeugt einen neuen Ordner:
- `output/runs/<timestamp>/dataset/...`
- `output/runs/<timestamp>/slitranet/slide_changes.csv`
- `output/runs/<timestamp>/slitranet/keyframes/{slide,full}`
- `output/runs/<timestamp>/slitranet/transcript_segments.{json,csv}`
- `output/runs/<timestamp>/slitranet/transcript_segments_translated.{json,csv}`
- `output/runs/<timestamp>/slitranet/slide_text_map.{json,csv}`
- `output/runs/<timestamp>/slitranet/slide_text_map_final.{json,csv}`
- `output/runs/<timestamp>/slitranet/slides_final_manifest.csv`
- `output/runs/<timestamp>/slitranet/keyframes/final/{slide,full}`
- `output/runs/<timestamp>/slitranet/keyframes/final/slide_raw`
- `output/runs/<timestamp>/slitranet/keyframes/final/slide_translated`
- `output/runs/<timestamp>/slitranet/keyframes/final/slide_upscaled`
- `output/runs/<timestamp>/slitranet/keyframes/final/slide_translated_upscaled`
- `output/runs/<timestamp>/slitranet/keyframes/final/upscale_manifest.json`
- `output/runs/<timestamp>/slitranet/slide_text_map_final_translated.{json,csv}`
- `output/runs/<timestamp>/slitranet/tts/audio/*.wav`
- `output/runs/<timestamp>/slitranet/tts/tts_manifest.{json,csv}`
- `output/runs/<timestamp>/slitranet/video_export/timeline.{json,csv}`
- `output/runs/<timestamp>/slitranet/video_export/final_<sprache>.mp4`
- `output/runs/<timestamp>/slitranet/video_export/final_<sprache>.srt`

`output/latest` zeigt auf den neuesten Run.

Wenn ein später Step fehlschlägt, zeigt die Home-Ansicht trotzdem den bis dahin verfügbaren Stand des neuesten Runs.

## Web UI

Start:

```bash
source .venv/bin/activate
.venv/bin/python web/server.py
```

Dann öffnen:
- `http://127.0.0.1:8000`

Weitere Details:
- `web/README.md`
