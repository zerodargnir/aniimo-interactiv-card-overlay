"""Is the in-game map open? (later phase, not implemented yet).

Detection is currently triggered by the player (F10) once the map is open, or by the
auto mode which only reacts when both doors are found with enough confidence.
"""

from __future__ import annotations

import numpy as np


def is_map_open(image: np.ndarray) -> bool | None:
    """Unknown for now: returns None. Needs real game screenshots to be implemented."""
    return None
