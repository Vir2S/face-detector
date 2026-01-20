class MinorDetectedError(Exception):
    """Raised when the uploaded image likely contains a minor (<18)."""
    pass


class MinorGuardProviderError(Exception):
    """Raised when the provider fails (network/auth/invalid response)."""
    pass


class MinorCheckUnavailableError(Exception):
    """Raised when we block (fail-closed) because the provider is unavailable/broken."""
    pass
