import logging
import sys
import time
import uuid

from contextvars import ContextVar

from server.config import LOG_LEVEL


# Request ID stored in context (per-request), available inside logs
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Inject request_id into every log record
        record.request_id = request_id_ctx.get("-")
        return True


def setup_logging() -> None:
    """
    Configure root logging once.
    - Logs go to stdout (good for Docker/K8s)
    - Adds request_id field to every record
    - Avoids duplicate handlers
    """
    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)

    # Remove default handlers to avoid duplicated logs
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(LOG_LEVEL)

    fmt = "%(asctime)s | %(levelname)s | %(name)s | rid=%(request_id)s | %(message)s"
    handler.setFormatter(logging.Formatter(fmt))
    handler.addFilter(RequestIdFilter())

    root.addHandler(handler)

    # Make Uvicorn loggers propagate to root, so formatting is consistent
    logging.getLogger("uvicorn").propagate = True
    logging.getLogger("uvicorn.error").propagate = True
    logging.getLogger("uvicorn.access").propagate = True

    # Disable uvicorn access logs (we already log requests in middleware with request_id)
    uv_access = logging.getLogger("uvicorn.access")
    uv_access.handlers.clear()
    uv_access.propagate = False
    uv_access.disabled = True


def new_request_id() -> str:
    # Short, human-friendly request id
    return uuid.uuid4().hex[:12]


class Timer:
    """Simple context manager to measure elapsed time in ms."""
    def __enter__(self):
        self.t0 = time.perf_counter()
        self.ms = 0.0
        return self

    def __exit__(self, exc_type, exc, tb):
        self.ms = (time.perf_counter() - self.t0) * 1000
