#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="$ROOT_DIR/config/slitranet.env"
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

# shellcheck disable=SC1090
source "$CONFIG_FILE"

if [ -z "${PHASE:-}" ]; then
  PHASE="test"
fi

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

DATASET_DIR="$DATASET_DIR" VIDEO_PATH_OVERRIDE="$VIDEO_PATH_RESOLVED" bash "$ROOT_DIR/scripts/prepare_dataset.sh"
bash "$ROOT_DIR/scripts/check_weights.sh"

if ! "$PYTHON_BIN" - <<'PY'
import torch
raise SystemExit(0 if torch.cuda.is_available() else 1)
PY
then
  echo "ERROR: torch.cuda.is_available() is False." >&2
  echo "The original SliTraNet inference script uses .cuda() and needs a CUDA-capable runtime." >&2
  exit 1
fi

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

"$PYTHON_BIN" "$ROOT_DIR/scripts/postprocess_slitranet.py" \
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

TRANSCRIPT_JSON="$OUT_BASE/transcript_segments.json"
TRANSCRIPT_CSV="$OUT_BASE/transcript_segments.csv"
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

echo "[ASR] Preparing transcription step ..."
"$PYTHON_BIN" "$ROOT_DIR/scripts/transcribe_whisper.py" "${TRANSCRIPT_ARGS[@]}"
echo "[ASR] Transcription step finished."

SLIDE_TEXT_MAP_JSON="$OUT_BASE/slide_text_map.json"
SLIDE_TEXT_MAP_CSV="$OUT_BASE/slide_text_map.csv"
echo "[ASR] Mapping transcript to slide windows ..."
"$PYTHON_BIN" "$ROOT_DIR/scripts/map_transcript_to_slides.py" \
  --video "$PHASE_DIR/$VIDEO_NAME" \
  --slide-csv "$OUT_BASE/slide_changes.csv" \
  --transcript-json "$TRANSCRIPT_JSON" \
  --out-json "$SLIDE_TEXT_MAP_JSON" \
  --out-csv "$SLIDE_TEXT_MAP_CSV"
echo "[ASR] Slide text mapping finished."

SLIDE_TEXT_MAP_FINAL_JSON="$OUT_BASE/slide_text_map_final.json"
SLIDE_TEXT_MAP_FINAL_CSV="$OUT_BASE/slide_text_map_final.csv"
SLIDE_FILTER_MANIFEST_CSV="$OUT_BASE/slides_final_manifest.csv"
FINAL_SLIDE_DIR="$OUT_BASE/keyframes/final/slide"
FINAL_FULL_DIR="$OUT_BASE/keyframes/final/full"
FILTER_ARGS=(
  --video "$PHASE_DIR/$VIDEO_NAME"
  --slide-map-json "$SLIDE_TEXT_MAP_JSON"
  --slide-map-csv "$SLIDE_TEXT_MAP_CSV"
  --slide-keyframes-dir "$OUT_BASE/keyframes/slide"
  --full-keyframes-dir "$OUT_BASE/keyframes/full"
  --out-json "$SLIDE_TEXT_MAP_FINAL_JSON"
  --out-csv "$SLIDE_TEXT_MAP_FINAL_CSV"
  --out-manifest-csv "$SLIDE_FILTER_MANIFEST_CSV"
  --out-final-slide-dir "$FINAL_SLIDE_DIR"
  --out-final-full-dir "$FINAL_FULL_DIR"
  --speaker-min-stage1-video-ratio "${SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO:-0.75}"
  --speaker-max-edge-density "${SPEAKER_FILTER_MAX_EDGE_DENSITY:-0.011}"
  --speaker-max-laplacian-var "${SPEAKER_FILTER_MAX_LAPLACIAN_VAR:-80}"
  --speaker-max-duration-sec "${SPEAKER_FILTER_MAX_DURATION_SEC:-2.5}"
)
if [ -f "$STAGE1_FILE" ]; then
  FILTER_ARGS+=(--stage1-file "$STAGE1_FILE")
fi

echo "[ASR] Filtering speaker-only slides and merging transcript ..."
"$PYTHON_BIN" "$ROOT_DIR/scripts/filter_and_merge_speaker_only.py" "${FILTER_ARGS[@]}"
echo "[ASR] Speaker-only filtering finished."

LATEST_LINK="$ROOT_DIR/output/latest"
if [ -L "$LATEST_LINK" ] || [ ! -e "$LATEST_LINK" ]; then
  ln -sfn "$RUN_DIR" "$LATEST_LINK"
fi

echo "Done."
echo "Run dir: $RUN_DIR"
echo "Main output: $OUT_BASE/slide_changes.csv"
echo "Transcript: $TRANSCRIPT_JSON"
echo "Slide text map: $SLIDE_TEXT_MAP_JSON"
echo "Final slide text map: $SLIDE_TEXT_MAP_FINAL_JSON"
