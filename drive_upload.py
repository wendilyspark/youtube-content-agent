"""
Google Drive Uploader
Uploads a project folder's images + audio to a new Google Drive folder
and returns a shareable link.
"""

import os
import mimetypes
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import GOOGLE_SERVICE_ACCOUNT_FILE


def _get_drive_service():
    scopes = ["https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=scopes)
    return build("drive", "v3", credentials=creds)


def upload_project_to_drive(project_dir: str, parent_folder_id: str = None, folder_name: str = None) -> str:
    """
    Upload all images + audio from a project directory into a Google Drive folder.
    If parent_folder_id is given, uploads directly into that folder (user's Drive).
    Otherwise creates a new top-level folder (requires service account quota).
    Returns the folder URL.
    """
    project_path = Path(project_dir)
    if not folder_name:
        folder_name = project_path.name

    service = _get_drive_service()

    if parent_folder_id:
        # Upload into the user-owned folder directly
        folder_id = parent_folder_id
        print(f"Uploading into existing Drive folder: {folder_id}")
    else:
        # 1. Create a new folder
        print(f"Creating Drive folder: '{folder_name}'...")
        folder_meta = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = service.files().create(body=folder_meta, fields="id").execute()
        folder_id = folder["id"]

        # 2. Make it shareable by anyone with the link
        service.permissions().create(
            fileId=folder_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()

    # 3. Collect files to upload: images then audio (skip timestamps JSON)
    files_to_upload = []
    images_dir = project_path / "images"
    audio_dir  = project_path / "audio"

    if images_dir.exists():
        for f in sorted(images_dir.glob("*.jpg")):
            files_to_upload.append(f)

    if audio_dir.exists():
        for f in sorted(audio_dir.glob("*.mp3")):
            files_to_upload.append(f)

    # 4. Upload each file
    print(f"Uploading {len(files_to_upload)} files...")
    for fpath in files_to_upload:
        mime_type = mimetypes.guess_type(str(fpath))[0] or "application/octet-stream"
        file_meta = {"name": fpath.name, "parents": [folder_id]}
        media = MediaFileUpload(str(fpath), mimetype=mime_type, resumable=True)
        service.files().create(body=file_meta, media_body=media, fields="id").execute()
        print(f"  Uploaded: {fpath.name}")

    folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
    print(f"\nDone! Folder link: {folder_url}")
    return folder_url


if __name__ == "__main__":
    import sys
    project_dir = sys.argv[1] if len(sys.argv) > 1 else None
    folder_name = sys.argv[2] if len(sys.argv) > 2 else None

    if not project_dir:
        print("Usage: python drive_upload.py <project_dir> [folder_name]")
        sys.exit(1)

    url = upload_project_to_drive(project_dir, folder_name)
    print(f"\nOpen in browser: {url}")
