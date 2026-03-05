#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import ImageFont

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.lib.slide_glossary import (
    event_metadata_by_id,
    is_translatable_text,
    load_slide_events,
    parse_event_id_from_name,
    write_csv,
    write_json,
)
from scripts.lib.slide_ocr import ensure_cloud_vision_client, ocr_slide_fragments
from scripts.lib.slide_style_classifier import classify_text_units
from scripts.lib.slide_style_config import (
    DEFAULT_SLIDE_TRANSLATE_STYLE_CONFIG_REL,
    load_style_config,
    merged_style,
    resolve_style_font_path,
)
from scripts.lib.slide_text_normalization import NORMALIZATION_VERSION, normalize_slide_text
from scripts.lib.slide_text_render import (
    estimate_background_color,
    estimate_text_color,
    fit_text_to_box,
    inflate_bbox,
    layout_hanging_text_block,
    resolve_text_layout_with_overflow,
    render_text_entries,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a frozen slide translation glossary to final slide images.")
    parser.add_argument("--input-dir", required=True, help="Directory with final slide images.")
    parser.add_argument("--slide-map-json", required=True, help="slide_text_map_final.json path.")
    parser.add_argument("--glossary-json", required=True, help="Frozen glossary JSON path.")
    parser.add_argument("--output-dir", required=True, help="Output directory for translated slide images.")
    parser.add_argument("--manifest-json", required=True, help="Apply manifest JSON output path.")
    parser.add_argument("--manifest-csv", required=True, help="Apply manifest CSV output path.")
    parser.add_argument("--needs-review-json", required=True, help="Needs-review JSON output path.")
    parser.add_argument("--font-path", required=True, help="Fallback font file for deterministic rendering.")
    parser.add_argument("--vision-project-id", required=True, help="Google Cloud Vision quota project.")
    parser.add_argument("--vision-feature", default="DOCUMENT_TEXT_DETECTION", help="Google Vision feature.")
    parser.add_argument(
        "--style-config-json",
        default=str(ROOT_DIR / DEFAULT_SLIDE_TRANSLATE_STYLE_CONFIG_REL),
        help="Role/slot style config JSON.",
    )
    parser.add_argument("--style-manifest-json", default="", help="Optional style manifest JSON output path.")
    parser.add_argument(
        "--global-max-font-size",
        type=int,
        default=120,
        help="Global upper cap for rendered font sizes across all text elements.",
    )
    parser.add_argument(
        "--max-expand-px",
        type=int,
        default=120,
        help="Global right/down expansion limit (pixels) applied to every text element.",
    )
    parser.add_argument(
        "--layout-max-attempts",
        type=int,
        default=50000,
        help="Max layout attempts per text element/group (0 disables attempt budget).",
    )
    parser.add_argument(
        "--layout-max-ms",
        type=int,
        default=15000,
        help="Max layout time in ms per text element/group (0 disables time budget).",
    )
    parser.add_argument(
        "--needs-review-policy",
        default="mark_only",
        choices=["mark_only", "allow_partial"],
        help="Whether unresolved slides remain unchanged or allow partial rendering.",
    )
    parser.add_argument("--debug-dir", default="", help="Optional debug output directory.")
    return parser.parse_args()


def load_glossary(path: Path) -> tuple[dict[str, dict], dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise RuntimeError("Glossary JSON must contain an 'entries' array.")
    lookup: dict[str, dict] = {}
    for row in entries:
        if not isinstance(row, dict):
            continue
        text_norm = normalize_slide_text(str(row.get("source_text_norm", "") or ""))
        target_text = str(row.get("target_text", "") or "").strip()
        if text_norm and target_text and text_norm not in lookup:
            lookup[text_norm] = row
    return lookup, payload if isinstance(payload, dict) else {}


def clear_pngs(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for png in path.glob("*.png"):
        png.unlink()


def _draw_labeled_bbox(
    image_bgr: np.ndarray,
    *,
    bbox: dict[str, int],
    color_bgr: tuple[int, int, int],
    label: str,
) -> None:
    x = int(bbox.get("x", 0) or 0)
    y = int(bbox.get("y", 0) or 0)
    w = max(1, int(bbox.get("w", 0) or 0))
    h = max(1, int(bbox.get("h", 0) or 0))
    cv2.rectangle(image_bgr, (x, y), (x + w, y + h), color_bgr, 2)

    text = str(label or "").strip()
    if not text:
        return

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.45
    thickness = 1
    pad_x = 4
    pad_y = 3
    (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    box_w = text_w + pad_x * 2
    box_h = text_h + baseline + pad_y * 2

    label_x = max(0, x)
    label_y = y - box_h - 2
    if label_y < 0:
        label_y = y + 2
    label_x2 = label_x + box_w
    label_y2 = label_y + box_h

    cv2.rectangle(image_bgr, (label_x, label_y), (label_x2, label_y2), color_bgr, thickness=-1)
    text_org = (label_x + pad_x, label_y2 - baseline - pad_y)
    cv2.putText(
        image_bgr,
        text,
        text_org,
        font,
        font_scale,
        (255, 255, 255),
        thickness,
        lineType=cv2.LINE_AA,
    )


def overlay_debug_image(
    image_bgr: np.ndarray,
    classified_entries: list[dict],
    unresolved_entries: list[dict],
    layout_strategy_by_unit: dict[int, str] | None = None,
    layout_bbox_by_unit: dict[int, dict[str, int]] | None = None,
) -> np.ndarray:
    overlay = image_bgr.copy()
    strategy_lookup = layout_strategy_by_unit or {}
    layout_bbox_lookup = layout_bbox_by_unit or {}
    unresolved_ids = {
        int(entry.get("unit_id", 0) or 0)
        for entry in unresolved_entries
        if int(entry.get("unit_id", 0) or 0) > 0
    }
    drawn_ids: set[int] = set()
    for entry in classified_entries:
        unit_id = int(entry.get("unit_id", 0) or 0)
        bbox = layout_bbox_lookup.get(unit_id, entry.get("bbox", {}))
        role = str(entry.get("role", "") or "").strip() or "text"
        unresolved = unit_id > 0 and unit_id in unresolved_ids
        color = (0, 0, 255) if unresolved else (0, 180, 0)
        strategy = str(strategy_lookup.get(unit_id, "") or "").strip()
        if unit_id > 0:
            label = f"{unit_id}:{role}:{strategy}" if strategy else f"{unit_id}:{role}"
        else:
            label = role
        _draw_labeled_bbox(overlay, bbox=bbox, color_bgr=color, label=label)
        if unit_id > 0:
            drawn_ids.add(unit_id)

    for entry in unresolved_entries:
        unit_id = int(entry.get("unit_id", 0) or 0)
        if unit_id > 0 and unit_id in drawn_ids:
            continue
        reason = str(entry.get("reason", "") or "").strip() or "unresolved"
        label = f"{unit_id}:{reason}" if unit_id > 0 else reason
        _draw_labeled_bbox(overlay, bbox=entry.get("bbox", {}), color_bgr=(0, 0, 255), label=label)
    return overlay


def _resolve_path(path_value: str) -> Path:
    path = Path(str(path_value or "").strip())
    if path.is_absolute():
        return path.resolve()
    return (ROOT_DIR / path).resolve()


def _bbox_xywh(bbox: dict[str, int]) -> tuple[int, int, int, int]:
    return (
        int(bbox.get("x", 0) or 0),
        int(bbox.get("y", 0) or 0),
        max(1, int(bbox.get("w", 0) or 0)),
        max(1, int(bbox.get("h", 0) or 0)),
    )


def _entry_render_left(entry: dict) -> int:
    bbox = _effective_entry_bbox(entry)
    layout = entry.get("layout", {})
    x, _y, _w, _h = _bbox_xywh(bbox)
    return int(entry.get("render_x", x + int(layout.get("offset_x", 0) or 0)))


def _clamp_int(value: int, low: int, high: int) -> int:
    if low > high:
        return int(low)
    return max(int(low), min(int(high), int(value)))


def _bbox_union(boxes: list[dict[str, int]]) -> dict[str, int]:
    if not boxes:
        return {"x": 0, "y": 0, "w": 0, "h": 0}
    x0 = min(int(box.get("x", 0) or 0) for box in boxes)
    y0 = min(int(box.get("y", 0) or 0) for box in boxes)
    x1 = max(int(box.get("x", 0) or 0) + max(1, int(box.get("w", 0) or 0)) for box in boxes)
    y1 = max(int(box.get("y", 0) or 0) + max(1, int(box.get("h", 0) or 0)) for box in boxes)
    return {"x": x0, "y": y0, "w": max(1, x1 - x0), "h": max(1, y1 - y0)}


def _is_list_entry(entry: dict) -> bool:
    return int(entry.get("list_marker_fragment_id", 0) or 0) > 0 or str(entry.get("role", "") or "").startswith("list_item_")


def _has_marker_anchor(entry: dict) -> bool:
    if int(entry.get("list_marker_fragment_id", 0) or 0) > 0:
        return True
    if _bool_value(entry.get("list_marker_inferred"), False):
        marker_bbox = _normalized_marker_bbox(entry)
        return marker_bbox["w"] > 0 and marker_bbox["h"] > 0
    return False


def _is_list_group(group: list[dict]) -> bool:
    return any(_is_list_entry(entry) for entry in group)


def _style_group_score(group: list[dict], entry: dict) -> float | None:
    entry_x, entry_y, entry_w, entry_h = _bbox_xywh(entry.get("bbox", {}))
    _last_x, last_y, _last_w, last_h = _bbox_xywh(group[-1].get("bbox", {}))
    median_x = int(round(float(np.median([_bbox_xywh(item.get("bbox", {}))[0] for item in group]))))
    median_h = max(1, int(round(float(np.median([_bbox_xywh(item.get("bbox", {}))[3] for item in group])))))
    median_w = max(1, int(round(float(np.median([_bbox_xywh(item.get("bbox", {}))[2] for item in group])))))

    x_tolerance = max(18, int(round(max(median_h, entry_h) * 0.9)))
    top_gap = entry_y - last_y
    vertical_gap = entry_y - (last_y + last_h)
    max_top_gap = max(34, int(round(max(median_h, entry_h) * 3.5)))
    min_vertical_gap = -max(6, int(round(min(median_h, entry_h) * 0.35)))
    width_ratio = float(entry_w) / float(max(1, median_w))

    if abs(entry_x - median_x) > x_tolerance:
        return None
    if top_gap < 0 or top_gap > max_top_gap:
        return None
    if vertical_gap < min_vertical_gap:
        return None
    if width_ratio < 0.45 or width_ratio > 2.4:
        return None

    return float(abs(entry_x - median_x) + max(0, top_gap - int(round(max(median_h, entry_h) * 2.2))))


def build_stacked_style_groups(entries: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    sorted_entries = sorted(entries, key=lambda item: (_bbox_xywh(item.get("bbox", {}))[1], _bbox_xywh(item.get("bbox", {}))[0]))
    for entry in sorted_entries:
        best_group: list[dict] | None = None
        best_score: float | None = None
        for group in groups:
            score = _style_group_score(group, entry)
            if score is None:
                continue
            if best_score is None or score < best_score:
                best_group = group
                best_score = score
        if best_group is None:
            groups.append([entry])
        else:
            best_group.append(entry)
    return [group for group in groups if len(group) >= 2]


def _normalized_marker_bbox(entry: dict) -> dict[str, int]:
    marker_bbox = entry.get("list_marker_bbox", {}) if isinstance(entry.get("list_marker_bbox", {}), dict) else {}
    if not marker_bbox:
        return {"x": 0, "y": 0, "w": 0, "h": 0}
    return {
        "x": int(marker_bbox.get("x", 0) or 0),
        "y": int(marker_bbox.get("y", 0) or 0),
        "w": max(1, int(marker_bbox.get("w", 0) or 0)),
        "h": max(1, int(marker_bbox.get("h", 0) or 0)),
    }


def _parse_hex_color(value: str) -> tuple[int, int, int] | None:
    text = str(value or "").strip()
    if not text or text.lower() in {"auto", "source", "source_entry", "source_median"}:
        return None
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6:
        return None
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except ValueError:
        return None


def _median_int(values: list[int], fallback: int) -> int:
    if not values:
        return int(fallback)
    return int(round(float(np.median(np.array(values, dtype=np.float32)))))


def _median_rgb(values: list[tuple[int, int, int]], fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    if not values:
        return tuple(int(v) for v in fallback)
    median = np.median(np.array(values, dtype=np.float32), axis=0)
    return tuple(int(round(v)) for v in median.tolist())


def _bool_value(value, default: bool) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


def _float_value(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _int_value(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _default_font_size_from_bbox(entry: dict) -> int:
    _x, _y, _w, h = _bbox_xywh(entry.get("bbox", {}))
    line_count = max(1, int(entry.get("line_count", 1) or 1))
    return max(8, int(round(float(h) / float(line_count) * 0.72)))


def _short_text(text: str, limit: int = 48) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= int(limit):
        return compact
    return compact[: max(4, int(limit) - 1)] + "\u2026"


def _alnum_only(text: str) -> str:
    raw = str(text or "")
    return "".join(ch for ch in raw if ch.isalnum())


def _is_noise_like_ocr_unit(unit: dict, classification: dict) -> bool:
    role = str(classification.get("role", "body") or "body").strip().lower()
    if role in {"title", "subtitle", "section_heading", "list_item_level_1", "list_item_level_2"}:
        return False
    if int(unit.get("list_marker_fragment_id", 0) or 0) > 0:
        return False
    if _bool_value(unit.get("list_marker_inferred"), False):
        return False

    source_text = str(unit.get("source_text", "") or "").strip()
    compact_alnum = _alnum_only(source_text)
    _x, _y, w, h = _bbox_xywh(unit.get("bbox", {}))
    area = int(w) * int(h)

    # Typical OCR blips from graphics/noise: tiny box + 0-2 chars (e.g. single "F").
    if len(compact_alnum) == 0 and area <= 700:
        return True
    if len(compact_alnum) <= 1 and area <= 1200:
        return True
    if len(compact_alnum) <= 2 and area <= 350:
        return True
    return False


def _parse_padding_shorthand(value: str) -> tuple[float, float, float, float] | None:
    text = str(value or "").strip()
    if not text:
        return None
    parts = text.replace(",", " ").split()
    if not 1 <= len(parts) <= 4:
        return None
    try:
        values = [float(part) for part in parts]
    except ValueError:
        return None
    if len(values) == 1:
        top = right = bottom = left = values[0]
    elif len(values) == 2:
        top, right = values
        bottom, left = top, right
    elif len(values) == 3:
        top, right, bottom = values
        left = right
    else:
        top, right, bottom, left = values
    return (top, right, bottom, left)


def _resolve_style_padding(style: dict) -> tuple[float, float, float, float]:
    padding = _parse_padding_shorthand(str(style.get("padding", "") or ""))
    if padding is not None:
        return padding
    pad_x = _float_value(style.get("box_padding_x_ratio"), 0.04)
    pad_y = _float_value(style.get("box_padding_y_ratio"), 0.08)
    top = _float_value(style.get("box_padding_top_ratio"), pad_y)
    right = _float_value(style.get("box_padding_right_ratio"), pad_x)
    bottom = _float_value(style.get("box_padding_bottom_ratio"), pad_y)
    left = _float_value(style.get("box_padding_left_ratio"), pad_x)
    return (top, right, bottom, left)


def _resolve_style_min_padding(style: dict, default_padding: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    min_padding = _parse_padding_shorthand(str(style.get("min_padding", "") or ""))
    if min_padding is not None:
        return (
            max(0.0, min(default_padding[0], float(min_padding[0]))),
            max(0.0, min(default_padding[1], float(min_padding[1]))),
            max(0.0, min(default_padding[2], float(min_padding[2]))),
            max(0.0, min(default_padding[3], float(min_padding[3]))),
        )

    default_top, default_right, default_bottom, default_left = default_padding
    min_pad_x_default = max(0.0, min(default_left, default_right) * 0.6)
    min_pad_y_default = max(0.0, min(default_top, default_bottom) * 0.6)
    min_pad_x = _float_value(style.get("min_box_padding_x_ratio"), min_pad_x_default)
    min_pad_y = _float_value(style.get("min_box_padding_y_ratio"), min_pad_y_default)
    top = max(0.0, min(default_top, _float_value(style.get("min_box_padding_top_ratio"), min_pad_y)))
    right = max(0.0, min(default_right, _float_value(style.get("min_box_padding_right_ratio"), min_pad_x)))
    bottom = max(0.0, min(default_bottom, _float_value(style.get("min_box_padding_bottom_ratio"), min_pad_y)))
    left = max(0.0, min(default_left, _float_value(style.get("min_box_padding_left_ratio"), min_pad_x)))
    return (top, right, bottom, left)


def _ratio_candidates(high: float, low: float) -> list[float]:
    high_value = float(high)
    low_value = max(0.0, min(float(low), high_value))
    values = [high_value]
    mid = high_value + (low_value - high_value) * 0.5
    if abs(mid - high_value) > 1e-6:
        values.append(mid)
    if abs(low_value - values[-1]) > 1e-6:
        values.append(low_value)
    return values


def _expand_candidates(max_expand_px: int, step_px: int) -> list[int]:
    max_expand = max(0, int(max_expand_px))
    if max_expand <= 0:
        return [0]
    step = max(4, int(step_px))
    values = [0]
    next_value = step
    while next_value < max_expand:
        values.append(next_value)
        next_value += step
    if values[-1] != max_expand:
        values.append(max_expand)
    return values


def _expand_bbox(
    base_bbox: dict[str, int],
    *,
    image_shape: tuple[int, ...],
    expand_left: int,
    expand_right: int,
    expand_up: int,
    expand_down: int,
) -> dict[str, int]:
    base_x, base_y, base_w, base_h = _bbox_xywh(base_bbox)
    image_h, image_w = image_shape[:2]
    x0 = max(0, base_x - max(0, int(expand_left)))
    y0 = max(0, base_y - max(0, int(expand_up)))
    x1 = min(image_w, base_x + base_w + max(0, int(expand_right)))
    y1 = min(image_h, base_y + base_h + max(0, int(expand_down)))
    return {"x": int(x0), "y": int(y0), "w": max(1, int(x1 - x0)), "h": max(1, int(y1 - y0))}


def _boxes_intersect(a: dict[str, int], b: dict[str, int], margin: int = 0) -> bool:
    pad = max(0, int(margin))
    ax0 = int(a.get("x", 0) or 0) - pad
    ay0 = int(a.get("y", 0) or 0) - pad
    ax1 = int(a.get("x", 0) or 0) + max(1, int(a.get("w", 0) or 0)) + pad
    ay1 = int(a.get("y", 0) or 0) + max(1, int(a.get("h", 0) or 0)) + pad
    bx0 = int(b.get("x", 0) or 0) - pad
    by0 = int(b.get("y", 0) or 0) - pad
    bx1 = int(b.get("x", 0) or 0) + max(1, int(b.get("w", 0) or 0)) + pad
    by1 = int(b.get("y", 0) or 0) + max(1, int(b.get("h", 0) or 0)) + pad
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def _collides_any(candidate_bbox: dict[str, int], blocked_boxes: list[dict[str, int]], margin: int = 2) -> bool:
    for blocked in blocked_boxes:
        if not isinstance(blocked, dict) or not blocked:
            continue
        if _boxes_intersect(candidate_bbox, blocked, margin=margin):
            return True
    return False


def _effective_entry_bbox(entry: dict) -> dict[str, int]:
    layout_bbox = entry.get("layout_bbox")
    if isinstance(layout_bbox, dict) and layout_bbox:
        return dict(layout_bbox)
    return dict(entry.get("bbox", {}))


def _slot_container_defaults(role: str, event_id: int) -> tuple[bool, float, float]:
    normalized_role = str(role or "").strip().lower()
    if normalized_role == "title":
        if int(event_id) == 1:
            return (True, 0.62, 0.16)
        return (True, 0.62, 0.10)
    if normalized_role == "subtitle":
        if int(event_id) == 1:
            return (True, 0.42, 0.12)
        return (True, 0.42, 0.08)
    if normalized_role == "caption":
        return (True, 0.16, 0.05)
    return (False, 0.0, 0.0)


def _measure_text_dimensions(font: ImageFont.FreeTypeFont, text: str) -> tuple[int, int]:
    lines = [line for line in str(text or "").splitlines()]
    if not lines:
        lines = [str(text or "").strip()]
    if not lines:
        lines = [""]
    widths: list[int] = []
    heights: list[int] = []
    for line in lines:
        sample = line if line else " "
        left, top, right, bottom = font.getbbox(sample)
        widths.append(max(1, int(right - left)))
        heights.append(max(1, int(bottom - top)))
    line_height = max(1, int(max(heights, default=font.size)))
    total_height = max(1, line_height * len(lines))
    return max(1, int(max(widths, default=1))), total_height


def _entry_layout_start_bbox(entry: dict, style: dict, image_shape: tuple[int, ...]) -> dict[str, int]:
    bbox_x, bbox_y, bbox_w, bbox_h = _bbox_xywh(entry.get("bbox", {}))
    role = str(entry.get("role", "body") or "body")
    event_id = int(entry.get("event_id", 0) or 0)
    default_slot_enabled, default_min_width_ratio, default_min_height_ratio = _slot_container_defaults(role, event_id)
    slot_enabled = _bool_value(style.get("slot_container_enabled"), default_slot_enabled)
    if not slot_enabled:
        return _expand_bbox(
            {"x": bbox_x, "y": bbox_y, "w": bbox_w, "h": bbox_h},
            image_shape=image_shape,
            expand_left=0,
            expand_right=0,
            expand_up=0,
            expand_down=0,
        )

    image_h, image_w = image_shape[:2]
    min_width_ratio = max(0.0, _float_value(style.get("slot_min_width_ratio"), default_min_width_ratio))
    min_height_ratio = max(0.0, _float_value(style.get("slot_min_height_ratio"), default_min_height_ratio))
    min_width_px = max(0, _int_value(style.get("slot_min_width_px"), 0))
    min_height_px = max(0, _int_value(style.get("slot_min_height_px"), 0))
    min_width = max(min_width_px, int(round(float(image_w) * min_width_ratio)))
    min_height = max(min_height_px, int(round(float(image_h) * min_height_ratio)))

    # For fixed-size text, compute a text-width-aware start box so non-event1 titles/subtitles
    # are not constrained by the tiny OCR source box.
    font_size_mode = str(style.get("font_size_mode", "fixed") or "fixed").strip().lower()
    if font_size_mode == "fixed":
        font_size = max(8, _int_value(style.get("font_size"), 8))
        font_path_raw = str(style.get("font_path", "") or "").strip()
        target_text = str(entry.get("target_text", "") or "").strip()
        if font_path_raw and target_text:
            try:
                font = ImageFont.truetype(str(font_path_raw), size=int(font_size))
                text_width, text_height = _measure_text_dimensions(font, target_text)
                pad_top = max(0.0, _float_value(style.get("box_padding_top_ratio"), _float_value(style.get("box_padding_y_ratio"), 0.08)))
                pad_right = max(0.0, _float_value(style.get("box_padding_right_ratio"), _float_value(style.get("box_padding_x_ratio"), 0.04)))
                pad_bottom = max(0.0, _float_value(style.get("box_padding_bottom_ratio"), _float_value(style.get("box_padding_y_ratio"), 0.08)))
                pad_left = max(0.0, _float_value(style.get("box_padding_left_ratio"), _float_value(style.get("box_padding_x_ratio"), 0.04)))
                width_denominator = max(0.05, 1.0 - min(0.95, pad_left + pad_right))
                height_denominator = max(0.05, 1.0 - min(0.95, pad_top + pad_bottom))
                min_width = max(min_width, int(round(float(text_width) / width_denominator)))
                min_height = max(min_height, int(round(float(text_height) / height_denominator)))
            except Exception:
                pass

    start_bbox = {
        "x": int(bbox_x),
        "y": int(bbox_y),
        "w": max(int(bbox_w), int(min_width)),
        "h": max(int(bbox_h), int(min_height)),
    }
    return _expand_bbox(
        start_bbox,
        image_shape=image_shape,
        expand_left=0,
        expand_right=0,
        expand_up=0,
        expand_down=0,
    )


def _sample_source_font_size(entry: dict, style: dict, font_path: Path) -> int:
    source_text = str(entry.get("source_text", "") or "").strip()
    bbox = entry.get("bbox", {})
    pad_top, pad_right, pad_bottom, pad_left = _resolve_style_padding(style)
    source_layout = fit_text_to_box(
        text=source_text,
        bbox=bbox,
        font_path=font_path,
        min_font_size=8,
        max_font_size=max(8, _bbox_xywh(bbox)[3]),
        line_spacing_ratio=_float_value(style.get("line_spacing_ratio"), 0.22),
        pad_top_ratio=pad_top,
        pad_right_ratio=pad_right,
        pad_bottom_ratio=pad_bottom,
        pad_left_ratio=pad_left,
    )
    if source_layout is not None:
        return int(source_layout.get("font_size", 8) or 8)
    return _default_font_size_from_bbox(entry)


def _build_style_metrics(entries: list[dict], style_config: dict, style_config_path: Path, fallback_font_path: Path) -> dict:
    role_font_sizes: dict[str, list[int]] = {}
    slot_font_sizes: dict[str, list[int]] = {}
    role_colors: dict[str, list[tuple[int, int, int]]] = {}
    slot_colors: dict[str, list[tuple[int, int, int]]] = {}

    for entry in entries:
        role = str(entry.get("role", "body") or "body")
        slot_id = str(entry.get("slot_id", f"{role}.middle_left") or f"{role}.middle_left")
        style = merged_style(style_config, role=role, slot_id=slot_id)
        font_path = resolve_style_font_path(
            style,
            root_dir=ROOT_DIR,
            config_path=style_config_path,
            fallback_font_path=fallback_font_path,
        )
        sample_font_size = _sample_source_font_size(entry, style, font_path)
        role_font_sizes.setdefault(role, []).append(sample_font_size)
        slot_font_sizes.setdefault(slot_id, []).append(sample_font_size)

        source_color_rgb = tuple(int(v) for v in entry.get("source_text_color_rgb", (32, 32, 32)))
        role_colors.setdefault(role, []).append(source_color_rgb)
        slot_colors.setdefault(slot_id, []).append(source_color_rgb)

    return {
        "role_font_sizes": role_font_sizes,
        "slot_font_sizes": slot_font_sizes,
        "role_colors": role_colors,
        "slot_colors": slot_colors,
    }


def _resolve_entry_style(
    entry: dict,
    style_config: dict,
    style_config_path: Path,
    style_metrics: dict,
    fallback_font_path: Path,
    global_max_font_size: int,
) -> dict:
    role = str(entry.get("role", "body") or "body")
    slot_id = str(entry.get("slot_id", f"{role}.middle_left") or f"{role}.middle_left")
    event_id = int(entry.get("event_id", 0) or 0)
    style = merged_style(style_config, role=role, slot_id=slot_id)
    font_path = resolve_style_font_path(
        style,
        root_dir=ROOT_DIR,
        config_path=style_config_path,
        fallback_font_path=fallback_font_path,
    )

    # Deterministic styling defaults to fixed size, but keeps mode awareness for fast-path decisions.
    font_size_mode = str(style.get("font_size_mode", "fixed") or "fixed").strip().lower()
    if font_size_mode not in {"fixed", "fit"}:
        font_size_mode = "fixed"
    requested_font_size = _int_value(style.get("font_size"), _default_font_size_from_bbox(entry))
    global_font_cap = max(8, int(global_max_font_size))
    font_size = min(max(8, int(requested_font_size)), global_font_cap)

    if font_size_mode == "fixed":
        min_font_size = int(font_size)
    else:
        raw_min_font_size = style.get("min_font_size", font_size)
        min_font_size = _int_value(raw_min_font_size, font_size)
        min_font_size = max(8, min(int(font_size), int(min_font_size)))

    text_color_mode = str(style.get("text_color_mode", "source_median") or "source_median").strip().lower()
    fixed_color = _parse_hex_color(str(style.get("text_color", "") or ""))
    source_color_rgb = tuple(int(v) for v in entry.get("source_text_color_rgb", (32, 32, 32)))
    slot_color_samples = list(style_metrics.get("slot_colors", {}).get(slot_id, []))
    role_color_samples = list(style_metrics.get("role_colors", {}).get(role, []))
    if text_color_mode == "fixed" and fixed_color is not None:
        text_color_rgb = fixed_color
    elif text_color_mode == "source_entry":
        text_color_rgb = source_color_rgb
    else:
        text_color_rgb = _median_rgb(slot_color_samples, _median_rgb(role_color_samples, source_color_rgb))

    pad_top, pad_right, pad_bottom, pad_left = _resolve_style_padding(style)
    min_pad_top, min_pad_right, min_pad_bottom, min_pad_left = _resolve_style_min_padding(
        style, (pad_top, pad_right, pad_bottom, pad_left)
    )
    line_spacing_ratio = _float_value(style.get("line_spacing_ratio"), 0.22)
    min_line_spacing_ratio = max(
        0.04,
        min(
            line_spacing_ratio,
            _float_value(style.get("min_line_spacing_ratio"), max(0.06, line_spacing_ratio * 0.7)),
        ),
    )
    list_item_gap_ratio = _float_value(style.get("list_item_gap_ratio"), 0.72)
    list_bullet_gap_ratio = _float_value(style.get("list_bullet_gap_ratio"), 0.45)
    min_list_item_gap_ratio = max(
        0.08,
        min(
            list_item_gap_ratio,
            _float_value(style.get("min_list_item_gap_ratio"), max(0.12, list_item_gap_ratio * 0.7)),
        ),
    )
    min_list_bullet_gap_ratio = max(
        0.08,
        min(
            list_bullet_gap_ratio,
            _float_value(style.get("min_list_bullet_gap_ratio"), max(0.1, list_bullet_gap_ratio * 0.75)),
        ),
    )
    default_slot_container_enabled, default_slot_min_width_ratio, default_slot_min_height_ratio = _slot_container_defaults(role, event_id)
    return {
        "role": role,
        "slot_id": slot_id,
        "font_path": str(font_path),
        "font_size_mode": font_size_mode,
        "font_size": font_size,
        "min_font_size": min_font_size,
        "line_spacing_ratio": line_spacing_ratio,
        "min_line_spacing_ratio": min_line_spacing_ratio,
        "padding": str(style.get("padding", "") or "").strip(),
        "box_padding_x_ratio": _float_value(style.get("box_padding_x_ratio"), 0.04),
        "box_padding_y_ratio": _float_value(style.get("box_padding_y_ratio"), 0.08),
        "box_padding_top_ratio": pad_top,
        "box_padding_right_ratio": pad_right,
        "box_padding_bottom_ratio": pad_bottom,
        "box_padding_left_ratio": pad_left,
        "min_box_padding_top_ratio": min_pad_top,
        "min_box_padding_right_ratio": min_pad_right,
        "min_box_padding_bottom_ratio": min_pad_bottom,
        "min_box_padding_left_ratio": min_pad_left,
        "list_item_gap_ratio": list_item_gap_ratio,
        "list_bullet_gap_ratio": list_bullet_gap_ratio,
        "min_list_item_gap_ratio": min_list_item_gap_ratio,
        "min_list_bullet_gap_ratio": min_list_bullet_gap_ratio,
        "max_expand_x_ratio": max(0.0, _float_value(style.get("max_expand_x_ratio"), 0.45)),
        "max_expand_y_ratio": max(0.0, _float_value(style.get("max_expand_y_ratio"), 0.35)),
        "max_expand_right_ratio": max(0.0, _float_value(style.get("max_expand_right_ratio"), _float_value(style.get("max_expand_x_ratio"), 0.45))),
        "max_expand_down_ratio": max(0.0, _float_value(style.get("max_expand_down_ratio"), _float_value(style.get("max_expand_y_ratio"), 0.35))),
        "max_expand_left_ratio": max(0.0, _float_value(style.get("max_expand_left_ratio"), 0.0)),
        "max_expand_up_ratio": max(0.0, _float_value(style.get("max_expand_up_ratio"), 0.0)),
        "max_expand_right_px": max(0, _int_value(style.get("max_expand_right_px"), 0)),
        "max_expand_down_px": max(0, _int_value(style.get("max_expand_down_px"), 0)),
        "max_expand_left_px": max(0, _int_value(style.get("max_expand_left_px"), 0)),
        "max_expand_up_px": max(0, _int_value(style.get("max_expand_up_px"), 0)),
        "expand_step_px": max(4, _int_value(style.get("expand_step_px"), 12)),
        "allow_hyphenation": _bool_value(style.get("allow_hyphenation"), True),
        "hyphenation_min_word_length": max(4, _int_value(style.get("hyphenation_min_word_length"), 8)),
        "collision_margin_px": max(0, _int_value(style.get("collision_margin_px"), 2)),
        "slot_container_enabled": _bool_value(style.get("slot_container_enabled"), default_slot_container_enabled),
        "slot_min_width_ratio": max(0.0, _float_value(style.get("slot_min_width_ratio"), default_slot_min_width_ratio)),
        "slot_min_height_ratio": max(0.0, _float_value(style.get("slot_min_height_ratio"), default_slot_min_height_ratio)),
        "slot_min_width_px": max(0, _int_value(style.get("slot_min_width_px"), 0)),
        "slot_min_height_px": max(0, _int_value(style.get("slot_min_height_px"), 0)),
        "text_color_mode": text_color_mode,
        "text_color_rgb": text_color_rgb,
        "stack_align_left": _bool_value(style.get("stack_align_left"), True),
    }


def apply_list_block_layout(
    entries: list[dict],
    image_shape: tuple[int, ...],
    *,
    layout_max_attempts: int,
    layout_max_ms: int,
    max_expand_px: int,
) -> tuple[int, int, list[dict[str, int]]]:
    groups_applied = 0
    grouped_fragments = 0
    occupied_group_boxes: list[dict[str, int]] = []
    all_entry_boxes = [
        {"entry_id": id(entry), "bbox": dict(entry.get("bbox", {}))}
        for entry in entries
        if isinstance(entry.get("bbox", {}), dict) and entry.get("bbox", {})
    ]

    for group_index, group in enumerate(build_stacked_style_groups(entries), start=1):
        if not _is_list_group(group):
            continue
        sorted_group = sorted(group, key=lambda entry: (_bbox_xywh(entry.get("bbox", {}))[1], _bbox_xywh(entry.get("bbox", {}))[0]))
        group_entry_ids = {id(entry) for entry in sorted_group}
        container = _bbox_union(
            [dict(entry.get("bbox", {})) for entry in sorted_group]
            + [
                _normalized_marker_bbox(entry)
                for entry in sorted_group
                if _normalized_marker_bbox(entry)["w"] > 0 and _normalized_marker_bbox(entry)["h"] > 0
            ]
        )
        if container["w"] <= 0 or container["h"] <= 0:
            continue

        base_style = dict(sorted_group[0].get("resolved_style", {}))
        font_path_raw = str(base_style.get("font_path", "") or "").strip()
        if not font_path_raw:
            continue
        font_path = Path(font_path_raw)
        base_font_size = max(8, min(int(entry.get("resolved_style", {}).get("font_size", 8) or 8) for entry in sorted_group))
        min_font_size = max(8, min(int(entry.get("resolved_style", {}).get("min_font_size", 8) or 8) for entry in sorted_group))
        base_line_spacing_ratio = _float_value(base_style.get("line_spacing_ratio"), 0.22)
        min_line_spacing_ratio = max(
            0.04,
            min(
                base_line_spacing_ratio,
                _float_value(base_style.get("min_line_spacing_ratio"), max(0.06, base_line_spacing_ratio * 0.7)),
            ),
        )
        base_item_gap_ratio = _float_value(base_style.get("list_item_gap_ratio"), 0.72)
        min_item_gap_ratio = max(
            0.08,
            min(
                base_item_gap_ratio,
                _float_value(base_style.get("min_list_item_gap_ratio"), max(0.12, base_item_gap_ratio * 0.7)),
            ),
        )
        base_bullet_gap_ratio = _float_value(base_style.get("list_bullet_gap_ratio"), 0.45)
        min_bullet_gap_ratio = max(
            0.08,
            min(
                base_bullet_gap_ratio,
                _float_value(base_style.get("min_list_bullet_gap_ratio"), max(0.1, base_bullet_gap_ratio * 0.75)),
            ),
        )
        allow_hyphenation = _bool_value(base_style.get("allow_hyphenation"), True)
        hyphenation_min_word_length = max(4, _int_value(base_style.get("hyphenation_min_word_length"), 8))
        collision_margin = max(0, _int_value(base_style.get("collision_margin_px"), 2))
        expand_step_px = max(4, _int_value(base_style.get("expand_step_px"), 12))
        max_expand_right_ratio_px = max(
            0,
            int(
                round(
                    container["w"]
                    * _float_value(
                        base_style.get("max_expand_right_ratio"),
                        _float_value(base_style.get("max_expand_x_ratio"), 0.45),
                    )
                )
            ),
        )
        max_expand_down_ratio_px = max(
            0,
            int(
                round(
                    container["h"]
                    * _float_value(
                        base_style.get("max_expand_down_ratio"),
                        _float_value(base_style.get("max_expand_y_ratio"), 0.35),
                    )
                )
            ),
        )
        style_expand_right_px = max(0, _int_value(base_style.get("max_expand_right_px"), 0))
        style_expand_down_px = max(0, _int_value(base_style.get("max_expand_down_px"), 0))
        global_expand_px = max(0, int(max_expand_px))
        max_expand_right = (
            style_expand_right_px
            if style_expand_right_px > 0
            else (global_expand_px if global_expand_px > 0 else max_expand_right_ratio_px)
        )
        max_expand_down = (
            style_expand_down_px
            if style_expand_down_px > 0
            else (global_expand_px if global_expand_px > 0 else max_expand_down_ratio_px)
        )
        # Keep anchor on original top-left and grow only to the right/down.
        max_expand_left = 0
        max_expand_up = 0

        prefix_text = next(
            (
                str(candidate.get("list_marker_text", "") or "").strip()
                for candidate in sorted_group
                if str(candidate.get("list_marker_text", "") or "").strip()
            ),
            "\u2022",
        )

        marker_boxes = [
            _normalized_marker_bbox(entry)
            for entry in sorted_group
            if _normalized_marker_bbox(entry)["w"] > 0 and _normalized_marker_bbox(entry)["h"] > 0
        ]
        marker_entries = [entry for entry in sorted_group if _normalized_marker_bbox(entry)["w"] > 0 and _normalized_marker_bbox(entry)["h"] > 0]
        marker_x_values = [int(box.get("x", 0) or 0) for box in marker_boxes]
        marker_right_values = [int(box.get("x", 0) or 0) + max(1, int(box.get("w", 0) or 0)) for box in marker_boxes]
        marker_column_x = min(marker_x_values) if marker_x_values else container["x"]
        marker_column_w = max(marker_right_values, default=marker_column_x + max(1, int(round(container["w"] * 0.06)))) - marker_column_x

        original_marker_dx = (
            int(
                round(
                    float(
                        np.median(
                            [
                                int(_normalized_marker_bbox(entry)["x"]) - int(entry.get("bbox", {}).get("x", 0) or 0)
                                for entry in marker_entries
                            ]
                        )
                    )
                )
            )
            if marker_entries
            else -max(18, int(round(container["w"] * 0.06)))
        )
        original_marker_dy = (
            int(
                round(
                    float(
                        np.median(
                            [
                                int(_normalized_marker_bbox(entry)["y"]) - int(entry.get("bbox", {}).get("y", 0) or 0)
                                for entry in marker_entries
                            ]
                        )
                    )
                )
            )
            if marker_entries
            else 0
        )
        original_marker_w = max(
            [int(_normalized_marker_bbox(entry)["w"]) for entry in marker_entries],
            default=max(1, marker_column_w),
        )
        original_marker_h = max(
            [int(_normalized_marker_bbox(entry)["h"]) for entry in marker_entries],
            default=max(1, marker_column_w),
        )

        blocked_boxes = [
            dict(item.get("bbox", {}))
            for item in all_entry_boxes
            if int(item.get("entry_id", 0) or 0) not in group_entry_ids and isinstance(item.get("bbox", {}), dict)
        ]
        blocked_boxes.extend(dict(box) for box in occupied_group_boxes if isinstance(box, dict))

        left_candidates = _expand_candidates(max_expand_left, expand_step_px)
        right_candidates = _expand_candidates(max_expand_right, expand_step_px)
        up_candidates = _expand_candidates(max_expand_up, expand_step_px)
        down_candidates = _expand_candidates(max_expand_down, expand_step_px)
        expansion_candidates = sorted(
            {
                (expand_left, expand_right, expand_up, expand_down)
                for expand_down in down_candidates
                for expand_right in right_candidates
                for expand_left in left_candidates
                for expand_up in up_candidates
            },
            key=lambda item: (item[0] + item[1] + item[2] + item[3], item[3], item[1], item[0], item[2]),
        )

        fixed_font_size = str(base_style.get("font_size_mode", "fixed") or "fixed").strip().lower() == "fixed"
        if fixed_font_size:
            line_ratio_candidates = [base_line_spacing_ratio]
            item_gap_ratio_candidates = [base_item_gap_ratio]
            bullet_gap_ratio_candidates = [base_bullet_gap_ratio]
            hyphenation_candidates = [False]
        else:
            line_ratio_candidates = _ratio_candidates(base_line_spacing_ratio, min_line_spacing_ratio)
            item_gap_ratio_candidates = _ratio_candidates(base_item_gap_ratio, min_item_gap_ratio)
            bullet_gap_ratio_candidates = _ratio_candidates(base_bullet_gap_ratio, min_bullet_gap_ratio)
            hyphenation_candidates = [False, True] if allow_hyphenation else [False]
        budget_max_attempts = max(0, int(layout_max_attempts))
        budget_max_ms = max(0, int(layout_max_ms))
        budget_started = time.perf_counter()
        budget_attempts = 0

        def _budget_hit() -> bool:
            if budget_max_attempts > 0 and budget_attempts >= budget_max_attempts:
                return True
            if budget_max_ms > 0:
                elapsed_ms = int(round((time.perf_counter() - budget_started) * 1000.0))
                if elapsed_ms >= budget_max_ms:
                    return True
            return False

        chosen_layouts: list[dict] | None = None
        chosen_font_size = 0
        chosen_item_gap = 0
        chosen_line_spacing_ratio = base_line_spacing_ratio
        chosen_hyphenation = False
        chosen_container = dict(container)
        chosen_block_x = int(marker_column_x)
        chosen_block_w = max(48, container["x"] + container["w"] - chosen_block_x)
        chosen_strategy = "fit"
        budget_exceeded = False
        print(
            (
                f"[SlideTranslate] list-group start: group={group_index} items={len(sorted_group)} "
                f"font={base_font_size} fixed_font={int(fixed_font_size)}"
            ),
            flush=True,
        )

        for expand_left, expand_right, expand_up, expand_down in expansion_candidates:
            if _budget_hit():
                budget_exceeded = True
                break
            candidate_container = _expand_bbox(
                container,
                image_shape=image_shape,
                expand_left=expand_left,
                expand_right=expand_right,
                expand_up=expand_up,
                expand_down=expand_down,
            )
            expanded_candidate = (expand_left + expand_right + expand_up + expand_down) > 0
            if expanded_candidate and (not fixed_font_size) and _collides_any(candidate_container, blocked_boxes, margin=collision_margin):
                continue

            candidate_block_x = min(int(marker_column_x), int(candidate_container["x"]))
            candidate_block_w = max(48, int(candidate_container["x"]) + int(candidate_container["w"]) - candidate_block_x)

            found = False
            for use_hyphenation in hyphenation_candidates:
                if found:
                    break
                for line_spacing_ratio in line_ratio_candidates:
                    if found:
                        break
                    for item_gap_ratio in item_gap_ratio_candidates:
                        if found:
                            break
                        for bullet_gap_ratio in bullet_gap_ratio_candidates:
                            if found:
                                break
                            font_sizes: list[int] | range
                            if fixed_font_size:
                                font_sizes = [int(base_font_size)]
                            else:
                                font_sizes = range(base_font_size, min_font_size - 1, -1)
                            for font_size in font_sizes:
                                if _budget_hit():
                                    budget_exceeded = True
                                    break
                                budget_attempts += 1
                                bullet_gap = max(4, int(round(float(bullet_gap_ratio) * font_size)))
                                item_gap = max(2, int(round(float(item_gap_ratio) * font_size)))
                                layouts: list[dict] = []
                                for entry in sorted_group:
                                    layout = layout_hanging_text_block(
                                        text=str(entry.get("target_text", "") or ""),
                                        font_path=font_path,
                                        font_size=font_size,
                                        max_width=candidate_block_w,
                                        prefix_text=prefix_text,
                                        prefix_gap=bullet_gap,
                                        line_spacing_ratio=float(line_spacing_ratio),
                                        allow_hyphenation=use_hyphenation,
                                        hyphenation_min_word_length=hyphenation_min_word_length,
                                    )
                                    if layout is None:
                                        layouts = []
                                        break
                                    layouts.append(layout)
                                if not layouts:
                                    continue
                                total_height = sum(int(layout.get("text_height", 0) or 0) for layout in layouts)
                                if len(layouts) > 1:
                                    total_height += item_gap * (len(layouts) - 1)
                                if total_height > int(candidate_container["h"]):
                                    continue
                                chosen_layouts = layouts
                                chosen_font_size = font_size
                                chosen_item_gap = item_gap
                                chosen_line_spacing_ratio = float(line_spacing_ratio)
                                chosen_hyphenation = bool(use_hyphenation)
                                chosen_container = dict(candidate_container)
                                chosen_block_x = int(candidate_block_x)
                                chosen_block_w = int(candidate_block_w)
                                compacted = (
                                    line_spacing_ratio < (base_line_spacing_ratio - 1e-6)
                                    or item_gap_ratio < (base_item_gap_ratio - 1e-6)
                                    or bullet_gap_ratio < (base_bullet_gap_ratio - 1e-6)
                                    or font_size < base_font_size
                                )
                                if use_hyphenation:
                                    chosen_strategy = "hyphenate"
                                elif expanded_candidate:
                                    chosen_strategy = "expand"
                                elif compacted:
                                    chosen_strategy = "compact"
                                else:
                                    chosen_strategy = "fit"
                                found = True
                                break
                            if budget_exceeded:
                                break
                        if budget_exceeded:
                            break
                    if budget_exceeded:
                        break
                if budget_exceeded:
                    break
            if found:
                break
            if budget_exceeded:
                break

        if not chosen_layouts:
            if budget_exceeded:
                print(
                    (
                        f"[SlideTranslate] list-group budget exceeded: group={group_index} "
                        f"attempts={budget_attempts} max_attempts={budget_max_attempts} max_ms={budget_max_ms}"
                    ),
                    flush=True,
                )
            continue
        print(
            (
                f"[SlideTranslate] list-group ok: group={group_index} strategy={chosen_strategy} "
                f"font={chosen_font_size} attempts={budget_attempts}"
            ),
            flush=True,
        )

        total_height = sum(int(layout.get("text_height", 0) or 0) for layout in chosen_layouts)
        if len(chosen_layouts) > 1:
            total_height += chosen_item_gap * (len(chosen_layouts) - 1)
        current_y = int(chosen_container["y"])
        for entry, layout in zip(sorted_group, chosen_layouts, strict=True):
            original_mask_boxes = list(entry.get("mask_boxes", [entry.get("mask_bbox")]))
            if int(entry.get("list_marker_fragment_id", 0) or 0) > 0:
                original_marker_bbox = _normalized_marker_bbox(entry)
            else:
                bbox_x, bbox_y, _bbox_w, _bbox_h = _bbox_xywh(entry.get("bbox", {}))
                original_marker_bbox = {
                    "x": bbox_x + original_marker_dx,
                    "y": bbox_y + original_marker_dy,
                    "w": original_marker_w,
                    "h": original_marker_h,
                }
            if original_marker_bbox["w"] > 0 and original_marker_bbox["h"] > 0:
                original_mask_boxes.append(
                    inflate_bbox(
                        original_marker_bbox,
                        image_shape,
                        max(2, int(round(min(original_marker_bbox["w"], original_marker_bbox["h"]) * 0.35))),
                    )
                )
            entry["layout"] = layout
            entry["layout_bbox"] = {
                "x": int(chosen_block_x),
                "y": int(current_y),
                "w": int(chosen_block_w),
                "h": max(1, int(layout.get("text_height", 0) or 0)),
            }
            entry["layout_strategy"] = chosen_strategy
            entry["layout_line_spacing_ratio"] = chosen_line_spacing_ratio
            entry["layout_hyphenation"] = chosen_hyphenation
            entry["font_path"] = str(font_path)
            entry["render_x"] = int(chosen_block_x)
            entry["render_y"] = int(current_y)
            entry["text_color_rgb"] = tuple(int(v) for v in entry.get("resolved_style", {}).get("text_color_rgb", entry.get("text_color_rgb", (32, 32, 32))))
            entry["mask_boxes"] = [box for box in original_mask_boxes if isinstance(box, dict) and box]
            entry["style_group_id"] = f"list_block_{group_index}"
            entry["style_group_size"] = len(sorted_group)
            entry["style_group_kind"] = "list_block"
            entry["applied_font_size"] = chosen_font_size
            entry.pop("render_marker_text", None)
            entry.pop("render_marker_bbox", None)
            entry.pop("render_marker_font_size", None)
            current_y += int(layout.get("text_height", 0) or 0) + chosen_item_gap

        occupied_group_boxes.append(dict(chosen_container))
        groups_applied += 1
        grouped_fragments += len(sorted_group)

    return groups_applied, grouped_fragments, occupied_group_boxes


def align_stacked_style_groups(entries: list[dict]) -> tuple[int, int]:
    groups_applied = 0
    grouped_fragments = 0
    for group_index, group in enumerate(build_stacked_style_groups(entries), start=1):
        if _is_list_group(group):
            continue
        if not all(entry.get("layout") for entry in group):
            continue
        if not all(_bool_value(entry.get("resolved_style", {}).get("stack_align_left"), True) for entry in group):
            continue
        style_keys = {
            (
                str(entry.get("role", "") or ""),
                str(entry.get("slot_id", "") or ""),
                str(entry.get("font_path", "") or ""),
                int(entry.get("layout", {}).get("font_size", 0) or 0),
            )
            for entry in group
        }
        if len(style_keys) != 1:
            continue
        preferred_left = int(round(float(np.median([_entry_render_left(item) for item in group]))))
        for item in group:
            layout = item.get("layout", {})
            bbox_x, _bbox_y, bbox_w, _bbox_h = _bbox_xywh(_effective_entry_bbox(item))
            max_left = bbox_x + max(0, bbox_w - int(layout.get("text_width", 0) or 0))
            item["render_x"] = _clamp_int(preferred_left, bbox_x, max_left)
            item["style_group_id"] = f"stacked_style_{group_index}"
            item["style_group_size"] = len(group)
            item["style_group_kind"] = "stacked_style"
            grouped_fragments += 1
        groups_applied += 1
    return groups_applied, grouped_fragments


def assign_list_marker_rendering(entries: list[dict], image_shape: tuple[int, ...]) -> tuple[int, int]:
    grouped_entry_ids: set[int] = set()
    groups_with_markers = 0
    markers_rendered = 0

    for group in build_stacked_style_groups(entries):
        if any(str(entry.get("style_group_kind", "") or "") == "list_block" for entry in group):
            grouped_entry_ids.update(id(entry) for entry in group)
            continue
        actual_marker_entries = [
            entry
            for entry in group
            if _has_marker_anchor(entry) and isinstance(entry.get("list_marker_bbox", {}), dict)
        ]
        group = [entry for entry in group if entry.get("layout")]
        if not actual_marker_entries or not group:
            continue

        groups_with_markers += 1
        grouped_entry_ids.update(id(entry) for entry in group)
        shared_font_size = min(int(entry.get("layout", {}).get("font_size", 8) or 8) for entry in group)
        marker_texts = [str(entry.get("list_marker_text", "") or "").strip() for entry in actual_marker_entries]
        shared_marker_text = next((text for text in marker_texts if text), "\u2022")
        dx_values = []
        dy_values = []
        w_values = []
        h_values = []
        for entry in actual_marker_entries:
            marker_bbox = _normalized_marker_bbox(entry)
            bbox_x, bbox_y, _bbox_w, _bbox_h = _bbox_xywh(entry.get("bbox", {}))
            dx_values.append(int(marker_bbox["x"]) - bbox_x)
            dy_values.append(int(marker_bbox["y"]) - bbox_y)
            w_values.append(int(marker_bbox["w"]))
            h_values.append(int(marker_bbox["h"]))
        shared_dx = int(round(float(np.median(dx_values)))) if dx_values else -max(18, int(round(shared_font_size * 1.6)))
        shared_dy = int(round(float(np.median(dy_values)))) if dy_values else max(0, int(round(shared_font_size * 0.15)))
        shared_w = max(w_values, default=max(1, int(round(shared_font_size * 0.5))))
        shared_h = max(h_values, default=max(1, int(round(shared_font_size * 0.5))))

        for entry in group:
            text_font_size = int(entry.get("layout", {}).get("font_size", shared_font_size) or shared_font_size)
            bbox_x, bbox_y, _bbox_w, _bbox_h = _bbox_xywh(entry.get("bbox", {}))
            if _has_marker_anchor(entry):
                marker_bbox = _normalized_marker_bbox(entry)
            else:
                marker_bbox = {
                    "x": bbox_x + shared_dx,
                    "y": bbox_y + shared_dy,
                    "w": shared_w,
                    "h": shared_h,
                }
            marker_bbox = inflate_bbox(marker_bbox, image_shape, 0)
            entry["render_marker_text"] = shared_marker_text
            entry["render_marker_bbox"] = marker_bbox
            entry["render_marker_font_size"] = text_font_size
            existing_mask_boxes = list(entry.get("mask_boxes", [entry.get("mask_bbox")]))
            existing_mask_boxes.append(inflate_bbox(marker_bbox, image_shape, max(2, int(round(min(marker_bbox["w"], marker_bbox["h"]) * 0.35)))))
            entry["mask_boxes"] = [box for box in existing_mask_boxes if isinstance(box, dict) and box]
            markers_rendered += 1

    for entry in entries:
        if id(entry) in grouped_entry_ids:
            continue
        if str(entry.get("style_group_kind", "") or "") == "list_block":
            continue
        if not _has_marker_anchor(entry):
            continue
        if not entry.get("layout"):
            continue
        text_font_size = int(entry.get("layout", {}).get("font_size", 8) or 8)
        marker_bbox = _normalized_marker_bbox(entry)
        marker_bbox = inflate_bbox(marker_bbox, image_shape, 0)
        entry["render_marker_text"] = str(entry.get("list_marker_text", "") or "").strip() or "\u2022"
        entry["render_marker_bbox"] = marker_bbox
        entry["render_marker_font_size"] = text_font_size
        existing_mask_boxes = list(entry.get("mask_boxes", [entry.get("mask_bbox")]))
        existing_mask_boxes.append(inflate_bbox(marker_bbox, image_shape, max(2, int(round(min(marker_bbox["w"], marker_bbox["h"]) * 0.35)))))
        entry["mask_boxes"] = [box for box in existing_mask_boxes if isinstance(box, dict) and box]
        markers_rendered += 1

    return groups_with_markers, markers_rendered


def _entry_layout_from_style(
    entry: dict,
    *,
    image_shape: tuple[int, ...],
    blocked_boxes: list[dict[str, int]],
    layout_max_attempts: int,
    layout_max_ms: int,
    max_expand_px: int,
) -> tuple[dict | None, str]:
    style = dict(entry.get("resolved_style", {}))
    font_path_raw = str(style.get("font_path", "") or entry.get("font_path", "")).strip()
    if not font_path_raw:
        return None, "missing_font_path"
    font_path = Path(font_path_raw)
    start_bbox = _entry_layout_start_bbox(entry, style, image_shape)
    debug_info: dict[str, object] = {}
    # Important: resolved_style may carry 0 for max_expand_*_px when unset in config.
    # In that case we must fall back to the global max_expand_px instead of disabling growth.
    style_expand_right_px = _int_value(style.get("max_expand_right_px"), -1)
    style_expand_down_px = _int_value(style.get("max_expand_down_px"), -1)
    effective_expand_right_px = int(max_expand_px) if style_expand_right_px <= 0 else style_expand_right_px
    effective_expand_down_px = int(max_expand_px) if style_expand_down_px <= 0 else style_expand_down_px
    result = resolve_text_layout_with_overflow(
        text=str(entry.get("target_text", "") or ""),
        start_bbox=start_bbox,
        image_shape=image_shape,
        font_path=font_path,
        min_font_size=int(style.get("min_font_size", 8) or 8),
        max_font_size=int(style.get("font_size", 8) or 8),
        line_spacing_ratio=_float_value(style.get("line_spacing_ratio"), 0.22),
        min_line_spacing_ratio=_float_value(
            style.get("min_line_spacing_ratio"),
            max(0.06, _float_value(style.get("line_spacing_ratio"), 0.22) * 0.7),
        ),
        pad_top_ratio=_float_value(style.get("box_padding_top_ratio"), _float_value(style.get("box_padding_y_ratio"), 0.08)),
        pad_right_ratio=_float_value(style.get("box_padding_right_ratio"), _float_value(style.get("box_padding_x_ratio"), 0.04)),
        pad_bottom_ratio=_float_value(style.get("box_padding_bottom_ratio"), _float_value(style.get("box_padding_y_ratio"), 0.08)),
        pad_left_ratio=_float_value(style.get("box_padding_left_ratio"), _float_value(style.get("box_padding_x_ratio"), 0.04)),
        min_pad_top_ratio=_float_value(
            style.get("min_box_padding_top_ratio"),
            _float_value(style.get("box_padding_top_ratio"), _float_value(style.get("box_padding_y_ratio"), 0.08)) * 0.6,
        ),
        min_pad_right_ratio=_float_value(
            style.get("min_box_padding_right_ratio"),
            _float_value(style.get("box_padding_right_ratio"), _float_value(style.get("box_padding_x_ratio"), 0.04)) * 0.6,
        ),
        min_pad_bottom_ratio=_float_value(
            style.get("min_box_padding_bottom_ratio"),
            _float_value(style.get("box_padding_bottom_ratio"), _float_value(style.get("box_padding_y_ratio"), 0.08)) * 0.6,
        ),
        min_pad_left_ratio=_float_value(
            style.get("min_box_padding_left_ratio"),
            _float_value(style.get("box_padding_left_ratio"), _float_value(style.get("box_padding_x_ratio"), 0.04)) * 0.6,
        ),
        max_expand_right_ratio=_float_value(
            style.get("max_expand_right_ratio"),
            _float_value(style.get("max_expand_x_ratio"), 0.45),
        ),
        max_expand_down_ratio=_float_value(
            style.get("max_expand_down_ratio"),
            _float_value(style.get("max_expand_y_ratio"), 0.35),
        ),
        max_expand_left_ratio=0.0,
        max_expand_up_ratio=0.0,
        max_expand_right_px=max(0, int(effective_expand_right_px)),
        max_expand_down_px=max(0, int(effective_expand_down_px)),
        max_expand_left_px=max(0, _int_value(style.get("max_expand_left_px"), 0)),
        max_expand_up_px=max(0, _int_value(style.get("max_expand_up_px"), 0)),
        expand_step_px=max(4, _int_value(style.get("expand_step_px"), 12)),
        blocked_boxes=blocked_boxes,
        allow_hyphenation=_bool_value(style.get("allow_hyphenation"), True),
        hyphenation_min_word_length=max(4, _int_value(style.get("hyphenation_min_word_length"), 8)),
        collision_margin=max(0, _int_value(style.get("collision_margin_px"), 2)),
        fixed_font_size=str(style.get("font_size_mode", "fixed") or "fixed").strip().lower() == "fixed",
        max_layout_attempts=max(0, int(layout_max_attempts)),
        max_layout_ms=max(0, int(layout_max_ms)),
        debug_info=debug_info,
    )
    return result, str(debug_info.get("reason", "target_text_overflow") or "target_text_overflow")


def main() -> int:
    args = parse_args()
    layout_max_attempts = max(0, int(args.layout_max_attempts))
    layout_max_ms = max(0, int(args.layout_max_ms))
    max_expand_px = max(0, int(args.max_expand_px))
    input_dir = Path(args.input_dir).resolve()
    slide_map_json = Path(args.slide_map_json).resolve()
    glossary_json = Path(args.glossary_json).resolve()
    output_dir = Path(args.output_dir).resolve()
    manifest_json = Path(args.manifest_json).resolve()
    manifest_csv = Path(args.manifest_csv).resolve()
    needs_review_json = Path(args.needs_review_json).resolve()
    font_path = Path(args.font_path).resolve()
    style_config_path = _resolve_path(args.style_config_json)
    style_manifest_json = Path(args.style_manifest_json).resolve() if args.style_manifest_json else None
    debug_dir = Path(args.debug_dir).resolve() if args.debug_dir else None

    if not input_dir.exists():
        raise FileNotFoundError(input_dir)
    if not slide_map_json.exists():
        raise FileNotFoundError(slide_map_json)
    if not glossary_json.exists():
        raise FileNotFoundError(glossary_json)
    if not font_path.exists():
        raise FileNotFoundError(font_path)
    if not style_config_path.exists():
        raise FileNotFoundError(style_config_path)

    slide_events = load_slide_events(slide_map_json)
    events_by_id = event_metadata_by_id(slide_events)
    glossary_lookup, glossary_payload = load_glossary(glossary_json)
    if str(glossary_payload.get("normalization_version", "") or "") not in {"", NORMALIZATION_VERSION}:
        raise RuntimeError("Glossary normalization version does not match the renderer normalization version.")

    style_config = load_style_config(style_config_path, fallback_font_path=font_path)
    vision_client, vision, vision_project_id_used, _default_project = ensure_cloud_vision_client(args.vision_project_id)
    slide_paths = sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png")
    print(
        (
            f"[SlideTranslate] layout_budget attempts={layout_max_attempts} "
            f"max_ms={layout_max_ms} global_max_font_size={max(8, int(args.global_max_font_size))} "
            f"max_expand_px={max_expand_px}"
        ),
        flush=True,
    )

    clear_pngs(output_dir)
    if debug_dir is not None:
        clear_pngs(debug_dir / "overlay")
        clear_pngs(debug_dir / "masks")

    slide_jobs: list[dict] = []
    style_metric_entries: list[dict] = []

    for fallback_index, slide_path in enumerate(slide_paths, start=1):
        print(f"@@STEP DETAIL translate apply-glossary:{slide_path.name}")
        event_id = parse_event_id_from_name(slide_path.name) or 0
        event_meta = events_by_id.get(event_id, {})
        slide_index = int(event_meta.get("slide_index", fallback_index) or fallback_index)
        original = cv2.imread(str(slide_path), cv2.IMREAD_COLOR)
        if original is None or original.size == 0:
            raise RuntimeError(f"Failed to read slide image: {slide_path}")

        ocr_doc = ocr_slide_fragments(
            vision_client,
            vision,
            image_path=slide_path,
            event_id=event_id,
            slide_index=slide_index,
            feature=args.vision_feature,
        )
        classifications = classify_text_units(
            ocr_doc.get("text_units", []),
            image_width=int(ocr_doc.get("image_width", original.shape[1]) or original.shape[1]),
            image_height=int(ocr_doc.get("image_height", original.shape[0]) or original.shape[0]),
        )
        classification_by_unit_id = {int(item.get("unit_id", 0) or 0): item for item in classifications}
        classified_units = []
        for unit in ocr_doc.get("text_units", []):
            unit_id = int(unit.get("unit_id", 0) or 0)
            classification = classification_by_unit_id.get(
                unit_id,
                {
                    "role": "body",
                    "slot_id": "body.middle_left",
                    "slot_vertical_zone": "middle",
                    "slot_horizontal_zone": "left",
                    "classification_reason": "fallback_body",
                },
            )
            classified_units.append(
                {
                    "unit_id": unit_id,
                    "source_text": str(unit.get("source_text", "") or ""),
                    "bbox": dict(unit.get("bbox", {})),
                    "role": str(classification.get("role", "body") or "body"),
                    "slot_id": str(classification.get("slot_id", "body.middle_left") or "body.middle_left"),
                    "classification_reason": str(
                        classification.get("classification_reason", "fallback_body") or "fallback_body"
                    ),
                }
            )

        entries: list[dict] = []
        unresolved_entries: list[dict] = []
        identical_fragments = 0
        skipped_graphic_units = 0
        skipped_noise_units = 0
        skipped_fragments = sum(
            1
            for fragment in ocr_doc.get("fragments", [])
            if not is_translatable_text(str(fragment.get("text_norm", "") or fragment.get("text_raw", "") or "").strip())
        )

        for unit in ocr_doc.get("text_units", []):
            unit_id = int(unit.get("unit_id", 0) or 0)
            classification = classification_by_unit_id.get(
                unit_id,
                {
                    "role": "body",
                    "slot_id": "body.middle_left",
                    "slot_vertical_zone": "middle",
                    "slot_horizontal_zone": "left",
                    "classification_reason": "fallback_body",
                },
            )
            if str(classification.get("role", "body") or "body") == "graphic_embedded":
                skipped_graphic_units += 1
                continue
            if _is_noise_like_ocr_unit(unit, classification):
                skipped_noise_units += 1
                continue
            text_norm = str(unit.get("source_text_norm", "") or "").strip()
            source_text = str(unit.get("source_text", "") or "").strip()
            if not text_norm or not is_translatable_text(text_norm):
                continue

            glossary_row = glossary_lookup.get(text_norm)
            if not glossary_row:
                unresolved_entries.append(
                    {
                        "unit_id": unit_id,
                        "fragment_ids": unit.get("fragment_ids", []),
                        "reason": "missing_glossary_match",
                        "text_raw": source_text,
                        "text_norm": text_norm,
                        "bbox": unit.get("bbox", {}),
                    }
                )
                continue

            target_text = str(glossary_row.get("target_text", "") or "").strip()
            if not target_text:
                unresolved_entries.append(
                    {
                        "unit_id": unit_id,
                        "fragment_ids": unit.get("fragment_ids", []),
                        "reason": "empty_target_text",
                        "text_raw": source_text,
                        "text_norm": text_norm,
                        "bbox": unit.get("bbox", {}),
                    }
                )
                continue

            if normalize_slide_text(target_text) == text_norm:
                identical_fragments += 1
                continue

            bbox = dict(unit.get("bbox", {}))
            background_bgr = estimate_background_color(original, bbox)
            text_bgr = estimate_text_color(original, bbox, background_bgr)
            entry = {
                "slide_index": slide_index,
                "event_id": event_id,
                "image_name": slide_path.name,
                "unit_id": unit_id,
                "fragment_ids": unit.get("fragment_ids", []),
                "block_id": unit.get("block_ids", []),
                "line_id": unit.get("line_ids", []),
                "line_count": int(unit.get("line_count", 1) or 1),
                "list_marker_fragment_id": int(unit.get("list_marker_fragment_id", 0) or 0),
                "list_marker_text": str(unit.get("list_marker_text", "") or ""),
                "list_marker_bbox": dict(unit.get("list_marker_bbox", {})),
                "list_marker_inferred": _bool_value(unit.get("list_marker_inferred"), False),
                "source_text": source_text,
                "source_text_norm": text_norm,
                "target_text": target_text,
                "bbox": bbox,
                "mask_bbox": inflate_bbox(bbox, original.shape, max(2, int(round(min(bbox.get("w", 0), bbox.get("h", 0)) * 0.08)))),
                "mask_boxes": [inflate_bbox(bbox, original.shape, max(2, int(round(min(bbox.get("w", 0), bbox.get("h", 0)) * 0.08))))],
                "background_color_bgr": background_bgr,
                "source_text_color_rgb": tuple(reversed(text_bgr)),
                "text_color_rgb": tuple(reversed(text_bgr)),
                "role": str(classification.get("role", "body") or "body"),
                "slot_id": str(classification.get("slot_id", "body.middle_left") or "body.middle_left"),
                "slot_vertical_zone": str(classification.get("slot_vertical_zone", "middle") or "middle"),
                "slot_horizontal_zone": str(classification.get("slot_horizontal_zone", "left") or "left"),
                "classification_reason": str(classification.get("classification_reason", "fallback_body") or "fallback_body"),
            }
            entries.append(entry)
            style_metric_entries.append(entry)

        slide_jobs.append(
            {
                "slide_path": slide_path,
                "slide_index": slide_index,
                "event_id": event_id,
                "ocr_doc": ocr_doc,
                "entries": entries,
                "classified_units": classified_units,
                "unresolved_entries": unresolved_entries,
                "identical_fragments": identical_fragments,
                "skipped_fragments": skipped_fragments,
                "skipped_graphic_units": skipped_graphic_units,
                "skipped_noise_units": skipped_noise_units,
            }
        )

    style_metrics = _build_style_metrics(style_metric_entries, style_config, style_config_path, font_path)

    manifest_rows: list[dict] = []
    needs_review_rows: list[dict] = []
    style_manifest_rows: list[dict] = []

    for job in slide_jobs:
        slide_path = job["slide_path"]
        original = cv2.imread(str(slide_path), cv2.IMREAD_COLOR)
        if original is None or original.size == 0:
            raise RuntimeError(f"Failed to read slide image: {slide_path}")

        unresolved_entries = list(job["unresolved_entries"])
        candidate_entries: list[dict] = []
        for entry in job["entries"]:
            resolved_style = _resolve_entry_style(
                entry,
                style_config,
                style_config_path,
                style_metrics,
                font_path,
                int(args.global_max_font_size),
            )
            candidate = dict(entry)
            candidate["resolved_style"] = resolved_style
            candidate["font_path"] = str(resolved_style["font_path"])
            candidate["text_color_rgb"] = tuple(int(v) for v in resolved_style["text_color_rgb"])
            candidate_entries.append(candidate)
            style_manifest_rows.append(
                {
                    "slide_index": candidate["slide_index"],
                    "event_id": candidate["event_id"],
                    "image_name": candidate["image_name"],
                    "unit_id": candidate["unit_id"],
                    "source_text": candidate["source_text"],
                    "target_text": candidate["target_text"],
                    "role": candidate["role"],
                    "slot_id": candidate["slot_id"],
                    "classification_reason": candidate["classification_reason"],
                    "font_path": candidate["font_path"],
                    "font_size": int(resolved_style["font_size"]),
                    "min_font_size": int(resolved_style["min_font_size"]),
                    "font_size_mode": resolved_style["font_size_mode"],
                    "text_color_mode": resolved_style["text_color_mode"],
                    "text_color_rgb": list(resolved_style["text_color_rgb"]),
                    "source_text_color_rgb": list(candidate["source_text_color_rgb"]),
                    "bbox": dict(candidate["bbox"]),
                    "line_count": int(candidate["line_count"]),
                    "list_marker": bool(candidate["list_marker_fragment_id"]) or _bool_value(candidate.get("list_marker_inferred"), False),
                }
            )

        list_block_groups_applied, list_block_grouped_fragments, list_group_boxes = apply_list_block_layout(
            candidate_entries,
            original.shape,
            layout_max_attempts=layout_max_attempts,
            layout_max_ms=layout_max_ms,
            max_expand_px=max_expand_px,
        )

        unit_boxes = [
            {
                "unit_id": int(candidate.get("unit_id", 0) or 0),
                "bbox": dict(candidate.get("bbox", {})),
            }
            for candidate in candidate_entries
            if isinstance(candidate.get("bbox", {}), dict) and candidate.get("bbox", {})
        ]
        occupied_boxes: list[dict[str, int]] = [dict(box) for box in list_group_boxes if isinstance(box, dict) and box]
        renderable_entries: list[dict] = []
        ordered_entries = sorted(
            candidate_entries,
            key=lambda entry: (
                int(entry.get("unit_id", 0) or 0),
                _bbox_xywh(entry.get("bbox", {}))[1],
                _bbox_xywh(entry.get("bbox", {}))[0],
            ),
        )
        total_units = len(ordered_entries)
        for entry_index, entry in enumerate(ordered_entries, start=1):
            if entry.get("layout"):
                print(
                    (
                        f"[SlideTranslate] slide={job['slide_index']} unit={entry.get('unit_id')} "
                        f"role={entry.get('role')} status=layout_precomputed"
                    ),
                    flush=True,
                )
                renderable_entries.append(entry)
                continue
            entry_unit_id = int(entry.get("unit_id", 0) or 0)
            print(
                (
                    f"[SlideTranslate] slide={job['slide_index']} unit={entry_index}/{total_units} "
                    f"id={entry_unit_id} role={entry.get('role')} text=\"{_short_text(entry.get('target_text', ''))}\" "
                    f"layout=start"
                ),
                flush=True,
            )
            blocked_boxes = [
                dict(item.get("bbox", {}))
                for item in unit_boxes
                if int(item.get("unit_id", 0) or 0) != entry_unit_id
            ]
            blocked_boxes.extend(dict(box) for box in occupied_boxes if isinstance(box, dict) and box)
            layout_result, layout_error_reason = _entry_layout_from_style(
                entry,
                image_shape=original.shape,
                blocked_boxes=blocked_boxes,
                layout_max_attempts=layout_max_attempts,
                layout_max_ms=layout_max_ms,
                max_expand_px=max_expand_px,
            )
            if layout_result is None:
                print(
                    (
                        f"[SlideTranslate] slide={job['slide_index']} id={entry_unit_id} "
                        f"layout=failed reason={layout_error_reason}"
                    ),
                    flush=True,
                )
                unresolved_entries.append(
                    {
                        "unit_id": entry.get("unit_id", ""),
                        "fragment_ids": entry.get("fragment_ids", []),
                        "reason": layout_error_reason or "target_text_overflow",
                        "text_raw": entry.get("source_text", ""),
                        "text_norm": entry.get("source_text_norm", ""),
                        "target_text": entry.get("target_text", ""),
                        "bbox": entry.get("bbox", {}),
                        "role": entry.get("role", ""),
                        "slot_id": entry.get("slot_id", ""),
                    }
                )
                continue
            layout = dict(layout_result.get("layout", {}))
            layout_bbox = dict(layout_result.get("bbox", entry.get("bbox", {})))
            entry["layout"] = layout
            entry["layout_bbox"] = layout_bbox
            fixed_font_anchor_top_left = (
                str(entry.get("resolved_style", {}).get("font_size_mode", "fixed") or "fixed").strip().lower()
                == "fixed"
            )
            if fixed_font_anchor_top_left:
                entry["render_x"] = int(layout_bbox.get("x", 0) or 0)
                entry["render_y"] = int(layout_bbox.get("y", 0) or 0)
            else:
                entry["render_x"] = int(layout_bbox.get("x", 0) or 0) + int(layout.get("offset_x", 0) or 0)
                entry["render_y"] = int(layout_bbox.get("y", 0) or 0) + int(layout.get("offset_y", 0) or 0)
            entry["layout_strategy"] = str(layout_result.get("strategy", "fit") or "fit")
            entry["layout_line_spacing_ratio"] = float(layout_result.get("line_spacing_ratio", entry.get("resolved_style", {}).get("line_spacing_ratio", 0.22)))
            entry["layout_hyphenation"] = bool(layout_result.get("hyphenation", False))
            entry["applied_font_size"] = int(layout.get("font_size", 8) or 8)
            entry["layout_attempts"] = int(layout_result.get("attempts", 0) or 0)
            entry["layout_elapsed_ms"] = int(layout_result.get("elapsed_ms", 0) or 0)
            print(
                (
                    f"[SlideTranslate] slide={job['slide_index']} id={entry_unit_id} "
                    f"layout=ok strategy={entry['layout_strategy']} font={entry['applied_font_size']} "
                    f"attempts={entry['layout_attempts']} elapsed_ms={entry['layout_elapsed_ms']}"
                ),
                flush=True,
            )
            occupied_boxes.append(layout_bbox)
            renderable_entries.append(entry)

        style_groups_applied, style_grouped_fragments = align_stacked_style_groups(renderable_entries)
        list_marker_groups_applied, list_markers_rendered = assign_list_marker_rendering(renderable_entries, original.shape)
        layout_strategy_by_unit = {
            int(entry.get("unit_id", 0) or 0): str(entry.get("layout_strategy", "fit") or "fit")
            for entry in renderable_entries
            if int(entry.get("unit_id", 0) or 0) > 0
        }
        layout_bbox_by_unit = {
            int(entry.get("unit_id", 0) or 0): dict(_effective_entry_bbox(entry))
            for entry in renderable_entries
            if int(entry.get("unit_id", 0) or 0) > 0
        }

        needs_review = bool(unresolved_entries)
        output_status = "unchanged"
        output_path = output_dir / slide_path.name
        if needs_review and args.needs_review_policy == "mark_only":
            shutil.copy2(slide_path, output_path)
            output_status = "needs_review_unmodified"
            if debug_dir is not None:
                if renderable_entries:
                    debug_rendered_bgr, debug_mask = render_text_entries(
                        original_bgr=original,
                        entries=renderable_entries,
                        font_path=font_path,
                    )
                    cv2.imwrite(str(debug_dir / "masks" / slide_path.name), debug_mask)
                    cv2.imwrite(
                        str(debug_dir / "overlay" / slide_path.name),
                        overlay_debug_image(
                            debug_rendered_bgr,
                            list(job.get("classified_units", [])),
                            unresolved_entries,
                            layout_strategy_by_unit,
                            layout_bbox_by_unit,
                        ),
                    )
                else:
                    empty_mask = np.zeros(original.shape[:2], dtype="uint8")
                    cv2.imwrite(str(debug_dir / "masks" / slide_path.name), empty_mask)
                    cv2.imwrite(
                        str(debug_dir / "overlay" / slide_path.name),
                        overlay_debug_image(
                            original,
                            list(job.get("classified_units", [])),
                            unresolved_entries,
                            layout_strategy_by_unit,
                            layout_bbox_by_unit,
                        ),
                    )
        elif renderable_entries:
            rendered_bgr, mask = render_text_entries(original_bgr=original, entries=renderable_entries, font_path=font_path)
            if not cv2.imwrite(str(output_path), rendered_bgr):
                raise RuntimeError(f"Failed to write translated slide: {output_path}")
            output_status = "needs_review_partial" if needs_review else "translated"
            if debug_dir is not None:
                cv2.imwrite(str(debug_dir / "masks" / slide_path.name), mask)
                cv2.imwrite(
                    str(debug_dir / "overlay" / slide_path.name),
                    overlay_debug_image(
                        rendered_bgr,
                        list(job.get("classified_units", [])),
                        unresolved_entries,
                        layout_strategy_by_unit,
                        layout_bbox_by_unit,
                    ),
                )
        else:
            shutil.copy2(slide_path, output_path)
            output_status = "needs_review_unmodified" if needs_review else "unchanged"
            if debug_dir is not None:
                empty_mask = np.zeros(original.shape[:2], dtype="uint8")
                cv2.imwrite(str(debug_dir / "masks" / slide_path.name), empty_mask)
                cv2.imwrite(
                    str(debug_dir / "overlay" / slide_path.name),
                    overlay_debug_image(
                        original,
                        list(job.get("classified_units", [])),
                        unresolved_entries,
                        layout_strategy_by_unit,
                        layout_bbox_by_unit,
                    ),
                )

        if needs_review:
            needs_review_rows.append(
                {
                    "slide_index": job["slide_index"],
                    "event_id": job["event_id"],
                    "image_name": slide_path.name,
                    "status": output_status,
                    "unresolved": unresolved_entries,
                }
            )

        manifest_rows.append(
            {
                "slide_index": job["slide_index"],
                "event_id": job["event_id"],
                "image_name": slide_path.name,
                "status": output_status,
                "rendered_fragments": len(renderable_entries),
                "unresolved_fragments": len(unresolved_entries),
                "identical_fragments": job["identical_fragments"],
                "skipped_fragments": job["skipped_fragments"],
                "skipped_graphic_units": int(job.get("skipped_graphic_units", 0) or 0),
                "skipped_noise_units": int(job.get("skipped_noise_units", 0) or 0),
                "list_block_groups_applied": list_block_groups_applied,
                "list_block_grouped_fragments": list_block_grouped_fragments,
                "style_groups_applied": style_groups_applied,
                "style_grouped_fragments": style_grouped_fragments,
                "list_marker_groups_applied": list_marker_groups_applied,
                "list_markers_rendered": list_markers_rendered,
                "needs_review": 1 if needs_review else 0,
                "needs_review_policy": args.needs_review_policy,
                "font_path": str(font_path),
                "style_config_path": str(style_config_path),
            }
        )

    write_json(
        manifest_json,
        {
            "vision_project_id_used": vision_project_id_used,
            "target_language": glossary_payload.get("target_language", ""),
            "slides_processed": len(manifest_rows),
            "style_config_path": str(style_config_path),
            "items": manifest_rows,
        },
    )
    write_csv(
        manifest_csv,
        [
            "slide_index",
            "event_id",
            "image_name",
            "status",
            "rendered_fragments",
            "unresolved_fragments",
            "identical_fragments",
            "skipped_fragments",
            "skipped_graphic_units",
            "skipped_noise_units",
            "list_block_groups_applied",
            "list_block_grouped_fragments",
            "style_groups_applied",
            "style_grouped_fragments",
            "list_marker_groups_applied",
            "list_markers_rendered",
            "needs_review",
            "needs_review_policy",
            "font_path",
            "style_config_path",
        ],
        manifest_rows,
    )
    write_json(
        needs_review_json,
        {
            "count": len(needs_review_rows),
            "items": needs_review_rows,
        },
    )
    if style_manifest_json is not None:
        write_json(
            style_manifest_json,
            {
                "style_config_path": str(style_config_path),
                "items": style_manifest_rows,
            },
        )

    print(f"[SlideTranslate] Slides processed: {len(manifest_rows)}")
    print(f"[SlideTranslate] Slides needing review: {len(needs_review_rows)}")
    print(f"[SlideTranslate] Output dir: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
