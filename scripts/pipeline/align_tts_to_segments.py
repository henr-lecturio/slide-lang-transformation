#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


WORD_RE = re.compile(r"\w+", re.UNICODE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Align full-transcript TTS chunk audio back to transcript segments.")
    parser.add_argument("--transcript-json", required=True, help="Transcript JSON path (translated preferred).")
    parser.add_argument("--tts-manifest-json", required=True, help="Transcript TTS manifest JSON path.")
    parser.add_argument("--out-json", required=True, help="Output alignment JSON path.")
    parser.add_argument("--out-csv", required=True, help="Output alignment CSV path.")
    parser.add_argument("--model", default="small", help="faster-whisper model for chunk re-transcription.")
    parser.add_argument("--device", default="cuda", help="faster-whisper device.")
    parser.add_argument("--compute-type", default="float16", help="faster-whisper compute type.")
    parser.add_argument("--language", default="", help="Optional ASR language code for alignment, e.g. de.")
    parser.add_argument("--beam-size", type=int, default=3, help="Beam size for alignment ASR.")
    parser.add_argument("--min-word-similarity", type=float, default=0.55, help="Minimum chunk text similarity to trust word timing alignment.")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_text(text: str) -> str:
    return " ".join((text or "").split())


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", clean_text(text)).lower()
    normalized = re.sub(r"[^\w\s]", "", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def token_count(text: str) -> int:
    return len(WORD_RE.findall(unicodedata.normalize("NFKC", str(text or "")).lower()))


def punctuation_bonus(text: str) -> float:
    stripped = str(text or "").strip()
    if not stripped:
        return 0.0
    if stripped.endswith((".", "!", "?")):
        return 0.6
    if stripped.endswith((",", ";", ":")):
        return 0.25
    return 0.0


def allocate_word_counts(weights: list[float], total_words: int) -> list[int] | None:
    positive = [idx for idx, weight in enumerate(weights) if weight > 0]
    if total_words <= 0 or not positive:
        return [0] * len(weights)
    if total_words < len(positive):
        return None

    counts = [0] * len(weights)
    for idx in positive:
        counts[idx] = 1
    remaining = total_words - len(positive)
    if remaining <= 0:
        return counts

    total_weight = sum(weights[idx] for idx in positive)
    ideals: list[tuple[float, int]] = []
    for idx in positive:
        ideal = (weights[idx] / total_weight) * remaining if total_weight > 0 else 0.0
        add = int(math.floor(ideal))
        counts[idx] += add
        ideals.append((ideal - add, idx))
    used = sum(counts) - len(positive)
    leftover = remaining - used
    ideals.sort(reverse=True)
    for _fraction, idx in ideals:
        if leftover <= 0:
            break
        counts[idx] += 1
        leftover -= 1
    return counts


def write_csv(path: Path, items: list[dict[str, Any]]) -> None:
    fieldnames = [
        "segment_id",
        "chunk_index",
        "source_start_sec",
        "source_end_sec",
        "tts_start_sec",
        "tts_end_sec",
        "tts_duration_sec",
        "alignment_mode",
        "confidence",
        "text",
        "translated_text",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)


def load_whisper_model(model_name: str, device: str, compute_type: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "faster-whisper is not installed in this environment. "
            "Run: source .venv/bin/activate && pip install faster-whisper"
        ) from exc
    return WhisperModel(model_name, device=device, compute_type=compute_type)


def transcribe_words(model, audio_path: Path, language: str, beam_size: int) -> tuple[list[dict[str, Any]], str]:
    kwargs: dict[str, Any] = {
        "beam_size": max(1, int(beam_size)),
        "vad_filter": False,
        "word_timestamps": True,
    }
    if language.strip():
        kwargs["language"] = language.strip()
    segments_iter, _info = model.transcribe(str(audio_path), **kwargs)
    words: list[dict[str, Any]] = []
    text_parts: list[str] = []
    for segment in segments_iter:
        segment_text = clean_text(getattr(segment, "text", ""))
        if segment_text:
            text_parts.append(segment_text)
        for word in getattr(segment, "words", []) or []:
            raw = str(getattr(word, "word", "") or "").strip()
            normalized = normalize_text(raw)
            if not normalized:
                continue
            words.append(
                {
                    "text": raw,
                    "normalized": normalized,
                    "start": float(getattr(word, "start", 0.0) or 0.0),
                    "end": float(getattr(word, "end", 0.0) or 0.0),
                }
            )
    return words, clean_text(" ".join(text_parts))


def align_chunk_with_words(
    chunk: dict[str, Any],
    chunk_segments: list[dict[str, Any]],
    recognized_words: list[dict[str, Any]],
    chunk_similarity: float,
) -> list[dict[str, Any]]:
    chunk_start = float(chunk.get("start_sec", 0.0) or 0.0)
    chunk_end = float(chunk.get("end_sec", chunk_start) or chunk_start)
    chunk_duration = max(0.0, chunk_end - chunk_start)
    weights = [max(1.0, float(token_count(seg["tts_text"]))) + punctuation_bonus(seg["tts_text"]) for seg in chunk_segments]
    word_counts = allocate_word_counts(weights, len(recognized_words))
    if word_counts is None:
        return []

    aligned: list[dict[str, Any]] = []
    cursor = 0
    for seg, count in zip(chunk_segments, word_counts, strict=False):
        if count > 0 and cursor + count <= len(recognized_words):
            slice_words = recognized_words[cursor : cursor + count]
            local_start = float(slice_words[0]["start"])
            local_end = float(slice_words[-1]["end"])
            cursor += count
        else:
            local_start = 0.0
            local_end = 0.0
        aligned.append(
            {
                "segment_id": int(seg["segment_id"]),
                "chunk_index": int(chunk.get("chunk_index", 0) or 0),
                "source_start_sec": round(float(seg["start_sec"]), 3),
                "source_end_sec": round(float(seg["end_sec"]), 3),
                "tts_start_sec": round(chunk_start + local_start, 3),
                "tts_end_sec": round(chunk_start + max(local_start, local_end), 3),
                "tts_duration_sec": round(max(0.0, local_end - local_start), 3),
                "alignment_mode": "asr_word_count",
                "confidence": round(chunk_similarity, 4),
                "text": str(seg["text"]),
                "translated_text": str(seg["translated_text"]),
            }
        )
    return aligned


def align_chunk_proportionally(chunk: dict[str, Any], chunk_segments: list[dict[str, Any]], chunk_similarity: float) -> list[dict[str, Any]]:
    chunk_start = float(chunk.get("start_sec", 0.0) or 0.0)
    chunk_end = float(chunk.get("end_sec", chunk_start) or chunk_start)
    chunk_duration = max(0.0, chunk_end - chunk_start)
    weights = [max(1.0, float(token_count(seg["tts_text"]))) + punctuation_bonus(seg["tts_text"]) for seg in chunk_segments]
    total_weight = sum(weights) or float(len(chunk_segments) or 1)
    cursor = chunk_start
    aligned: list[dict[str, Any]] = []
    for idx, (seg, weight) in enumerate(zip(chunk_segments, weights, strict=False), start=1):
        if idx == len(chunk_segments):
            seg_end = chunk_end
        else:
            seg_end = cursor + (chunk_duration * (weight / total_weight))
        aligned.append(
            {
                "segment_id": int(seg["segment_id"]),
                "chunk_index": int(chunk.get("chunk_index", 0) or 0),
                "source_start_sec": round(float(seg["start_sec"]), 3),
                "source_end_sec": round(float(seg["end_sec"]), 3),
                "tts_start_sec": round(cursor, 3),
                "tts_end_sec": round(max(cursor, seg_end), 3),
                "tts_duration_sec": round(max(0.0, seg_end - cursor), 3),
                "alignment_mode": "proportional",
                "confidence": round(min(chunk_similarity, 0.5), 4),
                "text": str(seg["text"]),
                "translated_text": str(seg["translated_text"]),
            }
        )
        cursor = seg_end
    return aligned


def main() -> int:
    args = parse_args()
    transcript_json = Path(args.transcript_json).resolve()
    tts_manifest_json = Path(args.tts_manifest_json).resolve()
    out_json = Path(args.out_json).resolve()
    out_csv = Path(args.out_csv).resolve()

    if not transcript_json.exists():
        raise FileNotFoundError(transcript_json)
    if not tts_manifest_json.exists():
        raise FileNotFoundError(tts_manifest_json)

    transcript_payload = load_json(transcript_json)
    tts_payload = load_json(tts_manifest_json)
    source_segments = transcript_payload.get("segments") if isinstance(transcript_payload, dict) else None
    chunks = tts_payload.get("chunks") if isinstance(tts_payload, dict) else None
    if not isinstance(source_segments, list):
        raise RuntimeError("Transcript JSON must contain a 'segments' array.")
    if not isinstance(chunks, list):
        raise RuntimeError("TTS manifest JSON must contain a 'chunks' array.")

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    segment_by_id: dict[int, dict[str, Any]] = {}
    for seg in source_segments:
        segment_id = int(seg.get("segment_id", 0) or 0)
        if segment_id <= 0:
            continue
        segment_by_id[segment_id] = {
            "segment_id": segment_id,
            "start_sec": float(seg.get("start_sec", 0.0) or 0.0),
            "end_sec": float(seg.get("end_sec", 0.0) or 0.0),
            "text": str(seg.get("text", "") or "").strip(),
            "translated_text": str(seg.get("translated_text") or seg.get("text") or "").strip(),
            "tts_text": str(seg.get("translated_text") or seg.get("text") or "").strip(),
        }

    audio_dir = tts_manifest_json.parent / "audio"
    full_audio_name = str(tts_payload.get("full_audio_file", "") or "").strip()
    full_audio_path = (audio_dir / full_audio_name).resolve() if full_audio_name else None
    whisper_model = load_whisper_model(str(args.model), str(args.device), str(args.compute_type))

    aligned_segments: list[dict[str, Any]] = []
    chunk_results: list[dict[str, Any]] = []
    aligned_words: list[dict[str, Any]] = []

    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        chunk_index = int(chunk.get("chunk_index", 0) or 0)
        audio_file = str(chunk.get("audio_file", "") or "").strip()
        audio_path = audio_dir / audio_file
        segment_ids = [int(seg_id) for seg_id in (chunk.get("segment_ids") or []) if int(seg_id or 0) > 0]
        chunk_segments = [segment_by_id[seg_id] for seg_id in segment_ids if seg_id in segment_by_id]
        if not chunk_segments:
            continue
        print(f"@@STEP DETAIL tts-alignment chunk_{chunk_index:03d}", flush=True)
        words: list[dict[str, Any]] = []
        asr_text = ""
        if audio_path.exists():
            try:
                words, asr_text = transcribe_words(whisper_model, audio_path, str(args.language), int(args.beam_size))
            except Exception as exc:  # noqa: BLE001
                print(f"[TTSAlign] WARN chunk {chunk_index}: ASR failed, falling back to proportional alignment: {exc}", flush=True)
                words, asr_text = [], ""

        chunk_start_sec = float(chunk.get("start_sec", 0.0) or 0.0)
        for word in words:
            aligned_words.append(
                {
                    "chunk_index": chunk_index,
                    "text": str(word.get("text", "") or ""),
                    "normalized": str(word.get("normalized", "") or ""),
                    "start_sec": round(chunk_start_sec + float(word.get("start", 0.0) or 0.0), 3),
                    "end_sec": round(chunk_start_sec + float(word.get("end", 0.0) or 0.0), 3),
                }
            )

        expected_text = clean_text(str(chunk.get("tts_text", "") or ""))
        chunk_similarity = (
            SequenceMatcher(None, normalize_text(expected_text), normalize_text(asr_text)).ratio()
            if expected_text and asr_text
            else 0.0
        )

        if words and chunk_similarity >= float(args.min_word_similarity):
            aligned_chunk = align_chunk_with_words(chunk, chunk_segments, words, chunk_similarity)
            if not aligned_chunk:
                aligned_chunk = align_chunk_proportionally(chunk, chunk_segments, chunk_similarity)
        else:
            aligned_chunk = align_chunk_proportionally(chunk, chunk_segments, chunk_similarity)

        aligned_segments.extend(aligned_chunk)
        chunk_results.append(
            {
                "chunk_index": chunk_index,
                "audio_file": audio_file,
                "segment_ids": segment_ids,
                "duration_sec": round(float(chunk.get("duration_sec", 0.0) or 0.0), 3),
                "asr_text": asr_text,
                "similarity": round(chunk_similarity, 4),
                "word_count": len(words),
            }
        )
        print(
            f"[TTSAlign] Chunk {chunk_index:03d}: mode={aligned_chunk[0]['alignment_mode'] if aligned_chunk else 'none'} "
            f"similarity={chunk_similarity:.3f} words={len(words)}",
            flush=True,
        )

    aligned_segments.sort(key=lambda item: item["segment_id"])
    payload = {
        "source_json": str(transcript_json),
        "tts_manifest_json": str(tts_manifest_json),
        "full_audio_file": full_audio_name,
        "full_audio_path": str(full_audio_path) if full_audio_path else "",
        "model": str(args.model),
        "device": str(args.device),
        "compute_type": str(args.compute_type),
        "language": str(args.language),
        "segment_count": len(source_segments),
        "aligned_segment_count": len(aligned_segments),
        "chunks": chunk_results,
        "segments": aligned_segments,
        "words": aligned_words,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_csv, aligned_segments)

    print(f"[TTSAlign] Segments aligned: {len(aligned_segments)}", flush=True)
    print(f"[TTSAlign] Full audio: {full_audio_path}", flush=True)
    print(f"[TTSAlign] Output JSON: {out_json}", flush=True)
    print(f"[TTSAlign] Output CSV: {out_csv}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
