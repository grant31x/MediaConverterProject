"""
ui_app.py
PyQt6 based UI for the Media Converter project.

Features:
- Select input and output directories
- Scan for videos and show a table of files
- Show file type, planned status (convert or skip), and audio summary per file
- Button to view subtitles for the selected file
- Toggle behavior flags
- Run conversion using main.run(...) in a background thread
"""

import sys
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QFileDialog,
    QCheckBox,
    QMessageBox,
)
from PyQt6.QtCore import QObject, pyqtSignal

import config
import main
from ui_backend import prepare_conversion_plan, describe_file
from utils import safe_run


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


class ConversionWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, args: UIArgs):
        super().__init__()
        self.args = args

    def run(self):
        try:
            main.run(self.args)
            self.finished.emit("Conversion run completed. Check terminal logs for details.")
        except Exception as e:
            self.error.emit(str(e))


def get_audio_summary(path: Path) -> str:
    """
    Use ffprobe to inspect audio streams and return a short summary string.
    Example: "eac3 5.1 (eng), aac 2.0 (eng)"
    """
    ffprobe_bin = getattr(config, "FFPROBE_BINARY", "ffprobe")
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "stream=index,codec_name,codec_type,channels,channel_layout:stream_tags=language",
        "-of",
        "json",
        str(path),
    ]
    success, stdout, _ = safe_run(cmd)
    if not success or not stdout.strip():
        return "unknown"

    try:
        import json

        data = json.loads(stdout)
        streams = data.get("streams", [])
        audio_parts: List[str] = []

        for s in streams:
            if s.get("codec_type") != "audio":
                continue
            codec = s.get("codec_name") or "audio"
            channels = s.get("channels")
            layout = s.get("channel_layout")
            lang = (s.get("tags", {}) or {}).get("language", "und")
            ch_text = ""
            if layout:
                ch_text = layout
            elif channels:
                ch_text = f"{channels} ch"
            audio_parts.append(f"{codec} {ch_text} ({lang})".strip())

        if not audio_parts:
            return "audio stream not found"

        return ", ".join(audio_parts)
    except Exception:
        return "unknown"


class MediaConverterWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.plan: List[Dict[str, Any]] = []

        self.setWindowTitle("Media Converter")
        self.resize(1000, 720)

        # Dark theme styling
        self.setStyleSheet(
            """
        QMainWindow {
            background-color: #020617;
        }
        QWidget {
            background-color: #020617;
            color: #e5e7eb;
            font-family: "Segoe UI", system-ui, -apple-system;
            font-size: 10pt;
        }
        QGroupBox {
            border: 1px solid #1f2937;
            margin-top: 6px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            color: #60a5fa;
        }
        QLabel {
            color: #e5e7eb;
        }
        QLineEdit {
            background-color: #020617;
            color: #e5e7eb;
            border: 1px solid #4b5563;
            padding: 4px;
        }
        QPushButton {
            background-color: #1d4ed8;
            color: #e5e7eb;
            border-radius: 4px;
            padding: 6px 10px;
        }
        QPushButton:hover {
            background-color: #2563eb;
        }
        QTableWidget {
            background-color: #020617;
            color: #e5e7eb;
            gridline-color: #1f2937;
            border: 1px solid #4b5563;
        }
        QHeaderView::section {
            background-color: #020617;
            color: #e5e7eb;
            border: 1px solid #1f2937;
            padding: 4px;
        }
        QTextEdit {
            background-color: #020617;
            color: #e5e7eb;
            border: 1px solid #4b5563;
        }
        QCheckBox {
            color: #e5e7eb;
        }
        """
        )

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        # Paths section
        paths_group = QGroupBox("Paths")
        root_layout.addWidget(paths_group)
        paths_layout = QVBoxLayout()
        paths_group.setLayout(paths_layout)

        # Input row
        input_row = QHBoxLayout()
        input_label = QLabel("Input directory")
        self.input_edit = QLineEdit(str(config.INPUT_DIR))
        input_browse = QPushButton("Browse")
        input_browse.clicked.connect(self.browse_input)
        input_row.addWidget(input_label)
        input_row.addWidget(self.input_edit)
        input_row.addWidget(input_browse)
        paths_layout.addLayout(input_row)

        # Output row
        output_row = QHBoxLayout()
        output_label = QLabel("Output directory")
        self.output_edit = QLineEdit(str(config.OUTPUT_DIR))
        output_browse = QPushButton("Browse")
        output_browse.clicked.connect(self.browse_output)
        output_row.addWidget(output_label)
        output_row.addWidget(self.output_edit)
        output_row.addWidget(output_browse)
        paths_layout.addLayout(output_row)

        # Action buttons row
        actions_row = QHBoxLayout()
        self.scan_button = QPushButton("Scan")
        self.scan_button.clicked.connect(self.scan_files)
        self.run_button = QPushButton("Run conversion")
        self.run_button.clicked.connect(self.run_conversion_clicked)
        actions_row.addWidget(self.scan_button)
        actions_row.addWidget(self.run_button)
        actions_row.addStretch()
        paths_layout.addLayout(actions_row)

        # Middle area: files table and details
        middle_layout = QHBoxLayout()
        root_layout.addLayout(middle_layout)

        files_group = QGroupBox("Files")
        middle_layout.addWidget(files_group, 3)
        files_layout = QVBoxLayout()
        files_group.setLayout(files_layout)

        self.files_table = QTableWidget()
        self.files_table.setColumnCount(4)
        self.files_table.setHorizontalHeaderLabels(["Name", "Type", "Status", "Audio"])
        self.files_table.setSelectionBehavior(self.files_table.SelectionBehavior.SelectRows)
        self.files_table.setSelectionMode(self.files_table.SelectionMode.SingleSelection)
        self.files_table.cellClicked.connect(self.on_file_row_selected)
        self.files_table.horizontalHeader().setStretchLastSection(True)
        files_layout.addWidget(self.files_table)

        details_group = QGroupBox("Details")
        middle_layout.addWidget(details_group, 2)
        details_layout = QVBoxLayout()
        details_group.setLayout(details_layout)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)

        self.subtitles_button = QPushButton("Show subtitles for selected file")
        self.subtitles_button.clicked.connect(self.show_subtitles_clicked)
        details_layout.addWidget(self.subtitles_button)

        # Options section
        options_group = QGroupBox("Options")
        root_layout.addWidget(options_group)
        options_layout = QVBoxLayout()
        options_group.setLayout(options_layout)

        row1 = QHBoxLayout()
        row2 = QHBoxLayout()

        self.cb_dry_run = QCheckBox("Dry run only")
        self.cb_same_dir = QCheckBox("Output next to source (ignore output directory)")
        self.cb_same_dir.setChecked(config.SAME_DIR_OUTPUT)
        self.cb_delete_original = QCheckBox("Delete original after conversion")
        self.cb_delete_original.setChecked(config.DELETE_ORIGINAL_AFTER_CONVERT)

        row1.addWidget(self.cb_dry_run)
        row1.addWidget(self.cb_same_dir)
        row1.addWidget(self.cb_delete_original)
        row1.addStretch()

        self.cb_high_4k = QCheckBox("High quality mode for 4K")
        self.cb_high_4k.setChecked(config.HIGH_QUALITY_FOR_4K)
        self.cb_skip_audio = QCheckBox("Skip audio validation")
        self.cb_no_discord = QCheckBox("Disable Discord for this run")

        row2.addWidget(self.cb_high_4k)
        row2.addWidget(self.cb_skip_audio)
        row2.addWidget(self.cb_no_discord)
        row2.addStretch()

        options_layout.addLayout(row1)
        options_layout.addLayout(row2)

    # Path selection

    def browse_input(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select input directory", str(config.INPUT_DIR)
        )
        if directory:
            self.input_edit.setText(directory)

    def browse_output(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select output directory", str(config.OUTPUT_DIR)
        )
        if directory:
            self.output_edit.setText(directory)

    # Scanning and table population

    def scan_files(self):
        input_dir = self.input_edit.text().strip()
        if not input_dir:
            QMessageBox.critical(self, "Error", "Input directory is required.")
            return

        config.INPUT_DIR = Path(input_dir)
        output_dir = self.output_edit.text().strip()
        if output_dir:
            config.OUTPUT_DIR = Path(output_dir)

        try:
            self.plan = prepare_conversion_plan()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Scan failed: {e}")
            return

        self.files_table.setRowCount(0)

        for idx, item in enumerate(self.plan):
            path = Path(item["path"])
            ext = path.suffix.lower() or "unknown"
            status = "convert" if item["needs_conversion"] else "skip"
            audio_summary = get_audio_summary(path)

            self.files_table.insertRow(idx)
            self.files_table.setItem(idx, 0, QTableWidgetItem(item["name"]))
            self.files_table.setItem(idx, 1, QTableWidgetItem(ext))
            self.files_table.setItem(idx, 2, QTableWidgetItem(status))
            self.files_table.setItem(idx, 3, QTableWidgetItem(audio_summary))

        self.details_text.setPlainText(
            "Scan complete. Select a row and click the subtitles button to view subtitle tracks."
        )

    def on_file_row_selected(self, row: int, column: int):
        # When a row is clicked, show basic details.
        if not self.plan:
            return
        if row < 0 or row >= len(self.plan):
            return

        item = self.plan[row]
        path = Path(item["path"])
        info = describe_file(path)
        lines = [
            f"File: {info.get('name', path.name)}",
            f"Path: {info.get('path', str(path))}",
            f"Extension: {info.get('extension', path.suffix.lower())}",
            "",
            "Click the subtitles button to view subtitle tracks.",
        ]
        self.details_text.setPlainText("\n".join(lines))

    # Subtitle viewing

    def get_selected_plan_item(self) -> Optional[Dict[str, Any]]:
        if not self.plan:
            return None
        current_row = self.files_table.currentRow()
        if current_row < 0 or current_row >= len(self.plan):
            return None
        return self.plan[current_row]

    def show_subtitles_clicked(self):
        item = self.get_selected_plan_item()
        if not item:
            QMessageBox.information(
                self, "No selection", "Select a file row first to view subtitles."
            )
            return

        path = Path(item["path"])
        info = describe_file(path)
        subs = info.get("subtitle_streams") or []

        lines: List[str] = []
        lines.append(f"File: {info.get('name', path.name)}")
        lines.append(f"Path: {info.get('path', str(path))}")
        lines.append("")

        if not subs:
            lines.append("No subtitle tracks detected.")
        else:
            lines.append("Subtitle tracks:")
            for s in subs:
                idx_s = s.get("index")
                lang = s.get("language", "und")
                title = s.get("title", "")
                codec = s.get("codec", "")
                line = f"- index {idx_s} [{lang}] {codec}"
                if title:
                    line += f"  {title}"
                lines.append(line)

        self.details_text.setPlainText("\n".join(lines))

    # Conversion

    def run_conversion_clicked(self):
        input_dir = self.input_edit.text().strip()
        output_dir = self.output_edit.text().strip() or None

        if not input_dir:
            QMessageBox.critical(self, "Error", "Input directory is required.")
            return

        args = UIArgs(
            input_dir=input_dir,
            output_dir=output_dir,
            dry_run=self.cb_dry_run.isChecked(),
            same_dir_output=self.cb_same_dir.isChecked(),
            delete_original=self.cb_delete_original.isChecked(),
            max_retries=None,
            high_quality_4k=self.cb_high_4k.isChecked(),
            skip_audio_validation=self.cb_skip_audio.isChecked(),
            no_discord=self.cb_no_discord.isChecked(),
        )

        worker = ConversionWorker(args)
        worker.finished.connect(self.on_conversion_finished)
        worker.error.connect(self.on_conversion_error)

        thread = threading.Thread(target=worker.run, daemon=True)
        thread.start()

        QMessageBox.information(
            self,
            "Started",
            "Conversion started in the background. Check terminal logs for progress.",
        )

    def on_conversion_finished(self, message: str):
        QMessageBox.information(self, "Done", message)

    def on_conversion_error(self, message: str):
        QMessageBox.critical(self, "Error", f"Conversion failed: {message}")


def main_qt():
    app = QApplication(sys.argv)
    window = MediaConverterWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main_qt()