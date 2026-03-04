from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Iterable, Sequence

from scripts.lib.slide_text_normalization import normalize_slide_text

EVENT_ID_RE = re.compile(r"(?:^|_)event_(\d+)(?:_|$)")


def parse_event_id_from_name(name: str) -> int | None:
    match = EVENT_ID_RE.search(str(name or ""))
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:  # noqa: BLE001
        return None


def load_slide_events(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(raw_events, list):
        raise RuntimeError("Slide map JSON must contain an 'events' array.")

    events: list[dict] = []
    slide_index = 0
    for raw in raw_events:
        if not isinstance(raw, dict):
            continue
        try:
            event_id = int(raw.get("event_id", 0) or 0)
        except Exception:  # noqa: BLE001
            continue
        if event_id <= 0:
            continue
        slide_index += 1
        events.append(
            {
                "slide_index": int(raw.get("slide_index", slide_index) or slide_index),
                "event_id": event_id,
                "bucket_id": str(raw.get("bucket_id", f"event_{event_id:03d}") or f"event_{event_id:03d}"),
                "slide_start": float(raw.get("slide_start", 0.0) or 0.0),
                "slide_end": float(raw.get("slide_end", 0.0) or 0.0),
                "text": str(raw.get("text", "") or "").strip(),
            }
        )
    return events


def event_metadata_by_id(events: Iterable[dict]) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for row in events:
        try:
            event_id = int(row.get("event_id", 0) or 0)
        except Exception:  # noqa: BLE001
            continue
        if event_id > 0:
            out[event_id] = dict(row)
    return out


def is_translatable_text(text: str) -> bool:
    normalized = normalize_slide_text(text)
    if not normalized:
        return False
    return any(ch.isalnum() for ch in normalized)


def build_exact_termbase_lookup(entries: Iterable) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for entry in entries:
        source_text = normalize_slide_text(getattr(entry, "source_text", ""))
        target_text = str(getattr(entry, "target_text", "") or "").strip()
        if source_text and target_text and source_text not in lookup:
            lookup[source_text] = target_text
    return lookup


def chunked(items: Sequence[str], size: int) -> list[list[str]]:
    chunk_size = max(1, int(size))
    return [list(items[i : i + chunk_size]) for i in range(0, len(items), chunk_size)]


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            serialized: dict[str, object] = {}
            for key in fieldnames:
                value = row.get(key, "")
                if isinstance(value, (dict, list)):
                    serialized[key] = json.dumps(value, ensure_ascii=False)
                else:
                    serialized[key] = value
            writer.writerow(serialized)
