#!/usr/bin/env python3
from __future__ import annotations

import argparse
import bisect
import csv
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a narrated slide video from final slide images and aligned full-transcript TTS audio.")
    parser.add_argument("--slide-map-json", required=True, help="Input slide text map JSON (translated or original).")
    parser.add_argument("--image-dir", required=True, help="Directory with final slide images to render.")
    parser.add_argument("--tts-alignment-json", default="", help="Optional TTS segment alignment JSON path.")
    parser.add_argument("--out-video", required=True, help="Output MP4 path.")
    parser.add_argument("--out-timeline-json", required=True, help="Output timeline JSON path.")
    parser.add_argument("--out-timeline-csv", required=True, help="Output timeline CSV path.")
    parser.add_argument("--out-srt", default="", help="Optional output subtitle path.")
    parser.add_argument("--min-slide-sec", type=float, default=1.2, help="Minimum per-slide duration in seconds.")
    parser.add_argument("--tail-pad-sec", type=float, default=0.35, help="Silence tail added after each voiced slide.")
    parser.add_argument("--intro-white-sec", type=float, default=1.0, help="Initial white screen duration before the first slide fades in.")
    parser.add_argument("--intro-fade-sec", type=float, default=0.4, help="Crossfade duration from white intro to the first slide.")
    parser.add_argument("--thumbnail-duration-sec", type=float, default=2.0, help="Display duration for slide 1 (thumbnail) before slide 2 appears.")
    parser.add_argument("--thumbnail-fade-sec", type=float, default=0.3, help="Crossfade duration between slide 1 (thumbnail) and slide 2.")
    parser.add_argument("--intro-color", default="white", help="Color used for the intro still before the first slide fades in.")
    parser.add_argument("--outro-hold-sec", type=float, default=1.5, help="Hold duration for the last slide after spoken audio ends.")
    parser.add_argument("--outro-fade-sec", type=float, default=1.5, help="Fade-out duration for the last slide at the end of the export.")
    parser.add_argument("--outro-fade-color", default="black", help="Color used for the outro fade target.")
    parser.add_argument("--outro-black-sec", type=float, default=2.0, help="Hold duration for a solid black frame after the outro fade.")
    parser.add_argument("--width", type=int, default=1920, help="Output video width.")
    parser.add_argument("--height", type=int, default=1080, help="Output video height.")
    parser.add_argument("--fps", type=int, default=30, help="Output video frame rate.")
    parser.add_argument("--bg-color", default="white", help="Background color for padded slides.")
    return parser.parse_args()


def ffmpeg_exists() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is not installed or not in PATH.")
    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe is not installed or not in PATH.")


def run_cmd(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_alignment(path: Path | None) -> tuple[dict[int, dict[str, Any]], Path | None, list[dict[str, Any]], list[float]]:
    if path is None or not path.exists():
        return {}, None, [], []
    payload = load_json(path)
    items = payload.get("segments") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {}, None, [], []
    full_audio_path = Path(str(payload.get("full_audio_path", "") or "")).resolve() if str(payload.get("full_audio_path", "") or "").strip() else None
    if full_audio_path is not None and not full_audio_path.exists():
        full_audio_path = None
    raw_words = payload.get("words") if isinstance(payload, dict) else None
    words: list[dict[str, Any]] = []
    word_boundaries: list[float] = []
    if isinstance(raw_words, list):
        for idx, word in enumerate(raw_words):
            if not isinstance(word, dict):
                continue
            try:
                start_sec = float(word.get("start_sec", 0.0) or 0.0)
                end_sec = float(word.get("end_sec", start_sec) or start_sec)
            except Exception:  # noqa: BLE001
                continue
            if end_sec < start_sec:
                end_sec = start_sec
            normalized = str(word.get("normalized", "") or "").strip()
            if not normalized:
                normalized = normalize_token(str(word.get("text", "") or ""))
            words.append(
                {
                    "_idx": idx,
                    "text": str(word.get("text", "") or ""),
                    "normalized": normalized,
                    "start_sec": round(start_sec, 3),
                    "end_sec": round(end_sec, 3),
                }
            )
            word_boundaries.append(round(start_sec, 3))
            word_boundaries.append(round(end_sec, 3))
    word_boundaries = sorted(set(word_boundaries))
    out: dict[int, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        segment_id = int(item.get("segment_id", 0) or 0)
        if segment_id <= 0:
            continue
        out[segment_id] = item
    return out, full_audio_path, words, word_boundaries


TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def normalize_token(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).lower()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"_+", "", text).strip()


def text_to_tokens(value: str) -> list[str]:
    out: list[str] = []
    for token in TOKEN_RE.findall(str(value or "")):
        norm = normalize_token(token)
        if norm:
            out.append(norm)
    return out


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


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "slide_index",
        "event_id",
        "bucket_id",
        "video_start_sec",
        "video_end_sec",
        "duration_sec",
        "image_name",
        "audio_source_name",
        "audio_clip_start_sec",
        "audio_clip_end_sec",
        "audio_clip_duration_sec",
        "text",
        "translated_text",
        "subtitle_text",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def probe_media_duration(path: Path) -> float:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    value = (proc.stdout or "").strip()
    if not value:
        return 0.0
    return max(0.0, float(value))


def compute_slide_audio_window(
    event: dict[str, Any],
    alignment_by_segment: dict[int, dict[str, Any]],
) -> tuple[float, float] | None:
    slide_start = float(event.get("slide_start", 0.0) or 0.0)
    slide_end = float(event.get("slide_end", slide_start) or slide_start)
    windows: list[tuple[float, float]] = []
    for segment_id in event.get("source_segment_ids", []) or []:
        row = alignment_by_segment.get(int(segment_id))
        if not row:
            continue
        source_start = float(row.get("source_start_sec", 0.0) or 0.0)
        source_end = float(row.get("source_end_sec", source_start) or source_start)
        tts_start = float(row.get("tts_start_sec", 0.0) or 0.0)
        tts_end = float(row.get("tts_end_sec", tts_start) or tts_start)
        if source_end <= source_start or tts_end <= tts_start:
            continue
        overlap_start = max(slide_start, source_start)
        overlap_end = min(slide_end, source_end)
        if overlap_end <= overlap_start:
            continue
        relative_start = (overlap_start - source_start) / (source_end - source_start)
        relative_end = (overlap_end - source_start) / (source_end - source_start)
        clip_start = tts_start + relative_start * (tts_end - tts_start)
        clip_end = tts_start + relative_end * (tts_end - tts_start)
        windows.append((clip_start, clip_end))
    if not windows:
        return None
    return min(start for start, _ in windows), max(end for _, end in windows)


def build_segment_word_candidates(
    event: dict[str, Any],
    alignment_by_segment: dict[int, dict[str, Any]],
    words: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    segment_rows: list[dict[str, Any]] = []
    for segment_id in event.get("source_segment_ids", []) or []:
        row = alignment_by_segment.get(int(segment_id))
        if row:
            segment_rows.append(row)
    if not segment_rows:
        return []
    tts_start = min(float(row.get("tts_start_sec", 0.0) or 0.0) for row in segment_rows)
    tts_end = max(float(row.get("tts_end_sec", tts_start) or tts_start) for row in segment_rows)
    pad = 0.25
    return [
        word
        for word in words
        if float(word.get("end_sec", 0.0) or 0.0) >= tts_start - pad
        and float(word.get("start_sec", 0.0) or 0.0) <= tts_end + pad
    ]


def exact_phrase_match(
    candidates: list[dict[str, Any]],
    target_tokens: list[str],
    min_global_idx: int,
) -> tuple[int, int] | None:
    target_len = len(target_tokens)
    if not target_len or len(candidates) < target_len:
        return None
    normalized = [str(item.get("normalized", "") or "") for item in candidates]
    for start_idx in range(0, len(candidates) - target_len + 1):
        if int(candidates[start_idx].get("_idx", -1)) < min_global_idx:
            continue
        if normalized[start_idx : start_idx + target_len] == target_tokens:
            return start_idx, start_idx + target_len - 1
    return None


def fuzzy_phrase_match(
    candidates: list[dict[str, Any]],
    target_tokens: list[str],
    min_global_idx: int,
) -> tuple[int, int] | None:
    from difflib import SequenceMatcher

    target = " ".join(target_tokens).strip()
    if not target:
        return None
    best: tuple[float, int, int] | None = None
    max_window = max(2, len(target_tokens) + 4)
    normalized = [str(item.get("normalized", "") or "") for item in candidates]
    for start_idx in range(len(candidates)):
        if int(candidates[start_idx].get("_idx", -1)) < min_global_idx:
            continue
        max_end = min(len(candidates), start_idx + max_window)
        for end_idx in range(start_idx + 1, max_end + 1):
            candidate_text = " ".join(normalized[start_idx:end_idx]).strip()
            if not candidate_text:
                continue
            score = SequenceMatcher(None, candidate_text, target).ratio()
            if best is None or score > best[0]:
                best = (score, start_idx, end_idx - 1)
    if best is None or best[0] < 0.78:
        return None
    return best[1], best[2]


def build_slide_phrase_matches(
    events: list[dict[str, Any]],
    alignment_by_segment: dict[int, dict[str, Any]],
    words: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    matches: dict[int, dict[str, Any]] = {}
    min_global_idx = 0
    for slide_index, event in enumerate(events, start=1):
        if slide_index == 1:
            matches[slide_index] = {"matched": False}
            continue
        phrase_text = str(event.get("translated_text", "") or "").strip() or str(event.get("text", "") or "").strip()
        target_tokens = text_to_tokens(phrase_text)
        if not target_tokens:
            matches[slide_index] = {"matched": False}
            continue
        candidates = build_segment_word_candidates(event, alignment_by_segment, words)
        if not candidates:
            matches[slide_index] = {"matched": False}
            continue
        match = exact_phrase_match(candidates, target_tokens, min_global_idx)
        match_mode = "exact"
        if match is None:
            match = fuzzy_phrase_match(candidates, target_tokens, min_global_idx)
            match_mode = "fuzzy"
        if match is None:
            matches[slide_index] = {"matched": False}
            continue
        start_idx, end_idx = match
        start_word = candidates[start_idx]
        end_word = candidates[end_idx]
        min_global_idx = int(end_word.get("_idx", min_global_idx)) + 1
        matches[slide_index] = {
            "matched": True,
            "match_mode": match_mode,
            "start_sec": float(start_word.get("start_sec", 0.0) or 0.0),
            "end_sec": float(end_word.get("end_sec", start_word.get("start_sec", 0.0)) or 0.0),
            "start_word_index": int(start_word.get("_idx", 0)),
            "end_word_index": int(end_word.get("_idx", 0)),
            "tokens_count": len(target_tokens),
        }
    return matches


def sorted_alignment_rows(alignment_by_segment: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in alignment_by_segment.values():
        try:
            source_start = float(row.get("source_start_sec", 0.0) or 0.0)
            source_end = float(row.get("source_end_sec", source_start) or source_start)
            tts_start = float(row.get("tts_start_sec", 0.0) or 0.0)
            tts_end = float(row.get("tts_end_sec", tts_start) or tts_start)
        except Exception:  # noqa: BLE001
            continue
        if source_end <= source_start or tts_end < tts_start:
            continue
        rows.append(
            {
                "source_start_sec": source_start,
                "source_end_sec": source_end,
                "tts_start_sec": tts_start,
                "tts_end_sec": tts_end,
            }
        )
    rows.sort(key=lambda item: (item["source_start_sec"], item["source_end_sec"], item["tts_start_sec"]))
    return rows


def snap_tts_time_to_word_boundary(
    projected_time: float,
    word_boundaries: list[float],
    full_audio_duration: float,
    max_delta_sec: float = 0.35,
) -> float:
    if not word_boundaries:
        return max(0.0, min(full_audio_duration, projected_time))
    idx = bisect.bisect_left(word_boundaries, projected_time)
    candidates: list[float] = []
    if idx < len(word_boundaries):
        candidates.append(float(word_boundaries[idx]))
    if idx > 0:
        candidates.append(float(word_boundaries[idx - 1]))
    if not candidates:
        return max(0.0, min(full_audio_duration, projected_time))
    nearest = min(candidates, key=lambda value: abs(value - projected_time))
    if abs(nearest - projected_time) <= max(0.0, float(max_delta_sec)):
        return max(0.0, min(full_audio_duration, nearest))
    return max(0.0, min(full_audio_duration, projected_time))


def project_source_time_to_tts(
    source_time: float,
    alignment_rows: list[dict[str, Any]],
    full_audio_duration: float,
    word_boundaries: list[float] | None = None,
) -> float | None:
    if not alignment_rows:
        return None

    eps = 1e-6
    left_ends: list[float] = []
    right_starts: list[float] = []
    left_row: dict[str, Any] | None = None
    right_row: dict[str, Any] | None = None

    for row in alignment_rows:
        source_start = float(row["source_start_sec"])
        source_end = float(row["source_end_sec"])
        tts_start = float(row["tts_start_sec"])
        tts_end = float(row["tts_end_sec"])

        if source_start + eps < source_time < source_end - eps:
            rel = (source_time - source_start) / (source_end - source_start)
            projected = max(0.0, min(full_audio_duration, tts_start + rel * (tts_end - tts_start)))
            return snap_tts_time_to_word_boundary(projected, word_boundaries or [], full_audio_duration)

        if abs(source_time - source_end) <= eps:
            left_ends.append(tts_end)
        if abs(source_time - source_start) <= eps:
            right_starts.append(tts_start)

        if source_end < source_time and (left_row is None or source_end >= float(left_row["source_end_sec"])):
            left_row = row
        if source_start > source_time and right_row is None:
            right_row = row

    if left_ends or right_starts:
        if left_ends and right_starts:
            projected = max(0.0, min(full_audio_duration, (max(left_ends) + min(right_starts)) / 2.0))
            return snap_tts_time_to_word_boundary(projected, word_boundaries or [], full_audio_duration)
        if left_ends:
            projected = max(0.0, min(full_audio_duration, max(left_ends)))
            return snap_tts_time_to_word_boundary(projected, word_boundaries or [], full_audio_duration)
        projected = max(0.0, min(full_audio_duration, min(right_starts)))
        return snap_tts_time_to_word_boundary(projected, word_boundaries or [], full_audio_duration)

    if left_row is not None and right_row is not None:
        left_source = float(left_row["source_end_sec"])
        right_source = float(right_row["source_start_sec"])
        left_tts = float(left_row["tts_end_sec"])
        right_tts = float(right_row["tts_start_sec"])
        if right_source > left_source:
            rel = (source_time - left_source) / (right_source - left_source)
            projected = max(0.0, min(full_audio_duration, left_tts + rel * (right_tts - left_tts)))
            return snap_tts_time_to_word_boundary(projected, word_boundaries or [], full_audio_duration)
        projected = max(0.0, min(full_audio_duration, (left_tts + right_tts) / 2.0))
        return snap_tts_time_to_word_boundary(projected, word_boundaries or [], full_audio_duration)

    if source_time <= float(alignment_rows[0]["source_start_sec"]):
        return 0.0
    return max(0.0, full_audio_duration)


def build_master_audio_timeline_rows(
    events: list[dict[str, Any]],
    image_dir: Path,
    alignment_by_segment: dict[int, dict[str, Any]],
    words: list[dict[str, Any]],
    word_boundaries: list[float],
    full_audio_duration: float,
    min_slide_sec: float,
    tail_pad_sec: float,
    thumbnail_duration_sec: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    alignment_rows = sorted_alignment_rows(alignment_by_segment)
    phrase_matches = build_slide_phrase_matches(events, alignment_by_segment, words)
    current_start = 0.0

    for idx, event in enumerate(events, start=1):
        event_id = int(event.get("event_id", 0) or 0)
        bucket_id = str(event.get("bucket_id", "") or "")
        if idx == 1:
            translated_text = ""
            original_text = ""
            subtitle_text = ""
        else:
            translated_text = str(event.get("translated_text", "") or "").strip()
            original_text = str(event.get("text", "") or "").strip()
            subtitle_text = translated_text or original_text
        image_path = find_image(image_dir, idx, event_id)

        if idx == 1:
            end_sec = current_start + max(0.04, float(thumbnail_duration_sec))
        elif idx < len(events):
            current_match = phrase_matches.get(idx, {})
            next_match = phrase_matches.get(idx + 1, {})
            next_start = float(next_match.get("start_sec", 0.0) or 0.0) if next_match.get("matched") else None
            if next_start is not None:
                end_sec = max(current_start + 0.04, next_start)
            elif current_match.get("matched"):
                end_sec = max(current_start + min_slide_sec, float(current_match.get("end_sec", current_start) or current_start) + tail_pad_sec)
            else:
                source_boundary = float(event.get("slide_end", 0.0) or 0.0)
                projected_end = project_source_time_to_tts(source_boundary, alignment_rows, full_audio_duration, word_boundaries)
                if projected_end is None:
                    audio_window = compute_slide_audio_window(event, alignment_by_segment)
                    projected_end = audio_window[1] if audio_window is not None else current_start + min_slide_sec
                end_sec = max(current_start + min_slide_sec, float(projected_end))
        else:
            current_match = phrase_matches.get(idx, {})
            end_candidates = [current_start + min_slide_sec, full_audio_duration + tail_pad_sec]
            if current_match.get("matched"):
                end_candidates.append(float(current_match.get("end_sec", current_start) or current_start) + tail_pad_sec)
            source_boundary = float(event.get("slide_end", event.get("slide_start", 0.0)) or 0.0)
            projected_end = project_source_time_to_tts(source_boundary, alignment_rows, full_audio_duration, word_boundaries)
            if projected_end is not None:
                end_candidates.append(float(projected_end))
            end_sec = max(end_candidates)

        current_match = phrase_matches.get(idx, {})
        if idx == 1:
            audio_clip_start = 0.0
            audio_clip_end = 0.0
            audio_clip_duration = 0.0
        elif current_match.get("matched"):
            audio_clip_start = min(max(0.0, float(current_match.get("start_sec", current_start) or current_start)), full_audio_duration)
            audio_clip_end = min(max(audio_clip_start, float(current_match.get("end_sec", audio_clip_start) or audio_clip_start)), full_audio_duration)
            audio_clip_duration = max(0.0, audio_clip_end - audio_clip_start)
        else:
            fallback_window = compute_slide_audio_window(event, alignment_by_segment)
            if fallback_window is not None:
                audio_clip_start = min(max(0.0, float(fallback_window[0])), full_audio_duration)
                audio_clip_end = min(max(audio_clip_start, float(fallback_window[1])), full_audio_duration)
                audio_clip_duration = max(0.0, audio_clip_end - audio_clip_start)
            else:
                audio_clip_start = min(current_start, full_audio_duration)
                audio_clip_end = min(end_sec, full_audio_duration)
                audio_clip_duration = max(0.0, audio_clip_end - audio_clip_start)
        if idx == 1:
            pass
        clip_duration = max(0.04, end_sec - current_start)

        rows.append(
            {
                "slide_index": idx,
                "event_id": event_id,
                "bucket_id": bucket_id,
                "video_start_sec": round(current_start, 3),
                "video_end_sec": round(end_sec, 3),
                "duration_sec": round(clip_duration, 3),
                "image_name": image_path.name,
                "audio_source_name": "",
                "audio_clip_start_sec": round(audio_clip_start, 3),
                "audio_clip_end_sec": round(audio_clip_end, 3),
                "audio_clip_duration_sec": round(audio_clip_duration, 3),
                "text": original_text,
                "translated_text": translated_text,
                "subtitle_text": subtitle_text,
            }
        )
        current_start = end_sec

    return rows


def build_segmented_timeline_rows(
    events: list[dict[str, Any]],
    image_dir: Path,
    alignment_by_segment: dict[int, dict[str, Any]],
    full_audio_name: str,
    min_slide_sec: float,
    tail_pad_sec: float,
    thumbnail_duration_sec: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current_start = 0.0

    for idx, event in enumerate(events, start=1):
        event_id = int(event.get("event_id", 0) or 0)
        bucket_id = str(event.get("bucket_id", "") or "")
        if idx == 1:
            translated_text = ""
            original_text = ""
            subtitle_text = ""
        else:
            translated_text = str(event.get("translated_text", "") or "").strip()
            original_text = str(event.get("text", "") or "").strip()
            subtitle_text = translated_text or original_text
        image_path = find_image(image_dir, idx, event_id)
        audio_window = compute_slide_audio_window(event, alignment_by_segment)
        audio_clip_start = 0.0
        audio_clip_end = 0.0
        audio_clip_duration = 0.0
        if idx != 1 and audio_window is not None:
            audio_clip_start = max(0.0, float(audio_window[0]))
            audio_clip_end = max(audio_clip_start, float(audio_window[1]))
            audio_clip_duration = max(0.0, audio_clip_end - audio_clip_start)
        if idx == 1:
            clip_duration = max(0.04, float(thumbnail_duration_sec))
        else:
            clip_duration = max(min_slide_sec, audio_clip_duration + tail_pad_sec if audio_clip_duration > 0 else min_slide_sec)
        start_sec = current_start
        end_sec = current_start + clip_duration
        current_start = end_sec

        rows.append(
            {
                "slide_index": idx,
                "event_id": event_id,
                "bucket_id": bucket_id,
                "video_start_sec": round(start_sec, 3),
                "video_end_sec": round(end_sec, 3),
                "duration_sec": round(clip_duration, 3),
                "image_name": image_path.name,
                "audio_source_name": full_audio_name,
                "audio_clip_start_sec": round(audio_clip_start, 3),
                "audio_clip_end_sec": round(audio_clip_end, 3),
                "audio_clip_duration_sec": round(audio_clip_duration, 3),
                "text": original_text,
                "translated_text": translated_text,
                "subtitle_text": subtitle_text,
            }
        )
    return rows


def apply_intro_outro_timing(
    timeline_rows: list[dict[str, Any]],
    intro_white_sec: float,
    outro_hold_sec: float,
    outro_fade_sec: float,
    outro_black_sec: float,
) -> list[dict[str, Any]]:
    if not timeline_rows:
        return []
    rows: list[dict[str, Any]] = []
    intro_offset = max(0.0, float(intro_white_sec))
    outro_extra = (
        max(0.0, float(outro_hold_sec))
        + max(0.0, float(outro_fade_sec))
        + max(0.0, float(outro_black_sec))
    )
    for idx, row in enumerate(timeline_rows, start=1):
        item = dict(row)
        item["video_start_sec"] = round(float(item["video_start_sec"]) + intro_offset, 3)
        item["video_end_sec"] = round(float(item["video_end_sec"]) + intro_offset, 3)
        audio_clip_duration = float(item.get("audio_clip_duration_sec", 0.0) or 0.0)
        if audio_clip_duration > 0:
            item["audio_clip_start_sec"] = round(float(item["audio_clip_start_sec"]) + intro_offset, 3)
            item["audio_clip_end_sec"] = round(float(item["audio_clip_end_sec"]) + intro_offset, 3)
            item["audio_clip_duration_sec"] = round(
                max(0.0, float(item["audio_clip_end_sec"]) - float(item["audio_clip_start_sec"])),
                3,
            )
        if idx == len(timeline_rows):
            item["video_end_sec"] = round(float(item["video_end_sec"]) + outro_extra, 3)
        item["duration_sec"] = round(max(0.0, float(item["video_end_sec"]) - float(item["video_start_sec"])), 3)
        rows.append(item)
    return rows


def write_srt(path: Path | None, timeline_rows: list[dict[str, Any]]) -> None:
    if path is None:
        return
    entries: list[str] = []
    for row in timeline_rows:
        subtitle_text = str(row.get("subtitle_text", "") or "").strip()
        if not subtitle_text:
            continue
        start_sec = float(row["video_start_sec"])
        end_sec = float(row["video_end_sec"])
        audio_clip_duration = float(row.get("audio_clip_duration_sec", 0.0) or 0.0)
        if audio_clip_duration > 0:
            start_sec = float(row.get("audio_clip_start_sec", start_sec) or start_sec)
            end_sec = float(row.get("audio_clip_end_sec", end_sec) or end_sec)
        entries.append(
            f"{len(entries) + 1}\n"
            f"{seconds_to_srt(start_sec)} --> {seconds_to_srt(end_sec)}\n"
            f"{subtitle_text}\n"
        )
    path.write_text("\n".join(entries).rstrip() + "\n", encoding="utf-8")


def render_segment_videos(
    timeline_rows: list[dict[str, Any]],
    image_dir: Path,
    tmp_dir: Path,
    width: int,
    height: int,
    fps: int,
    bg_color: str,
    intro_color: str,
    outro_fade_color: str,
    intro_white_sec: float,
    intro_fade_sec: float,
    thumbnail_fade_sec: float,
    outro_hold_sec: float,
    outro_fade_sec: float,
    outro_black_sec: float,
    step_label: str,
) -> tuple[Path, int]:
    concat_list = tmp_dir / "concat.txt"
    concat_lines: list[str] = []
    rendered_paths: list[Path] = []
    video_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={bg_color},"
        "format=yuv420p"
    )

    for row in timeline_rows:
        idx = int(row["slide_index"])
        image_path = image_dir / str(row["image_name"])
        clip_duration = float(row["duration_sec"])
        segment_video = tmp_dir / f"segment_video_{idx:03d}.mp4"
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
        rendered_paths.append(segment_video)
        print(f"@@STEP DETAIL {step_label} {image_path.name}", flush=True)
        print(f"[VideoExport] Segment {idx:03d}: {image_path.name} ({clip_duration:.3f}s)", flush=True)

    if not rendered_paths:
        raise RuntimeError("No slide video segments were rendered.")

    if len(rendered_paths) >= 2:
        thumb_duration = max(0.0, float(timeline_rows[0]["duration_sec"]))
        next_duration = max(0.0, float(timeline_rows[1]["duration_sec"]))
        fade_sec = min(max(0.0, float(thumbnail_fade_sec)), max(0.0, thumb_duration - 0.04), next_duration)
        if fade_sec > 0.0:
            thumb_transition = tmp_dir / "thumb_transition.mp4"
            run_cmd(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(rendered_paths[0]),
                    "-i",
                    str(rendered_paths[1]),
                    "-filter_complex",
                    (
                        f"[1:v]tpad=stop_mode=clone:stop_duration={fade_sec:.3f}[v1];"
                        f"[0:v][v1]xfade=transition=fade:duration={fade_sec:.3f}:offset={thumb_duration - fade_sec:.3f},"
                        "format=yuv420p[v]"
                    ),
                    "-map",
                    "[v]",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "18",
                    str(thumb_transition),
                ]
            )
            rendered_paths = [thumb_transition, *rendered_paths[2:]]

    final_paths: list[Path] = []
    intro_white_sec = max(0.0, float(intro_white_sec))
    intro_fade_sec = max(0.0, float(intro_fade_sec))
    outro_hold_sec = max(0.0, float(outro_hold_sec))
    outro_fade_sec = max(0.0, float(outro_fade_sec))
    outro_black_sec = max(0.0, float(outro_black_sec))

    if intro_white_sec > 0.0:
        if intro_fade_sec > 0.0:
            intro_base = tmp_dir / "intro_base.mp4"
            run_cmd(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c={intro_color}:s={width}x{height}:r={fps}:d={intro_white_sec + intro_fade_sec:.3f}",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    str(intro_base),
                ]
            )
            intro_transition = tmp_dir / "intro_transition.mp4"
            run_cmd(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(intro_base),
                    "-i",
                    str(rendered_paths[0]),
                    "-filter_complex",
                    f"[0:v][1:v]xfade=transition=fade:duration={intro_fade_sec:.3f}:offset={intro_white_sec:.3f},format=yuv420p[v]",
                    "-map",
                    "[v]",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "18",
                    str(intro_transition),
                ]
            )
            final_paths.append(intro_transition)
        else:
            intro_still = tmp_dir / "intro_still.mp4"
            run_cmd(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c={intro_color}:s={width}x{height}:r={fps}:d={intro_white_sec:.3f}",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    str(intro_still),
                ]
            )
            final_paths.append(intro_still)
            final_paths.append(rendered_paths[0])
        final_paths.extend(rendered_paths[1:])
    else:
        final_paths.extend(rendered_paths)

    if outro_hold_sec > 0.0 or outro_fade_sec > 0.0:
        last_row = timeline_rows[-1]
        last_image = image_dir / str(last_row["image_name"])
        outro_clip = tmp_dir / "outro.mp4"
        outro_duration = max(0.04, outro_hold_sec + outro_fade_sec)
        outro_filter = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={bg_color},"
            "format=yuv420p"
        )
        if outro_fade_sec > 0.0:
            fade_start = max(0.0, outro_duration - outro_fade_sec)
            outro_filter = f"{outro_filter},fade=t=out:st={fade_start:.3f}:d={outro_fade_sec:.3f}:color={outro_fade_color}"
        run_cmd(
            [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                str(last_image),
                "-t",
                f"{outro_duration:.3f}",
                "-vf",
                outro_filter,
                "-r",
                str(fps),
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                str(outro_clip),
            ]
        )
        final_paths.append(outro_clip)

    if outro_black_sec > 0.0:
        outro_black = tmp_dir / "outro_black.mp4"
        run_cmd(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c=black:s={width}x{height}:r={fps}:d={outro_black_sec:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                str(outro_black),
            ]
        )
        final_paths.append(outro_black)

    for path in final_paths:
        concat_lines.append(f"file '{path.name}'")
    concat_list.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    video_only = tmp_dir / "video_only.mp4"
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
            str(video_only),
        ]
    )
    return video_only, len(timeline_rows)


def main() -> int:
    args = parse_args()
    ffmpeg_exists()

    slide_map_json = Path(args.slide_map_json).resolve()
    image_dir = Path(args.image_dir).resolve()
    tts_alignment_json = Path(args.tts_alignment_json).resolve() if args.tts_alignment_json else None
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

    alignment_by_segment, full_audio_path, words, word_boundaries = load_alignment(tts_alignment_json)
    full_audio_duration = probe_media_duration(full_audio_path) if full_audio_path is not None and full_audio_path.exists() else 0.0
    width = int(args.width)
    height = int(args.height)
    fps = int(args.fps)
    min_slide_sec = max(0.1, float(args.min_slide_sec))
    tail_pad_sec = max(0.0, float(args.tail_pad_sec))
    thumbnail_duration_sec = max(0.04, float(args.thumbnail_duration_sec))
    intro_white_sec = max(0.0, float(args.intro_white_sec))
    intro_fade_sec = max(0.0, float(args.intro_fade_sec))
    thumbnail_fade_sec = max(0.0, float(args.thumbnail_fade_sec))
    outro_hold_sec = max(0.0, float(args.outro_hold_sec))
    outro_fade_sec = max(0.0, float(args.outro_fade_sec))
    outro_black_sec = max(0.0, float(args.outro_black_sec))

    with tempfile.TemporaryDirectory(prefix="slide_export_", dir=str(out_video.parent)) as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        use_master_audio = bool(alignment_by_segment) and full_audio_path is not None and full_audio_path.exists()
        if use_master_audio:
            base_timeline_rows = build_master_audio_timeline_rows(
                events,
                image_dir,
                alignment_by_segment,
                words,
                word_boundaries,
                full_audio_duration,
                min_slide_sec,
                tail_pad_sec,
                thumbnail_duration_sec,
            )
            timeline_rows = apply_intro_outro_timing(
                base_timeline_rows,
                intro_white_sec,
                outro_hold_sec,
                outro_fade_sec,
                outro_black_sec,
            )
            for row in timeline_rows:
                row["audio_source_name"] = full_audio_path.name
            audio_timeline_offset = next(
                (
                    float(row.get("video_start_sec", 0.0) or 0.0)
                    for row in timeline_rows
                    if float(row.get("audio_clip_duration_sec", 0.0) or 0.0) > 0.0
                ),
                0.0,
            )
            video_only, _segment_count = render_segment_videos(
                base_timeline_rows,
                image_dir,
                tmp_dir,
                width,
                height,
                fps,
                args.bg_color,
                args.intro_color,
                args.outro_fade_color,
                intro_white_sec,
                intro_fade_sec,
                thumbnail_fade_sec,
                outro_hold_sec,
                outro_fade_sec,
                outro_black_sec,
                "video-export",
            )
            mux_cmd = ["ffmpeg", "-y", "-i", str(video_only)]
            if audio_timeline_offset > 0.0:
                mux_cmd.extend(["-itsoffset", f"{audio_timeline_offset:.3f}"])
            mux_cmd.extend(
                [
                    "-i",
                    str(full_audio_path),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-movflags",
                    "+faststart",
                    str(out_video),
                ]
            )
            run_cmd(mux_cmd)
            total_duration_sec = max((float(row["video_end_sec"]) for row in timeline_rows), default=full_audio_duration)
            audio_mode = "master_track"
        else:
            audio_name = full_audio_path.name if full_audio_path is not None else ""
            timeline_rows = build_segmented_timeline_rows(
                events,
                image_dir,
                alignment_by_segment,
                audio_name,
                min_slide_sec,
                tail_pad_sec,
                thumbnail_duration_sec,
            )
            concat_list = tmp_dir / "concat.txt"
            concat_lines: list[str] = []
            for row in timeline_rows:
                idx = int(row["slide_index"])
                image_path = image_dir / str(row["image_name"])
                clip_duration = float(row["duration_sec"])
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
                audio_clip_duration = float(row["audio_clip_duration_sec"])
                audio_clip_start = float(row["audio_clip_start_sec"])
                if full_audio_path is not None and full_audio_path.exists() and audio_clip_duration > 0:
                    run_cmd(
                        [
                            "ffmpeg",
                            "-y",
                            "-ss",
                            f"{audio_clip_start:.3f}",
                            "-i",
                            str(full_audio_path),
                            "-t",
                            f"{audio_clip_duration:.3f}",
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
                    "-movflags",
                    "+faststart",
                    str(out_video),
                ]
            )
            total_duration_sec = max((float(row["video_end_sec"]) for row in timeline_rows), default=0.0)
            audio_mode = "segmented_audio_clips"

    timeline_payload = {
        "slide_map_json": str(slide_map_json),
        "image_dir": str(image_dir),
        "tts_alignment_json": str(tts_alignment_json) if tts_alignment_json else "",
        "tts_full_audio_path": str(full_audio_path) if full_audio_path else "",
        "audio_mode": audio_mode,
        "video_width": width,
        "video_height": height,
        "video_fps": fps,
        "min_slide_sec": min_slide_sec,
        "tail_pad_sec": tail_pad_sec,
        "intro_white_sec": intro_white_sec,
        "intro_fade_sec": intro_fade_sec,
        "thumbnail_duration_sec": thumbnail_duration_sec,
        "thumbnail_fade_sec": thumbnail_fade_sec,
        "intro_color": str(args.intro_color),
        "outro_hold_sec": outro_hold_sec,
        "outro_fade_sec": outro_fade_sec,
        "outro_fade_color": str(args.outro_fade_color),
        "outro_black_sec": outro_black_sec,
        "total_duration_sec": round(total_duration_sec, 3),
        "segments": timeline_rows,
    }
    out_timeline_json.write_text(json.dumps(timeline_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out_timeline_csv, timeline_rows)
    write_srt(out_srt, timeline_rows)

    print(f"[VideoExport] Segments: {len(timeline_rows)}", flush=True)
    print(f"[VideoExport] Duration: {total_duration_sec:.3f}s", flush=True)
    print(f"[VideoExport] Image dir: {image_dir}", flush=True)
    print(f"[VideoExport] Audio mode: {audio_mode}", flush=True)
    print(f"[VideoExport] Output video: {out_video}", flush=True)
    print(f"[VideoExport] Timeline JSON: {out_timeline_json}", flush=True)
    print(f"[VideoExport] Timeline CSV: {out_timeline_csv}", flush=True)
    if out_srt is not None:
        print(f"[VideoExport] Subtitle file: {out_srt}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
