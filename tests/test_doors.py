from __future__ import annotations

import cv2
import numpy as np
import pytest
from make_synthetic import SECTOR_ANGLES, SIZES, generate

from aniimo_overlay.detection.calibrate import crop_template, hsv_range_from_point
from aniimo_overlay.detection.direction import compute_direction
from aniimo_overlay.detection.doors import DoorParams, HsvRange, detect_doors, hsv_mask

CASES = [(sector, seed) for sector in SECTOR_ANGLES for seed in range(12)]


@pytest.mark.parametrize(("sector", "seed"), CASES)
def test_synthetic_images_are_classified(sector, seed):
    synth = generate(sector, seed=seed)
    det = detect_doors(synth.image)
    assert det.found, f"doors not found ({synth.image.shape})"
    assert np.hypot(det.orange[0] - synth.orange[0], det.orange[1] - synth.orange[1]) < 8
    assert np.hypot(det.blue[0] - synth.blue[0], det.blue[1] - synth.blue[1]) < 8
    direction = compute_direction(det.orange, det.blue)
    assert direction is not None and direction.sector == sector
    assert det.confidence >= 0.6


@pytest.mark.parametrize("size", SIZES)
def test_every_scale(size):
    for sector in SECTOR_ANGLES:
        synth = generate(sector, seed=7, size=size)
        det = detect_doors(synth.image)
        assert compute_direction(det.orange, det.blue).sector == sector


def test_empty_image_finds_nothing():
    det = detect_doors(np.full((720, 1280, 3), 25, np.uint8))
    assert det.orange is None and det.blue is None
    assert det.confidence == 0.0
    assert not det.found


def test_only_decoys_finds_nothing():
    img = np.full((720, 1280, 3), 25, np.uint8)
    cv2.circle(img, (200, 200), 15, (0, 0, 220), -1)  # red
    cv2.circle(img, (400, 200), 15, (0, 220, 0), -1)  # green
    cv2.circle(img, (600, 200), 15, (200, 0, 200), -1)  # purple
    cv2.line(img, (0, 500), (1280, 520), (0, 140, 255), 1)  # thin orange line
    det = detect_doors(img)
    assert det.orange is None and det.blue is None


def test_one_door_missing_has_zero_confidence():
    img = np.full((720, 1280, 3), 25, np.uint8)
    cv2.circle(img, (300, 300), 14, (0, 140, 255), -1)
    det = detect_doors(img)
    assert det.orange is not None and det.blue is None
    assert det.confidence == 0.0


def test_debug_masks():
    det = detect_doors(generate("N", 1).image, debug=True)
    assert set(det.masks) == {"orange", "blue"}


def test_bgra_and_gray_inputs():
    synth = generate("E", 3, size=(1280, 720))
    bgra = cv2.cvtColor(synth.image, cv2.COLOR_BGR2BGRA)
    assert detect_doors(bgra).found
    gray = cv2.cvtColor(synth.image, cv2.COLOR_BGR2GRAY)
    assert not detect_doors(gray).found


def test_hue_wraparound_mask():
    hsv = np.array([[[178, 200, 200], [2, 200, 200], [90, 200, 200]]], np.uint8)
    mask = hsv_mask(hsv, HsvRange((175, 100, 100), (5, 255, 255)))
    assert mask.tolist() == [[255, 255, 0]]


def test_calibration_from_click_then_detect():
    # Doors with unusual colours: defaults would miss them, calibration must catch them.
    img = np.full((720, 1280, 3), 25, np.uint8)
    cv2.circle(img, (300, 500), 14, (40, 200, 230), -1)  # yellow-ish "orange" door
    cv2.circle(img, (700, 200), 14, (230, 230, 40), -1)  # cyan-ish "blue" door
    params = DoorParams(
        orange=hsv_range_from_point(img, (300, 500)),
        blue=hsv_range_from_point(img, (700, 200)),
    )
    det = detect_doors(img, params)
    assert det.found
    assert compute_direction(det.orange, det.blue).sector == "NE"


def test_calibration_on_grey_pixel_fails():
    img = np.full((100, 100, 3), 80, np.uint8)
    with pytest.raises(ValueError):
        hsv_range_from_point(img, (50, 50))


def test_template_fallback():
    synth = generate("SE", 5, size=(1280, 720))
    ox, oy = round(synth.orange[0]), round(synth.orange[1])
    bx, by = round(synth.blue[0]), round(synth.blue[1])
    templates = {
        "orange": crop_template(synth.image, (ox - 16, oy - 16, 32, 32)),
        "blue": crop_template(synth.image, (bx - 16, by - 16, 32, 32)),
    }
    # HSV ranges that match nothing: detection must come from the templates.
    nothing = HsvRange((0, 255, 255), (0, 255, 255))
    det = detect_doors(synth.image, DoorParams(orange=nothing, blue=nothing), templates)
    assert det.found
    assert det.orange_match.method == "template"
    assert compute_direction(det.orange, det.blue).sector == "SE"
