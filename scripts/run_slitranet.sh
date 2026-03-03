#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="$ROOT_DIR/config/slitranet.env"
GEMINI_PROMPT_FILE="$ROOT_DIR/config/prompts/gemini_edit_prompt.txt"
GEMINI_TRANSLATE_PROMPT_FILE="$ROOT_DIR/config/prompts/gemini_translate_prompt.txt"
GEMINI_TEXT_TRANSLATE_PROMPT_FILE="$ROOT_DIR/config/prompts/gemini_text_translate_prompt.txt"
GEMINI_TTS_PROMPT_FILE="$ROOT_DIR/config/prompts/gemini_tts_prompt.txt"
TRANSLATION_TERMBASE_FILE="$ROOT_DIR/config/language/translation_termbase.csv"
TRANSLATION_MEMORY_DB="$ROOT_DIR/output/translation_memory/translation_memory.sqlite"
LOCAL_ENV_FILE="$ROOT_DIR/.env.local"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
VIDEO_PATH_ARG=""

usage() {
  cat <<USAGE
Usage: bash scripts/run_slitranet.sh [--video path/to/video.mp4]

Options:
  --video PATH   Override VIDEO_PATH from config for this run.
  -h, --help     Show this help text.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --video)
      if [ $# -lt 2 ]; then
        echo "ERROR: --video requires a path argument." >&2
        usage >&2
        exit 1
      fi
      VIDEO_PATH_ARG="$2"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [ ! -d "$VENV_DIR" ]; then
  echo "ERROR: .venv not found. Run: bash scripts/setup_venv.sh" >&2
  exit 1
fi

if [ -f "$LOCAL_ENV_FILE" ]; then
  # shellcheck disable=SC1090
  set -a
  source "$LOCAL_ENV_FILE"
  set +a
fi

# shellcheck disable=SC1090
source "$CONFIG_FILE"

if [ -z "${PHASE:-}" ]; then
  PHASE="test"
fi

FINAL_SLIDE_POSTPROCESS_MODE="${FINAL_SLIDE_POSTPROCESS_MODE:-local}"
GEMINI_EDIT_MODEL="${GEMINI_EDIT_MODEL:-gemini-3-pro-image-preview}"
FINAL_SLIDE_TRANSLATION_MODE="${FINAL_SLIDE_TRANSLATION_MODE:-none}"
FINAL_SLIDE_TARGET_LANGUAGE="${FINAL_SLIDE_TARGET_LANGUAGE:-German}"
GEMINI_TRANSLATE_MODEL="${GEMINI_TRANSLATE_MODEL:-gemini-3-pro-image-preview}"
GEMINI_TEXT_TRANSLATE_MODEL="${GEMINI_TEXT_TRANSLATE_MODEL:-gemini-2.5-flash}"
GEMINI_TTS_MODEL="${GEMINI_TTS_MODEL:-gemini-2.5-flash-tts}"
GEMINI_TTS_VOICE="${GEMINI_TTS_VOICE:-Kore}"
GOOGLE_TTS_PROJECT_ID="${GOOGLE_TTS_PROJECT_ID:-${GOOGLE_SPEECH_PROJECT_ID:-}}"
GOOGLE_TTS_LANGUAGE_CODE="${GOOGLE_TTS_LANGUAGE_CODE:-en-US}"
FINAL_SLIDE_UPSCALE_MODE="${FINAL_SLIDE_UPSCALE_MODE:-none}"
FINAL_SLIDE_UPSCALE_MODEL="${FINAL_SLIDE_UPSCALE_MODEL:-caidas/swin2SR-classical-sr-x4-64}"
FINAL_SLIDE_UPSCALE_DEVICE="${FINAL_SLIDE_UPSCALE_DEVICE:-auto}"
FINAL_SLIDE_UPSCALE_TILE_SIZE="${FINAL_SLIDE_UPSCALE_TILE_SIZE:-256}"
FINAL_SLIDE_UPSCALE_TILE_OVERLAP="${FINAL_SLIDE_UPSCALE_TILE_OVERLAP:-24}"
FINAL_SOURCE_MODE_AUTO="${FINAL_SOURCE_MODE_AUTO:-auto}"
FULLSLIDE_SAMPLE_FRAMES="${FULLSLIDE_SAMPLE_FRAMES:-3}"
FULLSLIDE_BORDER_STRIP_PX="${FULLSLIDE_BORDER_STRIP_PX:-24}"
FULLSLIDE_MIN_MATCHED_SIDES="${FULLSLIDE_MIN_MATCHED_SIDES:-2}"
FULLSLIDE_BORDER_DIFF_THRESHOLD="${FULLSLIDE_BORDER_DIFF_THRESHOLD:-16.0}"
FULLSLIDE_PERSON_BOX_AREA_RATIO="${FULLSLIDE_PERSON_BOX_AREA_RATIO:-0.02}"
FULLSLIDE_PERSON_OUTSIDE_RATIO="${FULLSLIDE_PERSON_OUTSIDE_RATIO:-0.35}"
RUN_STEP_EDIT="${RUN_STEP_EDIT:-1}"
RUN_STEP_TRANSLATE="${RUN_STEP_TRANSLATE:-1}"
RUN_STEP_UPSCALE="${RUN_STEP_UPSCALE:-1}"
RUN_STEP_TEXT_TRANSLATE="${RUN_STEP_TEXT_TRANSLATE:-1}"
RUN_STEP_TTS="${RUN_STEP_TTS:-1}"
RUN_STEP_VIDEO_EXPORT="${RUN_STEP_VIDEO_EXPORT:-1}"
REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND="${REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND:-0.000225}"
VIDEO_EXPORT_MIN_SLIDE_SEC="${VIDEO_EXPORT_MIN_SLIDE_SEC:-1.2}"
VIDEO_EXPORT_TAIL_PAD_SEC="${VIDEO_EXPORT_TAIL_PAD_SEC:-0.35}"
VIDEO_EXPORT_WIDTH="${VIDEO_EXPORT_WIDTH:-1920}"
VIDEO_EXPORT_HEIGHT="${VIDEO_EXPORT_HEIGHT:-1080}"
VIDEO_EXPORT_FPS="${VIDEO_EXPORT_FPS:-30}"
VIDEO_EXPORT_BG_COLOR="${VIDEO_EXPORT_BG_COLOR:-white}"

toggle_to_flag() {
  case "${1:-1}" in
    1|true|TRUE|True|yes|YES|on|ON) printf '1' ;;
    0|false|FALSE|False|no|NO|off|OFF) printf '0' ;;
    *)
      echo "ERROR: invalid step toggle value: $1" >&2
      exit 1
      ;;
  esac
}

RUN_STEP_EDIT="$(toggle_to_flag "$RUN_STEP_EDIT")"
RUN_STEP_TRANSLATE="$(toggle_to_flag "$RUN_STEP_TRANSLATE")"
RUN_STEP_UPSCALE="$(toggle_to_flag "$RUN_STEP_UPSCALE")"
RUN_STEP_TEXT_TRANSLATE="$(toggle_to_flag "$RUN_STEP_TEXT_TRANSLATE")"
RUN_STEP_TTS="$(toggle_to_flag "$RUN_STEP_TTS")"
RUN_STEP_VIDEO_EXPORT="$(toggle_to_flag "$RUN_STEP_VIDEO_EXPORT")"

emit_step() {
  local action="$1"
  local step="$2"
  shift 2
  if [ $# -gt 0 ]; then
    printf '@@STEP %s %s %s\n' "$action" "$step" "$*"
  else
    printf '@@STEP %s %s\n' "$action" "$step"
  fi
}

step_start() {
  emit_step START "$@"
}

step_done() {
  emit_step DONE "$@"
}

step_skip() {
  emit_step SKIP "$@"
}

step_detail() {
  emit_step DETAIL "$@"
}

refresh_latest_link() {
  if [ -L "$LATEST_LINK" ] || [ ! -e "$LATEST_LINK" ]; then
    ln -sfn "$RUN_DIR" "$LATEST_LINK"
  fi
}

publish_dir() {
  local tmp_dir="$1"
  local final_dir="$2"
  if [ ! -d "$tmp_dir" ]; then
    echo "ERROR: temp dir missing for publish: $tmp_dir" >&2
    exit 1
  fi
  rm -rf "$final_dir"
  mv "$tmp_dir" "$final_dir"
  refresh_latest_link
}

publish_file() {
  local tmp_file="$1"
  local final_file="$2"
  if [ ! -f "$tmp_file" ]; then
    echo "ERROR: temp file missing for publish: $tmp_file" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$final_file")"
  rm -f "$final_file"
  mv "$tmp_file" "$final_file"
  refresh_latest_link
}

VIDEO_PATH_RESOLVED="${VIDEO_PATH_ARG:-${VIDEO_PATH:-}}"
if [ -z "$VIDEO_PATH_RESOLVED" ]; then
  echo "ERROR: No video selected. Set VIDEO_PATH in config or pass --video." >&2
  exit 1
fi

case "$VIDEO_PATH_RESOLVED" in
  /*) VIDEO_ABS="$VIDEO_PATH_RESOLVED" ;;
  *) VIDEO_ABS="$ROOT_DIR/$VIDEO_PATH_RESOLVED" ;;
esac
if [ ! -f "$VIDEO_ABS" ]; then
  echo "ERROR: video not found: $VIDEO_ABS" >&2
  exit 1
fi

VIDEO_NAME="$(basename "$VIDEO_ABS")"
VIDEO_BASE="${VIDEO_NAME%.*}"

RUN_ID="$(date +%Y-%m-%d_%H-%M-%S)"
RUN_DIR="$ROOT_DIR/output/runs/$RUN_ID"
LATEST_LINK="$ROOT_DIR/output/latest"
DATASET_DIR="$RUN_DIR/dataset"
OUT_BASE="$RUN_DIR/slitranet"
PRED_DIR="$OUT_BASE/pred_stage1"
OUT_DIR="$OUT_BASE/transitions"
PHASE_DIR="$DATASET_DIR/videos/$PHASE"
ROI_FILE="$DATASET_DIR/videos/${PHASE}_bounding_box_list.txt"

mkdir -p "$RUN_DIR" "$PRED_DIR" "$OUT_DIR" "$OUT_BASE/keyframes/full" "$OUT_BASE/keyframes/slide"
cp "$CONFIG_FILE" "$RUN_DIR/config_used.env"
if grep -q '^VIDEO_PATH=' "$RUN_DIR/config_used.env"; then
  sed -i "s|^VIDEO_PATH=.*$|VIDEO_PATH=\"$VIDEO_PATH_RESOLVED\"|" "$RUN_DIR/config_used.env"
else
  printf '\nVIDEO_PATH="%s"\n' "$VIDEO_PATH_RESOLVED" >> "$RUN_DIR/config_used.env"
fi

step_start slide-detection
step_detail slide-detection "prepare-dataset"
DATASET_DIR="$DATASET_DIR" VIDEO_PATH_OVERRIDE="$VIDEO_PATH_RESOLVED" bash "$ROOT_DIR/scripts/pipeline/prepare_dataset.sh"
step_detail slide-detection "check-weights"
bash "$ROOT_DIR/scripts/pipeline/check_weights.sh"

step_detail slide-detection "cuda-check"
if ! "$PYTHON_BIN" - <<'PY'
import torch
raise SystemExit(0 if torch.cuda.is_available() else 1)
PY
then
  echo "ERROR: torch.cuda.is_available() is False." >&2
  echo "The original SliTraNet inference script uses .cuda() and needs a CUDA-capable runtime." >&2
  exit 1
fi

step_detail slide-detection "slitranet-inference"
pushd "$ROOT_DIR/slitranet" >/dev/null
"$PYTHON_BIN" test_SliTraNet.py \
  --dataset_dir "$DATASET_DIR" \
  --phase "$PHASE" \
  --pred_dir "$PRED_DIR" \
  --out_dir "$OUT_DIR" \
  --model_path_2D "$ROOT_DIR/weights/Frame_similarity_ResNet18_gray.pth" \
  --model_path_1 "$ROOT_DIR/weights/Slide_video_detection_3DResNet50.pth" \
  --model_path_2 "$ROOT_DIR/weights/Slide_transition_detection_3DResNet50.pth"
popd >/dev/null

TRANSITIONS_FILE="$OUT_DIR/${VIDEO_BASE}_transitions.txt"
if [ ! -f "$TRANSITIONS_FILE" ]; then
  echo "ERROR: Expected output file not found: $TRANSITIONS_FILE" >&2
  exit 1
fi
STAGE1_FILE="$PRED_DIR/${VIDEO_BASE}_results.txt"
STAGE1_ARGS=()
if [ -f "$STAGE1_FILE" ]; then
  STAGE1_ARGS+=(--stage1-file "$STAGE1_FILE")
else
  echo "WARN: Stage-1 result file not found, initial event will be skipped: $STAGE1_FILE" >&2
fi

step_detail slide-detection "postprocess"
"$PYTHON_BIN" "$ROOT_DIR/scripts/pipeline/postprocess_slitranet.py" \
  --video "$PHASE_DIR/$VIDEO_NAME" \
  --roi-file "$ROI_FILE" \
  --transitions-file "$TRANSITIONS_FILE" \
  "${STAGE1_ARGS[@]}" \
  --out-csv "$OUT_BASE/slide_changes.csv" \
  --out-full-dir "$OUT_BASE/keyframes/full" \
  --out-slide-dir "$OUT_BASE/keyframes/slide" \
  --settle-frames "${KEYFRAME_SETTLE_FRAMES:-4}" \
  --stable-end-guard-frames "${KEYFRAME_STABLE_END_GUARD_FRAMES:-2}" \
  --stable-lookahead-frames "${KEYFRAME_STABLE_LOOKAHEAD_FRAMES:-2}"
refresh_latest_link
step_done slide-detection

TRANSCRIPT_JSON="$OUT_BASE/transcript_segments.json"
TRANSCRIPT_CSV="$OUT_BASE/transcript_segments.csv"
echo "[ASR] Preparing transcription step ..."
echo "[Step] transcription: run"
step_start transcription
case "${TRANSCRIPTION_PROVIDER:-whisper}" in
  whisper)
    TRANSCRIPT_ARGS=(
      --video "$PHASE_DIR/$VIDEO_NAME"
      --out-json "$TRANSCRIPT_JSON"
      --out-csv "$TRANSCRIPT_CSV"
      --model "${WHISPER_MODEL:-medium}"
      --device "${WHISPER_DEVICE:-cuda}"
      --compute-type "${WHISPER_COMPUTE_TYPE:-float16}"
    )
    if [ -n "${WHISPER_LANGUAGE:-}" ]; then
      TRANSCRIPT_ARGS+=(--language "$WHISPER_LANGUAGE")
    fi
    step_detail transcription "faster-whisper"
    "$PYTHON_BIN" "$ROOT_DIR/scripts/providers/transcribe_whisper.py" "${TRANSCRIPT_ARGS[@]}"
    ;;
  google_chirp_3)
    if [ -z "${GOOGLE_SPEECH_PROJECT_ID:-}" ]; then
      echo "ERROR: GOOGLE_SPEECH_PROJECT_ID must not be empty when TRANSCRIPTION_PROVIDER=google_chirp_3." >&2
      exit 1
    fi
    TRANSCRIPT_ARGS=(
      --video "$PHASE_DIR/$VIDEO_NAME"
      --out-json "$TRANSCRIPT_JSON"
      --out-csv "$TRANSCRIPT_CSV"
      --project-id "${GOOGLE_SPEECH_PROJECT_ID}"
      --location "${GOOGLE_SPEECH_LOCATION:-global}"
      --model "${GOOGLE_SPEECH_MODEL:-chirp_3}"
      --language-codes "${GOOGLE_SPEECH_LANGUAGE_CODES:-en-US}"
      --chunk-sec "${GOOGLE_SPEECH_CHUNK_SEC:-55}"
      --chunk-overlap-sec "${GOOGLE_SPEECH_CHUNK_OVERLAP_SEC:-0.75}"
    )
    step_detail transcription "google-chirp-3"
    "$PYTHON_BIN" "$ROOT_DIR/scripts/providers/transcribe_google_speech.py" "${TRANSCRIPT_ARGS[@]}"
    ;;
  *)
    echo "ERROR: TRANSCRIPTION_PROVIDER must be one of: whisper, google_chirp_3" >&2
    exit 1
    ;;
esac
step_done transcription
echo "[ASR] Transcription step finished."

SLIDE_TEXT_MAP_JSON="$OUT_BASE/slide_text_map.json"
SLIDE_TEXT_MAP_CSV="$OUT_BASE/slide_text_map.csv"
echo "[ASR] Mapping transcript to slide windows ..."
echo "[Step] transcript-mapping: run"
step_start transcript-mapping
step_detail transcript-mapping "map-transcript-to-slides"
"$PYTHON_BIN" "$ROOT_DIR/scripts/pipeline/map_transcript_to_slides.py" \
  --video "$PHASE_DIR/$VIDEO_NAME" \
  --slide-csv "$OUT_BASE/slide_changes.csv" \
  --transcript-json "$TRANSCRIPT_JSON" \
  --out-json "$SLIDE_TEXT_MAP_JSON" \
  --out-csv "$SLIDE_TEXT_MAP_CSV"
step_done transcript-mapping
echo "[ASR] Slide text mapping finished."

SLIDE_TEXT_MAP_FINAL_JSON="$OUT_BASE/slide_text_map_final.json"
SLIDE_TEXT_MAP_FINAL_CSV="$OUT_BASE/slide_text_map_final.csv"
SLIDE_FILTER_MANIFEST_CSV="$OUT_BASE/slides_final_manifest.csv"
FINAL_SOURCE_MANIFEST_CSV="$OUT_BASE/final_image_source_manifest.csv"
FINAL_SLIDE_DIR="$OUT_BASE/keyframes/final/slide"
FINAL_SLIDE_RAW_DIR="$OUT_BASE/keyframes/final/slide_raw"
FINAL_SLIDE_TRANSLATED_DIR="$OUT_BASE/keyframes/final/slide_translated"
FINAL_SLIDE_UPSCALED_DIR="$OUT_BASE/keyframes/final/slide_upscaled"
FINAL_SLIDE_TRANSLATED_UPSCALED_DIR="$OUT_BASE/keyframes/final/slide_translated_upscaled"
UPSCALE_MANIFEST_JSON="$OUT_BASE/keyframes/final/upscale_manifest.json"
FINAL_FULL_DIR="$OUT_BASE/keyframes/final/full"
TEXT_TRANSLATED_JSON="$OUT_BASE/slide_text_map_final_translated.json"
TEXT_TRANSLATED_CSV="$OUT_BASE/slide_text_map_final_translated.csv"
TTS_AUDIO_DIR="$OUT_BASE/tts/audio"
TTS_MANIFEST_JSON="$OUT_BASE/tts/tts_manifest.json"
TTS_MANIFEST_CSV="$OUT_BASE/tts/tts_manifest.csv"
VIDEO_EXPORT_DIR="$OUT_BASE/video_export"
VIDEO_EXPORT_TIMELINE_JSON="$VIDEO_EXPORT_DIR/timeline.json"
VIDEO_EXPORT_TIMELINE_CSV="$VIDEO_EXPORT_DIR/timeline.csv"
UPSCALE_TRANSLATED_MANIFEST_JSON="$OUT_BASE/keyframes/final/upscale_translated_manifest.json"

lang_slug() {
  local raw="$1"
  local slug
  slug="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"
  if [ -z "$slug" ]; then
    slug="translated"
  fi
  printf '%s' "$slug"
}

dir_has_pngs() {
  local path="$1"
  [ -d "$path" ] && find "$path" -maxdepth 1 -type f -name '*.png' | grep -q .
}
FINAL_SLIDE_CLEAN_MODE="none"
if [ "$RUN_STEP_EDIT" = "1" ]; then
  case "$FINAL_SLIDE_POSTPROCESS_MODE" in
    none)
      FINAL_SLIDE_CLEAN_MODE="none"
      ;;
    local)
      FINAL_SLIDE_CLEAN_MODE="local"
      ;;
    gemini)
      FINAL_SLIDE_CLEAN_MODE="none"
      ;;
    *)
      echo "ERROR: FINAL_SLIDE_POSTPROCESS_MODE must be one of: none, local, gemini" >&2
      exit 1
      ;;
  esac
else
  FINAL_SLIDE_CLEAN_MODE="none"
fi
FILTER_ARGS=(
  --video "$PHASE_DIR/$VIDEO_NAME"
  --slide-map-json "$SLIDE_TEXT_MAP_JSON"
  --slide-map-csv "$SLIDE_TEXT_MAP_CSV"
  --slide-keyframes-dir "$OUT_BASE/keyframes/slide"
  --full-keyframes-dir "$OUT_BASE/keyframes/full"
  --out-json "$SLIDE_TEXT_MAP_FINAL_JSON.__tmp"
  --out-csv "$SLIDE_TEXT_MAP_FINAL_CSV.__tmp"
  --out-manifest-csv "$SLIDE_FILTER_MANIFEST_CSV.__tmp"
  --out-final-source-manifest-csv "$FINAL_SOURCE_MANIFEST_CSV.__tmp"
  --out-final-slide-dir "$FINAL_SLIDE_DIR.__tmp"
  --out-final-slide-raw-dir "$FINAL_SLIDE_RAW_DIR.__tmp"
  --out-final-full-dir "$FINAL_FULL_DIR.__tmp"
  --final-slide-clean-mode "$FINAL_SLIDE_CLEAN_MODE"
  --final-source-mode-auto "$FINAL_SOURCE_MODE_AUTO"
  --roi-x0 "${ROI_X0:-0}"
  --roi-y0 "${ROI_Y0:-0}"
  --roi-x1 "${ROI_X1:-0}"
  --roi-y1 "${ROI_Y1:-0}"
  --fullslide-sample-frames "$FULLSLIDE_SAMPLE_FRAMES"
  --fullslide-border-strip-px "$FULLSLIDE_BORDER_STRIP_PX"
  --fullslide-min-matched-sides "$FULLSLIDE_MIN_MATCHED_SIDES"
  --fullslide-border-diff-threshold "$FULLSLIDE_BORDER_DIFF_THRESHOLD"
  --fullslide-person-box-area-ratio "$FULLSLIDE_PERSON_BOX_AREA_RATIO"
  --fullslide-person-outside-ratio "$FULLSLIDE_PERSON_OUTSIDE_RATIO"
  --speaker-min-stage1-video-ratio "${SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO:-0.75}"
  --speaker-max-edge-density "${SPEAKER_FILTER_MAX_EDGE_DENSITY:-0.011}"
  --speaker-max-laplacian-var "${SPEAKER_FILTER_MAX_LAPLACIAN_VAR:-80}"
  --speaker-max-duration-sec "${SPEAKER_FILTER_MAX_DURATION_SEC:-2.5}"
)
if [ -f "$STAGE1_FILE" ]; then
  FILTER_ARGS+=(--stage1-file "$STAGE1_FILE")
fi

echo "[ASR] Filtering speaker-only slides and merging transcript ..."
step_start finalize-slides
step_detail finalize-slides "speaker-filter-and-final-export"
rm -f "$SLIDE_TEXT_MAP_FINAL_JSON.__tmp" "$SLIDE_TEXT_MAP_FINAL_CSV.__tmp" "$SLIDE_FILTER_MANIFEST_CSV.__tmp" "$FINAL_SOURCE_MANIFEST_CSV.__tmp"
rm -rf "$FINAL_SLIDE_DIR.__tmp" "$FINAL_SLIDE_RAW_DIR.__tmp" "$FINAL_FULL_DIR.__tmp"
"$PYTHON_BIN" "$ROOT_DIR/scripts/pipeline/filter_and_merge_speaker_only.py" "${FILTER_ARGS[@]}"
publish_file "$SLIDE_TEXT_MAP_FINAL_JSON.__tmp" "$SLIDE_TEXT_MAP_FINAL_JSON"
publish_file "$SLIDE_TEXT_MAP_FINAL_CSV.__tmp" "$SLIDE_TEXT_MAP_FINAL_CSV"
publish_file "$SLIDE_FILTER_MANIFEST_CSV.__tmp" "$SLIDE_FILTER_MANIFEST_CSV"
publish_file "$FINAL_SOURCE_MANIFEST_CSV.__tmp" "$FINAL_SOURCE_MANIFEST_CSV"
publish_dir "$FINAL_SLIDE_RAW_DIR.__tmp" "$FINAL_SLIDE_RAW_DIR"
publish_dir "$FINAL_SLIDE_DIR.__tmp" "$FINAL_SLIDE_DIR"
publish_dir "$FINAL_FULL_DIR.__tmp" "$FINAL_FULL_DIR"
step_done finalize-slides
if [ "$RUN_STEP_EDIT" = "1" ] && [ "$FINAL_SLIDE_POSTPROCESS_MODE" = "local" ]; then
  step_done edit "local cleanup applied within finalize-slides"
fi
echo "[ASR] Speaker-only filtering finished."

if [ "$RUN_STEP_EDIT" = "1" ] && [ "$FINAL_SLIDE_POSTPROCESS_MODE" = "gemini" ]; then
  if [ -z "${GEMINI_API_KEY:-}" ]; then
    echo "ERROR: FINAL_SLIDE_POSTPROCESS_MODE=gemini requires GEMINI_API_KEY in the environment." >&2
    exit 1
  fi

  echo "[Gemini] Editing raw final slides with model $GEMINI_EDIT_MODEL ..."
  step_start edit
  step_detail edit "gemini-image-edit"
  rm -rf "$FINAL_SLIDE_DIR.__tmp"
  "$PYTHON_BIN" "$ROOT_DIR/scripts/providers/edit_final_slides_gemini.py" \
    --input-dir "$FINAL_SLIDE_RAW_DIR" \
    --output-dir "$FINAL_SLIDE_DIR.__tmp" \
    --model "$GEMINI_EDIT_MODEL" \
    --prompt-file "$GEMINI_PROMPT_FILE" \
    --source-manifest-csv "$FINAL_SOURCE_MANIFEST_CSV" \
    --mask-debug-dir "$OUT_BASE/keyframes/final/slide_gemini_mask" \
    --overlay-debug-dir "$OUT_BASE/keyframes/final/slide_gemini_overlay"
  publish_dir "$FINAL_SLIDE_DIR.__tmp" "$FINAL_SLIDE_DIR"
  step_done edit
  echo "[Gemini] Editing finished."
elif [ "$RUN_STEP_EDIT" = "0" ]; then
  echo "[Step] edit: skipped"
  step_skip edit "disabled"
elif [ "$FINAL_SLIDE_POSTPROCESS_MODE" = "none" ]; then
  step_skip edit "mode=none"
fi

if [ "$RUN_STEP_TRANSLATE" = "1" ]; then
  case "$FINAL_SLIDE_TRANSLATION_MODE" in
    none)
      step_skip translate "mode=none"
      ;;
    gemini)
      if [ -z "${GEMINI_API_KEY:-}" ]; then
        echo "ERROR: FINAL_SLIDE_TRANSLATION_MODE=gemini requires GEMINI_API_KEY in the environment." >&2
        exit 1
      fi
      if [ -z "${FINAL_SLIDE_TARGET_LANGUAGE:-}" ]; then
        echo "ERROR: FINAL_SLIDE_TARGET_LANGUAGE must not be empty when translation is enabled." >&2
        exit 1
      fi
      echo "[Translate] Translating final slides to $FINAL_SLIDE_TARGET_LANGUAGE with model $GEMINI_TRANSLATE_MODEL ..."
      step_start translate
      step_detail translate "$FINAL_SLIDE_TARGET_LANGUAGE"
      rm -rf "$FINAL_SLIDE_TRANSLATED_DIR.__tmp"
      "$PYTHON_BIN" "$ROOT_DIR/scripts/providers/translate_final_slides_gemini.py" \
        --input-dir "$FINAL_SLIDE_DIR" \
        --output-dir "$FINAL_SLIDE_TRANSLATED_DIR.__tmp" \
        --model "$GEMINI_TRANSLATE_MODEL" \
        --prompt-file "$GEMINI_TRANSLATE_PROMPT_FILE" \
        --termbase-file "$TRANSLATION_TERMBASE_FILE" \
        --target-language "$FINAL_SLIDE_TARGET_LANGUAGE"
      publish_dir "$FINAL_SLIDE_TRANSLATED_DIR.__tmp" "$FINAL_SLIDE_TRANSLATED_DIR"
      step_done translate
      echo "[Translate] Translation finished."
      ;;
    *)
      echo "ERROR: FINAL_SLIDE_TRANSLATION_MODE must be one of: none, gemini" >&2
      exit 1
      ;;
  esac
else
  echo "[Step] translate: skipped"
  step_skip translate "disabled"
fi

if [ "$RUN_STEP_UPSCALE" = "1" ]; then
  case "$FINAL_SLIDE_UPSCALE_MODE" in
    none)
      step_skip upscale "mode=none"
      ;;
    swin2sr)
      echo "[Upscale] Upscaling processed final slides with model $FINAL_SLIDE_UPSCALE_MODEL ..."
      step_start upscale
      step_detail upscale "processed-final-slides"
      rm -rf "$FINAL_SLIDE_UPSCALED_DIR.__tmp" "$FINAL_SLIDE_TRANSLATED_UPSCALED_DIR.__tmp"
      "$PYTHON_BIN" "$ROOT_DIR/scripts/providers/upscale_final_slides_swin2sr.py" \
        --input-dir "$FINAL_SLIDE_DIR" \
        --output-dir "$FINAL_SLIDE_UPSCALED_DIR.__tmp" \
        --model-id "$FINAL_SLIDE_UPSCALE_MODEL" \
        --device "$FINAL_SLIDE_UPSCALE_DEVICE" \
        --tile-size "$FINAL_SLIDE_UPSCALE_TILE_SIZE" \
        --tile-overlap "$FINAL_SLIDE_UPSCALE_TILE_OVERLAP"
      publish_dir "$FINAL_SLIDE_UPSCALED_DIR.__tmp" "$FINAL_SLIDE_UPSCALED_DIR"
      if [ -d "$FINAL_SLIDE_TRANSLATED_DIR" ] && find "$FINAL_SLIDE_TRANSLATED_DIR" -maxdepth 1 -type f -name '*.png' | grep -q .; then
        echo "[Upscale] Upscaling translated final slides with model $FINAL_SLIDE_UPSCALE_MODEL ..."
        step_detail upscale "translated-final-slides"
        "$PYTHON_BIN" "$ROOT_DIR/scripts/providers/upscale_final_slides_swin2sr.py" \
          --input-dir "$FINAL_SLIDE_TRANSLATED_DIR" \
          --output-dir "$FINAL_SLIDE_TRANSLATED_UPSCALED_DIR.__tmp" \
          --model-id "$FINAL_SLIDE_UPSCALE_MODEL" \
          --device "$FINAL_SLIDE_UPSCALE_DEVICE" \
          --tile-size "$FINAL_SLIDE_UPSCALE_TILE_SIZE" \
          --tile-overlap "$FINAL_SLIDE_UPSCALE_TILE_OVERLAP"
        publish_dir "$FINAL_SLIDE_TRANSLATED_UPSCALED_DIR.__tmp" "$FINAL_SLIDE_TRANSLATED_UPSCALED_DIR"
      fi
      step_done upscale
      echo "[Upscale] Upscaling finished."
      ;;
    replicate_nightmare_realesrgan)
      if [ -z "${REPLICATE_API_TOKEN:-}" ]; then
        echo "ERROR: $FINAL_SLIDE_UPSCALE_MODE requires REPLICATE_API_TOKEN in the environment." >&2
        exit 1
      fi
      REPLICATE_PROVIDER="nightmare_realesrgan"
      REPLICATE_EXTRA_ARGS=(
        --nightmare-realesrgan-model-ref "${REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF:-nightmareai/real-esrgan}"
        --nightmare-realesrgan-version-id "${REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID:-f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa}"
        --nightmare-realesrgan-scale 4
        --nightmare-realesrgan-face-enhance false
        --nightmare-realesrgan-price-per-second "${REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND:-0.000225}"
      )
      echo "[Upscale] Upscaling processed final slides with Replicate provider $REPLICATE_PROVIDER ..."
      step_start upscale
      step_detail upscale "processed-final-slides:$REPLICATE_PROVIDER"
      rm -rf "$FINAL_SLIDE_UPSCALED_DIR.__tmp" "$FINAL_SLIDE_TRANSLATED_UPSCALED_DIR.__tmp"
      rm -f "$UPSCALE_MANIFEST_JSON.__tmp" "$UPSCALE_TRANSLATED_MANIFEST_JSON.__tmp"
      "$PYTHON_BIN" "$ROOT_DIR/scripts/providers/upscale_final_slides_replicate.py" \
        --input-dir "$FINAL_SLIDE_DIR" \
        --output-dir "$FINAL_SLIDE_UPSCALED_DIR.__tmp" \
        --provider "$REPLICATE_PROVIDER" \
        --concurrency "${REPLICATE_UPSCALE_CONCURRENCY:-2}" \
        --manifest-path "$UPSCALE_MANIFEST_JSON.__tmp" \
        "${REPLICATE_EXTRA_ARGS[@]}"
      publish_dir "$FINAL_SLIDE_UPSCALED_DIR.__tmp" "$FINAL_SLIDE_UPSCALED_DIR"
      publish_file "$UPSCALE_MANIFEST_JSON.__tmp" "$UPSCALE_MANIFEST_JSON"
      if [ -d "$FINAL_SLIDE_TRANSLATED_DIR" ] && find "$FINAL_SLIDE_TRANSLATED_DIR" -maxdepth 1 -type f -name '*.png' | grep -q .; then
        echo "[Upscale] Upscaling translated final slides with Replicate provider $REPLICATE_PROVIDER ..."
        step_detail upscale "translated-final-slides:$REPLICATE_PROVIDER"
        "$PYTHON_BIN" "$ROOT_DIR/scripts/providers/upscale_final_slides_replicate.py" \
          --input-dir "$FINAL_SLIDE_TRANSLATED_DIR" \
          --output-dir "$FINAL_SLIDE_TRANSLATED_UPSCALED_DIR.__tmp" \
          --concurrency "${REPLICATE_UPSCALE_CONCURRENCY:-2}" \
          --manifest-path "$UPSCALE_TRANSLATED_MANIFEST_JSON.__tmp" \
          --provider "$REPLICATE_PROVIDER" \
          "${REPLICATE_EXTRA_ARGS[@]}"
        publish_dir "$FINAL_SLIDE_TRANSLATED_UPSCALED_DIR.__tmp" "$FINAL_SLIDE_TRANSLATED_UPSCALED_DIR"
        publish_file "$UPSCALE_TRANSLATED_MANIFEST_JSON.__tmp" "$UPSCALE_TRANSLATED_MANIFEST_JSON"
      fi
      step_done upscale
      echo "[Upscale] Replicate upscaling finished."
      ;;
    *)
      echo "ERROR: FINAL_SLIDE_UPSCALE_MODE must be one of: none, swin2sr, replicate_nightmare_realesrgan" >&2
      exit 1
      ;;
  esac
else
  echo "[Step] upscale: skipped"
  step_skip upscale "disabled"
fi

TEXT_TRANSLATE_INPUT_JSON="$SLIDE_TEXT_MAP_FINAL_JSON"
TEXT_TRANSLATE_LANGUAGE="$FINAL_SLIDE_TARGET_LANGUAGE"

if [ "$RUN_STEP_TEXT_TRANSLATE" = "1" ]; then
  if [ -z "${GEMINI_API_KEY:-}" ]; then
    echo "ERROR: text translation requires GEMINI_API_KEY in the environment." >&2
    exit 1
  fi
  if [ -z "${FINAL_SLIDE_TARGET_LANGUAGE:-}" ]; then
    echo "ERROR: FINAL_SLIDE_TARGET_LANGUAGE must not be empty when text translation is enabled." >&2
    exit 1
  fi
  echo "[TextTranslate] Translating mapped slide text to $FINAL_SLIDE_TARGET_LANGUAGE with model $GEMINI_TEXT_TRANSLATE_MODEL ..."
  step_start text-translate
  step_detail text-translate "$FINAL_SLIDE_TARGET_LANGUAGE"
  rm -f "$TEXT_TRANSLATED_JSON.__tmp" "$TEXT_TRANSLATED_CSV.__tmp"
  "$PYTHON_BIN" "$ROOT_DIR/scripts/pipeline/translate_slide_text.py" \
    --input-json "$SLIDE_TEXT_MAP_FINAL_JSON" \
    --out-json "$TEXT_TRANSLATED_JSON.__tmp" \
    --out-csv "$TEXT_TRANSLATED_CSV.__tmp" \
    --model "$GEMINI_TEXT_TRANSLATE_MODEL" \
    --prompt-file "$GEMINI_TEXT_TRANSLATE_PROMPT_FILE" \
    --termbase-file "$TRANSLATION_TERMBASE_FILE" \
    --tm-db "$TRANSLATION_MEMORY_DB" \
    --origin-run-id "$RUN_ID" \
    --target-language "$FINAL_SLIDE_TARGET_LANGUAGE"
  publish_file "$TEXT_TRANSLATED_JSON.__tmp" "$TEXT_TRANSLATED_JSON"
  publish_file "$TEXT_TRANSLATED_CSV.__tmp" "$TEXT_TRANSLATED_CSV"
  step_done text-translate
  TEXT_TRANSLATE_INPUT_JSON="$TEXT_TRANSLATED_JSON"
  echo "[TextTranslate] Translation finished."
else
  echo "[Step] text-translate: skipped"
  step_skip text-translate "disabled"
fi

TTS_INPUT_JSON="$TEXT_TRANSLATE_INPUT_JSON"
TTS_LANGUAGE_LABEL="$FINAL_SLIDE_TARGET_LANGUAGE"
if [ "$RUN_STEP_TEXT_TRANSLATE" = "0" ]; then
  TTS_LANGUAGE_LABEL="source language of the text"
fi

if [ "$RUN_STEP_TTS" = "1" ]; then
  if [ -z "${GOOGLE_TTS_PROJECT_ID:-}" ]; then
    echo "ERROR: TTS requires GOOGLE_TTS_PROJECT_ID (or GOOGLE_SPEECH_PROJECT_ID) in the environment/config." >&2
    exit 1
  fi
  if [ -z "${GOOGLE_TTS_LANGUAGE_CODE:-}" ]; then
    echo "ERROR: TTS requires GOOGLE_TTS_LANGUAGE_CODE in the environment/config." >&2
    exit 1
  fi
  echo "[TTS] Generating voiceover with model $GEMINI_TTS_MODEL and voice $GEMINI_TTS_VOICE ..."
  step_start tts
  step_detail tts "$GEMINI_TTS_VOICE"
  rm -rf "$TTS_AUDIO_DIR.__tmp"
  rm -f "$TTS_MANIFEST_JSON.__tmp" "$TTS_MANIFEST_CSV.__tmp"
  "$PYTHON_BIN" "$ROOT_DIR/scripts/pipeline/generate_slide_tts.py" \
    --input-json "$TTS_INPUT_JSON" \
    --output-dir "$TTS_AUDIO_DIR.__tmp" \
    --out-manifest-json "$TTS_MANIFEST_JSON.__tmp" \
    --out-manifest-csv "$TTS_MANIFEST_CSV.__tmp" \
    --model "$GEMINI_TTS_MODEL" \
    --voice "$GEMINI_TTS_VOICE" \
    --project-id "$GOOGLE_TTS_PROJECT_ID" \
    --language-code "$GOOGLE_TTS_LANGUAGE_CODE" \
    --prompt-file "$GEMINI_TTS_PROMPT_FILE" \
    --language-label "$TTS_LANGUAGE_LABEL"
  publish_dir "$TTS_AUDIO_DIR.__tmp" "$TTS_AUDIO_DIR"
  publish_file "$TTS_MANIFEST_JSON.__tmp" "$TTS_MANIFEST_JSON"
  publish_file "$TTS_MANIFEST_CSV.__tmp" "$TTS_MANIFEST_CSV"
  step_done tts
  echo "[TTS] Voiceover generation finished."
else
  echo "[Step] tts: skipped"
  step_skip tts "disabled"
fi

EXPORT_IMAGE_DIR="$FINAL_SLIDE_DIR"
EXPORT_IMAGE_LABEL="processed"
if dir_has_pngs "$FINAL_SLIDE_TRANSLATED_UPSCALED_DIR"; then
  EXPORT_IMAGE_DIR="$FINAL_SLIDE_TRANSLATED_UPSCALED_DIR"
  EXPORT_IMAGE_LABEL="translated_upscaled"
elif dir_has_pngs "$FINAL_SLIDE_TRANSLATED_DIR"; then
  EXPORT_IMAGE_DIR="$FINAL_SLIDE_TRANSLATED_DIR"
  EXPORT_IMAGE_LABEL="translated"
elif dir_has_pngs "$FINAL_SLIDE_UPSCALED_DIR"; then
  EXPORT_IMAGE_DIR="$FINAL_SLIDE_UPSCALED_DIR"
  EXPORT_IMAGE_LABEL="upscaled"
fi

VIDEO_LANG_SLUG="$(lang_slug "$FINAL_SLIDE_TARGET_LANGUAGE")"
VIDEO_EXPORT_MP4="$VIDEO_EXPORT_DIR/final_${VIDEO_LANG_SLUG}.mp4"
VIDEO_EXPORT_SRT="$VIDEO_EXPORT_DIR/final_${VIDEO_LANG_SLUG}.srt"

if [ "$RUN_STEP_VIDEO_EXPORT" = "1" ]; then
  echo "[VideoExport] Building narrated slide video from $EXPORT_IMAGE_LABEL images ..."
  step_start video-export
  step_detail video-export "$EXPORT_IMAGE_LABEL"
  TTS_MANIFEST_ARG=()
  if [ -f "$TTS_MANIFEST_JSON" ]; then
    TTS_MANIFEST_ARG+=(--tts-manifest-json "$TTS_MANIFEST_JSON")
  fi
  rm -rf "$VIDEO_EXPORT_DIR.__tmp"
  mkdir -p "$VIDEO_EXPORT_DIR.__tmp"
  "$PYTHON_BIN" "$ROOT_DIR/scripts/pipeline/export_slide_video.py" \
    --slide-map-json "$TTS_INPUT_JSON" \
    --image-dir "$EXPORT_IMAGE_DIR" \
    "${TTS_MANIFEST_ARG[@]}" \
    --out-video "$VIDEO_EXPORT_DIR.__tmp/final_${VIDEO_LANG_SLUG}.mp4" \
    --out-timeline-json "$VIDEO_EXPORT_DIR.__tmp/timeline.json" \
    --out-timeline-csv "$VIDEO_EXPORT_DIR.__tmp/timeline.csv" \
    --out-srt "$VIDEO_EXPORT_DIR.__tmp/final_${VIDEO_LANG_SLUG}.srt" \
    --min-slide-sec "$VIDEO_EXPORT_MIN_SLIDE_SEC" \
    --tail-pad-sec "$VIDEO_EXPORT_TAIL_PAD_SEC" \
    --width "$VIDEO_EXPORT_WIDTH" \
    --height "$VIDEO_EXPORT_HEIGHT" \
    --fps "$VIDEO_EXPORT_FPS" \
    --bg-color "$VIDEO_EXPORT_BG_COLOR"
  publish_dir "$VIDEO_EXPORT_DIR.__tmp" "$VIDEO_EXPORT_DIR"
  step_done video-export
  echo "[VideoExport] Export finished."
else
  echo "[Step] video-export: skipped"
  step_skip video-export "disabled"
fi

refresh_latest_link

echo "Done."
echo "Run dir: $RUN_DIR"
echo "Main output: $OUT_BASE/slide_changes.csv"
echo "Transcript: $TRANSCRIPT_JSON"
echo "Transcription provider: ${TRANSCRIPTION_PROVIDER:-whisper}"
echo "Slide text map: $SLIDE_TEXT_MAP_JSON"
echo "Final slide text map: $SLIDE_TEXT_MAP_FINAL_JSON"
echo "Final slide raw images: $FINAL_SLIDE_RAW_DIR"
echo "Final image source manifest: $FINAL_SOURCE_MANIFEST_CSV"
echo "Final slide mode: $FINAL_SLIDE_POSTPROCESS_MODE"
echo "Final source mode auto: $FINAL_SOURCE_MODE_AUTO"
echo "Run step edit: $RUN_STEP_EDIT"
echo "Run step translate: $RUN_STEP_TRANSLATE"
echo "Run step upscale: $RUN_STEP_UPSCALE"
echo "Run step text translate: $RUN_STEP_TEXT_TRANSLATE"
echo "Run step tts: $RUN_STEP_TTS"
echo "Run step video export: $RUN_STEP_VIDEO_EXPORT"
echo "Final slide translated images: $FINAL_SLIDE_TRANSLATED_DIR"
echo "Final slide translation mode: $FINAL_SLIDE_TRANSLATION_MODE"
echo "Final slide upscaled images: $FINAL_SLIDE_UPSCALED_DIR"
echo "Final slide translated upscaled images: $FINAL_SLIDE_TRANSLATED_UPSCALED_DIR"
echo "Final slide upscale mode: $FINAL_SLIDE_UPSCALE_MODE"
echo "Translated text map: $TEXT_TRANSLATED_JSON"
echo "TTS manifest: $TTS_MANIFEST_JSON"
echo "Video export image source: $EXPORT_IMAGE_DIR"
echo "Video export output: $VIDEO_EXPORT_MP4"
