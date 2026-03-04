from __future__ import annotations

import os


def ensure_cloud_vision_client(project_id: str):
    try:
        import google.auth
        from google.cloud import vision
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-cloud-vision is not installed in this environment. "
            "Run: source .venv/bin/activate && pip install google-cloud-vision"
        ) from exc

    quota_project_id = project_id.strip() or (os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip()
    if not quota_project_id:
        raise RuntimeError("GOOGLE_VISION_PROJECT_ID / --project-id must not be empty.")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", quota_project_id)

    credentials, default_project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
        quota_project_id=quota_project_id,
    )
    client = vision.ImageAnnotatorClient(credentials=credentials)
    return client, vision, quota_project_id, default_project


def detect_image_text_bytes(client, vision, image_bytes: bytes, feature: str = "DOCUMENT_TEXT_DETECTION") -> str:
    image = vision.Image(content=image_bytes)
    normalized_feature = str(feature or "DOCUMENT_TEXT_DETECTION").strip().upper()

    if normalized_feature == "DOCUMENT_TEXT_DETECTION":
        response = client.document_text_detection(image=image)
        if response.error.message:
            raise RuntimeError(response.error.message)
        return str(getattr(getattr(response, "full_text_annotation", None), "text", "") or "").strip()

    if normalized_feature == "TEXT_DETECTION":
        response = client.text_detection(image=image)
        if response.error.message:
            raise RuntimeError(response.error.message)
        annotations = getattr(response, "text_annotations", None) or []
        if not annotations:
            return ""
        return str(getattr(annotations[0], "description", "") or "").strip()

    raise ValueError("GOOGLE_VISION_FEATURE must be DOCUMENT_TEXT_DETECTION or TEXT_DETECTION")
