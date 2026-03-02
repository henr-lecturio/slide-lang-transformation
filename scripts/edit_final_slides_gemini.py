#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import csv
import io
import os
import re
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from filter_and_merge_speaker_only import build_final_corner_cleanup_mask


ROOT_DIR = Path(__file__).resolve().parent.parent
LOCAL_ENV_PATH = ROOT_DIR / ".env.local"
DEFAULT_PROMPT_PATH = ROOT_DIR / "config" / "gemini_edit_prompt.txt"
SLIDE_INDEX_RE = re.compile(r"^slide_(\d{3})_")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Gemini image editing on raw final slide ROI images."
    )
    parser.add_argument("--input-dir", required=True, help="Directory with raw final slide images.")
    parser.add_argument("--output-dir", required=True, help="Directory for edited slide images.")
    parser.add_argument("--model", default="gemini-3-pro-image-preview", help="Gemini image model.")
    parser.add_argument(
        "--prompt-file",
        default=str(DEFAULT_PROMPT_PATH),
        help="Path to the Gemini edit prompt text file.",
    )
    parser.add_argument(
        "--skip-first-slide",
        type=int,
        default=1,
        help="Skip Gemini editing for the first N slide images (default: 1).",
    )
    parser.add_argument(
        "--source-manifest-csv",
        default="",
        help="Optional final image source manifest. Slides with source_mode_final=full are copied through unchanged.",
    )
    parser.add_argument("--mask-debug-dir", default="", help="Optional output directory for binary masks.")
    parser.add_argument(
        "--overlay-debug-dir",
        default="",
        help="Optional output directory for red overlay guide images.",
    )
    return parser.parse_args()


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_prompt(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"Prompt file is empty: {path}")
    return text


def ensure_client():
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover - import error path depends on env
        raise RuntimeError(
            "google-genai is not installed in this environment. "
            "Run: source .venv/bin/activate && pip install google-genai"
        ) from exc

    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")

    return genai.Client(api_key=api_key), types


def slide_index_from_name(path: Path) -> int | None:
    match = SLIDE_INDEX_RE.match(path.name)
    if not match:
        return None


def load_source_manifest(path: Path | None) -> dict[int, str]:
    if path is None or not path.exists():
        return {}
    out: dict[int, str] = {}
    with path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                slide_index = int(row.get("slide_index", "0") or "0")
            except ValueError:
                continue
            if slide_index <= 0:
                continue
            mode = str(row.get("source_mode_final", "") or "").strip().lower()
            if mode in {"slide", "full"}:
                out[slide_index] = mode
    return out
    try:
        return int(match.group(1))
    except ValueError:
        return None


def make_overlay(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    overlay = image.copy()
    active = mask > 0
    red = np.zeros_like(overlay)
    red[:, :, 2] = 255
    overlay[active] = cv2.addWeighted(overlay, 0.35, red, 0.65, 0)[active]

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(overlay, contours, -1, (0, 0, 255), 2)
    return overlay


def encode_png(image: np.ndarray) -> bytes:
    ok, data = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("Failed to encode PNG image.")
    return data.tobytes()


def extract_image_bytes(response) -> bytes | None:
    part_sets = []
    direct_parts = getattr(response, "parts", None)
    if direct_parts:
        part_sets.append(direct_parts)

    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None)
        if parts:
            part_sets.append(parts)

    for parts in part_sets:
        for part in parts:
            inline_data = getattr(part, "inline_data", None)
            data = getattr(inline_data, "data", None)
            if data:
                if isinstance(data, bytes):
                    return data
                if isinstance(data, str):
                    try:
                        return base64.b64decode(data)
                    except Exception:
                        pass

            as_image = getattr(part, "as_image", None)
            if callable(as_image):
                try:
                    img = as_image()
                except Exception:
                    continue
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()
    return None


def decode_image_bytes(data: bytes, expected_shape: tuple[int, int, int]) -> np.ndarray | None:
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        try:
            pil_img = Image.open(io.BytesIO(data)).convert("RGB")
        except Exception:
            return None
        image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    if image.shape[:2] != expected_shape[:2]:
        image = cv2.resize(image, (expected_shape[1], expected_shape[0]), interpolation=cv2.INTER_AREA)
    return image


def generate_edited_image(
    client,
    types,
    model: str,
    prompt: str,
    original: np.ndarray,
    overlay: np.ndarray,
    mask: np.ndarray,
) -> np.ndarray:
    response = client.models.generate_content(
        model=model,
        contents=[
            prompt,
            types.Part.from_bytes(data=encode_png(original), mime_type="image/png"),
            types.Part.from_bytes(data=encode_png(overlay), mime_type="image/png"),
            types.Part.from_bytes(data=encode_png(mask), mime_type="image/png"),
        ],
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
    )
    image_bytes = extract_image_bytes(response)
    if not image_bytes:
        raise RuntimeError("Gemini response did not include an image.")
    edited = decode_image_bytes(image_bytes, original.shape)
    if edited is None:
        raise RuntimeError("Failed to decode Gemini image response.")
    return edited


def clear_pngs(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for p in path.glob("*.png"):
        p.unlink()


def main() -> int:
    args = parse_args()
    load_local_env(LOCAL_ENV_PATH)
    prompt = load_prompt(Path(args.prompt_file).resolve())
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    source_manifest_csv = Path(args.source_manifest_csv).resolve() if args.source_manifest_csv else None
    mask_debug_dir = Path(args.mask_debug_dir).resolve() if args.mask_debug_dir else None
    overlay_debug_dir = Path(args.overlay_debug_dir).resolve() if args.overlay_debug_dir else None

    if not input_dir.exists():
        raise FileNotFoundError(input_dir)

    client, types = ensure_client()
    source_modes = load_source_manifest(source_manifest_csv)
    clear_pngs(output_dir)
    if mask_debug_dir is not None:
        clear_pngs(mask_debug_dir)
    if overlay_debug_dir is not None:
        clear_pngs(overlay_debug_dir)

    slide_paths = sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png")
    edited_count = 0
    skipped_count = 0
    fallback_count = 0

    for slide_path in slide_paths:
        dst_path = output_dir / slide_path.name
        slide_idx = slide_index_from_name(slide_path)
        print(f"@@STEP DETAIL edit {slide_path.name}")

        if slide_idx is not None and slide_idx <= max(0, int(args.skip_first_slide)):
            shutil.copy2(slide_path, dst_path)
            skipped_count += 1
            print(f"[Gemini] Skip {slide_path.name}: configured skip window.")
            continue
        if slide_idx is not None and source_modes.get(slide_idx) == "full":
            shutil.copy2(slide_path, dst_path)
            skipped_count += 1
            print(f"[Gemini] Skip {slide_path.name}: final source is full.")
            continue

        original = cv2.imread(str(slide_path), cv2.IMREAD_COLOR)
        if original is None or original.size == 0:
            shutil.copy2(slide_path, dst_path)
            fallback_count += 1
            print(f"[Gemini] Fallback {slide_path.name}: failed to read image.")
            continue

        mask = build_final_corner_cleanup_mask(original)
        if mask is None or not np.any(mask):
            shutil.copy2(slide_path, dst_path)
            skipped_count += 1
            print(f"[Gemini] Skip {slide_path.name}: no cleanup mask.")
            continue

        overlay = make_overlay(original, mask)
        if mask_debug_dir is not None:
            cv2.imwrite(str(mask_debug_dir / slide_path.name), mask)
        if overlay_debug_dir is not None:
            cv2.imwrite(str(overlay_debug_dir / slide_path.name), overlay)

        try:
            edited = generate_edited_image(client, types, str(args.model), prompt, original, overlay, mask)
        except Exception as exc:  # noqa: BLE001
            shutil.copy2(slide_path, dst_path)
            fallback_count += 1
            print(f"[Gemini] Fallback {slide_path.name}: {exc}")
            continue

        cv2.imwrite(str(dst_path), edited)
        edited_count += 1
        print(f"[Gemini] Edited {slide_path.name}")

    print(f"[Gemini] Slides processed: {len(slide_paths)}")
    print(f"[Gemini] Edited: {edited_count}")
    print(f"[Gemini] Skipped: {skipped_count}")
    print(f"[Gemini] Raw fallback: {fallback_count}")
    print(f"[Gemini] Prompt file: {Path(args.prompt_file).resolve()}")
    if source_manifest_csv is not None:
        print(f"[Gemini] Source manifest: {source_manifest_csv}")
    print(f"[Gemini] Output dir: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
