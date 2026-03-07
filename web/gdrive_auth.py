"""Google Drive OAuth helper – separate token from ADC (cloud-platform)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN_PATH = Path(__file__).resolve().parent.parent / "output" / "gdrive_token.json"


def get_valid_credentials() -> Credentials:
    """Load Drive-specific credentials and refresh if needed."""
    if not TOKEN_PATH.exists():
        raise RuntimeError("No Google Drive credentials found. Authenticate via Settings → Backup.")
    data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    creds = Credentials(
        token=None,
        refresh_token=data["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def get_auth_status() -> dict:
    """Return ``{authenticated: bool, email: str}``."""
    if not TOKEN_PATH.exists():
        return {"authenticated": False, "email": ""}
    try:
        creds = get_valid_credentials()
        email = _get_user_email(creds)
        return {"authenticated": True, "email": email or "Authenticated"}
    except Exception:
        return {"authenticated": False, "email": ""}


def save_credentials(client_id: str, client_secret: str, refresh_token: str) -> None:
    """Persist Drive OAuth token to disk."""
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_oauth_client_credentials() -> tuple[str, str]:
    """Read GCLOUD_OAUTH_CLIENT_ID / SECRET from env or .env.local."""
    root = Path(__file__).resolve().parent.parent
    local_env_path = root / ".env.local"
    local_env: dict[str, str] = {}
    if local_env_path.exists():
        for line in local_env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            local_env[k.strip()] = v.strip().strip('"').strip("'")
    client_id = local_env.get("GCLOUD_OAUTH_CLIENT_ID", "") or os.environ.get("GCLOUD_OAUTH_CLIENT_ID", "")
    client_secret = local_env.get("GCLOUD_OAUTH_CLIENT_SECRET", "") or os.environ.get("GCLOUD_OAUTH_CLIENT_SECRET", "")
    return client_id, client_secret


def _get_user_email(creds: Credentials) -> str:
    try:
        from googleapiclient.discovery import build
        service = build("oauth2", "v2", credentials=creds)
        user_info = service.userinfo().get().execute()
        return user_info.get("email", "")
    except Exception:
        return ""
