"""Qt (PySide6) user interface for the ETS2 Triple Monitor Configurator."""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from . import __version__
from .core import (
    Settings,
    compute_geometry,
    ets2_user_dir,
    generate_sii,
    preview_text,
    size_from_diagonal,
)

APP_NAME = "ETS2 Triple Monitor Configurator"


def format_number(value: float) -> str:
    return f"{value:g}"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.resize(740, 640)

        self._defaults = Settings()
        self.edits: dict[str, QLineEdit] = {}
        self.labels: dict[str, str] = {}
        # Multiplier from the displayed unit to millimetres.
        self.to_mm = {"distance_mm": 10.0}

        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_screens(), "Screens")
        self.tabs.addTab(self._tab_fov(), "FOV")
        self.tabs.addTab(self._tab_advanced(), "Advanced")

        preview_btn = QPushButton("Preview calculations")
        preview_btn.clicked.connect(self.on_preview)
        generate_btn = QPushButton("Generate multimon_config.sii")
        generate_btn.clicked.connect(self.on_generate)
        generate_btn.setDefault(True)

        buttons = QHBoxLayout()
        buttons.addWidget(preview_btn)
        buttons.addStretch(1)
        buttons.addWidget(generate_btn)

        root = QVBoxLayout()
        root.addWidget(self.tabs)
        root.addLayout(buttons)

        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

    # --------------------------------------------------------
    # UI building helpers
    # --------------------------------------------------------

    def _group(self, title: str, fields: list[tuple[str, str]], cols: int) -> QGroupBox:
        """A titled grid of labelled text fields. Keys match Settings attributes."""
        box = QGroupBox(title)
        grid = QGridLayout(box)
        for i, (key, label) in enumerate(fields):
            row, col = divmod(i, cols)
            grid.addWidget(QLabel(label), row * 2, col)
            shown = getattr(self._defaults, key) / self.to_mm.get(key, 1.0)
            edit = QLineEdit(format_number(shown))
            grid.addWidget(edit, row * 2 + 1, col)
            self.edits[key] = edit
            self.labels[key] = label
        for col in range(cols):
            grid.setColumnStretch(col, 1)
        return box

    @staticmethod
    def _note(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        return label

    @staticmethod
    def _page(*widgets: QWidget) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch(1)
        return page

    # --------------------------------------------------------
    # Tabs
    # --------------------------------------------------------

    def _tab_screens(self) -> QWidget:
        self.size_mode = QComboBox()
        self.size_mode.addItems(
            ["Screen size (width x height in mm)", "Diagonal in inches (16:9)"]
        )
        mode_box = QGroupBox("Size input")
        QVBoxLayout(mode_box).addWidget(self.size_mode)

        self.diag_edit = QLineEdit("27")
        self.diag_group = QGroupBox("Diagonal")
        diag_layout = QGridLayout(self.diag_group)
        diag_layout.addWidget(QLabel("Monitor diagonal (inches, 16:9)"), 0, 0)
        diag_layout.addWidget(self.diag_edit, 1, 0)

        self.size_group = self._group(
            "Visible screen size",
            [
                ("width_mm", "Visible monitor width (mm)"),
                ("height_mm", "Visible monitor height (mm)"),
            ],
            cols=2,
        )
        self.size_mode.currentIndexChanged.connect(self._update_size_mode)
        self._update_size_mode()

        self.bezel_mode = QComboBox()
        self.bezel_mode.addItems(
            ["Combined bezel between two monitors", "Bezel of a single monitor"]
        )
        dims = self._group(
            "Bezel and distance",
            [
                ("bezel_mm", "Bezel (mm)"),
                ("distance_mm", "Eyes → screen distance (cm)"),
            ],
            cols=2,
        )
        dims.layout().addWidget(self.bezel_mode, 2, 0, 1, 2)

        angle = self._group(
            "Side monitor angle",
            [("side_angle", "Physical angle of each side monitor (degrees)")],
            cols=1,
        )
        note = self._note(
            "Example: 54° means the left monitor is rotated +54° and the right "
            "one -54° relative to the center monitor."
        )
        return self._page(
            mode_box, self.diag_group, self.size_group, dims, angle, note,
            *self._camera_widgets(),
        )

    def _update_size_mode(self) -> None:
        by_diagonal = self.size_mode.currentIndex() == 1
        self.diag_group.setVisible(by_diagonal)
        self.size_group.setVisible(not by_diagonal)

    def _camera_widgets(self) -> list[QWidget]:
        offset = self._group(
            "Camera Space Offset",
            [
                ("camera_x", "X - lateral (m)"),
                ("camera_y", "Y - vertical (m)"),
                ("camera_z", "Z - depth (m)"),
            ],
            cols=3,
        )
        note = self._note(
            "Camera offset. Z moves the camera closer to / farther from the "
            "game's reference point."
        )
        orientation = self._group(
            "Orientation",
            [("pitch", "Pitch (°)"), ("roll", "Roll (°)")],
            cols=2,
        )
        return [note, offset, orientation]

    def _tab_fov(self) -> QWidget:
        self.auto_fov = QCheckBox(
            "Calculate FOV automatically from monitor size and distance"
        )
        self.auto_fov.setChecked(self._defaults.auto_fov)

        self.manual_fov = self._group(
            "Manual FOV (used only when automatic FOV is off)",
            [
                ("fov_h", "Horizontal FOV per monitor (°)"),
                ("fov_v", "Vertical FOV per monitor (°)"),
            ],
            cols=2,
        )
        self.auto_fov.toggled.connect(lambda on: self.manual_fov.setEnabled(not on))
        self.manual_fov.setEnabled(not self.auto_fov.isChecked())

        relative = self._group(
            "Relative FOV offsets",
            [
                ("center_h_rel", "Center H"),
                ("left_h_rel", "Left H"),
                ("right_h_rel", "Right H"),
                ("center_v_rel", "Center V"),
                ("left_v_rel", "Left V"),
                ("right_v_rel", "Right V"),
            ],
            cols=3,
        )
        note = self._note(
            "Relative offsets should normally stay at 0. They allow an "
            "individual compensation per monitor."
        )
        return self._page(self.auto_fov, self.manual_fov, relative, note)

    def _tab_advanced(self) -> QWidget:
        render = QGroupBox("Render")
        render_layout = QVBoxLayout(render)
        self.render_interior = QCheckBox("Render interior")
        self.render_interior.setChecked(self._defaults.render_interior)
        self.render_exterior = QCheckBox("Render exterior")
        self.render_exterior.setChecked(self._defaults.render_exterior)
        render_layout.addWidget(self.render_interior)
        render_layout.addWidget(self.render_exterior)

        frustum = self._group(
            "Frustum Subrect",
            [
                ("frustum_x", "X"),
                ("frustum_y", "Y"),
                ("frustum_w", "Width"),
                ("frustum_h", "Height"),
            ],
            cols=2,
        )
        note = self._note(
            "For a normal triple-monitor setup use X=0, Y=0, Width=1 and Height=1."
        )
        return self._page(render, frustum, note)

    # --------------------------------------------------------
    # Reading + validating the form
    # --------------------------------------------------------

    def read_settings(self) -> Settings:
        s = Settings()
        for key, edit in self.edits.items():
            if self.auto_fov.isChecked() and key in ("fov_h", "fov_v"):
                continue  # manual FOV is ignored while automatic FOV is on
            text = edit.text().strip().replace(",", ".")
            try:
                value = float(text)
            except ValueError:
                value = math.nan
            if not math.isfinite(value):
                raise ValueError(f"{self.labels[key]} must be a valid number.")
            setattr(s, key, value * self.to_mm.get(key, 1.0))

        if self.size_mode.currentIndex() == 1:
            try:
                diagonal = float(self.diag_edit.text().strip().replace(",", "."))
            except ValueError:
                diagonal = math.nan
            if not math.isfinite(diagonal) or diagonal <= 0:
                raise ValueError("The diagonal must be a number greater than 0.")
            s.width_mm, s.height_mm = size_from_diagonal(diagonal)
        if self.bezel_mode.currentIndex() == 1:
            s.bezel_mm *= 2  # two adjacent bezels sit between monitors

        s.auto_fov = self.auto_fov.isChecked()
        s.render_interior = self.render_interior.isChecked()
        s.render_exterior = self.render_exterior.isChecked()
        s.validate()
        return s

    # --------------------------------------------------------
    # Actions
    # --------------------------------------------------------

    def on_preview(self) -> None:
        try:
            s = self.read_settings()
            text = preview_text(s, compute_geometry(s))
        except ValueError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Preview")
        view = QPlainTextEdit(text)
        view.setReadOnly(True)
        view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        layout = QVBoxLayout(dialog)
        layout.addWidget(view)
        dialog.resize(420, 560)
        dialog.exec()

    def on_generate(self) -> None:
        try:
            s = self.read_settings()
            geometry = compute_geometry(s)
            content = generate_sii(s)
        except ValueError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        documents = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        start_dir = ets2_user_dir(Path(documents) if documents else None)

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save ETS2 configuration",
            str(start_dir / "multimon_config.sii"),
            "SII files (*.sii);;All files (*)",
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as exc:
            QMessageBox.critical(self, "Error saving file", str(exc))
            return

        QMessageBox.information(
            self,
            "Configuration generated",
            "File generated successfully.\n\n"
            f"Horizontal FOV: {geometry.fov_h:.2f}°\n"
            f"Vertical FOV: {geometry.fov_v:.2f}°\n\n"
            f"Left heading: +{geometry.left_heading:.2f}°\n"
            f"Right heading: {geometry.right_heading:.2f}°\n\n"
            f"File:\n{path}",
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
