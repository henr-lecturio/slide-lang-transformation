from __future__ import annotations

import os
from pathlib import Path

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

    quota_project_id = str(project_id or "").strip() or (os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip()
    if not quota_project_id:
        raise RuntimeError("GOOGLE_VISION_PROJECT_ID / --project-id must not be empty.")
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


def build_text_units(fragments: list[dict]) -> list[dict]:
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
                "bbox": _bbox_union(line_boxes),
                "line_bboxes": line_boxes,
                "line_count": len(line_fragments),
                "list_marker_fragment_id": int(unit.get("list_marker_fragment_id", 0) or 0),
                "list_marker_text": str(unit.get("list_marker_text", "") or ""),
                "list_marker_bbox": dict(unit.get("list_marker_bbox", {})),
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
    text_units = build_text_units(fragments)
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
