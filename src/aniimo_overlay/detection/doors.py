"""Find the orange (main) and blue (secondary) doors on a capture of the in-game map.

Pure module: numpy / OpenCV only, no Qt, no screen access.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

Point = tuple[float, float]


@dataclass(frozen=True)
class HsvRange:
    """Inclusive HSV bounds, OpenCV scale (H 0-179). lower H > upper H means hue wrap-around."""

    lower: tuple[int, int, int]
    upper: tuple[int, int, int]

    @classmethod
    def from_list(cls, bounds: list[list[int]]) -> HsvRange:
        lo, hi = bounds
        return cls((int(lo[0]), int(lo[1]), int(lo[2])), (int(hi[0]), int(hi[1]), int(hi[2])))

    def to_list(self) -> list[list[int]]:
        return [list(self.lower), list(self.upper)]


@dataclass(frozen=True)
class DoorParams:
    orange: HsvRange = HsvRange((5, 120, 150), (22, 255, 255))
    blue: HsvRange = HsvRange((95, 120, 120), (120, 255, 255))
    min_area_frac: float = 2e-5  # blob area relative to the image area
    max_area_frac: float = 0.02
    min_circularity: float = 0.35  # 4*pi*area / perimeter^2 (1.0 = disc)
    max_aspect: float = 3.0
    template_threshold: float = 0.7


@dataclass(frozen=True)
class Blob:
    center: Point
    area: float
    circularity: float
    bbox: tuple[int, int, int, int]  # x, y, w, h


@dataclass(frozen=True)
class DoorMatch:
    center: Point
    score: float  # 0..1
    bbox: tuple[int, int, int, int]
    method: str  # "hsv" or "template"


@dataclass
class DoorDetection:
    orange: Point | None
    blue: Point | None
    confidence: float
    orange_match: DoorMatch | None = None
    blue_match: DoorMatch | None = None
    masks: dict[str, np.ndarray] = field(default_factory=dict)  # filled when debug=True

    @property
    def found(self) -> bool:
        return self.orange is not None and self.blue is not None


def hsv_mask(hsv: np.ndarray, rng: HsvRange) -> np.ndarray:
    lo, hi = rng.lower, rng.upper
    if lo[0] <= hi[0]:
        return cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
    # Hue wrap-around (reds): [lo_h, 179] U [0, hi_h]
    a = cv2.inRange(hsv, np.array(lo, np.uint8), np.array((179, hi[1], hi[2]), np.uint8))
    b = cv2.inRange(hsv, np.array((0, lo[1], lo[2]), np.uint8), np.array(hi, np.uint8))
    return cv2.bitwise_or(a, b)


def _kernel_size(shape: tuple[int, ...]) -> int:
    k = max(3, round(min(shape[0], shape[1]) / 360))
    return k if k % 2 == 1 else k + 1


def clean_mask(mask: np.ndarray) -> np.ndarray:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_kernel_size(mask.shape),) * 2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def find_blobs(mask: np.ndarray, params: DoorParams) -> list[Blob]:
    """Plausible door blobs, largest first."""
    image_area = float(mask.shape[0] * mask.shape[1])
    min_area = max(12.0, params.min_area_frac * image_area)
    max_area = params.max_area_frac * image_area
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    blobs: list[Blob] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if not min_area <= area <= max_area:
            continue
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        circularity = min(1.0, 4.0 * math.pi * area / (perimeter * perimeter))
        if circularity < params.min_circularity:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if max(w, h) / max(1, min(w, h)) > params.max_aspect:
            continue
        m = cv2.moments(contour)
        if m["m00"] == 0:
            continue
        center = (m["m10"] / m["m00"], m["m01"] / m["m00"])
        blobs.append(Blob(center, area, circularity, (x, y, w, h)))
    blobs.sort(key=lambda b: b.area, reverse=True)
    return blobs


def _blob_score(blobs: list[Blob]) -> float:
    """Confidence for the biggest blob: round shape + no competing blob of similar size."""
    best = blobs[0]
    shape = min(1.0, best.circularity / 0.7)
    uniqueness = 1.0 - (blobs[1].area / best.area) if len(blobs) > 1 else 1.0
    return 0.5 * shape + 0.5 * uniqueness


def match_template(image: np.ndarray, template: np.ndarray, threshold: float) -> DoorMatch | None:
    """Multi-scale template matching on grayscale images. Best match above threshold."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    tmpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if template.ndim == 3 else template
    best: DoorMatch | None = None
    for scale in np.linspace(0.5, 2.0, 16):
        th, tw = int(tmpl.shape[0] * scale), int(tmpl.shape[1] * scale)
        if th < 6 or tw < 6 or th > gray.shape[0] or tw > gray.shape[1]:
            continue
        resized = cv2.resize(tmpl, (tw, th), interpolation=cv2.INTER_AREA)
        result = cv2.matchTemplate(gray, resized, cv2.TM_CCOEFF_NORMED)
        _, score, _, loc = cv2.minMaxLoc(result)
        if score >= threshold and (best is None or score > best.score):
            center = (loc[0] + tw / 2.0, loc[1] + th / 2.0)
            best = DoorMatch(center, float(score), (loc[0], loc[1], tw, th), "template")
    return best


def _find_door(
    image: np.ndarray,
    hsv: np.ndarray,
    rng: HsvRange,
    params: DoorParams,
    template: np.ndarray | None,
    masks: dict[str, np.ndarray] | None,
    name: str,
) -> DoorMatch | None:
    mask = clean_mask(hsv_mask(hsv, rng))
    if masks is not None:
        masks[name] = mask
    blobs = find_blobs(mask, params)
    if blobs:
        return DoorMatch(blobs[0].center, _blob_score(blobs), blobs[0].bbox, "hsv")
    if template is not None:
        return match_template(image, template, params.template_threshold)
    return None


def detect_doors(
    image: np.ndarray,
    params: DoorParams | None = None,
    templates: dict[str, np.ndarray] | None = None,
    debug: bool = False,
) -> DoorDetection:
    """Locate both doors on a BGR image.

    HSV segmentation first; for a door it cannot find, fall back to the user-made
    template (if any). Confidence is the weakest of the two door scores.
    """
    params = params or DoorParams()
    templates = templates or {}
    if image is None or image.size == 0:
        return DoorDetection(None, None, 0.0)
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    masks: dict[str, np.ndarray] | None = {} if debug else None

    orange = _find_door(image, hsv, params.orange, params, templates.get("orange"), masks, "orange")
    blue = _find_door(image, hsv, params.blue, params, templates.get("blue"), masks, "blue")

    confidence = min(orange.score, blue.score) if orange and blue else 0.0
    return DoorDetection(
        orange=orange.center if orange else None,
        blue=blue.center if blue else None,
        confidence=round(confidence, 3),
        orange_match=orange,
        blue_match=blue,
        masks=masks or {},
    )
