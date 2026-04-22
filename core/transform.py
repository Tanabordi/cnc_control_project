"""Affine transformation math for CNC coordinate mapping.

Pure-math module — no PySide6 / Qt dependencies.
Used for:
  - Center-shifting imported paths (origin mode)
  - 2-point affine calibration (crooked material compensation)

The 2-point calibration computes rotation + uniform scale + translation
from two known point pairs (design-space ↔ machine-space).
"""

import math
from dataclasses import dataclass
from typing import List, Tuple, Optional


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Polyline = List[Tuple[float, float]]


@dataclass
class AffineResult:
    """Result of a 2-point affine calibration."""
    scale: float       # uniform scale factor  (machine / design)
    rotation: float    # rotation angle in radians
    cos_r: float       # cos(rotation) * scale  — pre-computed for speed
    sin_r: float       # sin(rotation) * scale


# ---------------------------------------------------------------------------
# Bounding box
# ---------------------------------------------------------------------------

def compute_bounding_box(
    polylines: List[Polyline],
) -> Tuple[float, float, float, float]:
    """Return ``(xmin, ymin, xmax, ymax)`` for a list of polylines.

    Raises ``ValueError`` if *polylines* is empty or contains no points.
    """
    all_x = [pt[0] for poly in polylines for pt in poly]
    all_y = [pt[1] for poly in polylines for pt in poly]
    if not all_x:
        raise ValueError("No points in polylines")
    return min(all_x), min(all_y), max(all_x), max(all_y)


# ---------------------------------------------------------------------------
# Center-shift
# ---------------------------------------------------------------------------

def center_shift_polylines(
    polylines: List[Polyline],
) -> List[Polyline]:
    """Shift all polyline vertices so the bounding-box center is at (0, 0).

    Returns a **new** list of polylines; the originals are not mutated.
    """
    xmin, ymin, xmax, ymax = compute_bounding_box(polylines)
    cx = (xmin + xmax) / 2.0
    cy = (ymin + ymax) / 2.0
    return [
        [(x - cx, y - cy) for x, y in poly]
        for poly in polylines
    ]


# ---------------------------------------------------------------------------
# 2-point affine calibration
# ---------------------------------------------------------------------------

def compute_affine_2point(
    design_p1: Tuple[float, float],
    design_p2: Tuple[float, float],
    machine_p1: Tuple[float, float],
    machine_p2: Tuple[float, float],
) -> Optional[AffineResult]:
    """Compute affine parameters (scale + rotation) from two point pairs.

    Parameters
    ----------
    design_p1, design_p2 :
        Two reference coordinates in design space (e.g. bounding-box corners).
    machine_p1, machine_p2 :
        Corresponding machine-space coordinates (user-jogged positions).

    Returns
    -------
    AffineResult or None if the point pairs are degenerate (zero distance).
    """
    dcx = design_p2[0] - design_p1[0]
    dcy = design_p2[1] - design_p1[1]
    dmx = machine_p2[0] - machine_p1[0]
    dmy = machine_p2[1] - machine_p1[1]

    design_len = math.sqrt(dcx * dcx + dcy * dcy)
    machine_len = math.sqrt(dmx * dmx + dmy * dmy)

    if design_len == 0 or machine_len == 0:
        return None

    scale = machine_len / design_len
    rotation = math.atan2(dmy, dmx) - math.atan2(dcy, dcx)
    cos_r = math.cos(rotation) * scale
    sin_r = math.sin(rotation) * scale

    return AffineResult(scale=scale, rotation=rotation,
                        cos_r=cos_r, sin_r=sin_r)


def apply_affine_to_point(
    x: float,
    y: float,
    anchor: Tuple[float, float],
    cos_r: float,
    sin_r: float,
    translation: Tuple[float, float],
) -> Tuple[float, float]:
    """Apply rotation+scale around *anchor*, then translate.

    Parameters
    ----------
    x, y : point to transform (design space, already scaled)
    anchor : rotation anchor in design space  (usually design_p1)
    cos_r, sin_r : from ``AffineResult.cos_r / sin_r``
    translation : (tx, ty) — machine position of the anchor point

    Returns
    -------
    (new_x, new_y) in machine space.
    """
    # Local coordinates relative to anchor
    lx = x - anchor[0]
    ly = y - anchor[1]
    # Rotate + scale
    rx = lx * cos_r - ly * sin_r
    ry = lx * sin_r + ly * cos_r
    # Translate to machine space
    return (translation[0] + rx, translation[1] + ry)


def apply_affine_to_polylines(
    polylines: List[Polyline],
    anchor: Tuple[float, float],
    cos_r: float,
    sin_r: float,
    translation: Tuple[float, float],
) -> List[Polyline]:
    """Apply affine transform to all vertices in a list of polylines.

    Returns a **new** list; originals are not mutated.
    """
    return [
        [apply_affine_to_point(x, y, anchor, cos_r, sin_r, translation)
         for x, y in poly]
        for poly in polylines
    ]
