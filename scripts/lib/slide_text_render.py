from __future__ import annotations

import math
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


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    paragraphs = str(text or "").splitlines() or [str(text or "")]
    lines: list[str] = []
    for paragraph in paragraphs:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            width, _ = _measure_text(candidate, font)
            if current and width > max_width:
                lines.append(current)
                current = word
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
) -> dict | None:
    font = ImageFont.truetype(str(font_path), size=max(1, int(font_size)))
    spacing = _resolve_spacing(int(font_size), line_spacing_ratio)
    lines = _wrap_text(text, font, max(1, int(max_width)))
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
) -> dict | None:
    font = ImageFont.truetype(str(font_path), size=max(1, int(font_size)))
    spacing = _resolve_spacing(int(font_size), line_spacing_ratio)
    prefix_label = str(prefix_text or "").strip() or "\u2022"
    prefix_w, _prefix_h = _measure_text(prefix_label, font)
    gap = max(4, int(prefix_gap) if prefix_gap is not None else int(round(font_size * 0.45)))
    hanging_indent = prefix_w + gap
    available_text_w = max(1, int(max_width) - hanging_indent)
    lines = _wrap_text(text, font, available_text_w)
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
    lines = _wrap_text(text, font, available_w)
    text_w, text_h = _measure_multiline(lines, font, spacing)
    if text_w > available_w or text_h > available_h:
        return None

    offset_x = pad_left
    offset_y = pad_top
    if available_h > text_h:
        offset_y += int(math.floor((available_h - text_h) / 2.0))
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
) -> dict | None:
    box_h = max(1, int(bbox.get("h", 0) or 0))
    resolved_max_font_size = max_font_size
    if resolved_max_font_size is None:
        resolved_max_font_size = max(min_font_size, min(box_h, max(18, int(round(box_h * 0.95)))))
    for font_size in range(int(resolved_max_font_size), int(min_font_size) - 1, -1):
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
        )
        if layout is not None:
            return layout
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
                    draw.text((base_x, line_y), inline_prefix_text, font=font, fill=text_rgb)
                draw.text((base_x + indent, line_y), line, font=font, fill=text_rgb)
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
        )

    rendered = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    return rendered, mask
