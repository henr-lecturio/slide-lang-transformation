#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import cv2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a narrated slide video from final slide images and optional TTS audio.")
    parser.add_argument("--slide-map-json", required=True, help="Input slide text map JSON (translated or original).")
    parser.add_argument("--image-dir", required=True, help="Directory with final slide images to render.")
    parser.add_argument("--tts-manifest-json", default="", help="Optional TTS manifest JSON path.")
    parser.add_argument("--out-video", required=True, help="Output MP4 path.")
    parser.add_argument("--out-timeline-json", required=True, help="Output timeline JSON path.")
    parser.add_argument("--out-timeline-csv", required=True, help="Output timeline CSV path.")
    parser.add_argument("--out-srt", default="", help="Optional output subtitle path.")
    parser.add_argument("--min-slide-sec", type=float, default=1.2, help="Minimum per-slide duration in seconds.")
    parser.add_argument("--tail-pad-sec", type=float, default=0.35, help="Silence tail added after each voiced slide.")
    parser.add_argument("--width", type=int, default=1920, help="Output video width.")
    parser.add_argument("--height", type=int, default=1080, help="Output video height.")
    parser.add_argument("--fps", type=int, default=30, help="Output video frame rate.")
    parser.add_argument("--bg-color", default="white", help="Background color for padded slides.")
    return parser.parse_args()


def ffmpeg_exists() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is not installed or not in PATH.")


def run_cmd(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_tts_map(path: Path | None) -> tuple[dict[int, dict[str, Any]], Path | None]:
    if path is None or not path.exists():
        return {}, None
    payload = load_json(path)
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {}, None
    base_dir = path.parent / "audio"
    out: dict[int, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        event_id = int(item.get("event_id", 0) or 0)
        if event_id <= 0:
            continue
        out[event_id] = item
    return out, base_dir


def seconds_to_srt(value: float) -> str:
    total_ms = int(round(max(0.0, value) * 1000.0))
    hours = total_ms // 3_600_000
    total_ms %= 3_600_000
    minutes = total_ms // 60_000
    total_ms %= 60_000
    seconds = total_ms // 1_000
    millis = total_ms % 1_000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def find_image(image_dir: Path, slide_index: int, event_id: int) -> Path:
    patterns = [
        f"slide_{slide_index:03d}_event_{event_id:03d}_*.png",
        f"*event_{event_id:03d}_*.png",
    ]
    for pattern in patterns:
        matches = sorted(image_dir.glob(pattern))
        if matches:
            return matches[0]
    raise FileNotFoundError(f"No image found for slide_index={slide_index}, event_id={event_id} in {image_dir}")


def image_size(path: Path) -> tuple[int, int]:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise RuntimeError(f"Failed to read image: {path}")
    h, w = image.shape[:2]
    return w, h


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "slide_index",
        "event_id",
        "bucket_id",
        "start_sec",
        "end_sec",
        "duration_sec",
        "image_name",
        "audio_name",
        "tts_duration_sec",
        "text",
        "translated_text",
        "subtitle_text",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    ffmpeg_exists()

    slide_map_json = Path(args.slide_map_json).resolve()
    image_dir = Path(args.image_dir).resolve()
    tts_manifest_json = Path(args.tts_manifest_json).resolve() if args.tts_manifest_json else None
    out_video = Path(args.out_video).resolve()
    out_timeline_json = Path(args.out_timeline_json).resolve()
    out_timeline_csv = Path(args.out_timeline_csv).resolve()
    out_srt = Path(args.out_srt).resolve() if args.out_srt else None

    if not slide_map_json.exists():
        raise FileNotFoundError(slide_map_json)
    if not image_dir.exists():
        raise FileNotFoundError(image_dir)
    if args.width <= 0 or args.height <= 0:
        raise RuntimeError("--width and --height must be > 0")
    if args.fps <= 0:
        raise RuntimeError("--fps must be > 0")

    out_video.parent.mkdir(parents=True, exist_ok=True)
    out_timeline_json.parent.mkdir(parents=True, exist_ok=True)
    out_timeline_csv.parent.mkdir(parents=True, exist_ok=True)
    if out_srt is not None:
        out_srt.parent.mkdir(parents=True, exist_ok=True)

    payload = load_json(slide_map_json)
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        raise RuntimeError("slide map JSON must contain an 'events' array")

    tts_by_event, tts_audio_base_dir = load_tts_map(tts_manifest_json)
    width = int(args.width)
    height = int(args.height)
    fps = int(args.fps)
    min_slide_sec = max(0.1, float(args.min_slide_sec))
    tail_pad_sec = max(0.0, float(args.tail_pad_sec))

    timeline_rows: list[dict[str, Any]] = []
    srt_entries: list[str] = []
    current_start = 0.0

    with tempfile.TemporaryDirectory(prefix="slide_export_", dir=str(out_video.parent)) as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        concat_list = tmp_dir / "concat.txt"
        concat_lines: list[str] = []

        for idx, event in enumerate(events, start=1):
            event_id = int(event.get("event_id", 0) or 0)
            bucket_id = str(event.get("bucket_id", "") or "")
            translated_text = str(event.get("translated_text", "") or "").strip()
            original_text = str(event.get("text", "") or "").strip()
            subtitle_text = translated_text or original_text
            image_path = find_image(image_dir, idx, event_id)
            audio_item = tts_by_event.get(event_id, {})
            audio_name = str(audio_item.get("audio_file", "") or "")
            tts_duration = float(audio_item.get("duration_sec", 0.0) or 0.0)
            clip_duration = max(min_slide_sec, tts_duration + tail_pad_sec if tts_duration > 0 else min_slide_sec)
            start_sec = current_start
            end_sec = current_start + clip_duration
            current_start = end_sec

            segment_video = tmp_dir / f"segment_video_{idx:03d}.mp4"
            segment_audio = tmp_dir / f"segment_audio_{idx:03d}.m4a"
            segment_out = tmp_dir / f"segment_{idx:03d}.mp4"

            video_filter = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={args.bg_color},"
                "format=yuv420p"
            )
            run_cmd(
                [
                    "ffmpeg",
                    "-y",
                    "-loop",
                    "1",
                    "-i",
                    str(image_path),
                    "-t",
                    f"{clip_duration:.3f}",
                    "-vf",
                    video_filter,
                    "-r",
                    str(fps),
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "18",
                    str(segment_video),
                ]
            )

            if audio_name and tts_audio_base_dir is not None and (tts_audio_base_dir / audio_name).exists() and tts_duration > 0:
                run_cmd(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(tts_audio_base_dir / audio_name),
                        "-af",
                        "apad",
                        "-t",
                        f"{clip_duration:.3f}",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "192k",
                        str(segment_audio),
                    ]
                )
            else:
                run_cmd(
                    [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        "anullsrc=r=24000:cl=mono",
                        "-t",
                        f"{clip_duration:.3f}",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "128k",
                        str(segment_audio),
                    ]
                )

            run_cmd(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(segment_video),
                    "-i",
                    str(segment_audio),
                    "-c:v",
                    "copy",
                    "-c:a",
                    "copy",
                    "-shortest",
                    str(segment_out),
                ]
            )
            concat_lines.append(f"file '{segment_out.name}'")

            timeline_rows.append(
                {
                    "slide_index": idx,
                    "event_id": event_id,
                    "bucket_id": bucket_id,
                    "start_sec": round(start_sec, 3),
                    "end_sec": round(end_sec, 3),
                    "duration_sec": round(clip_duration, 3),
                    "image_name": image_path.name,
                    "audio_name": audio_name,
                    "tts_duration_sec": round(tts_duration, 3),
                    "text": original_text,
                    "translated_text": translated_text,
                    "subtitle_text": subtitle_text,
                }
            )

            if subtitle_text:
                srt_entries.append(
                    f"{len(srt_entries) + 1}\n{seconds_to_srt(start_sec)} --> {seconds_to_srt(end_sec)}\n{subtitle_text}\n"
                )
            print(f"@@STEP DETAIL video-export {image_path.name}", flush=True)
            print(f"[VideoExport] Segment {idx:03d}: {image_path.name} ({clip_duration:.3f}s)", flush=True)

        concat_list.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
        run_cmd(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-c",
                "copy",
                str(out_video),
            ]
        )

    timeline_payload = {
        "slide_map_json": str(slide_map_json),
        "image_dir": str(image_dir),
        "tts_manifest_json": str(tts_manifest_json) if tts_manifest_json else "",
        "video_width": width,
        "video_height": height,
        "video_fps": fps,
        "min_slide_sec": min_slide_sec,
        "tail_pad_sec": tail_pad_sec,
        "total_duration_sec": round(current_start, 3),
        "segments": timeline_rows,
    }
    out_timeline_json.write_text(json.dumps(timeline_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_timeline_csv, timeline_rows)
    if out_srt is not None:
        out_srt.write_text("\n".join(srt_entries).rstrip() + "\n", encoding="utf-8")

    print(f"[VideoExport] Segments: {len(timeline_rows)}", flush=True)
    print(f"[VideoExport] Duration: {current_start:.3f}s", flush=True)
    print(f"[VideoExport] Image dir: {image_dir}", flush=True)
    print(f"[VideoExport] Output video: {out_video}", flush=True)
    print(f"[VideoExport] Timeline JSON: {out_timeline_json}", flush=True)
    print(f"[VideoExport] Timeline CSV: {out_timeline_csv}", flush=True)
    if out_srt is not None:
        print(f"[VideoExport] Subtitle file: {out_srt}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
