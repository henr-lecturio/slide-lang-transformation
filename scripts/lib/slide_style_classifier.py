from __future__ import annotations

from scripts.lib.slide_text_normalization import normalize_slide_text


def _bbox_xywh(bbox: dict[str, int]) -> tuple[int, int, int, int]:
    return (
        int(bbox.get("x", 0) or 0),
        int(bbox.get("y", 0) or 0),
        max(1, int(bbox.get("w", 0) or 0)),
        max(1, int(bbox.get("h", 0) or 0)),
    )


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(int(value) for value in values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[mid])
    return float(ordered[mid - 1] + ordered[mid]) / 2.0


def _percentile(values: list[int], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(int(value) for value in values)
    if len(ordered) == 1:
        return float(ordered[0])
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * float(ratio)))))
    return float(ordered[index])


def _word_count(text: str) -> int:
    normalized = normalize_slide_text(text)
    return len([part for part in normalized.split(" ") if part])


def _horizontal_zone(center_x_ratio: float) -> str:
    if center_x_ratio < 0.34:
        return "left"
    if center_x_ratio > 0.66:
        return "right"
    return "center"


def _vertical_zone(center_y_ratio: float) -> str:
    if center_y_ratio < 0.18:
        return "top"
    if center_y_ratio < 0.38:
        return "upper"
    if center_y_ratio < 0.68:
        return "middle"
    if center_y_ratio < 0.88:
        return "lower"
    return "bottom"


def _slot_id(role: str, bbox: dict[str, int], image_width: int, image_height: int) -> tuple[str, str, str]:
    x, y, w, h = _bbox_xywh(bbox)
    center_x_ratio = (float(x) + float(w) / 2.0) / float(max(1, image_width))
    center_y_ratio = (float(y) + float(h) / 2.0) / float(max(1, image_height))
    horizontal = _horizontal_zone(center_x_ratio)
    vertical = _vertical_zone(center_y_ratio)
    if role.startswith("list_item_"):
        return f"{role}.{horizontal}", vertical, horizontal
    return f"{role}.{vertical}_{horizontal}", vertical, horizontal


def _pick_title_candidate(units: list[dict], image_height: int, median_h: float, p75_h: float, p90_h: float) -> int:
    best_unit_id = 0
    best_score = None
    for unit in units:
        if int(unit.get("list_marker_fragment_id", 0) or 0) > 0:
            continue
        x, y, w, h = _bbox_xywh(unit.get("bbox", {}))
        if (float(y) / float(max(1, image_height))) > 0.34:
            continue
        words = _word_count(str(unit.get("source_text", "") or ""))
        if words > 18:
            continue
        if float(h) < max(median_h * 1.2, p75_h * 0.95):
            continue
        score = float(h) * 2.0 + float(w) * 0.08 - float(y) * 0.04 - float(max(0, words - 8)) * 1.2
        if float(h) >= p90_h:
            score += 10.0
        if best_score is None or score > best_score:
            best_score = score
            best_unit_id = int(unit.get("unit_id", 0) or 0)
    return best_unit_id


def _pick_subtitle_candidate(
    units: list[dict],
    *,
    title_unit_id: int,
    image_height: int,
    median_h: float,
    p75_h: float,
) -> int:
    if title_unit_id <= 0:
        return 0
    title_unit = next((unit for unit in units if int(unit.get("unit_id", 0) or 0) == title_unit_id), None)
    if not title_unit:
        return 0
    _tx, ty, _tw, th = _bbox_xywh(title_unit.get("bbox", {}))
    title_bottom = ty + th

    best_unit_id = 0
    best_score = None
    for unit in units:
        unit_id = int(unit.get("unit_id", 0) or 0)
        if unit_id == title_unit_id or int(unit.get("list_marker_fragment_id", 0) or 0) > 0:
            continue
        x, y, w, h = _bbox_xywh(unit.get("bbox", {}))
        if y <= ty:
            continue
        if (float(y) / float(max(1, image_height))) > 0.5:
            continue
        if y - title_bottom > max(120, int(round(max(th, h) * 4.5))):
            continue
        words = _word_count(str(unit.get("source_text", "") or ""))
        if words > 26:
            continue
        if float(h) < max(median_h * 1.02, p75_h * 0.75):
            continue
        score = float(h) * 1.6 + float(w) * 0.05 - float(y - title_bottom) * 0.06 - float(max(0, words - 12)) * 0.9
        if best_score is None or score > best_score:
            best_score = score
            best_unit_id = unit_id
    return best_unit_id


def classify_text_units(text_units: list[dict], *, image_width: int, image_height: int) -> list[dict]:
    units = [dict(unit) for unit in text_units]
    non_list_heights = [
        _bbox_xywh(unit.get("bbox", {}))[3]
        for unit in units
        if int(unit.get("list_marker_fragment_id", 0) or 0) <= 0
    ]
    median_h = _median(non_list_heights) or 24.0
    p75_h = _percentile(non_list_heights, 0.75) or median_h
    p90_h = _percentile(non_list_heights, 0.9) or p75_h

    title_unit_id = _pick_title_candidate(units, image_height, median_h, p75_h, p90_h)
    subtitle_unit_id = _pick_subtitle_candidate(
        units,
        title_unit_id=title_unit_id,
        image_height=image_height,
        median_h=median_h,
        p75_h=p75_h,
    )

    out: list[dict] = []
    for unit in sorted(units, key=lambda item: (_bbox_xywh(item.get("bbox", {}))[1], _bbox_xywh(item.get("bbox", {}))[0])):
        unit_id = int(unit.get("unit_id", 0) or 0)
        x, y, w, h = _bbox_xywh(unit.get("bbox", {}))
        words = _word_count(str(unit.get("source_text", "") or ""))
        line_count = max(1, int(unit.get("line_count", 1) or 1))
        rel_top = float(y) / float(max(1, image_height))
        rel_bottom = float(y + h) / float(max(1, image_height))
        rel_width = float(w) / float(max(1, image_width))

        reason = "fallback_body"
        if int(unit.get("list_marker_fragment_id", 0) or 0) > 0:
            role = "list_item_level_1"
            reason = "list_marker"
        elif unit_id == title_unit_id:
            role = "title"
            reason = "top_largest_text"
        elif unit_id == subtitle_unit_id:
            role = "subtitle"
            reason = "below_title_large_text"
        elif rel_bottom >= 0.96 and float(h) <= max(p75_h * 1.1, median_h * 1.25):
            role = "footer"
            reason = "bottom_small_text"
        elif (
            words <= 14
            and line_count <= 2
            and float(h) >= max(median_h * 1.14, p75_h * 0.92)
            and rel_top < 0.78
        ):
            role = "section_heading"
            reason = "short_large_heading"
        elif rel_top >= 0.66 and rel_width <= 0.48 and float(h) <= max(p75_h * 1.1, median_h * 1.2):
            role = "caption"
            reason = "small_lower_text"
        else:
            role = "body"

        slot_id, vertical_zone, horizontal_zone = _slot_id(role, unit.get("bbox", {}), image_width, image_height)
        out.append(
            {
                "unit_id": unit_id,
                "role": role,
                "slot_id": slot_id,
                "slot_vertical_zone": vertical_zone,
                "slot_horizontal_zone": horizontal_zone,
                "classification_reason": reason,
            }
        )
    return out
