#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_FILE="$ROOT_DIR/config/slitranet.env"
DATASET_DIR="${DATASET_DIR:-$ROOT_DIR/dataset}"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "ERROR: config file missing: $CONFIG_FILE" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$CONFIG_FILE"

VIDEO_PATH_RESOLVED="${VIDEO_PATH_OVERRIDE:-${VIDEO_PATH:-}}"
if [ -z "$VIDEO_PATH_RESOLVED" ]; then
  echo "ERROR: video path missing. Set VIDEO_PATH in config or pass VIDEO_PATH_OVERRIDE." >&2
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
VIDEO_DIR="$DATASET_DIR/videos/$PHASE"
VIDEO_LINK="$VIDEO_DIR/$VIDEO_NAME"
ROI_FILE="$DATASET_DIR/videos/${PHASE}_bounding_box_list.txt"

mkdir -p "$VIDEO_DIR"

if [ -L "$VIDEO_LINK" ]; then
  ln -sfn "$VIDEO_ABS" "$VIDEO_LINK"
elif [ ! -e "$VIDEO_LINK" ]; then
  ln -s "$VIDEO_ABS" "$VIDEO_LINK"
fi

cat > "$ROI_FILE" <<EOF
Video,x0,y0,x1,y1
$VIDEO_BASE,$ROI_X0,$ROI_Y0,$ROI_X1,$ROI_Y1
EOF

echo "Prepared dataset:"
echo "  Dataset dir: $DATASET_DIR"
echo "  Video: $VIDEO_LINK"
echo "  ROI file: $ROI_FILE"
