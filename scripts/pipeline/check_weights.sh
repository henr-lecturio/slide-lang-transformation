#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEIGHTS_DIR="$ROOT_DIR/weights"

required=(
  "Frame_similarity_ResNet18_gray.pth"
  "Slide_video_detection_3DResNet50.pth"
  "Slide_transition_detection_3DResNet50.pth"
)

missing=0
for file in "${required[@]}"; do
  if [ ! -f "$WEIGHTS_DIR/$file" ]; then
    echo "Missing: $WEIGHTS_DIR/$file"
    missing=1
  fi
done

if [ "$missing" -ne 0 ]; then
  echo
  echo "Download the 3 pretrained weights from:"
  echo "https://drive.google.com/drive/folders/1aQDVplbbpt-zgH2O1q7685AZ1hl0BsVV?usp=sharing"
  echo "and place them in: $WEIGHTS_DIR"
  exit 1
fi

echo "All required weights found."
