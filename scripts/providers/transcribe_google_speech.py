#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Iterable

import cv2

ROOT_DIR = Path(__file__).resolve().parents[2]
LOCAL_ENV_PATH = ROOT_DIR / ".env.local"


def clean_text(text: str) -> str:
    return " ".join((text or "").split())


def video_duration_seconds(video_path: Path) -> float:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return 0.0
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
    cap.release()
    if fps <= 0.0 or frame_count <= 0.0:
        return 0.0
    return frame_count / fps


def write_segments_csv(path: Path, segments: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["segment_id", "start_sec", "end_sec", "duration_sec", "text"],
        )
        writer.writeheader()
        writer.writerows(segments)


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def ensure_client(location: str):
    try:
        from google.cloud import speech_v2
        from google.cloud.speech_v2.types import cloud_speech
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-cloud-speech is not installed in this environment. "
            "Run: source .venv/bin/activate && pip install google-cloud-speech"
        ) from exc

    client_kwargs = {}
    if location and location != "global":
        client_kwargs["client_options"] = {"api_endpoint": f"{location}-speech.googleapis.com"}
    client = speech_v2.SpeechClient(**client_kwargs)
    return client, cloud_speech


def duration_to_seconds(value) -> float:
    if value is None:
        return 0.0
    seconds = getattr(value, "seconds", 0) or 0
    nanos = getattr(value, "nanos", 0) or 0
    return float(seconds) + float(nanos) / 1_000_000_000.0


def estimate_segment_duration_sec(text: str) -> float:
    cleaned = clean_text(text)
    words = len(cleaned.split())
    chars = len(cleaned)
    words_based = words / 2.8 if words > 0 else 0.0
    chars_based = chars / 16.0 if chars > 0 else 0.0
    return max(0.2, min(12.0, max(words_based, chars_based, 0.35)))


def parse_language_codes(raw: str) -> list[str]:
    items = [part.strip() for part in (raw or "").split(",")]
    items = [item for item in items if item]
    return items or ["en-US"]


def extract_wav(video_path: Path, wav_path: Path, sample_rate: int = 16000) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-sample_fmt",
        "s16",
        str(wav_path),
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed: {result.stdout[-800:]}")


def chunk_wav_bytes(wf: wave.Wave_read, start_frame: int, frame_count: int) -> bytes:
    wf.setpos(start_frame)
    frames = wf.readframes(frame_count)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out_wav:
        out_wav.setnchannels(wf.getnchannels())
        out_wav.setsampwidth(wf.getsampwidth())
        out_wav.setframerate(wf.getframerate())
        out_wav.writeframes(frames)
    return buf.getvalue()


def iter_chunk_ranges(total_frames: int, sample_rate: int, chunk_sec: float, overlap_sec: float) -> Iterable[tuple[int, int]]:
    chunk_frames = max(1, int(round(chunk_sec * sample_rate)))
    overlap_frames = max(0, int(round(overlap_sec * sample_rate)))
    if overlap_frames >= chunk_frames:
        overlap_frames = max(0, chunk_frames - 1)
    step_frames = max(1, chunk_frames - overlap_frames)

    start = 0
    while start < total_frames:
        end = min(total_frames, start + chunk_frames)
        yield start, end
        if end >= total_frames:
            break
        start += step_frames


def classify_google_speech_error(exc: Exception) -> str:
    text = str(exc or "").upper()
    if "SERVICE_DISABLED" in text:
        return "SERVICE_DISABLED"
    if "CLOUD SPEECH-TO-TEXT API HAS NOT BEEN USED" in text and "DISABLED" in text:
        return "SERVICE_DISABLED"
    if "PERMISSION_DENIED" in text or "STATUSCODE.PERMISSION_DENIED" in text:
        return "PERMISSION_DENIED"
    return "UNKNOWN"


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe a video with Google Cloud Speech-to-Text v2.")
    parser.add_argument("--video", required=True, help="Input video path.")
    parser.add_argument("--out-json", required=True, help="Output JSON path for transcript segments.")
    parser.add_argument("--out-csv", default="", help="Optional CSV output path for transcript segments.")
    parser.add_argument("--project-id", required=True, help="Google Cloud project id.")
    parser.add_argument("--location", default="global", help="Speech-to-Text location, e.g. global or us.")
    parser.add_argument("--model", default="chirp_3", help="Speech-to-Text model, default chirp_3.")
    parser.add_argument("--language-codes", default="en-US", help="Comma-separated BCP-47 language codes.")
    parser.add_argument("--chunk-sec", type=float, default=55.0, help="Chunk length in seconds for sync recognize.")
    parser.add_argument("--chunk-overlap-sec", type=float, default=0.75, help="Chunk overlap in seconds.")
    args = parser.parse_args()

    load_local_env(LOCAL_ENV_PATH)

    video_path = Path(args.video).resolve()
    out_json = Path(args.out_json).resolve()
    out_csv = Path(args.out_csv).resolve() if args.out_csv else None
    project_id = str(args.project_id).strip()
    location = str(args.location).strip() or "global"
    model = str(args.model).strip() or "chirp_3"
    language_codes = parse_language_codes(args.language_codes)

    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if not project_id:
        raise RuntimeError("--project-id must not be empty.")
    if args.chunk_sec <= 0:
        raise RuntimeError("--chunk-sec must be > 0")
    if args.chunk_overlap_sec < 0:
        raise RuntimeError("--chunk-overlap-sec must be >= 0")

    out_json.parent.mkdir(parents=True, exist_ok=True)
    if out_csv is not None:
        out_csv.parent.mkdir(parents=True, exist_ok=True)

    client, cloud_speech = ensure_client(location)
    recognizer = f"projects/{project_id}/locations/{location}/recognizers/_"
    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        language_codes=language_codes,
        model=model,
        features=cloud_speech.RecognitionFeatures(enable_automatic_punctuation=True),
    )

    print(f"[ASR] Source video: {video_path}", flush=True)
    print(
        f"[ASR] Using Google Speech-to-Text v2 model='{model}' project='{project_id}' location='{location}' languages={language_codes}",
        flush=True,
    )

    duration_sec = video_duration_seconds(video_path)
    with tempfile.TemporaryDirectory(prefix="google_stt_") as tmp_dir:
        wav_path = Path(tmp_dir) / "audio.wav"
        print("[ASR] Extracting audio track with ffmpeg ...", flush=True)
        extract_wav(video_path, wav_path)

        segments: list[dict] = []
        accepted_end_global = 0.0
        segment_id = 1
        missing_timing_fallback_count = 0

        with wave.open(str(wav_path), "rb") as wf:
            sample_rate = wf.getframerate()
            total_frames = wf.getnframes()
            total_chunks = math.ceil(total_frames / max(1, int(round((args.chunk_sec - min(args.chunk_overlap_sec, args.chunk_sec * 0.9)) * sample_rate))))
            total_chunks = max(1, total_chunks)

            for chunk_index, (start_frame, end_frame) in enumerate(
                iter_chunk_ranges(total_frames, sample_rate, args.chunk_sec, args.chunk_overlap_sec),
                start=1,
            ):
                chunk_start_sec = start_frame / float(sample_rate)
                chunk_duration_sec = (end_frame - start_frame) / float(sample_rate)
                print(
                    f"[ASR] Chunk {chunk_index}/{total_chunks}: start={chunk_start_sec:.2f}s dur={chunk_duration_sec:.2f}s",
                    flush=True,
                )
                audio_bytes = chunk_wav_bytes(wf, start_frame, end_frame - start_frame)
                request = cloud_speech.RecognizeRequest(
                    recognizer=recognizer,
                    config=config,
                    content=audio_bytes,
                )
                response = client.recognize(request=request)

                local_prev_end = 0.0
                nonempty_results: list[tuple[object, str]] = []
                for result in response.results:
                    if not result.alternatives:
                        continue
                    transcript = clean_text(result.alternatives[0].transcript)
                    if not transcript:
                        continue
                    nonempty_results.append((result, transcript))

                result_count = len(nonempty_results)
                for result_index, (result, transcript) in enumerate(nonempty_results, start=1):
                    local_end = duration_to_seconds(getattr(result, "result_end_offset", None))
                    local_start = local_prev_end
                    if local_end <= local_start + 1e-3:
                        remaining_after = result_count - result_index
                        reserve_tail_sec = max(0.0, float(remaining_after) * 0.15)
                        max_allowed_end = max(local_start + 0.15, chunk_duration_sec - reserve_tail_sec)
                        est_duration = estimate_segment_duration_sec(transcript)
                        local_end = min(max_allowed_end, local_start + est_duration)
                        missing_timing_fallback_count += 1
                    local_end = min(chunk_duration_sec, max(local_end, local_start + 0.001))

                    global_end = chunk_start_sec + local_end
                    global_start = chunk_start_sec + local_start
                    local_prev_end = max(local_prev_end, local_end)

                    if global_end <= accepted_end_global + 0.05:
                        continue
                    global_start = max(global_start, accepted_end_global)
                    if duration_sec > 0.0:
                        global_start = min(global_start, duration_sec)
                        global_end = min(global_end, duration_sec)
                    if global_end - global_start <= 1e-3:
                        continue

                    segments.append(
                        {
                            "segment_id": segment_id,
                            "start_sec": round(global_start, 3),
                            "end_sec": round(global_end, 3),
                            "duration_sec": round(global_end - global_start, 3),
                            "text": transcript,
                        }
                    )
                    accepted_end_global = max(accepted_end_global, global_end)
                    segment_id += 1

    payload = {
        "video_path": str(video_path),
        "video_duration_sec": round(duration_sec, 3),
        "provider": "google_speech_v2",
        "model": model,
        "project_id": project_id,
        "location": location,
        "language_codes": language_codes,
        "segment_count": len(segments),
        "timing_fallback_segments": missing_timing_fallback_count,
        "segments": segments,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if out_csv is not None:
        write_segments_csv(out_csv, segments)

    print(f"[ASR] Segments: {len(segments)}", flush=True)
    if missing_timing_fallback_count > 0:
        print(f"[ASR] Timing fallback used for {missing_timing_fallback_count} segments.", flush=True)
    print(f"[ASR] Wrote transcript JSON: {out_json}", flush=True)
    if out_csv is not None:
        print(f"[ASR] Wrote transcript CSV: {out_csv}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        error_code = classify_google_speech_error(exc)
        print(f"[ASR] ERROR_CODE: {error_code}", file=sys.stderr, flush=True)
        if error_code == "SERVICE_DISABLED":
            print(
                "[ASR] ERROR: Cloud Speech-to-Text API is disabled for the configured project. "
                "Enable speech.googleapis.com or use whisper.",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(f"[ASR] ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
