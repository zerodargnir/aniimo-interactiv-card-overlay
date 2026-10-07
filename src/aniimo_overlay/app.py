"""Application wiring: config, overlay, site bridge, hotkeys, tray, detection, control window."""

from __future__ import annotations

import argparse
import getpass
import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QRect, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from aniimo_overlay import APP_ID, APP_NAME, __version__, paths
from aniimo_overlay import config as config_mod
from aniimo_overlay.bridge.site import SiteBridge
from aniimo_overlay.capture.game_window import (
    enable_dpi_awareness,
    find_game_window,
    is_exclusive_fullscreen,
)
from aniimo_overlay.capture.screen import Region
from aniimo_overlay.detect_task import DetectionOutcome, DetectionRequest, DetectTask
from aniimo_overlay.detection.calibrate import load_templates
from aniimo_overlay.detection.doors import DoorParams, HsvRange
from aniimo_overlay.hotkeys import HotkeyManager
from aniimo_overlay.overlay.clickthrough import exclude_from_capture
from aniimo_overlay.overlay.window import OverlayWindow, create_profile
from aniimo_overlay.tray import Tray

log = logging.getLogger(__name__)

SAVE_DELAY_MS = 500
GAME_POLL_MS = 3000
OPACITY_STEP = 0.05
ZOOM_STEP = 0.1
INSTANCE_KEY = f"{APP_ID}-{getpass.getuser()}"


class App(QObject):
    """Owns every module and exposes the actions used by hotkeys, tray and GUI."""

    state_changed = Signal()
    detection_done = Signal(object)  # DetectionOutcome
    test_done = Signal(object)  # DetectionOutcome of a "test" run (GUI preview)

    def __init__(self, qapp: QApplication, cfg_path: Path, debug_detection: bool = False):
        super().__init__()
        self.qapp = qapp
        self.cfg_path = cfg_path
        self.cfg = config_mod.load(cfg_path)
        if debug_detection:
            self.cfg.detection.debug = True
        self.icon = QIcon(str(paths.resource_path("app.png")))

        self.game_found = False
        self.last_outcome: DetectionOutcome | None = None
        self._last_sent_sector: str | None = None
        self._auto_previous: str | None = None
        self._task: DetectTask | None = None
        self._pool = QThreadPool.globalInstance()
        self._templates = load_templates(paths.templates_dir())

        self._save_timer = QTimer(self, singleShot=True, interval=SAVE_DELAY_MS)
        self._save_timer.timeout.connect(self.save_now)

        # Overlay + site
        self.profile = create_profile(paths.web_profile_dir())
        self.overlay = OverlayWindow(self.profile)
        self.overlay.setWindowIcon(self.icon)
        self._capture_excluded = False
        w = self.cfg.window
        self.overlay.setGeometry(self._on_screen(QRect(w.x, w.y, w.width, w.height)))
        self.overlay.set_opacity(w.opacity)
        self.overlay.set_zoom(w.zoom)
        self.overlay.geometry_changed.connect(self._on_overlay_geometry)
        self.overlay.hide_requested.connect(lambda: self.set_visible(False))
        self.overlay.passive_requested.connect(lambda: self.set_interactive(False))
        self.bridge = SiteBridge(self.overlay.view, self)
        self.bridge.status.connect(self._on_bridge_status)

        # Hotkeys
        self.hotkeys = HotkeyManager(self)
        self.hotkeys.triggered.connect(self.run_action)

        # Tray
        self.tray = Tray(self.icon, self)
        self.tray.toggle_visible.connect(self.toggle_visible)
        self.tray.toggle_interactive.connect(self.toggle_interactive)
        self.tray.detect.connect(self.detect_now)
        self.tray.show_control.connect(self.show_control)
        self.tray.quit_requested.connect(self.quit)
        self.state_changed.connect(self._update_tray)

        # Timers
        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(lambda: self.detect_now(source="auto"))
        self._game_timer = QTimer(self, interval=GAME_POLL_MS)
        self._game_timer.timeout.connect(self._poll_game)

        from aniimo_overlay.gui.control_window import ControlWindow

        self.control = ControlWindow(self)
        self.control.setWindowIcon(self.icon)

    # --- start / stop -------------------------------------------------------------

    def start(self) -> None:
        self.bridge.load(self.cfg.site.url)
        self.hotkeys.start(self.cfg.hotkeys.as_dict())
        self.tray.show()
        self._apply_auto()
        self._poll_game()
        self._game_timer.start()
        if self.cfg.window.start_visible:
            self.set_visible(True)
        self.show_control()
        self.state_changed.emit()

    def quit(self) -> None:
        log.info("Quitting")
        self._store_geometry(self.overlay.geometry())
        self.save_now()
        self.hotkeys.stop()
        self._auto_timer.stop()
        self._game_timer.stop()
        self.tray.hide()
        self.control.allow_close = True
        self.control.close()
        self.overlay.hide()
        self.overlay.dispose()
        self.overlay.deleteLater()
        QTimer.singleShot(0, self.profile.deleteLater)
        QTimer.singleShot(50, self.qapp.quit)

    def show_control(self) -> None:
        self.control.showNormal()
        self.control.raise_()
        self.control.activateWindow()
        exclude_from_capture(self.control)

    # --- config persistence --------------------------------------------------------

    def schedule_save(self) -> None:
        self._save_timer.start()

    def save_now(self) -> None:
        try:
            config_mod.save(self.cfg, self.cfg_path)
        except OSError:
            log.exception("Could not save the config")

    # --- actions (hotkeys / tray / GUI) --------------------------------------------

    def run_action(self, action: str) -> None:
        handlers = {
            "toggle_visible": self.toggle_visible,
            "toggle_interactive": self.toggle_interactive,
            "detect": self.detect_now,
            "opacity_up": lambda: self.set_opacity(self.cfg.window.opacity + OPACITY_STEP),
            "opacity_down": lambda: self.set_opacity(self.cfg.window.opacity - OPACITY_STEP),
            "zoom_in": lambda: self.set_zoom(self.cfg.window.zoom + ZOOM_STEP),
            "zoom_out": lambda: self.set_zoom(self.cfg.window.zoom - ZOOM_STEP),
        }
        handler = handlers.get(action)
        if handler is not None:
            log.debug("Action %s", action)
            handler()

    @property
    def overlay_visible(self) -> bool:
        return self.overlay.isVisible()

    def toggle_visible(self) -> None:
        self.set_visible(not self.overlay.isVisible())

    def set_visible(self, visible: bool) -> None:
        if visible:
            self.overlay.show_overlay()
            self._capture_excluded = exclude_from_capture(self.overlay)
            if is_exclusive_fullscreen():
                self.overlay.toast(
                    self.tr(
                        "Le jeu semble en plein écran exclusif : passe-le en plein écran fenêtré"
                    )
                )
        else:
            if self.overlay.interactive:
                self.set_interactive(False)
            self.overlay.hide()
        self.state_changed.emit()

    def toggle_interactive(self) -> None:
        self.set_interactive(not self.overlay.interactive)

    def set_interactive(self, enabled: bool) -> None:
        if enabled and not self.overlay.isVisible():
            self.set_visible(True)
        self.overlay.set_interactive(enabled)
        self.state_changed.emit()

    def set_opacity(self, value: float) -> None:
        self.cfg.window.opacity = self.overlay.set_opacity(value)
        self.schedule_save()
        self.state_changed.emit()

    def set_zoom(self, value: float) -> None:
        self.cfg.window.zoom = self.overlay.set_zoom(value)
        self.schedule_save()
        self.state_changed.emit()

    def set_overlay_geometry(self, rect: QRect) -> None:
        self.overlay.setGeometry(rect)
        self._store_geometry(self.overlay.geometry())

    def snap_overlay(self, corner: str, target: str) -> None:
        """Move the overlay to a corner ("tl", "tr", "bl", "br") of the screen or game."""
        area = None
        if target == "game":
            game = find_game_window(self.cfg.capture.game_window_title)
            if game is None:
                self.control.show_message(self.tr("Fenêtre du jeu introuvable"), error=True)
                return
            area = self._physical_to_logical(game.client)
        if area is None:
            screen = self.overlay.screen() or QGuiApplication.primaryScreen()
            area = screen.availableGeometry()
        size = self.overlay.size()
        margin = 8
        x = area.left() + margin if corner in ("tl", "bl") else area.right() - size.width() - margin
        y = (
            area.top() + margin
            if corner in ("tl", "tr")
            else area.bottom() - size.height() - margin
        )
        self.set_overlay_geometry(QRect(QPoint(x, y), size))

    def reset_position(self) -> None:
        defaults = config_mod.WindowConfig()
        self.set_overlay_geometry(
            self._on_screen(QRect(defaults.x, defaults.y, defaults.width, defaults.height))
        )

    def set_start_visible(self, value: bool) -> None:
        self.cfg.window.start_visible = value
        self.schedule_save()

    # hotkeys
    def set_hotkeys(self, mapping: dict[str, str]) -> None:
        for action, spec in mapping.items():
            setattr(self.cfg.hotkeys, action, spec)
        self.hotkeys.update(self.cfg.hotkeys.as_dict())
        self.schedule_save()
        self.state_changed.emit()

    def set_hotkeys_recording(self, recording: bool) -> None:
        if recording:
            self.hotkeys.suspend()
        else:
            self.hotkeys.resume()

    # detection settings
    def set_auto(self, enabled: bool) -> None:
        self.cfg.detection.auto = enabled
        self._apply_auto()
        self.schedule_save()
        self.state_changed.emit()

    def set_interval(self, seconds: float) -> None:
        self.cfg.detection.interval_s = seconds
        self.cfg.clamp()
        self._apply_auto()
        self.schedule_save()

    def set_min_confidence(self, value: float) -> None:
        self.cfg.detection.min_confidence = value
        self.cfg.clamp()
        self.schedule_save()

    def set_hsv(self, orange: HsvRange, blue: HsvRange) -> None:
        self.cfg.detection.orange_hsv = orange.to_list()
        self.cfg.detection.blue_hsv = blue.to_list()
        self.save_now()

    def reset_hsv(self) -> None:
        defaults = config_mod.DetectionConfig()
        self.cfg.detection.orange_hsv = defaults.orange_hsv
        self.cfg.detection.blue_hsv = defaults.blue_hsv
        self.save_now()

    def reload_templates(self) -> None:
        self._templates = load_templates(paths.templates_dir())

    def set_game_title(self, title: str) -> None:
        self.cfg.capture.game_window_title = title.strip()
        self.schedule_save()
        self._poll_game()

    def set_debug_detection(self, enabled: bool) -> None:
        self.cfg.detection.debug = enabled
        self.schedule_save()

    # site
    def set_url(self, url: str) -> None:
        url = url.strip()
        if not url or url == self.cfg.site.url:
            return
        self.cfg.site.url = url
        self.save_now()
        self._last_sent_sector = None
        self.bridge.load(url)

    def reload_page(self) -> None:
        self._last_sent_sector = None
        self.bridge.reload()

    def open_in_browser(self) -> None:
        QDesktopServices.openUrl(QUrl(self.cfg.site.url))

    def open_log_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.log_dir())))

    # --- detection -----------------------------------------------------------------

    def door_params(self) -> DoorParams:
        d = self.cfg.detection
        return DoorParams(
            orange=HsvRange.from_list(d.orange_hsv), blue=HsvRange.from_list(d.blue_hsv)
        )

    def detect_now(self, source: str = "manual", image=None) -> bool:
        """Start a detection in the thread pool. False if one is already running."""
        if self._task is not None:
            return False
        c = self.cfg.capture
        request = DetectionRequest(
            source=source,
            params=self.door_params(),
            templates=self._templates,
            game_title=c.game_window_title,
            monitor=c.monitor,
            roi=c.roi,
            hide=self._own_windows_regions(),
            image=image,
            debug_dir=paths.debug_dir() if self.cfg.detection.debug else None,
        )
        self._task = DetectTask(request)
        self._task.signals.finished.connect(self._on_detection_finished)
        self._pool.start(self._task)
        return True

    def _on_detection_finished(self, outcome: DetectionOutcome) -> None:
        self._task = None
        if outcome.game_found is not None:
            self.game_found = outcome.game_found
        message = outcome.describe()
        if outcome.source == "test":
            self.test_done.emit(outcome)
            return
        log.info("Detection (%s): %s", outcome.source, message)

        if outcome.source == "manual":
            self._record(outcome)
            if outcome.found:
                self._send(outcome.direction.sector, outcome.direction.numpad)
            self.overlay.set_status(message)
            if self.overlay.isVisible():
                self.overlay.toast(message)
        elif outcome.source == "auto":
            self._handle_auto(outcome)
        self.detection_done.emit(outcome)
        self.state_changed.emit()

    def _handle_auto(self, outcome: DetectionOutcome) -> None:
        threshold = self.cfg.detection.min_confidence
        if not outcome.found or outcome.detection.confidence < threshold:
            self._auto_previous = None
            return
        sector = outcome.direction.sector
        stable = sector == self._auto_previous
        self._auto_previous = sector
        if not stable:
            return
        self._record(outcome)
        if sector != self._last_sent_sector:
            self._send(sector, outcome.direction.numpad)
            message = outcome.describe()
            self.overlay.set_status(message)
            if self.overlay.isVisible():
                self.overlay.toast(message)

    def _record(self, outcome: DetectionOutcome) -> None:
        self.last_outcome = outcome
        self._update_tray()

    def _update_tray(self) -> None:
        last = self.last_outcome.describe() if self.last_outcome else ""
        self.tray.update_state(self.overlay_visible, self.overlay.interactive, last)

    def _send(self, sector: str, numpad: int) -> None:
        self._last_sent_sector = sector
        self.bridge.select_direction(sector, numpad)

    def _apply_auto(self) -> None:
        if self.cfg.detection.auto:
            self._auto_previous = None
            self._auto_timer.start(int(self.cfg.detection.interval_s * 1000))
        else:
            self._auto_timer.stop()

    def _on_bridge_status(self, message: str) -> None:
        self.overlay.set_status(message)
        if self.overlay.isVisible():
            self.overlay.toast(message)
        self.control.show_message(message, error=True)

    # --- helpers -------------------------------------------------------------------

    def _poll_game(self) -> None:
        if sys.platform != "win32":
            return
        found = find_game_window(self.cfg.capture.game_window_title) is not None
        if found != self.game_found:
            self.game_found = found
            self.state_changed.emit()

    def _on_overlay_geometry(self, rect: QRect) -> None:
        self._store_geometry(rect)

    def _store_geometry(self, rect: QRect) -> None:
        w = self.cfg.window
        new = (rect.x(), rect.y(), rect.width(), rect.height())
        if new != (w.x, w.y, w.width, w.height):
            w.x, w.y, w.width, w.height = new
            self.schedule_save()
            self.state_changed.emit()

    def _on_screen(self, rect: QRect) -> QRect:
        """Keep a restored geometry reachable if a monitor was unplugged."""
        for screen in QGuiApplication.screens():
            if screen.availableGeometry().intersects(rect):
                return rect
        primary = QGuiApplication.primaryScreen().availableGeometry()
        return QRect(primary.topLeft() + QPoint(50, 50), rect.size())

    def _own_windows_regions(self) -> list[Region]:
        """Our visible windows in physical pixels, masked out of captures when the OS
        cannot exclude them from screen capture."""
        if sys.platform == "win32" and self._capture_excluded:
            return []
        regions = []
        for widget in (self.overlay, self.control):
            if widget.isVisible():
                regions.append(self._logical_to_physical(widget.frameGeometry()))
        return regions

    @staticmethod
    def _logical_to_physical(rect: QRect) -> Region:
        screen = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
        ratio = screen.devicePixelRatio()
        origin = screen.geometry().topLeft()
        x = origin.x() + (rect.x() - origin.x()) * ratio
        y = origin.y() + (rect.y() - origin.y()) * ratio
        return Region(round(x), round(y), round(rect.width() * ratio), round(rect.height() * ratio))

    @staticmethod
    def _physical_to_logical(region: Region) -> QRect:
        for screen in QGuiApplication.screens():
            ratio = screen.devicePixelRatio()
            geo = screen.geometry()
            phys_w, phys_h = geo.width() * ratio, geo.height() * ratio
            if (
                geo.x() <= region.left < geo.x() + phys_w
                and geo.y() <= region.top < geo.y() + phys_h
            ):
                x = geo.x() + (region.left - geo.x()) / ratio
                y = geo.y() + (region.top - geo.y()) / ratio
                return QRect(
                    round(x), round(y), round(region.width / ratio), round(region.height / ratio)
                )
        return QRect(region.left, region.top, region.width, region.height)

    def last_detection_text(self) -> str:
        outcome = self.last_outcome
        if outcome is None:
            return self.tr("aucune")
        age = int(time.time() - outcome.timestamp)
        if outcome.direction is None or outcome.detection is None:
            return outcome.describe()
        ago = f"il y a {age} s" if age < 120 else f"il y a {age // 60} min"
        return (
            f"{outcome.direction.label_fr} · confiance {outcome.detection.confidence:.2f} · {ago}"
        )


# --- entry point -------------------------------------------------------------------------


def _setup_logging(debug: bool) -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    try:
        handler = logging.handlers.RotatingFileHandler(
            paths.log_dir() / "aniimo-overlay.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(fmt)
        root.addHandler(handler)
    except OSError:
        pass
    if sys.stderr is not None:  # None in the windowed exe
        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        root.addHandler(stream)


def _check_session() -> None:
    if not sys.platform.startswith("linux") or os.environ.get("XDG_SESSION_TYPE") != "wayland":
        return
    message = (
        "Session Wayland détectée : capture d'écran, raccourcis globaux et « toujours au "
        "premier plan » peuvent ne pas fonctionner. Utilise une session X11 si possible."
    )
    if "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "xcb"
        message += " L'application tourne via XWayland (QT_QPA_PLATFORM=xcb)."
    log.warning(message)


def _close_splash() -> None:
    if "_PYI_SPLASH_IPC" not in os.environ:  # not started from the exe with a splash
        return
    try:
        import pyi_splash  # type: ignore[import-not-found]

        pyi_splash.close()
    except Exception:
        pass


def _already_running() -> bool:
    """Ask a running instance to show its control window. True if there was one."""
    socket = QLocalSocket()
    socket.connectToServer(INSTANCE_KEY)
    if socket.waitForConnected(300):
        socket.write(b"show")
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        return True
    return False


def _listen_for_instances(app: App) -> QLocalServer:
    server = QLocalServer(app)
    QLocalServer.removeServer(INSTANCE_KEY)  # stale socket after a crash
    server.listen(INSTANCE_KEY)

    def on_connection() -> None:
        conn = server.nextPendingConnection()
        if conn is not None:
            conn.readyRead.connect(conn.readAll)
            conn.disconnected.connect(conn.deleteLater)
        app.show_control()

    server.newConnection.connect(on_connection)
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aniimo_overlay", description=APP_NAME)
    parser.add_argument("--debug", action="store_true", help="detailed logs")
    parser.add_argument(
        "--debug-detection", action="store_true", help="save captures, masks and results"
    )
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    _setup_logging(args.debug)
    _check_session()
    enable_dpi_awareness()
    log.info(
        "%s %s starting (Python %s, %s)",
        APP_NAME,
        __version__,
        sys.version.split()[0],
        sys.platform,
    )

    qapp = QApplication(sys.argv[:1])
    qapp.setApplicationName(APP_NAME)
    qapp.setApplicationVersion(__version__)
    qapp.setQuitOnLastWindowClosed(False)

    if _already_running():
        log.info("Another instance is running, bringing it to the front")
        _close_splash()
        return 0

    from aniimo_overlay.gui.control_window import load_stylesheet

    qapp.setStyleSheet(load_stylesheet())
    app = App(qapp, paths.config_file(), debug_detection=args.debug_detection)
    _server = _listen_for_instances(app)
    app.start()
    _close_splash()
    return qapp.exec()
