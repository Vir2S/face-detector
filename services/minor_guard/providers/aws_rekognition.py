import logging
import os
import time

import boto3
from starlette.concurrency import run_in_threadpool

from server.config import AWS_REGION, MINOR_GUARD_STRICT
from ..base import MinorGuard
from ..exceptions import MinorGuardProviderError
from ..log_utils import key_value_serializer
from ..types import MinorCheckResult

logger = logging.getLogger(__name__)


class AwsRekognitionMinorGuard(MinorGuard):
    """
    AWS Rekognition DetectFaces AgeRange.
    - Honors AWS_PROFILE (useful for SSO/dev)
    - Uses perf_counter so timing is correct even on exceptions
    - Logs __file__ path once to prove which module is actually executed
    """

    def __init__(self) -> None:
        profile = os.getenv("AWS_PROFILE")
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()

        self._client = session.client("rekognition", region_name=AWS_REGION)
        self._strict = MINOR_GUARD_STRICT

        logger.info(
            "minor_guard aws_initialized "
            + key_value_serializer(
                region=AWS_REGION,
                strict=self._strict,
                profile=profile or "-",
                aws_provider_file=os.path.abspath(__file__),
            )
        )

    async def check(self, image_bytes: bytes, content_type: str | None = None) -> MinorCheckResult:
        t0 = time.perf_counter()

        try:
            resp = await run_in_threadpool(
                lambda: self._client.detect_faces(
                    Image={"Bytes": image_bytes},
                    Attributes=["AGE_RANGE"],
                )
            )

        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000
            logger.exception(
                "minor_guard aws_detect_faces_failed "
                + key_value_serializer(
                    ms=f"{ms:.2f}"
                )
            )
            raise MinorGuardProviderError(f"AWS Rekognition failed: {e}") from e

        ms = (time.perf_counter() - t0) * 1000

        faces = resp.get("FaceDetails", []) or []
        reasons: list[str] = []

        for i, fd in enumerate(faces):
            age = (fd.get("AgeRange") or {})
            low = age.get("Low")
            high = age.get("High")
            if low is None or high is None:
                continue

            # STRICT:
            #   If the lower bound is < 18, the person might be a minor => block.
            # Non-strict:
            #   Only block if the upper bound is < 18 (more permissive).
            if self._strict:
                if int(low) < 18:
                    reasons.append(f"face[{i}] age_low={low} (<18)")
            else:
                if int(high) < 18:
                    reasons.append(f"face[{i}] age_high={high} (<18)")

        logger.info(
            "minor_guard aws_ok "
            + key_value_serializer(
                ms=f"{ms:.2f}",
                faces=len(faces),
                flagged=len(reasons)
            )
        )

        return MinorCheckResult(
            is_minor=len(reasons) > 0,
            reasons=reasons if reasons else [f"faces_detected={len(faces)}"],
            provider="aws_rekognition",
        )
