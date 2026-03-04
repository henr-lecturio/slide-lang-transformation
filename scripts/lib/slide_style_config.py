from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULT_SLIDE_TRANSLATE_STYLE_CONFIG_REL = "config/slide_translate_styles.json"


def default_style_config_path(root_dir: Path) -> Path:
    return (root_dir / DEFAULT_SLIDE_TRANSLATE_STYLE_CONFIG_REL).resolve()


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def load_style_config(path: Path, *, fallback_font_path: Path | None = None) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Style config must be a JSON object.")

    defaults = payload.get("defaults", {})
    roles = payload.get("roles", {})
    slots = payload.get("slots", {})
    if not isinstance(defaults, dict):
        raise RuntimeError("Style config key 'defaults' must be an object.")
    if not isinstance(roles, dict):
        raise RuntimeError("Style config key 'roles' must be an object.")
    if not isinstance(slots, dict):
        raise RuntimeError("Style config key 'slots' must be an object.")

    normalized_defaults = dict(defaults)
    if fallback_font_path is not None and not str(normalized_defaults.get("font_path", "") or "").strip():
        normalized_defaults["font_path"] = str(fallback_font_path)

    return {
        "version": int(payload.get("version", 1) or 1),
        "path": str(path),
        "defaults": normalized_defaults,
        "roles": {str(key): value for key, value in roles.items() if isinstance(value, dict)},
        "slots": {str(key): value for key, value in slots.items() if isinstance(value, dict)},
    }


def merged_style(config: dict, *, role: str, slot_id: str) -> dict:
    style = dict(config.get("defaults", {}))
    role_style = config.get("roles", {}).get(str(role), {})
    if isinstance(role_style, dict):
        style = _deep_merge(style, role_style)
    slot_style = config.get("slots", {}).get(str(slot_id), {})
    if isinstance(slot_style, dict):
        style = _deep_merge(style, slot_style)
    return style


def resolve_style_font_path(
    style: dict,
    *,
    root_dir: Path,
    config_path: Path,
    fallback_font_path: Path,
) -> Path:
    raw = str(style.get("font_path", "") or fallback_font_path).strip()
    if not raw:
        return fallback_font_path.resolve()
    path = Path(raw)
    if path.is_absolute():
        resolved = path.resolve()
    else:
        root_candidate = (root_dir / path).resolve()
        if root_candidate.exists():
            resolved = root_candidate
        else:
            resolved = (config_path.parent / path).resolve()

    weight = str(style.get("font_weight", "") or "").strip().lower()
    if weight not in {"regular", "medium", "bold"}:
        return resolved

    stem = resolved.stem
    suffix = resolved.suffix
    target = {"regular": "Regular", "medium": "Medium", "bold": "Bold"}[weight]
    replaced = re.sub(r"(?i)(regular|medium|bold)", target, stem)
    candidates: list[Path] = []
    if replaced != stem:
        candidates.append(resolved.with_name(f"{replaced}{suffix}"))
    for sep in ("-", "_", " "):
        candidates.append(resolved.with_name(f"{stem}{sep}{target}{suffix}"))

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return resolved
