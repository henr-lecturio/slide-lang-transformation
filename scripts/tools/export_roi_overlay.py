#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, val = s.split("=", 1)
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def clamp_roi(roi: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = roi
    x0 = max(0, min(width - 1, x0))
    y0 = max(0, min(height - 1, y0))
    x1 = max(x0 + 1, min(width, x1))
    y1 = max(y0 + 1, min(height, y1))
    return x0, y0, x1, y1


def draw_corner_label(
    image,
    text: str,
    corner: str,
    roi: tuple[int, int, int, int],
    width: int,
    height: int,
) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.45
    thickness = 1
    (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    x0, y0, x1, y1 = roi

    gap = 2
    pad = 1
    box_w = tw + 2 * pad
    box_h = th + baseline + 2 * pad

    if corner == "TL":
        x = x0
        y = y0 - gap - box_h
        if y < 0:
            y = y1 + gap
    elif corner == "TR":
        x = x1 - box_w
        y = y0 - gap - box_h
        if y < 0:
            y = y1 + gap
    elif corner == "BL":
        x = x0
        y = y1 + gap
        if y + box_h > height:
            y = y0 - gap - box_h
    elif corner == "BR":
        x = x1 - box_w
        y = y1 + gap
        if y + box_h > height:
            y = y0 - gap - box_h
    else:
        raise ValueError(f"Unsupported corner: {corner}")

    x = max(0, min(width - box_w, x))
    y = max(0, min(height - box_h, y))

    cv2.rectangle(image, (x, y), (x + box_w, y + box_h), (0, 0, 0), -1)
    cv2.putText(
        image,
        text,
        (x + pad, y + pad + th),
        font,
        font_scale,
        (0, 255, 255),
        thickness,
        cv2.LINE_AA,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export one video frame with current ROI overlay and corner coordinates "
            "from config/pipeline.env."
        )
    )
    parser.add_argument("--config", default="config/pipeline.env", help="Path to .env config.")
    parser.add_argument(
        "--video",
        default="",
        help="Video path for the preview frame. Falls back to VIDEO_PATH from config if present.",
    )
    parser.add_argument("--time-sec", type=float, default=30.0, help="Timestamp in seconds for frame export.")
    parser.add_argument(
        "--out",
        default="output/roi_tuning/roi_overlay.png",
        help="Output image path.",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        raise FileNotFoundError(config_path)

    env = parse_env_file(config_path)
    required = ("ROI_X0", "ROI_Y0", "ROI_X1", "ROI_Y1")
    missing = [k for k in required if k not in env]
    if missing:
        raise RuntimeError(f"Missing ROI keys in {config_path}: {', '.join(missing)}")

    x0 = int(env["ROI_X0"])
    y0 = int(env["ROI_Y0"])
    x1 = int(env["ROI_X1"])
    y1 = int(env["ROI_Y1"])
    raw_roi = (x0, y0, x1, y1)

    if args.video:
        video_path = Path(args.video).resolve()
    else:
        if "VIDEO_PATH" not in env:
            raise RuntimeError(f"Missing VIDEO_PATH in {config_path} and no --video given.")
        root_dir = config_path.parent.parent
        video_path = Path(env["VIDEO_PATH"])
        if not video_path.is_absolute():
            video_path = (root_dir / video_path).resolve()

    if not video_path.exists():
        raise FileNotFoundError(video_path)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_idx = max(0, int(round(args.time_sec * fps)))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise RuntimeError(f"Could not read frame at t={args.time_sec:.3f}s (frame {frame_idx}).")

    h, w = frame.shape[:2]
    roi = clamp_roi(raw_roi, w, h)
    cx0, cy0, cx1, cy1 = roi

    cv2.rectangle(frame, (cx0, cy0), (cx1 - 1, cy1 - 1), (0, 255, 0), 2)
    for px, py in ((cx0, cy0), (cx1 - 1, cy0), (cx0, cy1 - 1), (cx1 - 1, cy1 - 1)):
        cv2.circle(frame, (px, py), 5, (0, 255, 0), -1)

    # Labels show configured ROI corner coordinates for fast manual adjustment.
    draw_corner_label(frame, f"TL ({x0},{y0})", "TL", roi, w, h)
    draw_corner_label(frame, f"TR ({x1},{y0})", "TR", roi, w, h)
    draw_corner_label(frame, f"BL ({x0},{y1})", "BL", roi, w, h)
    draw_corner_label(frame, f"BR ({x1},{y1})", "BR", roi, w, h)

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), frame)

    print(f"Video: {video_path}")
    print(f"Frame: {frame_idx} (t={args.time_sec:.3f}s, fps={fps:.3f})")
    print(f"Config ROI: x0={x0}, y0={y0}, x1={x1}, y1={y1}")
    if raw_roi != roi:
        print(f"Clamped ROI for preview: x0={cx0}, y0={cy0}, x1={cx1}, y1={cy1}")
    print(f"Wrote overlay image: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
