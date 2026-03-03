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

from scripts.lib.cloud_tts import ensure_cloud_tts_client, synthesize_cloud_tts_audio, write_wave_bytes

LOCAL_ENV_PATH = ROOT_DIR / ".env.local"
DEFAULT_PROMPT_PATH = ROOT_DIR / "config" / "prompts" / "gemini_tts_prompt.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate per-slide TTS WAV files from translated slide text.")
    parser.add_argument("--input-json", required=True, help="Input translated slide text map JSON path.")
    parser.add_argument("--output-dir", required=True, help="Directory for generated WAV files.")
    parser.add_argument("--out-manifest-json", required=True, help="Output JSON manifest path.")
    parser.add_argument("--out-manifest-csv", required=True, help="Output CSV manifest path.")
    parser.add_argument("--model", default="gemini-2.5-flash-tts", help="Google Cloud Gemini TTS model.")
    parser.add_argument("--voice", default="Kore", help="Gemini prebuilt voice name.")
    parser.add_argument("--project-id", default="", help="Google Cloud project id used for quota/billing.")
    parser.add_argument("--language-code", default="en-US", help="Language code for Cloud TTS, e.g. en-US.")
    parser.add_argument(
        "--prompt-file",
        default=str(DEFAULT_PROMPT_PATH),
        help="Prompt template path for TTS style guidance.",
    )
    parser.add_argument(
        "--language-label",
        default="",
        help="Language label injected into the prompt. Falls back to source language of the text.",
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


def load_prompt(path: Path, language_label: str, voice_name: str) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    template = path.read_text(encoding="utf-8").strip()
    if not template:
        raise RuntimeError(f"Prompt file is empty: {path}")
    prompt = template.replace("{{TARGET_LANGUAGE}}", language_label.strip())
    prompt = prompt.replace("{{VOICE_NAME}}", voice_name.strip())
    return prompt


def write_csv(path: Path, items: list[dict[str, Any]]) -> None:
    fieldnames = [
        "slide_index",
        "event_id",
        "bucket_id",
        "audio_file",
        "duration_sec",
        "language_label",
        "voice_name",
        "status",
        "text",
        "translated_text",
        "tts_text",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)


def main() -> int:
    args = parse_args()
    load_local_env(LOCAL_ENV_PATH)

    input_json = Path(args.input_json).resolve()
    output_dir = Path(args.output_dir).resolve()
    out_manifest_json = Path(args.out_manifest_json).resolve()
    out_manifest_csv = Path(args.out_manifest_csv).resolve()
    prompt_file = Path(args.prompt_file).resolve()

    if not input_json.exists():
        raise FileNotFoundError(input_json)

    payload = json.loads(input_json.read_text(encoding="utf-8"))
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        raise RuntimeError("Input JSON must contain an 'events' array.")

    output_dir.mkdir(parents=True, exist_ok=True)
    out_manifest_json.parent.mkdir(parents=True, exist_ok=True)
    out_manifest_csv.parent.mkdir(parents=True, exist_ok=True)

    language_label = str(args.language_label).strip() or str(
        payload.get("text_translation", {}).get("target_language", "source language of the text")
    )
    if not str(args.language_code).strip():
        raise RuntimeError("--language-code must not be empty.")
    client, texttospeech, _resolved_project, _default_project = ensure_cloud_tts_client(str(args.project_id))
    prompt = load_prompt(prompt_file, language_label, str(args.voice).strip())

    manifest_items: list[dict[str, Any]] = []
    generated_count = 0
    skipped_count = 0
    failed_count = 0

    for idx, event in enumerate(events, start=1):
        event_id = int(event.get("event_id", 0) or 0)
        bucket_id = str(event.get("bucket_id", "") or "")
        source_text = str(event.get("text", "") or "").strip()
        translated_text = str(event.get("translated_text", "") or "").strip()
        tts_text = translated_text or source_text
        audio_name = f"slide_{idx:03d}_event_{event_id:03d}.wav"
        audio_path = output_dir / audio_name

        item = {
            "slide_index": idx,
            "event_id": event_id,
            "bucket_id": bucket_id,
            "audio_file": audio_name,
            "duration_sec": 0.0,
            "language_label": language_label,
            "voice_name": str(args.voice).strip(),
            "status": "pending",
            "text": source_text,
            "translated_text": translated_text,
            "tts_text": tts_text,
        }

        print(f"@@STEP DETAIL tts {bucket_id or f'event_{event_id:03d}'}", flush=True)

        if not tts_text:
            item["status"] = "skipped_empty"
            manifest_items.append(item)
            skipped_count += 1
            print(f"[TTS] Skip event {event_id}: empty text.", flush=True)
            continue

        try:
            audio_bytes = synthesize_cloud_tts_audio(
                client,
                texttospeech,
                model=str(args.model),
                voice_name=str(args.voice).strip(),
                language_code=str(args.language_code).strip(),
                prompt=prompt,
                text=tts_text,
            )
            item["duration_sec"] = write_wave_bytes(audio_path, audio_bytes)
        except Exception as exc:  # noqa: BLE001
            item["status"] = "error"
            manifest_items.append(item)
            failed_count += 1
            print(f"[TTS] ERROR event {event_id}: {exc}", flush=True)
            continue

        item["status"] = "generated"
        manifest_items.append(item)
        generated_count += 1
        print(f"[TTS] Generated {audio_name} ({item['duration_sec']:.3f}s)", flush=True)

    manifest = {
        "source_json": str(input_json),
        "model": str(args.model),
        "voice_name": str(args.voice).strip(),
        "project_id": str(args.project_id).strip(),
        "language_code": str(args.language_code).strip(),
        "language_label": language_label,
        "prompt_file": str(prompt_file),
        "generated_count": generated_count,
        "skipped_empty_count": skipped_count,
        "failed_count": failed_count,
        "items": manifest_items,
    }
    out_manifest_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_manifest_csv, manifest_items)

    print(f"[TTS] Slides processed: {len(events)}", flush=True)
    print(f"[TTS] Generated: {generated_count}", flush=True)
    print(f"[TTS] Skipped empty: {skipped_count}", flush=True)
    print(f"[TTS] Failed: {failed_count}", flush=True)
    print(f"[TTS] Project: {args.project_id}", flush=True)
    print(f"[TTS] Language code: {args.language_code}", flush=True)
    print(f"[TTS] Voice: {args.voice}", flush=True)
    print(f"[TTS] Language: {language_label}", flush=True)
    print(f"[TTS] Output dir: {output_dir}", flush=True)
    print(f"[TTS] Manifest JSON: {out_manifest_json}", flush=True)
    print(f"[TTS] Manifest CSV: {out_manifest_csv}", flush=True)
    return 1 if failed_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
