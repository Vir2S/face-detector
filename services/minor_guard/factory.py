import logging

from server.config import MINOR_GUARD_FAIL_CLOSED, MINOR_GUARD_PROVIDER
from .exceptions import (
    MinorDetectedError,
    MinorGuardProviderError,
    MinorCheckUnavailableError,
    FaceNotDetectedError,
)
from .log_utils import key_value_serializer, short_list
from .providers.aws_rekognition import AwsRekognitionMinorGuard
from .providers.hive import HiveDemographicMinorGuard
from .providers.opencv_caffe import OpenCvCaffeMinorGuard
from .providers.sightengine import SightengineMinorGuard
from .types import MinorCheckResult


logger = logging.getLogger(__name__)


def _is_no_face_result(result: MinorCheckResult) -> bool:
    """Heuristic: treat 'no face detected' as a domain error (cannot verify)."""
    reasons = result.reasons or []
    for r in reasons:
        if r == "no_faces_detected":
            return True
        if r.startswith("faces_detected="):
            try:
                if int(r.split("=", 1)[1]) == 0:
                    return True
            except ValueError:
                # Ignore parsing issues and continue
                pass
    return False


def get_minor_guard():
    provider = MINOR_GUARD_PROVIDER
    logger.info("minor_guard provider_selected " + key_value_serializer(provider=provider))

    if provider == "aws":
        return AwsRekognitionMinorGuard()
    if provider == "sightengine":
        return SightengineMinorGuard()
    if provider == "hive":
        return HiveDemographicMinorGuard()
    if provider == "opencv":
        return OpenCvCaffeMinorGuard()

    raise ValueError(f"Unknown MINOR_GUARD_PROVIDER: {provider}")


async def assert_no_minors(guard, image_bytes: bytes, content_type: str | None = None) -> MinorCheckResult:
    """
    Run minor check and return the full result (provider, is_minor, reasons).

    Raises:
      - MinorDetectedError (403 scenario) if a minor is detected.
      - MinorCheckUnavailableError (503 scenario) if provider fails and fail-closed is enabled.
    """
    try:
        result: MinorCheckResult = await guard.check(image_bytes=image_bytes, content_type=content_type)

    except MinorGuardProviderError as e:
        logger.exception(
            "minor_guard provider_error "
            + key_value_serializer(fail_closed=MINOR_GUARD_FAIL_CLOSED, provider=MINOR_GUARD_PROVIDER)
        )

        if MINOR_GUARD_FAIL_CLOSED:
            # Attach provider/cause so the API layer can return structured error data.
            exc = MinorCheckUnavailableError("Upload blocked: age-check temporarily unavailable.")
            setattr(exc, "provider", MINOR_GUARD_PROVIDER)
            setattr(exc, "cause", type(e).__name__)
            raise exc from e

        # Fail-open: treat as "not minor" but keep diagnostic info in the result
        return MinorCheckResult(
            is_minor=False,
            reasons=[f"provider_error_fail_open:{type(e).__name__}"],
            provider=MINOR_GUARD_PROVIDER,
        )

    logger.info(
        "minor_guard decision "
        + key_value_serializer(
            provider=result.provider,
            is_minor=result.is_minor,
            reasons=short_list(result.reasons),
        )
    )

    if result.is_minor:
        # Attach the full provider result to the exception so the API layer can return it.
        exc = MinorDetectedError("Upload blocked: image likely contains a minor (<18).")
        setattr(exc, "result", result)
        raise exc

    # If we couldn't detect any face, we cannot reliably verify age.
    # Return a structured client error so the caller can retry with a clearer face photo.
    if _is_no_face_result(result):
        exc = FaceNotDetectedError("No face detected in the image. Please upload a clear face photo.", result=result)
        raise exc

    return result
