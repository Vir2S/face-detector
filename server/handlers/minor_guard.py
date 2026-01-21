from dataclasses import asdict
from typing import Any, Optional


def minor_guard_payload(result: Any, *, max_reasons: int = 5) -> dict:
    """Convert MinorCheckResult (dataclass) into a JSON-friendly dict.

    We intentionally cap reasons to keep the response payload small.
    """
    d = asdict(result)
    d["reasons"] = (d.get("reasons") or [])[:max_reasons]
    return d


def minor_guard_payload_from_exception(exc: Exception, *, max_reasons: int = 5) -> Optional[dict]:
    """Extract MinorCheckResult payload from an exception, if it has `.result`."""
    result = getattr(exc, "result", None)

    if result is None:
        return None

    return minor_guard_payload(result, max_reasons=max_reasons)
