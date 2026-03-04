from __future__ import annotations

import re
import unicodedata

NORMALIZATION_VERSION = "slide_text_norm_v1"

SMART_CHAR_TRANSLATIONS = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2032": "'",
        "\u2033": '"',
        "\u00a0": " ",
    }
)


def normalize_slide_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    normalized = normalized.translate(SMART_CHAR_TRANSLATIONS)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized
