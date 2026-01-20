from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class MinorCheckResult:
    # True => image likely contains a minor
    is_minor: bool

    # Short reasons to help debugging (safe, no PII)
    reasons: List[str]

    # Provider name used for the check
    provider: str
