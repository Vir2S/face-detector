import secrets

from pathlib import Path
from fastapi import UploadFile

from server.config import UPLOAD_DIR, PUBLIC_BASE_URL


async def save_upload(file: UploadFile) -> str:
    """
    Save an uploaded file to disk and return a public URL.
    NOTE: The public URL must be reachable by BytePlus (no localhost).
    """
    ext = Path(file.filename or "").suffix or ".png"
    name = f"{secrets.token_hex(16)}{ext}"
    path = UPLOAD_DIR / name

    data = await file.read()
    path.write_bytes(data)

    return f"{PUBLIC_BASE_URL}/files/{name}"
