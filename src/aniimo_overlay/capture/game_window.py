"""Locate the game window. Windows: Win32 API via ctypes. Other OS: screen / ROI fallback.

All OS-specific code of this module lives behind the `sys.platform == "win32"` checks.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

import numpy as np

from aniimo_overlay.capture.screen import Region, grab, mask_regions, monitor_region

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GameWindow:
    handle: int
    title: str
    client: Region  # client area in physical screen pixels


@dataclass
class Capture:
    image: np.ndarray
    region: Region  # what was captured, physical pixels
    game: GameWindow | None


def enable_dpi_awareness() -> None:
    """Per-monitor DPI awareness, before the QApplication exists (Windows only)."""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        log.debug("DPI awareness not set", exc_info=True)


def find_game_window(title_part: str) -> GameWindow | None:
    """Visible, non-minimized top-level window whose title matches `title_part`.

    Preference: exact title, then title starting with it, then containing it. Our own
    windows and browser tabs of aniimotools.dev are ignored.
    """
    if sys.platform != "win32" or not title_part:
        return None
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    needle = title_part.casefold()
    found: list[GameWindow] = []

    enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        folded = title.casefold()
        if needle not in folded or title.startswith("Aniimo Overlay") or "aniimotools" in folded:
            return True
        rect = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return True
        origin = wintypes.POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(origin))
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if width > 0 and height > 0:
            found.append(GameWindow(int(hwnd), title, Region(origin.x, origin.y, width, height)))
        return True

    user32.EnumWindows(enum_proc_type(callback), 0)
    if not found:
        return None

    def rank(window: GameWindow) -> int:
        folded = window.title.casefold().strip()
        return 0 if folded == needle else 1 if folded.startswith(needle) else 2

    return min(found, key=rank)  # stable: keeps Z-order among equals


def is_exclusive_fullscreen() -> bool:
    """Best effort: a Direct3D app is running in exclusive fullscreen (Windows only)."""
    if sys.platform != "win32":
        return False
    import ctypes

    state = ctypes.c_int(0)
    try:
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0:
            return False
    except (AttributeError, OSError):
        return False
    return state.value == 3  # QUNS_RUNNING_D3D_FULL_SCREEN


def capture_region(
    title: str, monitor: int, roi: list[int] | None
) -> tuple[Region, GameWindow | None]:
    game = find_game_window(title)
    base = game.client if game else monitor_region(monitor)
    if roi:
        x, y, w, h = roi
        roi_region = Region(base.left + x, base.top + y, w, h)
        clipped = base.intersect(roi_region)
        if clipped is not None:
            return clipped, game
        log.warning("ROI %s is outside the capture area, ignored", roi)
    return base, game


def capture_game(
    title: str, monitor: int, roi: list[int] | None, hide: list[Region] | None = None
) -> Capture:
    """Capture the game client area (or the monitor), blacking out `hide` regions."""
    region, game = capture_region(title, monitor, roi)
    image = grab(region)
    if hide:
        mask_regions(image, region, hide)
    return Capture(image, region, game)
