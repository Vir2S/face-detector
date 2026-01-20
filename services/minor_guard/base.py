from abc import ABC, abstractmethod

from services.minor_guard.types import MinorCheckResult


class MinorGuard(ABC):
    @abstractmethod
    async def check(self, image_bytes: bytes, content_type: str | None = None) -> MinorCheckResult:
        """
        Validate whether the image likely contains a minor (<18).
        Must never log or store the image bytes.
        """
        raise NotImplementedError
