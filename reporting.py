"""
reporting.py
Generates summary data and optional text output for conversion sessions.
"""

from datetime import datetime
from pathlib import Path
from utils import log
import config


class Report:
    """
    Simple object to store session results.
    """
    def __init__(self):
        self.start_time = datetime.now()
        self.end_time = None
        self.total_files = 0
        self.converted = 0
        self.skipped = 0
        self.failed = 0
        self.failed_files = []
        # Additional tracking fields for richer reporting
        self.audio_failures = 0
        self.audio_failed_files = []
        self.retry_failures = 0
        self.mode = "NORMAL"  # or "DRY_RUN"

    def mark_complete(self):
        self.end_time = datetime.now()

    def add_failure(self, file_path: Path, reason: str | None = None):
        self.failed += 1
        self.failed_files.append(str(file_path))
        # For now we just record the file path; reasons can be used later for Discord or UI.

    def add_audio_failure(self, file_path: Path):
        """Track a failure specifically due to audio validation issues."""
        self.audio_failures += 1
        self.audio_failed_files.append(str(file_path))
        # Ensure it is also counted as a general failure
        if str(file_path) not in self.failed_files:
            self.failed += 1
            self.failed_files.append(str(file_path))

    def add_retry_failure(self, file_path: Path):
        """Track failures that persisted after all retries were exhausted."""
        self.retry_failures += 1
        # Do not double count in failed_files; main/converters will already call add_failure.

    def mark_dry_run(self):
        """Mark this report as representing a dry run (no actual conversions)."""
        self.mode = "DRY_RUN"

    def summary_text(self):
        """Return a human readable summary."""
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time else 0

        lines = [
            "============================================================",
            "VIDEO CONVERSION SUMMARY",
            "============================================================",
            f"Mode:       {self.mode}",
            f"Start Time: {self.start_time}",
            f"End Time:   {self.end_time}",
            f"Duration:   {duration} seconds",
            "------------------------------------------------------------",
            f"Total Files Found:        {self.total_files}",
            f"Converted Successfully:   {self.converted}",
            f"Skipped (no conversion):  {self.skipped}",
            f"Failed (total):           {self.failed}",
        ]

        if self.audio_failures:
            lines.append(f"  └ Audio validation failures: {self.audio_failures}")
        if self.retry_failures:
            lines.append(f"  └ Failures after retries:    {self.retry_failures}")

        lines.append("------------------------------------------------------------")

        if self.failed_files:
            lines.append("Failed Files:")
            for f in self.failed_files:
                lines.append(f"  - {f}")

        if self.audio_failed_files:
            lines.append("Audio Validation Failed Files:")
            for f in self.audio_failed_files:
                lines.append(f"  - {f}")

        return "\n".join(lines)

    def to_summary_dict(self) -> dict:
        """
        Return a dictionary representation of the core summary metrics.
        Useful for Discord embeds or JSON reports.
        """
        return {
            "mode": self.mode,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_files": self.total_files,
            "converted": self.converted,
            "skipped": self.skipped,
            "failed": self.failed,
            "audio_failures": self.audio_failures,
            "retry_failures": self.retry_failures,
            "failed_files": list(self.failed_files),
            "audio_failed_files": list(self.audio_failed_files),
        }

    def save_to_file(self):
        """Save summary to temp/summary.txt."""
        summary_path = config.TEMP_DIR / "summary.txt"
        summary_path.write_text(self.summary_text())
        log(f"Summary saved to {summary_path}")


def print_and_save(report: Report):
    """Helper to finalize, print, and save report."""
    report.mark_complete()
    text = report.summary_text()
    print(text)

    if config.LOGGING_ENABLED:
        report.save_to_file()

    log("Reporting complete.")