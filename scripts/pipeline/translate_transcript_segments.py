#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.lib.cloud_translate import (
    ensure_cloud_translate_client,
    resolve_target_language_codes,
    translate_texts_llm,
)
from scripts.lib.translation_memory import (
    DEFAULT_TERMBASE_PATH,
    DEFAULT_TM_DB_PATH,
    apply_termbase_placeholders,
    init_translation_memory,
    load_termbase_entries,
    lookup_tm_exact,
    restore_termbase_placeholders,
    upsert_tm_entry,
)

LOCAL_ENV_PATH = ROOT_DIR / ".env.local"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate transcript segments into a target language while preserving segment IDs.")
    parser.add_argument("--input-json", required=True, help="Input transcript_segments.json path.")
    parser.add_argument("--out-json", required=True, help="Output JSON path.")
    parser.add_argument("--out-csv", required=True, help="Output CSV path.")
    parser.add_argument("--project-id", required=True, help="Google Cloud project id for Translation LLM.")
    parser.add_argument("--location", default="us-central1", help="Google Cloud Translation location, e.g. us-central1.")
    parser.add_argument("--model", default="general/translation-llm", help="Google Cloud Translation LLM model id or full model path.")
    parser.add_argument("--source-language-code", default="", help="Optional source language code. Leave empty for auto-detect.")
    parser.add_argument("--target-language", required=True, help="Target language label, e.g. French (France).")
    parser.add_argument("--termbase-file", default=str(DEFAULT_TERMBASE_PATH), help="CSV termbase path.")
    parser.add_argument("--tm-db", default=str(DEFAULT_TM_DB_PATH), help="SQLite translation memory path.")
    parser.add_argument("--origin-run-id", default="", help="Optional run id stored on newly created TM entries.")
    parser.add_argument("--chunk-size", type=int, default=12, help="Maximum number of translatable segments per chunk.")
    parser.add_argument("--chunk-max-chars", type=int, default=2800, help="Maximum total source characters per chunk.")
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


def load_transcript_segments(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_segments = payload.get("segments") if isinstance(payload, dict) else None
    if not isinstance(raw_segments, list):
        raise RuntimeError("Input JSON must contain a 'segments' array.")

    segments: list[dict[str, Any]] = []
    for row in raw_segments:
        if not isinstance(row, dict):
            continue
        text = " ".join(str(row.get("text", "") or "").split())
        segments.append(
            {
                "segment_id": int(row.get("segment_id", len(segments) + 1)),
                "start_sec": float(row.get("start_sec", 0.0) or 0.0),
                "end_sec": float(row.get("end_sec", row.get("start_sec", 0.0)) or 0.0),
                "text": text,
            }
        )
    segments.sort(key=lambda item: (item["start_sec"], item["end_sec"], item["segment_id"]))
    return segments


def build_translation_chunks(segments: list[dict[str, Any]], chunk_size: int, chunk_max_chars: int) -> list[list[dict[str, Any]]]:
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0
    max_count = max(1, int(chunk_size))
    max_chars = max(400, int(chunk_max_chars))

    for segment in segments:
        seg_len = len(str(segment.get("text", "") or ""))
        if current and (len(current) >= max_count or current_chars + seg_len > max_chars):
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(segment)
        current_chars += seg_len

    if current:
        chunks.append(current)
    return chunks


def translate_chunk(
    client,
    *,
    project_id: str,
    location: str,
    model: str,
    target_language: str,
    target_language_code: str,
    source_language_code: str,
    pending_segments: list[dict[str, Any]],
) -> dict[int, str]:
    translated_list = translate_texts_llm(
        client,
        project_id=project_id,
        location=location,
        model=model,
        contents=[str(item["protected_text"]) for item in pending_segments],
        target_language_code=target_language_code,
        source_language_code=source_language_code,
    )
    if len(translated_list) != len(pending_segments):
        raise RuntimeError(
            "Cloud Translation returned a mismatched translation count "
            f"(expected={len(pending_segments)}, got={len(translated_list)})."
        )

    out: dict[int, str] = {}
    for pending, translated_text in zip(pending_segments, translated_list, strict=True):
        segment_id = int(pending["segment_id"])
        translated_text = str(translated_text or "").strip()
        if not translated_text:
            raise RuntimeError(f"Cloud Translation did not return translated_text for segment_id={segment_id}.")
        out[segment_id] = translated_text
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "segment_id",
        "start_sec",
        "end_sec",
        "text",
        "translated_text",
        "target_language",
        "translation_status",
        "tm_exact_hit",
        "termbase_hits",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    load_local_env(LOCAL_ENV_PATH)

    target_language = str(args.target_language).strip()
    if not target_language:
        raise RuntimeError("--target-language must not be empty.")

    input_json = Path(args.input_json).resolve()
    out_json = Path(args.out_json).resolve()
    out_csv = Path(args.out_csv).resolve()
    termbase_file = Path(args.termbase_file).resolve()
    tm_db_path = Path(args.tm_db).resolve()

    if not input_json.exists():
        raise FileNotFoundError(input_json)

    segments = load_transcript_segments(input_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    termbase_entries = load_termbase_entries(termbase_file, target_language)
    target_language_code, _tts_language_code = resolve_target_language_codes(target_language)
    client, _translate_v3, resolved_project, _default_project, resolved_location = ensure_cloud_translate_client(
        str(args.project_id),
        str(args.location),
    )
    tm_conn = init_translation_memory(tm_db_path)

    translated_rows: list[dict[str, Any]] = []
    tm_exact_hits_total = 0
    termbase_hits_total = 0
    translated_count = 0
    results_by_segment_id: dict[int, dict[str, Any]] = {}

    translatable_segments = [segment for segment in segments if str(segment.get("text", "")).strip()]
    chunks = build_translation_chunks(translatable_segments, args.chunk_size, args.chunk_max_chars)

    for chunk_index, chunk in enumerate(chunks, start=1):
        pending_segments: list[dict[str, Any]] = []
        for segment in chunk:
            segment_id = int(segment["segment_id"])
            source_text = str(segment["text"])
            print(f"@@STEP DETAIL text-translate segment_{segment_id:04d}", flush=True)
            tm_hit = lookup_tm_exact(tm_conn, source_text, target_language)
            if tm_hit:
                results_by_segment_id[segment_id] = {
                    "translated_text": str(tm_hit.get("target_text", "") or ""),
                    "translation_status": "tm_exact",
                    "tm_exact_hit": 1,
                    "termbase_hits": 0,
                }
                tm_exact_hits_total += 1
                continue

            protected_text, placeholder_map, term_hits = apply_termbase_placeholders(source_text, termbase_entries)
            pending_segments.append(
                {
                    "segment_id": segment_id,
                    "source_text": source_text,
                    "protected_text": protected_text,
                    "placeholder_map": placeholder_map,
                    "termbase_hits": len(term_hits),
                }
            )

        if not pending_segments:
            continue

        print(
            f"[TranscriptTranslate] Translating chunk {chunk_index}/{len(chunks)} "
            f"({len(pending_segments)} segments)",
            flush=True,
        )
        translated_map = translate_chunk(
            client,
            project_id=resolved_project,
            location=resolved_location,
            model=str(args.model),
            target_language=target_language,
            target_language_code=target_language_code,
            source_language_code=str(args.source_language_code or "").strip(),
            pending_segments=pending_segments,
        )
        for pending in pending_segments:
            segment_id = int(pending["segment_id"])
            restored_text = restore_termbase_placeholders(
                translated_map[segment_id],
                dict(pending["placeholder_map"]),
            )
            upsert_tm_entry(
                tm_conn,
                source_text=str(pending["source_text"]),
                target_language=target_language,
                target_text=restored_text,
                status="machine_unreviewed",
                origin_run_id=str(args.origin_run_id or ""),
            )
            term_hits = int(pending["termbase_hits"])
            results_by_segment_id[segment_id] = {
                "translated_text": restored_text,
                "translation_status": "translated_with_termbase" if term_hits else "translated",
                "tm_exact_hit": 0,
                "termbase_hits": term_hits,
            }
            translated_count += 1
            termbase_hits_total += term_hits

    for segment in segments:
        segment_id = int(segment["segment_id"])
        source_text = str(segment["text"] or "")
        result = results_by_segment_id.get(segment_id)
        if result is None:
            result = {
                "translated_text": source_text,
                "translation_status": "skipped_empty" if not source_text.strip() else "source_fallback",
                "tm_exact_hit": 0,
                "termbase_hits": 0,
            }
        translated_rows.append(
            {
                "segment_id": segment_id,
                "start_sec": round(float(segment["start_sec"]), 3),
                "end_sec": round(float(segment["end_sec"]), 3),
                "text": source_text,
                "translated_text": str(result["translated_text"]),
                "target_language": target_language,
                "translation_status": str(result["translation_status"]),
                "tm_exact_hit": int(result["tm_exact_hit"]),
                "termbase_hits": int(result["termbase_hits"]),
            }
        )

    payload = {
        "source_json": str(input_json),
        "target_language": target_language,
        "target_language_code": target_language_code,
        "project_id": resolved_project,
        "location": resolved_location,
        "model": str(args.model),
        "source_language_code": str(args.source_language_code or "").strip(),
        "segment_count": len(segments),
        "translated_segment_count": len([row for row in translated_rows if row["translated_text"]]),
        "tm_exact_hits": tm_exact_hits_total,
        "translated_new_segments": translated_count,
        "termbase_hits": termbase_hits_total,
        "segments": translated_rows,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_csv, translated_rows)

    tm_conn.close()
    print(f"[TranscriptTranslate] Segments processed: {len(segments)}", flush=True)
    print(f"[TranscriptTranslate] TM exact hits: {tm_exact_hits_total}", flush=True)
    print(f"[TranscriptTranslate] New translated segments: {translated_count}", flush=True)
    print(f"[TranscriptTranslate] Termbase hits: {termbase_hits_total}", flush=True)
    print(f"[TranscriptTranslate] Output JSON: {out_json}", flush=True)
    print(f"[TranscriptTranslate] Output CSV: {out_csv}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
