"""Draw a detection result on an image (preview in the GUI, debug dumps)."""

from __future__ import annotations

import cv2
import numpy as np

from aniimo_overlay.detection.direction import Direction
from aniimo_overlay.detection.doors import DoorDetection

ORANGE_BGR = (0, 140, 255)
BLUE_BGR = (255, 140, 0)


def annotate(
    image: np.ndarray, detection: DoorDetection, direction: Direction | None
) -> np.ndarray:
    out = image.copy()
    scale = max(1.0, min(out.shape[0], out.shape[1]) / 540.0)
    thickness = max(2, round(2 * scale))
    radius = max(12, round(18 * scale))

    for point, color in ((detection.orange, ORANGE_BGR), (detection.blue, BLUE_BGR)):
        if point is not None:
            center = (round(point[0]), round(point[1]))
            cv2.circle(out, center, radius, (0, 0, 0), thickness + 2)
            cv2.circle(out, center, radius, color, thickness)

    if detection.orange is not None and detection.blue is not None:
        p1 = (round(detection.orange[0]), round(detection.orange[1]))
        p2 = (round(detection.blue[0]), round(detection.blue[1]))
        cv2.arrowedLine(out, p1, p2, (255, 255, 255), thickness, cv2.LINE_AA, tipLength=0.08)

    text = f"{direction.sector}  ({detection.confidence:.2f})" if direction else "?"
    org = (round(10 * scale), round(30 * scale))
    font_scale = 0.8 * scale
    cv2.putText(out, text, org, cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thickness + 2)
    cv2.putText(out, text, org, cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness)
    return out
