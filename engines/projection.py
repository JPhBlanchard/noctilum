"""
Projection des coordonnées célestes (alt/az) vers pixels 2D.

Projection azimutale stéréographique :
  zénith  = centre du disque
  horizon = bord du disque  (rayon = min(width,height)/2 − marge)
  nord    = haut   (az=0°  → y décroissant)
  est     = droite (az=90° → x croissant)
"""

from __future__ import annotations

import math
from typing import Optional

# Marge en pixels entre l'horizon et le bord de l'image
_MARGIN: int = 20

# Rayon du disque pour une image 800×800 — exporté pour sky_chart.py
CHART_RADIUS: int = 400 - _MARGIN  # 380 px


# ---------------------------------------------------------------------------
# Projection spatiale
# ---------------------------------------------------------------------------

def altaz_to_xy(
    alt_deg: float,
    az_deg: float,
    width: int = 800,
    height: int = 800,
) -> Optional[tuple[float, float]]:
    """
    Projette (alt, az) en pixels (x, y) via la projection stéréographique
    azimutale centrée sur le zénith.

      alt=90° → centre exact (width/2, height/2)
      alt=0°  → bord du disque (rayon = min(width,height)/2 − _MARGIN)
      az=0°   → nord (haut,  y décroissant)
      az=90°  → est  (droite, x croissant)

    Retourne None si alt < 0° (corps sous l'horizon).

    Formule : r = R·tan(z/2),  z = 90° − alt
    À z=90° (horizon) : r = R·tan(45°) = R  ✓
    À z=0°  (zénith)  : r = 0             ✓
    """
    if alt_deg < 0.0:
        return None

    radius = min(width, height) / 2.0 - _MARGIN
    cx = width / 2.0
    cy = height / 2.0

    z_rad = math.radians(90.0 - alt_deg)   # distance zénithale
    az_rad = math.radians(az_deg)

    r = radius * math.tan(z_rad / 2.0)

    x = cx + r * math.sin(az_rad)
    y = cy - r * math.cos(az_rad)
    return x, y


# ---------------------------------------------------------------------------
# Taille des points
# ---------------------------------------------------------------------------

# Interpolation linéaire : mag ∈ [−2, 5] → taille ∈ [8, 1.5] px
_MAG_SIZE_LO  = -2.0
_MAG_SIZE_HI  =  5.0
_SIZE_BRIGHT  =  8.0   # px à mag −2
_SIZE_FAINT   =  1.5   # px à mag  5
_SIZE_SLOPE   = (_SIZE_FAINT - _SIZE_BRIGHT) / (_MAG_SIZE_HI - _MAG_SIZE_LO)


def magnitude_to_size(magnitude: float) -> float:
    """
    Rayon en pixels d'un point stellaire en fonction de la magnitude.

    Interpolation linéaire inversée, clampée :
      mag −2 → 8 px  |  mag 0 → ~6 px  |  mag 3 → ~3.4 px  |  mag 5 → 1.5 px
    """
    size = _SIZE_BRIGHT + (magnitude - _MAG_SIZE_LO) * _SIZE_SLOPE
    return max(_SIZE_FAINT, min(_SIZE_BRIGHT, size))


# ---------------------------------------------------------------------------
# Opacité des points
# ---------------------------------------------------------------------------

# Interpolation linéaire : mag ∈ [1, 4] → opacité ∈ [1.0, 0.5]
_MAG_OPA_BRIGHT = 1.0
_MAG_OPA_FAINT  = 4.0
_OPA_BRIGHT     = 1.0
_OPA_FAINT      = 0.5
_OPA_SLOPE      = (_OPA_FAINT - _OPA_BRIGHT) / (_MAG_OPA_FAINT - _MAG_OPA_BRIGHT)


def magnitude_to_opacity(magnitude: float) -> float:
    """
    Opacité [0.0–1.0] d'une étoile en fonction de la magnitude apparente.

      mag ≤ 1 → 1.0  (pleine opacité)
      mag = 4 → 0.5  (demi-transparence)
      mag > 4 → 0.5  (clampé)
    """
    opacity = _OPA_BRIGHT + (magnitude - _MAG_OPA_BRIGHT) * _OPA_SLOPE
    return max(_OPA_FAINT, min(_OPA_BRIGHT, opacity))
