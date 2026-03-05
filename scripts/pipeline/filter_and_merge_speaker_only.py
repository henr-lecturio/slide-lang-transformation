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
        "translated_text": str(row.get("translated_text", "")).strip(),
        "target_language": str(row.get("target_language", "")).strip(),
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


def clamp_roi_to_frame(
    roi: tuple[int, int, int, int],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = roi
    x0 = max(0, min(int(x0), max(0, width - 1)))
    y0 = max(0, min(int(y0), max(0, height - 1)))
    x1 = max(x0 + 1, min(int(x1), width))
    y1 = max(y0 + 1, min(int(y1), height))
    return x0, y0, x1, y1


def sample_event_frame_ids(start_sec: float, end_sec: float, fps: float, count: int) -> list[int]:
    start_frame, end_frame = frame_interval_for_event(start_sec, end_sec, fps)
    if count <= 1 or end_frame <= start_frame:
        return [max(1, int(round((start_frame + end_frame) / 2.0)))]
    frame_ids = [
        max(1, int(round(x)))
        for x in np.linspace(start_frame, end_frame, num=max(1, int(count)), dtype=np.float64)
    ]
    return sorted(set(frame_ids))


def read_video_frame(cap: cv2.VideoCapture, frame_id: int) -> np.ndarray | None:
    if frame_id <= 0:
        return None
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(frame_id) - 1))
    ok, frame = cap.read()
    if not ok or frame is None or frame.size == 0:
        return None
    return frame


def create_person_detector() -> cv2.HOGDescriptor:
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    return hog


def detect_people_boxes(
    frame: np.ndarray,
    hog: cv2.HOGDescriptor,
    *,
    max_width: int = 960,
    hit_threshold: float = 0.0,
) -> list[tuple[int, int, int, int, float]]:
    h, w = frame.shape[:2]
    scale = 1.0
    resized = frame
    if w > max_width:
        scale = float(max_width) / float(w)
        new_h = max(1, int(round(h * scale)))
        resized = cv2.resize(frame, (max_width, new_h), interpolation=cv2.INTER_AREA)

    boxes, weights = hog.detectMultiScale(
        resized,
        hitThreshold=float(hit_threshold),
        winStride=(8, 8),
        padding=(8, 8),
        scale=1.05,
    )
    results: list[tuple[int, int, int, int, float]] = []
    inv_scale = 1.0 / scale
    for (x, y, bw, bh), weight in zip(boxes, weights):
        score = float(weight[0] if isinstance(weight, np.ndarray) else weight)
        results.append(
            (
                int(round(x * inv_scale)),
                int(round(y * inv_scale)),
                int(round(bw * inv_scale)),
                int(round(bh * inv_scale)),
                score,
            )
        )
    return results


def rect_intersection_area(
    ax: int,
    ay: int,
    aw: int,
    ah: int,
    bx: int,
    by: int,
    bw: int,
    bh: int,
) -> int:
    x0 = max(ax, bx)
    y0 = max(ay, by)
    x1 = min(ax + aw, bx + bw)
    y1 = min(ay + ah, by + bh)
    if x1 <= x0 or y1 <= y0:
        return 0
    return max(0, x1 - x0) * max(0, y1 - y0)


def detect_person_outside_roi(
    frames: list[np.ndarray],
    roi: tuple[int, int, int, int],
    hog: cv2.HOGDescriptor,
    *,
    hit_threshold: float = 0.0,
    min_box_area_ratio: float = 0.02,
    min_outside_ratio: float = 0.35,
) -> dict:
    detected_frames = 0
    max_weight = 0.0
    sample_frames = 0

    for frame in frames:
        if frame is None or frame.size == 0:
            continue
        sample_frames += 1
        h, w = frame.shape[:2]
        x0, y0, x1, y1 = clamp_roi_to_frame(roi, w, h)
        roi_w = max(1, x1 - x0)
        roi_h = max(1, y1 - y0)
        frame_area = float(max(1, w * h))
        found = False

        for bx, by, bw, bh, weight in detect_people_boxes(frame, hog, hit_threshold=hit_threshold):
            if bw <= 0 or bh <= 0:
                continue
            area = float(bw * bh)
            if area < frame_area * max(0.0, float(min_box_area_ratio)):
                continue
            inside_area = rect_intersection_area(bx, by, bw, bh, x0, y0, roi_w, roi_h)
            outside_ratio = 1.0 - (float(inside_area) / area)
            if outside_ratio < max(0.0, float(min_outside_ratio)):
                continue
            max_weight = max(max_weight, float(weight))
            found = True

        if found:
            detected_frames += 1

    return {
        "person_present": detected_frames > 0,
        "person_detected_frames": detected_frames,
        "sample_frames": sample_frames,
        "person_max_weight": round(max_weight, 3),
    }


def _extract_side_strips(
    frame: np.ndarray,
    roi: tuple[int, int, int, int],
    strip_px: int,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = clamp_roi_to_frame(roi, w, h)
    strip = max(2, int(strip_px))
    pairs: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    if x0 - strip >= 0:
        pairs["left"] = (
            frame[y0:y1, x0 : min(x1, x0 + strip)],
            frame[y0:y1, x0 - strip : x0],
        )
    if x1 + strip <= w:
        pairs["right"] = (
            frame[y0:y1, max(x0, x1 - strip) : x1],
            frame[y0:y1, x1 : x1 + strip],
        )
    if y0 - strip >= 0:
        pairs["top"] = (
            frame[y0 : min(y1, y0 + strip), x0:x1],
            frame[y0 - strip : y0, x0:x1],
        )
    if y1 + strip <= h:
        pairs["bottom"] = (
            frame[max(y0, y1 - strip) : y1, x0:x1],
            frame[y1 : y1 + strip, x0:x1],
        )
    return pairs


def _side_strip_diff(inside: np.ndarray, outside: np.ndarray, side: str) -> float | None:
    if inside.size == 0 or outside.size == 0:
        return None
    target = (16, 96) if side in {"left", "right"} else (96, 16)
    inside_small = cv2.resize(cv2.GaussianBlur(inside, (7, 7), 0), target, interpolation=cv2.INTER_AREA)
    outside_small = cv2.resize(cv2.GaussianBlur(outside, (7, 7), 0), target, interpolation=cv2.INTER_AREA)
    inside_lab = cv2.cvtColor(inside_small, cv2.COLOR_BGR2Lab).astype(np.float32)
    outside_lab = cv2.cvtColor(outside_small, cv2.COLOR_BGR2Lab).astype(np.float32)
    return float(np.mean(np.abs(inside_lab - outside_lab)))


def analyze_border_continuity(
    frames: list[np.ndarray],
    roi: tuple[int, int, int, int],
    *,
    strip_px: int,
    diff_threshold: float,
    min_matched_sides: int,
) -> dict:
    per_frame_counts: list[int] = []
    matched_frame_count = 0
    side_diffs_by_name: dict[str, list[float]] = {name: [] for name in ("left", "right", "top", "bottom")}

    for frame in frames:
        if frame is None or frame.size == 0:
            continue
        matched = 0
        side_pairs = _extract_side_strips(frame, roi, strip_px)
        for side, (inside, outside) in side_pairs.items():
            diff = _side_strip_diff(inside, outside, side)
            if diff is None:
                continue
            side_diffs_by_name[side].append(diff)
            if diff <= float(diff_threshold):
                matched += 1
        per_frame_counts.append(matched)
        if matched >= max(1, int(min_matched_sides)):
            matched_frame_count += 1

    if not per_frame_counts:
        return {
            "slide_extension_detected": False,
            "sample_frames": 0,
            "matched_frame_count": 0,
            "median_matched_sides": 0,
            "side_diff_left": "",
            "side_diff_right": "",
            "side_diff_top": "",
            "side_diff_bottom": "",
        }

    median_matched_sides = int(round(float(np.median(per_frame_counts))))
    sample_frames = len(per_frame_counts)
    slide_extension_detected = matched_frame_count >= max(1, int(math.ceil(sample_frames / 2.0)))
    return {
        "slide_extension_detected": slide_extension_detected,
        "sample_frames": sample_frames,
        "matched_frame_count": matched_frame_count,
        "median_matched_sides": median_matched_sides,
        "side_diff_left": round(float(np.median(side_diffs_by_name["left"])), 3) if side_diffs_by_name["left"] else "",
        "side_diff_right": round(float(np.median(side_diffs_by_name["right"])), 3) if side_diffs_by_name["right"] else "",
        "side_diff_top": round(float(np.median(side_diffs_by_name["top"])), 3) if side_diffs_by_name["top"] else "",
        "side_diff_bottom": round(float(np.median(side_diffs_by_name["bottom"])), 3) if side_diffs_by_name["bottom"] else "",
    }


def load_sample_frames_for_event(
    cap: cv2.VideoCapture,
    row: dict,
    fps: float,
    *,
    sample_frames: int,
    fallback_full_image: Path | None,
) -> list[np.ndarray]:
    frames: list[np.ndarray] = []
    for frame_id in sample_event_frame_ids(float(row["slide_start"]), float(row["slide_end"]), fps, sample_frames):
        frame = read_video_frame(cap, frame_id)
        if frame is not None:
            frames.append(frame)

    if not frames and fallback_full_image is not None and fallback_full_image.exists():
        fallback = cv2.imread(str(fallback_full_image), cv2.IMREAD_COLOR)
        if fallback is not None and fallback.size > 0:
            frames.append(fallback)
    return frames


def detect_final_source_modes(
    kept_rows: list[dict],
    *,
    video_path: Path,
    fps: float,
    full_keyframes_dir: Path | None,
    roi: tuple[int, int, int, int],
    final_source_mode_auto: str,
    fullslide_sample_frames: int,
    fullslide_border_strip_px: int,
    fullslide_min_matched_sides: int,
    fullslide_border_diff_threshold: float,
    fullslide_person_box_area_ratio: float,
    fullslide_person_outside_ratio: float,
) -> list[dict]:
    source_rows: list[dict] = []
    if not kept_rows:
        return source_rows

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Failed to open video for final source detection: {video_path}")

    hog = create_person_detector()
    try:
        for slide_index, row in enumerate(kept_rows, start=1):
            event_id = int(row["event_id"])
            src_full = find_event_image(full_keyframes_dir, event_id) if full_keyframes_dir is not None else None
            info = {
                "slide_index": slide_index,
                "event_id": event_id,
                "source_mode_auto": "slide",
                "source_mode_final": "slide",
                "source_reason": "auto_disabled",
                "source_confidence": 0.0,
                "sample_frames": 0,
                "person_detected_frames": 0,
                "person_present": False,
                "person_max_weight": "",
                "matched_frame_count": 0,
                "median_matched_sides": 0,
                "side_diff_left": "",
                "side_diff_right": "",
                "side_diff_top": "",
                "side_diff_bottom": "",
            }

            if final_source_mode_auto != "auto":
                source_rows.append(info)
                continue
            if src_full is None or not src_full.exists():
                info["source_reason"] = "no_full_image"
                source_rows.append(info)
                continue

            frames = load_sample_frames_for_event(
                cap,
                row,
                fps,
                sample_frames=max(1, int(fullslide_sample_frames)),
                fallback_full_image=src_full,
            )
            if not frames:
                info["source_reason"] = "no_sample_frames"
                source_rows.append(info)
                continue

            height, width = frames[0].shape[:2]
            frame_roi = clamp_roi_to_frame(roi, width, height)
            person = detect_person_outside_roi(
                frames,
                frame_roi,
                hog,
                min_box_area_ratio=max(0.0, float(fullslide_person_box_area_ratio)),
                min_outside_ratio=max(0.0, float(fullslide_person_outside_ratio)),
            )
            border = analyze_border_continuity(
                frames,
                frame_roi,
                strip_px=max(2, int(fullslide_border_strip_px)),
                diff_threshold=max(0.0, float(fullslide_border_diff_threshold)),
                min_matched_sides=max(1, int(fullslide_min_matched_sides)),
            )

            info.update(
                {
                    "sample_frames": max(int(person["sample_frames"]), int(border["sample_frames"])),
                    "person_detected_frames": int(person["person_detected_frames"]),
                    "person_present": bool(person["person_present"]),
                    "person_max_weight": person["person_max_weight"],
                    "matched_frame_count": int(border["matched_frame_count"]),
                    "median_matched_sides": int(border["median_matched_sides"]),
                    "side_diff_left": border["side_diff_left"],
                    "side_diff_right": border["side_diff_right"],
                    "side_diff_top": border["side_diff_top"],
                    "side_diff_bottom": border["side_diff_bottom"],
                }
            )

            if (not person["person_present"]) and border["slide_extension_detected"]:
                info["source_mode_auto"] = "full"
                info["source_mode_final"] = "full"
                info["source_reason"] = "person_absent_and_border_match"
                conf = 0.55 + (0.1 * min(4, int(border["median_matched_sides"])))
                info["source_confidence"] = round(min(0.99, conf), 3)
            elif person["person_present"]:
                info["source_reason"] = "person_detected_outside_roi"
                info["source_confidence"] = round(min(0.99, 0.4 + (0.1 * int(person["person_detected_frames"]))), 3)
            elif not border["slide_extension_detected"]:
                info["source_reason"] = "border_match_insufficient"
                info["source_confidence"] = round(
                    max(0.0, min(0.95, 0.2 + (0.08 * int(border["median_matched_sides"])))),
                    3,
                )
            else:
                info["source_reason"] = "default_slide"

            source_rows.append(info)
    finally:
        cap.release()

    return source_rows


def estimate_slide_background_color(
    patch: np.ndarray,
    *,
    sat_threshold: int = 42,
    grad_threshold: float = 20.0,
) -> np.ndarray:
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = cv2.magnitude(grad_x, grad_y)

    bg_seed = (hsv[:, :, 1] <= sat_threshold) & (grad <= grad_threshold)
    if int(np.count_nonzero(bg_seed)) < 128:
        bg_seed = hsv[:, :, 1] <= max(55, sat_threshold + 10)
    if int(np.count_nonzero(bg_seed)) < 128:
        bg_seed = np.ones(patch.shape[:2], dtype=bool)

    pixels = patch[bg_seed]
    if pixels.size == 0:
        pixels = patch.reshape(-1, 3)
    return np.median(pixels.reshape(-1, 3), axis=0).astype(np.uint8)


def find_dynamic_corner_top(
    patch: np.ndarray,
    background_color: np.ndarray,
    default_zone_y0: int,
    *,
    edge_strip_ratio: float = 0.035,
    scan_top_ratio: float = 0.28,
    diff_threshold: float = 18.0,
    sat_threshold: int = 58,
    grad_threshold: float = 18.0,
    min_run_rows: int = 6,
    top_margin_rows: int = 22,
) -> int:
    h, w = patch.shape[:2]
    edge_w = max(6, int(round(w * edge_strip_ratio)))
    strip = patch[:, w - edge_w :]
    hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = cv2.magnitude(grad_x, grad_y)
    diff = np.max(
        np.abs(strip.astype(np.int16) - background_color.reshape(1, 1, 3).astype(np.int16)),
        axis=2,
    )
    active = (
        (diff >= diff_threshold)
        | (hsv[:, :, 1] >= sat_threshold)
        | (grad >= grad_threshold)
    )
    row_counts = np.count_nonzero(active, axis=1)
    row_active = row_counts >= max(3, int(round(edge_w * 0.18)))
    scan_start = max(0, min(int(round(h * scan_top_ratio)), int(default_zone_y0)))
    run_needed = max(2, int(min_run_rows))
    for y in range(scan_start, max(scan_start, h - run_needed + 1)):
        if int(np.count_nonzero(row_active[y : y + run_needed])) >= (run_needed - 1):
            return max(0, y - max(0, int(top_margin_rows)))
    return max(0, int(default_zone_y0))


def build_final_corner_cleanup_mask(
    patch: np.ndarray,
    *,
    corner_right_ratio: float = 0.12,
    corner_bottom_ratio: float = 0.40,
    grabcut_iters: int = 3,
    min_component_area: int = 350,
    max_mask_area_ratio: float = 0.08,
    border_tolerance_px: int = 2,
) -> np.ndarray | None:
    if patch.ndim != 3 or patch.shape[2] != 3:
        return None

    h, w = patch.shape[:2]
    if h <= 0 or w <= 0:
        return None

    right_ratio = min(0.50, max(0.04, float(corner_right_ratio)))
    bottom_ratio = min(0.60, max(0.12, float(corner_bottom_ratio)))
    zone_x0 = max(0, int(round(w * (1.0 - right_ratio))))
    default_zone_y0 = max(0, int(round(h * (1.0 - bottom_ratio))))
    bg_color = estimate_slide_background_color(patch)
    zone_y0 = find_dynamic_corner_top(
        patch,
        bg_color,
        default_zone_y0,
    )
    zone = patch[zone_y0:, zone_x0:]
    if zone.size == 0:
        return None

    zh, zw = zone.shape[:2]
    if zh < 16 or zw < 16:
        return None

    gc_mask = np.full((zh, zw), cv2.GC_PR_BGD, dtype=np.uint8)
    bg_left = max(6, int(round(zw * 0.32)))
    bg_top = max(6, int(round(zh * 0.22)))
    top_strip = max(4, int(round(zh * 0.08)))
    left_strip = max(4, int(round(zw * 0.10)))
    gc_mask[:bg_top, :bg_left] = cv2.GC_BGD
    gc_mask[:top_strip, :] = cv2.GC_BGD
    gc_mask[:, :left_strip] = cv2.GC_BGD

    fg_strip_w = max(4, int(round(zw * 0.08)))
    fg_y0 = max(0, int(round(zh * 0.06)))
    gc_mask[fg_y0:, zw - fg_strip_w :] = cv2.GC_FGD

    bgd_model = np.zeros((1, 65), dtype=np.float64)
    fgd_model = np.zeros((1, 65), dtype=np.float64)
    try:
        cv2.grabCut(
            zone,
            gc_mask,
            None,
            bgd_model,
            fgd_model,
            max(1, int(grabcut_iters)),
            cv2.GC_INIT_WITH_MASK,
        )
    except cv2.error:
        return None

    fg_mask = np.where(
        (gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD),
        255,
        0,
    ).astype(np.uint8)
    if not np.any(fg_mask):
        return None

    open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, open_kernel)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, close_kernel)
    if not np.any(fg_mask):
        return None

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(fg_mask, connectivity=8)
    if num_labels <= 1:
        return None

    max_mask_pixels = max(1, int(round(float(max_mask_area_ratio) * h * w)))
    border_tol = max(0, int(border_tolerance_px))
    zone_mask = np.zeros((zh, zw), dtype=np.uint8)

    for label_idx in range(1, num_labels):
        x, y, comp_w, comp_h, area = stats[label_idx]
        if area < max(1, int(min_component_area)) or area > max_mask_pixels:
            continue
        touches_right = (x + comp_w) >= (zw - border_tol)
        if not touches_right:
            continue
        zone_mask[labels == label_idx] = 255

    if not np.any(zone_mask):
        return None

    dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    zone_mask = cv2.dilate(zone_mask, dilate_kernel, iterations=1)
    zone_mask = cv2.morphologyEx(zone_mask, cv2.MORPH_CLOSE, close_kernel)

    if int(np.count_nonzero(zone_mask)) > max_mask_pixels:
        return None

    full_mask = np.zeros((h, w), dtype=np.uint8)
    full_mask[zone_y0:, zone_x0:] = zone_mask
    return full_mask


def analyze_visible_corner(
    patch: np.ndarray,
    mask: np.ndarray,
    *,
    corner_right_ratio: float = 0.12,
    corner_bottom_ratio: float = 0.40,
    bg_sat_threshold: int = 42,
    bg_grad_threshold: float = 20.0,
    graphic_diff_threshold: float = 20.0,
    graphic_sat_threshold: int = 52,
    graphic_grad_threshold: float = 18.0,
    min_graphic_area: int = 24,
    border_tolerance_px: int = 2,
) -> tuple[np.ndarray, np.ndarray, set[int]]:
    h, w = patch.shape[:2]
    right_ratio = min(0.50, max(0.04, float(corner_right_ratio)))
    bottom_ratio = min(0.60, max(0.12, float(corner_bottom_ratio)))
    zone_x0 = max(0, int(round(w * (1.0 - right_ratio))))
    zone_y0 = max(0, int(round(h * (1.0 - bottom_ratio))))

    zone = patch[zone_y0:, zone_x0:]
    zone_mask = mask[zone_y0:, zone_x0:] > 0
    zh, zw = zone.shape[:2]
    valid = ~zone_mask

    hsv = cv2.cvtColor(zone, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(zone, cv2.COLOR_BGR2GRAY)
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = cv2.magnitude(grad_x, grad_y)

    bg_seed = valid & (hsv[:, :, 1] <= bg_sat_threshold) & (grad <= bg_grad_threshold)
    if int(np.count_nonzero(bg_seed)) < 48:
        bg_seed = valid & (hsv[:, :, 1] <= max(55, bg_sat_threshold + 10))
    if int(np.count_nonzero(bg_seed)) < 48:
        bg_seed = valid

    bg_pixels = zone[bg_seed]
    if bg_pixels.size == 0:
        bg_pixels = zone[valid]
    if bg_pixels.size == 0:
        bg_pixels = zone.reshape(-1, 3)
    bg_color = np.median(bg_pixels.reshape(-1, 3), axis=0).astype(np.uint8)

    diff = np.max(np.abs(zone.astype(np.int16) - bg_color.reshape(1, 1, 3).astype(np.int16)), axis=2)
    graphic = valid & (
        (diff >= graphic_diff_threshold)
        | (hsv[:, :, 1] >= graphic_sat_threshold)
        | (grad >= graphic_grad_threshold)
    )
    graphic = graphic.astype(np.uint8) * 255
    if np.any(graphic):
        open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        graphic = cv2.morphologyEx(graphic, cv2.MORPH_OPEN, open_kernel)
        graphic = cv2.morphologyEx(graphic, cv2.MORPH_CLOSE, close_kernel)

    labels_full = np.zeros((h, w), dtype=np.int32)
    border_ids: set[int] = set()
    if not np.any(graphic):
        return bg_color, labels_full, border_ids

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(graphic, connectivity=8)
    next_label = 1
    for label_idx in range(1, num_labels):
        x, y, comp_w, comp_h, area = stats[label_idx]
        if area < max(1, int(min_graphic_area)):
            continue
        comp_mask = labels == label_idx
        full_label = next_label
        next_label += 1
        labels_full[zone_y0:, zone_x0:][comp_mask] = full_label

        full_x = zone_x0 + x
        full_y = zone_y0 + y
        touches_right = (full_x + comp_w) >= (w - max(0, int(border_tolerance_px)))
        touches_bottom = (full_y + comp_h) >= (h - max(0, int(border_tolerance_px)))
        if touches_right or touches_bottom:
            border_ids.add(full_label)

    return bg_color, labels_full, border_ids


def local_row_fill(
    patch: np.ndarray,
    mask: np.ndarray,
    background_color: np.ndarray,
    graphic_labels: np.ndarray,
    border_component_ids: set[int],
    *,
    sample_width: int = 18,
    vertical_radius: int = 2,
    bg_match_threshold: float = 24.0,
    interior_blend_width: int = 10,
) -> np.ndarray | None:
    if (
        patch.ndim != 3
        or mask.ndim != 2
        or graphic_labels.ndim != 2
        or patch.shape[:2] != mask.shape[:2]
        or patch.shape[:2] != graphic_labels.shape[:2]
    ):
        return None
    if not np.any(mask):
        return patch.copy()

    h, w = mask.shape
    cleaned = patch.copy()
    interior_band_mask = np.zeros((h, w), dtype=bool)
    bg_ref = background_color.astype(np.float32)
    last_border_color = bg_ref.copy()

    for y in range(h):
        xs = np.flatnonzero(mask[y] > 0)
        if xs.size == 0:
            continue

        x_start = int(xs.min())
        x_end = int(xs.max())
        bg_samples: list[np.ndarray] = []
        border_samples: list[np.ndarray] = []
        interior_samples: list[np.ndarray] = []
        nearest_border = False
        nearest_label = 0
        if x_start > 0:
            nearest_label = int(graphic_labels[y, x_start - 1])
            nearest_border = nearest_label in border_component_ids

        for dy in range(-vertical_radius, vertical_radius + 1):
            yy = y + dy
            if yy < 0 or yy >= h:
                continue
            left_end = x_start
            left_start = max(0, left_end - sample_width)
            if left_end <= left_start:
                continue
            row_valid = mask[yy, left_start:left_end] == 0
            row_pixels = patch[yy, left_start:left_end]
            row_labels = graphic_labels[yy, left_start:left_end]
            if not np.any(row_valid):
                continue

            valid_pixels = row_pixels[row_valid]
            valid_labels = row_labels[row_valid]
            if valid_pixels.size == 0:
                continue

            is_border = np.isin(valid_labels, list(border_component_ids)) if border_component_ids else np.zeros(valid_labels.shape, dtype=bool)
            if np.any(is_border):
                border_samples.append(valid_pixels[is_border].reshape(-1, 3))

            is_plain = valid_labels == 0
            if np.any(is_plain):
                plain_pixels = valid_pixels[is_plain].reshape(-1, 3)
                plain_diff = np.max(np.abs(plain_pixels.astype(np.float32) - bg_ref.reshape(1, 3)), axis=1)
                matched = plain_pixels[plain_diff <= max(0.0, float(bg_match_threshold))]
                if matched.size:
                    bg_samples.append(matched.reshape(-1, 3))
                elif plain_pixels.size:
                    bg_samples.append(plain_pixels)
            if nearest_label > 0:
                same_component = valid_labels == nearest_label
                if np.any(same_component):
                    interior_samples.append(valid_pixels[same_component].reshape(-1, 3))

        if nearest_border and border_samples:
            base_color = np.median(np.vstack(border_samples), axis=0).astype(np.float32)
            last_border_color = base_color
        elif bg_samples:
            base_color = np.median(np.vstack(bg_samples), axis=0).astype(np.float32)
        elif border_samples and nearest_border:
            base_color = last_border_color
        else:
            base_color = bg_ref

        cleaned[y, x_start : x_end + 1] = np.clip(base_color, 0, 255).astype(np.uint8)

        if nearest_label > 0 and (not nearest_border) and interior_samples:
            blend_color = np.median(np.vstack(interior_samples), axis=0).astype(np.float32)
            band = min(max(0, int(interior_blend_width)), x_end - x_start + 1)
            if band > 0:
                for step in range(band):
                    x = x_start + step
                    if x > x_end or mask[y, x] == 0:
                        break
                    alpha = 1.0 - (float(step + 1) / float(band + 1))
                    color = (blend_color * alpha) + (base_color * (1.0 - alpha))
                    cleaned[y, x] = np.clip(color, 0, 255).astype(np.uint8)
                    interior_band_mask[y, x] = True

    if np.any(interior_band_mask):
        horiz_blur = cv2.GaussianBlur(cleaned, (11, 3), 0)
        cleaned[interior_band_mask] = horiz_blur[interior_band_mask]
    blur = cv2.GaussianBlur(cleaned, (1, 5), 0)
    cleaned[mask > 0] = blur[mask > 0]
    return cleaned


def clean_final_slide_image(src_slide: Path) -> np.ndarray | None:
    patch = cv2.imread(str(src_slide), cv2.IMREAD_COLOR)
    if patch is None or patch.size == 0:
        return None
    mask = build_final_corner_cleanup_mask(patch)
    if mask is None:
        return patch
    bg_color, graphic_labels, border_component_ids = analyze_visible_corner(patch, mask)
    cleaned = local_row_fill(
        patch,
        mask,
        bg_color,
        graphic_labels,
        border_component_ids,
    )
    return cleaned if cleaned is not None else patch


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


def load_gray_image(image_path: Path | None) -> np.ndarray | None:
    if image_path is None or not image_path.exists():
        return None
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None or img.size == 0:
        return None
    return img.astype(np.int16)


def image_mad(a: np.ndarray | None, b: np.ndarray | None) -> float:
    if a is None or b is None:
        return float("inf")
    if a.shape != b.shape:
        return float("inf")
    return float(np.mean(np.abs(a - b)))


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


def prepend_text_to_row(
    row: dict,
    text_parts: list[str],
    translated_parts: list[str],
    source_ids: set[int],
) -> None:
    prefix_text = " ".join(x for x in text_parts if x).strip()
    prefix_translated_text = " ".join(x for x in translated_parts if x).strip()
    if prefix_text:
        row["text"] = f"{prefix_text} {str(row.get('text', '')).strip()}".strip()
    if prefix_translated_text:
        row["translated_text"] = f"{prefix_translated_text} {str(row.get('translated_text', '')).strip()}".strip()
    row["source_segment_ids"] = sorted(set(parse_source_segment_ids(row.get("source_segment_ids", []))).union(source_ids))
    row["segments_count"] = len(row["source_segment_ids"])


def copy_kept_images(
    kept_rows: list[dict],
    source_info_by_event: dict[int, dict],
    src_slide_dir: Path,
    src_full_dir: Path | None,
    dst_slide_dir: Path | None,
    dst_full_dir: Path | None,
    dst_slide_raw_dir: Path | None,
    *,
    final_slide_clean_mode: str,
) -> None:
    if dst_slide_raw_dir is not None:
        dst_slide_raw_dir.mkdir(parents=True, exist_ok=True)
        for p in dst_slide_raw_dir.glob("*.png"):
            p.unlink()

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
        source_info = source_info_by_event.get(event_id, {})
        source_mode_final = str(source_info.get("source_mode_final", "slide") or "slide")
        src_slide = find_event_image(src_slide_dir, event_id)
        src_full = find_event_image(src_full_dir, event_id) if src_full_dir is not None else None
        raw_source = src_full if source_mode_final == "full" and src_full is not None else src_slide

        if raw_source is not None and dst_slide_raw_dir is not None:
            raw_name = f"slide_{idx:03d}_{raw_source.name}"
            shutil.copy2(raw_source, dst_slide_raw_dir / raw_name)

        if raw_source is not None and dst_slide_dir is not None:
            dst_name = f"slide_{idx:03d}_{raw_source.name}"
            dst_path = dst_slide_dir / dst_name
            if final_slide_clean_mode == "local" and idx != 1 and source_mode_final == "slide" and src_slide is not None:
                cleaned = clean_final_slide_image(src_slide)
                if cleaned is None:
                    shutil.copy2(raw_source, dst_path)
                else:
                    cv2.imwrite(str(dst_path), cleaned)
            else:
                shutil.copy2(raw_source, dst_path)

        if src_full_dir is not None and dst_full_dir is not None:
            if src_full is not None:
                dst_name = f"slide_{idx:03d}_{src_full.name}"
                shutil.copy2(src_full, dst_full_dir / dst_name)


def merge_duplicate_kept_rows(
    kept_rows: list[dict],
    slide_keyframes_dir: Path,
    *,
    mad_threshold: float,
) -> tuple[list[dict], dict[int, int]]:
    if not kept_rows:
        return [], {}

    merged_rows: list[dict] = []
    duplicate_targets: dict[int, int] = {}
    previous_image: np.ndarray | None = None

    for row in kept_rows:
        event_id = int(row["event_id"])
        current_image = load_gray_image(find_event_image(slide_keyframes_dir, event_id))
        if merged_rows and image_mad(current_image, previous_image) <= mad_threshold:
            target = merged_rows[-1]
            target["slide_end"] = max(float(target["slide_end"]), float(row["slide_end"]))
            text = str(row.get("text", "")).strip()
            if text:
                if target["text"]:
                    target["text"] = f"{target['text']} {text}".strip()
                else:
                    target["text"] = text
            target["source_segment_ids"] = sorted(
                set(parse_source_segment_ids(target.get("source_segment_ids", []))).union(
                    parse_source_segment_ids(row.get("source_segment_ids", []))
                )
            )
            target["segments_count"] = len(target["source_segment_ids"])
            duplicate_targets[event_id] = int(target["event_id"])
            continue

        keep_row = dict(row)
        keep_row["source_segment_ids"] = sorted(parse_source_segment_ids(keep_row.get("source_segment_ids", [])))
        keep_row["segments_count"] = len(keep_row["source_segment_ids"])
        merged_rows.append(keep_row)
        previous_image = current_image

    return merged_rows, duplicate_targets


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
    parser.add_argument(
        "--out-final-source-manifest-csv",
        default="",
        help="Optional per-final-slide source selection manifest output.",
    )
    parser.add_argument("--out-final-slide-dir", default="", help="Optional folder with copied kept slide images.")
    parser.add_argument(
        "--out-final-slide-raw-dir",
        default="",
        help="Optional folder with raw copied kept slide images before any final slide cleanup.",
    )
    parser.add_argument("--out-final-full-dir", default="", help="Optional folder with copied kept full images.")
    parser.add_argument(
        "--final-slide-clean-mode",
        choices=("none", "local"),
        default="local",
        help="Final slide cleanup mode for copied kept ROI images (default: local).",
    )
    parser.add_argument(
        "--final-source-mode-auto",
        choices=("off", "auto"),
        default="auto",
        help="Choose whether final slides auto-switch from ROI to full image before postprocess steps.",
    )
    parser.add_argument("--roi-x0", type=int, default=0, help="ROI left coordinate in full-frame pixels.")
    parser.add_argument("--roi-y0", type=int, default=0, help="ROI top coordinate in full-frame pixels.")
    parser.add_argument("--roi-x1", type=int, default=0, help="ROI right coordinate in full-frame pixels.")
    parser.add_argument("--roi-y1", type=int, default=0, help="ROI bottom coordinate in full-frame pixels.")
    parser.add_argument(
        "--fullslide-sample-frames",
        type=int,
        default=3,
        help="Number of video frames sampled per final slide for auto full-slide detection (default: 3).",
    )
    parser.add_argument(
        "--fullslide-border-strip-px",
        type=int,
        default=24,
        help="Strip width outside/inside ROI used for full-slide border continuity checks (default: 24).",
    )
    parser.add_argument(
        "--fullslide-min-matched-sides",
        type=int,
        default=2,
        help="Minimum matched ROI border sides needed per sample frame to accept full-slide continuity (default: 2).",
    )
    parser.add_argument(
        "--fullslide-border-diff-threshold",
        type=float,
        default=16.0,
        help="Median Lab-strip difference threshold for border continuity (default: 16.0).",
    )
    parser.add_argument(
        "--fullslide-person-box-area-ratio",
        type=float,
        default=0.02,
        help="Minimum detected person box area ratio relative to full frame (default: 0.02).",
    )
    parser.add_argument(
        "--fullslide-person-outside-ratio",
        type=float,
        default=0.35,
        help="Minimum fraction of a detected person box that must lie outside the ROI (default: 0.35).",
    )
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
    parser.add_argument(
        "--duplicate-slide-mad-threshold",
        type=float,
        default=0.7,
        help="Merge consecutive kept slides when ROI image MAD stays below threshold (default: 0.7).",
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
    out_final_source_manifest_csv = (
        Path(args.out_final_source_manifest_csv).resolve() if args.out_final_source_manifest_csv else None
    )
    out_final_slide_dir = Path(args.out_final_slide_dir).resolve() if args.out_final_slide_dir else None
    out_final_slide_raw_dir = (
        Path(args.out_final_slide_raw_dir).resolve() if args.out_final_slide_raw_dir else None
    )
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
    if out_final_source_manifest_csv is not None:
        out_final_source_manifest_csv.parent.mkdir(parents=True, exist_ok=True)

    roi = (
        int(args.roi_x0),
        int(args.roi_y0),
        int(args.roi_x1),
        int(args.roi_y1),
    )
    if str(args.final_source_mode_auto) == "auto" and (roi[0] >= roi[2] or roi[1] >= roi[3]):
        raise ValueError("ROI must satisfy x0 < x1 and y0 < y1 when final source auto mode is enabled")

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
    leading_no_slide_translated_parts: list[str] = []
    leading_no_slide_ids: set[int] = set()
    thumbnail_received_merged_text = False

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
        translated_text = str(row.get("translated_text", "")).strip()
        src_ids = set(parse_source_segment_ids(row.get("source_segment_ids", [])))

        action = "keep"
        merge_target = None
        if is_no_slide or is_speaker_only:
            if kept_rows:
                if len(kept_rows) == 1:
                    target = kept_rows[0]
                    target["slide_end"] = max(float(target["slide_end"]), float(row["slide_end"]))
                    if text:
                        if target["text"]:
                            target["text"] = f"{target['text']} {text}".strip()
                        else:
                            target["text"] = text
                    if translated_text:
                        if target.get("translated_text"):
                            target["translated_text"] = f"{target['translated_text']} {translated_text}".strip()
                        else:
                            target["translated_text"] = translated_text
                    target["source_segment_ids"] = sorted(set(target["source_segment_ids"]).union(src_ids))
                    target["segments_count"] = len(target["source_segment_ids"])
                    merge_target = int(target["event_id"])
                    action = "merged_to_thumbnail"
                    if text or translated_text:
                        thumbnail_received_merged_text = True
                else:
                    target = kept_rows[-1]
                    target["slide_end"] = max(float(target["slide_end"]), float(row["slide_end"]))
                    if text:
                        if target["text"]:
                            target["text"] = f"{target['text']} {text}".strip()
                        else:
                            target["text"] = text
                    if translated_text:
                        if target.get("translated_text"):
                            target["translated_text"] = f"{target['translated_text']} {translated_text}".strip()
                        else:
                            target["translated_text"] = translated_text
                    target["source_segment_ids"] = sorted(set(target["source_segment_ids"]).union(src_ids))
                    target["segments_count"] = len(target["source_segment_ids"])
                    merge_target = int(target["event_id"])
                    action = "merged_to_previous"
            else:
                if text:
                    leading_no_slide_parts.append(text)
                if translated_text:
                    leading_no_slide_translated_parts.append(translated_text)
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

    kept_rows, duplicate_targets = merge_duplicate_kept_rows(
        kept_rows,
        slide_keyframes_dir,
        mad_threshold=max(0.0, float(args.duplicate_slide_mad_threshold)),
    )

    if kept_rows:
        thumbnail_row = kept_rows[0]
        if not thumbnail_received_merged_text:
            thumbnail_row["text"] = ""
            thumbnail_row["translated_text"] = ""
            thumbnail_row["source_segment_ids"] = []
            thumbnail_row["segments_count"] = 0
        if len(kept_rows) >= 2 and (leading_no_slide_parts or leading_no_slide_ids):
            prepend_text_to_row(kept_rows[1], leading_no_slide_parts, leading_no_slide_translated_parts, leading_no_slide_ids)
            leading_no_slide_parts.clear()
            leading_no_slide_translated_parts.clear()
            leading_no_slide_ids.clear()

    if duplicate_targets:
        for manifest in manifest_rows:
            event_id = int(manifest["event_id"])
            if event_id in duplicate_targets:
                manifest["decision_reason"] = "duplicate_slide"
                manifest["action"] = "merged_duplicate_slide"
                manifest["merge_target_event_id"] = duplicate_targets[event_id]

    source_rows = detect_final_source_modes(
        kept_rows,
        video_path=video_path,
        fps=fps,
        full_keyframes_dir=full_keyframes_dir,
        roi=roi,
        final_source_mode_auto=str(args.final_source_mode_auto),
        fullslide_sample_frames=max(1, int(args.fullslide_sample_frames)),
        fullslide_border_strip_px=max(2, int(args.fullslide_border_strip_px)),
        fullslide_min_matched_sides=max(1, int(args.fullslide_min_matched_sides)),
        fullslide_border_diff_threshold=max(0.0, float(args.fullslide_border_diff_threshold)),
        fullslide_person_box_area_ratio=max(0.0, float(args.fullslide_person_box_area_ratio)),
        fullslide_person_outside_ratio=max(0.0, float(args.fullslide_person_outside_ratio)),
    )
    source_info_by_event = {int(row["event_id"]): row for row in source_rows}

    final_rows: list[dict] = []
    if (not kept_rows) and (leading_no_slide_parts or leading_no_slide_ids):
        leading_text = " ".join(x for x in leading_no_slide_parts if x).strip()
        leading_translated_text = " ".join(x for x in leading_no_slide_translated_parts if x).strip()
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
                "translated_text": leading_translated_text,
                "target_language": str(next((str(row.get("target_language", "")).strip() for row in kept_rows if str(row.get("target_language", "")).strip()), "")),
                "segments_count": len(ids),
                "source_segment_ids": ids,
                "source_mode_auto": "",
                "source_mode_final": "",
                "source_reason": "",
                "source_confidence": "",
            }
        )

    for row in kept_rows:
        source_info = source_info_by_event.get(int(row["event_id"]), {})
        final_rows.append(
            {
                "event_id": int(row["event_id"]),
                "bucket_id": str(row["bucket_id"]),
                "slide_start": round(float(row["slide_start"]), 3),
                "slide_end": round(float(row["slide_end"]), 3),
                "is_no_slide": False,
                "merge_target_event_id": int(row["event_id"]),
                "text": str(row.get("text", "")).strip(),
                "translated_text": str(row.get("translated_text", "")).strip(),
                "target_language": str(row.get("target_language", "")).strip(),
                "segments_count": int(row.get("segments_count", 0)),
                "source_segment_ids": sorted(parse_source_segment_ids(row.get("source_segment_ids", []))),
                "source_mode_auto": str(source_info.get("source_mode_auto", "slide")),
                "source_mode_final": str(source_info.get("source_mode_final", "slide")),
                "source_reason": str(source_info.get("source_reason", "")),
                "source_confidence": float(source_info.get("source_confidence", 0.0)),
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
        "removed_event_count": len(
            [r for r in manifest_rows if r["action"] in {"merged_to_previous", "merged_to_thumbnail", "leading_no_previous"}]
        ),
        "final_source_mode_auto": str(args.final_source_mode_auto),
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
                "translated_text",
                "target_language",
                "segments_count",
                "source_segment_ids",
                "source_mode_auto",
                "source_mode_final",
                "source_reason",
                "source_confidence",
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
                    "translated_text": row.get("translated_text", ""),
                    "target_language": row.get("target_language", ""),
                    "segments_count": row["segments_count"],
                    "source_segment_ids": format_source_ids(row["source_segment_ids"]),
                    "source_mode_auto": row.get("source_mode_auto", ""),
                    "source_mode_final": row.get("source_mode_final", ""),
                    "source_reason": row.get("source_reason", ""),
                    "source_confidence": row.get("source_confidence", ""),
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

    if out_final_source_manifest_csv is not None:
        with out_final_source_manifest_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "slide_index",
                    "event_id",
                    "source_mode_auto",
                    "source_mode_final",
                    "source_reason",
                    "source_confidence",
                    "sample_frames",
                    "person_detected_frames",
                    "person_present",
                    "person_max_weight",
                    "matched_frame_count",
                    "median_matched_sides",
                    "side_diff_left",
                    "side_diff_right",
                    "side_diff_top",
                    "side_diff_bottom",
                ],
            )
            writer.writeheader()
            writer.writerows(source_rows)

    copy_kept_images(
        [row for row in final_rows if int(row["event_id"]) > 0],
        source_info_by_event,
        slide_keyframes_dir,
        full_keyframes_dir,
        out_final_slide_dir,
        out_final_full_dir,
        out_final_slide_raw_dir,
        final_slide_clean_mode=str(args.final_slide_clean_mode),
    )

    print(f"[ASR] Original mapped events: {len(rows)}")
    print(f"[ASR] Final events after filtering: {len(final_rows)}")
    print(f"[ASR] Kept slide events: {len([r for r in final_rows if int(r['event_id']) > 0])}")
    print(f"[ASR] Wrote final slide text map JSON: {out_json}")
    print(f"[ASR] Wrote final slide text map CSV: {out_csv}")
    print(f"[ASR] Wrote filter manifest CSV: {out_manifest_csv}")
    if out_final_source_manifest_csv is not None:
        print(f"[ASR] Wrote final image source manifest CSV: {out_final_source_manifest_csv}")
    if out_final_slide_dir is not None:
        print(f"[ASR] Wrote kept slide images: {out_final_slide_dir}")
    if out_final_slide_raw_dir is not None:
        print(f"[ASR] Wrote raw kept slide images: {out_final_slide_raw_dir}")
    if out_final_full_dir is not None:
        print(f"[ASR] Wrote kept full images: {out_final_full_dir}")
    auto_full_count = len([row for row in source_rows if row.get("source_mode_final") == "full"])
    print(f"[ASR] Final source mode auto: {args.final_source_mode_auto}")
    print(f"[ASR] Final slides routed to full source: {auto_full_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
