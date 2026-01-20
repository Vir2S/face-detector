import logging
from dataclasses import asdict

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from server.config import UPLOAD_DIR
from server.logger import setup_logging
from server.middlewares.request_id import RequestIdMiddleware
from server.routes import router

from services.minor_guard.exceptions import (
    MinorDetectedError,
    MinorCheckUnavailableError,
    FaceNotDetectedError,
)


# Initialize logging once at startup
setup_logging()
log = logging.getLogger("server")

app = FastAPI(title="Face Detector")


def _minor_guard_payload_from_exception(exc: Exception) -> dict | None:
    """Extract a JSON-friendly minor-guard payload from an exception, if available."""
    result = getattr(exc, "result", None)
    if result is None:
        return None

    d = asdict(result)
    # Keep payload small and safe
    d["reasons"] = (d.get("reasons") or [])[:5]
    return d


@app.exception_handler(MinorDetectedError)
async def minor_detected_handler(request: Request, exc: MinorDetectedError):
    """Return a structured 403 response including the model decision payload."""
    return JSONResponse(
        status_code=403,
        content={
            "ok": False,
            "error": "MINOR_DETECTED",
            "message": str(exc),
            "minor_guard": _minor_guard_payload_from_exception(exc),
        },
    )


@app.exception_handler(MinorCheckUnavailableError)
async def minor_check_unavailable_handler(request: Request, exc: MinorCheckUnavailableError):
    """Return a structured 503 response when fail-closed blocks due to provider issues."""
    return JSONResponse(
        status_code=503,
        content={
            "ok": False,
            "error": "AGE_CHECK_UNAVAILABLE",
            "message": str(exc),
            "minor_guard": {
                "provider": getattr(exc, "provider", "unknown"),
                "cause": getattr(exc, "cause", "unknown"),
            },
        },
    )


@app.exception_handler(FaceNotDetectedError)
async def face_not_detected_handler(request: Request, exc: FaceNotDetectedError):
    """Return a structured 422 response when no face is detected in the image."""
    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "error": "FACE_NOT_DETECTED",
            "message": str(exc),
            "minor_guard": _minor_guard_payload_from_exception(exc),
        },
    )

# Attach request-id middleware for per-request log correlation (rid=...)
app.add_middleware(RequestIdMiddleware)

# Expose uploaded files via HTTP so the upstream service can download them
app.mount("/files", StaticFiles(directory=str(UPLOAD_DIR)), name="files")

# API routes
app.include_router(router)


@app.get("/healthz")
def healthz():
    # Keep it lightweight
    log.debug("health check")
    return {"ok": True}
