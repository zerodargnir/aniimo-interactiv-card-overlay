"""Door colour calibration and template cropping, from the user's own game screenshots.

Library functions are used by the GUI calibration dialog. The CLI works without a
display (OpenCV headless), with coordinates given on the command line:

    python -m aniimo_overlay.detection.calibrate capture.png --orange 812,440 --blue 1033,301
    python -m aniimo_overlay.detection.calibrate capture.png --crop orange 800,428,24,24
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import cv2
import numpy as np

from aniimo_overlay.detection.doors import HsvRange

log = logging.getLogger(__name__)

HUE_MARGIN = 6
SAT_MARGIN = 50
VAL_MARGIN = 60
MIN_SAT = 60
MIN_VAL = 60


def hsv_range_from_point(image: np.ndarray, point: tuple[int, int], radius: int = 4) -> HsvRange:
    """HSV bounds covering the coloured pixels around a clicked point.

    Hue is handled circularly so reds near 0/179 get a wrap-around range.
    """
    h, w = image.shape[:2]
    x, y = int(point[0]), int(point[1])
    if not (0 <= x < w and 0 <= y < h):
        raise ValueError(f"Point {point} is outside the image ({w}x{h})")
    patch = image[max(0, y - radius) : y + radius + 1, max(0, x - radius) : x + radius + 1]
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(int)
    colored = hsv[hsv[:, 1] >= MIN_SAT]
    if len(colored) == 0:
        raise ValueError("Pas de couleur vive à cet endroit : clique bien au centre de la porte.")

    hue = colored[:, 0]
    ref = int(np.median(hue))
    delta = ((hue - ref + 90) % 180) - 90  # signed circular distance to the median
    h_lo = ref + int(np.percentile(delta, 5)) - HUE_MARGIN
    h_hi = ref + int(np.percentile(delta, 95)) + HUE_MARGIN
    s_lo = max(MIN_SAT, int(np.percentile(colored[:, 1], 5)) - SAT_MARGIN)
    v_lo = max(MIN_VAL, int(np.percentile(colored[:, 2], 5)) - VAL_MARGIN)
    if h_hi - h_lo >= 179:
        h_lo, h_hi = 0, 179
    return HsvRange((h_lo % 180, s_lo, v_lo), (h_hi % 180, 255, 255))


def crop_template(image: np.ndarray, rect: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = rect
    crop = image[max(0, y) : y + h, max(0, x) : x + w]
    if crop.size == 0:
        raise ValueError("Zone de découpe vide")
    return crop.copy()


def save_template(template: np.ndarray, name: str, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.png"
    if not cv2.imwrite(str(path), template):
        raise OSError(f"Could not write {path}")
    return path


def load_templates(directory: Path) -> dict[str, np.ndarray]:
    templates: dict[str, np.ndarray] = {}
    for name in ("orange", "blue"):
        path = directory / f"{name}.png"
        if path.exists():
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is not None:
                templates[name] = image
    return templates


def read_image(path: Path) -> np.ndarray:
    # imdecode handles non-ASCII Windows paths, unlike imread
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Image illisible : {path}")
    return image


def _parse_ints(text: str, count: int) -> tuple[int, ...]:
    parts = [int(p) for p in text.split(",")]
    if len(parts) != count:
        raise argparse.ArgumentTypeError(f"expected {count} comma-separated integers")
    return tuple(parts)


def main(argv: list[str] | None = None) -> int:
    from aniimo_overlay import config as config_mod
    from aniimo_overlay import paths

    parser = argparse.ArgumentParser(description="Calibrate door colours from a screenshot.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--orange", type=lambda s: _parse_ints(s, 2), help="x,y of the orange door")
    parser.add_argument("--blue", type=lambda s: _parse_ints(s, 2), help="x,y of the blue door")
    parser.add_argument(
        "--crop",
        nargs=2,
        metavar=("NAME", "X,Y,W,H"),
        help="crop a template (NAME = orange|blue) into the config folder",
    )
    parser.add_argument("--dry-run", action="store_true", help="print, do not save")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    image = read_image(args.image)
    cfg_path = paths.config_file()
    cfg = config_mod.load(cfg_path)
    changed = False

    for name, point in (("orange", args.orange), ("blue", args.blue)):
        if point is None:
            continue
        rng = hsv_range_from_point(image, point)
        log.info("%s HSV range: %s", name, rng.to_list())
        setattr(cfg.detection, f"{name}_hsv", rng.to_list())
        changed = True

    if args.crop:
        name, rect_text = args.crop
        if name not in ("orange", "blue"):
            parser.error("NAME must be orange or blue")
        template = crop_template(image, _parse_ints(rect_text, 4))
        if not args.dry_run:
            log.info("Template saved to %s", save_template(template, name, paths.templates_dir()))

    if changed and not args.dry_run:
        config_mod.save(cfg, cfg_path)
        log.info("Config saved to %s", cfg_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
