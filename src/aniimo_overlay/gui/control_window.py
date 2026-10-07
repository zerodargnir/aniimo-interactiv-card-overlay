"""Main control window: status header, big buttons, settings tabs."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from aniimo_overlay import APP_NAME, __version__, paths
from aniimo_overlay.gui.tab_about import AboutTab
from aniimo_overlay.gui.tab_detection import DetectionTab
from aniimo_overlay.gui.tab_display import DisplayTab
from aniimo_overlay.gui.tab_hotkeys import HotkeysTab
from aniimo_overlay.gui.tab_site import SiteTab
from aniimo_overlay.gui.widgets import StatusLight
from aniimo_overlay.hotkeys import hotkey_label

if TYPE_CHECKING:
    from aniimo_overlay.app import App

MESSAGE_MS = 6000


def load_stylesheet() -> str:
    try:
        qss = paths.resource_path("style.qss").read_text(encoding="utf-8")
    except OSError:
        return ""
    return qss.replace("%CHECK%", paths.resource_path("check.svg").as_posix())


def scrollable(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(widget)
    return area


class ControlWindow(QWidget):
    def __init__(self, app: App) -> None:
        super().__init__()
        self.app = app
        self.allow_close = False
        self.setWindowTitle(f"{APP_NAME}")
        self.resize(520, 640)
        self.setMinimumSize(460, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # Title row
        title_row = QHBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("appTitle")
        version = QLabel(f"v{__version__}")
        version.setObjectName("appVersion")
        quit_button = QPushButton(self.tr("Quitter"))
        quit_button.setObjectName("flatButton")
        quit_button.clicked.connect(app.quit)
        title_row.addWidget(title)
        title_row.addWidget(version, 0, Qt.AlignmentFlag.AlignBottom)
        title_row.addStretch(1)
        title_row.addWidget(quit_button)
        root.addLayout(title_row)

        # Header: status lights + big buttons
        header = QFrame()
        header.setObjectName("header")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(6)
        self.light_overlay = StatusLight(self.tr("Overlay"))
        self.light_mode = StatusLight(self.tr("Mode"))
        self.light_game = StatusLight(self.tr("Jeu"))
        self.light_detection = StatusLight(self.tr("Dernière détection"))
        lights = QGridLayout()
        lights.setHorizontalSpacing(16)
        lights.setVerticalSpacing(4)
        lights.addWidget(self.light_overlay, 0, 0)
        lights.addWidget(self.light_mode, 0, 1)
        lights.addWidget(self.light_game, 1, 0, 1, 2)
        lights.addWidget(self.light_detection, 2, 0, 1, 2)
        header_layout.addLayout(lights)

        buttons = QGridLayout()
        buttons.setHorizontalSpacing(8)
        buttons.setVerticalSpacing(2)
        self.btn_visible = QPushButton(self.tr("Afficher l'overlay"))
        self.btn_interactive = QPushButton(self.tr("Mode interactif"))
        self.btn_interactive.setCheckable(True)
        self.btn_detect = QPushButton(self.tr("Détecter maintenant"))
        self._hints: list[QLabel] = []
        for col, button in enumerate((self.btn_visible, self.btn_interactive, self.btn_detect)):
            button.setObjectName("bigButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            buttons.addWidget(button, 0, col)
            hint = QLabel()
            hint.setObjectName("hotkeyHint")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            buttons.addWidget(hint, 1, col)
            self._hints.append(hint)
        self.btn_visible.clicked.connect(app.toggle_visible)
        self.btn_interactive.clicked.connect(app.toggle_interactive)
        self.btn_detect.clicked.connect(lambda: app.detect_now("manual"))
        header_layout.addSpacing(6)
        header_layout.addLayout(buttons)
        root.addWidget(header)

        self.message = QLabel()
        self.message.setObjectName("message")
        self.message.setWordWrap(True)
        self.message.hide()
        root.addWidget(self.message)
        self._message_timer = QTimer(self, singleShot=True, interval=MESSAGE_MS)
        self._message_timer.timeout.connect(self.message.hide)

        # Tabs
        self.tabs = QTabWidget()
        self.tab_display = DisplayTab(app)
        self.tab_hotkeys = HotkeysTab(app)
        self.tab_detection = DetectionTab(app)
        self.tab_site = SiteTab(app)
        self.tab_about = AboutTab(app)
        self.tabs.addTab(scrollable(self.tab_display), self.tr("Affichage"))
        self.tabs.addTab(scrollable(self.tab_hotkeys), self.tr("Raccourcis"))
        self.tabs.addTab(scrollable(self.tab_detection), self.tr("Détection"))
        self.tabs.addTab(scrollable(self.tab_site), self.tr("Site"))
        self.tabs.addTab(scrollable(self.tab_about), self.tr("À propos"))
        root.addWidget(self.tabs, 1)

        app.state_changed.connect(self.refresh)
        self._clock = QTimer(self, interval=1000)
        self._clock.timeout.connect(self._refresh_detection_age)
        self._clock.start()
        self.refresh()

    def show_message(self, text: str, error: bool = False) -> None:
        self.message.setText(text)
        self.message.setProperty("error", error)
        self.message.style().unpolish(self.message)
        self.message.style().polish(self.message)
        self.message.show()
        self._message_timer.start()

    def refresh(self) -> None:
        app = self.app
        visible = app.overlay_visible
        interactive = app.overlay.interactive
        self.light_overlay.set_state(
            "ok" if visible else "off", self.tr("visible") if visible else self.tr("masqué")
        )
        self.light_mode.set_state(
            "warn" if interactive else "ok",
            self.tr("interactif") if interactive else self.tr("passif (clics traversants)"),
        )
        if sys.platform == "win32":
            title = app.cfg.capture.game_window_title
            if app.game_found:
                self.light_game.set_state("ok", self.tr("fenêtre « %s » trouvée") % title)
            else:
                self.light_game.set_state("warn", self.tr("fenêtre « %s » non trouvée") % title)
        else:
            self.light_game.set_state("off", self.tr("écran principal (hors Windows)"))
        self._refresh_detection_age()

        self.btn_visible.setText(
            self.tr("Masquer l'overlay") if visible else self.tr("Afficher l'overlay")
        )
        self.btn_interactive.setChecked(interactive)
        hk = app.cfg.hotkeys
        for hint, spec in zip(
            self._hints, (hk.toggle_visible, hk.toggle_interactive, hk.detect), strict=True
        ):
            hint.setText(hotkey_label(spec))

        for tab in (
            self.tab_display,
            self.tab_hotkeys,
            self.tab_detection,
            self.tab_site,
            self.tab_about,
        ):
            tab.refresh()

    def _refresh_detection_age(self) -> None:
        outcome = self.app.last_outcome
        if outcome is None:
            state = "off"
        elif (
            outcome.found and outcome.detection.confidence >= self.app.cfg.detection.min_confidence
        ):
            state = "ok"
        else:
            state = "warn"
        self.light_detection.set_state(state, self.app.last_detection_text())

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.allow_close or not self.app.tray.available:
            if not self.allow_close:
                event.ignore()
                self.app.quit()
                return
            event.accept()
            return
        # Closing the window keeps the app running in the tray.
        event.ignore()
        self.hide()
