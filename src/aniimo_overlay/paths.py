"""Filesystem locations: user dirs (config, logs, web profile) and bundled resources."""

from __future__ import annotations

import sys
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir, user_log_dir

from aniimo_overlay import APP_ID

# appauthor=False keeps Windows paths short: %APPDATA%\aniimo-overlay
_AUTHOR = False


def config_dir() -> Path:
    path = Path(user_config_dir(APP_ID, _AUTHOR, roaming=True))
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_file() -> Path:
    return config_dir() / "config.toml"


def templates_dir() -> Path:
    """User-made door templates, cropped from the user's own game screenshots."""
    path = config_dir() / "templates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    path = Path(user_data_dir(APP_ID, _AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def web_profile_dir() -> Path:
    path = data_dir() / "web-profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    path = Path(user_log_dir(APP_ID, _AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def debug_dir() -> Path:
    path = log_dir() / "detection-debug"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_path(name: str) -> Path:
    """Path of a bundled resource, both in dev mode and inside the PyInstaller exe."""
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:
        return Path(base) / "aniimo_overlay" / "resources" / name
    return Path(__file__).resolve().parent / "resources" / name
