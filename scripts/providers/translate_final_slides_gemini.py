#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.lib.cloud_gemini_image import ensure_cloud_gemini_image_client

LOCAL_ENV_PATH = ROOT_DIR / ".env.local"
DEFAULT_PROMPT_PATH = ROOT_DIR / "config" / "prompts" / "gemini_translate_prompt.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate cleaned final slide ROI images with Gemini (Extract → Translate → Render)."
    )
    parser.add_argument("--input-dir", required=True, help="Directory with cleaned final slide images.")
    parser.add_argument("--output-dir", required=True, help="Directory for translated slide images.")
    parser.add_argument("--model", default="gemini-3-pro-image-preview", help="Gemini image model for rendering.")
    parser.add_argument("--extract-model", default="gemini-3.1-pro-preview", help="Gemini text model for extract + translate steps.")
    parser.add_argument("--extract-prompt", default="", help="Custom prompt for Step 1 (extract text from image).")
    parser.add_argument("--translate-prompt", default="", help="Custom prompt for Step 2 (translate JSON). Use {{TARGET_LANGUAGE}} as placeholder.")
    parser.add_argument("--render-prompt", default="", help="Custom prompt for Step 3 (render text onto image).")
    parser.add_argument(
        "--target-language",
        required=True,
        help="Target language label injected into the prompt, e.g. German or French.",
    )
    parser.add_argument(
        "--project-id",
        default="",
        help="Optional Google Cloud project id (used only for Vertex fallback when no GEMINI_API_KEY is set).",
    )
    parser.add_argument(
        "--location",
        default="",
        help="Optional Gemini location for Vertex fallback (e.g. global or us-central1).",
    )
    parser.add_argument("--out-manifest-json", default="", help="Output JSON manifest path for per-slide status.")
    parser.add_argument("--resume", action="store_true", default=False, help="Resume: skip slides already translated in a previous run.")
    # Legacy args accepted but ignored (kept for CLI compatibility)
    parser.add_argument("--prompt-file", default="", help=argparse.SUPPRESS)
    parser.add_argument("--termbase-file", default="", help=argparse.SUPPRESS)
    parser.add_argument("--slide-map-json", default="", help=argparse.SUPPRESS)
    parser.add_argument("--vision-project-id", default="", help=argparse.SUPPRESS)
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
    """Load a prompt template file and substitute the target language placeholder.

    Kept as a public API.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    template = path.read_text(encoding="utf-8").strip()
    if not template:
        raise RuntimeError(f"Prompt file is empty: {path}")
    prompt = template.replace("{{TARGET_LANGUAGE}}", target_language.strip())
    if "{{TARGET_LANGUAGE}}" not in template:
        prompt = f"Target language: {target_language.strip()}\n\n{prompt}"
    return prompt


def ensure_client(project_id: str, location: str):
    client, types, project_id_used, _default_project, location_used = ensure_cloud_gemini_image_client(
        project_id=project_id,
        location=location,
    )
    return client, types, project_id_used, location_used


def ensure_text_client():
    """Create a text-only genai Client using the GEMINI_API_KEY."""
    from google import genai

    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    return genai.Client(api_key=api_key)


def extract_response_text(response) -> str:
    """Extract the text content from a Gemini response."""
    if hasattr(response, "text") and response.text:
        return response.text
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) if content else None
        if parts:
            for part in parts:
                text = getattr(part, "text", None)
                if text:
                    return text
    return ""


def strip_code_fences(text: str) -> str:
    """Remove markdown code fences from a string."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


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
                if img is None:
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


def bbox_overlap_ratio(a: dict, b: dict) -> float:
    """Compute intersection-over-union for two {x, y, w, h} dicts.

    Kept as a public API.
    """
    ax1, ay1 = a["x"], a["y"]
    ax2, ay2 = ax1 + a["w"], ay1 + a["h"]
    bx1, by1 = b["x"], b["y"]
    bx2, by2 = bx1 + b["w"], by1 + b["h"]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = a["w"] * a["h"]
    area_b = b["w"] * b["h"]
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


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


# ---------------------------------------------------------------------------
# 3-Step Pipeline: Extract → Translate → Render
# ---------------------------------------------------------------------------


DEFAULT_EXTRACT_PROMPT = (
    "Extract all visible text from the image. Return a JSON object with a single key "
    '"text_elements" containing an array of objects, each with "id" (integer, starting at 1) '
    'and "text" (the exact text as shown on the image). Only include actual text visible in '
    "the image. Do not include descriptions of visual elements, backgrounds, or icons."
)

DEFAULT_TRANSLATE_PROMPT = (
    "Translate the following text elements to {{TARGET_LANGUAGE}}.\n"
    'Return a JSON array where each object has "id" (same as input), '
    '"original" (unchanged), and "translated".'
)

DEFAULT_RENDER_PROMPT = (
    "Replace the text in the image according to this mapping. "
    "Only replace the listed text elements. "
    "Do not alter any other visual elements, backgrounds, colors, or layout."
)


def extract_slide_json(client, model: str, image_bytes: bytes, prompt: str = "") -> dict:
    """Step 1: Extract all visible text elements from a slide image."""
    from google.genai import types

    prompt = prompt.strip() or DEFAULT_EXTRACT_PROMPT

    response = client.models.generate_content(
        model=model,
        contents=[
            prompt,
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
        ],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )

    raw = extract_response_text(response)
    raw = strip_code_fences(raw)
    return json.loads(raw)


def translate_slide_json(
    client,
    model: str,
    text_elements: list[dict],
    target_language: str,
    glossary: dict[str, str],
    prompt_template: str = "",
) -> list[dict]:
    """Step 2: Translate extracted text elements, using a glossary for consistency."""
    from google.genai import types

    base_prompt = (prompt_template.strip() or DEFAULT_TRANSLATE_PROMPT).replace(
        "{{TARGET_LANGUAGE}}", target_language,
    )

    glossary_section = ""
    if glossary:
        lines = [f'  - "{k}" → "{v}"' for k, v in glossary.items()]
        glossary_section = (
            "\n\nMANDATORY GLOSSARY — use these exact translations where applicable:\n"
            + "\n".join(lines)
        )

    prompt = (
        f"{base_prompt}"
        f"{glossary_section}\n\n"
        f"Input:\n{json.dumps(text_elements, ensure_ascii=False)}"
    )

    response = client.models.generate_content(
        model=model,
        contents=[prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )

    raw = extract_response_text(response)
    raw = strip_code_fences(raw)
    result = json.loads(raw)
    # Handle both bare array and {"translations": [...]} wrapper
    if isinstance(result, dict):
        for key in ("translations", "text_elements", "translated"):
            if key in result and isinstance(result[key], list):
                return result[key]
        return list(result.values())[0] if result else []
    return result


def render_translated_image(
    client, types, model: str, original: np.ndarray, mapping: list[dict], prompt_base: str = "",
) -> np.ndarray:
    """Step 3: Render the translated text onto the original slide image."""
    json_mapping = json.dumps(mapping, indent=2, ensure_ascii=False)
    base = prompt_base.strip() or DEFAULT_RENDER_PROMPT
    prompt = f"{base}\n\n{json_mapping}"

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
        raise RuntimeError("Gemini render response did not include an image.")
    translated = decode_image_bytes(image_bytes, original.shape)
    if translated is None:
        raise RuntimeError("Failed to decode Gemini render image response.")
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

    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not input_dir.exists():
        raise FileNotFoundError(input_dir)

    # Text-only client for extract + translate steps
    text_client = ensure_text_client()
    # Image client for render step
    image_client, types, project_id_used, location_used = ensure_client(args.project_id, args.location)

    print(f"[Translate] Gemini backend: {project_id_used}", flush=True)
    print(f"[Translate] Gemini endpoint/location: {location_used}", flush=True)
    print(f"[Translate] Extract/Translate model: {args.extract_model}", flush=True)
    print(f"[Translate] Render model: {args.model}", flush=True)
    out_manifest_path = Path(args.out_manifest_json).resolve() if args.out_manifest_json else None

    # Resume support: load existing manifest to skip completed slides
    existing_status: dict[str, str] = {}
    if args.resume and out_manifest_path and out_manifest_path.exists():
        try:
            prev = json.loads(out_manifest_path.read_text(encoding="utf-8"))
            for item in prev.get("items", []):
                name = item.get("name", "")
                status = item.get("status", "")
                if status in ("translated", "no_text") and (output_dir / name).exists():
                    existing_status[name] = status
            if existing_status:
                print(f"[Translate] Resume: {len(existing_status)} slides already processed, skipping.", flush=True)
        except Exception:
            pass

    if not args.resume:
        clear_pngs(output_dir)

    slide_paths = sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png")
    translated_count = 0
    fallback_count = 0
    glossary: dict[str, str] = {}
    manifest_items: list[dict[str, str]] = []

    # Resume: rebuild glossary from existing _mapping.json files (in slide order)
    if existing_status:
        for sp in slide_paths:
            if sp.name in existing_status and existing_status[sp.name] == "translated":
                mapping_file = output_dir / f"{sp.stem}_mapping.json"
                if mapping_file.exists():
                    try:
                        mapping_data = json.loads(mapping_file.read_text(encoding="utf-8"))
                        for entry in mapping_data:
                            orig = entry.get("original", "").strip()
                            trans = entry.get("translated", "").strip()
                            if orig and trans and orig != trans:
                                glossary[orig] = trans
                    except Exception:
                        pass
        if glossary:
            print(f"[Translate] Resume: rebuilt glossary with {len(glossary)} entries.", flush=True)

    for slide_path in slide_paths:
        dst_path = output_dir / slide_path.name
        print(f"@@STEP DETAIL translate {slide_path.name}")

        # Resume: reuse previously processed slide
        if slide_path.name in existing_status:
            prev_status = existing_status[slide_path.name]
            manifest_items.append({"name": slide_path.name, "status": prev_status, "reason": "resume"})
            if prev_status == "translated":
                translated_count += 1
            print(f"[Translate] Reused {slide_path.name} (resume, status={prev_status})")
            continue

        original = cv2.imread(str(slide_path), cv2.IMREAD_COLOR)
        if original is None or original.size == 0:
            shutil.copy2(slide_path, dst_path)
            fallback_count += 1
            manifest_items.append({"name": slide_path.name, "status": "fallback", "reason": "read_failed"})
            print(f"[Translate] Fallback {slide_path.name}: failed to read image.")
            continue

        image_bytes = encode_png(original)

        try:
            # Step 1: Extract text elements
            print(f"@@STEP DETAIL translate {slide_path.name}: Extract", flush=True)
            print(f"[Translate] [{slide_path.name}] Step 1/3: Extracting text ...", flush=True)
            extracted = extract_slide_json(text_client, str(args.extract_model), image_bytes, args.extract_prompt)
            text_elements = extracted.get("text_elements", [])

            if not text_elements:
                shutil.copy2(slide_path, dst_path)
                manifest_items.append({"name": slide_path.name, "status": "no_text"})
                print(f"[Translate] [{slide_path.name}] No text found — keeping original.")
                continue

            # Step 2: Translate text elements
            print(f"@@STEP DETAIL translate {slide_path.name}: Translate", flush=True)
            print(f"[Translate] [{slide_path.name}] Step 2/3: Translating {len(text_elements)} text elements ...", flush=True)
            mapping = translate_slide_json(
                text_client, str(args.extract_model), text_elements, target_language, glossary,
                args.translate_prompt,
            )

            # Step 3: Render translated image
            print(f"@@STEP DETAIL translate {slide_path.name}: Render", flush=True)
            print(f"[Translate] [{slide_path.name}] Step 3/3: Rendering translated image ...", flush=True)
            translated = render_translated_image(image_client, types, str(args.model), original, mapping, args.render_prompt)

            cv2.imwrite(str(dst_path), translated)
            translated_count += 1
            manifest_items.append({"name": slide_path.name, "status": "translated"})

            # Update glossary for next slides
            for entry in mapping:
                orig = entry.get("original", "").strip()
                trans = entry.get("translated", "").strip()
                if orig and trans and orig != trans:
                    glossary[orig] = trans

            # Save debug artifacts
            (output_dir / f"{slide_path.stem}_extracted.json").write_text(
                json.dumps(extracted, indent=2, ensure_ascii=False), encoding="utf-8",
            )
            (output_dir / f"{slide_path.stem}_mapping.json").write_text(
                json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8",
            )

            print(f"[Translate] Translated {slide_path.name}")

        except Exception as exc:  # noqa: BLE001
            shutil.copy2(slide_path, dst_path)
            fallback_count += 1
            manifest_items.append({"name": slide_path.name, "status": "fallback", "reason": str(exc)})
            print(f"[Translate] Fallback {slide_path.name}: {exc}")
            continue

    # Save final glossary
    if glossary:
        (output_dir / "_glossary.json").write_text(
            json.dumps(glossary, indent=2, ensure_ascii=False), encoding="utf-8",
        )

    if out_manifest_path:
        manifest = {"items": manifest_items, "translated_count": translated_count, "fallback_count": fallback_count}
        out_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        out_manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[Translate] Slides processed: {len(slide_paths)}")
    print(f"[Translate] Translated: {translated_count}")
    print(f"[Translate] Fallback: {fallback_count}")
    print(f"[Translate] Glossary entries: {len(glossary)}")
    print(f"[Translate] Target language: {target_language}")
    print(f"[Translate] Output dir: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
