"""
Simple Media Converter
A single-file Python script to scan and convert video files using ffmpeg.
This combines the logic from the multi-file project into one place.
"""

import sys
import os
import subprocess
import threading
import json
from pathlib import Path
from tkinter import (
    Tk,
    Frame,
    Label,
    Entry,
    Button,
    Text,
    Scrollbar,
    filedialog,
    Checkbutton,
    IntVar,
    Toplevel,
    ttk,
)

# --- 1. CONFIGURATION (Replaces config.py) ---

# Set your ffmpeg/ffprobe paths here.
# On Windows, this might be r"C:\ffmpeg\bin\ffmpeg.exe"
# On macOS/Linux, it's often just "ffmpeg" if it's in your PATH.
FFMPEG_BINARY = "ffmpeg"
FFPROBE_BINARY = "ffprobe"

# Types of video files to scan for
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".mov", ".m4v", ".avi", ".webm"}

# --- END CONFIGURATION ---


class SimpleConverterApp:
    """
    The main application class.
    """

    def __init__(self, root):
        self.root = root
        self.root.title("Simple Media Converter")
        self.root.geometry("800x600")
        self.root.configure(bg="#2b2b2b")

        self.scan_dir = ""
        self.dest_dir = ""
        self.conversion_plan = []  # List of files to convert

        # --- Settings ---
        self.setting_same_dir = IntVar(value=0)
        self.setting_delete_original = IntVar(value=0)
        self.setting_high_4k = IntVar(value=0)
        self.setting_skip_audio = IntVar(value=0)

        # --- UI Setup ---
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            ".",
            background="#2b2b2b",
            foreground="#e0e0e0",
            fieldbackground="#3c3c3c",
            bordercolor="#555555",
        )
        style.configure("TButton", background="#007acc", foreground="#ffffff")
        style.map(
            "TButton", background=[("active", "#005f9e")],
        )
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TEntry", font=("Segoe UI", 10))

        # --- Top Frame: Paths ---
        path_frame = ttk.Frame(root, padding=10)
        path_frame.pack(fill="x", side="top")

        # Scan Directory
        ttk.Label(path_frame, text="Scan Directory:").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        self.scan_entry = ttk.Entry(path_frame, width=60)
        self.scan_entry.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(path_frame, text="Browse...", command=self.browse_scan).grid(
            row=0, column=2, padx=5
        )

        # Destination Directory
        ttk.Label(path_frame, text="Destination Directory:").grid(
            row=1, column=0, sticky="w", padx=5, pady=5
        )
        self.dest_entry = ttk.Entry(path_frame, width=60)
        self.dest_entry.grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Button(path_frame, text="Browse...", command=self.browse_dest).grid(
            row=1, column=2, padx=5
        )

        path_frame.columnconfigure(1, weight=1)

        # --- Middle Frame: Actions ---
        action_frame = ttk.Frame(root, padding=10)
        action_frame.pack(fill="x", side="top")

        ttk.Button(action_frame, text="Settings", command=self.open_settings).pack(
            side="left", padx=5
        )
        ttk.Button(action_frame, text="Scan For Videos", command=self.scan_files).pack(
            side="left", padx=5
        )
        self.run_button = ttk.Button(
            action_frame,
            text="Run Conversion (0 files)",
            command=self.run_conversion_thread,
            state="disabled",
        )
        self.run_button.pack(side="left", padx=5)

        # --- Bottom Frame: Log Output ---
        log_frame = ttk.Frame(root, padding=10)
        log_frame.pack(fill="both", expand=True)

        self.log_text = Text(
            log_frame,
            wrap="word",
            height=15,
            bg="#1e1e1e",
            fg="#d4d4d4",
            font=("Consolas", 10),
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#555555",
        )
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log("Welcome to Simple Media Converter.")
        self.log("Please select a Scan and Destination directory.")

    def log(self, message):
        """Appends a message to the text log, ensuring it runs on the main thread."""

        def _append_log():
            self.log_text.config(state="normal")
            self.log_text.insert("end", f"{message}\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")

        # Check if we are on the main thread
        if self.root.winfo_exists():
            self.root.after(0, _append_log)

    def browse_scan(self):
        dir_path = filedialog.askdirectory(title="Select Scan Directory")
        if dir_path:
            self.scan_dir = dir_path
            self.scan_entry.delete(0, "end")
            self.scan_entry.insert(0, self.scan_dir)
            self.log(f"Scan Directory set to: {self.scan_dir}")

    def browse_dest(self):
        dir_path = filedialog.askdirectory(title="Select Destination Directory")
        if dir_path:
            self.dest_dir = dir_path
            self.dest_entry.delete(0, "end")
            self.dest_entry.insert(0, self.dest_dir)
            self.log(f"Destination Directory set to: {self.dest_dir}")

    def open_settings(self):
        """Opens a new Toplevel window for settings."""
        settings_win = Toplevel(self.root)
        settings_win.title("Settings")
        settings_win.configure(bg="#2b2b2b")
        settings_win.transient(self.root)
        settings_win.grab_set()

        frame = ttk.Frame(settings_win, padding=20)
        frame.pack()

        ttk.Checkbutton(
            frame,
            text="Output next to source file (ignores Destination Directory)",
            variable=self.setting_same_dir,
        ).pack(anchor="w", pady=5)
        ttk.Checkbutton(
            frame,
            text="Delete original after successful conversion (USE WITH CAUTION!)",
            variable=self.setting_delete_original,
        ).pack(anchor="w", pady=5)
        ttk.Checkbutton(
            frame,
            text="Enable high quality mode for 4K sources",
            variable=self.setting_high_4k,
        ).pack(anchor="w", pady=5)
        ttk.Checkbutton(
            frame,
            text="Skip audio validation (faster, but risky)",
            variable=self.setting_skip_audio,
        ).pack(anchor="w", pady=5)

        ttk.Button(frame, text="Done", command=settings_win.destroy).pack(pady=10)

    # --- 2. SCANNING LOGIC (Replaces scanner.py) ---

    def scan_files(self):
        self.scan_dir = self.scan_entry.get()
        self.dest_dir = self.dest_entry.get()

        if not self.scan_dir:
            self.log("Error: Please select a Scan Directory first.")
            return

        # Check "Same Dir" setting
        if self.setting_same_dir.get() == 0 and not self.dest_dir:
            self.log("Error: Please select a Destination Directory or enable 'Output next to source' in Settings.")
            return

        self.log(f"Scanning {self.scan_dir} for videos...")
        self.conversion_plan = []
        found_files = []

        try:
            for root, _, files in os.walk(self.scan_dir):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.suffix.lower() in VIDEO_EXTENSIONS:
                        found_files.append(file_path)

            self.log(f"Found {len(found_files)} total video files.")

            # Now, check which ones need conversion
            for file_path in found_files:
                output_path = self.get_output_path(file_path)
                if not output_path.exists():
                    self.conversion_plan.append(file_path)
                else:
                    self.log(f"Skipping (exists): {file_path.name}")

            self.log(f"Plan created: {len(self.conversion_plan)} files need conversion.")
            self.run_button.config(
                text=f"Run Conversion ({len(self.conversion_plan)} files)",
                state="normal" if self.conversion_plan else "disabled",
            )
        except Exception as e:
            self.log(f"Error during scan: {e}")

    # --- 3. CONVERSION LOGIC (Replaces converters.py) ---

    def get_output_path(self, input_path: Path) -> Path:
        """
        Determines the final output path for a file.
        Includes the critical bug fix.
        """
        if self.setting_same_dir.get() == 1:
            base_dir = input_path.parent
        else:
            # Recreate the subfolder structure in the destination
            relative_path = input_path.relative_to(self.scan_dir)
            base_dir = Path(self.dest_dir) / relative_path.parent

        # Ensure output directory exists
        base_dir.mkdir(parents=True, exist_ok=True)

        output_path = base_dir / f"{input_path.stem}.mp4"

        # --- CRITICAL BUG FIX ---
        # Prevent overwriting the source file if names are identical
        if output_path.resolve() == input_path.resolve():
            output_path = base_dir / f"{input_path.stem}_converted.mp4"
        # --- END BUG FIX ---

        return output_path

    def safe_run(self, cmd):
        """Runs a subprocess command safely."""
        try:
            # Use CREATE_NO_WINDOW on Windows to hide the ffmpeg console
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="ignore",
                startupinfo=startupinfo,
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)

    def has_audio(self, file_path: Path) -> bool:
        """Checks if a file has an audio stream using ffprobe."""
        if self.setting_skip_audio.get() == 1:
            return True  # Skip the check

        cmd = [
            FFPROBE_BINARY,
            "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "default=nokey=1:noprint_wrappers=1",
            str(file_path),
        ]
        success, stdout, _ = self.safe_run(cmd)
        return success and bool(stdout.strip())

    def is_4k(self, file_path: Path) -> bool:
        """Checks if a file is 4K resolution."""
        if self.setting_high_4k.get() == 0:
            return False

        cmd = [
            FFPROBE_BINARY,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=height",
            "-of", "csv=p=0",
            str(file_path),
        ]
        success, stdout, _ = self.safe_run(cmd)
        if not success or not stdout.strip():
            return False
        try:
            height = int(stdout.strip().splitlines()[0])
            return height >= 2160
        except Exception:
            return False

    def convert_file(self, input_path: Path, output_path: Path):
        """
        Runs the ffmpeg conversion for a single file.
        Tries to copy first, then re-encodes on failure.
        """
        self.log(f"Attempting copy: {input_path.name} -> {output_path.name}")
        
        # --- Attempt 1: Stream Copy (Fast) ---
        copy_cmd = [
            FFMPEG_BINARY,
            "-i", str(input_path),
            "-c", "copy",       # Copy all streams
            "-map", "0",        # Map all streams
            "-c:s", "mov_text", # Convert subtitle formats if possible
            str(output_path),
        ]
        success, _, stderr = self.safe_run(copy_cmd)

        if success and self.has_audio(output_path):
            self.log(f"Success (Copy): {input_path.name}")
            return True, "copy"

        # --- Attempt 2: Re-encode (Slow) ---
        self.log(f"Copy failed (or no audio). Retrying with re-encode: {input_path.name}")
        if "Subtitle codec not supported" in stderr:
            self.log("...Reason: Unsupported subtitle format. Re-encoding without them.")
        
        # Build encode command
        video_args = ["-c:v", "libx264", "-preset", "slow", "-crf", "20"]
        audio_args = ["-c:a", "aac", "-b:a", "192k"]

        if self.is_4k(input_path):
            self.log(f"...Using 4K settings for: {input_path.name}")
            video_args = ["-c:v", "libx264", "-preset", "slow", "-crf", "18"]
            audio_args = ["-c:a", "aac", "-b:a", "320k"]

        encode_cmd = [
            FFMPEG_BINARY,
            "-i", str(input_path),
            *video_args,
            *audio_args,
            "-map", "0:v",      # Map video
            "-map", "0:a?",     # Map audio (if it exists)
            # We skip subtitles on re-encode for simplicity
            str(output_path),
        ]
        
        success, _, _ = self.safe_run(encode_cmd)

        if success and self.has_audio(output_path):
            self.log(f"Success (Encode): {input_path.name}")
            return True, "encode"
        
        self.log(f"Failed (Encode): {input_path.name}")
        # Clean up failed partial file
        if output_path.exists():
            output_path.unlink()
        return False, "failed"

    def run_conversion_thread(self):
        """
        Starts the conversion process in a new thread
        to avoid locking up the UI.
        """
        # Disable button to prevent re-clicks
        self.run_button.config(state="disabled")

        # Create and start the thread
        thread = threading.Thread(target=self.conversion_worker, daemon=True)
        thread.start()

    def conversion_worker(self):
        """
        This is the function that runs in the background thread.
        """
        self.log("--- Conversion Started ---")
        total_files = len(self.conversion_plan)
        success_count = 0
        fail_count = 0

        # We operate on a copy of the list
        plan = list(self.conversion_plan)

        for i, input_path in enumerate(plan):
            self.log(f"--- [ {i+1} / {total_files} ] ---")
            
            # Double-check output path right before conversion
            output_path = self.get_output_path(input_path)

            if output_path.exists():
                self.log(f"Skipping (exists): {input_path.name}")
                continue

            success, mode = self.convert_file(input_Write(input_path, output_path))

            if success:
                success_count += 1
                # Optionally delete original
                if self.setting_delete_original.get() == 1:
                    try:
                        input_path.unlink()
                        self.log(f"Deleted original: {input_path.name}")
                    except Exception as e:
                        self.log(f"Error deleting original file: {e}")
            else:
                fail_count += 1
                self.log(f"Failed to convert: {input_path.name}")

        self.log("--- Conversion Finished ---")
        self.log(f"Summary: {success_count} succeeded, {fail_count} failed.")

        # Re-enable the UI button on the main thread
        self.root.after(
            0,
            lambda: self.run_button.config(
                text=f"Run Conversion (0 files)", state="disabled"
            ),
        )
        # Clear the plan
        self.conversion_plan = []


if __name__ == "__main__":
    # Ensure ffprobe and ffmpeg are available
    try:
        subprocess.run(
            [FFMPEG_BINARY, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        subprocess.run(
            [FFPROBE_BINARY, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except FileNotFoundError:
        print(
            f"FATAL ERROR: {FFMPEG_BINARY} or {FFPROBE_BINARY} not found.",
            file=sys.stderr,
        )
        print(
            "Please install ffmpeg and ffprobe, or set the FFMPEG_BINARY and FFPROBE_BINARY variables in this script.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"FATAL ERROR: Could not run ffmpeg/ffprobe. {e}", file=sys.stderr)
        sys.exit(1)

    root = Tk()
    app = SimpleConverterApp(root)
    root.mainloop()