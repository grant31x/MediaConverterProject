"""
main.py
Entry point for the Media Converter project.
Orchestrates scanning, conversion, reporting, and optional notifications.
"""

from pathlib import Path
import argparse

import config
from config import ensure_directories
from scanner import scan_for_videos, needs_conversion
from converters import convert_video
from reporting import Report, print_and_save
from notifications import send_summary_embed, send_discord_message
from ui_backend import prepare_conversion_plan
from utils import log


def parse_args():
    """
    Parse command line arguments for the media converter.
    Allows overriding input/output, profile, dry run, and behavior flags.
    """
    parser = argparse.ArgumentParser(description="Media Converter")

    parser.add_argument(
        "--input",
        dest="input_dir",
        help="Input directory to scan for videos (overrides config.INPUT_DIR)",
    )
    parser.add_argument(
        "--output",
        dest="output_dir",
        help="Output directory for converted videos (overrides config.OUTPUT_DIR)",
    )
    parser.add_argument(
        "--profile",
        dest="profile",
        help="Video extension/profile name (overrides config.ACTIVE_PROFILE)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and show what would be converted without running ffmpeg",
    )
    parser.add_argument(
        "--plan",
        dest="show_plan",
        action="store_true",
        help="Show a conversion plan (files and subtitle streams) and exit",
    )
    parser.add_argument(
        "--same-dir-output",
        action="store_true",
        help="Write output mp4 next to the source file instead of a global output folder",
    )
    parser.add_argument(
        "--delete-original",
        action="store_true",
        help="Delete source file after successful conversion",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        dest="max_retries",
        help="Maximum number of additional attempts on failure (overrides config.MAX_RETRIES)",
    )
    parser.add_argument(
        "--high-quality-4k",
        action="store_true",
        help="Enable high quality settings for 4K sources",
    )
    parser.add_argument(
        "--skip-audio-validation",
        action="store_true",
        help="Skip audio validation on converted files",
    )
    parser.add_argument(
        "--no-discord",
        action="store_true",
        help="Disable Discord notifications for this run",
    )

    return parser.parse_args()


def run(args):
    """Main execution flow for a single conversion session."""
    # Apply runtime overrides from CLI arguments
    if args.input_dir:
        config.INPUT_DIR = Path(args.input_dir)
    if args.output_dir:
        config.OUTPUT_DIR = Path(args.output_dir)
    if args.profile:
        # Override active profile and extensions if present
        if hasattr(config, "ACTIVE_PROFILE"):
            config.ACTIVE_PROFILE = args.profile
        if hasattr(config, "VIDEO_EXTENSION_PROFILES"):
            config.VIDEO_EXTENSIONS = config.VIDEO_EXTENSION_PROFILES.get(
                args.profile, config.VIDEO_EXTENSIONS
            )

    if args.same_dir_output:
        config.SAME_DIR_OUTPUT = True
    if args.delete_original:
        config.DELETE_ORIGINAL_AFTER_CONVERT = True
    if args.max_retries is not None:
        config.MAX_RETRIES = args.max_retries
    if args.high_quality_4k:
        config.HIGH_QUALITY_FOR_4K = True
    if args.skip_audio_validation:
        config.VALIDATE_AUDIO = False
    if args.no_discord:
        config.WEBHOOK_ENABLED = False

    ensure_directories()
    log("Media Converter started.")

    report = Report()

    # Scan for input files
    videos = scan_for_videos()
    report.total_files = len(videos)

    # Plan-only mode: show conversion plan and exit
    if getattr(args, "show_plan", False):
        print("=== Conversion Plan ===")
        plan = prepare_conversion_plan()
        for item in plan:
            print(f"- {item['name']}")
            print(f"  Path: {item['path']}")
            print(f"  Needs conversion: {item['needs_conversion']}")
            subs = item.get("subtitle_streams") or []
            if subs:
                print("  Subtitles:")
                for s in subs:
                    idx = s.get("index")
                    lang = s.get("language", "und")
                    title = s.get("title", "")
                    codec = s.get("codec", "")
                    line = f"    - index {idx} [{lang}] {codec}"
                    if title:
                        line += f"  {title}"
                    print(line)
            else:
                print("  Subtitles: none")
            print()

        log("Plan-only run complete. No files were converted.")
        return

    if args.dry_run:
        # Only report what would be converted or skipped
        for video_path in videos:
            if needs_conversion(video_path):
                print(f"[DRY RUN] Would convert: {video_path}")
            else:
                print(f"[DRY RUN] Skip (no conversion needed): {video_path}")
                report.skipped += 1
        print_and_save(report)
        log("Dry run complete. No files were converted.")
        return

    total = len(videos)
    index = 0

    for video_path in videos:
        index += 1

        if not needs_conversion(video_path):
            report.skipped += 1
            continue

        success = convert_video(video_path, index=index, total=total)
        if success:
            report.converted += 1
        else:
            report.add_failure(video_path)

    # Final reporting
    print_and_save(report)

    # Optional notifications
    if config.WEBHOOK_ENABLED and getattr(config, "WEBHOOK_URL", ""):
        # Try rich embed first, fall back to simple text if needed
        sent_embed = send_summary_embed(report)
        if not sent_embed:
            send_discord_message("Media conversion batch completed. Check logs for details.")

    log("Media Converter finished.")


if __name__ == "__main__":
    cli_args = parse_args()
    run(cli_args)