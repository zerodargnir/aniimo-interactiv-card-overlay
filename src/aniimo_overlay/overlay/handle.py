"""Handle bar shown on top of the overlay in interactive mode: move window, status, buttons."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class HandleBar(QWidget):
    passive_requested = Signal()
    hide_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("handleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self._drag_offset: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 4, 0)
        layout.setSpacing(6)

        self._status = QLabel(self.tr("Mode interactif — glisser pour déplacer"))
        self._status.setObjectName("handleStatus")
        layout.addWidget(self._status, 1)

        passive = QPushButton(self.tr("Passif"))
        passive.setObjectName("handleButton")
        passive.setToolTip(self.tr("Revenir en mode passif (clics traversants)"))
        passive.setCursor(Qt.CursorShape.ArrowCursor)
        passive.clicked.connect(self.passive_requested)
        layout.addWidget(passive)

        close = QPushButton("✕")
        close.setObjectName("handleButton")
        close.setToolTip(self.tr("Masquer l'overlay"))
        close.setCursor(Qt.CursorShape.ArrowCursor)
        close.setFixedWidth(28)
        close.clicked.connect(self.hide_requested)
        layout.addWidget(close)

    def set_status(self, text: str) -> None:
        self._status.setText(text)
        self._status.setToolTip(text)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        handle = self.window().windowHandle()
        # Native move when supported (Windows, X11); manual drag otherwise.
        if handle is None or not handle.startSystemMove():
            self._drag_offset = event.globalPosition().toPoint() - self.window().pos()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
