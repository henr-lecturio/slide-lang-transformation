from __future__ import annotations

import csv
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TERMBASE_PATH = ROOT_DIR / "config" / "translation_termbase.csv"
DEFAULT_TM_DB_PATH = ROOT_DIR / "output" / "translation_memory" / "translation_memory.sqlite"
TM_SCHEMA = """
CREATE TABLE IF NOT EXISTS tm_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_text TEXT NOT NULL,
  source_text_norm TEXT NOT NULL,
  target_language TEXT NOT NULL,
  target_text TEXT NOT NULL,
  source_lang TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'machine_unreviewed',
  origin_run_id TEXT NOT NULL DEFAULT '',
  hit_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_text_norm, target_language)
);
CREATE INDEX IF NOT EXISTS idx_tm_entries_lang_norm
ON tm_entries(target_language, source_text_norm);
"""


@dataclass(frozen=True)
class TermbaseEntry:
    source_text: str
    target_language: str
    target_text: str
    case_sensitive: bool = False


def normalize_tm_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _boolish(value: str | bool | int | None) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _compile_term_pattern(term: str, case_sensitive: bool) -> re.Pattern[str]:
    escaped = re.escape(term)
    prefix = r"(?<!\w)" if term[:1].isalnum() else ""
    suffix = r"(?!\w)" if term[-1:].isalnum() else ""
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(f"{prefix}{escaped}{suffix}", flags)


def load_termbase_entries(path: Path | str = DEFAULT_TERMBASE_PATH, target_language: str = "") -> list[TermbaseEntry]:
    termbase_path = Path(path)
    if not termbase_path.exists():
        return []

    target = str(target_language or "").strip()
    entries: list[TermbaseEntry] = []
    with termbase_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source_text = str(row.get("source_text", "") or "").strip()
            row_target_language = str(row.get("target_language", "") or "").strip()
            target_text = str(row.get("target_text", "") or "").strip()
            if not source_text or not target_text:
                continue
            if target and row_target_language and row_target_language not in {target, "*"}:
                continue
            entries.append(
                TermbaseEntry(
                    source_text=source_text,
                    target_language=row_target_language or target,
                    target_text=target_text,
                    case_sensitive=_boolish(row.get("case_sensitive", "0")),
                )
            )
    entries.sort(key=lambda item: len(item.source_text), reverse=True)
    return entries


def append_glossary_to_prompt(prompt: str, entries: Iterable[TermbaseEntry]) -> str:
    glossary_entries = list(entries)
    if not glossary_entries:
        return prompt
    lines = [
        str(prompt or "").strip(),
        "",
        "Glossary terms. Use these target forms consistently for visible terms:",
    ]
    for entry in glossary_entries:
        lines.append(f"- {entry.source_text} -> {entry.target_text}")
    return "\n".join(line for line in lines if line is not None).strip()


def apply_termbase_placeholders(text: str, entries: Iterable[TermbaseEntry]) -> tuple[str, dict[str, str], list[dict[str, str]]]:
    working = str(text or "")
    placeholder_map: dict[str, str] = {}
    hits: list[dict[str, str]] = []
    placeholder_index = 0

    for entry in entries:
        pattern = _compile_term_pattern(entry.source_text, entry.case_sensitive)

        def replace(match: re.Match[str]) -> str:
            nonlocal placeholder_index
            placeholder_index += 1
            placeholder = f"__TERM_{placeholder_index:04d}__"
            placeholder_map[placeholder] = entry.target_text
            hits.append(
                {
                    "source_text": match.group(0),
                    "target_text": entry.target_text,
                    "placeholder": placeholder,
                }
            )
            return placeholder

        working = pattern.sub(replace, working)

    return working, placeholder_map, hits


def restore_termbase_placeholders(text: str, placeholder_map: dict[str, str]) -> str:
    restored = str(text or "")
    missing = [placeholder for placeholder in placeholder_map if placeholder not in restored]
    if missing:
        raise RuntimeError(
            "Model output changed or removed protected term placeholders: "
            + ", ".join(missing[:5])
        )
    for placeholder, replacement in placeholder_map.items():
        restored = restored.replace(placeholder, replacement)
    return restored


def split_translation_units(text: str) -> list[dict[str, str]]:
    raw_parts = re.split(r"(\n+|(?<=[.!?])\s+)", str(text or ""))
    units: list[dict[str, str]] = []
    for part in raw_parts:
        if not part:
            continue
        if part.isspace():
            units.append({"type": "separator", "text": part})
        else:
            units.append({"type": "segment", "text": part})
    return units


def iter_translatable_segments(units: Iterable[dict[str, str]]) -> list[str]:
    return [unit["text"] for unit in units if unit.get("type") == "segment" and str(unit.get("text", "")).strip()]


def init_translation_memory(path: Path | str = DEFAULT_TM_DB_PATH) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(TM_SCHEMA)
    conn.commit()
    return conn


def lookup_tm_exact(conn: sqlite3.Connection, source_text: str, target_language: str) -> dict | None:
    normalized = normalize_tm_text(source_text)
    if not normalized or not str(target_language or "").strip():
        return None
    row = conn.execute(
        "SELECT id, source_text, target_text, target_language, source_lang, status, origin_run_id, hit_count "
        "FROM tm_entries WHERE source_text_norm = ? AND target_language = ?",
        (normalized, str(target_language).strip()),
    ).fetchone()
    if row is None:
        return None
    conn.execute(
        "UPDATE tm_entries SET hit_count = hit_count + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (row["id"],),
    )
    conn.commit()
    return dict(row)


def upsert_tm_entry(
    conn: sqlite3.Connection,
    *,
    source_text: str,
    target_language: str,
    target_text: str,
    source_lang: str = "",
    status: str = "machine_unreviewed",
    origin_run_id: str = "",
) -> None:
    normalized = normalize_tm_text(source_text)
    if not normalized or not str(target_language or "").strip() or not str(target_text or "").strip():
        return
    conn.execute(
        """
        INSERT INTO tm_entries (
          source_text,
          source_text_norm,
          target_language,
          target_text,
          source_lang,
          status,
          origin_run_id,
          hit_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        ON CONFLICT(source_text_norm, target_language) DO UPDATE SET
          source_text = excluded.source_text,
          target_text = excluded.target_text,
          source_lang = excluded.source_lang,
          status = excluded.status,
          origin_run_id = CASE WHEN excluded.origin_run_id != '' THEN excluded.origin_run_id ELSE tm_entries.origin_run_id END,
          updated_at = CURRENT_TIMESTAMP
        """,
        (
            str(source_text),
            normalized,
            str(target_language).strip(),
            str(target_text).strip(),
            str(source_lang or "").strip(),
            str(status or "machine_unreviewed").strip(),
            str(origin_run_id or "").strip(),
        ),
    )
    conn.commit()
