"""
config.py
Centralized configuration for the Media Converter project.
This file defines paths, defaults, and behavior toggles used by all modules.
"""

from pathlib import Path
import os
import platform


# Base project directory
SYSTEM = platform.system()
DEFAULT_BASE_DIR = Path("/Volumes/G-256/MediaConverterProject")
BASE_DIR = Path(os.getenv("MEDIA_CONVERTER_BASE_DIR", DEFAULT_BASE_DIR))

# Input directory to scan for videos
INPUT_DIR = BASE_DIR / "input"

# Output directory where converted mp4 files will go
OUTPUT_DIR = BASE_DIR / "output"

# Temporary work directory (for logs, temp files, failed attempts)
TEMP_DIR = BASE_DIR / "temp"


# Supported input extensions and profiles
DEFAULT_VIDEO_EXTENSIONS = {".m4v", ".mp4", ".mov", ".mkv"}
VIDEO_EXTENSION_PROFILES = {
    "plex_friendly": DEFAULT_VIDEO_EXTENSIONS,
    "archival": {".mkv", ".mov"},
}
ACTIVE_PROFILE = os.getenv("MEDIA_PROFILE", "plex_friendly")
VIDEO_EXTENSIONS = VIDEO_EXTENSION_PROFILES.get(ACTIVE_PROFILE, DEFAULT_VIDEO_EXTENSIONS)


# ffmpeg and ffprobe behavior settings
if SYSTEM == "Windows":
    DEFAULT_FFMPEG_BINARY = r"C:\ffmpeg\bin\ffmpeg.exe"
    DEFAULT_FFPROBE_BINARY = r"C:\ffmpeg\bin\ffprobe.exe"
else:
    DEFAULT_FFMPEG_BINARY = "ffmpeg"
    DEFAULT_FFPROBE_BINARY = "ffprobe"

FFMPEG_BINARY = os.getenv("FFMPEG_BINARY", DEFAULT_FFMPEG_BINARY)
FFPROBE_BINARY = os.getenv("FFPROBE_BINARY", DEFAULT_FFPROBE_BINARY)

FFMPEG = {
    "copy_mode": ["-c", "copy", "-map", "0"],
    "encode_video": ["-c:v", "libx264", "-preset", "slow", "-crf", "18"],
    "encode_audio": ["-c:a", "aac"],
    # Optional 4K specific settings used when HIGH_QUALITY_FOR_4K is true
    "encode_video_4k": ["-c:v", "libx264", "-preset", "slow", "-crf", "16"],
    "encode_audio_4k": ["-c:a", "aac", "-b:a", "640k"],
}


# Discord webhook settings (optional)
WEBHOOK_ENABLED = True
# Webhook URL is loaded from environment or a separate secrets file
WEBHOOK_URL = os.getenv("MEDIA_CONVERTER_WEBHOOK_URL", "")
DISCORD_EMBED_COLOR = 0x2ECC71


# General behavior flags
DELETE_ORIGINAL_AFTER_CONVERT = False      # When true, delete source after successful conversion
OVERWRITE_EXISTING = False                 # When false, skip files where output already exists
LOGGING_ENABLED = True

# Conversion behavior flags
SAME_DIR_OUTPUT = False                    # When true, write output mp4 next to the source file
MAX_RETRIES = 1                            # Additional attempts after the first failure
VALIDATE_AUDIO = True                      # Verify that output has at least one audio stream
HIGH_QUALITY_FOR_4K = False                # When true, use 4K specific encode settings
FAILED_DIR = TEMP_DIR / "failed"           # Where to move files that fail after all retries

# Subtitle behavior flags
KEEP_SUBTITLES = False                     # Keep subtitle tracks in mp4 when possible
BURN_IN_SUBTITLES = False                  # Burn subtitles into the video image when supported

# Renaming patterns for cleaned up output names
# Add strings like "1080p", "2160p", "x265", "ELiTE" to strip them from filenames.
RENAME_PATTERNS = []

# Ensure all directories exist at startup
def ensure_directories():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)