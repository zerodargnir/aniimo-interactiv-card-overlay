"""System tray icon: show/hide overlay, interactive mode, detect, settings, quit."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class Tray(QObject):
    toggle_visible = Signal()
    toggle_interactive = Signal()
    detect = Signal()
    show_control = Signal()
    quit_requested = Signal()

    def __init__(self, icon: QIcon, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.available = QSystemTrayIcon.isSystemTrayAvailable()
        self._icon = QSystemTrayIcon(icon, self)
        self._icon.setToolTip("Aniimo Overlay")

        menu = QMenu()
        self._visible_action = QAction(self.tr("Afficher l'overlay"), menu)
        self._visible_action.triggered.connect(self.toggle_visible)
        self._interactive_action = QAction(self.tr("Mode interactif"), menu, checkable=True)
        self._interactive_action.triggered.connect(self.toggle_interactive)
        detect_action = QAction(self.tr("Détecter le plan maintenant"), menu)
        detect_action.triggered.connect(self.detect)
        control_action = QAction(self.tr("Fenêtre de contrôle et réglages…"), menu)
        control_action.triggered.connect(self.show_control)
        quit_action = QAction(self.tr("Quitter"), menu)
        quit_action.triggered.connect(self.quit_requested)

        menu.addAction(self._visible_action)
        menu.addAction(self._interactive_action)
        menu.addAction(detect_action)
        menu.addSeparator()
        menu.addAction(control_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self._menu = menu
        self._icon.setContextMenu(menu)
        self._icon.activated.connect(self._on_activated)

    def show(self) -> None:
        if self.available:
            self._icon.show()

    def hide(self) -> None:
        self._icon.hide()

    def update_state(self, visible: bool, interactive: bool, last_detection: str) -> None:
        self._visible_action.setText(
            self.tr("Masquer l'overlay") if visible else self.tr("Afficher l'overlay")
        )
        self._interactive_action.setChecked(interactive)
        tip = "Aniimo Overlay"
        if last_detection:
            tip += "\n" + last_detection
        self._icon.setToolTip(tip)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_control.emit()
