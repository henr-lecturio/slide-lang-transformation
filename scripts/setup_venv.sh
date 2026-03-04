#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found." >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r "$ROOT_DIR/slitranet/requirements.txt"
"$PYTHON_BIN" -m pip install faster-whisper
"$PYTHON_BIN" -m pip install google-cloud-speech
"$PYTHON_BIN" -m pip install "google-cloud-texttospeech>=2.31.0"
"$PYTHON_BIN" -m pip install google-cloud-vision
"$PYTHON_BIN" -m pip install google-genai
"$PYTHON_BIN" -m pip install replicate
"$PYTHON_BIN" -m pip install transformers safetensors
