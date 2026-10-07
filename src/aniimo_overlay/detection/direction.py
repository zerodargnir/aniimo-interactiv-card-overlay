"""Turn the orange -> blue door vector into one of 8 compass sectors and a numpad key."""

from __future__ import annotations

import math
from dataclasses import dataclass

# Counter-clockwise from East, 45 degrees each (math convention: 0 = East, 90 = North).
SECTORS: tuple[str, ...] = ("E", "NE", "N", "NW", "W", "SW", "S", "SE")

# Numpad layout mirrors a compass rose.
NUMPAD: dict[str, int] = {"N": 8, "NE": 9, "E": 6, "SE": 3, "S": 2, "SW": 1, "W": 4, "NW": 7}

LABELS_FR: dict[str, str] = {
    "N": "Nord",
    "NE": "Nord-Est",
    "E": "Est",
    "SE": "Sud-Est",
    "S": "Sud",
    "SW": "Sud-Ouest",
    "W": "Ouest",
    "NW": "Nord-Ouest",
}

Point = tuple[float, float]


@dataclass(frozen=True)
class Direction:
    sector: str  # "N", "NE", ...
    numpad: int  # numpad digit for the sector
    angle_deg: float  # 0 = East, 90 = North, counter-clockwise, in [0, 360)
    distance: float  # pixels between the two doors

    @property
    def label_fr(self) -> str:
        return LABELS_FR[self.sector]


def sector_from_angle(angle_deg: float) -> str:
    """Map an angle (0 = East, counter-clockwise) to a sector.

    Each sector covers [center - 22.5, center + 22.5); an angle exactly on a boundary
    goes to the next sector counter-clockwise (22.5 -> NE, 67.5 -> N, ...).
    """
    index = int(((angle_deg + 22.5) % 360.0) // 45.0) % 8
    return SECTORS[index]


def compute_direction(orange: Point, blue: Point, min_distance: float = 1.0) -> Direction | None:
    """Direction of the blue door seen from the orange door, in screen coordinates.

    Screen Y grows downwards, so it is flipped to get a North-up angle.
    Returns None when the doors are (almost) at the same spot.
    """
    dx = blue[0] - orange[0]
    dy = orange[1] - blue[1]  # flip the screen Y axis
    distance = math.hypot(dx, dy)
    if distance < min_distance:
        return None
    angle = math.degrees(math.atan2(dy, dx)) % 360.0
    sector = sector_from_angle(angle)
    return Direction(sector=sector, numpad=NUMPAD[sector], angle_deg=angle, distance=distance)
