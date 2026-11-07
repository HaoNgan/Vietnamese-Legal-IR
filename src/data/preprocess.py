"""Text normalization shared by dataset adapters."""

import unicodedata


def normalize_text(value: object) -> str:
    """Normalize Unicode to NFC and collapse whitespace without changing IDs."""
    if value is None:
        return ""
    return " ".join(unicodedata.normalize("NFC", str(value)).split())


def query_fingerprint(value: object) -> str:
    """Canonical exact-match key for duplicate-query checks (not model input)."""
    return normalize_text(value).casefold()
