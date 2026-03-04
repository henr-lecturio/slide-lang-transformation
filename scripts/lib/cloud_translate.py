from __future__ import annotations

import json
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
LANGUAGE_OPTIONS_PATH = ROOT_DIR / "config" / "language" / "gemini_tts_languages.json"

SPECIAL_TRANSLATE_CODES = {
    "cmn-CN": "zh-CN",
    "cmn-tw": "zh-TW",
}


def derive_translate_language_code(tts_language_code: str) -> str:
    code = str(tts_language_code or "").strip()
    if not code:
        return ""
    if code in SPECIAL_TRANSLATE_CODES:
        return SPECIAL_TRANSLATE_CODES[code]
    primary = code.split("-", 1)[0].strip().lower()
    return primary


def load_language_option_maps(path: Path = LANGUAGE_OPTIONS_PATH) -> tuple[dict[str, dict], dict[str, dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_label: dict[str, dict] = {}
    by_tts_code: dict[str, dict] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "") or "").strip()
        tts_language_code = str(item.get("tts_language_code", "") or "").strip()
        if not label or not tts_language_code:
            continue
        option = {
            "label": label,
            "tts_language_code": tts_language_code,
            "translate_language_code": str(item.get("translate_language_code", "") or "").strip()
            or derive_translate_language_code(tts_language_code),
            "launch_readiness": str(item.get("launch_readiness", "") or "").strip(),
        }
        by_label[label] = option
        by_tts_code[tts_language_code] = option
    return by_label, by_tts_code


def resolve_target_language_codes(target_language_label: str) -> tuple[str, str]:
    by_label, _by_tts_code = load_language_option_maps()
    option = by_label.get(str(target_language_label or "").strip())
    if not option:
        raise RuntimeError(f"Unknown target language label: {target_language_label}")
    return option["translate_language_code"], option["tts_language_code"]


def ensure_cloud_translate_client(project_id: str, location: str):
    try:
        import google.auth
        from google.cloud import translate_v3
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-cloud-translate is not installed in this environment. "
            "Run: source .venv/bin/activate && pip install google-cloud-translate"
        ) from exc

    quota_project_id = project_id.strip() or (os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip()
    if not quota_project_id:
        raise RuntimeError("GOOGLE_TRANSLATE_PROJECT_ID / --project-id must not be empty.")
    location = str(location or "").strip() or "us-central1"
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", quota_project_id)

    credentials, default_project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
        quota_project_id=quota_project_id,
    )
    client = translate_v3.TranslationServiceClient(credentials=credentials)
    return client, translate_v3, quota_project_id, default_project, location


def build_translation_model_path(project_id: str, location: str, model: str) -> str:
    model_id = str(model or "").strip() or "general/translation-llm"
    if model_id.startswith("projects/"):
        return model_id
    return f"projects/{project_id}/locations/{location}/models/{model_id}"


def translate_texts_llm(
    client,
    *,
    project_id: str,
    location: str,
    model: str,
    contents: list[str],
    target_language_code: str,
    source_language_code: str = "",
) -> list[str]:
    try:
        response = client.translate_text(
            request={
                "parent": f"projects/{project_id}/locations/{location}",
                "model": build_translation_model_path(project_id, location, model),
                "contents": [str(item) for item in contents],
                "mime_type": "text/plain",
                "target_language_code": str(target_language_code or "").strip(),
                **(
                    {"source_language_code": str(source_language_code).strip()}
                    if str(source_language_code or "").strip()
                    else {}
                ),
            }
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(str(exc)) from exc

    out: list[str] = []
    for translation in getattr(response, "translations", []) or []:
        translated_text = str(getattr(translation, "translated_text", "") or "").strip()
        if not translated_text:
            raise RuntimeError("Cloud Translation response contained an empty translated_text entry.")
        out.append(translated_text)
    return out
