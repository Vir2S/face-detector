import hashlib
import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from server.config import MINOR_GUARD_FAIL_CLOSED, MINOR_GUARD_PROVIDER
from services.minor_guard.factory import get_minor_guard, assert_no_minors
from services.minor_guard.exceptions import MinorCheckUnavailableError, MinorDetectedError, MinorGuardProviderError


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

    guard = get_minor_guard()

    try:
        result = await guard.check(image_bytes=image_bytes, content_type=file.content_type)

    except MinorGuardProviderError as e:
        # Provider failure: fail-closed => block; fail-open => allow but report error
        if MINOR_GUARD_FAIL_CLOSED:
            return JSONResponse(
                status_code=503,
                content={
                    "ok": False,
                    "error": "AGE_CHECK_UNAVAILABLE",
                    "message": "Upload blocked: age-check temporarily unavailable.",
                    "minor_guard": {
                        "provider": MINOR_GUARD_PROVIDER,
                        "error": str(e),
                    },
                },
            )

        # Fail-open: allow the upload (but tell caller the check failed)
        result = None
        minor_guard_info = {
            "provider": MINOR_GUARD_PROVIDER,
            "is_minor": False,
            "reasons": [f"provider_error_fail_open: {type(e).__name__}"],
        }
    else:
        minor_guard_info = _minor_guard_payload(result)

        if result.is_minor:
            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "error": "MINOR_DETECTED",
                    "message": "Upload blocked: image likely contains a minor (<18).",
                    "minor_guard": minor_guard_info,
                },
            )

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "minor_guard": minor_guard_info,
        },
    )
