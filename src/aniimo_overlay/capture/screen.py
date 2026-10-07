"""Screen capture with mss. Coordinates are physical pixels."""

from __future__ import annotations

from dataclasses import dataclass

import mss
import numpy as np


@dataclass(frozen=True)
class Region:
    left: int
    top: int
    width: int
    height: int

    def as_mss(self) -> dict[str, int]:
        return {"left": self.left, "top": self.top, "width": self.width, "height": self.height}

    def intersect(self, other: Region) -> Region | None:
        left = max(self.left, other.left)
        top = max(self.top, other.top)
        right = min(self.left + self.width, other.left + other.width)
        bottom = min(self.top + self.height, other.top + other.height)
        if right <= left or bottom <= top:
            return None
        return Region(left, top, right - left, bottom - top)


def monitor_region(index: int = 1) -> Region:
    """mss monitor: 0 = all screens, 1 = primary, 2.. = others. Falls back to primary."""
    with mss.mss() as sct:
        monitors = sct.monitors
        mon = monitors[index] if 0 <= index < len(monitors) else monitors[1]
        return Region(mon["left"], mon["top"], mon["width"], mon["height"])


def monitor_count() -> int:
    with mss.mss() as sct:
        return len(sct.monitors) - 1


def grab(region: Region) -> np.ndarray:
    """Capture a region as a BGR image. A new mss instance per call: mss is not thread-safe."""
    with mss.mss() as sct:
        shot = sct.grab(region.as_mss())
    return np.ascontiguousarray(np.asarray(shot)[:, :, :3])


def mask_regions(image: np.ndarray, origin: Region, regions: list[Region]) -> None:
    """Black out parts of a capture (e.g. our own windows), in place."""
    for region in regions:
        inter = origin.intersect(region)
        if inter is None:
            continue
        x, y = inter.left - origin.left, inter.top - origin.top
        image[y : y + inter.height, x : x + inter.width] = 0
