"""
scanner.py
Walks the input directory and identifies all video files that need conversion.
"""

from pathlib import Path
import config
from utils import log


def scan_for_videos():
    """
    Returns a list of Path objects representing all video files
    inside config.INPUT_DIR with extensions listed in VIDEO_EXTENSIONS.
    """
    log("Starting scan for videos...")
    videos = []

    for ext in config.VIDEO_EXTENSIONS:
        for file in config.INPUT_DIR.rglob(f"*{ext}"):
            videos.append(file)

    log(f"Scan complete. Found {len(videos)} file(s).")
    return videos


def needs_conversion(path: Path):
    """
    Determine whether a file needs to be processed.
    Rules:
      1. The file must be an m4v or other allowed extension.
      2. If OVERWRITE_EXISTING is false and mp4 already exists, skip.
    """
    if path.suffix.lower() not in config.VIDEO_EXTENSIONS:
        return False

    output_path = config.OUTPUT_DIR / path.with_suffix(".mp4").name

    if not config.OVERWRITE_EXISTING and output_path.exists():
        log(f"Skipping {path.name} because output already exists.")
        return False

    return True