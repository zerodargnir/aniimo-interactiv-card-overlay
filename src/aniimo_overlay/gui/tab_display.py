"""Display tab: opacity, page zoom, overlay size and position."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QRect
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from aniimo_overlay.gui.widgets import ValueSlider

if TYPE_CHECKING:
    from aniimo_overlay.app import App


def section(title: str) -> QLabel:
    label = QLabel(title.upper())
    label.setObjectName("sectionTitle")
    return label


class DisplayTab(QWidget):
    def __init__(self, app: App) -> None:
        super().__init__()
        self.app = app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 14, 4, 4)
        layout.setSpacing(10)

        layout.addWidget(section(self.tr("Apparence")))
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        self.opacity = ValueSlider(20, 100, 5)
        self.opacity.value_changed.connect(lambda v: app.set_opacity(v / 100))
        self.zoom = ValueSlider(50, 200, 5)
        self.zoom.value_changed.connect(lambda v: app.set_zoom(v / 100))
        form.addRow(self.tr("Opacité"), self.opacity)
        form.addRow(self.tr("Zoom de la page"), self.zoom)
        layout.addLayout(form)

        layout.addSpacing(4)
        layout.addWidget(section(self.tr("Taille et position")))
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        self.width_box = self._spin(200, 10000)
        self.height_box = self._spin(150, 10000)
        self.x_box = self._spin(-20000, 20000)
        self.y_box = self._spin(-20000, 20000)
        grid.addWidget(QLabel(self.tr("Largeur")), 0, 0)
        grid.addWidget(self.width_box, 0, 1)
        grid.addWidget(QLabel(self.tr("Hauteur")), 0, 2)
        grid.addWidget(self.height_box, 0, 3)
        grid.addWidget(QLabel("X"), 1, 0)
        grid.addWidget(self.x_box, 1, 1)
        grid.addWidget(QLabel("Y"), 1, 2)
        grid.addWidget(self.y_box, 1, 3)
        layout.addLayout(grid)

        snap_row = QHBoxLayout()
        snap_row.addWidget(QLabel(self.tr("Placer dans un coin de")))
        self.snap_target = QComboBox()
        self.snap_target.addItem(self.tr("l'écran"), "screen")
        if sys.platform == "win32":
            self.snap_target.addItem(self.tr("la fenêtre du jeu"), "game")
        snap_row.addWidget(self.snap_target, 1)
        layout.addLayout(snap_row)

        corners = QHBoxLayout()
        for corner, text in (
            ("tl", "↖ Haut-gauche"),
            ("tr", "↗ Haut-droite"),
            ("bl", "↙ Bas-gauche"),
            ("br", "↘ Bas-droite"),
        ):
            button = QPushButton(self.tr(text))
            button.clicked.connect(
                lambda _=False, c=corner: app.snap_overlay(c, self.snap_target.currentData())
            )
            corners.addWidget(button)
        layout.addLayout(corners)

        reset = QPushButton(self.tr("Réinitialiser la position"))
        reset.clicked.connect(app.reset_position)
        reset_row = QHBoxLayout()
        reset_row.addWidget(reset)
        reset_row.addStretch(1)
        layout.addLayout(reset_row)

        layout.addSpacing(4)
        layout.addWidget(section(self.tr("Démarrage")))
        self.start_visible = QCheckBox(self.tr("Afficher l'overlay au démarrage"))
        self.start_visible.toggled.connect(app.set_start_visible)
        layout.addWidget(self.start_visible)
        layout.addStretch(1)

        for box in (self.width_box, self.height_box, self.x_box, self.y_box):
            box.editingFinished.connect(self._apply_geometry)

    @staticmethod
    def _spin(minimum: int, maximum: int) -> QSpinBox:
        box = QSpinBox()
        box.setRange(minimum, maximum)
        box.setSuffix(" px")
        box.setKeyboardTracking(False)
        return box

    def _apply_geometry(self) -> None:
        rect = QRect(
            self.x_box.value(), self.y_box.value(), self.width_box.value(), self.height_box.value()
        )
        if rect != self.app.overlay.geometry():
            self.app.set_overlay_geometry(rect)

    def refresh(self) -> None:
        w = self.app.cfg.window
        self.opacity.set_value(round(w.opacity * 100))
        self.zoom.set_value(round(w.zoom * 100))
        for box, value in (
            (self.width_box, w.width),
            (self.height_box, w.height),
            (self.x_box, w.x),
            (self.y_box, w.y),
        ):
            if not box.hasFocus():
                box.blockSignals(True)
                box.setValue(value)
                box.blockSignals(False)
        self.start_visible.blockSignals(True)
        self.start_visible.setChecked(w.start_visible)
        self.start_visible.blockSignals(False)
