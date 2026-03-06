#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.lib.translation_memory import DEFAULT_TERMBASE_PATH, append_glossary_to_prompt, load_termbase_entries
from scripts.lib.cloud_gemini_image import ensure_cloud_gemini_image_client
from scripts.lib.slide_glossary import parse_event_id_from_name

LOCAL_ENV_PATH = ROOT_DIR / ".env.local"
DEFAULT_PROMPT_PATH = ROOT_DIR / "config" / "prompts" / "gemini_translate_prompt.txt"


RETRY_PROMPT_SUFFIX = (
    "\n\nCRITICAL: Your previous output changed the background, layout, or visual elements beyond just the text. "
    "You MUST only replace text elements. Do NOT alter backgrounds, images, icons, colors, or layout in any way. "
    "The output image must be pixel-identical to the input except where text was replaced."
)


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
    parser.add_argument(
        "--slide-map-json",
        default="",
        help="Path to translated slide text map JSON (slide_text_map_final_translated.json) for transcript context.",
    )
    parser.add_argument(
        "--vision-project-id",
        default="",
        help="Google Cloud project id for Cloud Vision OCR (cross-slide glossary).",
    )
    parser.add_argument(
        "--review-threshold",
        type=float,
        default=0.08,
        help="Max allowed mean pixel diff in non-text regions (0.0–1.0). Set to 0 to disable review.",
    )
    parser.add_argument(
        "--max-review-retries",
        type=int,
        default=3,
        help="Retry attempts before fallback to original slide.",
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


def ensure_client(project_id: str, location: str):
    client, types, project_id_used, _default_project, location_used = ensure_cloud_gemini_image_client(
        project_id=project_id,
        location=location,
    )
    return client, types, project_id_used, location_used


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


def get_text_bboxes(
    image: np.ndarray,
    vision_client=None,
    vision_module=None,
    image_path: Path | None = None,
    event_id: int | None = None,
) -> list[dict]:
    """Detect text bounding boxes on the slide image.

    Uses Cloud Vision OCR when available, otherwise falls back to OpenCV contour detection.
    Returns list of {x, y, w, h} dicts.
    """
    if vision_client is not None and image_path is not None and event_id is not None:
        try:
            from scripts.lib.slide_ocr import ocr_slide_fragments

            result = ocr_slide_fragments(
                vision_client, vision_module, image_path=image_path, event_id=event_id, slide_index=0,
            )
            units = result.get("text_units", []) or result.get("fragments", [])
            bboxes = [u["bbox"] for u in units if u.get("bbox")]
            if bboxes:
                return bboxes
        except Exception:  # noqa: BLE001
            pass

    # Fallback: OpenCV contour-based text region approximation
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 4)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h_img, w_img = image.shape[:2]
    min_area = (h_img * w_img) * 0.0002  # filter tiny noise
    bboxes: list[dict] = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w * h >= min_area:
            bboxes.append({"x": x, "y": y, "w": w, "h": h})
    return bboxes


def review_translated_slide(
    original: np.ndarray,
    translated: np.ndarray,
    text_bboxes: list[dict],
    threshold: float,
    padding: int = 10,
) -> tuple[bool, float]:
    """Compare non-text regions between original and translated slide.

    Returns (passed, score) where score is the mean absolute pixel difference
    in non-text regions, normalized to 0.0–1.0.
    """
    h, w = original.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    for bbox in text_bboxes:
        x1 = max(0, bbox["x"] - padding)
        y1 = max(0, bbox["y"] - padding)
        x2 = min(w, bbox["x"] + bbox["w"] + padding)
        y2 = min(h, bbox["y"] + bbox["h"] + padding)
        mask[y1:y2, x1:x2] = 255

    gray_orig = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray_trans = cv2.cvtColor(translated, cv2.COLOR_BGR2GRAY).astype(np.float32)

    # Non-text pixels: where mask == 0
    non_text_mask = mask == 0
    non_text_count = int(np.count_nonzero(non_text_mask))
    if non_text_count == 0:
        return True, 0.0

    diff = np.abs(gray_orig - gray_trans)
    score = float(np.mean(diff[non_text_mask]) / 255.0)
    return score <= threshold, score


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


def load_slide_text_map(path: str) -> dict[int, str]:
    """Load translated slide text map and return {event_id: translated_text}."""
    p = Path(path).resolve() if path else None
    if not p or not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    events = data if isinstance(data, list) else data.get("events", data.get("slides", []))
    lookup: dict[int, str] = {}
    for entry in events:
        eid = int(entry.get("event_id", 0) or 0)
        text = str(entry.get("translated_text", "") or "").strip()
        if eid and text:
            lookup[eid] = text
    return lookup


def bbox_overlap_ratio(a: dict, b: dict) -> float:
    """Compute intersection-over-union for two {x, y, w, h} dicts."""
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


def build_cross_slide_glossary_entries(
    vision_client,
    vision_module,
    original_path: Path,
    translated_path: Path,
    event_id: int,
) -> list[tuple[str, str]]:
    """OCR original and translated slides, match text by bbox overlap, return (orig, translated) pairs."""
    from scripts.lib.slide_ocr import ocr_slide_fragments

    orig_result = ocr_slide_fragments(
        vision_client, vision_module, image_path=original_path, event_id=event_id, slide_index=0,
    )
    trans_result = ocr_slide_fragments(
        vision_client, vision_module, image_path=translated_path, event_id=event_id, slide_index=0,
    )
    orig_units = orig_result.get("text_units", []) or orig_result.get("fragments", [])
    trans_units = trans_result.get("text_units", []) or trans_result.get("fragments", [])

    pairs: list[tuple[str, str]] = []
    used_trans: set[int] = set()
    for ou in orig_units:
        orig_text = str(ou.get("text_norm", "") or ou.get("text_raw", "") or "").strip()
        orig_bbox = ou.get("bbox")
        if not orig_text or not orig_bbox:
            continue
        best_iou = 0.0
        best_idx = -1
        for ti, tu in enumerate(trans_units):
            if ti in used_trans:
                continue
            trans_bbox = tu.get("bbox")
            if not trans_bbox:
                continue
            iou = bbox_overlap_ratio(orig_bbox, trans_bbox)
            if iou > best_iou:
                best_iou = iou
                best_idx = ti
        if best_iou >= 0.3 and best_idx >= 0:
            trans_text = str(trans_units[best_idx].get("text_norm", "") or trans_units[best_idx].get("text_raw", "") or "").strip()
            if trans_text and trans_text != orig_text:
                pairs.append((orig_text, trans_text))
                used_trans.add(best_idx)
    return pairs


def format_transcript_context(transcript_text: str) -> str:
    return (
        '\n\nSPEAKER SCRIPT FOR THIS SLIDE (use as context to understand meaning, '
        'but the slide text may differ from what the speaker says):\n"""\n'
        + transcript_text.strip()
        + '\n"""\n'
        "Use the speaker script to understand context and domain terminology. "
        "However, the slide may use different wording than the speaker "
        "(e.g. slide says 'Anti-discrimination' while speaker says 'discrimination'). "
        "Always translate what is actually written on the slide, not what the speaker says. "
        "If a CROSS-SLIDE GLOSSARY is provided below, it ALWAYS takes priority over the speaker script."
    )


def format_glossary_context(glossary: dict[str, str]) -> str:
    if not glossary:
        return ""
    lines = [
        "\n\nCROSS-SLIDE GLOSSARY — MANDATORY (you MUST use these exact translations, "
        "they override any other context including the speaker script):"
    ]
    for orig, trans in glossary.items():
        lines.append(f'- "{orig}" → "{trans}"')
    return "\n".join(lines)


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
    base_prompt = append_glossary_to_prompt(load_prompt(Path(args.prompt_file).resolve(), target_language), termbase_entries)
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not input_dir.exists():
        raise FileNotFoundError(input_dir)

    # Load translated transcript map for per-slide context injection
    transcript_lookup = load_slide_text_map(args.slide_map_json)
    if transcript_lookup:
        print(f"[Translate] Transcript context: {len(transcript_lookup)} events loaded.", flush=True)

    # Set up Vision OCR client for cross-slide glossary (optional)
    vision_client = None
    vision_module = None
    vision_project_id = str(args.vision_project_id or "").strip()
    if vision_project_id:
        try:
            from scripts.lib.slide_ocr import ensure_cloud_vision_client
            vision_client, vision_module, _vp, _dp = ensure_cloud_vision_client(vision_project_id)
            print(f"[Translate] Cross-slide OCR enabled (project: {vision_project_id}).", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[Translate] Cross-slide OCR disabled: {exc}", flush=True)

    client, types, project_id_used, location_used = ensure_client(args.project_id, args.location)
    print(f"[Translate] Gemini backend: {project_id_used}", flush=True)
    print(f"[Translate] Gemini endpoint/location: {location_used}", flush=True)
    clear_pngs(output_dir)

    review_threshold = float(args.review_threshold)
    max_review_retries = int(args.max_review_retries)
    review_enabled = review_threshold > 0
    if review_enabled:
        print(f"[Translate] Structural review enabled: threshold={review_threshold}, max_retries={max_review_retries}", flush=True)

    slide_paths = sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png")
    translated_count = 0
    fallback_count = 0
    review_failed_count = 0
    cross_slide_glossary: dict[str, str] = {}
    slide_report: list[dict] = []

    for slide_path in slide_paths:
        dst_path = output_dir / slide_path.name
        print(f"@@STEP DETAIL translate {slide_path.name}")
        original = cv2.imread(str(slide_path), cv2.IMREAD_COLOR)
        if original is None or original.size == 0:
            shutil.copy2(slide_path, dst_path)
            fallback_count += 1
            slide_report.append({"slide": slide_path.name, "status": "fallback", "note": "failed to read image"})
            print(f"[Translate] Fallback {slide_path.name}: failed to read image.")
            continue

        # Build per-slide prompt with transcript context and cross-slide glossary
        slide_prompt = base_prompt
        event_id = parse_event_id_from_name(slide_path.stem)
        if event_id is not None and event_id in transcript_lookup:
            slide_prompt += format_transcript_context(transcript_lookup[event_id])
        slide_prompt += format_glossary_context(cross_slide_glossary)

        try:
            translated = generate_translated_image(client, types, str(args.model), slide_prompt, original)
        except Exception as exc:  # noqa: BLE001
            shutil.copy2(slide_path, dst_path)
            fallback_count += 1
            slide_report.append({"slide": slide_path.name, "status": "fallback", "note": f"generation error: {exc}"})
            print(f"[Translate] Fallback {slide_path.name}: {exc}")
            continue

        # Structural review: compare non-text regions
        if review_enabled:
            text_bboxes = get_text_bboxes(
                original,
                vision_client=vision_client,
                vision_module=vision_module,
                image_path=slide_path,
                event_id=event_id,
            )
            passed, score = review_translated_slide(original, translated, text_bboxes, review_threshold)
            print(f"[Translate] Review {slide_path.name}: score={score:.3f} {'passed' if passed else 'FAILED'}", flush=True)

            if not passed:
                for retry in range(max_review_retries):
                    retry_prompt = slide_prompt + RETRY_PROMPT_SUFFIX
                    try:
                        translated = generate_translated_image(client, types, str(args.model), retry_prompt, original)
                    except Exception as exc:  # noqa: BLE001
                        print(f"[Translate] Retry {retry + 1}/{max_review_retries} for {slide_path.name} failed: {exc}", flush=True)
                        continue
                    passed, score = review_translated_slide(original, translated, text_bboxes, review_threshold)
                    print(f"[Translate] Retry {retry + 1}/{max_review_retries} for {slide_path.name}: score={score:.3f} {'passed' if passed else 'FAILED'}", flush=True)
                    if passed:
                        break

                if not passed:
                    shutil.copy2(slide_path, dst_path)
                    review_failed_count += 1
                    fallback_count += 1
                    slide_report.append({"slide": slide_path.name, "status": "fallback", "note": "fallback: review retries failed", "review_score": round(score, 3)})
                    print(f"[Translate] Review fallback {slide_path.name}: kept original after {max_review_retries} retries.", flush=True)
                    continue

        cv2.imwrite(str(dst_path), translated)
        translated_count += 1
        slide_report.append({"slide": slide_path.name, "status": "translated"})
        print(f"[Translate] Translated {slide_path.name}")

        # Cross-slide OCR feedback: build glossary from original↔translated pairs
        if vision_client is not None and event_id is not None:
            try:
                pairs = build_cross_slide_glossary_entries(
                    vision_client, vision_module, slide_path, dst_path, event_id,
                )
                for orig_text, trans_text in pairs:
                    if orig_text not in cross_slide_glossary:
                        cross_slide_glossary[orig_text] = trans_text
                if pairs:
                    print(f"[Translate] Cross-slide glossary: +{len(pairs)} entries from {slide_path.name}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[Translate] Cross-slide OCR skipped for {slide_path.name}: {exc}", flush=True)

    # Save per-slide translation report
    report_path = output_dir / "translation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(slide_report, f, ensure_ascii=False, indent=2)
    print(f"[Translate] Report saved: {report_path}", flush=True)

    # Save cross-slide glossary artifact
    if cross_slide_glossary:
        glossary_path = output_dir / "cross_slide_glossary.json"
        with open(glossary_path, "w", encoding="utf-8") as f:
            json.dump(cross_slide_glossary, f, ensure_ascii=False, indent=2)
        print(f"[Translate] Cross-slide glossary saved: {glossary_path} ({len(cross_slide_glossary)} entries)", flush=True)

    print(f"[Translate] Slides processed: {len(slide_paths)}")
    print(f"[Translate] Translated: {translated_count}")
    print(f"[Translate] Fallback: {fallback_count}")
    if review_enabled:
        print(f"[Translate] Review failed (kept original): {review_failed_count}")
    print(f"[Translate] Target language: {target_language}")
    print(f"[Translate] Termbase glossary entries: {len(termbase_entries)}")
    print(f"[Translate] Termbase file: {termbase_file}")
    print(f"[Translate] Prompt file: {Path(args.prompt_file).resolve()}")
    print(f"[Translate] Output dir: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
