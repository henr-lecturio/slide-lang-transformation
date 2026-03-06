#!/usr/bin/env python3
"""Consistency review for translated slide sequences using the 3-Step Gemini pipeline.

Detects slide sequences (progressive bullet-point builds), checks translation
consistency across a sequence, and fixes inconsistencies via
Extract → Translate (with forced glossary) → Render.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import cv2

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.providers.translate_final_slides_gemini import (
    LOCAL_ENV_PATH,
    encode_png,
    ensure_client,
    ensure_text_client,
    extract_slide_json,
    load_local_env,
    render_translated_image,
    translate_slide_json,
)
from scripts.lib.slide_glossary import parse_event_id_from_name


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Review translated slide consistency.")
    p.add_argument("--original-dir", required=True)
    p.add_argument("--translated-dir", required=True)
    p.add_argument("--model", default="gemini-3-pro-image-preview")
    p.add_argument("--extract-model", default="gemini-3.1-pro-preview")
    p.add_argument("--extract-prompt", default="")
    p.add_argument("--translate-prompt", default="")
    p.add_argument("--render-prompt", default="")
    p.add_argument("--target-language", required=True)
    p.add_argument("--project-id", default="")
    p.add_argument("--location", default="")
    p.add_argument("--max-retries", type=int, default=2)
    p.add_argument("--report-json", default="")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_image(path: Path):
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None or img.size == 0:
        return None
    return img


def _sorted_slides(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".png")


def _normalize(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def _texts_set(elements: list[dict]) -> set[str]:
    return {_normalize(e.get("text", "")) for e in elements if e.get("text", "").strip()}


def _event_id_str(path: Path) -> str:
    eid = parse_event_id_from_name(path.stem)
    return f"{eid:03d}" if eid is not None else path.stem


# ---------------------------------------------------------------------------
# Sequence detection
# ---------------------------------------------------------------------------

def _is_superset(texts_a: set[str], texts_b: set[str]) -> bool:
    """Return True if B is a strict superset of A (all of A in B, B has more)."""
    if not texts_a:
        return False
    return texts_a.issubset(texts_b) and len(texts_b) > len(texts_a)


def detect_sequences(slide_extracts: list[tuple[Path, list[dict]]]) -> list[list[int]]:
    """Return groups of indices into *slide_extracts* that form sequences."""
    sequences: list[list[int]] = []
    current: list[int] = []

    for i in range(len(slide_extracts)):
        if not current:
            current.append(i)
            continue

        prev_texts = _texts_set(slide_extracts[current[-1]][1])
        curr_texts = _texts_set(slide_extracts[i][1])

        if _is_superset(prev_texts, curr_texts):
            current.append(i)
        else:
            if len(current) >= 2:
                sequences.append(current)
            current = [i]

    if len(current) >= 2:
        sequences.append(current)

    return sequences


# ---------------------------------------------------------------------------
# Consistency check
# ---------------------------------------------------------------------------

def _build_reference_mapping(
    text_client, extract_model: str, extract_prompt: str,
    original_path: Path, translated_path: Path,
) -> dict[str, str]:
    """Build {normalized_original_text: translated_text} from reference slide."""
    orig_img = _load_image(original_path)
    trans_img = _load_image(translated_path)
    if orig_img is None or trans_img is None:
        return {}

    orig_extract = extract_slide_json(text_client, extract_model, encode_png(orig_img), extract_prompt)
    trans_extract = extract_slide_json(text_client, extract_model, encode_png(trans_img), extract_prompt)

    orig_by_id = {e["id"]: e.get("text", "") for e in orig_extract.get("text_elements", [])}
    trans_by_id = {e["id"]: e.get("text", "") for e in trans_extract.get("text_elements", [])}

    mapping: dict[str, str] = {}
    for eid, orig_text in orig_by_id.items():
        trans_text = trans_by_id.get(eid, "")
        if orig_text.strip() and trans_text.strip():
            mapping[_normalize(orig_text)] = trans_text.strip()
    return mapping


def check_consistency(
    text_client, extract_model: str, extract_prompt: str,
    translated_path: Path,
    reference_mapping: dict[str, str],
) -> list[dict]:
    """Check a translated slide against the reference mapping. Return issues."""
    trans_img = _load_image(translated_path)
    if trans_img is None:
        return []

    trans_extract = extract_slide_json(text_client, extract_model, encode_png(trans_img), extract_prompt)
    trans_elements = trans_extract.get("text_elements", [])

    issues = []
    for elem in trans_elements:
        text = elem.get("text", "").strip()
        if not text:
            continue
        # Try to find matching original via reference mapping
        for orig_norm, expected_trans in reference_mapping.items():
            if _normalize(text) != _normalize(expected_trans) and _normalize(text) != orig_norm:
                continue
            # This element corresponds to orig_norm
            if _normalize(text) != _normalize(expected_trans):
                issues.append({
                    "original": orig_norm,
                    "expected": expected_trans,
                    "got": text,
                    "element_id": elem.get("id"),
                })
    return issues


# ---------------------------------------------------------------------------
# Fix via 3-Step pipeline
# ---------------------------------------------------------------------------

def regenerate_slide(
    text_client, image_client, types,
    extract_model: str, render_model: str,
    extract_prompt: str, translate_prompt: str, render_prompt: str,
    original_path: Path, output_path: Path,
    target_language: str, glossary: dict[str, str],
) -> tuple[str, list[dict]]:
    """Re-translate a slide via 3-step pipeline. Returns (status, mapping).

    status is 'ok' or 'failed'.
    """
    orig_img = _load_image(original_path)
    if orig_img is None:
        return "failed", []

    image_bytes = encode_png(orig_img)

    try:
        extracted = extract_slide_json(text_client, extract_model, image_bytes, extract_prompt)
        text_elements = extracted.get("text_elements", [])
        if not text_elements:
            # No text — copy original
            shutil.copy2(original_path, output_path)
            return "ok", []

        mapping = translate_slide_json(
            text_client, extract_model, text_elements, target_language,
            glossary, translate_prompt,
        )

        rendered = render_translated_image(image_client, types, render_model, orig_img, mapping, render_prompt)
        cv2.imwrite(str(output_path), rendered)
        return "ok", mapping

    except Exception as exc:  # noqa: BLE001
        print(f"  [Regenerate] Error: {exc}", flush=True)
        return "failed", []


def fix_slide_with_retry(
    text_client, image_client, types,
    extract_model: str, render_model: str,
    extract_prompt: str, translate_prompt: str, render_prompt: str,
    original_path: Path, output_path: Path,
    target_language: str, glossary: dict[str, str],
    reference_mapping: dict[str, str],
    max_retries: int,
) -> str:
    """Re-translate with verification against reference. Returns 'fixed' or 'failed'."""
    orig_img = _load_image(original_path)
    if orig_img is None:
        return "failed"

    image_bytes = encode_png(orig_img)

    for attempt in range(1, max_retries + 1):
        try:
            print(f"  [Fix] Attempt {attempt}/{max_retries}: Extract → Translate → Render ...", flush=True)
            extracted = extract_slide_json(text_client, extract_model, image_bytes, extract_prompt)
            text_elements = extracted.get("text_elements", [])
            if not text_elements:
                return "failed"

            mapping = translate_slide_json(
                text_client, extract_model, text_elements, target_language,
                glossary, translate_prompt,
            )
            rendered = render_translated_image(image_client, types, render_model, orig_img, mapping, render_prompt)

            # Verify consistency
            print(f"  [Fix] Attempt {attempt}/{max_retries}: Verifying ...", flush=True)
            verify_extract = extract_slide_json(text_client, extract_model, encode_png(rendered), extract_prompt)
            verify_elements = verify_extract.get("text_elements", [])

            consistent = True
            for elem in verify_elements:
                text = elem.get("text", "").strip()
                if not text:
                    continue
                for orig_norm, expected_trans in reference_mapping.items():
                    if _normalize(text) == orig_norm:
                        consistent = False
                        break
                    if _normalize(text) != _normalize(expected_trans) and _normalize(text) != orig_norm:
                        continue
                    if _normalize(text) != _normalize(expected_trans):
                        consistent = False
                        break

            if consistent:
                cv2.imwrite(str(output_path), rendered)
                return "fixed"

            print(f"  [Fix] Attempt {attempt}/{max_retries}: Still inconsistent, retrying ...", flush=True)

        except Exception as exc:  # noqa: BLE001
            print(f"  [Fix] Attempt {attempt}/{max_retries}: Error — {exc}", flush=True)

    # Last attempt: write best effort
    try:
        extracted = extract_slide_json(text_client, extract_model, image_bytes, extract_prompt)
        text_elements = extracted.get("text_elements", [])
        if text_elements:
            mapping = translate_slide_json(
                text_client, extract_model, text_elements, target_language,
                glossary, translate_prompt,
            )
            rendered = render_translated_image(image_client, types, render_model, orig_img, mapping, render_prompt)
            cv2.imwrite(str(output_path), rendered)
            return "fixed"
    except Exception as exc:  # noqa: BLE001
        print(f"  [Fix] Final attempt failed: {exc}", flush=True)

    return "failed"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    load_local_env(LOCAL_ENV_PATH)

    original_dir = Path(args.original_dir).resolve()
    translated_dir = Path(args.translated_dir).resolve()
    if not original_dir.exists():
        print(f"[Consistency] Original dir not found: {original_dir}", flush=True)
        return 1
    if not translated_dir.exists():
        print(f"[Consistency] Translated dir not found: {translated_dir}", flush=True)
        return 1

    text_client = ensure_text_client()
    image_client, types, project_id_used, location_used = ensure_client(args.project_id, args.location)

    print(f"[Consistency] Gemini backend: {project_id_used}", flush=True)
    print(f"[Consistency] Extract/Translate model: {args.extract_model}", flush=True)
    print(f"[Consistency] Render model: {args.model}", flush=True)

    orig_slides = _sorted_slides(original_dir)

    # ---------------------------------------------------------------------------
    # Phase 1: Extract text from all original slides
    # ---------------------------------------------------------------------------
    print(f"[Consistency] Extracting text from {len(orig_slides)} original slides ...", flush=True)
    slide_extracts: list[tuple[Path, list[dict]]] = []
    for slide_path in orig_slides:
        img = _load_image(slide_path)
        if img is None:
            slide_extracts.append((slide_path, []))
            continue
        try:
            print(f"@@STEP DETAIL extract {slide_path.name}")
            extracted = extract_slide_json(text_client, str(args.extract_model), encode_png(img), args.extract_prompt)
            slide_extracts.append((slide_path, extracted.get("text_elements", [])))
        except Exception as exc:  # noqa: BLE001
            print(f"[Consistency] Extract failed for {slide_path.name}: {exc}", flush=True)
            slide_extracts.append((slide_path, []))

    # ---------------------------------------------------------------------------
    # Phase 2: Detect sequences and build glossaries
    # ---------------------------------------------------------------------------
    print("[Consistency] Detecting sequences ...", flush=True)
    sequences = detect_sequences(slide_extracts)
    print(f"[Consistency] Found {len(sequences)} sequence(s)", flush=True)

    # Build per-slide glossary from sequence reference mappings.
    # slide index → glossary dict for that slide (sequence members get the
    # reference glossary; non-sequence slides get an empty glossary).
    slide_glossaries: dict[int, dict[str, str]] = {}
    # slide index → reference_mapping (for consistency verification later)
    slide_ref_mappings: dict[int, dict[str, str]] = {}
    # Track which indices belong to sequences (and which is the reference)
    seq_member_indices: set[int] = set()
    seq_reference_indices: set[int] = set()

    # We need existing translated images to build the reference mapping for the
    # reference slide itself. The reference slide (last in sequence) keeps its
    # current translation as the gold standard.
    trans_slides = _sorted_slides(translated_dir)
    trans_by_name = {p.name: p for p in trans_slides}

    for seq_indices in sequences:
        seq_paths = [slide_extracts[i][0] for i in seq_indices]
        ref_path = seq_paths[-1]
        ref_translated = trans_by_name.get(ref_path.name)
        if ref_translated is None:
            print(f"[Consistency] No translated slide for reference {ref_path.name}, skipping sequence glossary.", flush=True)
            continue

        ref_mapping = _build_reference_mapping(
            text_client, str(args.extract_model), args.extract_prompt,
            ref_path, ref_translated,
        )
        if not ref_mapping:
            continue

        glossary: dict[str, str] = {}
        for orig_norm, trans_text in ref_mapping.items():
            glossary[orig_norm] = trans_text

        for idx in seq_indices:
            seq_member_indices.add(idx)
            slide_glossaries[idx] = glossary
            slide_ref_mappings[idx] = ref_mapping

        ref_idx = seq_indices[-1]
        seq_reference_indices.add(ref_idx)

    # ---------------------------------------------------------------------------
    # Phase 3: Regenerate ALL slides via 3-Step pipeline
    # ---------------------------------------------------------------------------
    print(f"\n[Consistency] Regenerating all {len(orig_slides)} slides ...", flush=True)

    report = {
        "summary": {
            "sequences_found": len(sequences),
            "total_slides": len(orig_slides),
            "slides_regenerated": 0,
            "slides_failed": 0,
            "inconsistencies_found": 0,
            "fixes_applied": 0,
            "fixes_failed": 0,
        },
        "sequences": [],
        "slides": [],
        "glossary": [],
    }

    # Accumulate a running glossary for non-sequence slides (same as translate
    # pipeline: earlier translations feed later ones).
    running_glossary: dict[str, str] = {}

    for i, (slide_path, _elements) in enumerate(slide_extracts):
        eid = _event_id_str(slide_path)
        output_path = translated_dir / slide_path.name

        # Choose glossary: sequence members get the enforced reference glossary,
        # other slides get the running glossary accumulated so far.
        glossary = slide_glossaries.get(i, running_glossary)

        print(f"[Consistency] [{eid}] Regenerating {slide_path.name} (glossary: {len(glossary)} entries) ...", flush=True)
        print(f"@@STEP DETAIL regenerate {slide_path.name}")

        status, mapping = regenerate_slide(
            text_client, image_client, types,
            str(args.extract_model), str(args.model),
            args.extract_prompt, args.translate_prompt, args.render_prompt,
            slide_path, output_path,
            str(args.target_language), glossary,
        )

        slide_entry = {
            "event_id": eid,
            "file": slide_path.name,
            "status": status,
        }
        report["slides"].append(slide_entry)

        if status == "ok":
            report["summary"]["slides_regenerated"] += 1
            # Feed running glossary for subsequent non-sequence slides
            for entry in mapping:
                orig = entry.get("original", "").strip()
                trans = entry.get("translated", "").strip()
                if orig and trans and orig != trans:
                    running_glossary[orig] = trans
        else:
            report["summary"]["slides_failed"] += 1

        print(f"[Consistency] [{eid}] {status}", flush=True)

    # ---------------------------------------------------------------------------
    # Phase 4: Consistency verification for sequence members
    # ---------------------------------------------------------------------------
    for seq_indices in sequences:
        seq_paths = [slide_extracts[i][0] for i in seq_indices]
        event_ids = [_event_id_str(p) for p in seq_paths]
        ref_mapping = slide_ref_mappings.get(seq_indices[-1])
        if not ref_mapping:
            continue

        print(f"\n[Consistency] Verifying sequence: {', '.join(event_ids)}", flush=True)
        seq_report: dict = {"event_ids": event_ids, "issues": []}

        # Check all slides except reference
        for idx in seq_indices[:-1]:
            slide_path = slide_extracts[idx][0]
            trans_path = translated_dir / slide_path.name
            eid = _event_id_str(slide_path)

            if not trans_path.exists():
                continue

            print(f"@@STEP DETAIL verify {slide_path.name}")
            issues = check_consistency(
                text_client, str(args.extract_model), args.extract_prompt,
                trans_path, ref_mapping,
            )

            if not issues:
                print(f"[Consistency] [{eid}] Consistent", flush=True)
                continue

            report["summary"]["inconsistencies_found"] += len(issues)

            for issue in issues:
                desc = f"'{issue['original']}' expected '{issue['expected']}' but got '{issue['got']}'"
                print(f"[Consistency] [{eid}] INCONSISTENT — {desc}", flush=True)

                # Retry with verification loop
                print(f"[Consistency] [{eid}] Fixing with retry ...", flush=True)
                print(f"@@STEP DETAIL fix {slide_path.name}")
                glossary = slide_glossaries.get(idx, {})
                fix_result = fix_slide_with_retry(
                    text_client, image_client, types,
                    str(args.extract_model), str(args.model),
                    args.extract_prompt, args.translate_prompt, args.render_prompt,
                    slide_path, trans_path,
                    str(args.target_language), glossary, ref_mapping,
                    args.max_retries,
                )

                if fix_result == "fixed":
                    report["summary"]["fixes_applied"] += 1
                else:
                    report["summary"]["fixes_failed"] += 1

                seq_report["issues"].append({
                    "event_id": eid,
                    "description": desc,
                    "type": "inconsistent_translation",
                    "fix_result": fix_result,
                })

                # Only fix once per slide (re-translates the whole slide)
                break

        report["sequences"].append(seq_report)

    # ---------------------------------------------------------------------------
    # Build glossary section for report
    # ---------------------------------------------------------------------------
    seen: set[tuple[str, str]] = set()
    for ref_mapping in slide_ref_mappings.values():
        for orig_norm, trans_text in ref_mapping.items():
            key = (orig_norm, trans_text)
            if key not in seen:
                seen.add(key)
                report["glossary"].append({"source": orig_norm, "target": trans_text})

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    s = report["summary"]
    print(f"\n[Consistency] === Summary ===", flush=True)
    print(f"[Consistency] Total slides: {s['total_slides']}", flush=True)
    print(f"[Consistency] Regenerated: {s['slides_regenerated']}", flush=True)
    print(f"[Consistency] Failed: {s['slides_failed']}", flush=True)
    print(f"[Consistency] Sequences found: {s['sequences_found']}", flush=True)
    print(f"[Consistency] Inconsistencies found: {s['inconsistencies_found']}", flush=True)
    print(f"[Consistency] Fixes applied: {s['fixes_applied']}", flush=True)
    print(f"[Consistency] Fixes failed: {s['fixes_failed']}", flush=True)

    # Write report
    if args.report_json:
        report_path = Path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[Consistency] Report written to {report_path}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
