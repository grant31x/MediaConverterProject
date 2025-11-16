"""
ui_backend.py
Backend utility layer for interactive file selection, subtitle inspection,
and future UI features for the Media Converter Project.
"""

from pathlib import Path
from typing import List, Dict, Any

from scanner import scan_for_videos, list_subtitle_streams
import config


def list_all_videos() -> List[Path]:
    """
    Return all discovered video files in the configured INPUT_DIR.
    """
    return scan_for_videos()


def describe_file(path: Path) -> Dict[str, Any]:
    """
    Return a structured description of a media file:
      - filename
      - full path
      - extension
      - detected subtitle streams
    """
    subs = list_subtitle_streams(path)

    return {
        "name": path.name,
        "path": str(path),
        "extension": path.suffix.lower(),
        "subtitle_streams": subs,
    }


def preview_subtitles(path: Path) -> List[Dict[str, str]]:
    """
    Return a list of subtitle track metadata for UI preview.
    Each item includes:
      - index
      - codec
      - language
      - title
    """
    return list_subtitle_streams(path)


def prepare_conversion_plan() -> List[Dict[str, Any]]:
    """
    Build a complete conversion plan the UI layer can show:
      - files discovered
      - whether conversion is needed
      - subtitle tracks available
    """
    from scanner import needs_conversion

    videos = scan_for_videos()
    plan = []

    for v in videos:
        plan.append({
            "path": str(v),
            "name": v.name,
            "needs_conversion": needs_conversion(v),
            "subtitle_streams": list_subtitle_streams(v),
        })

    return plan


