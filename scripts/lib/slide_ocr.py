from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np

from scripts.lib.slide_text_normalization import NORMALIZATION_VERSION, normalize_slide_text

BREAK_VALUE_TO_TEXT = {
    1: " ",
    2: " ",
    3: "\n",
    4: "-",
    5: "\n",
    "SPACE": " ",
    "SURE_SPACE": " ",
    "EOL_SURE_SPACE": "\n",
    "HYPHEN": "-",
    "LINE_BREAK": "\n",
}

LIST_MARKER_TEXTS = {
    "•",
    "●",
    "◦",
    "▪",
    "■",
    "▸",
    "▹",
    "►",
    "‣",
    "∙",
    "·",
    "○",
    "◯",
    "◆",
    "◇",
    "*",
    "-",
    "–",
    "—",
}


def ensure_cloud_vision_client(project_id: str):
    try:
        import google.auth
        from google.cloud import vision
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-cloud-vision is not installed in this environment. "
            "Run: source .venv/bin/activate && pip install google-cloud-vision"
        ) from exc

    quota_project_id = (
        str(project_id or "").strip()
        or (os.environ.get("GCLOUD_VISION_PROJECTID") or "").strip()
        or (os.environ.get("GOOGLE_VISION_PROJECT_ID") or "").strip()
        or (os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip()
    )
    if not quota_project_id:
        raise RuntimeError("GCLOUD_VISION_PROJECTID / --project-id must not be empty.")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", quota_project_id)
    credentials, default_project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
        quota_project_id=quota_project_id,
    )
    client = vision.ImageAnnotatorClient(credentials=credentials)
    return client, vision, quota_project_id, default_project


def _vertex_points(bounding_poly) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for vertex in getattr(bounding_poly, "vertices", []) or []:
        x = int(getattr(vertex, "x", 0) or 0)
        y = int(getattr(vertex, "y", 0) or 0)
        points.append((x, y))
    return points


def _bbox_from_points(points: list[tuple[int, int]]) -> dict[str, int]:
    if not points:
        return {"x": 0, "y": 0, "w": 0, "h": 0}
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    x0 = min(xs)
    y0 = min(ys)
    x1 = max(xs)
    y1 = max(ys)
    return {
        "x": int(x0),
        "y": int(y0),
        "w": int(max(0, x1 - x0)),
        "h": int(max(0, y1 - y0)),
    }


def _word_text(word) -> str:
    chars: list[str] = []
    for symbol in getattr(word, "symbols", []) or []:
        chars.append(str(getattr(symbol, "text", "") or ""))
    return "".join(chars)


def _word_break_text(word) -> str:
    symbols = list(getattr(word, "symbols", []) or [])
    if not symbols:
        return ""
    prop = getattr(symbols[-1], "property", None)
    detected_break = getattr(prop, "detected_break", None)
    break_value = getattr(detected_break, "type_", None)
    if break_value is None:
        break_value = getattr(detected_break, "type", None)
    if hasattr(break_value, "name"):
        break_value = break_value.name
    return BREAK_VALUE_TO_TEXT.get(break_value, "")


def _has_alnum(text: str) -> bool:
    return any(ch.isalnum() for ch in normalize_slide_text(text))


def _is_list_marker_fragment(fragment: dict) -> bool:
    text_norm = normalize_slide_text(str(fragment.get("text_norm", "") or fragment.get("text_raw", "") or ""))
    if not text_norm or _has_alnum(text_norm):
        return False
    return text_norm in LIST_MARKER_TEXTS


def _bbox_union(boxes: list[dict[str, int]]) -> dict[str, int]:
    if not boxes:
        return {"x": 0, "y": 0, "w": 0, "h": 0}
    x0 = min(int(box.get("x", 0) or 0) for box in boxes)
    y0 = min(int(box.get("y", 0) or 0) for box in boxes)
    x1 = max(int(box.get("x", 0) or 0) + max(1, int(box.get("w", 0) or 0)) for box in boxes)
    y1 = max(int(box.get("y", 0) or 0) + max(1, int(box.get("h", 0) or 0)) for box in boxes)
    return {"x": x0, "y": y0, "w": max(1, x1 - x0), "h": max(1, y1 - y0)}


def _word_count(text: str) -> int:
    normalized = normalize_slide_text(str(text or ""))
    if not normalized:
        return 0
    return len([part for part in normalized.split(" ") if part])


def _clamp_bbox(bbox: dict[str, int], image_shape: tuple[int, ...]) -> tuple[int, int, int, int]:
    image_h, image_w = image_shape[:2]
    x = max(0, min(int(bbox.get("x", 0) or 0), max(0, image_w - 1)))
    y = max(0, min(int(bbox.get("y", 0) or 0), max(0, image_h - 1)))
    w = max(1, int(bbox.get("w", 0) or 0))
    h = max(1, int(bbox.get("h", 0) or 0))
    x1 = max(x + 1, min(image_w, x + w))
    y1 = max(y + 1, min(image_h, y + h))
    return x, y, x1 - x, y1 - y


def _graphic_context_metrics(
    image_bgr: np.ndarray | None,
    image_gray: np.ndarray | None,
    text_bbox: dict[str, int],
) -> dict[str, float]:
    if image_bgr is None or image_gray is None or image_bgr.size == 0 or image_gray.size == 0:
        return {
            "ring_std_gray": 0.0,
            "ring_edge_density": 0.0,
            "ring_sat_std": 0.0,
            "ring_luma_range": 0.0,
        }
    x, y, w, h = _clamp_bbox(text_bbox, image_bgr.shape)
    pad = max(2, int(round(min(w, h) * 0.22)))
    image_h, image_w = image_bgr.shape[:2]
    ex0 = max(0, x - pad)
    ey0 = max(0, y - pad)
    ex1 = min(image_w, x + w + pad)
    ey1 = min(image_h, y + h + pad)
    if ex1 <= ex0 or ey1 <= ey0:
        return {
            "ring_std_gray": 0.0,
            "ring_edge_density": 0.0,
            "ring_sat_std": 0.0,
            "ring_luma_range": 0.0,
        }

    gray_region = image_gray[ey0:ey1, ex0:ex1]
    bgr_region = image_bgr[ey0:ey1, ex0:ex1]
    if gray_region.size == 0 or bgr_region.size == 0:
        return {
            "ring_std_gray": 0.0,
            "ring_edge_density": 0.0,
            "ring_sat_std": 0.0,
            "ring_luma_range": 0.0,
        }

    inner_x0 = max(0, x - ex0)
    inner_y0 = max(0, y - ey0)
    inner_x1 = min(gray_region.shape[1], inner_x0 + w)
    inner_y1 = min(gray_region.shape[0], inner_y0 + h)
    ring_mask = np.ones(gray_region.shape[:2], dtype=bool)
    ring_mask[inner_y0:inner_y1, inner_x0:inner_x1] = False
    ring_area = int(np.count_nonzero(ring_mask))
    if ring_area < 12:
        return {
            "ring_std_gray": 0.0,
            "ring_edge_density": 0.0,
            "ring_sat_std": 0.0,
            "ring_luma_range": 0.0,
        }

    ring_gray = gray_region[ring_mask]
    ring_std_gray = float(np.std(ring_gray))
    try:
        luma_p10, luma_p90 = np.percentile(ring_gray, [10, 90])
        ring_luma_range = float(luma_p90 - luma_p10)
    except Exception:
        ring_luma_range = 0.0

    edges = cv2.Canny(gray_region, 60, 160)
    ring_edge_density = float(np.mean(edges[ring_mask] > 0))

    hsv_region = cv2.cvtColor(bgr_region, cv2.COLOR_BGR2HSV)
    ring_sat = hsv_region[:, :, 1][ring_mask]
    ring_sat_std = float(np.std(ring_sat))

    return {
        "ring_std_gray": ring_std_gray,
        "ring_edge_density": ring_edge_density,
        "ring_sat_std": ring_sat_std,
        "ring_luma_range": ring_luma_range,
    }


def _graphic_context_score(metrics: dict[str, float]) -> float:
    std_gray = float(metrics.get("ring_std_gray", 0.0) or 0.0)
    edge_density = float(metrics.get("ring_edge_density", 0.0) or 0.0)
    sat_std = float(metrics.get("ring_sat_std", 0.0) or 0.0)
    luma_range = float(metrics.get("ring_luma_range", 0.0) or 0.0)
    score = 0.0
    if std_gray >= 22.0:
        score += 1.2
    elif std_gray >= 16.0:
        score += 0.5
    if edge_density >= 0.06:
        score += 1.2
    elif edge_density >= 0.04:
        score += 0.5
    if sat_std >= 20.0:
        score += 1.0
    elif sat_std >= 14.0:
        score += 0.4
    if luma_range >= 56.0:
        score += 0.9
    elif luma_range >= 40.0:
        score += 0.35
    return score


def _is_graphic_embedded_candidate(
    *,
    context_score: float,
    word_count: int,
    line_count: int,
    bbox: dict[str, int],
    image_width: int,
    image_height: int,
) -> bool:
    bbox_w = max(1, int(bbox.get("w", 0) or 0))
    bbox_y = int(bbox.get("y", 0) or 0)
    rel_width = float(bbox_w) / float(max(1, image_width))
    rel_top = float(bbox_y) / float(max(1, image_height))
    if context_score < 2.95:
        return False
    if word_count <= 0 or word_count > 10:
        return False
    if line_count <= 0 or line_count > 3:
        return False
    if rel_width > 0.68:
        return False
    if rel_top < 0.12:
        return False
    return True


def _fragment_sort_key(fragment: dict) -> tuple[int, int, int]:
    bbox = fragment.get("bbox", {})
    return (
        int(bbox.get("y", 0) or 0),
        int(bbox.get("x", 0) or 0),
        int(fragment.get("fragment_id", 0) or 0),
    )


def _fragment_center_y(fragment: dict) -> float:
    bbox = fragment.get("bbox", {})
    y = int(bbox.get("y", 0) or 0)
    h = max(1, int(bbox.get("h", 0) or 0))
    return float(y) + float(h) / 2.0


def _find_best_list_marker(text_fragment: dict, marker_fragments: list[dict], used_marker_ids: set[int]) -> dict | None:
    bbox = text_fragment.get("bbox", {})
    text_x = int(bbox.get("x", 0) or 0)
    text_y = int(bbox.get("y", 0) or 0)
    text_w = max(1, int(bbox.get("w", 0) or 0))
    text_h = max(1, int(bbox.get("h", 0) or 0))
    text_center_y = _fragment_center_y(text_fragment)

    best_marker = None
    best_score = None
    for marker in marker_fragments:
        marker_id = int(marker.get("fragment_id", 0) or 0)
        if marker_id in used_marker_ids:
            continue
        marker_bbox = marker.get("bbox", {})
        marker_x = int(marker_bbox.get("x", 0) or 0)
        marker_y = int(marker_bbox.get("y", 0) or 0)
        marker_w = max(1, int(marker_bbox.get("w", 0) or 0))
        marker_h = max(1, int(marker_bbox.get("h", 0) or 0))
        marker_right = marker_x + marker_w
        horizontal_gap = text_x - marker_right
        if horizontal_gap < -8 or horizontal_gap > max(80, int(round(text_h * 3.2))):
            continue
        center_delta = abs(text_center_y - _fragment_center_y(marker))
        if center_delta > max(18.0, float(max(text_h, marker_h)) * 0.9):
            continue
        top_delta = abs(text_y - marker_y)
        if top_delta > max(28, int(round(max(text_h, marker_h) * 1.4))):
            continue
        score = center_delta + float(max(0, horizontal_gap)) * 0.15 + float(top_delta) * 0.1
        if best_score is None or score < best_score:
            best_marker = marker
            best_score = score
    return best_marker


def _infer_list_marker_bbox_from_pixels(
    image_gray: np.ndarray | None,
    text_bbox: dict[str, int],
    *,
    image_width: int,
    image_height: int,
) -> dict[str, int]:
    if image_gray is None or image_gray.size == 0:
        return {}
    text_x = int(text_bbox.get("x", 0) or 0)
    text_y = int(text_bbox.get("y", 0) or 0)
    text_w = max(1, int(text_bbox.get("w", 0) or 0))
    text_h = max(1, int(text_bbox.get("h", 0) or 0))
    if text_h < 16:
        return {}

    search_gap_right = max(4, int(round(text_h * 0.15)))
    search_w = max(12, int(round(text_h * 1.35)))
    search_x1 = text_x - search_gap_right
    search_x0 = max(0, search_x1 - search_w)
    search_y0 = max(0, text_y + int(round(text_h * 0.1)))
    search_y1 = min(image_height, text_y + int(round(text_h * 0.9)))
    if search_x1 <= search_x0 or search_y1 <= search_y0:
        return {}
    if search_x0 >= image_width or search_y0 >= image_height:
        return {}

    patch = image_gray[search_y0:search_y1, search_x0:search_x1]
    if patch.size == 0:
        return {}

    bg_level = float(np.median(patch))
    dark_threshold = int(max(0, min(255, round(bg_level - max(18.0, float(np.std(patch)) * 0.9)))))
    if dark_threshold <= 0:
        return {}

    dark_mask = (patch <= dark_threshold).astype(np.uint8) * 255
    kernel = np.ones((3, 3), dtype=np.uint8)
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    components, labels, stats, _centroids = cv2.connectedComponentsWithStats(dark_mask, connectivity=8)
    if components <= 1:
        return {}

    text_center_y = float(text_y) + float(text_h) / 2.0
    best_bbox: dict[str, int] | None = None
    best_score: float | None = None
    region_area = float(max(1, patch.shape[0] * patch.shape[1]))
    for idx in range(1, components):
        comp_x = int(stats[idx, cv2.CC_STAT_LEFT])
        comp_y = int(stats[idx, cv2.CC_STAT_TOP])
        comp_w = max(1, int(stats[idx, cv2.CC_STAT_WIDTH]))
        comp_h = max(1, int(stats[idx, cv2.CC_STAT_HEIGHT]))
        comp_area = int(stats[idx, cv2.CC_STAT_AREA])
        if comp_area < 6 or comp_area > max(1200, int(round(region_area * 0.18))):
            continue
        aspect = float(comp_w) / float(max(1, comp_h))
        if aspect < 0.45 or aspect > 2.2:
            continue
        marker_x = search_x0 + comp_x
        marker_y = search_y0 + comp_y
        if marker_x < int(round(float(image_width) * 0.045)):
            continue
        marker_right = marker_x + comp_w
        horizontal_gap = text_x - marker_right
        if horizontal_gap < 2 or horizontal_gap > max(64, int(round(text_h * 2.4))):
            continue
        marker_center_y = float(marker_y) + float(comp_h) / 2.0
        center_delta = abs(marker_center_y - text_center_y)
        if center_delta > max(18.0, float(text_h) * 0.55):
            continue
        rel_size = float(comp_h) / float(max(1, text_h))
        if rel_size < 0.12 or rel_size > 0.9:
            continue
        score = center_delta + float(horizontal_gap) * 0.2 + abs(0.32 - rel_size) * 12.0
        if best_score is None or score < best_score:
            best_score = score
            best_bbox = {"x": marker_x, "y": marker_y, "w": comp_w, "h": comp_h}

    return best_bbox or {}


def _can_append_to_text_unit(current_unit: dict, fragment: dict) -> bool:
    current_lines = list(current_unit.get("fragments", []) or [])
    if not current_lines:
        return False
    last_fragment = current_lines[-1]
    first_fragment = current_lines[0]
    last_bbox = last_fragment.get("bbox", {})
    first_bbox = first_fragment.get("bbox", {})
    bbox = fragment.get("bbox", {})

    fragment_x = int(bbox.get("x", 0) or 0)
    fragment_y = int(bbox.get("y", 0) or 0)
    fragment_w = max(1, int(bbox.get("w", 0) or 0))
    fragment_h = max(1, int(bbox.get("h", 0) or 0))
    first_x = int(first_bbox.get("x", 0) or 0)
    last_y = int(last_bbox.get("y", 0) or 0)
    last_h = max(1, int(last_bbox.get("h", 0) or 0))
    last_bottom = last_y + last_h
    vertical_gap = fragment_y - last_bottom
    top_gap = fragment_y - last_y
    x_delta = abs(fragment_x - first_x)
    width_ratio = float(fragment_w) / float(max(1, int(first_bbox.get("w", 0) or 1)))
    shared_block = int(fragment.get("block_id", 0) or 0) == int(last_fragment.get("block_id", 0) or 0)

    if top_gap < 0:
        return False
    if vertical_gap > max(32, int(round(max(last_h, fragment_h) * 1.15))):
        return False
    if x_delta > max(26, int(round(max(fragment_h, last_h) * 0.95))):
        return False
    if width_ratio < 0.28 or width_ratio > 3.2:
        return False
    if current_unit.get("list_marker_fragment_id") and not shared_block and vertical_gap > max(18, int(round(fragment_h * 0.6))):
        return False
    return shared_block or vertical_gap <= max(18, int(round(max(last_h, fragment_h) * 0.55)))


def build_text_units(
    fragments: list[dict],
    *,
    image_bgr: np.ndarray | None = None,
    image_gray: np.ndarray | None = None,
    image_width: int = 0,
    image_height: int = 0,
) -> list[dict]:
    marker_fragments = sorted([fragment for fragment in fragments if _is_list_marker_fragment(fragment)], key=_fragment_sort_key)
    text_fragments = sorted([fragment for fragment in fragments if _has_alnum(str(fragment.get("text_norm", "") or fragment.get("text_raw", "") or ""))], key=_fragment_sort_key)
    used_marker_ids: set[int] = set()
    units: list[dict] = []
    current_unit: dict | None = None
    next_unit_id = 1

    for fragment in text_fragments:
        marker = _find_best_list_marker(fragment, marker_fragments, used_marker_ids)
        start_new_unit = marker is not None or current_unit is None or not _can_append_to_text_unit(current_unit, fragment)
        if start_new_unit:
            marker_id = int(marker.get("fragment_id", 0) or 0) if marker else 0
            if marker_id > 0:
                used_marker_ids.add(marker_id)
            current_unit = {
                "unit_id": next_unit_id,
                "slide_index": int(fragment.get("slide_index", 0) or 0),
                "event_id": int(fragment.get("event_id", 0) or 0),
                "fragments": [],
                "list_marker_fragment_id": marker_id,
                "list_marker_text": str(marker.get("text_raw", "") or "") if marker else "",
                "list_marker_bbox": dict(marker.get("bbox", {})) if marker else {},
            }
            units.append(current_unit)
            next_unit_id += 1

        current_unit["fragments"].append(fragment)

    out: list[dict] = []
    for unit in units:
        line_fragments = sorted(list(unit.get("fragments", []) or []), key=_fragment_sort_key)
        line_boxes = [dict(fragment.get("bbox", {})) for fragment in line_fragments]
        line_texts = [str(fragment.get("text_raw", "") or "").strip() for fragment in line_fragments]
        source_text = " ".join(text for text in line_texts if text).strip()
        source_text_norm = normalize_slide_text(source_text)
        bbox = _bbox_union(line_boxes)
        marker_fragment_id = int(unit.get("list_marker_fragment_id", 0) or 0)
        marker_text = str(unit.get("list_marker_text", "") or "")
        marker_bbox = dict(unit.get("list_marker_bbox", {}))
        marker_inferred = False
        if marker_fragment_id <= 0 and image_gray is not None and image_width > 0 and image_height > 0:
            word_count = _word_count(source_text)
            line_count = len(line_fragments)
            bbox_w = max(1, int(bbox.get("w", 0) or 0))
            bbox_x = int(bbox.get("x", 0) or 0)
            rel_top = float(int(bbox.get("y", 0) or 0)) / float(max(1, image_height))
            rel_width = float(bbox_w) / float(max(1, image_width))
            rel_left = float(bbox_x) / float(max(1, image_width))
            if (
                1 <= line_count <= 3
                and 1 <= word_count <= 9
                and rel_width <= 0.5
                and rel_top >= 0.16
                and rel_left >= 0.08
            ):
                inferred_bbox = _infer_list_marker_bbox_from_pixels(
                    image_gray,
                    bbox,
                    image_width=image_width,
                    image_height=image_height,
                )
                if inferred_bbox:
                    marker_inferred = True
                    marker_text = "\u2022"
                    marker_bbox = inferred_bbox

        context_metrics = _graphic_context_metrics(image_bgr, image_gray, bbox)
        context_score = _graphic_context_score(context_metrics)
        graphic_embedded_candidate = _is_graphic_embedded_candidate(
            context_score=context_score,
            word_count=_word_count(source_text),
            line_count=len(line_fragments),
            bbox=bbox,
            image_width=image_width,
            image_height=image_height,
        )

        out.append(
            {
                "unit_id": int(unit.get("unit_id", 0) or 0),
                "slide_index": int(unit.get("slide_index", 0) or 0),
                "event_id": int(unit.get("event_id", 0) or 0),
                "fragment_ids": [int(fragment.get("fragment_id", 0) or 0) for fragment in line_fragments],
                "block_ids": sorted({int(fragment.get("block_id", 0) or 0) for fragment in line_fragments if int(fragment.get("block_id", 0) or 0) > 0}),
                "line_ids": [int(fragment.get("line_id", 0) or 0) for fragment in line_fragments],
                "source_lines": line_texts,
                "source_text": source_text,
                "source_text_norm": source_text_norm,
                "bbox": bbox,
                "line_bboxes": line_boxes,
                "line_count": len(line_fragments),
                "list_marker_fragment_id": marker_fragment_id,
                "list_marker_text": marker_text,
                "list_marker_bbox": marker_bbox,
                "list_marker_inferred": marker_inferred,
                "graphic_context_score": context_score,
                "graphic_ring_std_gray": float(context_metrics.get("ring_std_gray", 0.0) or 0.0),
                "graphic_ring_edge_density": float(context_metrics.get("ring_edge_density", 0.0) or 0.0),
                "graphic_ring_sat_std": float(context_metrics.get("ring_sat_std", 0.0) or 0.0),
                "graphic_ring_luma_range": float(context_metrics.get("ring_luma_range", 0.0) or 0.0),
                "graphic_embedded_candidate": bool(graphic_embedded_candidate),
            }
        )
    return out


def ocr_slide_fragments(
    client,
    vision,
    *,
    image_path: Path,
    event_id: int,
    slide_index: int,
    feature: str = "DOCUMENT_TEXT_DETECTION",
) -> dict:
    image_bytes = image_path.read_bytes()
    image_np = np.frombuffer(image_bytes, dtype=np.uint8)
    image_bgr = cv2.imdecode(image_np, cv2.IMREAD_COLOR) if image_np.size else None
    image_gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if image_bgr is not None else None
    image = vision.Image(content=image_bytes)
    if str(feature or "").strip().upper() != "DOCUMENT_TEXT_DETECTION":
        raise RuntimeError(f"Unsupported Google Vision feature: {feature}")

    response = client.document_text_detection(image=image)
    if getattr(response, "error", None) and getattr(response.error, "message", ""):
        raise RuntimeError(str(response.error.message))

    annotation = getattr(response, "full_text_annotation", None)
    fragments: list[dict] = []
    image_width = 0
    image_height = 0
    fragment_id = 0

    if annotation:
        pages = list(getattr(annotation, "pages", []) or [])
        if pages:
            image_width = int(getattr(pages[0], "width", 0) or 0)
            image_height = int(getattr(pages[0], "height", 0) or 0)

        for page_index, page in enumerate(pages):
            for block_index, block in enumerate(getattr(page, "blocks", []) or []):
                paragraphs = list(getattr(block, "paragraphs", []) or [])
                for paragraph_index, paragraph in enumerate(paragraphs):
                    text_parts: list[str] = []
                    for word in getattr(paragraph, "words", []) or []:
                        word_text = _word_text(word)
                        if not word_text:
                            continue
                        text_parts.append(word_text)
                        text_parts.append(_word_break_text(word))
                    text_raw = "".join(text_parts).strip()
                    text_norm = normalize_slide_text(text_raw)
                    bbox = _bbox_from_points(_vertex_points(getattr(paragraph, "bounding_box", None)))
                    fragment_id += 1
                    fragments.append(
                        {
                            "slide_index": int(slide_index),
                            "event_id": int(event_id),
                            "fragment_id": fragment_id,
                            "page_id": int(page_index + 1),
                            "block_id": int(block_index + 1),
                            "line_id": int(paragraph_index + 1),
                            "text_raw": text_raw,
                            "text_norm": text_norm,
                            "bbox": bbox,
                            "confidence": float(getattr(paragraph, "confidence", 0.0) or 0.0),
                        }
                    )

    full_text_raw = str(getattr(annotation, "text", "") or "").strip() if annotation else ""
    if (image_width <= 0 or image_height <= 0) and image_gray is not None:
        image_height = int(image_gray.shape[0])
        image_width = int(image_gray.shape[1])
    text_units = build_text_units(
        fragments,
        image_bgr=image_bgr,
        image_gray=image_gray,
        image_width=image_width,
        image_height=image_height,
    )
    return {
        "image_name": image_path.name,
        "image_path": str(image_path),
        "event_id": int(event_id),
        "slide_index": int(slide_index),
        "ocr_provider": "google_vision_document_text_detection",
        "normalization_version": NORMALIZATION_VERSION,
        "image_width": image_width,
        "image_height": image_height,
        "full_text_raw": full_text_raw,
        "full_text_norm": normalize_slide_text(full_text_raw),
        "fragments": fragments,
        "text_units": text_units,
    }
