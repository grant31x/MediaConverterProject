"""
converters.py
Handles video conversion logic using ffmpeg.
Chooses between stream copy or full reencode based on codec compatibility.
"""

from pathlib import Path
import shutil
import config
from utils import log, safe_run, ensure_mp4_suffix
from renamer import clean_name


def build_copy_command(input_path: Path, output_path: Path):
    """
    Build the ffmpeg command for lossless container rewrap.
    """
    return [
        config.FFMPEG_BINARY,
        "-i", str(input_path),
        *config.FFMPEG["copy_mode"],
        str(output_path)
    ]



def sanitize_output_name(input_path: Path) -> Path:
    """
    Decide the output path and apply optional renaming rules.
    If SAME_DIR_OUTPUT is true, write next to the source file.
    Otherwise, use the configured OUTPUT_DIR.
    """
    same_dir_output = getattr(config, "SAME_DIR_OUTPUT", False)
    base_dir = input_path.parent if same_dir_output else config.OUTPUT_DIR

    # Use renamer.clean_name to apply all renaming rules
    cleaned_stem = clean_name(input_path)

    output_path = base_dir / f"{cleaned_stem}.mp4"

    # --- CRITICAL BUG FIX ---
    # Prevent overwriting the source file if names are identical.
    # e.g., "Movie.mp4" in "SAME_DIR_OUTPUT" mode.
    if output_path.resolve() == input_path.resolve():
        output_path = base_dir / f"{cleaned_stem}_converted.mp4"
    # --- END BUG FIX ---

    return output_path


def is_4k_video(input_path: Path) -> bool:
    """
    Return true if input video appears to be 4K (height >= 2160).
    Uses ffprobe if HIGH_QUALITY_FOR_4K is enabled.
    """
    if not getattr(config, "HIGH_QUALITY_FOR_4K", False):
        return False

    ffprobe_bin = getattr(config, "FFPROBE_BINARY", "ffprobe")
    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=height",
        "-of", "csv=p=0",
        str(input_path),
    ]
    success, stdout, _ = safe_run(cmd)
    if not success or not stdout.strip():
        return False

    try:
        height = int(stdout.strip().splitlines()[0])
        return height >= 2160
    except Exception:
        return False


def has_audio_stream(path: Path) -> bool:
    """
    Return true if ffprobe finds at least one audio stream on the file.
    """
    ffprobe_bin = getattr(config, "FFPROBE_BINARY", "ffprobe")
    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=index",
        "-of", "default=nokey=1:noprint_wrappers=1",
        str(path),
    ]
    success, stdout, _ = safe_run(cmd)
    if not success:
        return False

    return bool(stdout.strip())


def build_encode_command(input_path: Path, output_path: Path):
    """
    Build the ffmpeg command for reencoding video and audio streams.
    Respects optional 4K and subtitle configuration.
    """
    encode_video = config.FFMPEG["encode_video"]
    encode_audio = config.FFMPEG["encode_audio"]

    # Optional high quality settings for 4K sources
    if is_4k_video(input_path):
        encode_video = config.FFMPEG.get("encode_video_4k", encode_video)
        encode_audio = config.FFMPEG.get("encode_audio_4k", encode_audio)

    extra_args = []

    # Subtitle behavior: burn in or keep as tracks
    if getattr(config, "BURN_IN_SUBTITLES", False):
        # Burn in subtitles from the source container where supported
        extra_args.extend(["-vf", f"subtitles={str(input_path)}"])
    elif getattr(config, "KEEP_SUBTITLES", False):
        # Keep subtitles as tracks where mp4 supports them
        extra_args.extend(["-c:s", "mov_text", "-map", "0"])

    return [
        config.FFMPEG_BINARY,
        "-i", str(input_path),
        *encode_video,
        *encode_audio,
        *extra_args,
        str(output_path)
    ]



def convert_video(input_path: Path, index: int | None = None, total: int | None = None):
    """
    Convert a single video file.
    Steps:
      1. Decide output path and name
      2. Optionally log progress index
      3. Try stream copy first
      4. If copy fails, retry with full reencode
      5. Validate audio if enabled
      6. Retry up to MAX_RETRIES times
      7. Move final failures to a failed folder
      8. Optionally delete original when successful
    """
    if index is not None and total is not None:
        msg = f"Processing {index} of {total}: {input_path.name}"
        print(msg)
        log(msg)
    else:
        log(f"Starting conversion: {input_path.name}")

    output_path = sanitize_output_name(input_path)

    # Ensure the output directory exists, especially for SAME_DIR_OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)

    max_retries = getattr(config, "MAX_RETRIES", 0)
    validate_audio = getattr(config, "VALIDATE_AUDIO", True)

    attempts = 0
    success = False

    while attempts <= max_retries and not success:
        attempts += 1

        # First attempt: lossless copy
        copy_cmd = build_copy_command(input_path, output_path)
        success, _, _ = safe_run(copy_cmd)

        if success:
            log(f"Copy mode succeeded for {input_path.name} on attempt {attempts}")
        else:
            log(f"Copy mode failed for {input_path.name} on attempt {attempts}, retrying with encode mode.")
            encode_cmd = build_encode_command(input_path, output_path)
            success, _, _ = safe_run(encode_cmd)

            if not success:
                log(f"Encoding failed for {input_path.name} on attempt {attempts}.")

        # Optional audio validation on the resulting file
        if success and validate_audio:
            if not has_audio_stream(output_path):
                log(f"Audio validation failed for {input_path.name} (no audio streams detected).")
                success = False

    if not success:
        # After all retries, move the source file to a failed folder
        failed_dir = getattr(config, "FAILED_DIR", config.TEMP_DIR / "failed")
        try:
            failed_dir.mkdir(parents=True, exist_ok=True)
            target = failed_dir / input_path.name
            shutil.move(str(input_path), str(target))
            log(f"Moved failed file to {target}")
        except Exception as e:
            log(f"Failed to move file after retries: {e}")
        return False

    # Optionally delete original file once conversion has succeeded and audio is validated
    if getattr(config, "DELETE_ORIGINAL_AFTER_CONVERT", False):
        try:
            input_path.unlink()
            log(f"Deleted original file: {input_path.name}")
        except Exception as e:
            log(f"Failed to delete original file: {e}")

    return True