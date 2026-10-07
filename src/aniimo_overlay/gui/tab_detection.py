"""Detection tab: auto mode, threshold, test on screen / image with annotated preview."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from aniimo_overlay.detect_task import DetectionOutcome
from aniimo_overlay.detection.annotate import annotate
from aniimo_overlay.detection.calibrate import read_image
from aniimo_overlay.gui.tab_display import section
from aniimo_overlay.gui.widgets import ValueSlider, bgr_to_pixmap

if TYPE_CHECKING:
    from aniimo_overlay.app import App

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
PREVIEW_SIZE = QSize(460, 260)


class DetectionTab(QWidget):
    def __init__(self, app: App) -> None:
        super().__init__()
        self.app = app
        self.last_image = None  # last analysed image, reused by the calibration dialog

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 14, 4, 4)
        layout.setSpacing(10)

        layout.addWidget(section(self.tr("Déclenchement")))
        self.auto = QCheckBox(self.tr("Détection automatique"))
        self.auto.toggled.connect(app.set_auto)
        layout.addWidget(self.auto)
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        self.interval = QDoubleSpinBox()
        self.interval.setRange(0.5, 5.0)
        self.interval.setSingleStep(0.5)
        self.interval.setSuffix(" s")
        self.interval.setDecimals(1)
        self.interval.valueChanged.connect(app.set_interval)
        self.threshold = ValueSlider(0, 100, 5)
        self.threshold.value_changed.connect(lambda v: app.set_min_confidence(v / 100))
        self.title = QLineEdit()
        self.title.setPlaceholderText("Aniimo")
        self.title.editingFinished.connect(
            lambda: app.set_game_title(self.title.text() or "Aniimo")
        )
        form.addRow(self.tr("Intervalle"), self.interval)
        form.addRow(self.tr("Seuil de confiance"), self.threshold)
        form.addRow(self.tr("Titre de la fenêtre du jeu"), self.title)
        layout.addLayout(form)

        layout.addSpacing(4)
        layout.addWidget(section(self.tr("Tester")))
        row = QHBoxLayout()
        self.test_screen = QPushButton(self.tr("Tester sur l'écran actuel"))
        self.test_screen.clicked.connect(self._test_screen)
        self.test_file = QPushButton(self.tr("Tester sur une image…"))
        self.test_file.clicked.connect(self._test_file)
        row.addWidget(self.test_screen)
        row.addWidget(self.test_file)
        layout.addLayout(row)

        self.preview = QLabel(self.tr("L'aperçu de la détection s'affichera ici."))
        self.preview.setObjectName("preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(180)
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview)
        self.result = QLabel()
        self.result.setWordWrap(True)
        layout.addWidget(self.result)

        layout.addSpacing(4)
        layout.addWidget(section(self.tr("Couleurs des portes")))
        row = QHBoxLayout()
        calibrate = QPushButton(self.tr("Calibrer les couleurs des portes"))
        calibrate.clicked.connect(self._calibrate)
        reset = QPushButton(self.tr("Couleurs par défaut"))
        reset.clicked.connect(self._reset_colors)
        row.addWidget(calibrate)
        row.addWidget(reset)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)

        app.test_done.connect(self._show_outcome)

    def _set_busy(self, busy: bool) -> None:
        self.test_screen.setEnabled(not busy)
        self.test_file.setEnabled(not busy)
        if busy:
            self.result.setText(self.tr("Analyse en cours…"))

    def _test_screen(self) -> None:
        if self.app.detect_now("test"):
            self._set_busy(True)
        else:
            self.result.setText(self.tr("Une détection est déjà en cours, réessaie."))

    def _test_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Choisir une capture du jeu"), "", IMAGE_FILTER
        )
        if not path:
            return
        try:
            image = read_image(Path(path))
        except ValueError as exc:
            self.result.setText(str(exc))
            return
        if self.app.detect_now("test", image=image):
            self._set_busy(True)

    def _show_outcome(self, outcome: DetectionOutcome) -> None:
        self._set_busy(False)
        if outcome.image is not None and outcome.detection is not None:
            self.last_image = outcome.image
            annotated = annotate(outcome.image, outcome.detection, outcome.direction)
            pixmap = bgr_to_pixmap(annotated).scaled(
                PREVIEW_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview.setPixmap(pixmap)
        text = outcome.describe()
        if outcome.direction is not None:
            text += f" — touche {outcome.direction.numpad}, angle {outcome.direction.angle_deg:.0f}°, distance {outcome.direction.distance:.0f} px"
        self.result.setText(text)

    def _calibrate(self) -> None:
        from aniimo_overlay.gui.calibration_dialog import CalibrationDialog

        dialog = CalibrationDialog(self.app, self.last_image, self)
        if dialog.exec():
            self.app.control.show_message(self.tr("Couleurs des portes enregistrées."))

    def _reset_colors(self) -> None:
        self.app.reset_hsv()
        self.app.control.show_message(self.tr("Couleurs des portes remises par défaut."))

    def refresh(self) -> None:
        d = self.app.cfg.detection
        for widget, setter, value in (
            (self.auto, self.auto.setChecked, d.auto),
            (self.interval, self.interval.setValue, d.interval_s),
        ):
            widget.blockSignals(True)
            setter(value)
            widget.blockSignals(False)
        self.threshold.set_value(round(d.min_confidence * 100))
        if not self.title.hasFocus():
            self.title.setText(self.app.cfg.capture.game_window_title)
