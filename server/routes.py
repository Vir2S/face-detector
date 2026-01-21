import hashlib
import logging

from fastapi import APIRouter, UploadFile, File

from server.handlers.minor_guard import minor_guard_payload
from server.handlers.response import api_response

from services.minor_guard.factory import get_minor_guard, assert_no_minors


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["face_detector"])


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

    return api_response(
        ok=True,
        status_code=200,
        data={
            "filename": file.filename,
            "content_type": file.content_type,
            "size_bytes": len(image_bytes),
            "sha12": sha12,
        },
        minor_guard=minor_guard_payload(result),
    )
