#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import cv2


@dataclass
class Bucket:
    bucket_id: str
    event_id: int
    slide_start: float
    slide_end: float
    is_no_slide: bool
    merge_target_event_id: int | None


def load_transcript_segments(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = data.get("segments", [])
    out: list[dict] = []
    for row in segments:
        text = " ".join(str(row.get("text", "")).split())
        if not text:
            continue
        start_sec = float(row.get("start_sec", 0.0))
        end_sec = float(row.get("end_sec", start_sec))
        if end_sec < start_sec:
            end_sec = start_sec
        out.append(
            {
                "segment_id": int(row.get("segment_id", len(out) + 1)),
                "start_sec": start_sec,
                "end_sec": end_sec,
                "text": text,
            }
        )
    out.sort(key=lambda x: (x["start_sec"], x["end_sec"], x["segment_id"]))
    return out


def load_slide_events(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "event_id": int(row["event_id"]),
                    "time_sec": float(row["time_sec"]),
                }
            )
    rows.sort(key=lambda x: (x["time_sec"], x["event_id"]))
    return rows


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


def split_text_by_durations(text: str, durations: list[float]) -> list[str]:
    parts = [""] * len(durations)
    clean = " ".join(text.split())
    if not clean or not durations:
        return parts
    if len(durations) == 1:
        return [clean]

    words = clean.split(" ")
    n_words = len(words)
    n_parts = len(durations)
    if n_words < n_parts:
        best = max(range(n_parts), key=lambda i: durations[i])
        parts[best] = clean
        return parts

    total = sum(max(0.0, d) for d in durations)
    if total <= 0.0:
        parts[0] = clean
        return parts

    start = 0
    cumulative = 0.0
    for idx, duration in enumerate(durations):
        cumulative += max(0.0, duration)
        if idx == n_parts - 1:
            end = n_words
        else:
            end = int(round((cumulative / total) * n_words))
            end = max(start, min(n_words, end))
        parts[idx] = " ".join(words[start:end]).strip()
        start = end
    if start < n_words:
        tail = " ".join(words[start:]).strip()
        if tail:
            if parts[-1]:
                parts[-1] = f"{parts[-1]} {tail}"
            else:
                parts[-1] = tail
    return parts


def build_slide_intervals(slide_events: list[dict], duration_sec: float) -> list[dict]:
    intervals: list[dict] = []
    for idx, event in enumerate(slide_events):
        start = max(0.0, float(event["time_sec"]))
        if duration_sec > 0.0:
            start = min(start, duration_sec)
        if idx < len(slide_events) - 1:
            end = max(start, float(slide_events[idx + 1]["time_sec"]))
        else:
            end = max(start, duration_sec)
        if duration_sec > 0.0:
            end = min(end, duration_sec)
        intervals.append(
            {
                "event_id": int(event["event_id"]),
                "start": start,
                "end": end,
            }
        )
    return intervals


def build_buckets(slide_intervals: list[dict], duration_sec: float, eps: float) -> list[Bucket]:
    buckets: list[Bucket] = []
    cursor = 0.0
    previous_slide_event_id: int | None = None
    no_slide_idx = 1

    for slide in slide_intervals:
        start = max(0.0, float(slide["start"]))
        end = max(start, float(slide["end"]))
        if duration_sec > 0.0:
            start = min(start, duration_sec)
            end = min(end, duration_sec)

        if start > cursor + eps:
            buckets.append(
                Bucket(
                    bucket_id=f"no_slide_{no_slide_idx:03d}",
                    event_id=0,
                    slide_start=cursor,
                    slide_end=start,
                    is_no_slide=True,
                    merge_target_event_id=previous_slide_event_id,
                )
            )
            no_slide_idx += 1

        start = max(start, cursor)
        if end > start + eps:
            event_id = int(slide["event_id"])
            buckets.append(
                Bucket(
                    bucket_id=f"event_{event_id:03d}",
                    event_id=event_id,
                    slide_start=start,
                    slide_end=end,
                    is_no_slide=False,
                    merge_target_event_id=event_id,
                )
            )
            cursor = end
            previous_slide_event_id = event_id
        else:
            cursor = max(cursor, end)

    if duration_sec > cursor + eps:
        buckets.append(
            Bucket(
                bucket_id=f"no_slide_{no_slide_idx:03d}",
                event_id=0,
                slide_start=cursor,
                slide_end=duration_sec,
                is_no_slide=True,
                merge_target_event_id=previous_slide_event_id,
            )
        )

    if not buckets and duration_sec > eps:
        buckets.append(
            Bucket(
                bucket_id="no_slide_001",
                event_id=0,
                slide_start=0.0,
                slide_end=duration_sec,
                is_no_slide=True,
                merge_target_event_id=None,
            )
        )
    return buckets


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "event_id",
                "bucket_id",
                "slide_start",
                "slide_end",
                "is_no_slide",
                "merge_target_event_id",
                "text",
                "segments_count",
                "source_segment_ids",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Map transcript segments to slide time windows.")
    parser.add_argument("--video", required=True, help="Input video path.")
    parser.add_argument("--slide-csv", required=True, help="Path to slide_changes.csv.")
    parser.add_argument("--transcript-json", required=True, help="Path to transcript_segments.json.")
    parser.add_argument("--out-json", required=True, help="Output JSON path.")
    parser.add_argument("--out-csv", required=True, help="Output CSV path.")
    parser.add_argument("--eps", type=float, default=1e-6, help="Overlap epsilon (default: 1e-6).")
    args = parser.parse_args()

    video_path = Path(args.video).resolve()
    slide_csv = Path(args.slide_csv).resolve()
    transcript_json = Path(args.transcript_json).resolve()
    out_json = Path(args.out_json).resolve()
    out_csv = Path(args.out_csv).resolve()
    eps = max(0.0, float(args.eps))

    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if not slide_csv.exists():
        raise FileNotFoundError(slide_csv)
    if not transcript_json.exists():
        raise FileNotFoundError(transcript_json)

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    transcript_segments = load_transcript_segments(transcript_json)
    slide_events = load_slide_events(slide_csv)

    inferred_duration = 0.0
    if transcript_segments:
        inferred_duration = max(inferred_duration, max(s["end_sec"] for s in transcript_segments))
    if slide_events:
        inferred_duration = max(inferred_duration, max(s["time_sec"] for s in slide_events))
    video_duration = video_duration_seconds(video_path)
    duration_sec = max(video_duration, inferred_duration)

    slide_intervals = build_slide_intervals(slide_events, duration_sec)
    buckets = build_buckets(slide_intervals, duration_sec, eps)

    accum = {
        b.bucket_id: {
            "bucket": b,
            "text_parts": [],
            "source_segment_ids": set(),
            "mapped_fragments": 0,
        }
        for b in buckets
    }

    for seg in transcript_segments:
        seg_start = max(0.0, float(seg["start_sec"]))
        seg_end = max(seg_start, float(seg["end_sec"]))
        if duration_sec > 0.0:
            seg_start = min(seg_start, duration_sec)
            seg_end = min(seg_end, duration_sec)
        if seg_end <= seg_start + eps:
            continue

        overlaps: list[tuple[Bucket, float, float, float]] = []
        for bucket in buckets:
            ov_start = max(seg_start, bucket.slide_start)
            ov_end = min(seg_end, bucket.slide_end)
            if ov_end > ov_start + eps:
                overlaps.append((bucket, ov_start, ov_end, ov_end - ov_start))
        if not overlaps:
            continue

        durations = [item[3] for item in overlaps]
        text_chunks = split_text_by_durations(seg["text"], durations)

        for idx, (bucket, _ov_start, _ov_end, _ov_dur) in enumerate(overlaps):
            entry = accum[bucket.bucket_id]
            chunk = text_chunks[idx].strip()
            if chunk:
                entry["text_parts"].append(chunk)
            entry["source_segment_ids"].add(int(seg["segment_id"]))
            entry["mapped_fragments"] += 1

    event_rows: list[dict] = []
    csv_rows: list[dict] = []
    for bucket in buckets:
        entry = accum[bucket.bucket_id]
        source_ids = sorted(entry["source_segment_ids"])
        source_ids_text = ";".join(str(x) for x in source_ids)
        text = " ".join(part for part in entry["text_parts"] if part).strip()

        row = {
            "event_id": bucket.event_id,
            "bucket_id": bucket.bucket_id,
            "slide_start": round(bucket.slide_start, 3),
            "slide_end": round(bucket.slide_end, 3),
            "is_no_slide": bool(bucket.is_no_slide),
            "merge_target_event_id": bucket.merge_target_event_id,
            "text": text,
            "segments_count": len(source_ids),
            "source_segment_ids": source_ids,
            "mapped_fragments": int(entry["mapped_fragments"]),
        }
        event_rows.append(row)
        csv_rows.append(
            {
                "event_id": row["event_id"],
                "bucket_id": row["bucket_id"],
                "slide_start": row["slide_start"],
                "slide_end": row["slide_end"],
                "is_no_slide": str(row["is_no_slide"]).lower(),
                "merge_target_event_id": "" if row["merge_target_event_id"] is None else row["merge_target_event_id"],
                "text": row["text"],
                "segments_count": row["segments_count"],
                "source_segment_ids": source_ids_text,
            }
        )

    payload = {
        "video_path": str(video_path),
        "video_duration_sec": round(duration_sec, 3),
        "transcript_segment_count": len(transcript_segments),
        "slide_event_count": len(slide_events),
        "mapped_event_count": len(event_rows),
        "events": event_rows,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_csv, csv_rows)

    print(f"Video duration: {duration_sec:.3f}s")
    print(f"Slide events: {len(slide_events)}")
    print(f"Transcript segments: {len(transcript_segments)}")
    print(f"Wrote slide text map JSON: {out_json}")
    print(f"Wrote slide text map CSV: {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
