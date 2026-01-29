import os

from dotenv import load_dotenv
from pathlib import Path


# Load environment variables from .env (local dev friendly)
load_dotenv()

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Minor guard core
MINOR_GUARD_PROVIDER = os.getenv("MINOR_GUARD_PROVIDER", "aws").lower().strip()  # aws | sightengine | hive | opencv
MINOR_GUARD_FAIL_CLOSED = os.getenv("MINOR_GUARD_FAIL_CLOSED", "true").lower() == "true"
MINOR_GUARD_STRICT = os.getenv("MINOR_GUARD_STRICT", "true").lower() == "true"

# AWS Rekognition
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")

# Sightengine
SIGHTENGINE_API_USER = os.getenv("SIGHTENGINE_API_USER", "")
SIGHTENGINE_API_SECRET = os.getenv("SIGHTENGINE_API_SECRET", "")
SIGHTENGINE_MINOR_PROB_THRESHOLD = float(os.getenv("SIGHTENGINE_MINOR_PROB_THRESHOLD", "0.5"))

# Hive
HIVE_API_KEY = os.getenv("HIVE_API_KEY", "")
HIVE_API_URL = os.getenv("HIVE_API_URL", "https://api.thehive.ai/api/v2/task/sync")
HIVE_MINOR_SCORE_THRESHOLD = float(os.getenv("HIVE_MINOR_SCORE_THRESHOLD", "0.5"))

# Public base URL that BytePlus can reach to download your uploaded images.
# IMPORTANT: BytePlus cannot access your local "http://localhost:8000".
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

# Ark SDK config (official parameters: timeout, max_retries)
ARK_TIMEOUT_S = float(os.getenv("ARK_TIMEOUT_S", "30"))
ARK_MAX_RETRIES = int(os.getenv("ARK_MAX_RETRIES", "2"))

# Extra backoff retries at app level (useful for polling bursts)
ARK_BACKOFF_MAX_ATTEMPTS = int(os.getenv("ARK_BACKOFF_MAX_ATTEMPTS", "6"))
ARK_BACKOFF_BASE_DELAY_S = float(os.getenv("ARK_BACKOFF_BASE_DELAY_S", "0.6"))
ARK_BACKOFF_MAX_DELAY_S = float(os.getenv("ARK_BACKOFF_MAX_DELAY_S", "8.0"))
ARK_BACKOFF_JITTER = float(os.getenv("ARK_BACKOFF_JITTER", "0.2"))

# Local upload storage
_default_upload_dir = Path(__file__).resolve().parents[1] / "storage" / "uploads"
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(_default_upload_dir)))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- OpenCV (local) minor-guard models ---
OPENCV_MODEL_DIR = Path(os.getenv("OPENCV_MODEL_DIR", "models/opencv")).resolve()
OPENCV_FACE_CONF_TH = float(os.getenv("OPENCV_FACE_CONF_TH", "0.5"))

# Which age buckets are considered "minor" (conservative default)
# Age model buckets: (0-2), (4-6), (8-12), (15-20), (25-32), (38-43), (48-53), (60-100)
OPENCV_BLOCK_BUCKETS = [
    s.strip() for s in os.getenv("OPENCV_BLOCK_BUCKETS", "(0-3),(4-7),(8-12)").split(",")
    if s.strip()
]

# Auto-download models on first run if missing
OPENCV_DOWNLOAD_MODELS = os.getenv("OPENCV_DOWNLOAD_MODELS", "true").lower() == "true"
