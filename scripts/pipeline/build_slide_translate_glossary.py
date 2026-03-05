#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]

import sys

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.lib.cloud_translate import ensure_cloud_translate_client, resolve_target_language_codes, translate_texts_llm
from scripts.lib.slide_glossary import (
    build_exact_termbase_lookup,
    chunked,
    event_metadata_by_id,
    is_translatable_text,
    load_slide_events,
    parse_event_id_from_name,
    write_csv,
    write_json,
)
from scripts.lib.slide_ocr import ensure_cloud_vision_client, ocr_slide_fragments
from scripts.lib.slide_style_classifier import classify_text_units
from scripts.lib.translation_memory import DEFAULT_TERMBASE_PATH, load_termbase_entries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a frozen deck glossary for deterministic slide translation.")
    parser.add_argument("--input-dir", required=True, help="Directory with final slide images.")
    parser.add_argument("--slide-map-json", required=True, help="slide_text_map_final.json path.")
    parser.add_argument("--out-dir", required=True, help="Output directory for slide translation artifacts.")
    parser.add_argument("--target-language", required=True, help="Target language label, e.g. German (Germany).")
    parser.add_argument("--termbase-file", default=str(DEFAULT_TERMBASE_PATH), help="Global translation termbase CSV.")
    parser.add_argument("--vision-project-id", required=True, help="Google Cloud Vision quota project.")
    parser.add_argument("--vision-feature", default="DOCUMENT_TEXT_DETECTION", help="Google Vision feature.")
    parser.add_argument("--translate-project-id", required=True, help="Google Cloud Translation quota project.")
    parser.add_argument("--translate-location", default="us-central1", help="Google Cloud Translation location.")
    parser.add_argument("--translate-model", default="general/translation-llm", help="Google Cloud Translation model.")
    parser.add_argument("--source-language-code", default="", help="Optional source language code.")
    parser.add_argument("--translate-batch-size", type=int, default=32, help="Batch size for glossary translation.")
    return parser.parse_args()


def ocr_fragment_rows(ocr_docs: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for doc in ocr_docs:
        for fragment in doc.get("fragments", []):
            rows.append(
                {
                    "slide_index": fragment.get("slide_index", ""),
                    "event_id": fragment.get("event_id", ""),
                    "fragment_id": fragment.get("fragment_id", ""),
                    "block_id": fragment.get("block_id", ""),
                    "line_id": fragment.get("line_id", ""),
                    "text_raw": fragment.get("text_raw", ""),
                    "text_norm": fragment.get("text_norm", ""),
                    "confidence": fragment.get("confidence", ""),
                    "bbox_x": fragment.get("bbox", {}).get("x", ""),
                    "bbox_y": fragment.get("bbox", {}).get("y", ""),
                    "bbox_w": fragment.get("bbox", {}).get("w", ""),
                    "bbox_h": fragment.get("bbox", {}).get("h", ""),
                    "image_name": doc.get("image_name", ""),
                }
            )
    return rows


def ocr_unit_rows(ocr_docs: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for doc in ocr_docs:
        for unit in doc.get("text_units", []):
            rows.append(
                {
                    "slide_index": unit.get("slide_index", ""),
                    "event_id": unit.get("event_id", ""),
                    "unit_id": unit.get("unit_id", ""),
                    "fragment_ids": unit.get("fragment_ids", []),
                    "block_ids": unit.get("block_ids", []),
                    "line_ids": unit.get("line_ids", []),
                    "line_count": unit.get("line_count", ""),
                    "list_marker_fragment_id": unit.get("list_marker_fragment_id", ""),
                    "list_marker_inferred": unit.get("list_marker_inferred", ""),
                    "list_marker_text": unit.get("list_marker_text", ""),
                    "source_text": unit.get("source_text", ""),
                    "source_text_norm": unit.get("source_text_norm", ""),
                    "classification_role": unit.get("classification_role", ""),
                    "classification_reason": unit.get("classification_reason", ""),
                    "graphic_embedded_candidate": unit.get("graphic_embedded_candidate", ""),
                    "graphic_context_score": unit.get("graphic_context_score", ""),
                    "bbox_x": unit.get("bbox", {}).get("x", ""),
                    "bbox_y": unit.get("bbox", {}).get("y", ""),
                    "bbox_w": unit.get("bbox", {}).get("w", ""),
                    "bbox_h": unit.get("bbox", {}).get("h", ""),
                    "image_name": doc.get("image_name", ""),
                }
            )
    return rows


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    slide_map_json = Path(args.slide_map_json).resolve()
    out_dir = Path(args.out_dir).resolve()
    termbase_file = Path(args.termbase_file).resolve()
    if not input_dir.exists():
        raise FileNotFoundError(input_dir)
    if not slide_map_json.exists():
        raise FileNotFoundError(slide_map_json)

    slide_events = load_slide_events(slide_map_json)
    events_by_id = event_metadata_by_id(slide_events)
    slide_paths = sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png")
    target_language = str(args.target_language or "").strip()
    if not target_language:
        raise RuntimeError("--target-language must not be empty.")

    vision_client, vision, vision_project_id_used, _default_project = ensure_cloud_vision_client(args.vision_project_id)
    translate_client, _translate_v3, translate_project_id_used, _default_project, translate_location = ensure_cloud_translate_client(
        args.translate_project_id,
        args.translate_location,
    )
    target_language_code, _tts_language_code = resolve_target_language_codes(target_language)
    termbase_entries = load_termbase_entries(termbase_file, target_language)
    termbase_lookup = build_exact_termbase_lookup(termbase_entries)

    ocr_docs: list[dict] = []
    candidate_by_norm: dict[str, dict] = {}
    skipped_graphic_units = 0
    for fallback_index, slide_path in enumerate(slide_paths, start=1):
        event_id = parse_event_id_from_name(slide_path.name) or 0
        event_meta = events_by_id.get(event_id, {})
        slide_index = int(event_meta.get("slide_index", fallback_index) or fallback_index)
        ocr_doc = ocr_slide_fragments(
            vision_client,
            vision,
            image_path=slide_path,
            event_id=event_id,
            slide_index=slide_index,
            feature=args.vision_feature,
        )
        classifications = classify_text_units(
            ocr_doc.get("text_units", []),
            image_width=int(ocr_doc.get("image_width", 0) or 0),
            image_height=int(ocr_doc.get("image_height", 0) or 0),
        )
        classification_by_unit_id = {int(row.get("unit_id", 0) or 0): row for row in classifications}
        for unit in ocr_doc.get("text_units", []):
            unit_id = int(unit.get("unit_id", 0) or 0)
            classification = classification_by_unit_id.get(unit_id, {})
            unit["classification_role"] = str(classification.get("role", "body") or "body")
            unit["classification_reason"] = str(classification.get("classification_reason", "fallback_body") or "fallback_body")
        ocr_docs.append(ocr_doc)

        for unit in ocr_doc.get("text_units", []):
            if str(unit.get("classification_role", "body") or "body") == "graphic_embedded":
                skipped_graphic_units += 1
                continue
            text_norm = str(unit.get("source_text_norm", "") or "").strip()
            text_raw = str(unit.get("source_text", "") or "").strip()
            if not text_norm or not is_translatable_text(text_norm):
                continue
            candidate = candidate_by_norm.setdefault(
                text_norm,
                {
                    "source_text": text_raw or text_norm,
                    "source_text_norm": text_norm,
                    "occurrences": 0,
                    "slide_indices": [],
                    "event_ids": [],
                    "image_names": [],
                    "source_examples": [],
                    "line_counts": [],
                    "list_marker_occurrences": 0,
                },
            )
            candidate["occurrences"] += 1
            candidate["slide_indices"].append(int(unit.get("slide_index", 0) or 0))
            candidate["event_ids"].append(int(unit.get("event_id", 0) or 0))
            candidate["image_names"].append(str(ocr_doc.get("image_name", "") or ""))
            candidate["line_counts"].append(int(unit.get("line_count", 1) or 1))
            if int(unit.get("list_marker_fragment_id", 0) or 0) > 0 or bool(unit.get("list_marker_inferred", False)):
                candidate["list_marker_occurrences"] += 1
            if text_raw and text_raw not in candidate["source_examples"] and len(candidate["source_examples"]) < 5:
                candidate["source_examples"].append(text_raw)

    candidate_rows = []
    for text_norm, row in sorted(candidate_by_norm.items(), key=lambda item: item[0]):
        slide_indices = sorted({int(v) for v in row["slide_indices"] if int(v) > 0})
        event_ids = sorted({int(v) for v in row["event_ids"] if int(v) > 0})
        image_names = sorted({str(v) for v in row["image_names"] if str(v)})
        candidate_rows.append(
            {
                "source_text": row["source_text"],
                "source_text_norm": text_norm,
                "occurrences": int(row["occurrences"]),
                "slide_indices": slide_indices,
                "event_ids": event_ids,
                "image_names": image_names,
                "source_examples": row["source_examples"],
                "max_line_count": max([int(v) for v in row["line_counts"]], default=1),
                "list_marker_occurrences": int(row["list_marker_occurrences"]),
            }
        )

    glossary_rows: list[dict] = []
    pending_rows: list[dict] = []
    for row in candidate_rows:
        termbase_target = termbase_lookup.get(row["source_text_norm"])
        if termbase_target:
            glossary_rows.append(
                {
                    **row,
                    "target_text": termbase_target,
                    "target_language": target_language,
                    "target_language_code": target_language_code,
                    "origin": "termbase",
                    "status": "frozen",
                }
            )
        else:
            pending_rows.append(row)

    pending_without_target = [row for row in pending_rows if "target_text" not in row]
    for row_batch in chunked(pending_without_target, args.translate_batch_size):
        batch = [row["source_text"] for row in row_batch]
        translated_batch = translate_texts_llm(
            translate_client,
            project_id=translate_project_id_used,
            location=translate_location,
            model=args.translate_model,
            contents=batch,
            target_language_code=target_language_code,
            source_language_code=args.source_language_code,
        )
        for row, translated_text in zip(row_batch, translated_batch, strict=True):
            row["target_text"] = translated_text
            row["target_language"] = target_language
            row["target_language_code"] = target_language_code
            row["origin"] = "llm"
            row["status"] = "frozen"
            glossary_rows.append(row)

    glossary_rows.sort(key=lambda row: str(row.get("source_text_norm", "")))

    out_dir.mkdir(parents=True, exist_ok=True)
    ocr_json_path = out_dir / "ocr_pass1.json"
    ocr_csv_path = out_dir / "ocr_pass1.csv"
    ocr_units_csv_path = out_dir / "ocr_units_pass1.csv"
    candidate_json_path = out_dir / "glossary_candidates.json"
    candidate_csv_path = out_dir / "glossary_candidates.csv"
    glossary_json_path = out_dir / "glossary.json"
    glossary_csv_path = out_dir / "glossary.csv"

    write_json(
        ocr_json_path,
        {
            "slides_processed": len(ocr_docs),
            "ocr_provider": "google_vision_document_text_detection",
            "vision_project_id_used": vision_project_id_used,
            "vision_feature": args.vision_feature,
            "slides": ocr_docs,
        },
    )
    write_csv(
        ocr_csv_path,
        [
            "slide_index",
            "event_id",
            "fragment_id",
            "block_id",
            "line_id",
            "text_raw",
            "text_norm",
            "confidence",
            "bbox_x",
            "bbox_y",
            "bbox_w",
            "bbox_h",
            "image_name",
        ],
        ocr_fragment_rows(ocr_docs),
    )
    write_csv(
        ocr_units_csv_path,
        [
            "slide_index",
            "event_id",
            "unit_id",
            "fragment_ids",
            "block_ids",
            "line_ids",
            "line_count",
            "list_marker_fragment_id",
            "list_marker_inferred",
            "list_marker_text",
            "source_text",
            "source_text_norm",
            "classification_role",
            "classification_reason",
            "graphic_embedded_candidate",
            "graphic_context_score",
            "bbox_x",
            "bbox_y",
            "bbox_w",
            "bbox_h",
            "image_name",
        ],
        ocr_unit_rows(ocr_docs),
    )
    write_json(
        candidate_json_path,
        {
            "target_language": target_language,
            "candidate_count": len(candidate_rows),
            "items": candidate_rows,
        },
    )
    write_csv(
        candidate_csv_path,
        [
            "source_text",
            "source_text_norm",
            "occurrences",
            "slide_indices",
            "event_ids",
            "image_names",
            "source_examples",
            "max_line_count",
            "list_marker_occurrences",
        ],
        candidate_rows,
    )
    write_json(
        glossary_json_path,
        {
            "target_language": target_language,
            "target_language_code": target_language_code,
            "source_language_code": str(args.source_language_code or "").strip(),
            "translate_model": str(args.translate_model or "").strip(),
            "translate_location": translate_location,
            "translate_project_id_used": translate_project_id_used,
            "normalization_version": ocr_docs[0].get("normalization_version", "") if ocr_docs else "",
            "entry_count": len(glossary_rows),
            "entries": glossary_rows,
        },
    )
    write_csv(
        glossary_csv_path,
        [
            "source_text",
            "source_text_norm",
            "target_text",
            "target_language",
            "target_language_code",
            "origin",
            "status",
            "occurrences",
            "slide_indices",
            "event_ids",
            "image_names",
            "source_examples",
            "max_line_count",
            "list_marker_occurrences",
        ],
        glossary_rows,
    )

    print(f"[SlideTranslate] OCR slides processed: {len(ocr_docs)}")
    print(f"[SlideTranslate] Glossary candidates: {len(candidate_rows)}")
    print(f"[SlideTranslate] Graphic-embedded units skipped: {skipped_graphic_units}")
    print(f"[SlideTranslate] Frozen glossary entries: {len(glossary_rows)}")
    print(f"[SlideTranslate] Target language: {target_language} ({target_language_code})")
    print(f"[SlideTranslate] Vision project: {vision_project_id_used}")
    print(f"[SlideTranslate] Translate project: {translate_project_id_used}")
    print(f"[SlideTranslate] Output dir: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
