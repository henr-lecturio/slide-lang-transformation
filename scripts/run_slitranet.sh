#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="$ROOT_DIR/config/slitranet.env"
VENV_DIR="$ROOT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "ERROR: .venv not found. Run: bash scripts/setup_venv.sh" >&2
  exit 1
fi

source "$VENV_DIR/bin/activate"

# shellcheck disable=SC1090
source "$CONFIG_FILE"

if [ -z "${PHASE:-}" ]; then
  PHASE="test"
fi

VIDEO_ABS="$ROOT_DIR/$VIDEO_PATH"
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

DATASET_DIR="$DATASET_DIR" bash "$ROOT_DIR/scripts/prepare_dataset.sh"
bash "$ROOT_DIR/scripts/check_weights.sh"

if ! python - <<'PY'
import torch
raise SystemExit(0 if torch.cuda.is_available() else 1)
PY
then
  echo "ERROR: torch.cuda.is_available() is False." >&2
  echo "The original SliTraNet inference script uses .cuda() and needs a CUDA-capable runtime." >&2
  exit 1
fi

pushd "$ROOT_DIR/slitranet" >/dev/null
python test_SliTraNet.py \
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

python "$ROOT_DIR/scripts/postprocess_slitranet.py" \
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

LATEST_LINK="$ROOT_DIR/output/latest"
if [ -L "$LATEST_LINK" ] || [ ! -e "$LATEST_LINK" ]; then
  ln -sfn "$RUN_DIR" "$LATEST_LINK"
fi

echo "Done."
echo "Run dir: $RUN_DIR"
echo "Main output: $OUT_BASE/slide_changes.csv"
