import logging
import os
import threading
from pathlib import Path
from typing import Tuple

import cv2
import httpx
import numpy as np

from server.config import (
    OPENCV_MODEL_DIR,
    OPENCV_FACE_CONF_TH,
    OPENCV_BLOCK_BUCKETS,
    OPENCV_DOWNLOAD_MODELS,
)
from ..base import MinorGuard
from ..exceptions import MinorGuardProviderError
from ..log_utils import key_value_serializer
from ..types import MinorCheckResult

logger = logging.getLogger(__name__)

# -----------------------------
# Model URLs (stable sources)
# -----------------------------

# Face detector (OpenCV DNN ResNet-10 SSD)
FACE_PROTO_URL = "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
FACE_MODEL_URL = "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20180205_fp16/res10_300x300_ssd_iter_140000_fp16.caffemodel"

# Age model (Caffe) - keep proto + weights from the same repo to avoid mismatches
# This repo hosts both files together, which drastically reduces "proto/weights mismatch" pain.
AGE_PROTO_URL = "https://github.com/eveningglow/age-and-gender-classification/raw/master/model/deploy_age2.prototxt"
AGE_MODEL_URL = "https://github.com/eveningglow/age-and-gender-classification/raw/master/model/age_net.caffemodel"

FACE_PROTO_NAME = "deploy.prototxt"
FACE_MODEL_NAME = "res10_300x300_ssd_iter_140000_fp16.caffemodel"
AGE_PROTO_NAME = "deploy_age2.prototxt"
AGE_MODEL_NAME = "age_net.caffemodel"

# Mean values used in common OpenCV age/gender examples (BGR order)
MODEL_MEAN_VALUES = (78.4263377603, 87.7689143744, 114.895847746)

# Fixed age buckets for this model
AGE_BUCKETS = ["(0-2)", "(4-6)", "(8-12)", "(15-20)", "(25-32)", "(38-43)", "(48-53)", "(60-100)"]


def _download_file(url: str, dst: Path) -> None:
    """
    Download a file into dst.
    We use follow_redirects=True to handle raw/GitHub redirects.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)

    logger.info("opencv_model download_start " + key_value_serializer(url=url, dst=str(dst)))

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        dst.write_bytes(r.content)

    logger.info(
        "opencv_model download_ok " + key_value_serializer(dst=str(dst), size_bytes=dst.stat().st_size)
    )


def _looks_like_html(path: Path) -> bool:
    """
    Model downloads sometimes return HTML (e.g. blocked page, rate limit, etc.).
    This quick check catches that early.
    """
    try:
        head = path.read_bytes()[:512].lower()
    except Exception:
        return True

    return b"<html" in head or b"<!doctype html" in head


def _validate_model_file(path: Path, min_bytes: int) -> None:
    """
    Basic sanity checks:
    - file exists
    - file size is not tiny
    - file is not HTML
    """
    if not path.exists():
        raise MinorGuardProviderError(f"OpenCV model file missing: {path}")

    size = path.stat().st_size
    if size < min_bytes:
        raise MinorGuardProviderError(f"OpenCV model file too small: {path} size={size} (<{min_bytes})")

    if _looks_like_html(path):
        raise MinorGuardProviderError(f"OpenCV model file looks like HTML (bad download): {path}")


def _ensure_models_present(model_dir: Path) -> Tuple[Path, Path, Path, Path]:
    """
    Ensure face+age models exist and look valid.
    If OPENCV_DOWNLOAD_MODELS=true, missing files will be downloaded.
    """
    face_proto = model_dir / FACE_PROTO_NAME
    face_model = model_dir / FACE_MODEL_NAME
    age_proto = model_dir / AGE_PROTO_NAME
    age_model = model_dir / AGE_MODEL_NAME

    missing = [p for p in [face_proto, face_model, age_proto, age_model] if not p.exists()]
    if missing:
        if not OPENCV_DOWNLOAD_MODELS:
            raise MinorGuardProviderError(
                f"OpenCV models missing and OPENCV_DOWNLOAD_MODELS=false. Missing: {[str(p) for p in missing]}"
            )

        # Download only what is missing
        if not face_proto.exists():
            _download_file(FACE_PROTO_URL, face_proto)
        if not face_model.exists():
            _download_file(FACE_MODEL_URL, face_model)
        if not age_proto.exists():
            _download_file(AGE_PROTO_URL, age_proto)
        if not age_model.exists():
            _download_file(AGE_MODEL_URL, age_model)

    # Validate files (fail fast with a clear error message)
    _validate_model_file(face_proto, min_bytes=200)          # prototxt
    _validate_model_file(age_proto, min_bytes=200)           # prototxt
    _validate_model_file(face_model, min_bytes=1_000_000)    # caffemodel (MBs)
    _validate_model_file(age_model, min_bytes=1_000_000)     # caffemodel (MBs)

    return face_proto, face_model, age_proto, age_model


class OpenCvCaffeMinorGuard(MinorGuard):
    """
    Local (no cloud) minor-guard using OpenCV DNN:
    1) Detect faces with ResNet-10 SSD
    2) Predict age bucket for each face
    3) If any face bucket is in OPENCV_BLOCK_BUCKETS => block

    Notes:
    - The age model predicts age *groups*, not exact age.
    - Blocking "(15-20)" is conservative and catches teenagers reliably enough for policy gating.
    - OpenCV DNN Net forward() is not guaranteed thread-safe => guarded by a lock.
    """

    def __init__(self) -> None:
        model_dir = Path(OPENCV_MODEL_DIR)
        face_proto, face_model, age_proto, age_model = _ensure_models_present(model_dir)

        try:
            self._face_net = cv2.dnn.readNetFromCaffe(str(face_proto), str(face_model))
            self._age_net = cv2.dnn.readNetFromCaffe(str(age_proto), str(age_model))
        except cv2.error as e:
            raise MinorGuardProviderError(f"OpenCV failed to load Caffe models: {e}") from e

        self._conf_th = float(OPENCV_FACE_CONF_TH)
        self._block_buckets = set(OPENCV_BLOCK_BUCKETS)

        # Guard forward() calls: safer under concurrent requests
        self._lock = threading.Lock()

        logger.info(
            "minor_guard opencv_initialized "
            + key_value_serializer(
                model_dir=str(model_dir),
                face_conf_th=self._conf_th,
                block_buckets=list(self._block_buckets),
                opencv_provider_file=os.path.abspath(__file__),
            )
        )

    async def check(self, image_bytes: bytes, content_type: str | None = None) -> MinorCheckResult:
        # Decode bytes into BGR image
        buf = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None:
            raise MinorGuardProviderError("OpenCV failed to decode image bytes (imdecode returned None).")

        h, w = img.shape[:2]

        # -----------------------------
        # Face detection
        # -----------------------------
        face_blob = cv2.dnn.blobFromImage(
            img, 1.0, (300, 300), (104, 117, 123), swapRB=False, crop=False
        )

        with self._lock:
            try:
                self._face_net.setInput(face_blob)
                detections = self._face_net.forward()
            except cv2.error as e:
                raise MinorGuardProviderError(f"OpenCV face detector forward() failed: {e}") from e

        faces = []
        for i in range(detections.shape[2]):
            conf = float(detections[0, 0, i, 2])
            if conf < self._conf_th:
                continue

            x1 = int(detections[0, 0, i, 3] * w)
            y1 = int(detections[0, 0, i, 4] * h)
            x2 = int(detections[0, 0, i, 5] * w)
            y2 = int(detections[0, 0, i, 6] * h)

            # Clamp to bounds
            x1 = max(0, min(x1, w - 1))
            y1 = max(0, min(y1, h - 1))
            x2 = max(0, min(x2, w - 1))
            y2 = max(0, min(y2, h - 1))

            if x2 <= x1 or y2 <= y1:
                continue

            faces.append((x1, y1, x2, y2, conf))

        if not faces:
            # No face detected => allow (otherwise you'd block landscapes, etc.)
            return MinorCheckResult(
                is_minor=False,
                reasons=["no_faces_detected"],
                provider="opencv_caffe",
            )

        # -----------------------------
        # Age estimation per face
        # -----------------------------
        reasons: list[str] = [f"faces_detected={len(faces)}"]
        is_minor = False

        for idx, (x1, y1, x2, y2, conf) in enumerate(faces):
            face_roi = img[y1:y2, x1:x2]

            # Age net expects 227x227 BGR with mean subtraction
            age_blob = cv2.dnn.blobFromImage(
                face_roi, 1.0, (227, 227), MODEL_MEAN_VALUES, swapRB=False, crop=False
            )

            with self._lock:
                try:
                    self._age_net.setInput(age_blob)
                    age_preds = self._age_net.forward()
                except cv2.error as e:
                    raise MinorGuardProviderError(f"OpenCV age model forward() failed: {e}") from e

            best_i = int(age_preds[0].argmax())
            best_prob = float(age_preds[0][best_i])
            bucket = AGE_BUCKETS[best_i]

            reasons.append(f"face[{idx}] conf={conf:.2f} age_bucket={bucket} p={best_prob:.2f}")

            if bucket in self._block_buckets:
                is_minor = True

        return MinorCheckResult(
            is_minor=is_minor,
            reasons=reasons,
            provider="opencv_caffe",
        )
