"""Global hotkeys with pynput. Callbacks run in pynput's thread: they only emit a Qt signal."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Qt, Signal

log = logging.getLogger(__name__)

ACTIONS: tuple[str, ...] = (
    "toggle_visible",
    "toggle_interactive",
    "detect",
    "opacity_up",
    "opacity_down",
    "zoom_in",
    "zoom_out",
)

_NAMED_KEYS_FR = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "alt_gr": "AltGr",
    "shift": "Maj",
    "cmd": "Win",
    "up": "Haut",
    "down": "Bas",
    "left": "Gauche",
    "right": "Droite",
    "space": "Espace",
    "enter": "Entrée",
    "tab": "Tab",
    "backspace": "Retour arrière",
    "delete": "Suppr",
    "insert": "Inser",
    "home": "Début",
    "end": "Fin",
    "page_up": "Page préc.",
    "page_down": "Page suiv.",
    "pause": "Pause",
    "print_screen": "Impr. écran",
    "scroll_lock": "Arrêt défil.",
    "esc": "Échap",
}


def hotkey_label(spec: str) -> str:
    """Human-readable French label for a pynput hotkey string ("<ctrl>+<alt>+<up>")."""
    if not spec:
        return ""
    parts = []
    for part in spec.split("+"):
        if part.startswith("<") and part.endswith(">"):
            name = part[1:-1]
            parts.append(_NAMED_KEYS_FR.get(name, name.upper()))
        else:
            parts.append(part.upper())
    return " + ".join(parts)


def is_valid_hotkey(spec: str) -> bool:
    if not spec:
        return False
    try:
        from pynput import keyboard

        keyboard.HotKey.parse(spec)
    except Exception:  # pynput raises ValueError, or ImportError without a backend
        return False
    return True


def find_conflicts(mapping: dict[str, str]) -> dict[str, list[str]]:
    """Hotkey string -> actions sharing it (only when shared by 2+ actions)."""
    by_key: dict[str, list[str]] = {}
    for action, spec in mapping.items():
        if spec:
            by_key.setdefault(_normalize(spec), []).append(action)
    return {key: actions for key, actions in by_key.items() if len(actions) > 1}


def _normalize(spec: str) -> str:
    return "+".join(sorted(spec.lower().split("+")))


class HotkeyManager(QObject):
    """Owns the pynput listener. `triggered(action)` is delivered in the Qt main thread."""

    triggered = Signal(str)
    _fired = Signal(str)  # emitted from the pynput thread

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._listener = None
        self._mapping: dict[str, str] = {}
        self._suspended = False
        self.available = True
        self.error = ""
        self._fired.connect(self._deliver, Qt.ConnectionType.QueuedConnection)

    def start(self, mapping: dict[str, str]) -> None:
        self._mapping = dict(mapping)
        self._restart()

    def update(self, mapping: dict[str, str]) -> None:
        self.start(mapping)

    def suspend(self) -> None:
        """Stop reacting while the user records a new hotkey in the GUI."""
        self._suspended = True
        self._stop_listener()

    def resume(self) -> None:
        self._suspended = False
        self._restart()

    def stop(self) -> None:
        self._stop_listener()

    def _restart(self) -> None:
        self._stop_listener()
        if self._suspended:
            return
        try:
            from pynput import keyboard
        except Exception as exc:  # no X server / unsupported backend
            self.available = False
            self.error = f"Raccourcis globaux indisponibles : {exc}"
            log.warning(self.error)
            return

        bindings = {}
        for action, spec in self._mapping.items():
            if not spec:
                continue
            if not is_valid_hotkey(spec):
                log.warning("Invalid hotkey for %s: %r (ignored)", action, spec)
                continue
            bindings[spec] = self._make_callback(action)
        if not bindings:
            return
        try:
            self._listener = keyboard.GlobalHotKeys(bindings)
            self._listener.daemon = True
            self._listener.start()
            self.available = True
            self.error = ""
            log.info("Global hotkeys active: %s", ", ".join(sorted(bindings)))
        except Exception as exc:
            self.available = False
            self.error = f"Raccourcis globaux indisponibles : {exc}"
            log.warning(self.error)

    def _make_callback(self, action: str):
        def callback() -> None:
            self._fired.emit(action)

        return callback

    def _deliver(self, action: str) -> None:
        if not self._suspended:
            self.triggered.emit(action)

    def _stop_listener(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                log.debug("Error while stopping the hotkey listener", exc_info=True)
            self._listener = None
