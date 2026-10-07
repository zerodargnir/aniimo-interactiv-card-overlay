"""Generate synthetic "in-game map" images: dark background, two coloured door markers,
noise and coloured decoys. Used by the tests and by tools/fake_game.py.

    python tools/make_synthetic.py --out tests/fixtures/synthetic
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

SECTOR_ANGLES = {"E": 0, "NE": 45, "N": 90, "NW": 135, "W": 180, "SW": 225, "S": 270, "SE": 315}
SIZES = [(640, 360), (1280, 720), (1920, 1080), (2560, 1440)]


@dataclass
class Synthetic:
    image: np.ndarray
    sector: str
    orange: tuple[float, float]
    blue: tuple[float, float]


def _hsv_color(h: float, s: float, v: float) -> tuple[int, int, int]:
    px = np.uint8([[[int(h) % 180, int(s), int(v)]]])
    b, g, r = cv2.cvtColor(px, cv2.COLOR_HSV2BGR)[0, 0]
    return int(b), int(g), int(r)


def _draw_marker(img: np.ndarray, center: tuple[int, int], radius: int, color, rng) -> None:
    shape = rng.integers(0, 3)
    if shape == 0:
        cv2.circle(img, center, radius, color, -1, cv2.LINE_AA)
    elif shape == 1:
        x, y = center
        r = radius
        cv2.rectangle(img, (x - r, y - r), (x + r, y + r), color, -1)
    else:  # door-ish: rounded top
        x, y = center
        r = radius
        cv2.rectangle(img, (x - r, y - r // 3), (x + r, y + r), color, -1)
        cv2.circle(img, (x, y - r // 3), r, color, -1, cv2.LINE_AA)
    # dark outline + white glyph, like a map icon
    cv2.circle(img, center, max(2, radius // 4), (235, 235, 235), -1, cv2.LINE_AA)


def generate(sector: str, seed: int, size: tuple[int, int] | None = None) -> Synthetic:
    rng = np.random.default_rng(seed)
    w, h = size or SIZES[seed % len(SIZES)]
    scale = min(w, h) / 720.0

    # Background: dark map with greyish rooms and corridors
    img = np.full((h, w, 3), rng.integers(15, 35), np.uint8)
    for _ in range(int(rng.integers(8, 16))):
        x0, y0 = int(rng.integers(0, w)), int(rng.integers(0, h))
        rw, rh = int(rng.integers(40, 200) * scale), int(rng.integers(40, 200) * scale)
        tone = int(rng.integers(40, 90))
        cv2.rectangle(img, (x0, y0), (x0 + rw, y0 + rh), (tone, tone, tone + 5), -1)
    # muted blue-ish "water" (dark, low value: must not trigger the blue mask)
    cv2.circle(img, (int(w * 0.8), int(h * 0.8)), int(80 * scale), (90, 60, 40), -1)

    # Doors
    radius = max(5, int(rng.uniform(9, 16) * scale))
    angle = math.radians(SECTOR_ANGLES[sector] + rng.uniform(-15, 15))
    dist = rng.uniform(0.18, 0.35) * min(w, h)
    margin = radius * 3
    cx = rng.uniform(margin + dist, w - margin - dist) if w > 2 * (margin + dist) else w / 2
    cy = rng.uniform(margin + dist, h - margin - dist) if h > 2 * (margin + dist) else h / 2
    orange = (cx - dist / 2 * math.cos(angle), cy + dist / 2 * math.sin(angle))
    blue = (cx + dist / 2 * math.cos(angle), cy - dist / 2 * math.sin(angle))

    # Decoys first so doors are drawn on top
    decoy_hues = [0, 2, 30, 60, 75, 140, 160]  # red, yellow, green, purple, pink
    for _ in range(int(rng.integers(3, 7))):
        pos = (int(rng.integers(0, w)), int(rng.integers(0, h)))
        if min(math.dist(pos, orange), math.dist(pos, blue)) < radius * 4:
            continue
        color = _hsv_color(rng.choice(decoy_hues), 230, 230)
        cv2.circle(img, pos, int(radius * rng.uniform(0.8, 1.5)), color, -1, cv2.LINE_AA)
    # thin orange route line and tiny orange / blue specks (too thin / too small)
    p1 = (int(rng.integers(0, w)), int(rng.integers(0, h)))
    p2 = (int(rng.integers(0, w)), int(rng.integers(0, h)))
    cv2.line(img, p1, p2, _hsv_color(15, 230, 240), 1, cv2.LINE_AA)
    for _ in range(12):
        pos = (int(rng.integers(0, w)), int(rng.integers(0, h)))
        hue = 15 if rng.random() < 0.5 else 108
        cv2.circle(img, pos, 1, _hsv_color(hue, 230, 240), -1)
    # a smaller orange marker (e.g. a chest icon): must lose against the real door
    for _ in range(5):
        pos = (int(rng.integers(0, w)), int(rng.integers(0, h)))
        if min(math.dist(pos, orange), math.dist(pos, blue)) > radius * 4:
            cv2.circle(img, pos, max(3, int(radius * 0.55)), _hsv_color(17, 220, 230), -1)
            break

    orange_color = _hsv_color(rng.uniform(12, 18), rng.uniform(200, 255), rng.uniform(220, 255))
    blue_color = _hsv_color(rng.uniform(100, 112), rng.uniform(190, 255), rng.uniform(200, 255))
    _draw_marker(img, (round(orange[0]), round(orange[1])), radius, orange_color, rng)
    _draw_marker(img, (round(blue[0]), round(blue[1])), radius, blue_color, rng)

    # Sensor-like noise and slight blur
    noise = rng.normal(0, 6, img.shape)
    img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    img = cv2.GaussianBlur(img, (3, 3), 0)
    return Synthetic(img, sector, orange, blue)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("tests/fixtures/synthetic"))
    parser.add_argument("--per-sector", type=int, default=3)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    count = 0
    for index, sector in enumerate(SECTOR_ANGLES):
        for i in range(args.per_sector):
            synth = generate(sector, seed=index * 100 + i)
            path = args.out / f"{sector.lower()}_{i + 1:02d}.png"
            cv2.imwrite(str(path), synth.image)
            count += 1
    print(f"{count} images written to {args.out}")


if __name__ == "__main__":
    main()
