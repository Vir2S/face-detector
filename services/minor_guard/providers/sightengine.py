import logging
import httpx

from server.config import (
    SIGHTENGINE_API_USER,
    SIGHTENGINE_API_SECRET,
    SIGHTENGINE_MINOR_PROB_THRESHOLD,
)
from server.logger import Timer

from ..base import MinorGuard
from ..exceptions import MinorGuardProviderError
from ..log_utils import key_value_serializer
from ..types import MinorCheckResult

logger = logging.getLogger(__name__)


class SightengineMinorGuard(MinorGuard):
    """
    Uses Sightengine Face Age model (models=face-age).
    Blocks if faces[].attributes.age.minor >= threshold.
    """

    def __init__(self) -> None:
        if not SIGHTENGINE_API_USER or not SIGHTENGINE_API_SECRET:
            raise ValueError("Sightengine credentials missing (SIGHTENGINE_API_USER / SIGHTENGINE_API_SECRET).")

        self._threshold = SIGHTENGINE_MINOR_PROB_THRESHOLD
        logger.info(
            "minor_guard sightengine_initialized "
            + key_value_serializer(threshold=self._threshold)
        )

    async def check(self, image_bytes: bytes, content_type: str | None = None) -> MinorCheckResult:
        url = "https://api.sightengine.com/1.0/check.json"
        ct = content_type or "image/jpeg"

        data = {
            "models": "face-age",
            "api_user": SIGHTENGINE_API_USER,
            "api_secret": SIGHTENGINE_API_SECRET,
        }
        files = {
            "media": ("upload", image_bytes, ct),
        }

        with Timer() as t:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    r = await client.post(url, data=data, files=files)
                    r.raise_for_status()
                    payload = r.json()
            except Exception as e:
                logger.exception(
                    "minor_guard sightengine_call_failed "
                    + key_value_serializer(ms=t.ms)
                )
                raise MinorGuardProviderError(f"Sightengine request failed: {e}") from e

        if payload.get("status") != "success":
            logger.error(
                "minor_guard sightengine_non_success "
                + key_value_serializer(status=payload.get("status"))
            )
            raise MinorGuardProviderError(f"Sightengine returned failure: {payload}")

        faces = payload.get("faces", []) or []
        reasons: list[str] = []

        for i, f in enumerate(faces):
            minor_prob = ((((f.get("attributes") or {}).get("age") or {}).get("minor")))
            if isinstance(minor_prob, (int, float)) and minor_prob >= self._threshold:
                reasons.append(f"face[{i}] minor_prob={minor_prob} (>= {self._threshold})")

        logger.info(
            "minor_guard sightengine_ok "
            + key_value_serializer(
                ms=f"{t.ms:.2f}",
                faces=len(faces),
                flagged=len(reasons)
            )
        )

        return MinorCheckResult(
            is_minor=len(reasons) > 0,
            reasons=reasons if reasons else [f"faces_detected={len(faces)}"],
            provider="sightengine",
        )
