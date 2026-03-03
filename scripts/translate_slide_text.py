#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
LOCAL_ENV_PATH = ROOT_DIR / ".env.local"
DEFAULT_PROMPT_PATH = ROOT_DIR / "config" / "gemini_text_translate_prompt.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate slide_text_map_final events into a target language.")
    parser.add_argument("--input-json", required=True, help="Input slide_text_map_final JSON path.")
    parser.add_argument("--out-json", required=True, help="Output JSON path.")
    parser.add_argument("--out-csv", required=True, help="Output CSV path.")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Gemini text model.")
    parser.add_argument(
        "--prompt-file",
        default=str(DEFAULT_PROMPT_PATH),
        help="Prompt template path.",
    )
    parser.add_argument(
        "--target-language",
        required=True,
        help="Target language, e.g. German or French.",
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


def translate_text(client, model: str, prompt: str, source_text: str) -> str:
    response = client.models.generate_content(
        model=model,
        contents=[
            f"{prompt}\n\nSource text:\n{json.dumps(source_text, ensure_ascii=False)}"
        ],
        config={
            "response_mime_type": "application/json",
        },
    )
    raw = strip_code_fences(extract_response_text(response))
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse Gemini translation JSON: {raw[:200]}") from exc
    translated = str(payload.get("translated_text", "") or "").strip()
    if not translated:
        raise RuntimeError("Gemini translation JSON did not include translated_text.")
    return translated


def write_csv(path: Path, events: list[dict[str, Any]]) -> None:
    fieldnames = [
        "slide_index",
        "event_id",
        "bucket_id",
        "slide_start",
        "slide_end",
        "is_no_slide",
        "merge_target_event_id",
        "text",
        "translated_text",
        "target_language",
        "translation_status",
        "segments_count",
        "source_segment_ids",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in events:
            writer.writerow(
                {
                    "slide_index": row.get("slide_index", ""),
                    "event_id": row.get("event_id", ""),
                    "bucket_id": row.get("bucket_id", ""),
                    "slide_start": row.get("slide_start", ""),
                    "slide_end": row.get("slide_end", ""),
                    "is_no_slide": row.get("is_no_slide", ""),
                    "merge_target_event_id": row.get("merge_target_event_id", ""),
                    "text": row.get("text", ""),
                    "translated_text": row.get("translated_text", ""),
                    "target_language": row.get("target_language", ""),
                    "translation_status": row.get("translation_status", ""),
                    "segments_count": row.get("segments_count", ""),
                    "source_segment_ids": json.dumps(row.get("source_segment_ids", []), ensure_ascii=False),
                }
            )


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

    if not input_json.exists():
        raise FileNotFoundError(input_json)

    payload = json.loads(input_json.read_text(encoding="utf-8"))
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        raise RuntimeError("Input JSON must contain an 'events' array.")

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    prompt = load_prompt(prompt_file, target_language)
    client = ensure_client()

    translated_events: list[dict[str, Any]] = []
    translated_count = 0
    skipped_count = 0
    failed_count = 0

    for idx, event in enumerate(events, start=1):
        event_id = int(event.get("event_id", 0) or 0)
        bucket_id = str(event.get("bucket_id", "") or "")
        source_text = str(event.get("text", "") or "").strip()
        translated_event = dict(event)
        translated_event["slide_index"] = idx
        translated_event["target_language"] = target_language
        translated_event["translated_text"] = ""
        translated_event["translation_status"] = "pending"
        print(f"@@STEP DETAIL text-translate {bucket_id or f'event_{event_id:03d}'}", flush=True)

        if not source_text:
            translated_event["translation_status"] = "skipped_empty"
            translated_events.append(translated_event)
            skipped_count += 1
            print(f"[TextTranslate] Skip event {event_id}: empty text.", flush=True)
            continue

        try:
            translated_text = translate_text(client, str(args.model), prompt, source_text)
        except Exception as exc:  # noqa: BLE001
            translated_event["translation_status"] = "error"
            translated_events.append(translated_event)
            failed_count += 1
            print(f"[TextTranslate] ERROR event {event_id}: {exc}", flush=True)
            continue

        translated_event["translated_text"] = translated_text
        translated_event["translation_status"] = "translated"
        translated_events.append(translated_event)
        translated_count += 1
        print(f"[TextTranslate] Translated event {event_id}", flush=True)

    out_payload = dict(payload)
    out_payload["text_translation"] = {
        "model": str(args.model),
        "prompt_file": str(prompt_file),
        "target_language": target_language,
        "translated_count": translated_count,
        "skipped_empty_count": skipped_count,
        "failed_count": failed_count,
    }
    out_payload["events"] = translated_events
    out_json.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_csv, translated_events)

    print(f"[TextTranslate] Events processed: {len(events)}", flush=True)
    print(f"[TextTranslate] Translated: {translated_count}", flush=True)
    print(f"[TextTranslate] Skipped empty: {skipped_count}", flush=True)
    print(f"[TextTranslate] Failed: {failed_count}", flush=True)
    print(f"[TextTranslate] Target language: {target_language}", flush=True)
    print(f"[TextTranslate] Output JSON: {out_json}", flush=True)
    print(f"[TextTranslate] Output CSV: {out_csv}", flush=True)
    return 1 if failed_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
