#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.lib.translation_memory import (
    DEFAULT_TM_DB_PATH,
    init_translation_memory,
    iter_translatable_segments,
    split_translation_units,
    upsert_tm_entry,
)
DEFAULT_RUNS_DIR = ROOT_DIR / "output" / "runs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap the translation memory from existing translated run outputs.")
    parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR), help="Directory containing run folders.")
    parser.add_argument("--tm-db", default=str(DEFAULT_TM_DB_PATH), help="SQLite translation memory path.")
    return parser.parse_args()


def load_events(path: Path) -> tuple[str, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    target_language = str(payload.get("text_translation", {}).get("target_language", "") or "").strip()
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        return target_language, []
    return target_language, [event for event in events if isinstance(event, dict)]


def segment_pairs(source_text: str, target_text: str) -> list[tuple[str, str]]:
    source_segments = iter_translatable_segments(split_translation_units(source_text))
    target_segments = iter_translatable_segments(split_translation_units(target_text))
    if source_segments and len(source_segments) == len(target_segments):
        return list(zip(source_segments, target_segments))
    if source_text.strip() and target_text.strip():
        return [(source_text.strip(), target_text.strip())]
    return []


def main() -> int:
    args = parse_args()
    runs_dir = Path(args.runs_dir).resolve()
    tm_db = Path(args.tm_db).resolve()
    conn = init_translation_memory(tm_db)

    files = sorted(runs_dir.glob("*/slitranet/slide_text_map_final_translated.json"))
    run_count = 0
    pair_count = 0
    for path in files:
        run_id = path.parents[1].name
        target_language, events = load_events(path)
        if not target_language:
            continue
        run_count += 1
        inserted_this_run = 0
        for event in events:
            source_text = str(event.get("text", "") or "")
            target_text = str(event.get("translated_text", "") or "")
            for source_segment, target_segment in segment_pairs(source_text, target_text):
                upsert_tm_entry(
                    conn,
                    source_text=source_segment,
                    target_language=target_language,
                    target_text=target_segment,
                    status="bootstrap",
                    origin_run_id=run_id,
                )
                pair_count += 1
                inserted_this_run += 1
        print(f"[TM] Bootstrapped run {run_id}: {inserted_this_run} segment pairs", flush=True)

    conn.close()
    print(f"[TM] Runs processed: {run_count}", flush=True)
    print(f"[TM] Segment pairs stored: {pair_count}", flush=True)
    print(f"[TM] Database: {tm_db}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
