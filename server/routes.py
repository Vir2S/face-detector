import hashlib
import logging
from dataclasses import asdict

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse

from services.minor_guard.factory import get_minor_guard, assert_no_minors


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["face_detector"])


def _minor_guard_payload(result) -> dict:
    d = asdict(result)
    # Keep payload small and safe
    d["reasons"] = (d.get("reasons") or [])[:5]
    return d


@router.post("/check_image")
async def upload_image(file: UploadFile = File(...)):
    """
    Upload endpoint.
    - Reads bytes (in memory)
    - Runs minor-guard BEFORE any storage/processing
    - Logs sha256 prefix to correlate retries without storing the image
    """
    image_bytes = await file.read()

    # Hash prefix helps correlate retries without storing the image
    sha12 = hashlib.sha256(image_bytes).hexdigest()[:12]
    logger.info(
        "upload received filename=%s content_type=%s size_bytes=%s sha12=%s",
        file.filename,
        file.content_type,
        len(image_bytes),
        sha12,
    )

    guard = get_minor_guard()

    # This returns MinorCheckResult on success and raises domain exceptions on block.
    # Those exceptions are handled globally in server/main.py.
    result = await assert_no_minors(guard, image_bytes, content_type=file.content_type)

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "minor_guard": _minor_guard_payload(result),
        },
    )
