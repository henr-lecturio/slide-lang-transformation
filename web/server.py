#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / "web"
CONFIG_PATH = ROOT_DIR / "config" / "slitranet.env"
OUTPUT_DIR = ROOT_DIR / "output"
RUNS_DIR = OUTPUT_DIR / "runs"
OVERLAY_PATH = OUTPUT_DIR / "roi_tuning" / "roi_overlay.png"
VIDEOS_DIR = ROOT_DIR / "videos"
VIDEO_THUMB_DIR = OUTPUT_DIR / "ui" / "video_thumbs"
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}

VENV_PY = ROOT_DIR / ".venv" / "bin" / "python"
PYTHON_BIN = str(VENV_PY if VENV_PY.exists() else Path(sys.executable))

RUN_ID_PATTERN = re.compile(r"^(?:\d{8}_\d{6}|\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})$")

RUN_LOCK = threading.Lock()
RUN_STATE = {
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "run_id": None,
    "exit_code": None,
    "log_tail": deque(maxlen=600),
    "process": None,
}


def latest_run_id() -> str | None:
    if not RUNS_DIR.exists():
        return None
    for entry in sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if entry.is_dir() and RUN_ID_PATTERN.match(entry.name):
            return entry.name
    return None


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, val = stripped.split("=", 1)
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def _format_config_value(value: int | float | str) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f"\"{escaped}\""
    return str(value)


def write_config_values(path: Path, values: dict[str, int | float | str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    keys = tuple(values.keys())
    found = set()
    out_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0] if "=" in stripped else ""
        if key in keys:
            out_lines.append(f"{key}={_format_config_value(values[key])}")
            found.add(key)
        else:
            out_lines.append(line)

    if len(found) != len(keys):
        out_lines.append("")
        for key in keys:
            if key not in found:
                out_lines.append(f"{key}={_format_config_value(values[key])}")

    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def ensure_within(base: Path, target: Path) -> Path:
    base_resolved = base.resolve()
    target_resolved = target.resolve()
    if base_resolved == target_resolved:
        return target_resolved
    if base_resolved not in target_resolved.parents:
        raise ValueError("Path traversal blocked")
    return target_resolved


def count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.iterdir() if p.is_file())


def csv_event_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        rows = sum(1 for _ in f)
    return max(0, rows - 1)


def csv_preview(path: Path, limit: int = 20) -> list[str]:
    if not path.exists():
        return []
    out: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= limit:
                break
            out.append(line.rstrip("\n"))
    return out


def is_video_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in VIDEO_EXTS


def resolve_video_config_path(video_path: str) -> Path:
    text = (video_path or "").strip()
    if not text:
        raise ValueError("VIDEO_PATH must not be empty")
    target = ensure_within(ROOT_DIR, ROOT_DIR / text)
    target = ensure_within(VIDEOS_DIR, target)
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(str(target))
    if not is_video_file(target):
        raise ValueError(f"VIDEO_PATH is not a supported video: {video_path}")
    return target


def list_videos_catalog() -> list[dict]:
    items: list[dict] = []
    if not VIDEOS_DIR.exists():
        return items

    def walk(current: Path) -> None:
        rel = current.relative_to(VIDEOS_DIR)
        if current != VIDEOS_DIR:
            depth = max(0, len(rel.parts) - 1)
            items.append(
                {
                    "type": "dir",
                    "name": current.name,
                    "path": (Path("videos") / rel).as_posix(),
                    "depth": depth,
                }
            )

        children = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        for child in children:
            if child.is_dir():
                walk(child)
            elif is_video_file(child):
                rel_file = child.relative_to(VIDEOS_DIR)
                items.append(
                    {
                        "type": "video",
                        "name": child.name,
                        "path": (Path("videos") / rel_file).as_posix(),
                        "depth": max(0, len(rel_file.parts) - 1),
                    }
                )

    walk(VIDEOS_DIR)
    return items


def ensure_video_thumbnail(video_config_path: str) -> Path:
    video_path = resolve_video_config_path(video_config_path)
    cache_key = hashlib.sha1(
        f"{video_path.as_posix()}:{video_path.stat().st_mtime_ns}".encode("utf-8")
    ).hexdigest()[:24]
    thumb_path = VIDEO_THUMB_DIR / f"{cache_key}.jpg"
    if thumb_path.exists():
        return thumb_path

    VIDEO_THUMB_DIR.mkdir(parents=True, exist_ok=True)
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
    if fps > 0.0 and frame_count > 0.0:
        probe_frame = min(frame_count - 1, max(0.0, fps * 1.0))
        cap.set(cv2.CAP_PROP_POS_FRAMES, probe_frame)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise RuntimeError(f"Failed to read frame from video: {video_path}")

    h, w = frame.shape[:2]
    target_w = min(420, w)
    if target_w > 0 and target_w != w:
        target_h = max(1, int(round(h * (target_w / w))))
        frame = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)
    if not cv2.imwrite(str(thumb_path), frame):
        raise RuntimeError(f"Failed to write thumbnail: {thumb_path}")
    return thumb_path


def list_runs() -> list[dict]:
    runs: list[dict] = []
    if not RUNS_DIR.exists():
        return runs

    for entry in sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not entry.is_dir() or not RUN_ID_PATTERN.match(entry.name):
            continue
        csv_path = entry / "slitranet" / "slide_changes.csv"
        final_csv_path = entry / "slitranet" / "slide_text_map_final.csv"
        slide_dir = entry / "slitranet" / "keyframes" / "slide"
        final_slide_dir = entry / "slitranet" / "keyframes" / "final" / "slide"
        full_dir = entry / "slitranet" / "keyframes" / "full"
        runs.append(
            {
                "id": entry.name,
                "path": str(entry),
                "has_csv": csv_path.exists(),
                "event_count": csv_event_count(csv_path),
                "final_event_count": csv_event_count(final_csv_path),
                "slide_images": count_files(slide_dir),
                "final_slide_images": count_files(final_slide_dir),
                "full_images": count_files(full_dir),
                "mtime": int(entry.stat().st_mtime),
            }
        )
    return runs


def run_detail(run_id: str) -> dict:
    if not RUN_ID_PATTERN.match(run_id):
        raise ValueError("Invalid run id")

    run_dir = ensure_within(RUNS_DIR, RUNS_DIR / run_id)
    if not run_dir.exists():
        raise FileNotFoundError(run_id)

    csv_path = run_dir / "slitranet" / "slide_changes.csv"
    final_csv_path = run_dir / "slitranet" / "slide_text_map_final.csv"
    transitions_dir = run_dir / "slitranet" / "transitions"
    slide_dir = run_dir / "slitranet" / "keyframes" / "slide"
    final_slide_dir = run_dir / "slitranet" / "keyframes" / "final" / "slide"
    full_dir = run_dir / "slitranet" / "keyframes" / "full"

    transition_files = []
    if transitions_dir.exists():
        transition_files = sorted(p.name for p in transitions_dir.iterdir() if p.is_file())

    return {
        "id": run_id,
        "path": str(run_dir),
        "has_csv": csv_path.exists(),
        "event_count": csv_event_count(csv_path),
        "final_event_count": csv_event_count(final_csv_path),
        "csv_preview": csv_preview(csv_path),
        "final_csv_preview": csv_preview(final_csv_path),
        "csv_url": f"/api/runs/{run_id}/file/slitranet/slide_changes.csv",
        "final_csv_url": f"/api/runs/{run_id}/file/slitranet/slide_text_map_final.csv",
        "transition_files": transition_files,
        "slide_images": count_files(slide_dir),
        "final_slide_images": count_files(final_slide_dir),
        "full_images": count_files(full_dir),
    }


def run_images(run_id: str, image_type: str) -> list[dict]:
    if not RUN_ID_PATTERN.match(run_id):
        raise ValueError("Invalid run id")
    if image_type not in {"slide", "full"}:
        raise ValueError("Invalid image type")

    base = ensure_within(RUNS_DIR, RUNS_DIR / run_id)
    image_dir = base / "slitranet" / "keyframes" / image_type
    if not image_dir.exists():
        return []

    items: list[dict] = []
    for p in sorted(image_dir.iterdir()):
        if not p.is_file():
            continue
        rel = p.relative_to(base).as_posix()
        items.append({"name": p.name, "url": f"/api/runs/{run_id}/file/{rel}"})
    return items


def _find_event_image_rel(
    run_dir: Path,
    event_id: int,
    variants: list[str],
    *,
    include_final: bool = True,
) -> str | None:
    if event_id <= 0:
        return None
    candidates: list[Path] = []
    if include_final:
        candidates.extend(run_dir / "slitranet" / "keyframes" / "final" / v for v in variants)
    candidates.extend(run_dir / "slitranet" / "keyframes" / v for v in variants)
    for image_dir in candidates:
        if not image_dir.exists():
            continue
        matches = sorted(image_dir.glob(f"*event_{event_id:03d}_*.png"))
        if not matches:
            matches = sorted(image_dir.glob(f"event_{event_id:03d}_*.png"))
        if matches:
            return matches[0].relative_to(run_dir).as_posix()
    return None


def run_final_slides(run_id: str) -> list[dict]:
    if not RUN_ID_PATTERN.match(run_id):
        raise ValueError("Invalid run id")
    run_dir = ensure_within(RUNS_DIR, RUNS_DIR / run_id)
    final_csv = run_dir / "slitranet" / "slide_text_map_final.csv"
    if not final_csv.exists():
        return []

    items: list[dict] = []
    with final_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            event_id = int(row.get("event_id", "0") or "0")
            if event_id <= 0:
                continue
            if event_id == 1:
                # Intro/thumbnail should be shown as full frame, not ROI crop.
                rel = _find_event_image_rel(run_dir, event_id, ["full", "slide"], include_final=True)
            else:
                rel = _find_event_image_rel(run_dir, event_id, ["slide", "full"], include_final=True)
            items.append(
                {
                    "index": idx,
                    "event_id": event_id,
                    "bucket_id": row.get("bucket_id", ""),
                    "slide_start": float(row.get("slide_start", "0") or "0"),
                    "slide_end": float(row.get("slide_end", "0") or "0"),
                    "text": (row.get("text", "") or "").strip(),
                    "segments_count": int(row.get("segments_count", "0") or "0"),
                    "source_segment_ids": row.get("source_segment_ids", "") or "",
                    "image_url": f"/api/runs/{run_id}/file/{rel}" if rel else "",
                    "image_name": Path(rel).name if rel else "",
                }
            )
    return items


def run_base_events(run_id: str) -> list[dict]:
    if not RUN_ID_PATTERN.match(run_id):
        raise ValueError("Invalid run id")
    run_dir = ensure_within(RUNS_DIR, RUNS_DIR / run_id)
    base_csv = run_dir / "slitranet" / "slide_changes.csv"
    if not base_csv.exists():
        return []

    items: list[dict] = []
    with base_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            event_id = int(row.get("event_id", "0") or "0")
            if event_id <= 0:
                continue

            if event_id == 1:
                rel = _find_event_image_rel(run_dir, event_id, ["full", "slide"], include_final=False)
            else:
                rel = _find_event_image_rel(run_dir, event_id, ["slide", "full"], include_final=False)

            items.append(
                {
                    "index": idx,
                    "event_id": event_id,
                    "transition_no": int(row.get("transition_no", "0") or "0"),
                    "frame_id_0": int(row.get("frame_id_0", "0") or "0"),
                    "frame_id_1": int(row.get("frame_id_1", "0") or "0"),
                    "event_frame": int(row.get("event_frame", "0") or "0"),
                    "time_sec": float(row.get("time_sec", "0") or "0"),
                    "timecode": row.get("timecode", "") or "",
                    "image_url": f"/api/runs/{run_id}/file/{rel}" if rel else "",
                    "image_name": Path(rel).name if rel else "",
                }
            )
    return items


def _now() -> int:
    return int(time.time())


def snapshot_run_state() -> dict:
    reconcile_run_state()
    with RUN_LOCK:
        return {
            "status": RUN_STATE["status"],
            "started_at": RUN_STATE["started_at"],
            "finished_at": RUN_STATE["finished_at"],
            "run_id": RUN_STATE["run_id"],
            "exit_code": RUN_STATE["exit_code"],
            "log_tail": list(RUN_STATE["log_tail"]),
        }


def reconcile_run_state() -> None:
    with RUN_LOCK:
        proc = RUN_STATE.get("process")
        if proc is None:
            return
        code = proc.poll()
        if code is None:
            return
        RUN_STATE["exit_code"] = code
        if RUN_STATE["finished_at"] is None:
            RUN_STATE["finished_at"] = _now()
        RUN_STATE["status"] = "done" if code == 0 else "error"
        RUN_STATE["process"] = None
        if not RUN_STATE.get("run_id"):
            RUN_STATE["run_id"] = latest_run_id()


def _run_worker(process: subprocess.Popen) -> None:
    run_id: str | None = None
    try:
        assert process.stdout is not None
        for raw in process.stdout:
            line = raw.rstrip("\n")
            with RUN_LOCK:
                RUN_STATE["log_tail"].append(line)
            if line.startswith("Run dir:"):
                path_text = line.split("Run dir:", 1)[1].strip()
                p = Path(path_text)
                if p.name and RUN_ID_PATTERN.match(p.name):
                    run_id = p.name
                    with RUN_LOCK:
                        RUN_STATE["run_id"] = run_id
    finally:
        code = process.wait()
        with RUN_LOCK:
            RUN_STATE["exit_code"] = code
            RUN_STATE["finished_at"] = _now()
            RUN_STATE["status"] = "done" if code == 0 else "error"
            RUN_STATE["process"] = None
            if run_id and not RUN_STATE.get("run_id"):
                RUN_STATE["run_id"] = run_id


def start_run() -> tuple[bool, str]:
    with RUN_LOCK:
        proc = RUN_STATE.get("process")
        if proc is not None and proc.poll() is None:
            return False, "Run already in progress"

        RUN_STATE["status"] = "running"
        RUN_STATE["started_at"] = _now()
        RUN_STATE["finished_at"] = None
        RUN_STATE["run_id"] = None
        RUN_STATE["exit_code"] = None
        RUN_STATE["log_tail"].clear()

        process = subprocess.Popen(
            ["bash", "scripts/run_slitranet.sh"],
            cwd=str(ROOT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        RUN_STATE["process"] = process

    thread = threading.Thread(target=_run_worker, args=(process,), daemon=True)
    thread.start()
    return True, "started"


def run_overlay(time_sec: float) -> tuple[int, str]:
    cmd = [
        PYTHON_BIN,
        "scripts/export_roi_overlay.py",
        "--time-sec",
        f"{time_sec}",
    ]
    result = subprocess.run(
        cmd,
        cwd=str(ROOT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return result.returncode, result.stdout


class Handler(BaseHTTPRequestHandler):
    server_version = "SceneDetectionUI/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            if path == "/":
                return self._serve_static("index.html")
            if path == "/styles.css":
                return self._serve_static("styles.css")
            if path == "/app.js":
                return self._serve_static("app.js")

            if path == "/api/config":
                env = parse_env(CONFIG_PATH)
                payload = {
                    "VIDEO_PATH": env.get("VIDEO_PATH", ""),
                    "PHASE": env.get("PHASE", "test"),
                    "ROI_X0": int(env.get("ROI_X0", "0")),
                    "ROI_Y0": int(env.get("ROI_Y0", "0")),
                    "ROI_X1": int(env.get("ROI_X1", "0")),
                    "ROI_Y1": int(env.get("ROI_Y1", "0")),
                    "KEYFRAME_SETTLE_FRAMES": int(env.get("KEYFRAME_SETTLE_FRAMES", "4")),
                    "KEYFRAME_STABLE_END_GUARD_FRAMES": int(env.get("KEYFRAME_STABLE_END_GUARD_FRAMES", "2")),
                    "KEYFRAME_STABLE_LOOKAHEAD_FRAMES": int(env.get("KEYFRAME_STABLE_LOOKAHEAD_FRAMES", "2")),
                    "SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO": float(env.get("SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO", "0.75")),
                    "SPEAKER_FILTER_MAX_EDGE_DENSITY": float(env.get("SPEAKER_FILTER_MAX_EDGE_DENSITY", "0.011")),
                    "SPEAKER_FILTER_MAX_LAPLACIAN_VAR": float(env.get("SPEAKER_FILTER_MAX_LAPLACIAN_VAR", "80")),
                    "SPEAKER_FILTER_MAX_DURATION_SEC": float(env.get("SPEAKER_FILTER_MAX_DURATION_SEC", "2.5")),
                }
                return self._send_json(200, payload)

            if path == "/api/videos":
                env = parse_env(CONFIG_PATH)
                payload = {
                    "items": list_videos_catalog(),
                    "selected_video": env.get("VIDEO_PATH", ""),
                }
                return self._send_json(200, payload)

            if path == "/api/videos/thumbnail":
                video_path = query.get("path", [""])[0]
                if not video_path:
                    raise ValueError("Missing query parameter: path")
                thumb = ensure_video_thumbnail(video_path)
                return self._serve_file(thumb)

            if path == "/api/overlay":
                exists = OVERLAY_PATH.exists()
                payload = {
                    "exists": exists,
                    "url": "/api/file/output/roi_tuning/roi_overlay.png",
                }
                if exists:
                    payload["mtime"] = int(OVERLAY_PATH.stat().st_mtime)
                return self._send_json(200, payload)

            if path == "/api/runs":
                return self._send_json(
                    200,
                    {
                        "runs": list_runs(),
                        "current": snapshot_run_state(),
                    },
                )

            if path == "/api/runs/current":
                return self._send_json(200, snapshot_run_state())

            if path.startswith("/api/runs/"):
                rest = path[len("/api/runs/") :]
                parts = rest.split("/")
                if len(parts) >= 2 and parts[1] == "images":
                    run_id = parts[0]
                    image_type = query.get("type", ["slide"])[0]
                    images = run_images(run_id, image_type)
                    return self._send_json(200, {"images": images})

                if len(parts) >= 2 and parts[1] == "final-slides":
                    run_id = parts[0]
                    items = run_final_slides(run_id)
                    return self._send_json(200, {"items": items})

                if len(parts) >= 2 and parts[1] == "base-events":
                    run_id = parts[0]
                    items = run_base_events(run_id)
                    return self._send_json(200, {"items": items})

                if len(parts) >= 3 and parts[1] == "file":
                    run_id = parts[0]
                    rel = unquote("/".join(parts[2:]))
                    run_dir = ensure_within(RUNS_DIR, RUNS_DIR / run_id)
                    target = ensure_within(run_dir, run_dir / rel)
                    return self._serve_file(target)

                if len(parts) == 1:
                    return self._send_json(200, run_detail(parts[0]))

            if path.startswith("/api/file/"):
                rel = unquote(path[len("/api/file/") :])
                target = ensure_within(ROOT_DIR, ROOT_DIR / rel)
                return self._serve_file(target)

            return self._send_json(404, {"error": "Not found"})
        except FileNotFoundError as exc:
            return self._send_json(404, {"error": str(exc)})
        except ValueError as exc:
            return self._send_json(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            return self._send_json(500, {"error": str(exc)})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == "/api/config":
                data = self._read_json_body()
                video_path = str(data["VIDEO_PATH"]).strip()
                resolve_video_config_path(video_path)
                cfg = {
                    "VIDEO_PATH": video_path,
                    "ROI_X0": int(data["ROI_X0"]),
                    "ROI_Y0": int(data["ROI_Y0"]),
                    "ROI_X1": int(data["ROI_X1"]),
                    "ROI_Y1": int(data["ROI_Y1"]),
                    "KEYFRAME_SETTLE_FRAMES": int(data["KEYFRAME_SETTLE_FRAMES"]),
                    "KEYFRAME_STABLE_END_GUARD_FRAMES": int(data["KEYFRAME_STABLE_END_GUARD_FRAMES"]),
                    "KEYFRAME_STABLE_LOOKAHEAD_FRAMES": int(data["KEYFRAME_STABLE_LOOKAHEAD_FRAMES"]),
                    "SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO": float(data["SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO"]),
                    "SPEAKER_FILTER_MAX_EDGE_DENSITY": float(data["SPEAKER_FILTER_MAX_EDGE_DENSITY"]),
                    "SPEAKER_FILTER_MAX_LAPLACIAN_VAR": float(data["SPEAKER_FILTER_MAX_LAPLACIAN_VAR"]),
                    "SPEAKER_FILTER_MAX_DURATION_SEC": float(data["SPEAKER_FILTER_MAX_DURATION_SEC"]),
                }
                if cfg["ROI_X0"] >= cfg["ROI_X1"] or cfg["ROI_Y0"] >= cfg["ROI_Y1"]:
                    raise ValueError("ROI must satisfy x0 < x1 and y0 < y1")
                if cfg["KEYFRAME_SETTLE_FRAMES"] < 0:
                    raise ValueError("KEYFRAME_SETTLE_FRAMES must be >= 0")
                if cfg["KEYFRAME_STABLE_END_GUARD_FRAMES"] < 0:
                    raise ValueError("KEYFRAME_STABLE_END_GUARD_FRAMES must be >= 0")
                if cfg["KEYFRAME_STABLE_LOOKAHEAD_FRAMES"] < 1:
                    raise ValueError("KEYFRAME_STABLE_LOOKAHEAD_FRAMES must be >= 1")
                if not (0.0 <= cfg["SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO"] <= 1.0):
                    raise ValueError("SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO must be in [0, 1]")
                if not (0.0 <= cfg["SPEAKER_FILTER_MAX_EDGE_DENSITY"] <= 1.0):
                    raise ValueError("SPEAKER_FILTER_MAX_EDGE_DENSITY must be in [0, 1]")
                if cfg["SPEAKER_FILTER_MAX_LAPLACIAN_VAR"] < 0:
                    raise ValueError("SPEAKER_FILTER_MAX_LAPLACIAN_VAR must be >= 0")
                if cfg["SPEAKER_FILTER_MAX_DURATION_SEC"] < 0:
                    raise ValueError("SPEAKER_FILTER_MAX_DURATION_SEC must be >= 0")
                write_config_values(CONFIG_PATH, cfg)
                return self._send_json(200, {"ok": True, **cfg})

            if path == "/api/overlay":
                data = self._read_json_body(optional=True)
                time_sec = float(data.get("time_sec", 30))
                code, output = run_overlay(time_sec)
                if code != 0:
                    return self._send_json(500, {"ok": False, "output": output, "exit_code": code})
                payload = {
                    "ok": True,
                    "output": output,
                    "url": "/api/file/output/roi_tuning/roi_overlay.png",
                    "mtime": int(OVERLAY_PATH.stat().st_mtime) if OVERLAY_PATH.exists() else None,
                }
                return self._send_json(200, payload)

            if path == "/api/runs":
                ok, msg = start_run()
                if not ok:
                    return self._send_json(409, {"ok": False, "error": msg, "current": snapshot_run_state()})
                return self._send_json(202, {"ok": True, "message": msg, "current": snapshot_run_state()})

            return self._send_json(404, {"error": "Not found"})
        except (KeyError, ValueError) as exc:
            return self._send_json(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            return self._send_json(500, {"error": str(exc)})

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        return

    def _serve_static(self, filename: str) -> None:
        target = ensure_within(WEB_DIR, WEB_DIR / filename)
        self._serve_file(target)

    def _serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(str(path))

        ctype, _ = mimetypes.guess_type(str(path))
        if not ctype:
            ctype = "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self, optional: bool = False) -> dict:
        raw_len = self.headers.get("Content-Length")
        if raw_len is None:
            if optional:
                return {}
            raise ValueError("Missing Content-Length")

        length = int(raw_len)
        if length == 0:
            return {}
        body = self.rfile.read(length)
        return json.loads(body.decode("utf-8"))

    def _send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local UI server for scene-detection project")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving on http://{args.host}:{args.port}")
    print(f"Python for helper scripts: {PYTHON_BIN}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
