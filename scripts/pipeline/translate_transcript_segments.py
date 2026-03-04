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

from scripts.lib.translation_memory import (
    DEFAULT_TERMBASE_PATH,
    DEFAULT_TM_DB_PATH,
    apply_termbase_placeholders,
    append_glossary_to_prompt,
    init_translation_memory,
    load_termbase_entries,
    lookup_tm_exact,
    restore_termbase_placeholders,
    upsert_tm_entry,
)

LOCAL_ENV_PATH = ROOT_DIR / ".env.local"
DEFAULT_PROMPT_PATH = ROOT_DIR / "config" / "prompts" / "gemini_text_translate_prompt.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate transcript segments into a target language while preserving segment IDs.")
    parser.add_argument("--input-json", required=True, help="Input transcript_segments.json path.")
    parser.add_argument("--out-json", required=True, help="Output JSON path.")
    parser.add_argument("--out-csv", required=True, help="Output CSV path.")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Gemini text model.")
    parser.add_argument("--prompt-file", default=str(DEFAULT_PROMPT_PATH), help="Prompt template path.")
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


def load_prompt(path: Path, target_language: str) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    template = path.read_text(encoding="utf-8").strip()
    if not template:
        raise RuntimeError(f"Prompt file is empty: {path}")
    prompt = template.replace("{{TARGET_LANGUAGE}}", target_language.strip())
    if "{{TARGET_LANGUAGE}}" not in template:
        prompt = f"Target language: {target_language.strip()}\n\n{prompt}"
    if "placeholder" not in prompt.lower():
        prompt = (
            f"{prompt}\n\n"
            "If the source text contains placeholders like __TERM_0001__, preserve them exactly and do not translate, rewrite, or remove them."
        )
    return prompt


def ensure_client():
    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-genai is not installed in this environment. "
            "Run: source .venv/bin/activate && pip install google-genai"
        ) from exc

    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")
    return genai.Client(api_key=api_key)


def extract_response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            part_text = getattr(part, "text", None)
            if isinstance(part_text, str) and part_text.strip():
                return part_text.strip()
    raise RuntimeError("Gemini response did not contain text.")


def strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


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
    model: str,
    prompt: str,
    target_language: str,
    pending_segments: list[dict[str, Any]],
) -> dict[int, str]:
    request_segments = [
        {
            "segment_id": int(item["segment_id"]),
            "text": str(item["protected_text"]),
        }
        for item in pending_segments
    ]
    instruction = (
        f"{prompt}\n\n"
        f"Translate the following transcript segments into {target_language}.\n"
        "Keep each segment aligned to the same segment_id.\n"
        "Return valid JSON only with this shape:\n"
        '{"segments":[{"segment_id":123,"translated_text":"..."}]}\n\n'
        f"Segments:\n{json.dumps(request_segments, ensure_ascii=False)}"
    )
    response = client.models.generate_content(
        model=model,
        contents=[instruction],
        config={"response_mime_type": "application/json"},
    )
    raw = strip_code_fences(extract_response_text(response))
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse Gemini transcript translation JSON: {raw[:300]}") from exc

    translated_segments = payload.get("segments")
    if not isinstance(translated_segments, list):
        raise RuntimeError("Gemini transcript translation JSON did not include a valid 'segments' array.")

    out: dict[int, str] = {}
    for item in translated_segments:
        if not isinstance(item, dict):
            continue
        try:
            segment_id = int(item.get("segment_id"))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Gemini transcript translation returned an invalid segment_id: {item!r}") from exc
        translated_text = str(item.get("translated_text", "") or "").strip()
        if not translated_text:
            raise RuntimeError(f"Gemini transcript translation did not include translated_text for segment_id={segment_id}.")
        out[segment_id] = translated_text

    expected_ids = {int(item["segment_id"]) for item in pending_segments}
    returned_ids = set(out)
    if returned_ids != expected_ids:
        missing = sorted(expected_ids - returned_ids)
        extra = sorted(returned_ids - expected_ids)
        raise RuntimeError(
            "Gemini transcript translation returned mismatched segment ids "
            f"(missing={missing[:5]}, extra={extra[:5]})."
        )
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
    prompt_file = Path(args.prompt_file).resolve()
    termbase_file = Path(args.termbase_file).resolve()
    tm_db_path = Path(args.tm_db).resolve()

    if not input_json.exists():
        raise FileNotFoundError(input_json)

    segments = load_transcript_segments(input_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    termbase_entries = load_termbase_entries(termbase_file, target_language)
    prompt = append_glossary_to_prompt(load_prompt(prompt_file, target_language), termbase_entries)
    client = ensure_client()
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
            model=str(args.model),
            prompt=prompt,
            target_language=target_language,
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
        "model": str(args.model),
        "prompt_file": str(prompt_file),
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
