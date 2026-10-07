"""Small reusable widgets: hotkey recorder, slider with value, status light."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFocusEvent, QImage, QKeyEvent, QKeySequence, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QWidget

from aniimo_overlay.hotkeys import hotkey_label

_NAMED_QT_KEYS = {
    Qt.Key.Key_Up: "<up>",
    Qt.Key.Key_Down: "<down>",
    Qt.Key.Key_Left: "<left>",
    Qt.Key.Key_Right: "<right>",
    Qt.Key.Key_Space: "<space>",
    Qt.Key.Key_Tab: "<tab>",
    Qt.Key.Key_Backspace: "<backspace>",
    Qt.Key.Key_Return: "<enter>",
    Qt.Key.Key_Enter: "<enter>",
    Qt.Key.Key_Delete: "<delete>",
    Qt.Key.Key_Insert: "<insert>",
    Qt.Key.Key_Home: "<home>",
    Qt.Key.Key_End: "<end>",
    Qt.Key.Key_PageUp: "<page_up>",
    Qt.Key.Key_PageDown: "<page_down>",
    Qt.Key.Key_Pause: "<pause>",
    Qt.Key.Key_Print: "<print_screen>",
    Qt.Key.Key_ScrollLock: "<scroll_lock>",
}

_MODIFIER_KEYS = {
    Qt.Key.Key_Control,
    Qt.Key.Key_Alt,
    Qt.Key.Key_AltGr,
    Qt.Key.Key_Shift,
    Qt.Key.Key_Meta,
    Qt.Key.Key_Super_L,
    Qt.Key.Key_Super_R,
}


def bgr_to_pixmap(image: np.ndarray) -> QPixmap:
    """OpenCV BGR (or single channel) image -> QPixmap (copied)."""
    image = np.ascontiguousarray(image)
    h, w = image.shape[:2]
    if image.ndim == 2:
        qimage = QImage(image.data, w, h, image.strides[0], QImage.Format.Format_Grayscale8)
    else:
        qimage = QImage(image.data, w, h, image.strides[0], QImage.Format.Format_BGR888)
    return QPixmap.fromImage(qimage.copy())


def qt_key_to_pynput(key: int, modifiers: Qt.KeyboardModifier) -> str | None:
    """Convert a Qt key press to pynput hotkey syntax. None if the key is not supported."""
    key = Qt.Key(key)
    if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
        name = f"<f{key - Qt.Key.Key_F1 + 1}>"
    elif key in _NAMED_QT_KEYS:
        name = _NAMED_QT_KEYS[key]
    elif Qt.Key.Key_A <= key <= Qt.Key.Key_Z or Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        name = chr(key).lower()
    else:
        text = QKeySequence(key).toString()
        if len(text) != 1 or not text.isprintable():
            return None
        name = text.lower()
    parts = []
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        parts.append("<ctrl>")
    if modifiers & Qt.KeyboardModifier.AltModifier:
        parts.append("<alt>")
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        parts.append("<shift>")
    if modifiers & Qt.KeyboardModifier.MetaModifier:
        parts.append("<cmd>")
    parts.append(name)
    return "+".join(parts)


class HotkeyEdit(QPushButton):
    """Click, then press a key combination: it is recorded in pynput syntax.

    Escape cancels. `recording_changed(True/False)` lets the app suspend global hotkeys.
    """

    changed = Signal(str)
    recording_changed = Signal(bool)

    def __init__(self, value: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("hotkeyEdit")
        self.setCheckable(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._value = value
        self._recording = False
        self.clicked.connect(self._start)
        self._refresh()

    def value(self) -> str:
        return self._value

    def set_value(self, value: str) -> None:
        self._value = value
        self._refresh()

    def _refresh(self, text: str | None = None) -> None:
        if text is None:
            text = hotkey_label(self._value) or self.tr("— aucun —")
        self.setText(text)
        self.setChecked(self._recording)

    def _start(self) -> None:
        if self._recording:
            self._stop()
            return
        self._recording = True
        self.grabKeyboard()
        self._refresh(self.tr("Appuie sur la combinaison… (Échap : annuler)"))
        self.recording_changed.emit(True)

    def _stop(self) -> None:
        if not self._recording:
            return
        self._recording = False
        self.releaseKeyboard()
        self._refresh()
        self.recording_changed.emit(False)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self._recording:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._stop()
            return
        if key in _MODIFIER_KEYS:
            return
        spec = qt_key_to_pynput(key, event.modifiers())
        if spec is None:
            self._refresh(self.tr("Touche non prise en charge, essaie une autre"))
            return
        self._value = spec
        self._stop()
        self.changed.emit(spec)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self._stop()
        super().focusOutEvent(event)


class ValueSlider(QWidget):
    """Horizontal slider showing its value, e.g. "85 %"."""

    value_changed = Signal(int)

    def __init__(
        self, minimum: int, maximum: int, step: int = 5, suffix: str = " %", parent=None
    ) -> None:
        super().__init__(parent)
        self._suffix = suffix
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setSingleStep(step)
        self.slider.setPageStep(step * 2)
        self.slider.setTickInterval(step)
        self._step = step
        self.label = QLabel()
        self.label.setObjectName("sliderValue")
        self.label.setMinimumWidth(52)
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.label)
        self.slider.valueChanged.connect(self._on_change)
        self._on_change(self.slider.value(), emit=False)

    def _on_change(self, value: int, emit: bool = True) -> None:
        snapped = round(value / self._step) * self._step
        if snapped != value:
            self.slider.setValue(snapped)
            return
        self.label.setText(f"{value}{self._suffix}")
        if emit:
            self.value_changed.emit(value)

    def value(self) -> int:
        return self.slider.value()

    def set_value(self, value: int) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self.label.setText(f"{self.slider.value()}{self._suffix}")


class StatusLight(QWidget):
    """Coloured dot + caption + value. state: "ok", "warn", "off"."""

    def __init__(self, caption: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dot = QLabel("●")
        self._dot.setObjectName("statusDot")
        self._caption = QLabel(caption)
        self._caption.setObjectName("statusCaption")
        self._value = QLabel()
        self._value.setObjectName("statusValue")
        self._value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._dot)
        layout.addWidget(self._caption)
        layout.addWidget(self._value, 1)
        self.set_state("off", "")

    def set_state(self, state: str, text: str) -> None:
        self._dot.setProperty("state", state)
        self._dot.style().unpolish(self._dot)
        self._dot.style().polish(self._dot)
        self._value.setText(text)
