#!/usr/bin/env python3
"""Post-translation consistency review for slide sequences.

Detects slide sequences (incrementally built bullet points on the same slide),
checks translation consistency across the sequence using OCR, and corrects
inconsistent slides via re-translation with an explicit per-element glossary
or pixel-transplant as fallback.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.lib.slide_ocr import ensure_cloud_vision_client, ocr_slide_fragments
from scripts.lib.slide_glossary import parse_event_id_from_name
from scripts.lib.translation_memory import DEFAULT_TERMBASE_PATH, append_glossary_to_prompt, load_termbase_entries
from scripts.lib.cloud_gemini_image import ensure_cloud_gemini_image_client
from scripts.providers.translate_final_slides_gemini import (
    bbox_overlap_ratio,
    decode_image_bytes,
    encode_png,
    extract_image_bytes,
    generate_translated_image,
    load_prompt,
)

LOCAL_ENV_PATH = ROOT_DIR / ".env.local"
DEFAULT_PROMPT_PATH = ROOT_DIR / "config" / "prompts" / "gemini_translate_prompt.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review and fix translation consistency across slide sequences."
    )
    parser.add_argument("--original-dir", required=True, help="Directory with original slide PNGs.")
    parser.add_argument("--translated-dir", required=True, help="Directory with translated slide PNGs (modified in-place).")
    parser.add_argument("--vision-project-id", required=True, help="Google Cloud project ID for Vision OCR.")
    parser.add_argument("--vision-feature", default="DOCUMENT_TEXT_DETECTION", help="Vision OCR feature type.")
    parser.add_argument("--model", default="gemini-3-pro-image-preview", help="Gemini image model for re-translation.")
    parser.add_argument("--prompt-file", default=str(DEFAULT_PROMPT_PATH), help="Base translation prompt file.")
    parser.add_argument("--target-language", required=True, help="Target language label (e.g. German).")
    parser.add_argument("--termbase-file", default=str(DEFAULT_TERMBASE_PATH), help="CSV termbase for glossary.")
    parser.add_argument("--project-id", default="", help="Gemini project ID (Vertex fallback).")
    parser.add_argument("--location", default="", help="Gemini location (Vertex fallback).")
    parser.add_argument("--max-retries", type=int, default=2, help="Max re-translation attempts per slide.")
    parser.add_argument("--sequence-threshold", type=float, default=0.08, help="Max pixel-diff for sequence detection fallback.")
    parser.add_argument("--report-json", default="", help="Output report path (default: translated-dir/consistency_report.json).")
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


# ---------------------------------------------------------------------------
# Step A: Sequence Detection
# ---------------------------------------------------------------------------

def ocr_all_slides(
    slide_paths: list[Path],
    vision_client,
    vision_module,
    feature: str,
) -> dict[str, dict]:
    """OCR all slides, returning {filename: ocr_result} with text_units."""
    cache: dict[str, dict] = {}
    for path in slide_paths:
        event_id = parse_event_id_from_name(path.stem)
        if event_id is None:
            continue
        try:
            result = ocr_slide_fragments(
                vision_client, vision_module,
                image_path=path, event_id=event_id, slide_index=0,
                feature=feature,
            )
            cache[path.name] = result
        except Exception as exc:  # noqa: BLE001
            print(f"[Review] OCR failed for {path.name}: {exc}", flush=True)
    return cache


def text_units_from_ocr(ocr_result: dict) -> list[dict]:
    """Extract text units with bbox and normalized text from OCR result."""
    units = ocr_result.get("text_units", []) or ocr_result.get("fragments", [])
    return [u for u in units if u.get("bbox") and (u.get("source_text_norm") or u.get("text_norm") or u.get("source_text") or u.get("text_raw"))]


def unit_text(u: dict) -> str:
    """Get normalized text from a text unit."""
    return str(u.get("source_text_norm") or u.get("text_norm") or u.get("source_text") or u.get("text_raw") or "").strip()


def is_superset(units_a: list[dict], units_b: list[dict], min_overlap: float = 0.3) -> bool:
    """Check if B contains all text units from A (by bbox overlap) and at least one more."""
    if not units_a or not units_b:
        return False
    matched_a = 0
    used_b: set[int] = set()
    for ua in units_a:
        bbox_a = ua["bbox"]
        for bi, ub in enumerate(units_b):
            if bi in used_b:
                continue
            if bbox_overlap_ratio(bbox_a, ub["bbox"]) >= min_overlap:
                matched_a += 1
                used_b.add(bi)
                break
    return matched_a == len(units_a) and len(units_b) > len(units_a)


def detect_sequences(
    slide_names: list[str],
    ocr_cache: dict[str, dict],
) -> list[list[str]]:
    """Detect slide sequences where each slide is a superset of the previous."""
    sequences: list[list[str]] = []
    current_seq: list[str] = []

    for i, name in enumerate(slide_names):
        if name not in ocr_cache:
            if len(current_seq) >= 2:
                sequences.append(current_seq)
            current_seq = []
            continue

        units_curr = text_units_from_ocr(ocr_cache[name])
        if not current_seq:
            current_seq = [name]
            continue

        prev_name = current_seq[-1]
        units_prev = text_units_from_ocr(ocr_cache[prev_name])

        if is_superset(units_prev, units_curr):
            current_seq.append(name)
        else:
            if len(current_seq) >= 2:
                sequences.append(current_seq)
            current_seq = [name]

    if len(current_seq) >= 2:
        sequences.append(current_seq)

    return sequences


# ---------------------------------------------------------------------------
# Step B: Consistency Check
# ---------------------------------------------------------------------------

def build_canonical_glossary(
    orig_ocr: dict,
    trans_ocr: dict,
    min_overlap: float = 0.3,
) -> dict[str, str]:
    """Build {original_text: translated_text} glossary from reference slide pair."""
    orig_units = text_units_from_ocr(orig_ocr)
    trans_units = text_units_from_ocr(trans_ocr)
    glossary: dict[str, str] = {}
    used_trans: set[int] = set()

    for ou in orig_units:
        orig_text = unit_text(ou)
        if not orig_text:
            continue
        best_iou = 0.0
        best_idx = -1
        for ti, tu in enumerate(trans_units):
            if ti in used_trans:
                continue
            iou = bbox_overlap_ratio(ou["bbox"], tu["bbox"])
            if iou > best_iou:
                best_iou = iou
                best_idx = ti
        if best_iou >= min_overlap and best_idx >= 0:
            trans_text = unit_text(trans_units[best_idx])
            if trans_text and trans_text != orig_text:
                glossary[orig_text] = trans_text
                used_trans.add(best_idx)

    return glossary


def check_consistency(
    slide_name: str,
    orig_ocr: dict,
    trans_ocr: dict,
    canonical_glossary: dict[str, str],
    min_overlap: float = 0.3,
) -> list[dict]:
    """Check if translated slide matches canonical glossary. Returns list of inconsistencies."""
    orig_units = text_units_from_ocr(orig_ocr)
    trans_units = text_units_from_ocr(trans_ocr)
    inconsistencies: list[dict] = []

    # Match original units to translated units by bbox
    for ou in orig_units:
        orig_text = unit_text(ou)
        if orig_text not in canonical_glossary:
            continue
        expected = canonical_glossary[orig_text]

        # Find matching translated unit
        best_iou = 0.0
        best_idx = -1
        for ti, tu in enumerate(trans_units):
            iou = bbox_overlap_ratio(ou["bbox"], tu["bbox"])
            if iou > best_iou:
                best_iou = iou
                best_idx = ti

        if best_iou >= min_overlap and best_idx >= 0:
            actual = unit_text(trans_units[best_idx])
            if actual and actual != expected:
                inconsistencies.append({
                    "original": orig_text,
                    "expected": expected,
                    "actual": actual,
                    "bbox": ou["bbox"],
                })

    return inconsistencies


# ---------------------------------------------------------------------------
# Step C: Correction
# ---------------------------------------------------------------------------

def format_mandatory_glossary_prompt(inconsistencies: list[dict]) -> str:
    """Build a MANDATORY TRANSLATIONS prompt section from inconsistencies."""
    lines = [
        "\n\nMANDATORY TRANSLATIONS (override everything else — you MUST use these exact translations):"
    ]
    seen: set[str] = set()
    for inc in inconsistencies:
        key = inc["original"]
        if key in seen:
            continue
        seen.add(key)
        lines.append(f'- "{inc["original"]}" MUST be translated as "{inc["expected"]}"')
    return "\n".join(lines)


def pixel_transplant(
    inconsistent_img: np.ndarray,
    reference_img: np.ndarray,
    inconsistencies: list[dict],
    trans_ocr_inconsistent: dict,
    trans_ocr_reference: dict,
    min_overlap: float = 0.3,
    padding: int = 5,
) -> np.ndarray:
    """Copy text regions from reference translated slide to inconsistent slide."""
    result = inconsistent_img.copy()
    ref_units = text_units_from_ocr(trans_ocr_reference)
    inc_units = text_units_from_ocr(trans_ocr_inconsistent)
    h, w = result.shape[:2]

    for inc in inconsistencies:
        orig_bbox = inc["bbox"]
        # Find the corresponding region on the inconsistent translated slide
        inc_bbox = None
        for iu in inc_units:
            if bbox_overlap_ratio(orig_bbox, iu["bbox"]) >= min_overlap:
                inc_bbox = iu["bbox"]
                break
        # Find the corresponding region on the reference translated slide
        ref_bbox = None
        for ru in ref_units:
            if bbox_overlap_ratio(orig_bbox, ru["bbox"]) >= min_overlap:
                ref_bbox = ru["bbox"]
                break

        if inc_bbox is None or ref_bbox is None:
            continue

        # Copy from reference to result
        ry1 = max(0, ref_bbox["y"] - padding)
        ry2 = min(h, ref_bbox["y"] + ref_bbox["h"] + padding)
        rx1 = max(0, ref_bbox["x"] - padding)
        rx2 = min(w, ref_bbox["x"] + ref_bbox["w"] + padding)

        dy1 = max(0, inc_bbox["y"] - padding)
        dy2 = min(h, inc_bbox["y"] + inc_bbox["h"] + padding)
        dx1 = max(0, inc_bbox["x"] - padding)
        dx2 = min(w, inc_bbox["x"] + inc_bbox["w"] + padding)

        src_region = reference_img[ry1:ry2, rx1:rx2]
        # Resize if bboxes differ slightly
        target_h = dy2 - dy1
        target_w = dx2 - dx1
        if src_region.shape[0] != target_h or src_region.shape[1] != target_w:
            src_region = cv2.resize(src_region, (target_w, target_h), interpolation=cv2.INTER_AREA)
        result[dy1:dy2, dx1:dx2] = src_region

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    load_local_env(LOCAL_ENV_PATH)

    original_dir = Path(args.original_dir).resolve()
    translated_dir = Path(args.translated_dir).resolve()
    report_path = Path(args.report_json).resolve() if args.report_json else translated_dir / "consistency_report.json"

    if not original_dir.exists():
        print(f"[Review] Original dir not found: {original_dir}", flush=True)
        return 1
    if not translated_dir.exists():
        print(f"[Review] Translated dir not found: {translated_dir}", flush=True)
        return 1

    # Setup Vision OCR
    print(f"[Review] Setting up Vision OCR (project: {args.vision_project_id}) ...", flush=True)
    vision_client, vision_module, _vp, _dp = ensure_cloud_vision_client(args.vision_project_id)

    # Setup Gemini client for re-translation
    client, types, project_id_used, _default_project, location_used = ensure_cloud_gemini_image_client(
        project_id=args.project_id, location=args.location,
    )
    print(f"[Review] Gemini backend: {project_id_used} / {location_used}", flush=True)

    # Load base prompt
    target_language = str(args.target_language).strip()
    termbase_entries = load_termbase_entries(Path(args.termbase_file).resolve(), target_language)
    base_prompt = append_glossary_to_prompt(
        load_prompt(Path(args.prompt_file).resolve(), target_language), termbase_entries,
    )

    # Collect slide paths
    orig_slides = sorted(p for p in original_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png")
    trans_slides = sorted(p for p in translated_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png")
    trans_by_name = {p.name: p for p in trans_slides}

    # Filter to slides that exist in both dirs
    slide_names = [p.name for p in orig_slides if p.name in trans_by_name]
    if not slide_names:
        print("[Review] No matching slides found between original and translated dirs.", flush=True)
        _write_empty_report(report_path)
        return 0

    # Step A: OCR all original slides and detect sequences
    print(f"[Review] OCR scanning {len(slide_names)} original slides ...", flush=True)
    orig_ocr_cache = ocr_all_slides(
        [original_dir / n for n in slide_names],
        vision_client, vision_module, args.vision_feature,
    )
    print(f"[Review] OCR completed for {len(orig_ocr_cache)}/{len(slide_names)} slides.", flush=True)

    sequences = detect_sequences(slide_names, orig_ocr_cache)
    print(f"[Review] Detected {len(sequences)} slide sequences:", flush=True)
    for seq in sequences:
        print(f"  [{len(seq)} slides] {seq[0]} ... {seq[-1]}", flush=True)

    if not sequences:
        print("[Review] No sequences found — nothing to review.", flush=True)
        _write_empty_report(report_path)
        return 0

    # Step B + C: For each sequence, check consistency and fix
    total_fixes = 0
    total_unfixable = 0
    report_sequences: list[dict] = []

    for seq in sequences:
        reference_name = seq[-1]  # Last = most complete slide
        print(f"@@STEP DETAIL translate-review {reference_name} (ref for {len(seq)} slides)")

        # OCR translated slides in this sequence
        trans_ocr_cache: dict[str, dict] = {}
        for name in seq:
            trans_path = trans_by_name.get(name)
            if trans_path is None:
                continue
            event_id = parse_event_id_from_name(Path(name).stem)
            if event_id is None:
                continue
            try:
                trans_ocr_cache[name] = ocr_slide_fragments(
                    vision_client, vision_module,
                    image_path=trans_path, event_id=event_id, slide_index=0,
                    feature=args.vision_feature,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[Review] OCR failed for translated {name}: {exc}", flush=True)

        if reference_name not in orig_ocr_cache or reference_name not in trans_ocr_cache:
            print(f"[Review] Skipping sequence — reference OCR missing for {reference_name}.", flush=True)
            continue

        # Build canonical glossary from reference pair
        canonical = build_canonical_glossary(orig_ocr_cache[reference_name], trans_ocr_cache[reference_name])
        if not canonical:
            print(f"[Review] No glossary entries from reference {reference_name} — skipping sequence.", flush=True)
            continue
        print(f"[Review] Canonical glossary ({len(canonical)} entries): {list(canonical.items())[:5]}...", flush=True)

        seq_fixes: list[dict] = []

        # Check earlier slides (all except reference)
        for name in seq[:-1]:
            if name not in orig_ocr_cache or name not in trans_ocr_cache:
                continue

            inconsistencies = check_consistency(
                name, orig_ocr_cache[name], trans_ocr_cache[name], canonical,
            )
            if not inconsistencies:
                print(f"[Review] {name}: consistent", flush=True)
                continue

            print(f"[Review] {name}: {len(inconsistencies)} inconsistencies found:", flush=True)
            for inc in inconsistencies:
                print(f"  '{inc['original']}': expected '{inc['expected']}', got '{inc['actual']}'", flush=True)

            # Strategy 1: Re-translation with mandatory glossary
            fixed = False
            method = "unfixable"
            trans_path = trans_by_name[name]
            orig_path = original_dir / name
            original_img = cv2.imread(str(orig_path), cv2.IMREAD_COLOR)

            if original_img is not None:
                glossary_prompt = base_prompt + format_mandatory_glossary_prompt(inconsistencies)
                for attempt in range(args.max_retries):
                    print(f"[Review] Re-translating {name} (attempt {attempt + 1}/{args.max_retries}) ...", flush=True)
                    try:
                        retranslated = generate_translated_image(
                            client, types, str(args.model), glossary_prompt, original_img,
                        )
                    except Exception as exc:  # noqa: BLE001
                        print(f"[Review] Re-translation failed: {exc}", flush=True)
                        continue

                    # Verify: OCR the retranslated image and check again
                    # Save temporarily to allow OCR
                    tmp_path = trans_path.with_suffix(".review_tmp.png")
                    cv2.imwrite(str(tmp_path), retranslated)
                    event_id = parse_event_id_from_name(Path(name).stem)
                    try:
                        new_trans_ocr = ocr_slide_fragments(
                            vision_client, vision_module,
                            image_path=tmp_path, event_id=event_id or 0, slide_index=0,
                            feature=args.vision_feature,
                        )
                        remaining = check_consistency(name, orig_ocr_cache[name], new_trans_ocr, canonical)
                    except Exception as exc:  # noqa: BLE001
                        print(f"[Review] Verification OCR failed: {exc}", flush=True)
                        tmp_path.unlink(missing_ok=True)
                        continue

                    tmp_path.unlink(missing_ok=True)

                    if not remaining:
                        # Success — overwrite the translated slide
                        cv2.imwrite(str(trans_path), retranslated)
                        print(f"[Review] {name}: fixed via re-translation (attempt {attempt + 1}).", flush=True)
                        fixed = True
                        method = "re-translation"
                        break
                    else:
                        print(f"[Review] Re-translation attempt {attempt + 1}: still {len(remaining)} inconsistencies.", flush=True)

            # Strategy 2: Pixel transplant fallback
            if not fixed:
                print(f"[Review] Attempting pixel transplant for {name} ...", flush=True)
                trans_img = cv2.imread(str(trans_path), cv2.IMREAD_COLOR)
                ref_trans_path = trans_by_name.get(reference_name)
                ref_trans_img = cv2.imread(str(ref_trans_path), cv2.IMREAD_COLOR) if ref_trans_path else None

                if trans_img is not None and ref_trans_img is not None:
                    transplanted = pixel_transplant(
                        trans_img, ref_trans_img, inconsistencies,
                        trans_ocr_cache[name], trans_ocr_cache[reference_name],
                    )
                    cv2.imwrite(str(trans_path), transplanted)
                    print(f"[Review] {name}: fixed via pixel transplant.", flush=True)
                    fixed = True
                    method = "pixel-transplant"
                else:
                    print(f"[Review] {name}: pixel transplant failed (images unreadable).", flush=True)

            if fixed:
                total_fixes += 1
            else:
                total_unfixable += 1

            seq_fixes.append({
                "slide": name,
                "terms": [
                    {"original": i["original"], "expected": i["expected"], "was": i["actual"]}
                    for i in inconsistencies
                ],
                "method": method,
            })

        report_sequences.append({
            "slides": seq,
            "reference": reference_name,
            "canonical_glossary": canonical,
            "fixes": seq_fixes,
        })

    # Step D: Write report
    report = {
        "sequences": report_sequences,
        "total_sequences": len(sequences),
        "total_fixes": total_fixes,
        "total_unfixable": total_unfixable,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[Review] Report saved: {report_path}", flush=True)

    print(f"[Review] Sequences: {len(sequences)}", flush=True)
    print(f"[Review] Fixes applied: {total_fixes}", flush=True)
    print(f"[Review] Unfixable: {total_unfixable}", flush=True)
    return 0


def _write_empty_report(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"sequences": [], "total_sequences": 0, "total_fixes": 0, "total_unfixable": 0}, f, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
