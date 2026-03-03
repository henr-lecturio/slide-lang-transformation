#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import io
import os
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.translation_memory import DEFAULT_TERMBASE_PATH, append_glossary_to_prompt, load_termbase_entries

LOCAL_ENV_PATH = ROOT_DIR / ".env.local"
DEFAULT_PROMPT_PATH = ROOT_DIR / "config" / "gemini_translate_prompt.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate cleaned final slide ROI images with Gemini image-to-image editing."
    )
    parser.add_argument("--input-dir", required=True, help="Directory with cleaned final slide images.")
    parser.add_argument("--output-dir", required=True, help="Directory for translated slide images.")
    parser.add_argument("--model", default="gemini-3-pro-image-preview", help="Gemini image model.")
    parser.add_argument(
        "--prompt-file",
        default=str(DEFAULT_PROMPT_PATH),
        help="Path to the Gemini translation prompt text file.",
    )
    parser.add_argument(
        "--target-language",
        required=True,
        help="Target language label injected into the prompt, e.g. German or French.",
    )
    parser.add_argument(
        "--termbase-file",
        default=str(DEFAULT_TERMBASE_PATH),
        help="CSV termbase applied as glossary instructions to the image translation prompt.",
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


def load_prompt(path: Path, target_language: str) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    template = path.read_text(encoding="utf-8").strip()
    if not template:
        raise RuntimeError(f"Prompt file is empty: {path}")
    prompt = template.replace("{{TARGET_LANGUAGE}}", target_language.strip())
    if "{{TARGET_LANGUAGE}}" not in template:
        prompt = f"Target language: {target_language.strip()}\n\n{prompt}"
    return prompt


def ensure_client():
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-genai is not installed in this environment. "
            "Run: source .venv/bin/activate && pip install google-genai"
        ) from exc

    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")
    return genai.Client(api_key=api_key), types


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


def generate_translated_image(client, types, model: str, prompt: str, original: np.ndarray) -> np.ndarray:
    response = client.models.generate_content(
        model=model,
        contents=[
            prompt,
            types.Part.from_bytes(data=encode_png(original), mime_type="image/png"),
        ],
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
    )
    image_bytes = extract_image_bytes(response)
    if not image_bytes:
        raise RuntimeError("Gemini response did not include an image.")
    translated = decode_image_bytes(image_bytes, original.shape)
    if translated is None:
        raise RuntimeError("Failed to decode Gemini image response.")
    return translated


def clear_pngs(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for p in path.glob("*.png"):
        p.unlink()


def main() -> int:
    args = parse_args()
    load_local_env(LOCAL_ENV_PATH)
    target_language = str(args.target_language).strip()
    if not target_language:
        raise RuntimeError("--target-language must not be empty.")

    termbase_file = Path(args.termbase_file).resolve()
    termbase_entries = load_termbase_entries(termbase_file, target_language)
    prompt = append_glossary_to_prompt(load_prompt(Path(args.prompt_file).resolve(), target_language), termbase_entries)
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not input_dir.exists():
        raise FileNotFoundError(input_dir)

    client, types = ensure_client()
    clear_pngs(output_dir)

    slide_paths = sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png")
    translated_count = 0
    fallback_count = 0

    for slide_path in slide_paths:
        dst_path = output_dir / slide_path.name
        print(f"@@STEP DETAIL translate {slide_path.name}")
        original = cv2.imread(str(slide_path), cv2.IMREAD_COLOR)
        if original is None or original.size == 0:
            shutil.copy2(slide_path, dst_path)
            fallback_count += 1
            print(f"[Translate] Fallback {slide_path.name}: failed to read image.")
            continue

        try:
            translated = generate_translated_image(client, types, str(args.model), prompt, original)
        except Exception as exc:  # noqa: BLE001
            shutil.copy2(slide_path, dst_path)
            fallback_count += 1
            print(f"[Translate] Fallback {slide_path.name}: {exc}")
            continue

        cv2.imwrite(str(dst_path), translated)
        translated_count += 1
        print(f"[Translate] Translated {slide_path.name}")

    print(f"[Translate] Slides processed: {len(slide_paths)}")
    print(f"[Translate] Translated: {translated_count}")
    print(f"[Translate] Fallback: {fallback_count}")
    print(f"[Translate] Target language: {target_language}")
    print(f"[Translate] Termbase glossary entries: {len(termbase_entries)}")
    print(f"[Translate] Termbase file: {termbase_file}")
    print(f"[Translate] Prompt file: {Path(args.prompt_file).resolve()}")
    print(f"[Translate] Output dir: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
