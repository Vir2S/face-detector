import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from server.config import UPLOAD_DIR
from server.logger import setup_logging
from server.middlewares.request_id import RequestIdMiddleware
from server.routes import router


# Initialize logging once at startup
setup_logging()
log = logging.getLogger("server")

app = FastAPI(title="Face Detector")

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
