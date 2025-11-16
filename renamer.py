"""
renamer.py
Helpers for cleaning and normalizing media file names.
"""

from pathlib import Path
from typing import Iterable, List

import config


def clean_name(path: Path, extra_patterns: Iterable[str] | None = None) -> str:
    """
    Return a cleaned base name for the given file path.

    Uses:
      - config.RENAME_PATTERNS for known tags to remove
      - optional extra_patterns passed in at call time

    This does not change the extension. It only returns the stem.
    """
    stem = path.stem

    patterns: List[str] = []
    patterns.extend(getattr(config, "RENAME_PATTERNS", []))
    if extra_patterns:
        patterns.extend(list(extra_patterns))

    cleaned = stem
    for pattern in patterns:
        cleaned = cleaned.replace(pattern, "")

    # Collapse double spaces after removals
    cleaned = " ".join(cleaned.split())

    if not cleaned:
        cleaned = stem

    return cleaned
