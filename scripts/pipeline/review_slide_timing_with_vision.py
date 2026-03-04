#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.lib.cloud_vision import detect_image_text_bytes, ensure_cloud_vision_client
from scripts.pipeline.export_slide_video import (
    compute_slide_audio_window,
    find_image,
    load_alignment,
    project_source_time_to_tts,
    sorted_alignment_rows,
)

WORD_RE = re.compile(r"\w+", re.UNICODE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review translated slide timing against TTS word timings with Google Cloud Vision OCR.")
    parser.add_argument("--slide-map-json", required=True, help="Path to slide_text_map_final.json.")
    parser.add_argument("--image-dir", required=True, help="Directory containing translated slide images.")
    parser.add_argument("--tts-alignment-json", required=True, help="Path to TTS segment_alignment.json.")
    parser.add_argument("--project-id", required=True, help="Google Cloud project id for Vision quota/billing.")
    parser.add_argument("--feature", default="DOCUMENT_TEXT_DETECTION", help="Vision OCR feature.")
    parser.add_argument("--min-match-confidence", type=float, default=0.70, help="Minimum confidence to accept OCR-word matching.")
    parser.add_argument("--min-ocr-chars", type=int, default=8, help="Minimum OCR character count to trust OCR text.")
    parser.add_argument("--max-boundary-adjust-sec", type=float, default=2.5, help="Maximum allowed adjustment relative to projected timing.")
    parser.add_argument("--out-slide-ocr-json", required=True, help="Output slide OCR JSON.")
    parser.add_argument("--out-slide-ocr-csv", required=True, help="Output slide OCR CSV.")
    parser.add_argument("--out-slide-voice-alignment-json", required=True, help="Output slide voice alignment JSON.")
    parser.add_argument("--out-slide-voice-alignment-csv", required=True, help="Output slide voice alignment CSV.")
    parser.add_argument("--out-reviewed-timeline-json", required=True, help="Output reviewed timeline JSON.")
    parser.add_argument("--out-reviewed-timeline-csv", required=True, help="Output reviewed timeline CSV.")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_text(text: str) -> str:
    return " ".join(str(text or "").split())


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", clean_text(text)).lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)
    return WORD_RE.findall(normalized)


def token_overlap_ratio(query_tokens: list[str], span_tokens: list[str]) -> float:
    if not query_tokens or not span_tokens:
        return 0.0
    query_counts = Counter(query_tokens)
    span_counts = Counter(span_tokens)
    overlap = sum(min(query_counts[token], span_counts[token]) for token in query_counts)
    base = max(len(query_tokens), len(span_tokens), 1)
    return overlap / float(base)


def score_span(query_tokens: list[str], span_tokens: list[str]) -> float:
    if not query_tokens or not span_tokens:
        return 0.0
    query_text = " ".join(query_tokens)
    span_text = " ".join(span_tokens)
    seq = SequenceMatcher(None, query_text, span_text).ratio()
    overlap = token_overlap_ratio(query_tokens, span_tokens)
    score = 0.65 * seq + 0.35 * overlap
    if query_tokens[0] == span_tokens[0]:
        score += 0.03
    if query_tokens[-1] == span_tokens[-1]:
        score += 0.03
    return min(1.0, score)


def find_best_word_span(query_tokens: list[str], words: list[dict[str, Any]], start_index: int) -> dict[str, Any] | None:
    if not query_tokens or start_index >= len(words):
        return None

    min_len = max(1, int(round(len(query_tokens) * 0.55)))
    max_len = max(min_len, int(round(len(query_tokens) * 1.75)) + 4)
    best: dict[str, Any] | None = None

    for start in range(max(0, start_index), len(words)):
        remaining = len(words) - start
        if remaining < min_len:
            break
        upper = min(remaining, max_len)
        for length in range(min_len, upper + 1):
            end = start + length
            span_tokens = [str(word.get("normalized", "") or "").strip() for word in words[start:end]]
            span_tokens = [token for token in span_tokens if token]
            if not span_tokens:
                continue
            score = score_span(query_tokens, span_tokens)
            if best is None or score > float(best["confidence"]):
                best = {
                    "start_index": start,
                    "end_index": end,
                    "confidence": score,
                    "matched_text": " ".join(str(word.get("text", "") or "").strip() for word in words[start:end]).strip(),
                    "tts_start_sec": float(words[start].get("start_sec", 0.0) or 0.0),
                    "tts_end_sec": float(words[end - 1].get("end_sec", 0.0) or 0.0),
                }
    return best


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    slide_map_json = Path(args.slide_map_json).resolve()
    image_dir = Path(args.image_dir).resolve()
    tts_alignment_json = Path(args.tts_alignment_json).resolve()
    out_slide_ocr_json = Path(args.out_slide_ocr_json).resolve()
    out_slide_ocr_csv = Path(args.out_slide_ocr_csv).resolve()
    out_slide_voice_alignment_json = Path(args.out_slide_voice_alignment_json).resolve()
    out_slide_voice_alignment_csv = Path(args.out_slide_voice_alignment_csv).resolve()
    out_reviewed_timeline_json = Path(args.out_reviewed_timeline_json).resolve()
    out_reviewed_timeline_csv = Path(args.out_reviewed_timeline_csv).resolve()

    if not slide_map_json.exists():
        raise FileNotFoundError(slide_map_json)
    if not image_dir.exists():
        raise FileNotFoundError(image_dir)
    if not tts_alignment_json.exists():
        raise FileNotFoundError(tts_alignment_json)

    payload = load_json(slide_map_json)
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        raise RuntimeError("slide_text_map_final.json must contain an 'events' array.")

    alignment_by_segment, full_audio_path, word_boundaries = load_alignment(tts_alignment_json)
    if not alignment_by_segment:
        raise RuntimeError("TTS alignment JSON must contain aligned segment rows.")
    alignment_rows = sorted_alignment_rows(alignment_by_segment)
    full_audio_duration = max(word_boundaries) if word_boundaries else 0.0
    alignment_payload = load_json(tts_alignment_json)
    words = alignment_payload.get("words", []) if isinstance(alignment_payload, dict) else []
    if not isinstance(words, list):
        words = []

    client, vision, resolved_project, default_project = ensure_cloud_vision_client(args.project_id)

    out_slide_ocr_json.parent.mkdir(parents=True, exist_ok=True)
    out_slide_voice_alignment_json.parent.mkdir(parents=True, exist_ok=True)
    out_reviewed_timeline_json.parent.mkdir(parents=True, exist_ok=True)

    slide_ocr_rows: list[dict[str, Any]] = []
    slide_voice_rows: list[dict[str, Any]] = []
    reviewed_timeline_rows: list[dict[str, Any]] = []

    word_cursor = 0
    for slide_index, event in enumerate(events, start=1):
        event_id = int(event.get("event_id", 0) or 0)
        image_path = find_image(image_dir, slide_index, event_id)
        image_bytes = image_path.read_bytes()
        ocr_text = detect_image_text_bytes(client, vision, image_bytes, feature=args.feature)
        ocr_normalized = normalize_text(ocr_text)
        ocr_tokens = tokenize(ocr_text)
        translated_text = clean_text(event.get("translated_text", "") or "")
        fallback_text = translated_text or clean_text(event.get("text", "") or "")
        fallback_tokens = tokenize(fallback_text)
        query_tokens = ocr_tokens if len("".join(ocr_tokens)) >= int(args.min_ocr_chars) else fallback_tokens
        query_text = " ".join(query_tokens)

        projected_window = compute_slide_audio_window(event, alignment_by_segment)
        if projected_window is not None:
            projected_start, projected_end = projected_window
        else:
            projected_start = project_source_time_to_tts(float(event.get("slide_start", 0.0) or 0.0), alignment_rows, full_audio_duration, word_boundaries)
            projected_end = project_source_time_to_tts(float(event.get("slide_end", float(event.get("slide_start", 0.0) or 0.0)) or 0.0), alignment_rows, full_audio_duration, word_boundaries)
        if projected_start is None:
            projected_start = 0.0
        if projected_end is None:
            projected_end = projected_start
        if projected_end < projected_start:
            projected_end = projected_start

        slide_ocr_rows.append(
            {
                "slide_index": slide_index,
                "event_id": event_id,
                "image_name": image_path.name,
                "ocr_text": ocr_text,
                "ocr_normalized": ocr_normalized,
                "ocr_chars": len(ocr_normalized.replace(" ", "")),
                "target_text": fallback_text,
            }
        )

        alignment_mode = "fallback_source_projection"
        confidence = 0.0
        matched_text = ""
        tts_start_sec = projected_start
        tts_end_sec = projected_end

        if query_tokens and slide_index != 1:
            best = find_best_word_span(query_tokens, words, word_cursor)
            if best and float(best["confidence"]) >= float(args.min_match_confidence):
                candidate_start = float(best["tts_start_sec"])
                candidate_end = float(best["tts_end_sec"])
                if (
                    abs(candidate_start - projected_start) <= float(args.max_boundary_adjust_sec)
                    or abs(candidate_end - projected_end) <= float(args.max_boundary_adjust_sec)
                ):
                    alignment_mode = "ocr_word_match"
                    confidence = float(best["confidence"])
                    matched_text = str(best["matched_text"])
                    tts_start_sec = candidate_start
                    tts_end_sec = max(candidate_start, candidate_end)
                    word_cursor = max(word_cursor, int(best["end_index"]))

        slide_voice_rows.append(
            {
                "slide_index": slide_index,
                "event_id": event_id,
                "bucket_id": str(event.get("bucket_id", "") or ""),
                "alignment_mode": alignment_mode,
                "confidence": round(confidence, 4),
                "projected_tts_start_sec": round(projected_start, 3),
                "projected_tts_end_sec": round(projected_end, 3),
                "tts_start_sec": round(tts_start_sec, 3),
                "tts_end_sec": round(tts_end_sec, 3),
                "matched_text": matched_text,
                "ocr_text": ocr_text,
                "translated_text": translated_text,
                "source_segment_ids": json.dumps(event.get("source_segment_ids", []) or []),
            }
        )

        reviewed_timeline_rows.append(
            {
                "slide_index": slide_index,
                "event_id": event_id,
                "bucket_id": str(event.get("bucket_id", "") or ""),
                "image_name": image_path.name,
                "reviewed_start_sec": round(tts_start_sec, 3),
                "reviewed_end_sec": round(tts_end_sec, 3),
                "duration_sec": round(max(0.0, tts_end_sec - tts_start_sec), 3),
                "alignment_mode": alignment_mode,
                "confidence": round(confidence, 4),
                "ocr_text": ocr_text,
                "matched_text": matched_text,
                "translated_text": translated_text,
            }
        )

    slide_ocr_payload = {
        "provider": "google_cloud_vision",
        "project_id_used": resolved_project,
        "default_project": default_project or "",
        "feature": str(args.feature).strip().upper(),
        "image_dir": str(image_dir),
        "slide_count": len(slide_ocr_rows),
        "slides": slide_ocr_rows,
    }
    slide_voice_payload = {
        "provider": "google_cloud_vision",
        "feature": str(args.feature).strip().upper(),
        "source_slide_map_json": str(slide_map_json),
        "source_tts_alignment_json": str(tts_alignment_json),
        "image_dir": str(image_dir),
        "slide_count": len(slide_voice_rows),
        "slides": slide_voice_rows,
    }
    reviewed_timeline_payload = {
        "provider": "google_cloud_vision",
        "feature": str(args.feature).strip().upper(),
        "source_slide_map_json": str(slide_map_json),
        "source_tts_alignment_json": str(tts_alignment_json),
        "image_dir": str(image_dir),
        "slide_count": len(reviewed_timeline_rows),
        "slides": reviewed_timeline_rows,
    }

    out_slide_ocr_json.write_text(json.dumps(slide_ocr_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_slide_voice_alignment_json.write_text(json.dumps(slide_voice_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_reviewed_timeline_json.write_text(json.dumps(reviewed_timeline_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_slide_ocr_csv, slide_ocr_rows)
    write_csv(out_slide_voice_alignment_csv, slide_voice_rows)
    write_csv(out_reviewed_timeline_csv, reviewed_timeline_rows)

    print(f"Reviewed slides: {len(reviewed_timeline_rows)}")
    print(f"OCR feature: {str(args.feature).strip().upper()}")
    print(f"Image dir: {image_dir}")
    print(f"Project: {resolved_project}")
    print(f"Full audio: {full_audio_path if full_audio_path else '-'}")
    print(f"Reviewed timeline: {out_reviewed_timeline_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
