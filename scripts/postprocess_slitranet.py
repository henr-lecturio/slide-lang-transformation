#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2


def to_timecode(seconds: float) -> str:
    ms = int(round(max(0.0, seconds) * 1000))
    hh = ms // 3_600_000
    mm = (ms % 3_600_000) // 60_000
    ss = (ms % 60_000) // 1000
    rem = ms % 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d}.{rem:03d}"


def load_roi(roi_path: Path, video_base: str) -> tuple[int, int, int, int]:
    with roi_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Video"].strip() == video_base:
                return (
                    int(row["x0"]),
                    int(row["y0"]),
                    int(row["x1"]),
                    int(row["y1"]),
                )
    raise RuntimeError(f"ROI for video '{video_base}' not found in {roi_path}")


def read_transitions(path: Path) -> list[tuple[int, int, int]]:
    transitions: list[tuple[int, int, int]] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        for row in reader:
            t_no = int(row["Transition No"])
            f0 = int(row["FrameID0"])
            f1 = int(row["FrameID1"])
            transitions.append((t_no, f0, f1))
    return transitions


def read_frame(cap: cv2.VideoCapture, frame_idx_1based: int):
    zero_based = max(0, frame_idx_1based - 1)
    cap.set(cv2.CAP_PROP_POS_FRAMES, zero_based)
    ok, frame = cap.read()
    return frame if ok else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert SliTraNet transition output to CSV + keyframes.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--roi-file", required=True)
    parser.add_argument("--transitions-file", required=True)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--out-full-dir", required=True)
    parser.add_argument("--out-slide-dir", required=True)
    args = parser.parse_args()

    video_path = Path(args.video).resolve()
    roi_file = Path(args.roi_file).resolve()
    transitions_file = Path(args.transitions_file).resolve()
    out_csv = Path(args.out_csv).resolve()
    out_full = Path(args.out_full_dir).resolve()
    out_slide = Path(args.out_slide_dir).resolve()

    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if not roi_file.exists():
        raise FileNotFoundError(roi_file)
    if not transitions_file.exists():
        raise FileNotFoundError(transitions_file)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_full.mkdir(parents=True, exist_ok=True)
    out_slide.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    video_base = video_path.stem
    x0, y0, x1, y1 = load_roi(roi_file, video_base)
    x0 = max(0, min(w - 1, x0))
    y0 = max(0, min(h - 1, y0))
    x1 = max(x0 + 1, min(w, x1))
    y1 = max(y0 + 1, min(h, y1))

    transitions = read_transitions(transitions_file)
    rows: list[dict] = []

    for i, (transition_no, f0, f1) in enumerate(transitions, start=1):
        frame_idx = int(round((f0 + f1) / 2.0))
        sec = (frame_idx - 1) / fps
        frame = read_frame(cap, frame_idx)
        if frame is not None:
            full_path = out_full / f"event_{i:03d}_f{frame_idx:06d}.png"
            slide_path = out_slide / f"event_{i:03d}_f{frame_idx:06d}.png"
            cv2.imwrite(str(full_path), frame)
            cv2.imwrite(str(slide_path), frame[y0:y1, x0:x1])

        rows.append(
            {
                "event_id": i,
                "transition_no": transition_no,
                "frame_id_0": f0,
                "frame_id_1": f1,
                "event_frame": frame_idx,
                "time_sec": round(sec, 3),
                "timecode": to_timecode(sec),
            }
        )

    cap.release()

    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "event_id",
                "transition_no",
                "frame_id_0",
                "frame_id_1",
                "event_frame",
                "time_sec",
                "timecode",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} events to {out_csv}")
    print(f"Full keyframes: {out_full}")
    print(f"Slide keyframes: {out_slide}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
