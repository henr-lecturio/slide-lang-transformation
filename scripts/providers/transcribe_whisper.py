#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe a video with faster-whisper and write timestamped segments.")
    parser.add_argument("--video", required=True, help="Input video path.")
    parser.add_argument("--out-json", required=True, help="Output JSON path for transcript segments.")
    parser.add_argument("--out-csv", default="", help="Optional CSV output path for transcript segments.")
    parser.add_argument("--model", default="medium", help="Whisper model name (default: medium).")
    parser.add_argument("--device", default="cuda", help="Whisper device (default: cuda).")
    parser.add_argument("--compute-type", default="float16", help="Whisper compute type (default: float16).")
    parser.add_argument("--language", default="", help="Optional language code, e.g. en, de.")
    parser.add_argument("--beam-size", type=int, default=5, help="Beam size for transcription (default: 5).")
    parser.add_argument(
        "--no-vad-filter",
        action="store_true",
        help="Disable built-in VAD filter (enabled by default).",
    )
    args = parser.parse_args()

    video_path = Path(args.video).resolve()
    out_json = Path(args.out_json).resolve()
    out_csv = Path(args.out_csv).resolve() if args.out_csv else None

    if not video_path.exists():
        raise FileNotFoundError(video_path)

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed in this environment. "
            "Run: source .venv/bin/activate && pip install faster-whisper"
        ) from exc

    out_json.parent.mkdir(parents=True, exist_ok=True)
    if out_csv is not None:
        out_csv.parent.mkdir(parents=True, exist_ok=True)

    print(f"[ASR] Source video: {video_path}", flush=True)
    print(
        f"[ASR] Loading Whisper model '{args.model}' on device={args.device}, compute_type={args.compute_type} ...",
        flush=True,
    )
    model = WhisperModel(
        args.model,
        device=args.device,
        compute_type=args.compute_type,
    )
    print("[ASR] Model loaded.", flush=True)

    transcribe_kwargs: dict = {
        "beam_size": max(1, int(args.beam_size)),
        "vad_filter": not bool(args.no_vad_filter),
    }
    language = args.language.strip()
    if language:
        transcribe_kwargs["language"] = language

    print("[ASR] Starting transcription ...", flush=True)
    segments_iter, info = model.transcribe(str(video_path), **transcribe_kwargs)

    raw_segments: list[dict] = []
    for idx, segment in enumerate(segments_iter, start=1):
        text = clean_text(getattr(segment, "text", ""))
        if not text:
            continue
        start_sec = float(getattr(segment, "start", 0.0) or 0.0)
        end_sec = float(getattr(segment, "end", start_sec) or start_sec)
        if end_sec < start_sec:
            end_sec = start_sec
        raw_segments.append(
            {
                "segment_id": idx,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "text": text,
            }
        )
        if idx % 25 == 0:
            print(f"[ASR] Collected {idx} transcript segments ...", flush=True)

    duration_sec = video_duration_seconds(video_path)
    segments: list[dict] = []
    for row in raw_segments:
        start_sec = max(0.0, float(row["start_sec"]))
        end_sec = max(start_sec, float(row["end_sec"]))
        if duration_sec > 0.0:
            start_sec = min(start_sec, duration_sec)
            end_sec = min(end_sec, duration_sec)
        if (end_sec - start_sec) <= 1e-6:
            continue
        segments.append(
            {
                "segment_id": int(row["segment_id"]),
                "start_sec": round(start_sec, 3),
                "end_sec": round(end_sec, 3),
                "duration_sec": round(end_sec - start_sec, 3),
                "text": str(row["text"]),
            }
        )

    payload = {
        "video_path": str(video_path),
        "video_duration_sec": round(duration_sec, 3),
        "whisper_model": args.model,
        "device": args.device,
        "compute_type": args.compute_type,
        "language": getattr(info, "language", None),
        "language_probability": round(float(getattr(info, "language_probability", 0.0) or 0.0), 6),
        "segment_count": len(segments),
        "segments": segments,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if out_csv is not None:
        write_segments_csv(out_csv, segments)

    print(f"[ASR] Whisper model: {args.model}", flush=True)
    print(f"[ASR] Segments: {len(segments)}", flush=True)
    print(f"[ASR] Wrote transcript JSON: {out_json}", flush=True)
    if out_csv is not None:
        print(f"[ASR] Wrote transcript CSV: {out_csv}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
