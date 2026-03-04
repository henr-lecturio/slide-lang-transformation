#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import wave
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.lib.cloud_tts import ensure_cloud_tts_client, write_wave_bytes, synthesize_cloud_tts_audio

LOCAL_ENV_PATH = ROOT_DIR / ".env.local"
DEFAULT_PROMPT_PATH = ROOT_DIR / "config" / "prompts" / "gemini_tts_prompt.txt"
DEFAULT_TTS_MAX_TEXT_BYTES = 3800
DEFAULT_TTS_MAX_PROMPT_BYTES = 4000
DEFAULT_TTS_MAX_REQUEST_BYTES = 7900
DEFAULT_TTS_SINGLE_REQUEST_MAX_ESTIMATED_SEC = 620.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate chunked full-transcript TTS audio from translated transcript segments.")
    parser.add_argument("--input-json", required=True, help="Input transcript JSON (translated preferred).")
    parser.add_argument("--output-dir", required=True, help="Directory for generated WAV files.")
    parser.add_argument("--out-manifest-json", required=True, help="Output JSON manifest path.")
    parser.add_argument("--out-manifest-csv", required=True, help="Output CSV manifest path.")
    parser.add_argument("--model", default="gemini-2.5-flash-tts", help="Google Cloud Gemini TTS model.")
    parser.add_argument("--voice", default="Kore", help="Gemini prebuilt voice name.")
    parser.add_argument("--project-id", default="", help="Google Cloud project id used for quota/billing.")
    parser.add_argument("--language-code", default="en-US", help="Language code for Cloud TTS, e.g. en-US.")
    parser.add_argument("--prompt-file", default=str(DEFAULT_PROMPT_PATH), help="Prompt template path for TTS style guidance.")
    parser.add_argument("--language-label", default="", help="Language label injected into the prompt.")
    parser.add_argument("--max-chars", type=int, default=3200, help="Soft maximum characters per TTS chunk.")
    parser.add_argument("--max-segments-per-chunk", type=int, default=40, help="Soft maximum transcript segments per TTS chunk.")
    parser.add_argument("--max-text-bytes", type=int, default=DEFAULT_TTS_MAX_TEXT_BYTES, help="Hard maximum UTF-8 text bytes per TTS request.")
    parser.add_argument("--max-prompt-bytes", type=int, default=DEFAULT_TTS_MAX_PROMPT_BYTES, help="Hard maximum UTF-8 prompt bytes per TTS request.")
    parser.add_argument("--max-request-bytes", type=int, default=DEFAULT_TTS_MAX_REQUEST_BYTES, help="Hard maximum combined prompt+text UTF-8 bytes per TTS request.")
    parser.add_argument("--single-request-max-estimated-sec", type=float, default=DEFAULT_TTS_SINGLE_REQUEST_MAX_ESTIMATED_SEC, help="Try a single TTS request only if the original transcript duration stays below this estimate.")
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


def utf8_size(value: str) -> int:
    return len(str(value or "").encode("utf-8"))


def estimated_transcript_duration(segments: list[dict[str, Any]]) -> float:
    if not segments:
        return 0.0
    starts = [float(seg.get("start_sec", 0.0) or 0.0) for seg in segments]
    ends = [float(seg.get("end_sec", 0.0) or 0.0) for seg in segments]
    return max(0.0, max(ends) - min(starts))


def effective_text_byte_budget(prompt: str, max_text_bytes: int, max_prompt_bytes: int, max_request_bytes: int) -> int:
    prompt_bytes = utf8_size(prompt)
    if prompt_bytes <= 0:
        raise RuntimeError("TTS prompt is empty.")
    if prompt_bytes > max_prompt_bytes:
        raise RuntimeError(
            f"TTS prompt is too large for Gemini TTS: {prompt_bytes} bytes > {max_prompt_bytes}."
        )
    remaining = max_request_bytes - prompt_bytes
    if remaining <= 0:
        raise RuntimeError(
            f"TTS prompt consumes the full request budget: prompt={prompt_bytes} bytes, request max={max_request_bytes}."
        )
    return max(200, min(max_text_bytes, remaining))


def build_chunk_payloads(
    segments: list[dict[str, Any]],
    *,
    prompt: str,
    max_chars: int,
    max_segments: int,
    max_text_bytes: int,
    max_prompt_bytes: int,
    max_request_bytes: int,
    single_request_max_estimated_sec: float,
) -> tuple[list[list[dict[str, Any]]], str, int]:
    if not segments:
        return [], "none", 0

    allowed_text_bytes = effective_text_byte_budget(prompt, max_text_bytes, max_prompt_bytes, max_request_bytes)
    max_chars = max(200, int(max_chars))
    max_segments = max(1, int(max_segments))
    estimated_sec = estimated_transcript_duration(segments)
    full_text = " ".join(str(item["tts_text"]).strip() for item in segments if str(item["tts_text"]).strip()).strip()
    full_text_bytes = utf8_size(full_text)

    if full_text and full_text_bytes <= allowed_text_bytes and estimated_sec <= float(single_request_max_estimated_sec):
        return [segments], "single_request", allowed_text_bytes

    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0
    current_bytes = 0

    for segment in segments:
        tts_text = str(segment.get("tts_text") or "").strip()
        if not tts_text:
            continue
        seg_chars = len(tts_text)
        seg_bytes = utf8_size(tts_text)
        if seg_bytes > allowed_text_bytes:
            raise RuntimeError(
                f"Transcript segment {segment.get('segment_id')} exceeds the Gemini TTS request text budget "
                f"({seg_bytes} bytes > {allowed_text_bytes})."
            )
        extra_chars = (1 if current else 0) + seg_chars
        extra_bytes = (1 if current else 0) + seg_bytes
        next_chars = current_chars + extra_chars
        next_bytes = current_bytes + extra_bytes
        if current and (len(current) >= max_segments or next_chars > max_chars or next_bytes > allowed_text_bytes):
            chunks.append(current)
            current = []
            current_chars = 0
            current_bytes = 0
            extra_chars = seg_chars
            extra_bytes = seg_bytes
        current.append(segment)
        current_chars += extra_chars
        current_bytes += extra_bytes
    if current:
        chunks.append(current)
    return chunks, "chapter_chunks", allowed_text_bytes


def concatenate_wavs(chunk_paths: list[Path], out_path: Path) -> float:
    if not chunk_paths:
        raise RuntimeError("No TTS chunk files were generated.")
    params: tuple[int, int, int] | None = None
    total_frames = 0
    with wave.open(str(out_path), "wb") as out_wav:
        for path in chunk_paths:
            with wave.open(str(path), "rb") as in_wav:
                current = (
                    in_wav.getnchannels(),
                    in_wav.getsampwidth(),
                    in_wav.getframerate(),
                )
                if params is None:
                    params = current
                    out_wav.setnchannels(current[0])
                    out_wav.setsampwidth(current[1])
                    out_wav.setframerate(current[2])
                elif params != current:
                    raise RuntimeError(f"Incompatible WAV parameters while concatenating: {path}")
                frames = in_wav.readframes(in_wav.getnframes())
                out_wav.writeframes(frames)
                total_frames += in_wav.getnframes()
    assert params is not None
    return round(total_frames / float(params[2]), 3)


def write_csv(path: Path, items: list[dict[str, Any]]) -> None:
    fieldnames = [
        "chunk_index",
        "audio_file",
        "start_sec",
        "end_sec",
        "duration_sec",
        "segment_count",
        "segment_ids",
        "language_label",
        "voice_name",
        "status",
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
    if not str(args.language_code).strip():
        raise RuntimeError("--language-code must not be empty.")

    payload = json.loads(input_json.read_text(encoding="utf-8"))
    segments = payload.get("segments") if isinstance(payload, dict) else None
    if not isinstance(segments, list):
        raise RuntimeError("Input JSON must contain a 'segments' array.")

    output_dir.mkdir(parents=True, exist_ok=True)
    out_manifest_json.parent.mkdir(parents=True, exist_ok=True)
    out_manifest_csv.parent.mkdir(parents=True, exist_ok=True)

    language_label = str(args.language_label).strip() or str(payload.get("target_language", "source language of the text"))
    client, texttospeech, resolved_project, _default_project = ensure_cloud_tts_client(str(args.project_id))
    prompt = load_prompt(prompt_file, language_label, str(args.voice).strip())

    source_segments: list[dict[str, Any]] = []
    for segment in segments:
        tts_text = str(segment.get("translated_text") or segment.get("text") or "").strip()
        if not tts_text:
            continue
        source_segments.append(
            {
                "segment_id": int(segment.get("segment_id", 0) or 0),
                "start_sec": float(segment.get("start_sec", 0.0) or 0.0),
                "end_sec": float(segment.get("end_sec", 0.0) or 0.0),
                "text": str(segment.get("text", "") or "").strip(),
                "translated_text": str(segment.get("translated_text", "") or "").strip(),
                "tts_text": tts_text,
            }
        )

    chunks, synthesis_mode, allowed_text_bytes = build_chunk_payloads(
        source_segments,
        prompt=prompt,
        max_chars=int(args.max_chars),
        max_segments=int(args.max_segments_per_chunk),
        max_text_bytes=int(args.max_text_bytes),
        max_prompt_bytes=int(args.max_prompt_bytes),
        max_request_bytes=int(args.max_request_bytes),
        single_request_max_estimated_sec=float(args.single_request_max_estimated_sec),
    )
    if not chunks:
        raise RuntimeError("No non-empty transcript segments available for TTS.")

    manifest_items: list[dict[str, Any]] = []
    chunk_paths: list[Path] = []
    generated_count = 0
    failed_count = 0
    current_start = 0.0

    for idx, chunk in enumerate(chunks, start=1):
        chunk_text = " ".join(str(item["tts_text"]).strip() for item in chunk if str(item["tts_text"]).strip()).strip()
        audio_name = f"chunk_{idx:03d}.wav"
        audio_path = output_dir / audio_name
        segment_ids = [int(item["segment_id"]) for item in chunk]
        manifest_item = {
            "chunk_index": idx,
            "audio_file": audio_name,
            "start_sec": 0.0,
            "end_sec": 0.0,
            "duration_sec": 0.0,
            "segment_count": len(chunk),
            "segment_ids": segment_ids,
            "language_label": language_label,
            "voice_name": str(args.voice).strip(),
            "status": "pending",
            "tts_text": chunk_text,
        }
        print(f"@@STEP DETAIL tts chunk_{idx:03d}", flush=True)
        try:
            audio_bytes = synthesize_cloud_tts_audio(
                client,
                texttospeech,
                model=str(args.model),
                voice_name=str(args.voice).strip(),
                language_code=str(args.language_code).strip(),
                prompt=prompt,
                text=chunk_text,
            )
            duration_sec = write_wave_bytes(audio_path, audio_bytes)
            manifest_item["duration_sec"] = duration_sec
            manifest_item["start_sec"] = round(current_start, 3)
            manifest_item["end_sec"] = round(current_start + duration_sec, 3)
            manifest_item["status"] = "generated"
            current_start += duration_sec
            chunk_paths.append(audio_path)
            generated_count += 1
            print(f"[TTS] Generated {audio_name} ({duration_sec:.3f}s)", flush=True)
        except Exception as exc:  # noqa: BLE001
            manifest_item["status"] = "error"
            failed_count += 1
            print(f"[TTS] ERROR chunk {idx}: {exc}", flush=True)
        manifest_items.append(manifest_item)

    if generated_count == 0:
        raise RuntimeError("No TTS chunks were generated successfully.")

    full_audio_name = "full_transcript.wav"
    full_audio_path = output_dir / full_audio_name
    total_duration_sec = concatenate_wavs(chunk_paths, full_audio_path)

    manifest = {
        "source_json": str(input_json),
        "model": str(args.model),
        "voice_name": str(args.voice).strip(),
        "project_id": resolved_project,
        "language_code": str(args.language_code).strip(),
        "language_label": language_label,
        "prompt_file": str(prompt_file),
        "synthesis_mode": synthesis_mode,
        "max_chars": int(args.max_chars),
        "max_segments_per_chunk": int(args.max_segments_per_chunk),
        "max_text_bytes": int(args.max_text_bytes),
        "max_prompt_bytes": int(args.max_prompt_bytes),
        "max_request_bytes": int(args.max_request_bytes),
        "effective_text_byte_budget": allowed_text_bytes,
        "estimated_transcript_duration_sec": round(estimated_transcript_duration(source_segments), 3),
        "chunk_count": len(manifest_items),
        "generated_count": generated_count,
        "failed_count": failed_count,
        "translated_segment_count": len(source_segments),
        "full_audio_file": full_audio_name,
        "full_audio_duration_sec": total_duration_sec,
        "chunks": manifest_items,
    }
    out_manifest_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_manifest_csv, manifest_items)

    print(f"[TTS] Transcript segments processed: {len(source_segments)}", flush=True)
    print(f"[TTS] Synthesis mode: {synthesis_mode}", flush=True)
    print(f"[TTS] Effective text byte budget: {allowed_text_bytes}", flush=True)
    print(f"[TTS] Chunks generated: {generated_count}/{len(manifest_items)}", flush=True)
    print(f"[TTS] Failed chunks: {failed_count}", flush=True)
    print(f"[TTS] Full transcript audio: {full_audio_path}", flush=True)
    print(f"[TTS] Full transcript duration: {total_duration_sec:.3f}s", flush=True)
    print(f"[TTS] Manifest JSON: {out_manifest_json}", flush=True)
    print(f"[TTS] Manifest CSV: {out_manifest_csv}", flush=True)
    return 1 if failed_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
