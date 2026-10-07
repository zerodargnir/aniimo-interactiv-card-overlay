"""Runs capture + detection in a QThreadPool worker; the outcome comes back as a signal."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QObject, QRunnable, Signal

from aniimo_overlay.capture.game_window import capture_game
from aniimo_overlay.capture.screen import Region
from aniimo_overlay.detection.annotate import annotate
from aniimo_overlay.detection.direction import Direction, compute_direction
from aniimo_overlay.detection.doors import DoorDetection, DoorParams, detect_doors

log = logging.getLogger(__name__)

DEBUG_KEEP = 20  # debug dumps kept in the log folder


@dataclass
class DetectionRequest:
    source: str  # "manual", "auto", "test"
    params: DoorParams
    templates: dict[str, np.ndarray] = field(default_factory=dict)
    game_title: str = "Aniimo"
    monitor: int = 1
    roi: list[int] | None = None
    hide: list[Region] = field(default_factory=list)
    image: np.ndarray | None = None  # set to analyse a file instead of the screen
    debug_dir: Path | None = None


@dataclass
class DetectionOutcome:
    source: str
    timestamp: float
    detection: DoorDetection | None = None
    direction: Direction | None = None
    image: np.ndarray | None = None
    game_found: bool | None = None  # None when analysing a file
    error: str = ""

    @property
    def found(self) -> bool:
        return self.direction is not None

    def describe(self) -> str:
        """User-facing French summary."""
        if self.error:
            return self.error
        if self.direction is None or self.detection is None:
            if self.detection is not None and (self.detection.orange or self.detection.blue):
                missing = "bleue" if self.detection.orange else "orange"
                return f"Porte {missing} non trouvée — ouvre la carte en jeu"
            return "Portes non trouvées — ouvre la carte en jeu"
        return (
            f"Porte bleue : {self.direction.label_fr} (confiance {self.detection.confidence:.2f})"
        )


def run_detection(request: DetectionRequest) -> DetectionOutcome:
    outcome = DetectionOutcome(source=request.source, timestamp=time.time())
    try:
        if request.image is not None:
            image = request.image
        else:
            capture = capture_game(request.game_title, request.monitor, request.roi, request.hide)
            image = capture.image
            outcome.game_found = capture.game is not None
        detection = detect_doors(
            image, request.params, request.templates, debug=request.debug_dir is not None
        )
        outcome.detection = detection
        outcome.image = image
        if detection.found:
            outcome.direction = compute_direction(detection.orange, detection.blue)
        if request.debug_dir is not None:
            _dump_debug(request.debug_dir, image, detection, outcome.direction)
    except Exception as exc:
        log.exception("Detection failed")
        outcome.error = f"Erreur de détection : {exc}"
    return outcome


def _dump_debug(
    directory: Path, image: np.ndarray, detection: DoorDetection, direction: Direction | None
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
    cv2.imwrite(str(directory / f"{stamp}_capture.png"), image)
    for name, mask in detection.masks.items():
        cv2.imwrite(str(directory / f"{stamp}_mask_{name}.png"), mask)
    cv2.imwrite(str(directory / f"{stamp}_result.png"), annotate(image, detection, direction))
    stamps = sorted({p.name.split("_")[0] for p in directory.glob("*_capture.png")})
    for old in stamps[:-DEBUG_KEEP]:
        for path in directory.glob(f"{old}_*.png"):
            path.unlink(missing_ok=True)
    log.debug("Detection debug images saved as %s_*.png in %s", stamp, directory)


class _Signals(QObject):
    finished = Signal(object)  # DetectionOutcome


class DetectTask(QRunnable):
    def __init__(self, request: DetectionRequest) -> None:
        super().__init__()
        self.request = request
        self.signals = _Signals()

    def run(self) -> None:
        self.signals.finished.emit(run_detection(self.request))
