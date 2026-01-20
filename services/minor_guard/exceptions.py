class MinorDetectedError(Exception):
    """Raised when the uploaded image likely contains a minor (<18)."""
    pass


class MinorGuardProviderError(Exception):
    """Raised when the provider fails (network/auth/invalid response)."""
    pass


class MinorCheckUnavailableError(Exception):
    """Raised when we block (fail-closed) because the provider is unavailable/broken."""
    pass


class FaceNotDetectedError(Exception):
    """Raised when no face is detected in the uploaded image."""

    def __init__(self, message: str, result=None):
        # Attach the model decision payload (if any) so the API can return it.
        super().__init__(message)
        self.result = result
