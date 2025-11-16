

"""
ui_app.py
PyQt6 based UI for the Media Converter project.

Features:
- Hero style empty state before first scan.
- Select input and output directories.
- Scan for videos and show a table of files.
- Show file type, planned status (convert or skip), and audio summary per file.
- Button to view subtitles for the selected file.
- Toggle behavior flags.
- Run conversion using main.run(...) in a background thread.
- Status panel with log and progress.
- Color coded badges in the Status column.
- Persistent column widths for the files table.
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
    QStackedWidget,
    QProgressBar,
)
from PyQt6.QtCore import QObject, pyqtSignal, QSettings, Qt

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
    Example: "eac3 5.1 (eng), aac 2.0 (eng)".
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

        self.settings = QSettings("GSteeze", "MediaConverter")
        self.plan: List[Dict[str, Any]] = []

        self.setWindowTitle("Media Converter")
        self.resize(1100, 750)

        # Dark theme styling for the whole window.
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
            background-color: #0891b2;
            color: #e5e7eb;
            border-radius: 6px;
            padding: 8px 14px;
        }
        QPushButton:hover {
            background-color: #06b6d4;
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
        QProgressBar {
            border: 1px solid #1f2937;
            background-color: #020617;
            color: #e5e7eb;
        }
        QProgressBar::chunk {
            background-color: #22c55e;
        }
        """
        )

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        # Header bar.
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 10, 10, 10)

        # Simple icon placeholder (text based).
        icon_label = QLabel("🎬")
        icon_label.setStyleSheet("font-size: 26px;")
        header_layout.addWidget(icon_label)

        title_block = QWidget()
        title_layout = QVBoxLayout(title_block)
        title_layout.setContentsMargins(8, 0, 0, 0)

        title_label = QLabel("Library Scanner")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #38bdf8;")
        subtitle_label = QLabel("Scan and manage your video library")
        subtitle_label.setStyleSheet("font-size: 11px; color: #9ca3af;")
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)

        header_layout.addWidget(title_block)
        header_layout.addStretch()

        self.scan_button_header = QPushButton("+ Scan Folder")
        self.scan_button_header.clicked.connect(self.scan_from_header)
        header_layout.addWidget(self.scan_button_header)

        root_layout.addWidget(header_widget)

        # Paths section (advanced controls, always visible under header).
        paths_group = QGroupBox("Paths")
        root_layout.addWidget(paths_group)
        paths_layout = QVBoxLayout()
        paths_group.setLayout(paths_layout)

        # Input row.
        input_row = QHBoxLayout()
        input_label = QLabel("Input directory")
        self.input_edit = QLineEdit(str(config.INPUT_DIR))
        input_browse = QPushButton("Browse")
        input_browse.clicked.connect(self.browse_input)
        input_row.addWidget(input_label)
        input_row.addWidget(self.input_edit)
        input_row.addWidget(input_browse)
        paths_layout.addLayout(input_row)

        # Output row.
        output_row = QHBoxLayout()
        output_label = QLabel("Output directory")
        self.output_edit = QLineEdit(str(config.OUTPUT_DIR))
        output_browse = QPushButton("Browse")
        output_browse.clicked.connect(self.browse_output)
        output_row.addWidget(output_label)
        output_row.addWidget(self.output_edit)
        output_row.addWidget(output_browse)
        paths_layout.addLayout(output_row)

        # Secondary actions row (Scan and Run) under paths for power users.
        actions_row = QHBoxLayout()
        self.scan_button = QPushButton("Scan")
        self.scan_button.clicked.connect(self.scan_files)
        self.run_button = QPushButton("Run conversion")
        self.run_button.clicked.connect(self.run_conversion_clicked)
        actions_row.addWidget(self.scan_button)
        actions_row.addWidget(self.run_button)
        actions_row.addStretch()
        paths_layout.addLayout(actions_row)

        # Stacked widget for hero empty state vs library view.
        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack, 1)

        # Page 0: hero empty state.
        self.empty_page = self._build_empty_page()
        self.stack.addWidget(self.empty_page)

        # Page 1: library view (table, details, options).
        self.library_page = self._build_library_page()
        self.stack.addWidget(self.library_page)

        # Status and log panel (always visible).
        status_group = QGroupBox("Status")
        root_layout.addWidget(status_group)
        status_layout = QVBoxLayout()
        status_group.setLayout(status_layout)

        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        status_layout.addWidget(self.progress_bar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(120)
        status_layout.addWidget(self.log_text)

        # Show hero empty state by default.
        self.show_empty_state()

    # Page builders.

    def _build_empty_page(self) -> QWidget:
        """Build the hero style empty state page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 40, 0, 0)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

        icon_box = QWidget()
        icon_box_layout = QVBoxLayout(icon_box)
        icon_box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(
            "background-color: #020617; border-radius: 24px; border: 1px solid #1f2937;"
        )
        icon_label = QLabel("📁")
        icon_label.setStyleSheet("font-size: 40px;")
        icon_box_layout.addWidget(icon_label)

        title = QLabel("No folders scanned yet")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #e5e7eb;")
        subtitle = QLabel(
            "Click the Scan Folder button above to start scanning your video library."
        )
        subtitle.setStyleSheet("font-size: 11px; color: #9ca3af;")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        center_layout.addWidget(icon_box)
        center_layout.addSpacing(16)
        center_layout.addWidget(title)
        center_layout.addWidget(subtitle)

        layout.addStretch()
        layout.addWidget(center)
        layout.addStretch()

        return page

    def _build_library_page(self) -> QWidget:
        """Build the main library view with table, details, and options."""
        page = QWidget()
        layout = QVBoxLayout(page)

        # Middle area: files table and details.
        middle_layout = QHBoxLayout()
        layout.addLayout(middle_layout, 1)

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

        header = self.files_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionsMovable(True)
        header.setHighlightSections(False)
        self.restore_table_settings()
        header.sectionResized.connect(self.on_column_resized)

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

        # Options section.
        options_group = QGroupBox("Options")
        layout.addWidget(options_group)
        options_layout = QVBoxLayout()
        options_group.setLayout(options_layout)

        row1 = QHBoxLayout()
        row2 = QHBoxLayout()

        self.cb_dry_run = QCheckBox("Dry run only")
        self.cb_same_dir = QCheckBox("Output next to source directory")
        self.cb_same_dir.setChecked(config.SAME_DIR_OUTPUT)
        self.cb_delete_original = QCheckBox("Delete original after conversion")
        self.cb_delete_original.setChecked(config.DELETE_ORIGINAL_AFTER_CONVERT)

        row1.addWidget(self.cb_dry_run)
        row1.addWidget(self.cb_same_dir)
        row1.addWidget(self.cb_delete_original)
        row1.addStretch()

        self.cb_high_4k = QCheckBox("High quality mode for 4K")
        self.cb_high_4k.setChecked(getattr(config, "HIGH_QUALITY_FOR_4K", False))
        self.cb_skip_audio = QCheckBox("Skip audio validation")
        self.cb_no_discord = QCheckBox("Disable Discord for this run")

        row2.addWidget(self.cb_high_4k)
        row2.addWidget(self.cb_skip_audio)
        row2.addWidget(self.cb_no_discord)
        row2.addStretch()

        options_layout.addLayout(row1)
        options_layout.addLayout(row2)

        return page

    # State helpers.

    def show_empty_state(self):
        self.stack.setCurrentWidget(self.empty_page)
        self.details_text = None
        self.files_table = None

    def show_library_view(self):
        self.stack.setCurrentWidget(self.library_page)

    # Logging and settings helpers.

    def log_message(self, message: str):
        """Append a line to the log panel and update status label."""
        if hasattr(self, "log_text") and self.log_text is not None:
            self.log_text.append(message)
        if hasattr(self, "status_label") and self.status_label is not None:
            self.status_label.setText(message)

    def restore_table_settings(self):
        """Restore column widths from QSettings if present."""
        widths = self.settings.value("files_table/column_widths")
        if not widths:
            return
        try:
            widths = [int(w) for w in widths]
        except Exception:
            return
        header = self.files_table.horizontalHeader()
        for idx, w in enumerate(widths):
            if idx < self.files_table.columnCount():
                header.resizeSection(idx, w)

    def on_column_resized(self, index: int, old_size: int, new_size: int):
        """Persist column widths on resize."""
        header = self.files_table.horizontalHeader()
        widths = [header.sectionSize(i) for i in range(self.files_table.columnCount())]
        self.settings.setValue("files_table/column_widths", widths)

    # Path selection.

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

    def scan_from_header(self):
        """Header button for Scan Folder, uses same logic as Scan."""
        self.scan_files()

    # Scanning and table population.

    def ensure_library_widgets(self):
        """
        Ensure table and details widgets are available.
        Needed because hero view is the initial page.
        """
        if self.stack.currentWidget() is not self.library_page:
            self.stack.setCurrentWidget(self.library_page)

    def scan_files(self):
        input_dir = self.input_edit.text().strip()
        if not input_dir:
            QMessageBox.critical(self, "Error", "Input directory is required.")
            return

        self.log_message("Scanning input directory...")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        config.INPUT_DIR = Path(input_dir)
        output_dir = self.output_edit.text().strip()
        if output_dir:
            config.OUTPUT_DIR = Path(output_dir)

        try:
            self.plan = prepare_conversion_plan()
            self.log_message("Scan complete. Building file table...")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Scan failed: {e}")
            self.log_message(f"Scan failed: {e}")
            return

        # Switch to library view now that we have a plan.
        self.ensure_library_widgets()

        self.files_table.setRowCount(0)

        for idx, item in enumerate(self.plan):
            path = Path(item["path"])
            ext = path.suffix.lower() or "unknown"
            status = "convert" if item["needs_conversion"] else "skip"
            audio_summary = get_audio_summary(path)

            self.files_table.insertRow(idx)
            self.files_table.setItem(idx, 0, QTableWidgetItem(item["name"]))
            self.files_table.setItem(idx, 1, QTableWidgetItem(ext))

            status_item = QTableWidgetItem("CONVERT" if item["needs_conversion"] else "SKIP")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            audio_item = QTableWidgetItem(audio_summary)

            if item["needs_conversion"]:
                status_item.setBackground(Qt.GlobalColor.darkBlue)
                status_item.setForeground(Qt.GlobalColor.white)
            else:
                status_item.setBackground(Qt.GlobalColor.darkGray)
                status_item.setForeground(Qt.GlobalColor.white)

            self.files_table.setItem(idx, 2, status_item)
            self.files_table.setItem(idx, 3, audio_item)

        total = len(self.plan)
        self.details_text.setPlainText(
            "Scan complete. Select a row and click the subtitles button to view subtitle tracks."
        )
        self.progress_bar.setValue(100 if total > 0 else 0)
        self.log_message(f"Scan complete. {total} files found.")

    def on_file_row_selected(self, row: int, column: int):
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

    # Subtitle viewing.

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

    # Conversion.

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

        self.progress_bar.setRange(0, 0)
        self.log_message("Starting conversion run...")

        thread = threading.Thread(target=worker.run, daemon=True)
        thread.start()

        QMessageBox.information(
            self,
            "Started",
            "Conversion started in the background. Check terminal logs for progress.",
        )

    def on_conversion_finished(self, message: str):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.log_message(message)
        QMessageBox.information(self, "Done", message)

    def on_conversion_error(self, message: str):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.log_message(f"Conversion failed: {message}")
        QMessageBox.critical(self, "Error", f"Conversion failed: {message}")

    # Close handling.

    def closeEvent(self, event):
        """Ensure column widths are persisted on close."""
        if hasattr(self, "files_table") and self.files_table is not None:
            header = self.files_table.horizontalHeader()
            widths = [header.sectionSize(i) for i in range(self.files_table.columnCount())]
            self.settings.setValue("files_table/column_widths", widths)
        super().closeEvent(event)


def main_qt():
    app = QApplication(sys.argv)
    window = MediaConverterWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main_qt()