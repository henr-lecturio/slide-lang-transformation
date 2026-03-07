#!/usr/bin/env python3
"""Upload a run's output directory to Google Drive."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root so we can import web.gdrive_auth
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Upload run output files to Google Drive.")
    p.add_argument("--run-dir", required=True, help="Path to the run output directory.")
    p.add_argument("--folder-id", required=True, help="Google Drive folder ID.")
    p.add_argument(
        "--subfolder-name",
        default="",
        help="Subfolder name inside the Drive folder (defaults to run dir name).",
    )
    return p.parse_args()


# Cache for created / looked-up sub-folders  {parent_id/name -> id}
_folder_cache: dict[str, str] = {}


def _ensure_subfolder(service, parent_id: str, name: str) -> str:
    """Return the ID of *name* inside *parent_id*, creating it if needed."""
    cache_key = f"{parent_id}/{name}"
    if cache_key in _folder_cache:
        return _folder_cache[cache_key]

    query = (
        f"'{parent_id}' in parents "
        f"and name='{name}' "
        f"and mimeType='application/vnd.google-apps.folder' "
        f"and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])

    if files:
        folder_id = files[0]["id"]
    else:
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = service.files().create(body=metadata, fields="id").execute()
        folder_id = folder["id"]

    _folder_cache[cache_key] = folder_id
    return folder_id


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir)

    if not run_dir.is_dir():
        print(f"ERROR: run dir does not exist: {run_dir}", file=sys.stderr)
        sys.exit(1)

    from web.gdrive_auth import get_valid_credentials

    creds = get_valid_credentials()
    if creds is None:
        print(
            "ERROR: No valid Google Drive credentials. "
            "Authenticate first via the web UI.",
            file=sys.stderr,
        )
        sys.exit(1)

    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    service = build("drive", "v3", credentials=creds)

    # Collect all files first for count
    all_files = sorted(f for f in run_dir.rglob("*") if f.is_file())
    total = len(all_files)

    # Create top-level subfolder for this run
    subfolder_name = args.subfolder_name or run_dir.name
    print(f"@@STEP DETAIL backup google drive upload: creating folder '{subfolder_name}'", flush=True)
    subfolder_meta = {
        "name": subfolder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [args.folder_id],
    }
    subfolder = service.files().create(body=subfolder_meta, fields="id").execute()
    subfolder_id = subfolder["id"]

    # Upload all files recursively
    uploaded = 0
    for file_path in all_files:
        relative = file_path.relative_to(run_dir)
        uploaded += 1
        print(f"@@STEP DETAIL backup google drive upload: {relative} ({uploaded}/{total})", flush=True)

        # Ensure intermediate directories exist in Drive
        parent_id = subfolder_id
        for part in relative.parts[:-1]:
            parent_id = _ensure_subfolder(service, parent_id, part)

        media = MediaFileUpload(str(file_path), resumable=True)
        file_metadata = {"name": file_path.name, "parents": [parent_id]}
        service.files().create(
            body=file_metadata, media_body=media, fields="id"
        ).execute()

    print(f"@@STEP DETAIL backup google drive upload: done ({uploaded} files)", flush=True)


if __name__ == "__main__":
    main()
