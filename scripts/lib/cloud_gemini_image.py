from __future__ import annotations

import os

DEFAULT_GEMINI_LOCATION = "global"
CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


def _first_non_empty(*values: str) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def resolve_gemini_project_id(project_id: str = "") -> str:
    return _first_non_empty(
        project_id,
        os.environ.get("GCLOUD_VERTEX_PROJECTID", ""),
        os.environ.get("GOOGLE_GEMINI_PROJECT_ID", ""),
        os.environ.get("GCLOUD_VISION_PROJECTID", ""),
        os.environ.get("GOOGLE_VISION_PROJECT_ID", ""),
        os.environ.get("GCLOUD_TRANSLATE_PROJECTID", ""),
        os.environ.get("GOOGLE_TRANSLATE_PROJECT_ID", ""),
        os.environ.get("GCLOUD_TTS_PROJECTID", ""),
        os.environ.get("GOOGLE_TTS_PROJECT_ID", ""),
        os.environ.get("GOOGLE_SPEECH_PROJECT_ID", ""),
        os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
    )


def resolve_gemini_location(location: str = "") -> str:
    return _first_non_empty(
        location,
        os.environ.get("GOOGLE_GEMINI_LOCATION", ""),
        os.environ.get("GOOGLE_TRANSLATE_LOCATION", ""),
        DEFAULT_GEMINI_LOCATION,
    )


def ensure_cloud_gemini_image_client(project_id: str = "", location: str = ""):
    try:
        import google.auth
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-genai is not installed in this environment. "
            "Run: source .venv/bin/activate && pip install google-genai"
        ) from exc

    resolved_project_id = resolve_gemini_project_id(project_id)
    if not resolved_project_id:
        raise RuntimeError("GCLOUD_VERTEX_PROJECTID / --project-id must not be empty.")
    resolved_location = resolve_gemini_location(location)
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", resolved_project_id)

    credentials, default_project = google.auth.default(
        scopes=[CLOUD_PLATFORM_SCOPE],
        quota_project_id=resolved_project_id,
    )
    client = genai.Client(
        vertexai=True,
        credentials=credentials,
        project=resolved_project_id,
        location=resolved_location,
    )
    return client, types, resolved_project_id, default_project, resolved_location
