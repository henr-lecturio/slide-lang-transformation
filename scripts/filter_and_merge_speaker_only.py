#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from pathlib import Path

import cv2
import numpy as np


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


def parse_source_segment_ids(value) -> list[int]:
    if isinstance(value, list):
        out: list[int] = []
        for x in value:
            try:
                out.append(int(x))
            except Exception:  # noqa: BLE001
                continue
        return sorted(set(out))
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    parts = [p.strip() for p in text.replace(",", ";").split(";")]
    out = []
    for p in parts:
        if not p:
            continue
        try:
            out.append(int(p))
        except Exception:  # noqa: BLE001
            continue
    return sorted(set(out))


def parse_event_row(row: dict) -> dict:
    event_id = int(row.get("event_id", 0))
    is_no_slide_raw = row.get("is_no_slide", False)
    is_no_slide = str(is_no_slide_raw).strip().lower() in {"1", "true", "yes"}
    merge_target = row.get("merge_target_event_id")
    merge_target_event_id = None
    if merge_target not in (None, "", "None"):
        try:
            merge_target_event_id = int(merge_target)
        except Exception:  # noqa: BLE001
            merge_target_event_id = None

    return {
        "event_id": event_id,
        "bucket_id": str(row.get("bucket_id", f"event_{event_id:03d}")),
        "slide_start": float(row.get("slide_start", 0.0)),
        "slide_end": float(row.get("slide_end", 0.0)),
        "is_no_slide": is_no_slide,
        "merge_target_event_id": merge_target_event_id,
        "text": str(row.get("text", "")).strip(),
        "segments_count": int(row.get("segments_count", 0)),
        "source_segment_ids": parse_source_segment_ids(row.get("source_segment_ids", [])),
    }


def load_slide_map(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [parse_event_row(row) for row in data.get("events", [])]
    rows.sort(key=lambda x: (x["slide_start"], x["slide_end"], x["bucket_id"]))
    return rows


def find_event_image(image_dir: Path, event_id: int) -> Path | None:
    if event_id <= 0 or not image_dir.exists():
        return None
    candidates = sorted(image_dir.glob(f"event_{event_id:03d}_*.png"))
    return candidates[0] if candidates else None


def frame_interval_for_event(start_sec: float, end_sec: float, fps: float) -> tuple[int, int]:
    start_frame = max(1, int(math.floor(max(0.0, start_sec) * fps)) + 1)
    end_frame = max(start_frame, int(math.ceil(max(start_sec, end_sec) * fps)))
    return start_frame, end_frame


def stage1_video_ratio_for_event(
    start_sec: float,
    end_sec: float,
    fps: float,
    stage1_segments: list[tuple[int, int, int]],
) -> float | None:
    if not stage1_segments:
        return None
    s, e = frame_interval_for_event(start_sec, end_sec, fps)
    total = max(1, e - s + 1)
    video_frames = 0
    for slide_id, f0, f1 in stage1_segments:
        if slide_id >= 0:
            continue
        a = max(s, f0)
        b = min(e, f1)
        if b >= a:
            video_frames += b - a + 1
    return float(video_frames) / float(total)


def image_metrics(image_path: Path | None) -> dict:
    if image_path is None or not image_path.exists():
        return {
            "edge_density": None,
            "laplacian_var": None,
            "has_image": False,
        }
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None or img.size == 0:
        return {
            "edge_density": None,
            "laplacian_var": None,
            "has_image": False,
        }
    edges = cv2.Canny(img, 80, 180)
    edge_density = float(np.mean(edges > 0))
    lap_var = float(cv2.Laplacian(img, cv2.CV_64F).var())
    return {
        "edge_density": edge_density,
        "laplacian_var": lap_var,
        "has_image": True,
    }


def decide_speaker_only(
    duration_sec: float,
    edge_density: float | None,
    laplacian_var: float | None,
    stage1_video_ratio: float | None,
    *,
    min_stage1_video_ratio: float,
    max_edge_density: float,
    max_laplacian_var: float,
    max_duration_sec: float,
) -> tuple[bool, str]:
    edge_ok = edge_density is not None and edge_density <= max_edge_density
    lap_ok = laplacian_var is not None and laplacian_var <= max_laplacian_var
    low_visual = edge_ok and lap_ok

    if stage1_video_ratio is not None and stage1_video_ratio >= min_stage1_video_ratio:
        return True, "stage1_video_ratio"

    # Soft rule: some stage-1 video overlap + weak visual detail.
    if stage1_video_ratio is not None and stage1_video_ratio >= 0.40 and low_visual:
        return True, "stage1_soft_ratio_plus_low_visual"

    # Fallback when no stage-1 information exists.
    if stage1_video_ratio is None and low_visual and duration_sec <= max_duration_sec:
        return True, "no_stage1_low_visual_short"

    return False, "keep"


def format_source_ids(ids: list[int]) -> str:
    return ";".join(str(x) for x in sorted(set(ids)))


def copy_kept_images(
    kept_rows: list[dict],
    src_slide_dir: Path,
    src_full_dir: Path | None,
    dst_slide_dir: Path | None,
    dst_full_dir: Path | None,
) -> None:
    if dst_slide_dir is not None:
        dst_slide_dir.mkdir(parents=True, exist_ok=True)
        for p in dst_slide_dir.glob("*.png"):
            p.unlink()

    if dst_full_dir is not None:
        dst_full_dir.mkdir(parents=True, exist_ok=True)
        for p in dst_full_dir.glob("*.png"):
            p.unlink()

    for idx, row in enumerate(kept_rows, start=1):
        event_id = int(row["event_id"])
        src_slide = find_event_image(src_slide_dir, event_id)
        if src_slide is not None and dst_slide_dir is not None:
            dst_name = f"slide_{idx:03d}_{src_slide.name}"
            shutil.copy2(src_slide, dst_slide_dir / dst_name)

        if src_full_dir is not None and dst_full_dir is not None:
            src_full = find_event_image(src_full_dir, event_id)
            if src_full is not None:
                dst_name = f"slide_{idx:03d}_{src_full.name}"
                shutil.copy2(src_full, dst_full_dir / dst_name)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Filter speaker-only events and merge their transcript text into the previous kept slide."
    )
    parser.add_argument("--video", required=True, help="Input video path.")
    parser.add_argument("--slide-map-json", required=True, help="Path to slide_text_map.json.")
    parser.add_argument("--slide-map-csv", default="", help="Optional raw slide_text_map.csv path.")
    parser.add_argument("--stage1-file", default="", help="Optional stage-1 result file.")
    parser.add_argument("--slide-keyframes-dir", required=True, help="Path to keyframes/slide.")
    parser.add_argument("--full-keyframes-dir", default="", help="Optional path to keyframes/full.")
    parser.add_argument("--out-json", required=True, help="Filtered map JSON output.")
    parser.add_argument("--out-csv", required=True, help="Filtered map CSV output.")
    parser.add_argument("--out-manifest-csv", required=True, help="Per-event decision manifest output.")
    parser.add_argument("--out-final-slide-dir", default="", help="Optional folder with copied kept slide images.")
    parser.add_argument("--out-final-full-dir", default="", help="Optional folder with copied kept full images.")
    parser.add_argument(
        "--speaker-min-stage1-video-ratio",
        type=float,
        default=0.75,
        help="Mark event as speaker-only when stage1 video overlap >= value (default: 0.75).",
    )
    parser.add_argument(
        "--speaker-max-edge-density",
        type=float,
        default=0.011,
        help="Low-visual threshold for edge density (default: 0.011).",
    )
    parser.add_argument(
        "--speaker-max-laplacian-var",
        type=float,
        default=80.0,
        help="Low-visual threshold for Laplacian variance (default: 80).",
    )
    parser.add_argument(
        "--speaker-max-duration-sec",
        type=float,
        default=2.5,
        help="Fallback max duration for speaker-only when no stage1 is available (default: 2.5).",
    )
    args = parser.parse_args()

    video_path = Path(args.video).resolve()
    slide_map_json = Path(args.slide_map_json).resolve()
    slide_map_csv = Path(args.slide_map_csv).resolve() if args.slide_map_csv else None
    stage1_file = Path(args.stage1_file).resolve() if args.stage1_file else None
    slide_keyframes_dir = Path(args.slide_keyframes_dir).resolve()
    full_keyframes_dir = Path(args.full_keyframes_dir).resolve() if args.full_keyframes_dir else None
    out_json = Path(args.out_json).resolve()
    out_csv = Path(args.out_csv).resolve()
    out_manifest_csv = Path(args.out_manifest_csv).resolve()
    out_final_slide_dir = Path(args.out_final_slide_dir).resolve() if args.out_final_slide_dir else None
    out_final_full_dir = Path(args.out_final_full_dir).resolve() if args.out_final_full_dir else None

    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if not slide_map_json.exists():
        raise FileNotFoundError(slide_map_json)
    if not slide_keyframes_dir.exists():
        raise FileNotFoundError(slide_keyframes_dir)
    if stage1_file is not None and not stage1_file.exists():
        stage1_file = None
    if full_keyframes_dir is not None and not full_keyframes_dir.exists():
        full_keyframes_dir = None

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_manifest_csv.parent.mkdir(parents=True, exist_ok=True)

    rows = load_slide_map(slide_map_json)
    if slide_map_csv is not None and slide_map_csv.exists():
        # Raw CSV is optional; JSON is the source of truth.
        pass

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
    cap.release()

    stage1_segments: list[tuple[int, int, int]] = []
    if stage1_file is not None:
        stage1_segments = read_stage1_segments(stage1_file)

    manifest_rows: list[dict] = []
    kept_rows: list[dict] = []
    leading_no_slide_parts: list[str] = []
    leading_no_slide_ids: set[int] = set()

    for row in rows:
        event_id = int(row["event_id"])
        is_no_slide = bool(row["is_no_slide"])
        duration_sec = max(0.0, float(row["slide_end"]) - float(row["slide_start"]))
        image_path = find_event_image(slide_keyframes_dir, event_id)
        metrics = image_metrics(image_path)
        stage1_ratio = stage1_video_ratio_for_event(
            float(row["slide_start"]),
            float(row["slide_end"]),
            fps,
            stage1_segments,
        )

        is_speaker_only = False
        reason = "keep"
        if not is_no_slide and event_id > 0:
            is_speaker_only, reason = decide_speaker_only(
                duration_sec,
                metrics["edge_density"],
                metrics["laplacian_var"],
                stage1_ratio,
                min_stage1_video_ratio=max(0.0, float(args.speaker_min_stage1_video_ratio)),
                max_edge_density=max(0.0, float(args.speaker_max_edge_density)),
                max_laplacian_var=max(0.0, float(args.speaker_max_laplacian_var)),
                max_duration_sec=max(0.0, float(args.speaker_max_duration_sec)),
            )
        elif is_no_slide:
            reason = "no_slide_bucket"

        text = str(row.get("text", "")).strip()
        src_ids = set(parse_source_segment_ids(row.get("source_segment_ids", [])))

        action = "keep"
        merge_target = None
        if is_no_slide or is_speaker_only:
            if kept_rows:
                target = kept_rows[-1]
                target["slide_end"] = max(float(target["slide_end"]), float(row["slide_end"]))
                if text:
                    if target["text"]:
                        target["text"] = f"{target['text']} {text}".strip()
                    else:
                        target["text"] = text
                target["source_segment_ids"] = sorted(set(target["source_segment_ids"]).union(src_ids))
                target["segments_count"] = len(target["source_segment_ids"])
                merge_target = int(target["event_id"])
                action = "merged_to_previous"
            else:
                if text:
                    leading_no_slide_parts.append(text)
                leading_no_slide_ids.update(src_ids)
                action = "leading_no_previous"
        else:
            keep_row = dict(row)
            keep_row["source_segment_ids"] = sorted(src_ids)
            keep_row["segments_count"] = len(keep_row["source_segment_ids"])
            kept_rows.append(keep_row)

        manifest_rows.append(
            {
                "event_id": event_id,
                "bucket_id": row["bucket_id"],
                "slide_start": round(float(row["slide_start"]), 3),
                "slide_end": round(float(row["slide_end"]), 3),
                "duration_sec": round(duration_sec, 3),
                "is_no_slide": str(is_no_slide).lower(),
                "is_speaker_only": str(bool(is_speaker_only)).lower(),
                "decision_reason": reason,
                "action": action,
                "merge_target_event_id": "" if merge_target is None else merge_target,
                "edge_density": "" if metrics["edge_density"] is None else round(float(metrics["edge_density"]), 6),
                "laplacian_var": "" if metrics["laplacian_var"] is None else round(float(metrics["laplacian_var"]), 3),
                "stage1_video_ratio": "" if stage1_ratio is None else round(float(stage1_ratio), 4),
                "text_len": len(text),
            }
        )

    final_rows: list[dict] = []
    if leading_no_slide_parts or leading_no_slide_ids:
        leading_text = " ".join(x for x in leading_no_slide_parts if x).strip()
        ids = sorted(leading_no_slide_ids)
        final_rows.append(
            {
                "event_id": 0,
                "bucket_id": "no_slide_leading",
                "slide_start": 0.0,
                "slide_end": round(float(kept_rows[0]["slide_start"]) if kept_rows else 0.0, 3),
                "is_no_slide": True,
                "merge_target_event_id": None,
                "text": leading_text,
                "segments_count": len(ids),
                "source_segment_ids": ids,
            }
        )

    for row in kept_rows:
        final_rows.append(
            {
                "event_id": int(row["event_id"]),
                "bucket_id": str(row["bucket_id"]),
                "slide_start": round(float(row["slide_start"]), 3),
                "slide_end": round(float(row["slide_end"]), 3),
                "is_no_slide": False,
                "merge_target_event_id": int(row["event_id"]),
                "text": str(row.get("text", "")).strip(),
                "segments_count": int(row.get("segments_count", 0)),
                "source_segment_ids": sorted(parse_source_segment_ids(row.get("source_segment_ids", []))),
            }
        )

    payload = {
        "video_path": str(video_path),
        "source_slide_map_json": str(slide_map_json),
        "stage1_file": str(stage1_file) if stage1_file is not None else None,
        "speaker_filter": {
            "min_stage1_video_ratio": float(args.speaker_min_stage1_video_ratio),
            "max_edge_density": float(args.speaker_max_edge_density),
            "max_laplacian_var": float(args.speaker_max_laplacian_var),
            "max_duration_sec": float(args.speaker_max_duration_sec),
        },
        "original_event_count": len(rows),
        "final_event_count": len(final_rows),
        "kept_slide_event_count": len([r for r in final_rows if int(r["event_id"]) > 0]),
        "removed_event_count": len([r for r in manifest_rows if r["action"] in {"merged_to_previous", "leading_no_previous"}]),
        "events": final_rows,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with out_csv.open("w", encoding="utf-8", newline="") as f:
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
        for row in final_rows:
            writer.writerow(
                {
                    "event_id": row["event_id"],
                    "bucket_id": row["bucket_id"],
                    "slide_start": row["slide_start"],
                    "slide_end": row["slide_end"],
                    "is_no_slide": str(bool(row["is_no_slide"])).lower(),
                    "merge_target_event_id": "" if row["merge_target_event_id"] is None else row["merge_target_event_id"],
                    "text": row["text"],
                    "segments_count": row["segments_count"],
                    "source_segment_ids": format_source_ids(row["source_segment_ids"]),
                }
            )

    with out_manifest_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "event_id",
                "bucket_id",
                "slide_start",
                "slide_end",
                "duration_sec",
                "is_no_slide",
                "is_speaker_only",
                "decision_reason",
                "action",
                "merge_target_event_id",
                "edge_density",
                "laplacian_var",
                "stage1_video_ratio",
                "text_len",
            ],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    copy_kept_images(
        [row for row in final_rows if int(row["event_id"]) > 0],
        slide_keyframes_dir,
        full_keyframes_dir,
        out_final_slide_dir,
        out_final_full_dir,
    )

    print(f"[ASR] Original mapped events: {len(rows)}")
    print(f"[ASR] Final events after filtering: {len(final_rows)}")
    print(f"[ASR] Kept slide events: {len([r for r in final_rows if int(r['event_id']) > 0])}")
    print(f"[ASR] Wrote final slide text map JSON: {out_json}")
    print(f"[ASR] Wrote final slide text map CSV: {out_csv}")
    print(f"[ASR] Wrote filter manifest CSV: {out_manifest_csv}")
    if out_final_slide_dir is not None:
        print(f"[ASR] Wrote kept slide images: {out_final_slide_dir}")
    if out_final_full_dir is not None:
        print(f"[ASR] Wrote kept full images: {out_final_full_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
