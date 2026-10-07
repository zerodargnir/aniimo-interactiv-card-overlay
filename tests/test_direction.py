from __future__ import annotations

import math

import pytest

from aniimo_overlay.detection.direction import (
    NUMPAD,
    compute_direction,
    sector_from_angle,
)

ORIGIN = (500.0, 400.0)


def point_at(angle_deg: float, dist: float = 100.0) -> tuple[float, float]:
    """Screen point at a compass angle from ORIGIN (screen Y grows downwards)."""
    a = math.radians(angle_deg)
    return (ORIGIN[0] + dist * math.cos(a), ORIGIN[1] - dist * math.sin(a))


@pytest.mark.parametrize(
    ("angle", "sector", "key"),
    [
        (0, "E", 6),
        (45, "NE", 9),
        (90, "N", 8),
        (135, "NW", 7),
        (180, "W", 4),
        (225, "SW", 1),
        (270, "S", 2),
        (315, "SE", 3),
    ],
)
def test_sector_centers(angle, sector, key):
    d = compute_direction(ORIGIN, point_at(angle))
    assert d is not None
    assert d.sector == sector
    assert d.numpad == key
    assert d.distance == pytest.approx(100.0)


def test_screen_y_axis_is_flipped():
    # Blue door *above* orange on screen (smaller y) is North.
    assert compute_direction((100, 100), (100, 20)).sector == "N"
    assert compute_direction((100, 100), (100, 180)).sector == "S"
    assert compute_direction((100, 100), (180, 20)).sector == "NE"
    assert compute_direction((100, 100), (20, 180)).sector == "SW"


@pytest.mark.parametrize("center", [0, 45, 90, 135, 180, 225, 270, 315])
def test_sector_boundaries(center):
    expected = sector_from_angle(center)
    assert sector_from_angle(center + 22.4) == expected
    assert sector_from_angle(center - 22.4) == expected
    # Exactly on the boundary: goes to the next sector counter-clockwise.
    assert sector_from_angle(center + 22.5) != expected
    assert sector_from_angle(center - 22.5) == expected


@pytest.mark.parametrize(
    ("angle", "sector"), [(22.5, "NE"), (67.5, "N"), (337.5, "E"), (-22.5, "E")]
)
def test_boundary_convention(angle, sector):
    assert sector_from_angle(angle) == sector


def test_angle_wraps():
    assert sector_from_angle(359.9) == "E"
    assert sector_from_angle(360.0) == "E"
    assert sector_from_angle(720 + 90) == "N"


def test_just_around_boundaries_with_vectors():
    assert compute_direction(ORIGIN, point_at(22.0)).sector == "E"
    assert compute_direction(ORIGIN, point_at(23.0)).sector == "NE"
    assert compute_direction(ORIGIN, point_at(-22.0)).sector == "E"
    assert compute_direction(ORIGIN, point_at(-23.0)).sector == "SE"


def test_same_position_returns_none():
    assert compute_direction((10, 10), (10, 10)) is None
    assert compute_direction((10, 10), (10.5, 10.2)) is None
    assert compute_direction((10, 10), (14, 10), min_distance=5) is None


def test_angle_and_label():
    d = compute_direction((0, 0), (10, -10))
    assert d.angle_deg == pytest.approx(45.0)
    assert d.label_fr == "Nord-Est"


def test_numpad_is_compass_layout():
    assert NUMPAD == {"N": 8, "NE": 9, "E": 6, "SE": 3, "S": 2, "SW": 1, "W": 4, "NW": 7}
