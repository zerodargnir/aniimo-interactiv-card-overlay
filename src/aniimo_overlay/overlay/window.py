"""The overlay: a frameless, always-on-top, semi-transparent window holding the web view."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QRect, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices, QMouseEvent, QMoveEvent, QResizeEvent
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from aniimo_overlay.config import OPACITY_MAX, OPACITY_MIN, ZOOM_MAX, ZOOM_MIN
from aniimo_overlay.overlay.clickthrough import exclude_from_capture, set_click_through
from aniimo_overlay.overlay.handle import HandleBar

log = logging.getLogger(__name__)

RESIZE_MARGIN = 6
TOAST_MS = 3500


def create_profile(storage: Path) -> QWebEngineProfile:
    """Persistent profile: cookies and local storage survive restarts (site preferences,
    login). The HTTP cache stays in memory so no site content is written to disk."""
    profile = QWebEngineProfile("aniimo-overlay")
    profile.setPersistentStoragePath(str(storage))
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
    )
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
    return profile


class _ExternalLinkPage(QWebEnginePage):
    """Throw-away page for links that want a new window: opens them in the system browser."""

    def acceptNavigationRequest(self, url: QUrl, nav_type, is_main_frame: bool) -> bool:
        if url.isValid() and url.scheme() in ("http", "https"):
            QDesktopServices.openUrl(url)
        self.deleteLater()
        return False


class _WebPage(QWebEnginePage):
    def createWindow(self, _type) -> QWebEnginePage:
        return _ExternalLinkPage(self.profile(), self)


class OverlayWindow(QWidget):
    geometry_changed = Signal(QRect)
    hide_requested = Signal()
    passive_requested = Signal()

    def __init__(self, profile: QWebEngineProfile) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setWindowTitle("Aniimo Overlay — carte")
        self.setObjectName("overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.setMinimumSize(200, 150)
        self._interactive = False
        self._zoom = 1.0

        self.handle = HandleBar(self)
        self.handle.passive_requested.connect(self.passive_requested)
        self.handle.hide_requested.connect(self.hide_requested)

        self.view = QWebEngineView(self)
        self.page = _WebPage(profile, self.view)
        self.view.setPage(self.page)
        self.view.loadFinished.connect(lambda _ok: self.view.setZoomFactor(self._zoom))

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.addWidget(self.handle)
        layout.addWidget(self.view, 1)
        self._layout = layout

        self._toast = QLabel(self)
        self._toast.setObjectName("toast")
        self._toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._toast.setWordWrap(True)
        self._toast.hide()
        self._toast_timer = QTimer(self, singleShot=True, interval=TOAST_MS)
        self._toast_timer.timeout.connect(self._toast.hide)

        self._apply_mode()

    # --- public API ---------------------------------------------------------------

    @property
    def interactive(self) -> bool:
        return self._interactive

    def set_interactive(self, enabled: bool) -> None:
        self._interactive = enabled
        self._apply_mode()
        if enabled and self.isVisible():
            self.raise_()
            self.activateWindow()

    def set_opacity(self, value: float) -> float:
        value = round(min(OPACITY_MAX, max(OPACITY_MIN, value)) * 20) / 20  # 5 % steps
        self.setWindowOpacity(value)
        # Qt may rewrite the layered style when opacity changes: re-apply click-through.
        if self.isVisible() and not self._interactive:
            set_click_through(self, True)
        return value

    def set_zoom(self, value: float) -> float:
        self._zoom = round(min(ZOOM_MAX, max(ZOOM_MIN, value)) * 20) / 20
        self.view.setZoomFactor(self._zoom)
        return self._zoom

    def set_status(self, text: str) -> None:
        self.handle.set_status(text)

    def toast(self, text: str) -> None:
        """Short message on top of the map, visible in passive mode too."""
        self._toast.setText(text)
        width = min(self.width() - 20, 360)
        self._toast.setFixedWidth(max(120, width))
        self._toast.adjustSize()
        self._toast.move(
            (self.width() - self._toast.width()) // 2, self.height() - self._toast.height() - 16
        )
        self._toast.raise_()
        self._toast.show()
        self._toast_timer.start()

    def show_overlay(self) -> None:
        self.show()
        self._apply_mode()
        exclude_from_capture(self)

    def dispose(self) -> None:
        """Delete the page before its profile (avoids a QtWebEngine warning on exit)."""
        self.view.setPage(None)
        self.page.deleteLater()

    # --- internals ----------------------------------------------------------------

    def _apply_mode(self) -> None:
        interactive = self._interactive
        self.handle.setVisible(interactive)
        margin = RESIZE_MARGIN if interactive else 0
        self._layout.setContentsMargins(margin, margin, margin, margin)
        self.setProperty("interactive", interactive)
        self.style().unpolish(self)
        self.style().polish(self)
        if self.isVisible() or self.windowHandle() is not None:
            set_click_through(self, not interactive)

    def _edges_at(self, pos) -> Qt.Edge:
        edges = Qt.Edge(0)
        if not self._interactive:
            return edges
        if pos.x() <= RESIZE_MARGIN:
            edges |= Qt.Edge.LeftEdge
        if pos.x() >= self.width() - RESIZE_MARGIN:
            edges |= Qt.Edge.RightEdge
        if pos.y() <= RESIZE_MARGIN:
            edges |= Qt.Edge.TopEdge
        if pos.y() >= self.height() - RESIZE_MARGIN:
            edges |= Qt.Edge.BottomEdge
        return edges

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        edges = self._edges_at(event.position().toPoint())
        left_right = Qt.Edge.LeftEdge | Qt.Edge.RightEdge
        top_bottom = Qt.Edge.TopEdge | Qt.Edge.BottomEdge
        if edges in (Qt.Edge.LeftEdge | Qt.Edge.TopEdge, Qt.Edge.RightEdge | Qt.Edge.BottomEdge):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edges in (Qt.Edge.RightEdge | Qt.Edge.TopEdge, Qt.Edge.LeftEdge | Qt.Edge.BottomEdge):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edges & left_right:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edges & top_bottom:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.unsetCursor()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        edges = self._edges_at(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and edges and self.windowHandle():
            self.windowHandle().startSystemResize(edges)

    def moveEvent(self, event: QMoveEvent) -> None:
        super().moveEvent(event)
        self.geometry_changed.emit(self.geometry())

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.geometry_changed.emit(self.geometry())

    def closeEvent(self, event: QCloseEvent) -> None:
        # Alt+F4 in interactive mode only hides the overlay; quitting is done from the tray.
        event.ignore()
        self.hide_requested.emit()
