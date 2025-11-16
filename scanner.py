"""
scanner.py
Scans for video files and determines whether they need conversion.
Also provides helpers for subtitle inspection.
"""

from pathlib import Path
import os

import config
from converters import sanitize_output_name
from utils import log, safe_run


def scan_for_videos():
    """
    Scan the input directory for video files matching the configured extensions.
    Returns a list of Path objects.
    """
    videos = []
    for root, _, files in os.walk(config.INPUT_DIR):
        for file in files:
            path = Path(root) / file
            if path.suffix.lower() in config.VIDEO_EXTENSIONS:
                videos.append(path)
    return videos


def needs_conversion(path: Path):
    """
    Determine whether a file needs to be processed.
    Rules:
      1. The file extension must be included in VIDEO_EXTENSIONS.
      2. If OVERWRITE_EXISTING is false and the target mp4 already exists, skip.
    """
    suffix = path.suffix.lower()
    if suffix not in config.VIDEO_EXTENSIONS:
        return False

    output_path = sanitize_output_name(path)

    if not config.OVERWRITE_EXISTING and output_path.exists():
        log(f"Skipping {path.name} because output already exists at {output_path}.")
        return False

    return True


def list_subtitle_streams(path: Path):
    """
    Return a list of subtitle stream descriptions for the given file.
    Uses ffprobe via FFPROBE_BINARY to inspect subtitle tracks.
    This is intended for UI and burn-in selection.
    """
    ffprobe_bin = getattr(config, "FFPROBE_BINARY", "ffprobe")
    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-select_streams", "s",
        "-show_entries", "stream=index,codec_name,codec_type:stream_tags=language,title",
        "-of", "json",
        str(path),
    ]
    success, stdout, _ = safe_run(cmd)
    if not success or not stdout.strip():
        return []

    try:
        import json
        data = json.loads(stdout)
        streams = data.get("streams", [])
        results = []
        for s in streams:
            tags = s.get("tags", {}) or {}
            results.append(
                {
                    "index": s.get("index"),
                    "codec": s.get("codec_name"),
                    "language": tags.get("language", "und"),
                    "title": tags.get("title", ""),
                }
            )
        return results
    except Exception:
        return []
