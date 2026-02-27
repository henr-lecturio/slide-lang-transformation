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


def read_stage1_segments(path: Path) -> list[tuple[int, int, int]]:
    segments: list[tuple[int, int, int]] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        for row in reader:
            slide_id = int(row["Slide No"])
            f0 = int(row["FrameID0"])
            f1 = int(row["FrameID1"])
            segments.append((slide_id, f0, f1))
    return segments


def read_frame(cap: cv2.VideoCapture, frame_idx_1based: int):
    zero_based = max(0, frame_idx_1based - 1)
    cap.set(cv2.CAP_PROP_POS_FRAMES, zero_based)
    ok, frame = cap.read()
    return frame if ok else None


def clear_old_event_images(path: Path) -> None:
    for img in path.glob("event_*.png"):
        if img.is_file():
            img.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert SliTraNet transition output to CSV + keyframes.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--roi-file", required=True)
    parser.add_argument("--transitions-file", required=True)
    parser.add_argument("--stage1-file")
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--out-full-dir", required=True)
    parser.add_argument("--out-slide-dir", required=True)
    parser.add_argument(
        "--settle-frames",
        type=int,
        default=4,
        help="Number of frames after FrameID1 used for keyframe export (default: 4).",
    )
    parser.add_argument(
        "--blend-max-frames",
        type=int,
        default=40,
        help="Max length of a stage-1 video segment treated as blend and skipped to next slide (default: 40).",
    )
    args = parser.parse_args()

    video_path = Path(args.video).resolve()
    roi_file = Path(args.roi_file).resolve()
    transitions_file = Path(args.transitions_file).resolve()
    stage1_file = Path(args.stage1_file).resolve() if args.stage1_file else None
    out_csv = Path(args.out_csv).resolve()
    out_full = Path(args.out_full_dir).resolve()
    out_slide = Path(args.out_slide_dir).resolve()

    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if not roi_file.exists():
        raise FileNotFoundError(roi_file)
    if not transitions_file.exists():
        raise FileNotFoundError(transitions_file)
    if stage1_file is not None and not stage1_file.exists():
        raise FileNotFoundError(stage1_file)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_full.mkdir(parents=True, exist_ok=True)
    out_slide.mkdir(parents=True, exist_ok=True)
    clear_old_event_images(out_full)
    clear_old_event_images(out_slide)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
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
    settle_frames = max(0, int(args.settle_frames))
    blend_max_frames = max(0, int(args.blend_max_frames))
    event_id = 1
    stage1_segments: list[tuple[int, int, int]] = []
    boundary_to_next_seg_idx: dict[tuple[int, int], int] = {}
    last_target_seg_idx: int | None = None

    if stage1_file is not None:
        stage1_segments = read_stage1_segments(stage1_file)
        for idx in range(len(stage1_segments) - 1):
            _, _, prev_f1 = stage1_segments[idx]
            _, next_f0, _ = stage1_segments[idx + 1]
            boundary_to_next_seg_idx[(prev_f1 + 1, next_f0 + 1)] = idx + 1

        for seg_idx, (slide_id, f0, f1) in enumerate(stage1_segments):
            if slide_id < 0:
                continue
            frame_idx = f0 + settle_frames
            frame_idx = max(f0, min(f1, frame_idx))
            if frame_count > 0:
                frame_idx = max(1, min(frame_count, frame_idx))
            else:
                frame_idx = max(1, frame_idx)

            sec = (frame_idx - 1) / fps
            frame = read_frame(cap, frame_idx)
            if frame is not None:
                full_path = out_full / f"event_{event_id:03d}_f{frame_idx:06d}.png"
                slide_path = out_slide / f"event_{event_id:03d}_f{frame_idx:06d}.png"
                cv2.imwrite(str(full_path), frame)
                cv2.imwrite(str(slide_path), frame[y0:y1, x0:x1])

            rows.append(
                {
                    "event_id": event_id,
                    "transition_no": 0,
                    "frame_id_0": f0,
                    "frame_id_1": f1,
                    "event_frame": frame_idx,
                    "time_sec": round(sec, 3),
                    "timecode": to_timecode(sec),
                }
            )
            event_id += 1
            last_target_seg_idx = seg_idx
            break

    for transition_no, f0, f1 in transitions:
        frame_idx = f1 + settle_frames
        target_seg_idx: int | None = None

        if boundary_to_next_seg_idx:
            mapped_idx = boundary_to_next_seg_idx.get((f0, f1))
            if mapped_idx is not None:
                target_seg_idx = mapped_idx
                slide_id, seg_f0, seg_f1 = stage1_segments[target_seg_idx]
                seg_len = seg_f1 - seg_f0 + 1
                if slide_id < 0 and seg_len <= blend_max_frames and target_seg_idx + 1 < len(stage1_segments):
                    next_slide_id, _, _ = stage1_segments[target_seg_idx + 1]
                    if next_slide_id >= 0:
                        target_seg_idx += 1
                        slide_id, seg_f0, seg_f1 = stage1_segments[target_seg_idx]
                frame_idx = max(seg_f0, min(seg_f1, seg_f0 + settle_frames))

        if target_seg_idx is not None and target_seg_idx == last_target_seg_idx:
            continue

        if frame_count > 0:
            frame_idx = max(1, min(frame_count, frame_idx))
        else:
            frame_idx = max(1, frame_idx)
        sec = (frame_idx - 1) / fps
        frame = read_frame(cap, frame_idx)
        if frame is not None:
            full_path = out_full / f"event_{event_id:03d}_f{frame_idx:06d}.png"
            slide_path = out_slide / f"event_{event_id:03d}_f{frame_idx:06d}.png"
            cv2.imwrite(str(full_path), frame)
            cv2.imwrite(str(slide_path), frame[y0:y1, x0:x1])

        rows.append(
            {
                "event_id": event_id,
                "transition_no": transition_no,
                "frame_id_0": f0,
                "frame_id_1": f1,
                "event_frame": frame_idx,
                "time_sec": round(sec, 3),
                "timecode": to_timecode(sec),
            }
        )
        last_target_seg_idx = target_seg_idx
        event_id += 1

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
