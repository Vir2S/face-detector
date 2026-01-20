from typing import Any


def key_value_serializer(**fields: Any) -> str:
    """
    Serialize fields into a key=value string.
    Useful when your logger formatter prints only the message.
    """
    parts: list[str] = []

    for k, v in fields.items():
        parts.append(f"{k}={v}")

    return " ".join(parts)


def short_list(items: list[str], limit: int = 3) -> list[str]:
    """Avoid logging huge arrays."""
    return items[:limit]
