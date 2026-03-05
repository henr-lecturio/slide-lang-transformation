from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

MEASURE_IMAGE = Image.new("RGB", (8, 8), (255, 255, 255))
MEASURE_DRAW = ImageDraw.Draw(MEASURE_IMAGE)


def _clamp_bbox(bbox: dict[str, int], image_shape: tuple[int, ...]) -> tuple[int, int, int, int]:
    height, width = image_shape[:2]
    x = max(0, min(int(bbox.get("x", 0) or 0), max(0, width - 1)))
    y = max(0, min(int(bbox.get("y", 0) or 0), max(0, height - 1)))
    w = max(1, int(bbox.get("w", 0) or 0))
    h = max(1, int(bbox.get("h", 0) or 0))
    x1 = max(x + 1, min(width, x + w))
    y1 = max(y + 1, min(height, y + h))
    return x, y, x1 - x, y1 - y


def inflate_bbox(bbox: dict[str, int], image_shape: tuple[int, ...], pad: int) -> dict[str, int]:
    x, y, w, h = _clamp_bbox(bbox, image_shape)
    height, width = image_shape[:2]
    x0 = max(0, x - int(pad))
    y0 = max(0, y - int(pad))
    x1 = min(width, x + w + int(pad))
    y1 = min(height, y + h + int(pad))
    return {"x": x0, "y": y0, "w": max(1, x1 - x0), "h": max(1, y1 - y0)}


def _luminance(color_bgr: tuple[int, int, int]) -> float:
    b, g, r = color_bgr
    return 0.114 * float(b) + 0.587 * float(g) + 0.299 * float(r)


def estimate_background_color(image_bgr: np.ndarray, bbox: dict[str, int]) -> tuple[int, int, int]:
    x, y, w, h = _clamp_bbox(bbox, image_bgr.shape)
    pad = max(2, int(round(min(w, h) * 0.08)))
    expanded = inflate_bbox({"x": x, "y": y, "w": w, "h": h}, image_bgr.shape, pad)
    ex, ey, ew, eh = _clamp_bbox(expanded, image_bgr.shape)
    region = image_bgr[ey : ey + eh, ex : ex + ew]
    if region.size == 0:
        return (255, 255, 255)

    inner_x0 = max(0, x - ex)
    inner_y0 = max(0, y - ey)
    inner_x1 = min(ew, inner_x0 + w)
    inner_y1 = min(eh, inner_y0 + h)
    ring_mask = np.ones((eh, ew), dtype=bool)
    ring_mask[inner_y0:inner_y1, inner_x0:inner_x1] = False
    ring_pixels = region[ring_mask]
    if ring_pixels.size == 0:
        ring_pixels = region.reshape(-1, 3)
    median = np.median(ring_pixels, axis=0)
    return tuple(int(round(v)) for v in median.tolist())


def estimate_text_color(
    image_bgr: np.ndarray,
    bbox: dict[str, int],
    background_color: tuple[int, int, int],
) -> tuple[int, int, int]:
    x, y, w, h = _clamp_bbox(bbox, image_bgr.shape)
    crop = image_bgr[y : y + h, x : x + w]
    if crop.size == 0:
        return (0, 0, 0)

    pixels = crop.reshape(-1, 3).astype(np.float32)
    bg = np.array(background_color, dtype=np.float32)
    distances = np.linalg.norm(pixels - bg[None, :], axis=1)
    threshold = max(18.0, float(np.percentile(distances, 75)))
    candidate_pixels = pixels[distances >= threshold]
    if candidate_pixels.shape[0] < 12:
        return (20, 20, 20) if _luminance(background_color) > 140 else (245, 245, 245)

    color = np.median(candidate_pixels, axis=0)
    out = tuple(int(round(v)) for v in color.tolist())
    if np.linalg.norm(np.array(out, dtype=np.float32) - bg) < 12.0:
        return (20, 20, 20) if _luminance(background_color) > 140 else (245, 245, 245)
    return out


def _measure_text(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    left, top, right, bottom = MEASURE_DRAW.textbbox((0, 0), text or " ", font=font)
    return max(0, int(right - left)), max(0, int(bottom - top))


def _font_line_height(font: ImageFont.FreeTypeFont) -> int:
    try:
        ascent, descent = font.getmetrics()
        return max(1, int(ascent + descent))
    except Exception:  # noqa: BLE001
        return max(1, _measure_text("Ag", font)[1])


def _resolve_spacing(font_size: int, line_spacing_ratio: float | None = None) -> int:
    ratio = float(line_spacing_ratio) if line_spacing_ratio is not None else 0.22
    return max(2, int(round(max(1, int(font_size)) * ratio)))


def _split_word_for_width(
    word: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    *,
    allow_hyphenation: bool,
    hyphenation_min_word_length: int,
) -> list[str]:
    token = str(word or "")
    if not token:
        return [""]
    if _measure_text(token, font)[0] <= max_width:
        return [token]
    if not allow_hyphenation:
        return [token]

    parts: list[str] = []
    remaining = token
    min_word_length = max(4, int(hyphenation_min_word_length))

    while remaining:
        if _measure_text(remaining, font)[0] <= max_width:
            parts.append(remaining)
            break

        split_index = 0
        if len(remaining) >= min_word_length:
            start_index = max(2, min_word_length - 1)
            for index in range(start_index, len(remaining)):
                candidate = f"{remaining[:index]}-"
                if _measure_text(candidate, font)[0] <= max_width:
                    split_index = index
                else:
                    break
        if split_index <= 0:
            return [token]
        parts.append(f"{remaining[:split_index]}-")
        remaining = remaining[split_index:]

    return parts


def _wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    *,
    allow_hyphenation: bool = False,
    hyphenation_min_word_length: int = 8,
) -> list[str]:
    paragraphs = str(text or "").splitlines() or [str(text or "")]
    lines: list[str] = []
    for paragraph in paragraphs:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = ""
        for word in words:
            word_parts = _split_word_for_width(
                word,
                font,
                max_width,
                allow_hyphenation=allow_hyphenation,
                hyphenation_min_word_length=hyphenation_min_word_length,
            )
            if not word_parts:
                word_parts = [word]
            for part in word_parts:
                if current.endswith("-"):
                    lines.append(current)
                    current = part
                    continue
                candidate = f"{current} {part}".strip()
                width, _ = _measure_text(candidate, font)
                if current and width > max_width:
                    lines.append(current)
                    current = part
                else:
                    current = candidate
        if current or not lines:
            lines.append(current)
    return lines or [""]


def _measure_multiline(lines: list[str], font: ImageFont.FreeTypeFont, spacing: int) -> tuple[int, int]:
    widths = [_measure_text(line or " ", font)[0] for line in lines] or [0]
    width = max(widths) if widths else 0
    line_height = _font_line_height(font)
    height = line_height * max(1, len(lines))
    if len(lines) > 1:
        height += spacing * (len(lines) - 1)
    return int(width), int(height)


def layout_text_block(
    *,
    text: str,
    font_path: Path,
    font_size: int,
    max_width: int,
    line_spacing_ratio: float | None = None,
    allow_hyphenation: bool = False,
    hyphenation_min_word_length: int = 8,
) -> dict | None:
    font = ImageFont.truetype(str(font_path), size=max(1, int(font_size)))
    spacing = _resolve_spacing(int(font_size), line_spacing_ratio)
    lines = _wrap_text(
        text,
        font,
        max(1, int(max_width)),
        allow_hyphenation=allow_hyphenation,
        hyphenation_min_word_length=hyphenation_min_word_length,
    )
    text_w, text_h = _measure_multiline(lines, font, spacing)
    if text_w > max(1, int(max_width)):
        return None
    return {
        "font_size": int(font_size),
        "spacing": spacing,
        "lines": lines,
        "text_width": text_w,
        "text_height": text_h,
        "offset_x": 0,
        "offset_y": 0,
        "line_height": _font_line_height(font),
    }


def layout_hanging_text_block(
    *,
    text: str,
    font_path: Path,
    font_size: int,
    max_width: int,
    prefix_text: str = "\u2022",
    prefix_gap: int | None = None,
    line_spacing_ratio: float | None = None,
    allow_hyphenation: bool = False,
    hyphenation_min_word_length: int = 8,
) -> dict | None:
    font = ImageFont.truetype(str(font_path), size=max(1, int(font_size)))
    spacing = _resolve_spacing(int(font_size), line_spacing_ratio)
    prefix_label = str(prefix_text or "").strip() or "\u2022"
    prefix_w, _prefix_h = _measure_text(prefix_label, font)
    gap = max(4, int(prefix_gap) if prefix_gap is not None else int(round(font_size * 0.45)))
    hanging_indent = prefix_w + gap
    available_text_w = max(1, int(max_width) - hanging_indent)
    lines = _wrap_text(
        text,
        font,
        available_text_w,
        allow_hyphenation=allow_hyphenation,
        hyphenation_min_word_length=hyphenation_min_word_length,
    )
    text_w, text_h = _measure_multiline(lines, font, spacing)
    if text_w > available_text_w:
        return None
    return {
        "font_size": int(font_size),
        "spacing": spacing,
        "lines": lines,
        "text_width": text_w,
        "text_height": text_h,
        "offset_x": 0,
        "offset_y": 0,
        "line_height": _font_line_height(font),
        "inline_prefix_text": prefix_label,
        "inline_prefix_gap": gap,
        "inline_prefix_width": hanging_indent,
    }


def layout_text_for_font_size(
    *,
    text: str,
    bbox: dict[str, int],
    font_path: Path,
    font_size: int,
    line_spacing_ratio: float | None = None,
    pad_x_ratio: float | None = None,
    pad_y_ratio: float | None = None,
    pad_top_ratio: float | None = None,
    pad_right_ratio: float | None = None,
    pad_bottom_ratio: float | None = None,
    pad_left_ratio: float | None = None,
    allow_hyphenation: bool = False,
    hyphenation_min_word_length: int = 8,
) -> dict | None:
    box_w = max(1, int(bbox.get("w", 0) or 0))
    box_h = max(1, int(bbox.get("h", 0) or 0))
    resolved_pad_left = float(pad_left_ratio) if pad_left_ratio is not None else (
        float(pad_x_ratio) if pad_x_ratio is not None else 0.04
    )
    resolved_pad_right = float(pad_right_ratio) if pad_right_ratio is not None else (
        float(pad_x_ratio) if pad_x_ratio is not None else 0.04
    )
    resolved_pad_top = float(pad_top_ratio) if pad_top_ratio is not None else (
        float(pad_y_ratio) if pad_y_ratio is not None else 0.08
    )
    resolved_pad_bottom = float(pad_bottom_ratio) if pad_bottom_ratio is not None else (
        float(pad_y_ratio) if pad_y_ratio is not None else 0.08
    )
    pad_left = max(1, int(round(box_w * resolved_pad_left)))
    pad_right = max(1, int(round(box_w * resolved_pad_right)))
    pad_top = max(1, int(round(box_h * resolved_pad_top)))
    pad_bottom = max(1, int(round(box_h * resolved_pad_bottom)))
    available_w = max(1, box_w - pad_left - pad_right)
    available_h = max(1, box_h - pad_top - pad_bottom)
    font = ImageFont.truetype(str(font_path), size=max(1, int(font_size)))
    spacing = _resolve_spacing(int(font_size), line_spacing_ratio)
    lines = _wrap_text(
        text,
        font,
        available_w,
        allow_hyphenation=allow_hyphenation,
        hyphenation_min_word_length=hyphenation_min_word_length,
    )
    text_w, text_h = _measure_multiline(lines, font, spacing)
    if text_w > available_w or text_h > available_h:
        return None

    offset_x = pad_left
    offset_y = pad_top
    return {
        "font_size": int(font_size),
        "spacing": spacing,
        "lines": lines,
        "text_width": text_w,
        "text_height": text_h,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "line_height": _font_line_height(font),
    }


def fit_text_to_box(
    *,
    text: str,
    bbox: dict[str, int],
    font_path: Path,
    min_font_size: int = 8,
    max_font_size: int | None = None,
    line_spacing_ratio: float | None = None,
    pad_x_ratio: float | None = None,
    pad_y_ratio: float | None = None,
    pad_top_ratio: float | None = None,
    pad_right_ratio: float | None = None,
    pad_bottom_ratio: float | None = None,
    pad_left_ratio: float | None = None,
    allow_hyphenation: bool = False,
    hyphenation_min_word_length: int = 8,
    fixed_font_size: bool = False,
) -> dict | None:
    box_h = max(1, int(bbox.get("h", 0) or 0))
    resolved_max_font_size = max_font_size
    if resolved_max_font_size is None:
        resolved_max_font_size = max(min_font_size, min(box_h, max(18, int(round(box_h * 0.95)))))
    if fixed_font_size:
        font_sizes = [int(resolved_max_font_size)]
    else:
        font_sizes = range(int(resolved_max_font_size), int(min_font_size) - 1, -1)
    for font_size in font_sizes:
        layout = layout_text_for_font_size(
            text=text,
            bbox=bbox,
            font_path=font_path,
            font_size=font_size,
            line_spacing_ratio=line_spacing_ratio,
            pad_x_ratio=pad_x_ratio,
            pad_y_ratio=pad_y_ratio,
            pad_top_ratio=pad_top_ratio,
            pad_right_ratio=pad_right_ratio,
            pad_bottom_ratio=pad_bottom_ratio,
            pad_left_ratio=pad_left_ratio,
            allow_hyphenation=allow_hyphenation,
            hyphenation_min_word_length=hyphenation_min_word_length,
        )
        if layout is not None:
            return layout
    return None


def _unique_ratio_candidates(high: float, low: float) -> list[float]:
    high_value = float(high)
    low_value = max(0.0, min(high_value, float(low)))
    candidates: list[float] = [high_value]
    midpoint = high_value + (low_value - high_value) * 0.5
    if abs(midpoint - high_value) > 1e-6:
        candidates.append(midpoint)
    if abs(low_value - candidates[-1]) > 1e-6:
        candidates.append(low_value)
    return candidates


def _expand_value_candidates(max_expand_px: int, step_px: int) -> list[int]:
    max_expand = max(0, int(max_expand_px))
    if max_expand <= 0:
        return [0]
    step = max(4, int(step_px))
    values = [0]
    value = step
    while value < max_expand:
        values.append(value)
        value += step
    if values[-1] != max_expand:
        values.append(max_expand)
    return values


def _expand_bbox_sides(
    base_bbox: dict[str, int],
    *,
    expand_left: int,
    expand_right: int,
    expand_up: int,
    expand_down: int,
    image_shape: tuple[int, ...],
) -> dict[str, int]:
    base_x, base_y, base_w, base_h = _clamp_bbox(base_bbox, image_shape)
    image_h, image_w = image_shape[:2]
    x0 = max(0, base_x - max(0, int(expand_left)))
    y0 = max(0, base_y - max(0, int(expand_up)))
    x1 = min(image_w, base_x + base_w + max(0, int(expand_right)))
    y1 = min(image_h, base_y + base_h + max(0, int(expand_down)))
    return {
        "x": int(x0),
        "y": int(y0),
        "w": max(1, int(x1 - x0)),
        "h": max(1, int(y1 - y0)),
    }


def _boxes_intersect(a: dict[str, int], b: dict[str, int], *, margin: int = 0) -> bool:
    ax = int(a.get("x", 0) or 0)
    ay = int(a.get("y", 0) or 0)
    aw = max(1, int(a.get("w", 0) or 0))
    ah = max(1, int(a.get("h", 0) or 0))
    bx = int(b.get("x", 0) or 0)
    by = int(b.get("y", 0) or 0)
    bw = max(1, int(b.get("w", 0) or 0))
    bh = max(1, int(b.get("h", 0) or 0))
    pad = max(0, int(margin))
    ax0 = ax - pad
    ay0 = ay - pad
    ax1 = ax + aw + pad
    ay1 = ay + ah + pad
    bx0 = bx - pad
    by0 = by - pad
    bx1 = bx + bw + pad
    by1 = by + bh + pad
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def _collides_with_blocked(
    bbox: dict[str, int],
    blocked_boxes: list[dict[str, int]],
    *,
    collision_margin: int,
) -> bool:
    for blocked in blocked_boxes:
        if not isinstance(blocked, dict):
            continue
        if _boxes_intersect(bbox, blocked, margin=collision_margin):
            return True
    return False


def resolve_text_layout_with_overflow(
    *,
    text: str,
    start_bbox: dict[str, int],
    image_shape: tuple[int, ...],
    font_path: Path,
    min_font_size: int = 8,
    max_font_size: int | None = None,
    line_spacing_ratio: float | None = None,
    min_line_spacing_ratio: float | None = None,
    pad_top_ratio: float | None = None,
    pad_right_ratio: float | None = None,
    pad_bottom_ratio: float | None = None,
    pad_left_ratio: float | None = None,
    min_pad_top_ratio: float | None = None,
    min_pad_right_ratio: float | None = None,
    min_pad_bottom_ratio: float | None = None,
    min_pad_left_ratio: float | None = None,
    max_expand_right_ratio: float = 0.0,
    max_expand_down_ratio: float = 0.0,
    max_expand_left_ratio: float = 0.0,
    max_expand_up_ratio: float = 0.0,
    max_expand_right_px: int | None = None,
    max_expand_down_px: int | None = None,
    max_expand_left_px: int | None = None,
    max_expand_up_px: int | None = None,
    expand_step_px: int = 12,
    blocked_boxes: list[dict[str, int]] | None = None,
    allow_hyphenation: bool = False,
    hyphenation_min_word_length: int = 8,
    collision_margin: int = 2,
    fixed_font_size: bool = False,
    max_layout_attempts: int = 0,
    max_layout_ms: int = 0,
    debug_info: dict | None = None,
) -> dict | None:
    debug_meta = debug_info if isinstance(debug_info, dict) else None
    if debug_meta is not None:
        debug_meta.clear()

    base_x, base_y, base_w, base_h = _clamp_bbox(start_bbox, image_shape)
    base_bbox = {"x": base_x, "y": base_y, "w": base_w, "h": base_h}
    high_line_spacing = float(line_spacing_ratio) if line_spacing_ratio is not None else 0.22
    low_line_spacing = (
        float(min_line_spacing_ratio)
        if min_line_spacing_ratio is not None
        else max(0.06, high_line_spacing * 0.7)
    )
    if fixed_font_size:
        # Fixed-size mode must keep styling deterministic and only search box expansion.
        line_spacing_candidates = [high_line_spacing]
    else:
        line_spacing_candidates = _unique_ratio_candidates(high_line_spacing, low_line_spacing)

    high_top = float(pad_top_ratio) if pad_top_ratio is not None else 0.08
    high_right = float(pad_right_ratio) if pad_right_ratio is not None else 0.04
    high_bottom = float(pad_bottom_ratio) if pad_bottom_ratio is not None else 0.08
    high_left = float(pad_left_ratio) if pad_left_ratio is not None else 0.04
    low_top = float(min_pad_top_ratio) if min_pad_top_ratio is not None else max(0.0, high_top * 0.6)
    low_right = float(min_pad_right_ratio) if min_pad_right_ratio is not None else max(0.0, high_right * 0.6)
    low_bottom = float(min_pad_bottom_ratio) if min_pad_bottom_ratio is not None else max(0.0, high_bottom * 0.6)
    low_left = float(min_pad_left_ratio) if min_pad_left_ratio is not None else max(0.0, high_left * 0.6)
    if fixed_font_size:
        padding_level_candidates = [0.0]
    else:
        padding_level_candidates = [0.0, 0.5, 1.0]

    max_expand_right_ratio_px = max(0, int(round(base_w * max(0.0, float(max_expand_right_ratio)))))
    max_expand_down_ratio_px = max(0, int(round(base_h * max(0.0, float(max_expand_down_ratio)))))
    max_expand_left_ratio_px = max(0, int(round(base_w * max(0.0, float(max_expand_left_ratio)))))
    max_expand_up_ratio_px = max(0, int(round(base_h * max(0.0, float(max_expand_up_ratio)))))
    max_expand_right_abs_px = max(0, int(max_expand_right_px or 0))
    max_expand_down_abs_px = max(0, int(max_expand_down_px or 0))
    max_expand_left_abs_px = max(0, int(max_expand_left_px or 0))
    max_expand_up_abs_px = max(0, int(max_expand_up_px or 0))
    max_expand_right = max_expand_right_abs_px if max_expand_right_abs_px > 0 else max_expand_right_ratio_px
    max_expand_down = max_expand_down_abs_px if max_expand_down_abs_px > 0 else max_expand_down_ratio_px
    max_expand_left = max_expand_left_abs_px if max_expand_left_abs_px > 0 else max_expand_left_ratio_px
    max_expand_up = max_expand_up_abs_px if max_expand_up_abs_px > 0 else max_expand_up_ratio_px
    left_candidates = _expand_value_candidates(max_expand_left, expand_step_px)
    right_candidates = _expand_value_candidates(max_expand_right, expand_step_px)
    up_candidates = _expand_value_candidates(max_expand_up, expand_step_px)
    down_candidates = _expand_value_candidates(max_expand_down, expand_step_px)

    expansion_candidates: list[tuple[int, int, int, int]] = []
    for expand_down in down_candidates:
        for expand_right in right_candidates:
            for expand_left in left_candidates:
                for expand_up in up_candidates:
                    expansion_candidates.append((expand_left, expand_right, expand_up, expand_down))
    expansion_candidates = sorted(
        set(expansion_candidates),
        key=lambda item: (item[0] + item[1] + item[2] + item[3], item[3], item[1], item[0], item[2]),
    )

    blocked = [dict(box) for box in (blocked_boxes or []) if isinstance(box, dict) and box]
    if fixed_font_size:
        hyphenation_candidates = [False]
    else:
        hyphenation_candidates = [False, True] if allow_hyphenation else [False]
    resolved_max_font = int(max_font_size) if max_font_size is not None else None
    attempt_budget = max(0, int(max_layout_attempts))
    time_budget_ms = max(0, int(max_layout_ms))
    started = time.perf_counter()
    attempt_count = 0

    def _set_debug_reason(reason: str) -> None:
        if debug_meta is None:
            return
        debug_meta["reason"] = str(reason)
        debug_meta["attempts"] = int(attempt_count)
        debug_meta["elapsed_ms"] = int(round((time.perf_counter() - started) * 1000.0))

    def _budget_exceeded() -> bool:
        if attempt_budget > 0 and attempt_count >= attempt_budget:
            _set_debug_reason("layout_budget_attempts_exceeded")
            return True
        if time_budget_ms > 0:
            elapsed_ms = int(round((time.perf_counter() - started) * 1000.0))
            if elapsed_ms >= time_budget_ms:
                _set_debug_reason("layout_budget_time_exceeded")
                return True
        return False

    for expand_left, expand_right, expand_up, expand_down in expansion_candidates:
        if _budget_exceeded():
            return None
        candidate_bbox = _expand_bbox_sides(
            base_bbox,
            expand_left=expand_left,
            expand_right=expand_right,
            expand_up=expand_up,
            expand_down=expand_down,
            image_shape=image_shape,
        )
        expanded = (expand_left + expand_right + expand_up + expand_down) > 0
        if expanded and (not fixed_font_size) and _collides_with_blocked(candidate_bbox, blocked, collision_margin=collision_margin):
            continue

        for use_hyphenation in hyphenation_candidates:
            for line_ratio in line_spacing_candidates:
                for padding_level in padding_level_candidates:
                    if _budget_exceeded():
                        return None
                    pad_top = high_top + (low_top - high_top) * padding_level
                    pad_right = high_right + (low_right - high_right) * padding_level
                    pad_bottom = high_bottom + (low_bottom - high_bottom) * padding_level
                    pad_left = high_left + (low_left - high_left) * padding_level
                    attempt_count += 1
                    layout = fit_text_to_box(
                        text=text,
                        bbox=candidate_bbox,
                        font_path=font_path,
                        min_font_size=int(min_font_size),
                        max_font_size=resolved_max_font,
                        line_spacing_ratio=float(line_ratio),
                        pad_top_ratio=float(max(0.0, pad_top)),
                        pad_right_ratio=float(max(0.0, pad_right)),
                        pad_bottom_ratio=float(max(0.0, pad_bottom)),
                        pad_left_ratio=float(max(0.0, pad_left)),
                        allow_hyphenation=use_hyphenation,
                        hyphenation_min_word_length=hyphenation_min_word_length,
                        fixed_font_size=fixed_font_size,
                    )
                    if layout is None:
                        continue

                    compacted = (
                        padding_level > 1e-6
                        or line_ratio < (high_line_spacing - 1e-6)
                    )
                    if use_hyphenation:
                        strategy = "hyphenate"
                    elif expanded:
                        strategy = "expand"
                    elif compacted:
                        strategy = "compact"
                    else:
                        strategy = "fit"
                    return {
                        "layout": layout,
                        "bbox": candidate_bbox,
                        "strategy": strategy,
                        "line_spacing_ratio": float(line_ratio),
                        "padding_level": float(padding_level),
                        "hyphenation": bool(use_hyphenation),
                        "attempts": int(attempt_count),
                        "elapsed_ms": int(round((time.perf_counter() - started) * 1000.0)),
                    }
    if fixed_font_size:
        _set_debug_reason("fixed_font_overflow")
    else:
        _set_debug_reason("target_text_overflow")
    return None


def make_mask_for_boxes(image_shape: tuple[int, ...], boxes: list[dict[str, int]]) -> np.ndarray:
    mask = np.zeros(image_shape[:2], dtype=np.uint8)
    for bbox in boxes:
        x, y, w, h = _clamp_bbox(bbox, image_shape)
        cv2.rectangle(mask, (x, y), (x + w, y + h), 255, thickness=-1)
    return mask


def render_text_entries(
    *,
    original_bgr: np.ndarray,
    entries: list[dict],
    font_path: Path | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    boxes: list[dict[str, int]] = []
    for entry in entries:
        mask_boxes = entry.get("mask_boxes")
        if isinstance(mask_boxes, list) and mask_boxes:
            boxes.extend(mask_boxes)
        else:
            boxes.append(entry["mask_bbox"])
    mask = make_mask_for_boxes(original_bgr.shape, boxes)
    inpainted = cv2.inpaint(original_bgr, mask, 3, cv2.INPAINT_TELEA)
    image_rgb = cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(image_rgb)
    draw = ImageDraw.Draw(pil_image)

    for entry in entries:
        bbox = entry["bbox"]
        layout = entry["layout"]
        entry_font_path_raw = str(entry.get("font_path", "") or "").strip()
        entry_font_path = Path(entry_font_path_raw) if entry_font_path_raw else font_path
        if entry_font_path is None:
            raise RuntimeError("render_text_entries requires either entry['font_path'] or a fallback font_path.")
        font = ImageFont.truetype(str(entry_font_path), size=int(layout["font_size"]))
        text_rgb = tuple(int(v) for v in entry["text_color_rgb"])
        inline_prefix_text = str(layout.get("inline_prefix_text", "") or "")
        if inline_prefix_text:
            base_x = int(entry.get("render_x", int(bbox["x"]) + int(layout.get("offset_x", 0) or 0)))
            base_y = int(entry.get("render_y", int(bbox["y"]) + int(layout.get("offset_y", 0) or 0)))
            line_height = int(layout.get("line_height", _font_line_height(font)) or _font_line_height(font))
            spacing = int(layout.get("spacing", 0) or 0)
            indent = int(layout.get("inline_prefix_width", 0) or 0)
            lines = list(layout.get("lines", []) or [""])
            for index, line in enumerate(lines):
                line_y = base_y + index * (line_height + spacing)
                if index == 0:
                    draw.text((base_x, line_y), inline_prefix_text, font=font, fill=text_rgb, anchor="lt")
                draw.text((base_x + indent, line_y), line, font=font, fill=text_rgb, anchor="lt")
            continue

        marker_text = str(entry.get("render_marker_text", "") or "")
        marker_bbox = entry.get("render_marker_bbox", {})
        if marker_text and isinstance(marker_bbox, dict) and marker_bbox:
            marker_font_size = int(entry.get("render_marker_font_size", layout["font_size"]) or layout["font_size"])
            marker_font = ImageFont.truetype(str(entry_font_path), size=max(1, marker_font_size))
            marker_w, marker_h = _measure_text(marker_text, marker_font)
            marker_x = int(marker_bbox.get("x", 0) or 0)
            marker_y = int(marker_bbox.get("y", 0) or 0)
            marker_box_w = max(1, int(marker_bbox.get("w", 0) or 0))
            marker_box_h = max(1, int(marker_bbox.get("h", 0) or 0))
            marker_draw_x = marker_x + max(0, int(round((marker_box_w - marker_w) / 2.0)))
            marker_draw_y = marker_y + max(0, int(round((marker_box_h - marker_h) / 2.0)))
            draw.text(
                (marker_draw_x, marker_draw_y),
                marker_text,
                font=marker_font,
                fill=text_rgb,
                anchor="lt",
            )

        x = int(entry.get("render_x", int(bbox["x"]) + int(layout["offset_x"])))
        y = int(entry.get("render_y", int(bbox["y"]) + int(layout["offset_y"])))
        draw.multiline_text(
            (x, y),
            "\n".join(layout["lines"]),
            font=font,
            fill=text_rgb,
            spacing=int(layout["spacing"]),
            align="left",
            anchor="lt",
        )

    rendered = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    return rendered, mask
