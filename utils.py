"""
utils.py
Shared helper functions for logging, paths, timestamps, and safe subprocess execution.
"""

import subprocess
import math
from datetime import datetime
from pathlib import Path
from typing import Union
import config


def timestamp():
    """Return a clean timestamp string for logs and reporting."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message):
    """Simple logger that writes to temp/log.txt if logging is enabled."""
    if not config.LOGGING_ENABLED:
        return

    log_file = config.TEMP_DIR / "log.txt"
    entry = f"[{timestamp()}] {message}\n"

    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a") as f:
        f.write(entry)


# --- New helper functions ---
def format_duration(seconds: Union[int, float]) -> str:
    """
    Return a human friendly string for a duration in seconds.
    Examples: 65 -> '1m 5s', 3605 -> '1h 0m 5s'
    """
    try:
        seconds = int(seconds)
    except Exception:
        return f"{seconds}s"

    if seconds < 60:
        return f"{seconds}s"

    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {sec}s"

    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {sec}s"


def human_size(num_bytes: Union[int, float]) -> str:
    """
    Return a human readable file size string.
    Examples: 1024 -> '1.0 KB', 1048576 -> '1.0 MB'
    """
    try:
        num = float(num_bytes)
    except Exception:
        return str(num_bytes)

    if num < 1024:
        return f"{num:.0f} B"

    units = ["KB", "MB", "GB", "TB", "PB"]
    idx = 0
    num /= 1024.0
    while num >= 1024.0 and idx < len(units) - 1:
        num /= 1024.0
        idx += 1

    return f"{num:.1f} {units[idx]}"


def safe_run(cmd):
    """
    Wrapper for subprocess.run that:
      • captures stdout and stderr
      • logs failures
      • returns (success, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            log(f"Command failed: {' '.join(cmd)}")
            log(f"stderr: {result.stderr.strip()}")
            return False, result.stdout, result.stderr

        return True, result.stdout, result.stderr

    except Exception as e:
        log(f"Exception while running command: {e}")
        return False, "", str(e)


def ensure_mp4_suffix(path: Path):
    """
    Given a Path object, return a new Path with .mp4 as the file extension.
    """
    return path.with_suffix(".mp4")