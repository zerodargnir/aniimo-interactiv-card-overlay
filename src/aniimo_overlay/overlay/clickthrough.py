"""Window-level OS tweaks for the overlay: click-through and exclusion from screen capture.

All OS-specific code of this module lives behind the `sys.platform == "win32"` checks.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

log = logging.getLogger(__name__)

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
LWA_ALPHA = 0x2
WDA_EXCLUDEFROMCAPTURE = 0x11


def set_click_through(widget: QWidget, enabled: bool) -> None:
    """Mouse clicks go through the window to whatever is below (the game)."""
    if sys.platform == "win32":
        _set_click_through_win32(widget, enabled)
        return
    handle = widget.windowHandle()
    if handle is not None:
        # QWindow.setFlag changes the input shape without recreating the native window.
        handle.setFlag(Qt.WindowType.WindowTransparentForInput, enabled)
    else:
        widget.setWindowFlag(Qt.WindowType.WindowTransparentForInput, enabled)
        if widget.isVisible():
            widget.hide()
            widget.show()


def _set_click_through_win32(widget: QWidget, enabled: bool) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    hwnd = int(widget.winId())
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    passive_bits = WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
    if enabled:
        style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW | passive_bits
    else:
        style &= ~passive_bits
        style |= WS_EX_TOOLWINDOW
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    if style & WS_EX_LAYERED:
        # A layered window without attributes is invisible: always set the alpha.
        alpha = max(0, min(255, round(widget.windowOpacity() * 255)))
        user32.SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA)


def exclude_from_capture(widget: QWidget) -> bool:
    """Hide the window from screen captures (Windows 10 2004+). False if unsupported."""
    if sys.platform != "win32":
        return False
    import ctypes

    try:
        ok = bool(
            ctypes.windll.user32.SetWindowDisplayAffinity(
                int(widget.winId()), WDA_EXCLUDEFROMCAPTURE
            )
        )
    except (AttributeError, OSError):
        ok = False
    if not ok:
        log.info("SetWindowDisplayAffinity unavailable, our windows will be masked in captures")
    return ok
