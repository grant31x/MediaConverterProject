"""
ui_app.py
Simple clickable UI for the Media Converter project using Tkinter.

Features:
- Select input and output directories
- Scan for videos and show a list of files
- Show subtitle tracks for the selected file
- Toggle behavior flags
- Run conversion using main.run(...) in a background thread
"""

import threading
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import config
import main
from ui_backend import prepare_conversion_plan, describe_file


class UIArgs:
    """
    Lightweight argument holder that matches the interface expected by main.run.
    """

    def __init__(
        self,
        input_dir: Optional[str],
        output_dir: Optional[str],
        dry_run: bool,
        same_dir_output: bool,
        delete_original: bool,
        max_retries: Optional[int],
        high_quality_4k: bool,
        skip_audio_validation: bool,
        no_discord: bool,
    ):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.profile = None
        self.dry_run = dry_run
        self.show_plan = False
        self.same_dir_output = same_dir_output
        self.delete_original = delete_original
        self.max_retries = max_retries
        self.high_quality_4k = high_quality_4k
        self.skip_audio_validation = skip_audio_validation
        self.no_discord = no_discord


class MediaConverterUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.configure(bg="#020617")  # Dark navy background
        self.title("Media Converter UI")
        self.geometry("900x700")

        # Visual styling
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Base frame and label styles
        style.configure("Main.TFrame", background="#020617")
        style.configure("Section.TLabelframe", background="#020617", foreground="#e5e7eb", borderwidth=1)
        style.configure("Section.TLabelframe.Label", background="#020617", foreground="#60a5fa")
        style.configure("Title.TLabel", background="#020617", foreground="#60a5fa", font=("Segoe UI", 16, "bold"))
        style.configure("Accent.TLabel", background="#020617", foreground="#e5e7eb")

        # Button style
        style.configure("Primary.TButton", background="#1d4ed8", foreground="#e5e7eb")
        style.map("Primary.TButton",
                  background=[("active", "#2563eb")])

        # Checkbutton style for dark background
        style.configure("Dark.TCheckbutton", background="#020617", foreground="#e5e7eb")

        # Checkbox / other controls will inherit frame background

        # App title
        title_label = ttk.Label(self, text="Media Converter", style="Title.TLabel")
        title_label.pack(side=tk.TOP, anchor="w", padx=10, pady=(10, 0))

        # Top frame for directory selection
        top_frame = ttk.Frame(self, style="Main.TFrame")
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        # Input directory
        ttk.Label(top_frame, text="Input directory", style="Accent.TLabel").grid(row=0, column=0, sticky="w")
        self.input_var = tk.StringVar(value=str(config.INPUT_DIR))
        self.input_entry = ttk.Entry(top_frame, textvariable=self.input_var, width=60)
        self.input_entry.grid(row=0, column=1, padx=5)
        ttk.Button(top_frame, text="Browse", command=self.browse_input, style="Primary.TButton").grid(
            row=0, column=2, padx=5
        )

        # Output directory
        ttk.Label(top_frame, text="Output directory", style="Accent.TLabel").grid(row=1, column=0, sticky="w")
        self.output_var = tk.StringVar(value=str(config.OUTPUT_DIR))
        self.output_entry = ttk.Entry(top_frame, textvariable=self.output_var, width=60)
        self.output_entry.grid(row=1, column=1, padx=5)
        ttk.Button(top_frame, text="Browse", command=self.browse_output, style="Primary.TButton").grid(
            row=1, column=2, padx=5
        )

        # Buttons
        ttk.Button(top_frame, text="Scan", command=self.scan_files, style="Primary.TButton").grid(
            row=2, column=0, pady=10, sticky="w"
        )
        ttk.Button(top_frame, text="Run Conversion", command=self.run_conversion_clicked, style="Primary.TButton").grid(
            row=2, column=1, pady=10, sticky="w"
        )

        # Middle frame for list and details
        middle_frame = ttk.Frame(self, style="Main.TFrame")
        middle_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)

        # File list
        list_frame = ttk.Frame(middle_frame, style="Main.TFrame")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(list_frame, text="Files", style="Accent.TLabel").pack(anchor="w")
        self.file_listbox = tk.Listbox(
            list_frame,
            height=20,
            bg="#020617",
            fg="#e5e7eb",
            selectbackground="#1d4ed8",
            selectforeground="#e5e7eb",
            highlightthickness=0,
            borderwidth=1,
            relief="solid",
        )
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.file_listbox.bind("<<ListboxSelect>>", self.on_file_selected)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox.config(yscrollcommand=scrollbar.set)

        # Details panel
        details_frame = ttk.Frame(middle_frame, style="Main.TFrame")
        details_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)

        ttk.Label(details_frame, text="Subtitle tracks", style="Accent.TLabel").pack(anchor="w")
        self.sub_text = tk.Text(
            details_frame,
            height=15,
            wrap="word",
            bg="#020617",
            fg="#e5e7eb",
            insertbackground="#e5e7eb",
            borderwidth=1,
            relief="solid",
        )
        self.sub_text.pack(fill=tk.BOTH, expand=True)

        # Behavior flags
        flags_frame = ttk.LabelFrame(self, text="Options", style="Section.TLabelframe")
        flags_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        self.dry_run_var = tk.BooleanVar(value=False)
        self.same_dir_var = tk.BooleanVar(value=config.SAME_DIR_OUTPUT)
        self.delete_orig_var = tk.BooleanVar(value=config.DELETE_ORIGINAL_AFTER_CONVERT)
        self.high_4k_var = tk.BooleanVar(value=config.HIGH_QUALITY_FOR_4K)
        self.skip_audio_var = tk.BooleanVar(value=False)
        self.no_discord_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(flags_frame, text="Dry run only", variable=self.dry_run_var, style="Dark.TCheckbutton").grid(
            row=0, column=0, sticky="w", padx=5, pady=2
        )
        ttk.Checkbutton(
            flags_frame,
            text="Output next to source (ignore output directory)",
            variable=self.same_dir_var,
            style="Dark.TCheckbutton",
        ).grid(row=0, column=1, sticky="w", padx=5, pady=2)
        ttk.Checkbutton(
            flags_frame,
            text="Delete original after conversion",
            variable=self.delete_orig_var,
            style="Dark.TCheckbutton",
        ).grid(row=0, column=2, sticky="w", padx=5, pady=2)

        ttk.Checkbutton(
            flags_frame,
            text="High quality mode for 4K",
            variable=self.high_4k_var,
            style="Dark.TCheckbutton",
        ).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Checkbutton(
            flags_frame,
            text="Skip audio validation",
            variable=self.skip_audio_var,
            style="Dark.TCheckbutton",
        ).grid(row=1, column=1, sticky="w", padx=5, pady=2)
        ttk.Checkbutton(
            flags_frame,
            text="Disable Discord for this run",
            variable=self.no_discord_var,
            style="Dark.TCheckbutton",
        ).grid(row=1, column=2, sticky="w", padx=5, pady=2)

    def browse_input(self):
        directory = filedialog.askdirectory(initialdir=self.input_var.get() or "/")
        if directory:
            self.input_var.set(directory)

    def browse_output(self):
        directory = filedialog.askdirectory(initialdir=self.output_var.get() or "/")
        if directory:
            self.output_var.set(directory)

    def scan_files(self):
        """
        Scan using ui_backend.prepare_conversion_plan and populate the listbox.
        """
        input_dir = self.input_var.get().strip()
        if not input_dir:
            messagebox.showerror("Error", "Input directory is required.")
            return

        # Update config paths before scan
        config.INPUT_DIR = Path(input_dir)
        output_dir = self.output_var.get().strip()
        if output_dir:
            config.OUTPUT_DIR = Path(output_dir)

        try:
            self.plan = prepare_conversion_plan()
        except Exception as e:
            messagebox.showerror("Error", f"Scan failed: {e}")
            return

        self.file_listbox.delete(0, tk.END)
        for item in self.plan:
            path = Path(item["path"])
            ext = path.suffix.lower() or "unknown"
            status = "convert" if item["needs_conversion"] else "skip"
            label = f"{item['name']}  | {ext}  | {status}"
            self.file_listbox.insert(tk.END, label)

        self.sub_text.delete("1.0", tk.END)
        self.sub_text.insert(tk.END, "Scan complete. Select a file to view subtitle tracks.\n")

    def on_file_selected(self, event):
        """
        Show subtitle information for the selected file.
        """
        if not self.plan:
            return

        selection = self.file_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx < 0 or idx >= len(self.plan):
            return

        item = self.plan[idx]
        path = Path(item["path"])
        self.selected_file = path

        # Use describe_file to get subtitle streams
        info = describe_file(path)
        subs = info.get("subtitle_streams") or []

        self.sub_text.delete("1.0", tk.END)
        self.sub_text.insert(tk.END, f"File: {info['name']}\n")
        self.sub_text.insert(tk.END, f"Path: {info['path']}\n\n")

        if not subs:
            self.sub_text.insert(tk.END, "No subtitle tracks detected.\n")
            return

        self.sub_text.insert(tk.END, "Subtitle tracks:\n")
        for s in subs:
            idx_s = s.get("index")
            lang = s.get("language", "und")
            title = s.get("title", "")
            codec = s.get("codec", "")
            line = f"- index {idx_s} [{lang}] {codec}"
            if title:
                line += f"  {title}"
            self.sub_text.insert(tk.END, line + "\n")

    def run_conversion_clicked(self):
        """
        Build UIArgs object and call main.run in a background thread.
        """
        input_dir = self.input_var.get().strip()
        output_dir = self.output_var.get().strip() or None

        if not input_dir:
            messagebox.showerror("Error", "Input directory is required.")
            return

        args = UIArgs(
            input_dir=input_dir,
            output_dir=output_dir,
            dry_run=self.dry_run_var.get(),
            same_dir_output=self.same_dir_var.get(),
            delete_original=self.delete_orig_var.get(),
            max_retries=None,
            high_quality_4k=self.high_4k_var.get(),
            skip_audio_validation=self.skip_audio_var.get(),
            no_discord=self.no_discord_var.get(),
        )

        def worker():
            try:
                main.run(args)
                messagebox.showinfo("Done", "Conversion run completed. Check terminal logs for details.")
            except Exception as e:
                messagebox.showerror("Error", f"Conversion failed: {e}")

        threading.Thread(target=worker, daemon=True).start()
        messagebox.showinfo("Started", "Conversion started in the background. Check terminal logs for progress.")


if __name__ == "__main__":
    app = MediaConverterUI()
    app.mainloop()
