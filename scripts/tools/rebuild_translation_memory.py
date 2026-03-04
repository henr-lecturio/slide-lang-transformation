#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.lib.translation_memory import DEFAULT_TM_DB_PATH, init_translation_memory, upsert_tm_entry
DEFAULT_RUNS_DIR = ROOT_DIR / "output" / "runs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap the translation memory from existing translated run outputs.")
    parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR), help="Directory containing run folders.")
    parser.add_argument("--tm-db", default=str(DEFAULT_TM_DB_PATH), help="SQLite translation memory path.")
    return parser.parse_args()


def load_segments(path: Path) -> tuple[str, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    target_language = str(payload.get("target_language", "") or "").strip()
    segments = payload.get("segments") if isinstance(payload, dict) else None
    if not isinstance(segments, list):
        return target_language, []
    return target_language, [segment for segment in segments if isinstance(segment, dict)]


def main() -> int:
    args = parse_args()
    runs_dir = Path(args.runs_dir).resolve()
    tm_db = Path(args.tm_db).resolve()
    conn = init_translation_memory(tm_db)

    files = sorted(runs_dir.glob("*/slitranet/transcript_segments_translated.json"))
    run_count = 0
    pair_count = 0
    for path in files:
        run_id = path.parents[1].name
        target_language, segments = load_segments(path)
        if not target_language:
            continue
        run_count += 1
        inserted_this_run = 0
        for segment in segments:
            source_text = str(segment.get("text", "") or "").strip()
            target_text = str(segment.get("translated_text", "") or "").strip()
            if not source_text or not target_text:
                continue
            upsert_tm_entry(
                conn,
                source_text=source_text,
                target_language=target_language,
                target_text=target_text,
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
