"""Door colour calibration: click the orange door, then the blue one, check the masks."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QMouseEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from aniimo_overlay import paths
from aniimo_overlay.capture.game_window import capture_game
from aniimo_overlay.detection.annotate import BLUE_BGR, ORANGE_BGR, annotate
from aniimo_overlay.detection.calibrate import (
    crop_template,
    hsv_range_from_point,
    read_image,
    save_template,
)
from aniimo_overlay.detection.direction import compute_direction
from aniimo_overlay.detection.doors import (
    DoorParams,
    HsvRange,
    clean_mask,
    detect_doors,
    find_blobs,
    hsv_mask,
)
from aniimo_overlay.gui.tab_detection import IMAGE_FILTER
from aniimo_overlay.gui.widgets import bgr_to_pixmap

if TYPE_CHECKING:
    from aniimo_overlay.app import App

CAPTURE_DELAY_MS = 300


class ClickableImage(QLabel):
    """Shows an image scaled to fit; reports clicks in image coordinates."""

    clicked = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("preview")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(QSize(480, 280))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._source: QPixmap | None = None
        self._image_size = QSize()

    def set_image(self, image: np.ndarray) -> None:
        self._source = bgr_to_pixmap(image)
        self._image_size = QSize(image.shape[1], image.shape[0])
        self._rescale()

    def _rescale(self) -> None:
        if self._source is not None:
            self.setPixmap(
                self._source.scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._rescale()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pixmap = self.pixmap()
        if self._source is None or pixmap is None or pixmap.isNull():
            return
        offset = QPoint(
            (self.width() - pixmap.width()) // 2, (self.height() - pixmap.height()) // 2
        )
        pos = event.position().toPoint() - offset
        if not (0 <= pos.x() < pixmap.width() and 0 <= pos.y() < pixmap.height()):
            return
        scale = self._image_size.width() / pixmap.width()
        self.clicked.emit(int(pos.x() * scale), int(pos.y() * scale))


class CalibrationDialog(QDialog):
    def __init__(self, app: App, image: np.ndarray | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app = app
        self.setWindowTitle(self.tr("Calibrer les couleurs des portes"))
        self.resize(760, 600)
        self.image: np.ndarray | None = None
        self.points: dict[str, tuple[int, int]] = {}
        self.ranges: dict[str, HsvRange] = {}

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        source_row = QHBoxLayout()
        capture = QPushButton(self.tr("Capturer l'écran"))
        capture.clicked.connect(self._capture)
        open_file = QPushButton(self.tr("Ouvrir une image…"))
        open_file.clicked.connect(self._open)
        source_row.addWidget(capture)
        source_row.addWidget(open_file)
        source_row.addStretch(1)
        layout.addLayout(source_row)

        self.instructions = QLabel()
        self.instructions.setWordWrap(True)
        layout.addWidget(self.instructions)

        self.view = ClickableImage()
        self.view.clicked.connect(self._on_click)
        layout.addWidget(self.view, 1)

        self.save_templates = QCheckBox(
            self.tr("Enregistrer aussi les icônes des portes comme modèles (détection de secours)")
        )
        layout.addWidget(self.save_templates)

        buttons = QHBoxLayout()
        self.restart = QPushButton(self.tr("Recommencer"))
        self.restart.clicked.connect(self._reset_points)
        self.toggle_view = QPushButton(self.tr("Voir l'image"))
        self.toggle_view.setCheckable(True)
        self.toggle_view.toggled.connect(self._update_view)
        cancel = QPushButton(self.tr("Annuler"))
        cancel.clicked.connect(self.reject)
        self.validate = QPushButton(self.tr("Valider"))
        self.validate.setDefault(True)
        self.validate.clicked.connect(self._validate)
        buttons.addWidget(self.restart)
        buttons.addWidget(self.toggle_view)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(self.validate)
        layout.addLayout(buttons)

        if image is not None:
            self._set_image(image)
        else:
            self._reset_points()
            self.instructions.setText(
                self.tr(
                    "Ouvre la carte en jeu puis clique sur « Capturer l'écran », ou ouvre une capture d'écran du jeu."
                )
            )

    # --- image source ---------------------------------------------------------------

    def _capture(self) -> None:
        # Make our windows invisible during the capture. The dialog is not hidden:
        # hiding a dialog would end its exec() loop.
        windows = [w for w in (self, self.app.control) if w.isVisible()]
        opacities = [w.windowOpacity() for w in windows]
        for w in windows:
            w.setWindowOpacity(0.0)
        overlay_visible = self.app.overlay.isVisible()
        if overlay_visible:
            self.app.overlay.hide()
        QApplication.processEvents()

        def grab() -> None:
            c = self.app.cfg.capture
            try:
                shot = capture_game(c.game_window_title, c.monitor, c.roi)
            except Exception as exc:
                self.instructions.setText(self.tr("Capture impossible : %s") % exc)
                shot = None
            finally:
                for w, opacity in zip(windows, opacities, strict=True):
                    w.setWindowOpacity(opacity)
                if overlay_visible:
                    self.app.overlay.show_overlay()
            if shot is not None:
                self._set_image(shot.image)

        QTimer.singleShot(CAPTURE_DELAY_MS, grab)

    def _open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Choisir une capture du jeu"), "", IMAGE_FILTER
        )
        if path:
            try:
                self._set_image(read_image(Path(path)))
            except ValueError as exc:
                self.instructions.setText(str(exc))

    def _set_image(self, image: np.ndarray) -> None:
        self.image = image
        self._reset_points()

    # --- clicks ---------------------------------------------------------------------

    def _reset_points(self) -> None:
        self.points.clear()
        self.ranges.clear()
        self.toggle_view.blockSignals(True)
        self.toggle_view.setChecked(False)
        self.toggle_view.blockSignals(False)
        self.toggle_view.setEnabled(False)
        self.validate.setEnabled(False)
        if self.image is not None:
            self.view.set_image(self.image)
            self.instructions.setText(
                self.tr("1. Clique au centre de la porte ORANGE (entrée principale).")
            )

    def _on_click(self, x: int, y: int) -> None:
        if self.image is None or len(self.points) >= 2:
            return
        name = "orange" if "orange" not in self.points else "blue"
        try:
            rng = hsv_range_from_point(self.image, (x, y))
        except ValueError as exc:
            self.instructions.setText(str(exc))
            return
        self.points[name] = (x, y)
        self.ranges[name] = rng
        if name == "orange":
            marked = self.image.copy()
            cv2.circle(marked, (x, y), 14, ORANGE_BGR, 3)
            self.view.set_image(marked)
            self.instructions.setText(
                self.tr("2. Clique au centre de la porte BLEUE (entrée secondaire).")
            )
            return
        self.toggle_view.setEnabled(True)
        self.validate.setEnabled(True)
        self._update_view()

    def _params(self) -> DoorParams:
        return DoorParams(orange=self.ranges["orange"], blue=self.ranges["blue"])

    def _update_view(self) -> None:
        if self.image is None or len(self.ranges) < 2:
            return
        params = self._params()
        detection = detect_doors(self.image, params, debug=True)
        direction = compute_direction(detection.orange, detection.blue) if detection.found else None
        if self.toggle_view.isChecked():
            self.toggle_view.setText(self.tr("Voir les masques"))
            self.view.set_image(annotate(self.image, detection, direction))
        else:
            self.toggle_view.setText(self.tr("Voir l'image"))
            preview = (self.image * 0.25).astype(np.uint8)
            preview[detection.masks["orange"] > 0] = ORANGE_BGR
            preview[detection.masks["blue"] > 0] = BLUE_BGR
            self.view.set_image(annotate(preview, detection, direction))
        if direction is not None:
            self.instructions.setText(
                self.tr(
                    "Masques : seules les portes devraient apparaître en couleur. Résultat : %s (confiance %.2f). Valide si c'est correct."
                )
                % (direction.label_fr, detection.confidence)
            )
        else:
            self.instructions.setText(
                self.tr(
                    "Les portes ne sont pas reconnues avec ces couleurs. Recommence en cliquant bien au centre des portes."
                )
            )

    # --- save -----------------------------------------------------------------------

    def _template_rect(self, name: str) -> tuple[int, int, int, int]:
        x, y = self.points[name]
        mask = clean_mask(hsv_mask(cv2.cvtColor(self.image, cv2.COLOR_BGR2HSV), self.ranges[name]))
        for blob in find_blobs(mask, self._params()):
            bx, by, bw, bh = blob.bbox
            if bx - 4 <= x <= bx + bw + 4 and by - 4 <= y <= by + bh + 4:
                pad = max(3, bw // 6)
                return bx - pad, by - pad, bw + 2 * pad, bh + 2 * pad
        return x - 12, y - 12, 24, 24

    def _validate(self) -> None:
        self.app.set_hsv(self.ranges["orange"], self.ranges["blue"])
        if self.save_templates.isChecked() and self.image is not None:
            for name in ("orange", "blue"):
                save_template(
                    crop_template(self.image, self._template_rect(name)),
                    name,
                    paths.templates_dir(),
                )
            self.app.reload_templates()
        self.accept()
