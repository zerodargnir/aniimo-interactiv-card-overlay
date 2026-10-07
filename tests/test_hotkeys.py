from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from aniimo_overlay.bridge.site import build_url, language_of
from aniimo_overlay.config import HotkeysConfig
from aniimo_overlay.gui.widgets import qt_key_to_pynput
from aniimo_overlay.hotkeys import find_conflicts, hotkey_label

M = Qt.KeyboardModifier


@pytest.mark.parametrize(
    ("key", "mods", "expected"),
    [
        (Qt.Key.Key_F8, M.NoModifier, "<f8>"),
        (Qt.Key.Key_F12, M.NoModifier, "<f12>"),
        (Qt.Key.Key_Up, M.ControlModifier | M.AltModifier, "<ctrl>+<alt>+<up>"),
        (Qt.Key.Key_D, M.ControlModifier | M.ShiftModifier, "<ctrl>+<shift>+d"),
        (Qt.Key.Key_5, M.AltModifier, "<alt>+5"),
        (Qt.Key.Key_PageDown, M.NoModifier, "<page_down>"),
    ],
)
def test_qt_key_to_pynput(key, mods, expected):
    assert qt_key_to_pynput(key, mods) == expected


def test_unsupported_key():
    assert qt_key_to_pynput(Qt.Key.Key_VolumeUp, M.NoModifier) is None


def test_label():
    assert hotkey_label("<ctrl>+<alt>+<up>") == "Ctrl + Alt + Haut"
    assert hotkey_label("<f10>") == "F10"
    assert hotkey_label("") == ""


def test_conflicts():
    mapping = HotkeysConfig().as_dict()
    assert find_conflicts(mapping) == {}
    mapping["detect"] = "<f8>"
    conflicts = find_conflicts(mapping)
    assert list(conflicts.values()) == [["toggle_visible", "detect"]]
    mapping["detect"] = ""
    mapping["zoom_in"] = ""
    assert find_conflicts(mapping) == {}


def test_conflicts_ignore_modifier_order():
    assert find_conflicts({"a": "<ctrl>+<alt>+x", "b": "<alt>+<ctrl>+x"})


def test_default_hotkeys_parse():
    from aniimo_overlay.hotkeys import is_valid_hotkey

    try:
        from pynput import keyboard  # noqa: F401
    except Exception:
        pytest.skip("pynput backend unavailable")
    for spec in HotkeysConfig().as_dict().values():
        assert is_valid_hotkey(spec)


def test_site_urls():
    assert build_url("fr") == "https://aniimotools.dev/fr/map/lost-sanctum/"
    assert build_url("en") == "https://aniimotools.dev/map/lost-sanctum/"
    assert build_url("xx") == build_url("fr")
    assert language_of("https://aniimotools.dev/de/map/lost-sanctum/") == "de"
    assert language_of("https://aniimotools.dev/map/lost-sanctum") == "en"
    assert language_of("https://example.com/") is None
