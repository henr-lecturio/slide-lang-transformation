from __future__ import annotations

from scripts.lib.slide_text_normalization import normalize_slide_text

SECTION_HEADING_SCORE_THRESHOLD = 2.0
SECTION_HEADING_PROMOTION_MIN_SCORE = 1.5
IMPLICIT_LIST_MIN_CLUSTER_SIZE = 2
GRAPHIC_EMBEDDED_SCORE_THRESHOLD = 2.95
SECTION_HEADING_ZONE_MAX_TOP = 0.36
SECTION_HEADING_ZONE_MAX_LEFT = 0.56
SECTION_HEADING_ZONE_MAX_CENTER_X = 0.48
SECTION_HEADING_ZONE_MIN_WIDTH = 0.08
SECTION_HEADING_ZONE_MAX_WIDTH = 0.72
SECTION_HEADING_ZONE_MAX_WORDS = 14
SECTION_HEADING_ZONE_MAX_LINES = 2
EVENT1_TITLE_ZONE_MIN_TOP = 0.24
EVENT1_TITLE_ZONE_MAX_TOP = 0.62
EVENT1_TITLE_ZONE_MAX_LEFT = 0.26
EVENT1_TITLE_ZONE_MIN_WIDTH = 0.20
EVENT1_TITLE_ZONE_MAX_WIDTH = 0.78
EVENT1_TITLE_ZONE_MAX_WORDS = 10
EVENT1_TITLE_ZONE_MAX_LINES = 2
EVENT1_SUBTITLE_ZONE_MAX_LEFT = 0.32
EVENT1_SUBTITLE_ZONE_MIN_WIDTH = 0.10
EVENT1_SUBTITLE_ZONE_MAX_WIDTH = 0.55
EVENT1_SUBTITLE_ZONE_MAX_WORDS = 10
EVENT1_SUBTITLE_ZONE_MAX_LINES = 2


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


def _median_float(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[mid])
    return float(ordered[mid - 1] + ordered[mid]) / 2.0


def _word_count(text: str) -> int:
    normalized = normalize_slide_text(text)
    return len([part for part in normalized.split(" ") if part])


def _bool_value(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() not in {"", "0", "false", "no", "off"}


def _has_list_marker(unit: dict) -> bool:
    if int(unit.get("list_marker_fragment_id", 0) or 0) > 0:
        return True
    if _bool_value(unit.get("list_marker_inferred")):
        return True
    marker_bbox = unit.get("list_marker_bbox", {})
    if isinstance(marker_bbox, dict):
        marker_w = int(marker_bbox.get("w", 0) or 0)
        marker_h = int(marker_bbox.get("h", 0) or 0)
        if marker_w > 0 and marker_h > 0:
            return True
    return False


def _is_graphic_embedded_unit(unit: dict, *, image_width: int, image_height: int) -> tuple[bool, str]:
    candidate = _bool_value(unit.get("graphic_embedded_candidate"))
    score = float(unit.get("graphic_context_score", 0.0) or 0.0)
    ring_std = float(unit.get("graphic_ring_std_gray", 0.0) or 0.0)
    ring_edge = float(unit.get("graphic_ring_edge_density", 0.0) or 0.0)
    ring_sat = float(unit.get("graphic_ring_sat_std", 0.0) or 0.0)
    ring_luma = float(unit.get("graphic_ring_luma_range", 0.0) or 0.0)
    _x, y, w, _h = _bbox_xywh(unit.get("bbox", {}))
    words = _word_count(str(unit.get("source_text", "") or ""))
    line_count = max(1, int(unit.get("line_count", 1) or 1))
    rel_width = float(w) / float(max(1, image_width))
    rel_top = float(y) / float(max(1, image_height))
    if not candidate and score < GRAPHIC_EMBEDDED_SCORE_THRESHOLD:
        return False, ""
    if words <= 0 or words > 10:
        return False, ""
    if line_count > 3:
        return False, ""
    if rel_width > 0.68:
        return False, ""
    if rel_top < 0.12:
        return False, ""
    reason = (
        "graphic_embedded;"
        f"score={score:.2f};std={ring_std:.1f};edge={ring_edge:.3f};"
        f"sat={ring_sat:.1f};luma={ring_luma:.1f}"
    )
    return True, reason


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
        if _has_list_marker(unit):
            continue
        _x, y, w, h = _bbox_xywh(unit.get("bbox", {}))
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
        if unit_id == title_unit_id or _has_list_marker(unit):
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


def _section_heading_score(
    *,
    words: int,
    line_count: int,
    h: int,
    rel_top: float,
    rel_width: float,
    median_h: float,
    p75_h: float,
) -> tuple[float, str]:
    score = 0.0

    if words <= 8:
        score += 0.9
    elif words <= 14:
        score += 0.6
    elif words <= 20:
        score += 0.2
    elif words <= 28:
        score -= 0.4
    else:
        score -= 1.0

    if line_count <= 1:
        score += 0.7
    elif line_count == 2:
        score += 0.5
    elif line_count == 3:
        score += 0.1
    else:
        score -= 0.8

    h_rel_med = float(h) / float(max(1.0, median_h))
    h_rel_p75 = float(h) / float(max(1.0, p75_h))
    if h_rel_med >= 1.25 or h_rel_p75 >= 1.05:
        score += 1.3
    elif h_rel_med >= 1.12 or h_rel_p75 >= 0.95:
        score += 0.9
    elif h_rel_med >= 1.0:
        score += 0.45
    elif h_rel_med >= 0.9:
        score += 0.05
    else:
        score -= 0.7

    if rel_top < 0.24:
        score += 0.8
    elif rel_top < 0.45:
        score += 0.55
    elif rel_top < 0.62:
        score += 0.25
    elif rel_top < 0.78:
        score -= 0.15
    else:
        score -= 0.7

    if rel_width <= 0.78:
        score += 0.25
    elif rel_width <= 0.92:
        score += 0.1
    else:
        score -= 0.15

    reason = (
        f"score={score:.2f};words={words};lines={line_count};"
        f"h={int(h)};h_med={h_rel_med:.2f};top={rel_top:.2f};w={rel_width:.2f}"
    )
    return score, reason


def _promote_section_heading_consistency(rows: list[dict]) -> None:
    heading_rows = [row for row in rows if str(row.get("role", "")) == "section_heading"]
    if not heading_rows:
        return

    heading_heights = [int(row.get("_h", 0) or 0) for row in heading_rows]
    heading_top_ratios = [float(row.get("_rel_top", 0.0) or 0.0) for row in heading_rows]
    heading_width_ratios = [float(row.get("_rel_width", 0.0) or 0.0) for row in heading_rows]
    heading_words = [int(row.get("_words", 0) or 0) for row in heading_rows]
    heading_lines = [int(row.get("_line_count", 1) or 1) for row in heading_rows]

    ref_height = max(1.0, _median([int(v) for v in heading_heights]) or 1.0)
    ref_top_min = max(0.0, min(heading_top_ratios, default=0.0) - 0.12)
    ref_top_max = min(0.9, max(heading_top_ratios, default=0.9) + 0.30)
    ref_width = max(0.05, _median_float(heading_width_ratios) or 0.05)
    ref_word_limit = max(24, int(round((_median([int(v) for v in heading_words]) or 12.0) + 8.0)))
    ref_line_limit = max(3, int(round((_median([int(v) for v in heading_lines]) or 1.0) + 1.0)))

    for row in rows:
        if str(row.get("role", "")) != "body":
            continue

        section_score = float(row.get("_section_heading_score", 0.0) or 0.0)
        if section_score < SECTION_HEADING_PROMOTION_MIN_SCORE:
            continue

        h = int(row.get("_h", 0) or 0)
        rel_top = float(row.get("_rel_top", 0.0) or 0.0)
        rel_width = float(row.get("_rel_width", 0.0) or 0.0)
        words = int(row.get("_words", 0) or 0)
        line_count = int(row.get("_line_count", 1) or 1)

        if h <= 0:
            continue
        h_ratio = float(h) / float(ref_height)
        if h_ratio < 0.82 or h_ratio > 1.55:
            continue
        if rel_top < ref_top_min or rel_top > ref_top_max:
            continue
        if line_count > ref_line_limit:
            continue
        if words > ref_word_limit:
            continue
        width_ratio = float(rel_width) / float(max(0.05, ref_width))
        if width_ratio < 0.55 or width_ratio > 1.65:
            continue

        row["role"] = "section_heading"
        row["classification_reason"] = (
            f"promoted_section_heading;"
            f"score={section_score:.2f};h_ratio={h_ratio:.2f};top={rel_top:.2f};w_ratio={width_ratio:.2f}"
        )


def _promote_graphic_embedded_neighbors(rows: list[dict], *, image_width: int, image_height: int) -> None:
    anchors = [row for row in rows if str(row.get("role", "")) == "graphic_embedded"]
    if not anchors:
        return

    for row in rows:
        role = str(row.get("role", "body") or "body")
        if role in {"graphic_embedded", "title", "subtitle", "footer", "list_item_level_1", "list_item_level_2"}:
            continue
        if role not in {"body", "section_heading", "caption"}:
            continue
        x, y, w, h = _bbox_xywh(row.get("_bbox", {}))
        words = int(row.get("_words", 0) or 0)
        rel_width = float(w) / float(max(1, image_width))
        rel_top = float(y) / float(max(1, image_height))
        if words <= 0 or words > 7:
            continue
        if rel_width > 0.26:
            continue
        if rel_top < 0.18:
            continue

        for anchor in anchors:
            ax, ay, aw, ah = _bbox_xywh(anchor.get("_bbox", {}))
            ax_center = float(ax) + float(aw) / 2.0
            x_center = float(x) + float(w) / 2.0
            center_delta_x = abs(x_center - ax_center)
            max_center_delta_x = max(36.0, float(max(w, aw)) * 0.45)
            if center_delta_x > max_center_delta_x:
                continue

            row_bottom = y + h
            anchor_bottom = ay + ah
            vertical_gap = max(0, max(ay - row_bottom, y - anchor_bottom))
            if vertical_gap > max(42, int(round(float(max(h, ah)) * 0.6))):
                continue

            previous_role = str(row.get("role", "body") or "body")
            row["role"] = "graphic_embedded"
            row["classification_reason"] = (
                "graphic_embedded_neighbor;"
                f"anchor={int(anchor.get('unit_id', 0) or 0)};"
                f"prev={previous_role};dx={center_delta_x:.1f};dy={vertical_gap}"
            )
            break


def _is_section_heading_zone_candidate(row: dict, *, image_width: int, image_height: int) -> bool:
    role = str(row.get("role", "body") or "body")
    if role in {"title", "subtitle", "footer", "graphic_embedded", "list_item_level_1", "list_item_level_2"}:
        return False
    if bool(row.get("_has_list_marker", False)):
        return False

    x, y, w, _h = _bbox_xywh(row.get("_bbox", {}))
    words = int(row.get("_words", 0) or 0)
    line_count = int(row.get("_line_count", 1) or 1)
    rel_left = float(x) / float(max(1, image_width))
    rel_top = float(y) / float(max(1, image_height))
    rel_width = float(w) / float(max(1, image_width))
    rel_center_x = (float(x) + float(w) / 2.0) / float(max(1, image_width))

    if words <= 0 or words > SECTION_HEADING_ZONE_MAX_WORDS:
        return False
    if line_count > SECTION_HEADING_ZONE_MAX_LINES:
        return False
    if rel_top > SECTION_HEADING_ZONE_MAX_TOP:
        return False
    if rel_left > SECTION_HEADING_ZONE_MAX_LEFT:
        return False
    if rel_center_x > SECTION_HEADING_ZONE_MAX_CENTER_X:
        return False
    if rel_width < SECTION_HEADING_ZONE_MIN_WIDTH or rel_width > SECTION_HEADING_ZONE_MAX_WIDTH:
        return False
    return True


def _pick_section_heading_zone_anchor(rows: list[dict], *, image_width: int, image_height: int) -> int:
    candidates: list[tuple[float, int, int, int, int, int]] = []
    for row in rows:
        if not _is_section_heading_zone_candidate(row, image_width=image_width, image_height=image_height):
            continue
        x, y, w, h = _bbox_xywh(row.get("_bbox", {}))
        rel_left = float(x) / float(max(1, image_width))
        rel_top = float(y) / float(max(1, image_height))
        section_score = float(row.get("_section_heading_score", 0.0) or 0.0)
        role_bonus = 1.2 if str(row.get("role", "body") or "body") == "section_heading" else 0.0
        score = (
            role_bonus
            + section_score * 1.15
            + (1.0 - rel_top) * 0.9
            + (1.0 - rel_left) * 0.6
            + min(1.0, float(h) / 140.0) * 0.3
        )
        candidates.append(
            (
                -score,
                int(y),
                int(x),
                -int(w),
                int(row.get("unit_id", 0) or 0),
                int(row.get("unit_id", 0) or 0),
            )
        )
    if not candidates:
        return 0
    candidates.sort()
    return int(candidates[0][-1])


def _enforce_section_heading_zone(rows: list[dict], *, image_width: int, image_height: int) -> None:
    anchor_unit_id = _pick_section_heading_zone_anchor(rows, image_width=image_width, image_height=image_height)

    for row in rows:
        unit_id = int(row.get("unit_id", 0) or 0)
        role = str(row.get("role", "body") or "body")
        if role == "section_heading" and unit_id != anchor_unit_id:
            row["role"] = "body"
            row["classification_reason"] = "forced_body_outside_section_zone"

    if anchor_unit_id <= 0:
        return

    for row in rows:
        unit_id = int(row.get("unit_id", 0) or 0)
        if unit_id != anchor_unit_id:
            continue
        previous_role = str(row.get("role", "body") or "body")
        row["role"] = "section_heading"
        row["classification_reason"] = f"forced_section_heading_zone;prev={previous_role}"
        break


def _single_event_id(rows: list[dict]) -> int:
    event_ids = {int(row.get("_event_id", 0) or 0) for row in rows if int(row.get("_event_id", 0) or 0) > 0}
    if len(event_ids) != 1:
        return 0
    return int(next(iter(event_ids)))


def _is_event1_title_candidate(row: dict, *, image_width: int, image_height: int) -> bool:
    role = str(row.get("role", "body") or "body")
    if role in {"graphic_embedded", "list_item_level_1", "list_item_level_2", "footer"}:
        return False
    if bool(row.get("_has_list_marker", False)):
        return False
    x, y, w, h = _bbox_xywh(row.get("_bbox", {}))
    words = int(row.get("_words", 0) or 0)
    lines = int(row.get("_line_count", 1) or 1)
    rel_left = float(x) / float(max(1, image_width))
    rel_top = float(y) / float(max(1, image_height))
    rel_width = float(w) / float(max(1, image_width))
    if words <= 0 or words > EVENT1_TITLE_ZONE_MAX_WORDS:
        return False
    if lines > EVENT1_TITLE_ZONE_MAX_LINES:
        return False
    if rel_top < EVENT1_TITLE_ZONE_MIN_TOP or rel_top > EVENT1_TITLE_ZONE_MAX_TOP:
        return False
    if rel_left > EVENT1_TITLE_ZONE_MAX_LEFT:
        return False
    if rel_width < EVENT1_TITLE_ZONE_MIN_WIDTH or rel_width > EVENT1_TITLE_ZONE_MAX_WIDTH:
        return False
    if h < max(24, int(round(float(image_height) * 0.028))):
        return False
    return True


def _pick_event1_title_anchor(rows: list[dict], *, image_width: int, image_height: int) -> int:
    candidates: list[tuple[float, int, int, int, int]] = []
    for row in rows:
        if not _is_event1_title_candidate(row, image_width=image_width, image_height=image_height):
            continue
        unit_id = int(row.get("unit_id", 0) or 0)
        role = str(row.get("role", "body") or "body")
        x, y, w, h = _bbox_xywh(row.get("_bbox", {}))
        rel_left = float(x) / float(max(1, image_width))
        rel_top = float(y) / float(max(1, image_height))
        role_bonus = 1.2 if role == "title" else 0.0
        section_bonus = max(0.0, float(row.get("_section_heading_score", 0.0) or 0.0) * 0.35)
        score = (
            role_bonus
            + section_bonus
            + min(1.0, float(w) / float(max(1.0, image_width * 0.52))) * 2.0
            + min(1.0, float(h) / 92.0) * 0.8
            + (1.0 - rel_left) * 0.7
            + (1.0 - abs(rel_top - 0.42)) * 0.5
        )
        candidates.append((-score, int(y), int(x), -int(w), unit_id))
    if not candidates:
        return 0
    candidates.sort()
    return int(candidates[0][-1])


def _pick_event1_subtitle_anchor(rows: list[dict], *, title_row: dict, image_width: int, image_height: int) -> int:
    tx, ty, tw, th = _bbox_xywh(title_row.get("_bbox", {}))
    title_bottom = ty + th
    candidates: list[tuple[int, int, int, int]] = []

    for row in rows:
        unit_id = int(row.get("unit_id", 0) or 0)
        if unit_id == int(title_row.get("unit_id", 0) or 0):
            continue
        role = str(row.get("role", "body") or "body")
        if role in {"graphic_embedded", "list_item_level_1", "list_item_level_2", "title", "footer"}:
            continue
        if bool(row.get("_has_list_marker", False)):
            continue
        x, y, w, h = _bbox_xywh(row.get("_bbox", {}))
        words = int(row.get("_words", 0) or 0)
        lines = int(row.get("_line_count", 1) or 1)
        rel_left = float(x) / float(max(1, image_width))
        rel_width = float(w) / float(max(1, image_width))
        if words <= 0 or words > EVENT1_SUBTITLE_ZONE_MAX_WORDS:
            continue
        if lines > EVENT1_SUBTITLE_ZONE_MAX_LINES:
            continue
        if rel_left > EVENT1_SUBTITLE_ZONE_MAX_LEFT:
            continue
        if rel_width < EVENT1_SUBTITLE_ZONE_MIN_WIDTH or rel_width > EVENT1_SUBTITLE_ZONE_MAX_WIDTH:
            continue
        if y <= title_bottom:
            continue
        vertical_gap = int(y - title_bottom)
        if vertical_gap > max(230, int(round(float(th) * 3.8))):
            continue
        x_delta = abs(x - tx)
        if x_delta > max(140, int(round(float(tw) * 0.28))):
            continue
        gap_distance = abs(vertical_gap - 54)
        candidates.append((gap_distance, x_delta, -int(w), unit_id))

    if not candidates:
        return 0
    candidates.sort()
    return int(candidates[0][-1])


def _enforce_event1_title_subtitle(rows: list[dict], *, image_width: int, image_height: int) -> None:
    if _single_event_id(rows) != 1:
        return

    title_unit_id = _pick_event1_title_anchor(rows, image_width=image_width, image_height=image_height)
    if title_unit_id <= 0:
        return
    title_row = next((row for row in rows if int(row.get("unit_id", 0) or 0) == title_unit_id), None)
    if not title_row:
        return

    subtitle_unit_id = _pick_event1_subtitle_anchor(
        rows,
        title_row=title_row,
        image_width=image_width,
        image_height=image_height,
    )

    for row in rows:
        unit_id = int(row.get("unit_id", 0) or 0)
        role = str(row.get("role", "body") or "body")
        if role not in {"title", "subtitle"}:
            continue
        if unit_id in {title_unit_id, subtitle_unit_id}:
            continue
        row["role"] = "body"
        row["classification_reason"] = "forced_body_event1_non_hero_text"

    previous_title_role = str(title_row.get("role", "body") or "body")
    title_row["role"] = "title"
    title_row["classification_reason"] = f"forced_title_event1_zone;prev={previous_title_role}"

    if subtitle_unit_id > 0:
        subtitle_row = next((row for row in rows if int(row.get("unit_id", 0) or 0) == subtitle_unit_id), None)
        if subtitle_row is not None:
            previous_subtitle_role = str(subtitle_row.get("role", "body") or "body")
            subtitle_row["role"] = "subtitle"
            subtitle_row["classification_reason"] = (
                f"forced_subtitle_event1_below_title;prev={previous_subtitle_role};title={title_unit_id}"
            )


def _remap_non_event1_title_to_section_heading(rows: list[dict]) -> None:
    # "title" is reserved for event 1 hero slide only.
    # If OCR/classification still marks a title outside event 1, map it deterministically.
    if _single_event_id(rows) == 1:
        return
    for row in rows:
        role = str(row.get("role", "body") or "body")
        if role != "title":
            continue
        previous_reason = str(row.get("classification_reason", "") or "").strip() or "title_non_event1"
        row["role"] = "section_heading"
        row["classification_reason"] = f"forced_section_heading_non_event1_title;prev={previous_reason}"


def _implicit_list_group_score(group: list[dict], row: dict, image_height: int) -> float | None:
    x, y, w, h = _bbox_xywh(row.get("_bbox", {}))
    words = int(row.get("_words", 0) or 0)
    line_count = int(row.get("_line_count", 1) or 1)
    rel_width = float(row.get("_rel_width", 0.0) or 0.0)
    rel_top = float(row.get("_rel_top", 0.0) or 0.0)
    role = str(row.get("role", "body") or "body")

    if role in {"title", "subtitle", "footer"}:
        return None
    if words <= 0 or words > 9:
        return None
    if line_count > 3:
        return None
    if rel_width > 0.55:
        return None
    if rel_top < 0.2:
        return None

    last = group[-1]
    last_x, last_y, last_w, last_h = _bbox_xywh(last.get("_bbox", {}))
    x_values = [_bbox_xywh(item.get("_bbox", {}))[0] for item in group]
    h_values = [_bbox_xywh(item.get("_bbox", {}))[3] for item in group]
    w_values = [_bbox_xywh(item.get("_bbox", {}))[2] for item in group]
    median_x = _median(x_values) or float(x)
    median_h = max(1.0, _median(h_values) or float(max(1, h)))
    median_w = max(1.0, _median(w_values) or float(max(1, w)))
    x_delta = abs(float(x) - median_x)
    top_gap = int(y - last_y)
    vertical_gap = int(y - (last_y + last_h))
    max_x_delta = max(24.0, median_h * 0.95)
    if x_delta > max_x_delta:
        return None
    if top_gap < 0:
        return None
    if vertical_gap < -max(6, int(round(min(median_h, float(h)) * 0.35))):
        return None
    if vertical_gap > max(72, int(round(max(median_h, float(h)) * 2.3))):
        return None
    width_ratio = float(w) / float(max(1.0, median_w))
    if width_ratio < 0.55 or width_ratio > 1.7:
        return None

    max_group_span = max(220, int(round(float(image_height) * 0.45)))
    group_top = min(_bbox_xywh(item.get("_bbox", {}))[1] for item in group)
    if y - group_top > max_group_span:
        return None

    return float(x_delta + max(0, vertical_gap) * 0.22 + abs(width_ratio - 1.0) * 12.0)


def _apply_implicit_list_clusters(rows: list[dict], *, image_height: int) -> None:
    candidate_rows = [
        row
        for row in sorted(rows, key=lambda item: (_bbox_xywh(item.get("_bbox", {}))[1], _bbox_xywh(item.get("_bbox", {}))[0]))
        if str(row.get("role", "body") or "body") in {"body", "section_heading", "caption"}
        and not _has_list_marker(row)
    ]
    groups: list[list[dict]] = []
    for row in candidate_rows:
        best_group: list[dict] | None = None
        best_score: float | None = None
        for group in groups:
            score = _implicit_list_group_score(group, row, image_height)
            if score is None:
                continue
            if best_score is None or score < best_score:
                best_group = group
                best_score = score
        if best_group is None:
            groups.append([row])
        else:
            best_group.append(row)

    for group in groups:
        if len(group) < IMPLICIT_LIST_MIN_CLUSTER_SIZE:
            continue
        list_candidates = 0
        for row in group:
            words = int(row.get("_words", 0) or 0)
            rel_width = float(row.get("_rel_width", 0.0) or 0.0)
            if words <= 7 and rel_width <= 0.42:
                list_candidates += 1
        if list_candidates < IMPLICIT_LIST_MIN_CLUSTER_SIZE:
            continue
        for row in group:
            previous_role = str(row.get("role", "body") or "body")
            row["role"] = "list_item_level_1"
            row["classification_reason"] = (
                "implicit_list_cluster;"
                f"size={len(group)};prev={previous_role};"
                f"score={float(row.get('_section_heading_score', 0.0) or 0.0):.2f}"
            )


def classify_text_units(text_units: list[dict], *, image_width: int, image_height: int) -> list[dict]:
    units = [dict(unit) for unit in text_units]
    non_list_heights = [
        _bbox_xywh(unit.get("bbox", {}))[3]
        for unit in units
        if not _has_list_marker(unit)
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

    classification_rows: list[dict] = []
    for unit in sorted(units, key=lambda item: (_bbox_xywh(item.get("bbox", {}))[1], _bbox_xywh(item.get("bbox", {}))[0])):
        unit_id = int(unit.get("unit_id", 0) or 0)
        x, y, w, h = _bbox_xywh(unit.get("bbox", {}))
        words = _word_count(str(unit.get("source_text", "") or ""))
        line_count = max(1, int(unit.get("line_count", 1) or 1))
        rel_top = float(y) / float(max(1, image_height))
        rel_bottom = float(y + h) / float(max(1, image_height))
        rel_width = float(w) / float(max(1, image_width))
        is_graphic_embedded, graphic_reason = _is_graphic_embedded_unit(
            unit,
            image_width=image_width,
            image_height=image_height,
        )
        section_score, section_score_reason = _section_heading_score(
            words=words,
            line_count=line_count,
            h=h,
            rel_top=rel_top,
            rel_width=rel_width,
            median_h=median_h,
            p75_h=p75_h,
        )

        reason = "fallback_body"
        if is_graphic_embedded:
            role = "graphic_embedded"
            reason = graphic_reason
        elif _has_list_marker(unit):
            role = "list_item_level_1"
            reason = "list_marker" if int(unit.get("list_marker_fragment_id", 0) or 0) > 0 else "list_marker_inferred"
        elif unit_id == title_unit_id:
            role = "title"
            reason = "top_largest_text"
        elif unit_id == subtitle_unit_id:
            role = "subtitle"
            reason = "below_title_large_text"
        elif rel_bottom >= 0.96 and float(h) <= max(p75_h * 1.1, median_h * 1.25):
            role = "footer"
            reason = "bottom_small_text"
        elif section_score >= SECTION_HEADING_SCORE_THRESHOLD:
            role = "section_heading"
            reason = f"section_heading_score;{section_score_reason}"
        elif rel_top >= 0.66 and rel_width <= 0.48 and float(h) <= max(p75_h * 1.1, median_h * 1.2):
            role = "caption"
            reason = "small_lower_text"
        else:
            role = "body"
            reason = f"fallback_body;section_heading_score={section_score:.2f}"

        classification_rows.append(
            {
                "unit_id": unit_id,
                "role": role,
                "classification_reason": reason,
                "_bbox": dict(unit.get("bbox", {})),
                "_event_id": int(unit.get("event_id", 0) or 0),
                "_has_list_marker": _has_list_marker(unit),
                "_section_heading_score": section_score,
                "_h": h,
                "_rel_top": rel_top,
                "_rel_width": rel_width,
                "_words": words,
                "_line_count": line_count,
            }
        )

    _promote_section_heading_consistency(classification_rows)
    _promote_graphic_embedded_neighbors(
        classification_rows,
        image_width=image_width,
        image_height=image_height,
    )
    _apply_implicit_list_clusters(classification_rows, image_height=image_height)
    _enforce_section_heading_zone(
        classification_rows,
        image_width=image_width,
        image_height=image_height,
    )
    _enforce_event1_title_subtitle(
        classification_rows,
        image_width=image_width,
        image_height=image_height,
    )
    _remap_non_event1_title_to_section_heading(classification_rows)

    out: list[dict] = []
    for row in classification_rows:
        role = str(row.get("role", "body") or "body")
        slot_id, vertical_zone, horizontal_zone = _slot_id(
            role,
            dict(row.get("_bbox", {})),
            image_width,
            image_height,
        )
        out.append(
            {
                "unit_id": int(row.get("unit_id", 0) or 0),
                "role": role,
                "slot_id": slot_id,
                "slot_vertical_zone": vertical_zone,
                "slot_horizontal_zone": horizontal_zone,
                "classification_reason": str(row.get("classification_reason", "fallback_body") or "fallback_body"),
            }
        )
    return out
