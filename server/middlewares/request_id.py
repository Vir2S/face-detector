import logging

from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from server.logger import request_id_ctx, new_request_id, Timer

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Adds a request id to ContextVar (for logs) and to the response header.
    Also logs basic request metrics.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # If client provides X-Request-Id, reuse it; otherwise generate a new one
        rid = request.headers.get("X-Request-Id") or new_request_id()
        token = request_id_ctx.set(rid)

        try:
            with Timer() as t:
                response = await call_next(request)

            # Expose request id to the client for correlation
            response.headers["X-Request-Id"] = rid

            logger.info(
                "http_request method=%s path=%s status=%s ms=%.2f",
                request.method,
                request.url.path,
                getattr(response, "status_code", "-"),
                t.ms,
            )
            return response
        finally:
            # Reset context to avoid leaking rid across requests
            request_id_ctx.reset(token)
