"""User configuration: dataclasses with defaults, TOML load/save."""

from __future__ import annotations

import logging
import tomllib
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

import tomli_w

log = logging.getLogger(__name__)

DEFAULT_URL = "https://aniimotools.dev/fr/map/lost-sanctum/"

OPACITY_MIN, OPACITY_MAX = 0.2, 1.0
ZOOM_MIN, ZOOM_MAX = 0.5, 2.0
INTERVAL_MIN, INTERVAL_MAX = 0.5, 5.0

HsvBounds = list[list[int]]  # [[h, s, v], [h, s, v]] (OpenCV scale: H 0-179)


@dataclass
class SiteConfig:
    url: str = DEFAULT_URL


@dataclass
class WindowConfig:
    x: int = 100
    y: int = 100
    width: int = 520
    height: int = 720
    opacity: float = 0.85
    zoom: float = 0.9
    start_visible: bool = False


@dataclass
class HotkeysConfig:
    toggle_visible: str = "<f8>"
    toggle_interactive: str = "<f9>"
    detect: str = "<f10>"
    opacity_up: str = "<ctrl>+<alt>+<up>"
    opacity_down: str = "<ctrl>+<alt>+<down>"
    zoom_in: str = "<ctrl>+<alt>+<right>"
    zoom_out: str = "<ctrl>+<alt>+<left>"

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class CaptureConfig:
    game_window_title: str = "Aniimo"
    monitor: int = 1
    roi: list[int] | None = None  # [x, y, w, h] relative to the game window


@dataclass
class DetectionConfig:
    auto: bool = False
    interval_s: float = 1.5
    min_confidence: float = 0.6
    orange_hsv: HsvBounds = field(default_factory=lambda: [[5, 120, 150], [22, 255, 255]])
    blue_hsv: HsvBounds = field(default_factory=lambda: [[95, 120, 120], [120, 255, 255]])
    debug: bool = False


@dataclass
class Config:
    site: SiteConfig = field(default_factory=SiteConfig)
    window: WindowConfig = field(default_factory=WindowConfig)
    hotkeys: HotkeysConfig = field(default_factory=HotkeysConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)

    def clamp(self) -> None:
        w = self.window
        w.opacity = min(OPACITY_MAX, max(OPACITY_MIN, w.opacity))
        w.zoom = min(ZOOM_MAX, max(ZOOM_MIN, w.zoom))
        w.width = max(200, w.width)
        w.height = max(150, w.height)
        d = self.detection
        d.interval_s = min(INTERVAL_MAX, max(INTERVAL_MIN, d.interval_s))
        d.min_confidence = min(1.0, max(0.0, d.min_confidence))
        self.capture.monitor = max(0, self.capture.monitor)


# --- validation helpers -------------------------------------------------------------


def _is_hsv_bounds(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(
            isinstance(row, list)
            and len(row) == 3
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 255 for v in row)
            for row in value
        )
    )


def _is_roi(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(isinstance(v, int) and not isinstance(v, bool) for v in value)
        and value[2] > 0
        and value[3] > 0
    )


def _accepts(name: str, default: Any, value: Any) -> bool:
    if name.endswith("_hsv"):
        return _is_hsv_bounds(value)
    if name == "roi":
        return _is_roi(value)
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool)
    if isinstance(default, float):
        return isinstance(value, int | float) and not isinstance(value, bool)
    if isinstance(default, str):
        return isinstance(value, str)
    return False


def _fill(instance: Any, data: dict[str, Any], section: str) -> None:
    for f in fields(instance):
        if f.name not in data:
            continue
        value = data[f.name]
        default = getattr(instance, f.name)
        if _accepts(f.name, default, value):
            if isinstance(default, float):
                value = float(value)
            setattr(instance, f.name, value)
        else:
            log.warning("Invalid value for [%s] %s: %r, using default", section, f.name, value)


def from_dict(data: dict[str, Any]) -> Config:
    config = Config()
    for f in fields(config):
        section = data.get(f.name)
        if isinstance(section, dict):
            _fill(getattr(config, f.name), section, f.name)
    config.clamp()
    return config


def to_dict(config: Config) -> dict[str, Any]:
    def strip_none(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: strip_none(v) for k, v in obj.items() if v is not None}
        return obj

    assert is_dataclass(config)
    return strip_none(asdict(config))


def load(path: Path) -> Config:
    """Load the config; missing values get defaults, a corrupt file is moved to .bak."""
    if not path.exists():
        return Config()
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError, OSError) as exc:
        backup = path.with_suffix(path.suffix + ".bak")
        log.error("Corrupt config file %s (%s), moved to %s", path, exc, backup)
        try:
            path.replace(backup)
        except OSError:
            log.exception("Could not back up corrupt config")
        return Config()
    return from_dict(data)


def save(config: Config, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as fh:
        tomli_w.dump(to_dict(config), fh)
    tmp.replace(path)
