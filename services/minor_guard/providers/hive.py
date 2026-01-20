import logging
import httpx

from server.config import (
    HIVE_API_KEY,
    HIVE_API_URL,
    HIVE_MINOR_SCORE_THRESHOLD,
)
from server.logger import Timer

from ..base import MinorGuard
from ..exceptions import MinorGuardProviderError
from ..log_utils import key_value_serializer
from ..types import MinorCheckResult


logger = logging.getLogger(__name__)


class HiveDemographicMinorGuard(MinorGuard):
    """
    Uses Hive Demographic Attributes API.
    Blocks if the model returns minor age-class labels above threshold.

    Note:
      Hive project/model schemas may vary; this parser is intentionally defensive.
    """

    # Common minor classes
    _MINOR_LABELS = {"teenager", "pre_teen", "toddler", "baby"}

    def __init__(self) -> None:
        if not HIVE_API_KEY:
            raise ValueError("Hive API key missing (HIVE_API_KEY).")

        self._url = HIVE_API_URL
        self._score_th = HIVE_MINOR_SCORE_THRESHOLD

        logger.info(
            "minor_guard hive_initialized "
            + key_value_serializer(
                url=self._url,
                threshold=self._score_th
            )
        )

    async def check(self, image_bytes: bytes, content_type: str | None = None) -> MinorCheckResult:
        ct = content_type or "image/jpeg"

        headers = {
            # Hive commonly accepts "Authorization: token <key>"
            "Authorization": f"token {HIVE_API_KEY}",
            "accept": "application/json",
        }
        files = {
            "media": ("upload", image_bytes, ct),
        }

        with Timer() as t:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.post(self._url, headers=headers, files=files)
                    r.raise_for_status()
                    payload = r.json()
            except Exception as e:
                logger.exception(
                    "minor_guard hive_call_failed "
                    + key_value_serializer(ms=t.ms)
                )
                raise MinorGuardProviderError(f"Hive request failed: {e}") from e

        statuses = payload.get("status") or []
        reasons: list[str] = []

        def iter_class_items(output_obj):
            """
            Try to walk through typical Hive detector-like structures:
              status[].response.output[].bounding_poly[].classes[]
            """
            frames = output_obj if isinstance(output_obj, list) else [output_obj]
            for frame in frames:
                for bp in (frame.get("bounding_poly") or []):
                    for cls in (bp.get("classes") or []):
                        yield cls

        for st in statuses:
            msg = (st.get("status") or {}).get("message")
            if msg and msg != "SUCCESS":
                logger.error(
                    "minor_guard hive_task_not_success "
                    + key_value_serializer(message=msg)
                )
                raise MinorGuardProviderError(f"Hive task status not SUCCESS: {msg}")

            output = ((st.get("response") or {}).get("output")) or []
            for cls in iter_class_items(output):
                label = (cls.get("class") or cls.get("label") or "").strip()
                score = cls.get("score")

                if not label:
                    continue

                if label in self._MINOR_LABELS and isinstance(score, (int, float)) and score >= self._score_th:
                    reasons.append(f"age_label={label} score={score} (>= {self._score_th})")

        logger.info(
            "minor_guard hive_ok "
            + key_value_serializer(
                ms=f"{t.ms:.2f}",
                flagged=len(reasons)
            )
        )

        return MinorCheckResult(
            is_minor=len(reasons) > 0,
            reasons=reasons if reasons else ["no_minor_signal_detected"],
            provider="hive_demographic",
        )
