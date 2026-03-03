#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import re
import signal
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from cloud_tts import ensure_cloud_tts_client, measure_wave_or_pcm_duration, synthesize_cloud_tts_audio

WEB_DIR = ROOT_DIR / "web"
CONFIG_PATH = ROOT_DIR / "config" / "slitranet.env"
GEMINI_PROMPT_PATH = ROOT_DIR / "config" / "gemini_edit_prompt.txt"
GEMINI_TRANSLATE_PROMPT_PATH = ROOT_DIR / "config" / "gemini_translate_prompt.txt"
GEMINI_TEXT_TRANSLATE_PROMPT_PATH = ROOT_DIR / "config" / "gemini_text_translate_prompt.txt"
GEMINI_TTS_PROMPT_PATH = ROOT_DIR / "config" / "gemini_tts_prompt.txt"
LOCAL_ENV_PATH = ROOT_DIR / ".env.local"
OUTPUT_DIR = ROOT_DIR / "output"
RUNS_DIR = OUTPUT_DIR / "runs"
LAB_DIR = OUTPUT_DIR / "ui_lab"
OVERLAY_PATH = OUTPUT_DIR / "roi_tuning" / "roi_overlay.png"
VIDEOS_DIR = ROOT_DIR / "videos"
VIDEO_THUMB_DIR = OUTPUT_DIR / "ui" / "video_thumbs"
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}

VENV_PY = ROOT_DIR / ".venv" / "bin" / "python"
PYTHON_BIN = str(VENV_PY if VENV_PY.exists() else Path(sys.executable))

RUN_ID_PATTERN = re.compile(r"^(?:\d{8}_\d{6}|\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})$")
STEP_MARKER_RE = re.compile(r"^@@STEP\s+(START|DONE|SKIP|DETAIL)\s+([a-z0-9-]+)(?:\s+(.*))?$")
STEP_DEFS = [
    ("slide-detection", "Slide Detection"),
    ("transcription", "Transcription"),
    ("transcript-mapping", "Transcript Mapping"),
    ("finalize-slides", "Finalize Slides"),
    ("edit", "Slide Edit"),
    ("translate", "Slide Translate"),
    ("upscale", "Slide Upscale"),
    ("text-translate", "Text Translate"),
    ("tts", "TTS"),
    ("video-export", "Video Export"),
]
STEP_LABELS = {step_id: label for step_id, label in STEP_DEFS}

RUN_LOCK = threading.Lock()
RUN_STATE = {
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "run_id": None,
    "exit_code": None,
    "log_tail": deque(maxlen=600),
    "process": None,
    "current_step": None,
    "current_detail": "",
    "step_statuses": {},
    "stop_requested": False,
    "stopping": False,
    "error_step": None,
}


def make_step_statuses() -> dict[str, dict[str, str]]:
    return {
        step_id: {"status": "pending", "detail": ""}
        for step_id, _label in STEP_DEFS
    }


RUN_STATE["step_statuses"] = make_step_statuses()

LAB_LOCK = threading.Lock()
LAB_STATE = {
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "job_id": None,
    "action": "",
    "provider": "",
    "run_id": None,
    "event_id": None,
    "input_name": "",
    "original_url": "",
    "result_url": "",
    "result_name": "",
    "estimated_cost_usd": 0.0,
    "manifest_path": "",
    "message": "",
    "log_tail": deque(maxlen=400),
    "process": None,
}


def run_status_path(run_dir: Path) -> Path:
    return run_dir / "run_status.json"


def write_run_status(run_dir: Path, payload: dict) -> None:
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        run_status_path(run_dir).write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass


def read_run_status(run_dir: Path) -> dict:
    raw = read_json_file(run_status_path(run_dir))
    return raw if isinstance(raw, dict) else {}


def current_state_for_run(run_id: str) -> dict | None:
    with RUN_LOCK:
        if RUN_STATE.get("run_id") != run_id:
            return None
        status = str(RUN_STATE.get("status", "") or "")
        if not status or status == "idle":
            return None
        return {
            "status": status,
            "started_at": RUN_STATE.get("started_at"),
            "finished_at": RUN_STATE.get("finished_at"),
            "exit_code": RUN_STATE.get("exit_code"),
            "current_step": RUN_STATE.get("current_step") or "",
            "current_detail": RUN_STATE.get("current_detail") or "",
            "error_step": RUN_STATE.get("error_step") or "",
        }


def effective_run_status(run_dir: Path, run_id: str) -> dict:
    current = current_state_for_run(run_id)
    if current:
        return current
    recorded = read_run_status(run_dir)
    if recorded:
        return {
            "status": str(recorded.get("status", "") or ""),
            "started_at": recorded.get("started_at"),
            "finished_at": recorded.get("finished_at"),
            "exit_code": recorded.get("exit_code"),
            "current_step": str(recorded.get("current_step", "") or ""),
            "current_detail": str(recorded.get("current_detail", "") or ""),
            "error_step": str(recorded.get("error_step", "") or ""),
        }
    return {
        "status": "",
        "started_at": None,
        "finished_at": None,
        "exit_code": None,
        "current_step": "",
        "current_detail": "",
        "error_step": "",
    }


def artifact_availability(run_dir: Path) -> dict[str, object]:
    base_csv = run_dir / "slitranet" / "slide_changes.csv"
    final_csv = run_dir / "slitranet" / "slide_text_map_final.csv"
    slide_dir = run_dir / "slitranet" / "keyframes" / "slide"
    final_slide_dir = run_dir / "slitranet" / "keyframes" / "final" / "slide"
    translated_slide_dir = run_dir / "slitranet" / "keyframes" / "final" / "slide_translated"
    upscaled_slide_dir = run_dir / "slitranet" / "keyframes" / "final" / "slide_upscaled"
    translated_upscaled_slide_dir = run_dir / "slitranet" / "keyframes" / "final" / "slide_translated_upscaled"
    translated_text_csv = run_dir / "slitranet" / "slide_text_map_final_translated.csv"
    tts_audio_dir = run_dir / "slitranet" / "tts" / "audio"
    video_export_dir = run_dir / "slitranet" / "video_export"
    exported_video = latest_file_in_dir(video_export_dir, ".mp4")

    base_events_ready = base_csv.exists() and csv_event_count(base_csv) > 0
    final_slides_ready = final_csv.exists() and count_files(final_slide_dir) > 0
    translated_slides_ready = count_files(translated_slide_dir) > 0
    upscaled_slides_ready = count_files(upscaled_slide_dir) > 0
    translated_upscaled_slides_ready = count_files(translated_upscaled_slide_dir) > 0
    translated_text_ready = translated_text_csv.exists() and csv_event_count(translated_text_csv) > 0
    tts_ready = count_files(tts_audio_dir) > 0
    video_export_ready = exported_video is not None

    highest_available = "none"
    highest_available_label = "no output yet"
    if video_export_ready:
        highest_available = "video_export"
        highest_available_label = "video export"
    elif tts_ready:
        highest_available = "tts"
        highest_available_label = "tts audio"
    elif translated_upscaled_slides_ready:
        highest_available = "translated_upscaled_slides"
        highest_available_label = "translated upscaled slides"
    elif upscaled_slides_ready:
        highest_available = "upscaled_slides"
        highest_available_label = "upscaled slides"
    elif translated_slides_ready:
        highest_available = "translated_slides"
        highest_available_label = "translated slides"
    elif final_slides_ready:
        highest_available = "final_slides"
        highest_available_label = "final slides"
    elif base_events_ready:
        highest_available = "base_events"
        highest_available_label = "base events"

    return {
        "base_events_ready": base_events_ready,
        "final_slides_ready": final_slides_ready,
        "translated_slides_ready": translated_slides_ready,
        "upscaled_slides_ready": upscaled_slides_ready,
        "translated_upscaled_slides_ready": translated_upscaled_slides_ready,
        "translated_text_ready": translated_text_ready,
        "tts_ready": tts_ready,
        "video_export_ready": video_export_ready,
        "highest_available": highest_available,
        "highest_available_label": highest_available_label,
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


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for key, value in parse_env(path).items():
        os.environ.setdefault(key, value)


load_local_env(LOCAL_ENV_PATH)


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


def read_text_file(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def write_text_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    path.write_text(normalized.rstrip("\n") + "\n", encoding="utf-8")


def read_json_file(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def ensure_within(base: Path, target: Path) -> Path:
    base_resolved = base.resolve()
    target_resolved = target.resolve()
    if base_resolved == target_resolved:
        return target_resolved
    if base_resolved not in target_resolved.parents:
        raise ValueError("Path traversal blocked")
    return target_resolved


def api_file_url_for(path: Path) -> str:
    rel = ensure_within(ROOT_DIR, path).relative_to(ROOT_DIR).as_posix()
    return f"/api/file/{rel}"


def count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.iterdir() if p.is_file())


def summarize_upscale_manifest(path: Path) -> dict[str, float | int | str]:
    raw = read_json_file(path)
    if not isinstance(raw, dict):
        return {
            "provider": "",
            "items_processed": 0,
            "upscaled": 0,
            "fallback": 0,
            "total_estimated_cost_usd": 0.0,
        }

    summary = raw.get("summary")
    items = raw.get("items")
    items = items if isinstance(items, list) else []
    if not isinstance(summary, dict):
        upscaled = sum(
            1
            for item in items
            if isinstance(item, dict) and item.get("status") in {"upscaled", "succeeded"}
        )
        fallback = len(items) - upscaled
        total_cost = 0.0
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                total_cost += float(item.get("estimated_cost_usd", 0.0) or 0.0)
            except Exception:
                continue
        summary = {
            "items_processed": len(items),
            "upscaled": upscaled,
            "fallback": fallback,
            "total_estimated_cost_usd": round(total_cost, 6),
        }
    elif items:
        # Prefer item-derived counts so older manifests with a bad summary can still render correctly.
        upscaled = sum(
            1
            for item in items
            if isinstance(item, dict) and item.get("status") in {"upscaled", "succeeded"}
        )
        fallback = len(items) - upscaled
        total_cost = 0.0
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                total_cost += float(item.get("estimated_cost_usd", 0.0) or 0.0)
            except Exception:
                continue
        summary = {
            **summary,
            "items_processed": len(items),
            "upscaled": upscaled,
            "fallback": fallback,
            "total_estimated_cost_usd": round(total_cost, 6),
        }

    def _num(key: str) -> float:
        try:
            return float(summary.get(key, 0.0) or 0.0)
        except Exception:
            return 0.0

    def _int(key: str) -> int:
        try:
            return int(summary.get(key, 0) or 0)
        except Exception:
            return 0

    return {
        "provider": str(raw.get("provider", "") or ""),
        "items_processed": _int("items_processed"),
        "upscaled": _int("upscaled"),
        "fallback": _int("fallback"),
        "total_estimated_cost_usd": round(_num("total_estimated_cost_usd"), 6),
    }


def summarize_run_upscale_cost(run_dir: Path) -> dict[str, float | int | str]:
    total_cost = 0.0
    provider = ""
    manifest_count = 0
    for rel in (
        "slitranet/keyframes/final/upscale_manifest.json",
        "slitranet/keyframes/final/upscale_translated_manifest.json",
    ):
        summary = summarize_upscale_manifest(run_dir / rel)
        if summary["items_processed"]:
            manifest_count += 1
        total_cost += float(summary["total_estimated_cost_usd"])
        if not provider and summary["provider"]:
            provider = str(summary["provider"])
    return {
        "provider": provider,
        "manifest_count": manifest_count,
        "upscale_estimated_cost_usd": round(total_cost, 6),
    }


def latest_file_in_dir(path: Path, suffix: str) -> Path | None:
    if not path.exists():
        return None
    files = sorted(
        (p for p in path.iterdir() if p.is_file() and p.suffix.lower() == suffix.lower()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


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
        translated_slide_dir = entry / "slitranet" / "keyframes" / "final" / "slide_translated"
        upscaled_slide_dir = entry / "slitranet" / "keyframes" / "final" / "slide_upscaled"
        translated_upscaled_slide_dir = (
            entry / "slitranet" / "keyframes" / "final" / "slide_translated_upscaled"
        )
        translated_text_csv = entry / "slitranet" / "slide_text_map_final_translated.csv"
        tts_audio_dir = entry / "slitranet" / "tts" / "audio"
        video_export_dir = entry / "slitranet" / "video_export"
        exported_video = latest_file_in_dir(video_export_dir, ".mp4")
        full_dir = entry / "slitranet" / "keyframes" / "full"
        config_used = parse_env(entry / "config_used.env") if (entry / "config_used.env").exists() else {}
        upscale_summary = summarize_run_upscale_cost(entry)
        run_status = effective_run_status(entry, entry.name)
        artifacts = artifact_availability(entry)
        runs.append(
            {
                "id": entry.name,
                "path": str(entry),
                "has_csv": csv_path.exists(),
                "event_count": csv_event_count(csv_path),
                "final_event_count": csv_event_count(final_csv_path),
                "slide_images": count_files(slide_dir),
                "final_slide_images": count_files(final_slide_dir),
                "translated_slide_images": count_files(translated_slide_dir),
                "upscaled_slide_images": count_files(upscaled_slide_dir),
                "translated_upscaled_slide_images": count_files(translated_upscaled_slide_dir),
                "translated_text_events": csv_event_count(translated_text_csv),
                "tts_segments": count_files(tts_audio_dir),
                "exported_video_name": exported_video.name if exported_video else "",
                "full_images": count_files(full_dir),
                "upscale_mode_used": config_used.get("FINAL_SLIDE_UPSCALE_MODE", ""),
                "upscale_estimated_cost_usd": upscale_summary["upscale_estimated_cost_usd"],
                "run_status": run_status["status"],
                "error_step": run_status["error_step"],
                "current_step": run_status["current_step"],
                "highest_available": artifacts["highest_available"],
                "highest_available_label": artifacts["highest_available_label"],
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
    translated_slide_dir = run_dir / "slitranet" / "keyframes" / "final" / "slide_translated"
    upscaled_slide_dir = run_dir / "slitranet" / "keyframes" / "final" / "slide_upscaled"
    translated_upscaled_slide_dir = run_dir / "slitranet" / "keyframes" / "final" / "slide_translated_upscaled"
    translated_text_csv = run_dir / "slitranet" / "slide_text_map_final_translated.csv"
    translated_text_json = run_dir / "slitranet" / "slide_text_map_final_translated.json"
    tts_audio_dir = run_dir / "slitranet" / "tts" / "audio"
    tts_manifest_json = run_dir / "slitranet" / "tts" / "tts_manifest.json"
    video_export_dir = run_dir / "slitranet" / "video_export"
    video_timeline_json = video_export_dir / "timeline.json"
    video_timeline_csv = video_export_dir / "timeline.csv"
    exported_video = latest_file_in_dir(video_export_dir, ".mp4")
    exported_srt = latest_file_in_dir(video_export_dir, ".srt")
    full_dir = run_dir / "slitranet" / "keyframes" / "full"
    config_used = parse_env(run_dir / "config_used.env") if (run_dir / "config_used.env").exists() else {}
    upscale_summary = summarize_run_upscale_cost(run_dir)
    run_status = effective_run_status(run_dir, run_id)
    artifacts = artifact_availability(run_dir)

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
        "translated_slide_images": count_files(translated_slide_dir),
        "upscaled_slide_images": count_files(upscaled_slide_dir),
        "translated_upscaled_slide_images": count_files(translated_upscaled_slide_dir),
        "translated_text_events": csv_event_count(translated_text_csv),
        "translated_text_json_url": f"/api/runs/{run_id}/file/slitranet/slide_text_map_final_translated.json" if translated_text_json.exists() else "",
        "translated_text_csv_url": f"/api/runs/{run_id}/file/slitranet/slide_text_map_final_translated.csv" if translated_text_csv.exists() else "",
        "tts_segments": count_files(tts_audio_dir),
        "tts_manifest_url": f"/api/runs/{run_id}/file/slitranet/tts/tts_manifest.json" if tts_manifest_json.exists() else "",
        "video_timeline_json_url": f"/api/runs/{run_id}/file/slitranet/video_export/timeline.json" if video_timeline_json.exists() else "",
        "video_timeline_csv_url": f"/api/runs/{run_id}/file/slitranet/video_export/timeline.csv" if video_timeline_csv.exists() else "",
        "exported_video_name": exported_video.name if exported_video else "",
        "exported_video_url": f"/api/runs/{run_id}/file/{exported_video.relative_to(run_dir).as_posix()}" if exported_video else "",
        "exported_srt_url": f"/api/runs/{run_id}/file/{exported_srt.relative_to(run_dir).as_posix()}" if exported_srt else "",
        "full_images": count_files(full_dir),
        "upscale_mode_used": config_used.get("FINAL_SLIDE_UPSCALE_MODE", ""),
        "upscale_estimated_cost_usd": upscale_summary["upscale_estimated_cost_usd"],
        "run_status": run_status["status"],
        "run_started_at": run_status["started_at"],
        "run_finished_at": run_status["finished_at"],
        "run_exit_code": run_status["exit_code"],
        "current_step": run_status["current_step"],
        "current_detail": run_status["current_detail"],
        "error_step": run_status["error_step"],
        **artifacts,
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


def final_image_mode_overrides_path(run_dir: Path) -> Path:
    return run_dir / "slitranet" / "final_image_mode_overrides.json"


def load_final_image_mode_overrides(run_dir: Path) -> dict[int, str]:
    path = final_image_mode_overrides_path(run_dir)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}

    out: dict[int, str] = {}
    for key, value in raw.items():
        if value not in {"slide", "full"}:
            continue
        try:
            out[int(key)] = value
        except Exception:
            continue
    return out


def save_final_image_mode_overrides(run_dir: Path, overrides: dict[int, str]) -> None:
    path = final_image_mode_overrides_path(run_dir)
    payload = {str(k): v for k, v in sorted(overrides.items()) if v in {"slide", "full"}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


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


def resolve_final_image_assets(run_dir: Path, run_id: str, event_id: int, override_mode: str | None = None) -> dict:
    slide_rel = _find_event_image_rel(run_dir, event_id, ["slide"], include_final=True)
    raw_slide_rel = _find_event_image_rel(run_dir, event_id, ["slide_raw"], include_final=True)
    translated_slide_rel = _find_event_image_rel(run_dir, event_id, ["slide_translated"], include_final=True)
    upscaled_slide_rel = _find_event_image_rel(run_dir, event_id, ["slide_upscaled"], include_final=True)
    translated_upscaled_slide_rel = _find_event_image_rel(
        run_dir,
        event_id,
        ["slide_translated_upscaled"],
        include_final=True,
    )
    full_rel = _find_event_image_rel(run_dir, event_id, ["full"], include_final=True)
    available_modes = [mode for mode, rel in (("slide", slide_rel), ("full", full_rel)) if rel]

    default_mode = "full" if event_id == 1 else "slide"
    if default_mode not in available_modes and available_modes:
        default_mode = available_modes[0]

    requested_mode = override_mode if override_mode in {"slide", "full"} else default_mode
    if requested_mode not in available_modes and available_modes:
        requested_mode = default_mode if default_mode in available_modes else available_modes[0]

    selected_rel = ""
    if requested_mode == "full" and full_rel:
        selected_rel = full_rel
    elif requested_mode == "slide" and slide_rel:
        selected_rel = slide_rel
    elif slide_rel:
        selected_rel = slide_rel
        requested_mode = "slide"
    elif full_rel:
        selected_rel = full_rel
        requested_mode = "full"
    else:
        requested_mode = ""

    return {
        "default_image_mode": default_mode if available_modes else "",
        "image_mode": requested_mode,
        "available_image_modes": available_modes,
        "slide_image_url": f"/api/runs/{run_id}/file/{slide_rel}" if slide_rel else "",
        "slide_image_name": Path(slide_rel).name if slide_rel else "",
        "processed_slide_image_url": f"/api/runs/{run_id}/file/{slide_rel}" if slide_rel else "",
        "processed_slide_image_name": Path(slide_rel).name if slide_rel else "",
        "raw_slide_image_url": f"/api/runs/{run_id}/file/{raw_slide_rel}" if raw_slide_rel else "",
        "raw_slide_image_name": Path(raw_slide_rel).name if raw_slide_rel else "",
        "translated_slide_image_url": f"/api/runs/{run_id}/file/{translated_slide_rel}" if translated_slide_rel else "",
        "translated_slide_image_name": Path(translated_slide_rel).name if translated_slide_rel else "",
        "processed_upscaled_slide_image_url": f"/api/runs/{run_id}/file/{upscaled_slide_rel}" if upscaled_slide_rel else "",
        "processed_upscaled_slide_image_name": Path(upscaled_slide_rel).name if upscaled_slide_rel else "",
        "translated_upscaled_slide_image_url": (
            f"/api/runs/{run_id}/file/{translated_upscaled_slide_rel}" if translated_upscaled_slide_rel else ""
        ),
        "translated_upscaled_slide_image_name": (
            Path(translated_upscaled_slide_rel).name if translated_upscaled_slide_rel else ""
        ),
        "full_image_url": f"/api/runs/{run_id}/file/{full_rel}" if full_rel else "",
        "full_image_name": Path(full_rel).name if full_rel else "",
        "image_url": f"/api/runs/{run_id}/file/{selected_rel}" if selected_rel else "",
        "image_name": Path(selected_rel).name if selected_rel else "",
    }


def run_final_slides(run_id: str) -> list[dict]:
    if not RUN_ID_PATTERN.match(run_id):
        raise ValueError("Invalid run id")
    run_dir = ensure_within(RUNS_DIR, RUNS_DIR / run_id)
    final_csv = run_dir / "slitranet" / "slide_text_map_final.csv"
    if not final_csv.exists():
        return []
    overrides = load_final_image_mode_overrides(run_dir)
    translated_map = read_json_file(run_dir / "slitranet" / "slide_text_map_final_translated.json")
    translated_text_by_event: dict[int, str] = {}
    if isinstance(translated_map, dict):
        translated_events = translated_map.get("events")
        if isinstance(translated_events, list):
            for event in translated_events:
                if not isinstance(event, dict):
                    continue
                try:
                    translated_event_id = int(event.get("event_id", "0") or "0")
                except Exception:
                    continue
                if translated_event_id <= 0:
                    continue
                translated_text_by_event[translated_event_id] = str(event.get("translated_text", "") or "").strip()

    items: list[dict] = []
    with final_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            event_id = int(row.get("event_id", "0") or "0")
            if event_id <= 0:
                continue
            assets = resolve_final_image_assets(run_dir, run_id, event_id, overrides.get(event_id))
            items.append(
                {
                    "index": idx,
                    "event_id": event_id,
                    "bucket_id": row.get("bucket_id", ""),
                    "slide_start": float(row.get("slide_start", "0") or "0"),
                    "slide_end": float(row.get("slide_end", "0") or "0"),
                    "text": (row.get("text", "") or "").strip(),
                    "translated_text": translated_text_by_event.get(event_id, ""),
                    "segments_count": int(row.get("segments_count", "0") or "0"),
                    "source_segment_ids": row.get("source_segment_ids", "") or "",
                    "source_mode_auto": row.get("source_mode_auto", "") or "",
                    "source_mode_final": row.get("source_mode_final", "") or "",
                    "source_reason": row.get("source_reason", "") or "",
                    "source_confidence": float(row.get("source_confidence", "0") or "0"),
                    **assets,
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


def list_lab_images() -> dict:
    run_id = latest_run_id()
    if not run_id:
        return {"latest_run_id": None, "items": []}

    items = run_final_slides(run_id)
    out: list[dict] = []
    for item in items:
        image_url = item.get("processed_slide_image_url") or item.get("image_url") or ""
        image_name = item.get("processed_slide_image_name") or item.get("image_name") or f"event_{item['event_id']}"
        if not image_url:
            continue
        out.append(
            {
                "run_id": run_id,
                "event_id": int(item["event_id"]),
                "name": image_name,
                "image_url": image_url,
                "slide_start": float(item.get("slide_start", 0.0) or 0.0),
                "slide_end": float(item.get("slide_end", 0.0) or 0.0),
                "text": str(item.get("text", "") or "").strip(),
                "source_mode_final": str(item.get("source_mode_final", "") or ""),
            }
        )
    return {"latest_run_id": run_id, "items": out}


def _lab_job_id(action: str) -> str:
    return f"{time.strftime('%Y-%m-%d_%H-%M-%S')}_{action}_{int(time.time() * 1000) % 1000:03d}"


def start_lab_job(action: str, run_id: str, event_id: int, provider: str = "") -> tuple[bool, str]:
    if action not in {"edit", "translate", "upscale"}:
        return False, "Invalid lab action"
    if not RUN_ID_PATTERN.match(run_id):
        return False, "Invalid run id"
    if event_id <= 0:
        return False, "event_id must be > 0"

    with RUN_LOCK:
        proc = RUN_STATE.get("process")
        if proc is not None and proc.poll() is None:
            return False, "A main run is currently in progress"

    run_dir = ensure_within(RUNS_DIR, RUNS_DIR / run_id)
    if not run_dir.exists():
        return False, "Run not found"
    source_rel = _find_event_image_rel(run_dir, event_id, ["slide"], include_final=True)
    if not source_rel:
        return False, f"No processed final slide found for event {event_id}"

    source_path = ensure_within(run_dir, run_dir / source_rel)
    env = parse_env(CONFIG_PATH)
    provider = provider.strip().lower()

    if action == "edit":
        mode = (env.get("FINAL_SLIDE_POSTPROCESS_MODE", "local") or "local").strip().lower()
        if mode != "gemini":
            return False, "Image Lab edit currently requires FINAL_SLIDE_POSTPROCESS_MODE=gemini"
        if not (os.environ.get("GEMINI_API_KEY") or "").strip():
            return False, "GEMINI_API_KEY is not set in the server environment"
    elif action == "translate":
        mode = (env.get("FINAL_SLIDE_TRANSLATION_MODE", "none") or "none").strip().lower()
        if mode != "gemini":
            return False, "Image Lab translate currently requires FINAL_SLIDE_TRANSLATION_MODE=gemini"
        if not (os.environ.get("GEMINI_API_KEY") or "").strip():
            return False, "GEMINI_API_KEY is not set in the server environment"
        if not (env.get("FINAL_SLIDE_TARGET_LANGUAGE", "") or "").strip():
            return False, "FINAL_SLIDE_TARGET_LANGUAGE must not be empty"
    else:
        mode = provider or (env.get("FINAL_SLIDE_UPSCALE_MODE", "none") or "none").strip().lower()
        if mode not in {"swin2sr", "replicate_nightmare_realesrgan"}:
            return False, "Image Lab upscale requires one of: swin2sr, replicate_nightmare_realesrgan"
        if mode == "replicate_nightmare_realesrgan" and not (os.environ.get("REPLICATE_API_TOKEN") or "").strip():
            return False, "REPLICATE_API_TOKEN is not set in the server environment"

    job_id = _lab_job_id(action)
    job_dir = LAB_DIR / job_id
    input_dir = job_dir / "input"
    output_dir = job_dir / "output"
    original_dir = job_dir / "original"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    original_dir.mkdir(parents=True, exist_ok=True)

    original_copy = original_dir / source_path.name
    input_copy = input_dir / source_path.name
    shutil.copy2(source_path, original_copy)
    shutil.copy2(source_path, input_copy)
    result_path = output_dir / source_path.name

    if action == "edit":
        cmd = [
            PYTHON_BIN,
            "scripts/edit_final_slides_gemini.py",
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--model",
            (env.get("GEMINI_EDIT_MODEL", "gemini-3-pro-image-preview") or "gemini-3-pro-image-preview").strip(),
            "--prompt-file",
            str(GEMINI_PROMPT_PATH),
            "--skip-first-slide",
            "0",
        ]
        message = "Running Gemini edit on selected final slide."
    elif action == "translate":
        cmd = [
            PYTHON_BIN,
            "scripts/translate_final_slides_gemini.py",
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--model",
            (env.get("GEMINI_TRANSLATE_MODEL", "gemini-3-pro-image-preview") or "gemini-3-pro-image-preview").strip(),
            "--prompt-file",
            str(GEMINI_TRANSLATE_PROMPT_PATH),
            "--target-language",
            (env.get("FINAL_SLIDE_TARGET_LANGUAGE", "") or "").strip(),
        ]
        message = "Running Gemini translate on selected final slide."
    else:
        if mode == "swin2sr":
            cmd = [
                PYTHON_BIN,
                "scripts/upscale_final_slides_swin2sr.py",
                "--input-dir",
                str(input_dir),
                "--output-dir",
                str(output_dir),
                "--model-id",
                (env.get("FINAL_SLIDE_UPSCALE_MODEL", "") or "caidas/swin2SR-classical-sr-x4-64").strip(),
                "--device",
                (env.get("FINAL_SLIDE_UPSCALE_DEVICE", "auto") or "auto").strip(),
                "--tile-size",
                str(int(env.get("FINAL_SLIDE_UPSCALE_TILE_SIZE", "256") or "256")),
                "--tile-overlap",
                str(int(env.get("FINAL_SLIDE_UPSCALE_TILE_OVERLAP", "24") or "24")),
            ]
            message = "Running local Swin2SR upscale on selected final slide."
        else:
            replicate_provider = "nightmare_realesrgan"
            cmd = [
                PYTHON_BIN,
                "scripts/upscale_final_slides_replicate.py",
                "--input-dir",
                str(input_dir),
                "--output-dir",
                str(output_dir),
                "--provider",
                replicate_provider,
                "--concurrency",
                "1",
                "--manifest-path",
                str(job_dir / "replicate_manifest.json"),
                "--nightmare-realesrgan-model-ref",
                (
                    env.get("REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF", "nightmareai/real-esrgan")
                    or "nightmareai/real-esrgan"
                ).strip(),
                "--nightmare-realesrgan-version-id",
                (
                    env.get(
                        "REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID",
                        "f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa",
                    )
                    or "f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa"
                ).strip(),
                "--nightmare-realesrgan-scale",
                "4",
                "--nightmare-realesrgan-face-enhance",
                "false",
                "--nightmare-realesrgan-price-per-second",
                str(
                    float(
                        env.get("REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND", "0.000225")
                        or "0.000225"
                    )
                ),
            ]
            message = "Running Replicate nightmareai/real-esrgan upscale on selected final slide."

    with LAB_LOCK:
        proc = LAB_STATE.get("process")
        if proc is not None and proc.poll() is None:
            return False, "Another Image Lab job is already in progress"

        LAB_STATE["status"] = "running"
        LAB_STATE["started_at"] = _now()
        LAB_STATE["finished_at"] = None
        LAB_STATE["job_id"] = job_id
        LAB_STATE["action"] = action
        LAB_STATE["provider"] = mode if action == "upscale" else ""
        LAB_STATE["run_id"] = run_id
        LAB_STATE["event_id"] = event_id
        LAB_STATE["input_name"] = source_path.name
        LAB_STATE["original_url"] = api_file_url_for(original_copy)
        LAB_STATE["result_url"] = api_file_url_for(result_path)
        LAB_STATE["result_name"] = result_path.name
        LAB_STATE["estimated_cost_usd"] = 0.0
        LAB_STATE["manifest_path"] = (
            str(job_dir / "replicate_manifest.json")
            if action == "upscale" and mode == "replicate_nightmare_realesrgan"
            else ""
        )
        LAB_STATE["message"] = message
        LAB_STATE["log_tail"].clear()
        LAB_STATE["log_tail"].append(f"[Lab] action={action}")
        if action == "upscale" and mode:
            LAB_STATE["log_tail"].append(f"[Lab] provider={mode}")
        LAB_STATE["log_tail"].append(f"[Lab] input={source_path.name}")

        process = subprocess.Popen(
            cmd,
            cwd=str(ROOT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            start_new_session=True,
        )
        LAB_STATE["process"] = process

    thread = threading.Thread(target=_lab_worker, args=(process,), daemon=True)
    thread.start()
    return True, "started"


def _now() -> int:
    return int(time.time())


def snapshot_steps() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for step_id, label in STEP_DEFS:
        info = RUN_STATE["step_statuses"].get(step_id, {})
        items.append(
            {
                "id": step_id,
                "label": label,
                "status": str(info.get("status", "pending") or "pending"),
                "detail": str(info.get("detail", "") or ""),
            }
        )
    return items


def set_step_state(
    step_id: str,
    status: str,
    detail: str = "",
    *,
    keep_current: bool = False,
) -> None:
    if step_id not in STEP_LABELS:
        return
    RUN_STATE["step_statuses"].setdefault(step_id, {"status": "pending", "detail": ""})
    RUN_STATE["step_statuses"][step_id]["status"] = status
    if detail or status in {"done", "skipped", "error", "stopped"}:
        RUN_STATE["step_statuses"][step_id]["detail"] = detail
    if status == "running":
        RUN_STATE["current_step"] = step_id
        RUN_STATE["current_detail"] = detail
    elif not keep_current and RUN_STATE.get("current_step") == step_id:
        RUN_STATE["current_step"] = None
        RUN_STATE["current_detail"] = ""
    elif RUN_STATE.get("current_step") == step_id and detail:
        RUN_STATE["current_detail"] = detail
    if status == "error":
        RUN_STATE["error_step"] = step_id


def parse_step_marker(line: str) -> tuple[str, str, str] | None:
    match = STEP_MARKER_RE.match(line.strip())
    if not match:
        return None
    action = match.group(1).upper()
    step_id = match.group(2)
    detail = (match.group(3) or "").strip()
    return action, step_id, detail


def apply_step_marker(line: str) -> bool:
    parsed = parse_step_marker(line)
    if not parsed:
        return False
    action, step_id, detail = parsed
    with RUN_LOCK:
        if action == "START":
            set_step_state(step_id, "running", detail)
        elif action == "DONE":
            set_step_state(step_id, "done", detail, keep_current=True)
        elif action == "SKIP":
            set_step_state(step_id, "skipped", detail, keep_current=True)
        elif action == "DETAIL":
            if step_id in STEP_LABELS:
                RUN_STATE["step_statuses"].setdefault(step_id, {"status": "pending", "detail": ""})
                RUN_STATE["step_statuses"][step_id]["detail"] = detail
                if RUN_STATE["step_statuses"][step_id]["status"] == "pending":
                    RUN_STATE["step_statuses"][step_id]["status"] = "running"
                RUN_STATE["current_step"] = step_id
                RUN_STATE["current_detail"] = detail
        current_step = RUN_STATE.get("current_step")
        if current_step and RUN_STATE["step_statuses"].get(current_step, {}).get("status") != "running":
            RUN_STATE["current_step"] = next(
                (
                    step_id
                    for step_id, _label in STEP_DEFS
                    if RUN_STATE["step_statuses"].get(step_id, {}).get("status") == "running"
                ),
                None,
            )
            RUN_STATE["current_detail"] = (
                RUN_STATE["step_statuses"].get(RUN_STATE["current_step"], {}).get("detail", "")
                if RUN_STATE["current_step"]
                else ""
            )
    return True


def finalize_run_state(code: int, run_id: str | None = None) -> None:
    with RUN_LOCK:
        RUN_STATE["exit_code"] = code
        if RUN_STATE["finished_at"] is None:
            RUN_STATE["finished_at"] = _now()
        stopped = bool(RUN_STATE.get("stop_requested"))
        current_step = RUN_STATE.get("current_step")
        if current_step and RUN_STATE["step_statuses"].get(current_step, {}).get("status") == "running":
            terminal = "stopped" if stopped else ("done" if code == 0 else "error")
            set_step_state(
                current_step,
                terminal,
                RUN_STATE["step_statuses"].get(current_step, {}).get("detail", ""),
            )
        RUN_STATE["status"] = "stopped" if stopped else ("done" if code == 0 else "error")
        RUN_STATE["process"] = None
        RUN_STATE["stopping"] = False
        RUN_STATE["stop_requested"] = False
        if code != 0 and not stopped and not RUN_STATE.get("error_step"):
            RUN_STATE["error_step"] = current_step
        if run_id and not RUN_STATE.get("run_id"):
            RUN_STATE["run_id"] = run_id
        elif not RUN_STATE.get("run_id"):
            RUN_STATE["run_id"] = latest_run_id()
        final_run_id = str(RUN_STATE.get("run_id") or "")
        payload = {
            "status": RUN_STATE["status"],
            "started_at": RUN_STATE.get("started_at"),
            "finished_at": RUN_STATE.get("finished_at"),
            "exit_code": RUN_STATE.get("exit_code"),
            "current_step": RUN_STATE.get("current_step") or "",
            "current_detail": RUN_STATE.get("current_detail") or "",
            "error_step": RUN_STATE.get("error_step") or "",
        }
    if final_run_id:
        run_dir = RUNS_DIR / final_run_id
        if run_dir.exists():
            write_run_status(run_dir, payload)


def snapshot_lab_state() -> dict:
    reconcile_lab_state()
    with LAB_LOCK:
        return {
            "status": LAB_STATE["status"],
            "started_at": LAB_STATE["started_at"],
            "finished_at": LAB_STATE["finished_at"],
            "job_id": LAB_STATE["job_id"],
            "action": LAB_STATE["action"],
            "provider": LAB_STATE["provider"],
            "run_id": LAB_STATE["run_id"],
            "event_id": LAB_STATE["event_id"],
            "input_name": LAB_STATE["input_name"],
            "original_url": LAB_STATE["original_url"],
            "result_url": LAB_STATE["result_url"],
            "result_name": LAB_STATE["result_name"],
            "estimated_cost_usd": LAB_STATE["estimated_cost_usd"],
            "message": LAB_STATE["message"],
            "log_tail": list(LAB_STATE["log_tail"]),
        }


def finalize_lab_state(code: int) -> None:
    with LAB_LOCK:
        manifest_path = Path(LAB_STATE["manifest_path"]) if LAB_STATE.get("manifest_path") else None
        LAB_STATE["finished_at"] = _now()
        LAB_STATE["status"] = "done" if code == 0 else "error"
        LAB_STATE["process"] = None
        LAB_STATE["estimated_cost_usd"] = 0.0
        if manifest_path and manifest_path.exists():
            summary = summarize_upscale_manifest(manifest_path)
            LAB_STATE["estimated_cost_usd"] = float(summary["total_estimated_cost_usd"] or 0.0)
        if code != 0 and not LAB_STATE["message"]:
            LAB_STATE["message"] = "Lab job failed."


def reconcile_lab_state() -> None:
    with LAB_LOCK:
        proc = LAB_STATE.get("process")
        if proc is None:
            return
        code = proc.poll()
        if code is None:
            return
    finalize_lab_state(code)


def _lab_worker(process: subprocess.Popen) -> None:
    try:
        assert process.stdout is not None
        for raw in process.stdout:
            line = raw.rstrip("\n")
            if line.startswith("@@STEP "):
                continue
            with LAB_LOCK:
                LAB_STATE["log_tail"].append(line)
    finally:
        code = process.wait()
        finalize_lab_state(code)


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
            "current_step": RUN_STATE["current_step"],
            "current_detail": RUN_STATE["current_detail"],
            "steps": snapshot_steps(),
            "stop_requested": bool(RUN_STATE["stop_requested"]),
            "stopping": bool(RUN_STATE["stopping"]),
            "error_step": RUN_STATE["error_step"],
        }


def reconcile_run_state() -> None:
    with RUN_LOCK:
        proc = RUN_STATE.get("process")
        if proc is None:
            return
        code = proc.poll()
        if code is None:
            return
    finalize_run_state(code)


def _run_worker(process: subprocess.Popen) -> None:
    run_id: str | None = None
    try:
        assert process.stdout is not None
        for raw in process.stdout:
            line = raw.rstrip("\n")
            if apply_step_marker(line):
                continue
            with RUN_LOCK:
                RUN_STATE["log_tail"].append(line)
            if line.startswith("Run dir:"):
                path_text = line.split("Run dir:", 1)[1].strip()
                p = Path(path_text)
                if p.name and RUN_ID_PATTERN.match(p.name):
                    run_id = p.name
                    with RUN_LOCK:
                        RUN_STATE["run_id"] = run_id
                        payload = {
                            "status": RUN_STATE.get("status", "running") or "running",
                            "started_at": RUN_STATE.get("started_at"),
                            "finished_at": RUN_STATE.get("finished_at"),
                            "exit_code": RUN_STATE.get("exit_code"),
                            "current_step": RUN_STATE.get("current_step") or "",
                            "current_detail": RUN_STATE.get("current_detail") or "",
                            "error_step": RUN_STATE.get("error_step") or "",
                        }
                    run_dir = RUNS_DIR / run_id
                    if run_dir.exists():
                        write_run_status(run_dir, payload)
    finally:
        code = process.wait()
        finalize_run_state(code, run_id)


def _terminate_process_group(pid: int, grace_sec: float = 5.0) -> None:
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return

    deadline = time.time() + grace_sec
    while time.time() < deadline:
        with RUN_LOCK:
            proc = RUN_STATE.get("process")
            if proc is None or proc.poll() is not None:
                return
        time.sleep(0.2)

    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def stop_run() -> tuple[bool, str]:
    with RUN_LOCK:
        proc = RUN_STATE.get("process")
        if proc is None or proc.poll() is not None:
            return False, "No running run"
        if RUN_STATE.get("stopping"):
            return True, "stopping"
        RUN_STATE["stop_requested"] = True
        RUN_STATE["stopping"] = True
        RUN_STATE["status"] = "stopping"
        pid = int(proc.pid)

    thread = threading.Thread(target=_terminate_process_group, args=(pid,), daemon=True)
    thread.start()
    return True, "stopping"


def start_run() -> tuple[bool, str]:
    env = parse_env(CONFIG_PATH)
    video_path = (env.get("VIDEO_PATH", "") or "").strip()
    if not video_path:
        return False, "No video selected"
    resolve_video_config_path(video_path)
    transcription_provider = (env.get("TRANSCRIPTION_PROVIDER", "whisper") or "whisper").strip().lower()
    run_step_edit = (env.get("RUN_STEP_EDIT", "1") or "1").strip() not in {"0", "false", "False", "no", "off"}
    run_step_translate = (env.get("RUN_STEP_TRANSLATE", "1") or "1").strip() not in {"0", "false", "False", "no", "off"}
    run_step_text_translate = (env.get("RUN_STEP_TEXT_TRANSLATE", "1") or "1").strip() not in {"0", "false", "False", "no", "off"}
    run_step_tts = (env.get("RUN_STEP_TTS", "1") or "1").strip() not in {"0", "false", "False", "no", "off"}
    final_slide_mode = (env.get("FINAL_SLIDE_POSTPROCESS_MODE", "local") or "local").strip().lower()
    translation_mode = (env.get("FINAL_SLIDE_TRANSLATION_MODE", "none") or "none").strip().lower()
    if (
        (run_step_edit and final_slide_mode == "gemini")
        or (run_step_translate and translation_mode == "gemini")
        or run_step_text_translate
    ) and not (os.environ.get("GEMINI_API_KEY") or "").strip():
        return False, "GEMINI_API_KEY is not set in the server environment"
    if transcription_provider == "google_chirp_3" and not (env.get("GOOGLE_SPEECH_PROJECT_ID", "") or "").strip():
        return False, "GOOGLE_SPEECH_PROJECT_ID must be set when TRANSCRIPTION_PROVIDER=google_chirp_3"
    if run_step_tts and not (
        (env.get("GOOGLE_TTS_PROJECT_ID", "") or env.get("GOOGLE_SPEECH_PROJECT_ID", "") or "").strip()
    ):
        return False, "GOOGLE_TTS_PROJECT_ID must be set when TTS is enabled"

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
        RUN_STATE["current_step"] = None
        RUN_STATE["current_detail"] = ""
        RUN_STATE["step_statuses"] = make_step_statuses()
        RUN_STATE["stop_requested"] = False
        RUN_STATE["stopping"] = False
        RUN_STATE["error_step"] = None

        process = subprocess.Popen(
            ["bash", "scripts/run_slitranet.sh"],
            cwd=str(ROOT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            start_new_session=True,
        )
        RUN_STATE["process"] = process

    thread = threading.Thread(target=_run_worker, args=(process,), daemon=True)
    thread.start()
    return True, "started"


def run_overlay(time_sec: float) -> tuple[int, str]:
    env = parse_env(CONFIG_PATH)
    video_path = (env.get("VIDEO_PATH", "") or "").strip()
    if not video_path:
        return 1, "ERROR: No video selected."

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


def tts_health_sample_text(language_code: str) -> str:
    prefix = (language_code or "").split("-", 1)[0].strip().lower()
    samples = {
        "de": "Dies ist ein kurzer Stimmtest.",
        "en": "This is a short voice test.",
        "es": "Esta es una breve prueba de voz.",
        "fr": "Ceci est un court test vocal.",
        "it": "Questo e un breve test vocale.",
        "pt": "Este e um breve teste de voz.",
        "nl": "Dit is een korte stemtest.",
    }
    return samples.get(prefix, "This is a short voice test.")


def run_tts_health_check(payload: dict) -> dict:
    project_id = str(payload.get("GOOGLE_TTS_PROJECT_ID", "") or "").strip()
    language_code = str(payload.get("GOOGLE_TTS_LANGUAGE_CODE", "") or "").strip()
    model = str(payload.get("GEMINI_TTS_MODEL", "") or "").strip()
    voice = str(payload.get("GEMINI_TTS_VOICE", "") or "").strip()
    prompt = str(payload.get("GEMINI_TTS_PROMPT", "") or "").strip()

    if not model:
        raise ValueError("GEMINI_TTS_MODEL must not be empty")
    if not voice:
        raise ValueError("GEMINI_TTS_VOICE must not be empty")
    if not language_code:
        raise ValueError("GOOGLE_TTS_LANGUAGE_CODE must not be empty")
    if not prompt:
        raise ValueError("GEMINI_TTS_PROMPT must not be empty")

    resolved_project = project_id
    default_project = ""
    start = time.perf_counter()
    try:
        client, texttospeech, resolved_project, default_project = ensure_cloud_tts_client(project_id)
        audio_bytes = synthesize_cloud_tts_audio(
            client,
            texttospeech,
            model=model,
            voice_name=voice,
            language_code=language_code,
            prompt=prompt,
            text=tts_health_sample_text(language_code),
        )
        latency_ms = int(round((time.perf_counter() - start) * 1000))
        duration_sec = measure_wave_or_pcm_duration(audio_bytes)
        return {
            "ok": True,
            "project_id_used": resolved_project,
            "default_project": default_project or "",
            "language_code": language_code,
            "model": model,
            "voice": voice,
            "latency_ms": latency_ms,
            "audio_bytes": len(audio_bytes),
            "duration_sec": duration_sec,
            "message": "TTS API reachable.",
        }
    except Exception as exc:  # noqa: BLE001
        latency_ms = int(round((time.perf_counter() - start) * 1000))
        return {
            "ok": False,
            "project_id_used": resolved_project,
            "default_project": default_project or "",
            "language_code": language_code,
            "model": model,
            "voice": voice,
            "latency_ms": latency_ms,
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
            "message": "TTS API check failed.",
        }


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
                    "TRANSCRIPTION_PROVIDER": env.get("TRANSCRIPTION_PROVIDER", "whisper"),
                    "WHISPER_MODEL": env.get("WHISPER_MODEL", "medium"),
                    "WHISPER_DEVICE": env.get("WHISPER_DEVICE", "cuda"),
                    "WHISPER_COMPUTE_TYPE": env.get("WHISPER_COMPUTE_TYPE", "float16"),
                    "WHISPER_LANGUAGE": env.get("WHISPER_LANGUAGE", ""),
                    "GOOGLE_SPEECH_PROJECT_ID": env.get("GOOGLE_SPEECH_PROJECT_ID", ""),
                    "GOOGLE_SPEECH_LOCATION": env.get("GOOGLE_SPEECH_LOCATION", "global"),
                    "GOOGLE_SPEECH_MODEL": env.get("GOOGLE_SPEECH_MODEL", "chirp_3"),
                    "GOOGLE_SPEECH_LANGUAGE_CODES": env.get("GOOGLE_SPEECH_LANGUAGE_CODES", "en-US"),
                    "GOOGLE_SPEECH_CHUNK_SEC": float(env.get("GOOGLE_SPEECH_CHUNK_SEC", "55")),
                    "GOOGLE_SPEECH_CHUNK_OVERLAP_SEC": float(env.get("GOOGLE_SPEECH_CHUNK_OVERLAP_SEC", "0.75")),
                    "RUN_STEP_EDIT": int(env.get("RUN_STEP_EDIT", "1")),
                    "RUN_STEP_TRANSLATE": int(env.get("RUN_STEP_TRANSLATE", "1")),
                    "RUN_STEP_UPSCALE": int(env.get("RUN_STEP_UPSCALE", "1")),
                    "RUN_STEP_TEXT_TRANSLATE": int(env.get("RUN_STEP_TEXT_TRANSLATE", "1")),
                    "RUN_STEP_TTS": int(env.get("RUN_STEP_TTS", "1")),
                    "RUN_STEP_VIDEO_EXPORT": int(env.get("RUN_STEP_VIDEO_EXPORT", "1")),
                    "FINAL_SOURCE_MODE_AUTO": env.get("FINAL_SOURCE_MODE_AUTO", "auto"),
                    "FULLSLIDE_SAMPLE_FRAMES": int(env.get("FULLSLIDE_SAMPLE_FRAMES", "3")),
                    "FULLSLIDE_BORDER_STRIP_PX": int(env.get("FULLSLIDE_BORDER_STRIP_PX", "24")),
                    "FULLSLIDE_MIN_MATCHED_SIDES": int(env.get("FULLSLIDE_MIN_MATCHED_SIDES", "2")),
                    "FULLSLIDE_BORDER_DIFF_THRESHOLD": float(env.get("FULLSLIDE_BORDER_DIFF_THRESHOLD", "16.0")),
                    "FULLSLIDE_PERSON_BOX_AREA_RATIO": float(env.get("FULLSLIDE_PERSON_BOX_AREA_RATIO", "0.02")),
                    "FULLSLIDE_PERSON_OUTSIDE_RATIO": float(env.get("FULLSLIDE_PERSON_OUTSIDE_RATIO", "0.35")),
                    "KEYFRAME_SETTLE_FRAMES": int(env.get("KEYFRAME_SETTLE_FRAMES", "4")),
                    "KEYFRAME_STABLE_END_GUARD_FRAMES": int(env.get("KEYFRAME_STABLE_END_GUARD_FRAMES", "2")),
                    "KEYFRAME_STABLE_LOOKAHEAD_FRAMES": int(env.get("KEYFRAME_STABLE_LOOKAHEAD_FRAMES", "2")),
                    "SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO": float(env.get("SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO", "0.75")),
                    "SPEAKER_FILTER_MAX_EDGE_DENSITY": float(env.get("SPEAKER_FILTER_MAX_EDGE_DENSITY", "0.011")),
                    "SPEAKER_FILTER_MAX_LAPLACIAN_VAR": float(env.get("SPEAKER_FILTER_MAX_LAPLACIAN_VAR", "80")),
                    "SPEAKER_FILTER_MAX_DURATION_SEC": float(env.get("SPEAKER_FILTER_MAX_DURATION_SEC", "2.5")),
                    "FINAL_SLIDE_POSTPROCESS_MODE": env.get("FINAL_SLIDE_POSTPROCESS_MODE", "local"),
                    "GEMINI_EDIT_MODEL": env.get("GEMINI_EDIT_MODEL", "gemini-3-pro-image-preview"),
                    "GEMINI_EDIT_PROMPT": read_text_file(GEMINI_PROMPT_PATH).rstrip("\n"),
                    "FINAL_SLIDE_TRANSLATION_MODE": env.get("FINAL_SLIDE_TRANSLATION_MODE", "none"),
                    "FINAL_SLIDE_TARGET_LANGUAGE": env.get("FINAL_SLIDE_TARGET_LANGUAGE", "German"),
                    "GEMINI_TRANSLATE_MODEL": env.get("GEMINI_TRANSLATE_MODEL", "gemini-3-pro-image-preview"),
                    "GEMINI_TRANSLATE_PROMPT": read_text_file(GEMINI_TRANSLATE_PROMPT_PATH).rstrip("\n"),
                    "GEMINI_TEXT_TRANSLATE_MODEL": env.get("GEMINI_TEXT_TRANSLATE_MODEL", "gemini-2.5-flash"),
                    "GEMINI_TEXT_TRANSLATE_PROMPT": read_text_file(GEMINI_TEXT_TRANSLATE_PROMPT_PATH).rstrip("\n"),
                    "GEMINI_TTS_MODEL": env.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-tts"),
                    "GEMINI_TTS_VOICE": env.get("GEMINI_TTS_VOICE", "Kore"),
                    "GOOGLE_TTS_PROJECT_ID": env.get("GOOGLE_TTS_PROJECT_ID", env.get("GOOGLE_SPEECH_PROJECT_ID", "")),
                    "GOOGLE_TTS_LANGUAGE_CODE": env.get("GOOGLE_TTS_LANGUAGE_CODE", "en-US"),
                    "GEMINI_TTS_PROMPT": read_text_file(GEMINI_TTS_PROMPT_PATH).rstrip("\n"),
                    "FINAL_SLIDE_UPSCALE_MODE": env.get("FINAL_SLIDE_UPSCALE_MODE", "none"),
                    "FINAL_SLIDE_UPSCALE_MODEL": env.get(
                        "FINAL_SLIDE_UPSCALE_MODEL",
                        "caidas/swin2SR-classical-sr-x4-64",
                    ),
                    "FINAL_SLIDE_UPSCALE_DEVICE": env.get("FINAL_SLIDE_UPSCALE_DEVICE", "auto"),
                    "FINAL_SLIDE_UPSCALE_TILE_SIZE": int(env.get("FINAL_SLIDE_UPSCALE_TILE_SIZE", "256")),
                    "FINAL_SLIDE_UPSCALE_TILE_OVERLAP": int(env.get("FINAL_SLIDE_UPSCALE_TILE_OVERLAP", "24")),
                    "REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF": env.get(
                        "REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF",
                        "nightmareai/real-esrgan",
                    ),
                    "REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID": env.get(
                        "REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID",
                        "f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa",
                    ),
                    "REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND": float(
                        env.get("REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND", "0.000225")
                    ),
                    "REPLICATE_UPSCALE_CONCURRENCY": int(env.get("REPLICATE_UPSCALE_CONCURRENCY", "2")),
                    "VIDEO_EXPORT_MIN_SLIDE_SEC": float(env.get("VIDEO_EXPORT_MIN_SLIDE_SEC", "1.2")),
                    "VIDEO_EXPORT_TAIL_PAD_SEC": float(env.get("VIDEO_EXPORT_TAIL_PAD_SEC", "0.35")),
                    "VIDEO_EXPORT_WIDTH": int(env.get("VIDEO_EXPORT_WIDTH", "1920")),
                    "VIDEO_EXPORT_HEIGHT": int(env.get("VIDEO_EXPORT_HEIGHT", "1080")),
                    "VIDEO_EXPORT_FPS": int(env.get("VIDEO_EXPORT_FPS", "30")),
                    "VIDEO_EXPORT_BG_COLOR": env.get("VIDEO_EXPORT_BG_COLOR", "white"),
                    "GEMINI_API_KEY_SET": bool((os.environ.get("GEMINI_API_KEY") or "").strip()),
                    "REPLICATE_API_TOKEN_SET": bool((os.environ.get("REPLICATE_API_TOKEN") or "").strip()),
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

            if path == "/api/lab/images":
                payload = list_lab_images()
                payload["current"] = snapshot_lab_state()
                return self._send_json(200, payload)

            if path == "/api/lab/status":
                return self._send_json(200, snapshot_lab_state())

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
            if path.startswith("/api/runs/") and path.endswith("/final-slide-image-mode"):
                rest = path[len("/api/runs/") :]
                parts = rest.split("/")
                if len(parts) != 2 or parts[1] != "final-slide-image-mode":
                    raise ValueError("Invalid final slide image mode path")

                run_id = parts[0]
                if not RUN_ID_PATTERN.match(run_id):
                    raise ValueError("Invalid run id")

                run_dir = ensure_within(RUNS_DIR, RUNS_DIR / run_id)
                final_csv = run_dir / "slitranet" / "slide_text_map_final.csv"
                if not run_dir.exists() or not final_csv.exists():
                    raise FileNotFoundError(run_id)

                data = self._read_json_body()
                event_id = int(data["event_id"])
                mode = str(data["mode"]).strip()
                if event_id <= 0:
                    raise ValueError("event_id must be > 0")
                if mode not in {"slide", "full"}:
                    raise ValueError("mode must be slide or full")

                assets = resolve_final_image_assets(run_dir, run_id, event_id, None)
                if mode not in assets["available_image_modes"]:
                    raise ValueError(f"Requested image mode is not available for event {event_id}")

                overrides = load_final_image_mode_overrides(run_dir)
                if mode == assets["default_image_mode"]:
                    overrides.pop(event_id, None)
                else:
                    overrides[event_id] = mode
                save_final_image_mode_overrides(run_dir, overrides)

                updated_assets = resolve_final_image_assets(run_dir, run_id, event_id, overrides.get(event_id))
                return self._send_json(200, {"ok": True, "event_id": event_id, **updated_assets})

            if path == "/api/config":
                data = self._read_json_body()
                video_path = str(data["VIDEO_PATH"]).strip()
                if video_path:
                    resolve_video_config_path(video_path)
                cfg = {
                    "VIDEO_PATH": video_path,
                    "ROI_X0": int(data["ROI_X0"]),
                    "ROI_Y0": int(data["ROI_Y0"]),
                    "ROI_X1": int(data["ROI_X1"]),
                    "ROI_Y1": int(data["ROI_Y1"]),
                    "TRANSCRIPTION_PROVIDER": str(data["TRANSCRIPTION_PROVIDER"]).strip(),
                    "WHISPER_MODEL": str(data["WHISPER_MODEL"]).strip(),
                    "WHISPER_DEVICE": str(data["WHISPER_DEVICE"]).strip(),
                    "WHISPER_COMPUTE_TYPE": str(data["WHISPER_COMPUTE_TYPE"]).strip(),
                    "WHISPER_LANGUAGE": str(data["WHISPER_LANGUAGE"]).strip(),
                    "GOOGLE_SPEECH_PROJECT_ID": str(data["GOOGLE_SPEECH_PROJECT_ID"]).strip(),
                    "GOOGLE_SPEECH_LOCATION": str(data["GOOGLE_SPEECH_LOCATION"]).strip(),
                    "GOOGLE_SPEECH_MODEL": str(data["GOOGLE_SPEECH_MODEL"]).strip(),
                    "GOOGLE_SPEECH_LANGUAGE_CODES": str(data["GOOGLE_SPEECH_LANGUAGE_CODES"]).strip(),
                    "GOOGLE_SPEECH_CHUNK_SEC": float(data["GOOGLE_SPEECH_CHUNK_SEC"]),
                    "GOOGLE_SPEECH_CHUNK_OVERLAP_SEC": float(data["GOOGLE_SPEECH_CHUNK_OVERLAP_SEC"]),
                    "RUN_STEP_EDIT": int(data["RUN_STEP_EDIT"]),
                    "RUN_STEP_TRANSLATE": int(data["RUN_STEP_TRANSLATE"]),
                    "RUN_STEP_UPSCALE": int(data["RUN_STEP_UPSCALE"]),
                    "RUN_STEP_TEXT_TRANSLATE": int(data["RUN_STEP_TEXT_TRANSLATE"]),
                    "RUN_STEP_TTS": int(data["RUN_STEP_TTS"]),
                    "RUN_STEP_VIDEO_EXPORT": int(data["RUN_STEP_VIDEO_EXPORT"]),
                    "FINAL_SOURCE_MODE_AUTO": str(data["FINAL_SOURCE_MODE_AUTO"]).strip(),
                    "FULLSLIDE_SAMPLE_FRAMES": int(data["FULLSLIDE_SAMPLE_FRAMES"]),
                    "FULLSLIDE_BORDER_STRIP_PX": int(data["FULLSLIDE_BORDER_STRIP_PX"]),
                    "FULLSLIDE_MIN_MATCHED_SIDES": int(data["FULLSLIDE_MIN_MATCHED_SIDES"]),
                    "FULLSLIDE_BORDER_DIFF_THRESHOLD": float(data["FULLSLIDE_BORDER_DIFF_THRESHOLD"]),
                    "FULLSLIDE_PERSON_BOX_AREA_RATIO": float(data["FULLSLIDE_PERSON_BOX_AREA_RATIO"]),
                    "FULLSLIDE_PERSON_OUTSIDE_RATIO": float(data["FULLSLIDE_PERSON_OUTSIDE_RATIO"]),
                    "KEYFRAME_SETTLE_FRAMES": int(data["KEYFRAME_SETTLE_FRAMES"]),
                    "KEYFRAME_STABLE_END_GUARD_FRAMES": int(data["KEYFRAME_STABLE_END_GUARD_FRAMES"]),
                    "KEYFRAME_STABLE_LOOKAHEAD_FRAMES": int(data["KEYFRAME_STABLE_LOOKAHEAD_FRAMES"]),
                    "SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO": float(data["SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO"]),
                    "SPEAKER_FILTER_MAX_EDGE_DENSITY": float(data["SPEAKER_FILTER_MAX_EDGE_DENSITY"]),
                    "SPEAKER_FILTER_MAX_LAPLACIAN_VAR": float(data["SPEAKER_FILTER_MAX_LAPLACIAN_VAR"]),
                    "SPEAKER_FILTER_MAX_DURATION_SEC": float(data["SPEAKER_FILTER_MAX_DURATION_SEC"]),
                    "FINAL_SLIDE_POSTPROCESS_MODE": str(data["FINAL_SLIDE_POSTPROCESS_MODE"]).strip(),
                    "GEMINI_EDIT_MODEL": str(data["GEMINI_EDIT_MODEL"]).strip(),
                    "FINAL_SLIDE_TRANSLATION_MODE": str(data["FINAL_SLIDE_TRANSLATION_MODE"]).strip(),
                    "FINAL_SLIDE_TARGET_LANGUAGE": str(data["FINAL_SLIDE_TARGET_LANGUAGE"]).strip(),
                    "GEMINI_TRANSLATE_MODEL": str(data["GEMINI_TRANSLATE_MODEL"]).strip(),
                    "GEMINI_TEXT_TRANSLATE_MODEL": str(data["GEMINI_TEXT_TRANSLATE_MODEL"]).strip(),
                    "GEMINI_TTS_MODEL": str(data["GEMINI_TTS_MODEL"]).strip(),
                    "GEMINI_TTS_VOICE": str(data["GEMINI_TTS_VOICE"]).strip(),
                    "GOOGLE_TTS_PROJECT_ID": str(data["GOOGLE_TTS_PROJECT_ID"]).strip(),
                    "GOOGLE_TTS_LANGUAGE_CODE": str(data["GOOGLE_TTS_LANGUAGE_CODE"]).strip(),
                    "FINAL_SLIDE_UPSCALE_MODE": str(data["FINAL_SLIDE_UPSCALE_MODE"]).strip(),
                    "FINAL_SLIDE_UPSCALE_MODEL": str(data["FINAL_SLIDE_UPSCALE_MODEL"]).strip(),
                    "FINAL_SLIDE_UPSCALE_DEVICE": str(data["FINAL_SLIDE_UPSCALE_DEVICE"]).strip(),
                    "FINAL_SLIDE_UPSCALE_TILE_SIZE": int(data["FINAL_SLIDE_UPSCALE_TILE_SIZE"]),
                    "FINAL_SLIDE_UPSCALE_TILE_OVERLAP": int(data["FINAL_SLIDE_UPSCALE_TILE_OVERLAP"]),
                    "REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF": str(
                        data["REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF"]
                    ).strip(),
                    "REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID": str(
                        data["REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID"]
                    ).strip(),
                    "REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND": float(
                        data["REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND"]
                    ),
                    "REPLICATE_UPSCALE_CONCURRENCY": int(data["REPLICATE_UPSCALE_CONCURRENCY"]),
                    "VIDEO_EXPORT_MIN_SLIDE_SEC": float(data["VIDEO_EXPORT_MIN_SLIDE_SEC"]),
                    "VIDEO_EXPORT_TAIL_PAD_SEC": float(data["VIDEO_EXPORT_TAIL_PAD_SEC"]),
                    "VIDEO_EXPORT_WIDTH": int(data["VIDEO_EXPORT_WIDTH"]),
                    "VIDEO_EXPORT_HEIGHT": int(data["VIDEO_EXPORT_HEIGHT"]),
                    "VIDEO_EXPORT_FPS": int(data["VIDEO_EXPORT_FPS"]),
                    "VIDEO_EXPORT_BG_COLOR": str(data["VIDEO_EXPORT_BG_COLOR"]).strip(),
                }
                gemini_edit_prompt = str(data["GEMINI_EDIT_PROMPT"])
                gemini_translate_prompt = str(data["GEMINI_TRANSLATE_PROMPT"])
                gemini_text_translate_prompt = str(data["GEMINI_TEXT_TRANSLATE_PROMPT"])
                gemini_tts_prompt = str(data["GEMINI_TTS_PROMPT"])
                if cfg["ROI_X0"] >= cfg["ROI_X1"] or cfg["ROI_Y0"] >= cfg["ROI_Y1"]:
                    raise ValueError("ROI must satisfy x0 < x1 and y0 < y1")
                for key in (
                    "RUN_STEP_EDIT",
                    "RUN_STEP_TRANSLATE",
                    "RUN_STEP_UPSCALE",
                    "RUN_STEP_TEXT_TRANSLATE",
                    "RUN_STEP_TTS",
                    "RUN_STEP_VIDEO_EXPORT",
                ):
                    if cfg[key] not in {0, 1}:
                        raise ValueError(f"{key} must be 0 or 1")
                if cfg["TRANSCRIPTION_PROVIDER"] not in {"whisper", "google_chirp_3"}:
                    raise ValueError("TRANSCRIPTION_PROVIDER must be whisper or google_chirp_3")
                if not cfg["WHISPER_MODEL"]:
                    raise ValueError("WHISPER_MODEL must not be empty")
                if not cfg["WHISPER_DEVICE"]:
                    raise ValueError("WHISPER_DEVICE must not be empty")
                if not cfg["WHISPER_COMPUTE_TYPE"]:
                    raise ValueError("WHISPER_COMPUTE_TYPE must not be empty")
                if cfg["TRANSCRIPTION_PROVIDER"] == "google_chirp_3":
                    if not cfg["GOOGLE_SPEECH_PROJECT_ID"]:
                        raise ValueError("GOOGLE_SPEECH_PROJECT_ID must not be empty when using google_chirp_3")
                    if not cfg["GOOGLE_SPEECH_LOCATION"]:
                        raise ValueError("GOOGLE_SPEECH_LOCATION must not be empty")
                    if not cfg["GOOGLE_SPEECH_MODEL"]:
                        raise ValueError("GOOGLE_SPEECH_MODEL must not be empty")
                    if not cfg["GOOGLE_SPEECH_LANGUAGE_CODES"]:
                        raise ValueError("GOOGLE_SPEECH_LANGUAGE_CODES must not be empty")
                    if cfg["GOOGLE_SPEECH_CHUNK_SEC"] <= 0:
                        raise ValueError("GOOGLE_SPEECH_CHUNK_SEC must be > 0")
                    if cfg["GOOGLE_SPEECH_CHUNK_OVERLAP_SEC"] < 0:
                        raise ValueError("GOOGLE_SPEECH_CHUNK_OVERLAP_SEC must be >= 0")
                    if cfg["GOOGLE_SPEECH_CHUNK_OVERLAP_SEC"] >= cfg["GOOGLE_SPEECH_CHUNK_SEC"]:
                        raise ValueError("GOOGLE_SPEECH_CHUNK_OVERLAP_SEC must be smaller than GOOGLE_SPEECH_CHUNK_SEC")
                if cfg["FINAL_SOURCE_MODE_AUTO"] not in {"off", "auto"}:
                    raise ValueError("FINAL_SOURCE_MODE_AUTO must be off or auto")
                if cfg["FULLSLIDE_SAMPLE_FRAMES"] < 1:
                    raise ValueError("FULLSLIDE_SAMPLE_FRAMES must be >= 1")
                if cfg["FULLSLIDE_BORDER_STRIP_PX"] < 2:
                    raise ValueError("FULLSLIDE_BORDER_STRIP_PX must be >= 2")
                if cfg["FULLSLIDE_MIN_MATCHED_SIDES"] < 1 or cfg["FULLSLIDE_MIN_MATCHED_SIDES"] > 4:
                    raise ValueError("FULLSLIDE_MIN_MATCHED_SIDES must be in [1, 4]")
                if cfg["FULLSLIDE_BORDER_DIFF_THRESHOLD"] < 0:
                    raise ValueError("FULLSLIDE_BORDER_DIFF_THRESHOLD must be >= 0")
                if not (0.0 <= cfg["FULLSLIDE_PERSON_BOX_AREA_RATIO"] <= 1.0):
                    raise ValueError("FULLSLIDE_PERSON_BOX_AREA_RATIO must be in [0, 1]")
                if not (0.0 <= cfg["FULLSLIDE_PERSON_OUTSIDE_RATIO"] <= 1.0):
                    raise ValueError("FULLSLIDE_PERSON_OUTSIDE_RATIO must be in [0, 1]")
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
                if cfg["FINAL_SLIDE_POSTPROCESS_MODE"] not in {"none", "local", "gemini"}:
                    raise ValueError("FINAL_SLIDE_POSTPROCESS_MODE must be none, local, or gemini")
                if not cfg["GEMINI_EDIT_MODEL"]:
                    raise ValueError("GEMINI_EDIT_MODEL must not be empty")
                if not gemini_edit_prompt.strip():
                    raise ValueError("GEMINI_EDIT_PROMPT must not be empty")
                if cfg["FINAL_SLIDE_TRANSLATION_MODE"] not in {"none", "gemini"}:
                    raise ValueError("FINAL_SLIDE_TRANSLATION_MODE must be none or gemini")
                if (
                    cfg["FINAL_SLIDE_TRANSLATION_MODE"] == "gemini"
                    or cfg["RUN_STEP_TEXT_TRANSLATE"] == 1
                ) and not cfg["FINAL_SLIDE_TARGET_LANGUAGE"]:
                    raise ValueError("FINAL_SLIDE_TARGET_LANGUAGE must not be empty when translation is enabled")
                if not cfg["GEMINI_TRANSLATE_MODEL"]:
                    raise ValueError("GEMINI_TRANSLATE_MODEL must not be empty")
                if not gemini_translate_prompt.strip():
                    raise ValueError("GEMINI_TRANSLATE_PROMPT must not be empty")
                if not cfg["GEMINI_TEXT_TRANSLATE_MODEL"]:
                    raise ValueError("GEMINI_TEXT_TRANSLATE_MODEL must not be empty")
                if not gemini_text_translate_prompt.strip():
                    raise ValueError("GEMINI_TEXT_TRANSLATE_PROMPT must not be empty")
                if not cfg["GEMINI_TTS_MODEL"]:
                    raise ValueError("GEMINI_TTS_MODEL must not be empty")
                if not cfg["GEMINI_TTS_VOICE"]:
                    raise ValueError("GEMINI_TTS_VOICE must not be empty")
                if cfg["RUN_STEP_TTS"] == 1 and not (
                    cfg["GOOGLE_TTS_PROJECT_ID"] or cfg["GOOGLE_SPEECH_PROJECT_ID"]
                ):
                    raise ValueError("GOOGLE_TTS_PROJECT_ID must not be empty when TTS is enabled")
                if cfg["RUN_STEP_TTS"] == 1 and not cfg["GOOGLE_TTS_LANGUAGE_CODE"]:
                    raise ValueError("GOOGLE_TTS_LANGUAGE_CODE must not be empty when TTS is enabled")
                if not gemini_tts_prompt.strip():
                    raise ValueError("GEMINI_TTS_PROMPT must not be empty")
                if cfg["FINAL_SLIDE_UPSCALE_MODE"] not in {
                    "none",
                    "swin2sr",
                    "replicate_nightmare_realesrgan",
                }:
                    raise ValueError(
                        "FINAL_SLIDE_UPSCALE_MODE must be none, swin2sr, or replicate_nightmare_realesrgan"
                    )
                if not cfg["FINAL_SLIDE_UPSCALE_MODEL"]:
                    raise ValueError("FINAL_SLIDE_UPSCALE_MODEL must not be empty")
                if cfg["FINAL_SLIDE_UPSCALE_DEVICE"] not in {"auto", "cuda", "cpu"}:
                    raise ValueError("FINAL_SLIDE_UPSCALE_DEVICE must be auto, cuda, or cpu")
                if cfg["FINAL_SLIDE_UPSCALE_TILE_SIZE"] < 0:
                    raise ValueError("FINAL_SLIDE_UPSCALE_TILE_SIZE must be >= 0")
                if cfg["FINAL_SLIDE_UPSCALE_TILE_OVERLAP"] < 0:
                    raise ValueError("FINAL_SLIDE_UPSCALE_TILE_OVERLAP must be >= 0")
                if (
                    cfg["FINAL_SLIDE_UPSCALE_TILE_SIZE"] > 0
                    and cfg["FINAL_SLIDE_UPSCALE_TILE_OVERLAP"] >= cfg["FINAL_SLIDE_UPSCALE_TILE_SIZE"]
                ):
                    raise ValueError(
                        "FINAL_SLIDE_UPSCALE_TILE_OVERLAP must be smaller than FINAL_SLIDE_UPSCALE_TILE_SIZE"
                    )
                if not cfg["REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF"]:
                    raise ValueError("REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF must not be empty")
                if not cfg["REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID"]:
                    raise ValueError("REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID must not be empty")
                if cfg["REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND"] < 0:
                    raise ValueError("REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND must be >= 0")
                if cfg["REPLICATE_UPSCALE_CONCURRENCY"] < 1:
                    raise ValueError("REPLICATE_UPSCALE_CONCURRENCY must be >= 1")
                if cfg["VIDEO_EXPORT_MIN_SLIDE_SEC"] <= 0:
                    raise ValueError("VIDEO_EXPORT_MIN_SLIDE_SEC must be > 0")
                if cfg["VIDEO_EXPORT_TAIL_PAD_SEC"] < 0:
                    raise ValueError("VIDEO_EXPORT_TAIL_PAD_SEC must be >= 0")
                if cfg["VIDEO_EXPORT_WIDTH"] <= 0 or cfg["VIDEO_EXPORT_HEIGHT"] <= 0:
                    raise ValueError("VIDEO_EXPORT_WIDTH and VIDEO_EXPORT_HEIGHT must be > 0")
                if cfg["VIDEO_EXPORT_FPS"] <= 0:
                    raise ValueError("VIDEO_EXPORT_FPS must be > 0")
                if not cfg["VIDEO_EXPORT_BG_COLOR"]:
                    raise ValueError("VIDEO_EXPORT_BG_COLOR must not be empty")
                write_config_values(CONFIG_PATH, cfg)
                write_text_file(GEMINI_PROMPT_PATH, gemini_edit_prompt)
                write_text_file(GEMINI_TRANSLATE_PROMPT_PATH, gemini_translate_prompt)
                write_text_file(GEMINI_TEXT_TRANSLATE_PROMPT_PATH, gemini_text_translate_prompt)
                write_text_file(GEMINI_TTS_PROMPT_PATH, gemini_tts_prompt)
                return self._send_json(
                    200,
                    {
                        "ok": True,
                        **cfg,
                        "GEMINI_EDIT_PROMPT": gemini_edit_prompt.rstrip("\n"),
                        "GEMINI_TRANSLATE_PROMPT": gemini_translate_prompt.rstrip("\n"),
                        "GEMINI_API_KEY_SET": bool((os.environ.get("GEMINI_API_KEY") or "").strip()),
                        "REPLICATE_API_TOKEN_SET": bool((os.environ.get("REPLICATE_API_TOKEN") or "").strip()),
                    },
                )

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

            if path == "/api/tts/health":
                data = self._read_json_body()
                return self._send_json(200, run_tts_health_check(data))

            if path == "/api/runs":
                ok, msg = start_run()
                if not ok:
                    return self._send_json(409, {"ok": False, "error": msg, "current": snapshot_run_state()})
                return self._send_json(202, {"ok": True, "message": msg, "current": snapshot_run_state()})

            if path == "/api/runs/stop":
                ok, msg = stop_run()
                if not ok:
                    return self._send_json(409, {"ok": False, "error": msg, "current": snapshot_run_state()})
                return self._send_json(202, {"ok": True, "message": msg, "current": snapshot_run_state()})

            if path in {"/api/lab/edit", "/api/lab/translate", "/api/lab/upscale"}:
                data = self._read_json_body()
                action = path.rsplit("/", 1)[-1]
                ok, msg = start_lab_job(
                    action,
                    str(data["run_id"]).strip(),
                    int(data["event_id"]),
                    str(data.get("provider", "")).strip(),
                )
                if not ok:
                    return self._send_json(409, {"ok": False, "error": msg, "current": snapshot_lab_state()})
                return self._send_json(202, {"ok": True, "message": msg, "current": snapshot_lab_state()})

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
    parser = argparse.ArgumentParser(description="Local UI server for slide-detection project")
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
