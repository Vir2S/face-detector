from typing import Any, Optional

from fastapi.responses import JSONResponse

from server.logger import request_id_ctx


def api_response(
    *,
    ok: bool,
    status_code: int = 200,
    data: Optional[dict[str, Any]] = None,
    error: Optional[str] = None,
    message: Optional[str] = None,
    minor_guard: Optional[dict[str, Any]] = None,
) -> JSONResponse:
    """Create a unified JSON API response.

    Shape (always):
      {
        "ok": bool,
        "request_id": str,
        "data": object,
        # error-only:
        "error"?: str,
        "message"?: str,
        # optional:
        "minor_guard"?: object
      }
    """
    payload: dict[str, Any] = {
        "ok": ok,
        "request_id": request_id_ctx.get("-"),
        "data": data or {},
    }

    # Keep "message" mainly for error cases, but allow it on success if needed.
    if ok:
        if message:
            payload["message"] = message
    else:
        payload["error"] = error or "UNKNOWN_ERROR"
        payload["message"] = message or "Request failed."

    if minor_guard is not None:
        payload["minor_guard"] = minor_guard

    return JSONResponse(
        status_code=status_code,
        content=payload
    )
