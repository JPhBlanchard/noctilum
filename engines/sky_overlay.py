"""
Superpositions célestes : plan de l'écliptique et grille équatoriale.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from engines.astro_engine import Observer, _get_eph, _to_sky_time
from engines.projection import altaz_to_xy

# Obliquité J2000 en degrés — suffisant pour l'affichage
_EPS_DEG = 23.4393


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _project_points(
    ra_arr: np.ndarray,
    dec_arr: np.ndarray,
    obs,
    t_sky,
    width: int,
    height: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Calcule alt/az pour un tableau de (ra_h, dec°) et retourne alt°, az°."""
    from skyfield.api import Star
    stars = Star(ra_hours=ra_arr, dec_degrees=dec_arr)
    alt_a, az_a, _ = obs.at(t_sky).observe(stars).apparent().altaz("standard")
    return alt_a.degrees, az_a.degrees


def _altaz_to_plotly(
    alts: np.ndarray,
    azs: np.ndarray,
    width: int,
    height: int,
    segments: list[slice],
) -> tuple[list, list]:
    """
    Projette les points alt/az en xs/ys Plotly.
    `segments` : liste de slice délimitant chaque ligne indépendante.
    Les coupures (horizon / None) sont insérées automatiquement.
    """
    xs: list = []
    ys: list = []

    for seg in segments:
        seg_alts = alts[seg]
        seg_azs  = azs[seg]
        in_seg = False
        for alt, az in zip(seg_alts, seg_azs):
            if alt < 0.0:
                if in_seg:
                    xs.append(None)
                    ys.append(None)
                    in_seg = False
                continue
            xy = altaz_to_xy(alt, az, width, height)
            if xy is None:
                if in_seg:
                    xs.append(None)
                    ys.append(None)
                    in_seg = False
            else:
                xs.append(xy[0])
                ys.append(xy[1])
                in_seg = True
        if in_seg:
            xs.append(None)
            ys.append(None)

    return xs, ys


# ---------------------------------------------------------------------------
# Écliptique
# ---------------------------------------------------------------------------

def get_ecliptic(
    observer: Observer,
    t=None,
    width: int = 800,
    height: int = 800,
    step_deg: int = 2,
) -> tuple[list, list]:
    """
    Retourne (xs, ys) pour la trace du plan de l'écliptique.

    Les coordonnées équatoriales sont calculées analytiquement à partir de
    l'obliquité J2000 (ε = 23.4393°), puis projetées alt/az par Skyfield.
    """
    eps = math.radians(_EPS_DEG)

    lons = np.arange(0, 361, step_deg, dtype=float)
    lam  = np.radians(lons)

    ra_rad  = np.arctan2(np.cos(eps) * np.sin(lam), np.cos(lam))
    dec_rad = np.arcsin(np.sin(eps) * np.sin(lam))

    ra_h  = (np.degrees(ra_rad) % 360.0) / 15.0
    dec_d = np.degrees(dec_rad)

    eph   = _get_eph()
    t_sky = _to_sky_time(t)
    obs   = eph["earth"] + observer.skyfield_location()

    alts, azs = _project_points(ra_h, dec_d, obs, t_sky, width, height)
    return _altaz_to_plotly(alts, azs, width, height, [slice(0, len(lons))])


# ---------------------------------------------------------------------------
# Grille céleste (méridiens + parallèles équatoriaux)
# ---------------------------------------------------------------------------

def get_celestial_grid(
    observer: Observer,
    t=None,
    width: int = 800,
    height: int = 800,
    ra_step_h: int = 2,
    dec_step_deg: int = 30,
) -> tuple[list, list]:
    """
    Retourne (xs, ys) pour la grille équatoriale :
      - Méridiens (RA fixe) tous les `ra_step_h` heures
      - Parallèles (Dec fixe) tous les `dec_step_deg` degrés, y compris l'équateur (Dec=0°)
    """
    all_ra:  list[float] = []
    all_dec: list[float] = []
    segments: list[slice] = []

    # Méridiens — Dec de −85° à +85°, pas 2°
    dec_pts = np.arange(-85.0, 85.1, 2.0)
    for ra_h in range(0, 24, ra_step_h):
        start = len(all_ra)
        all_ra.extend([float(ra_h)] * len(dec_pts))
        all_dec.extend(dec_pts.tolist())
        segments.append(slice(start, len(all_ra)))

    # Parallèles — RA de 0h à 24h (=0°), pas 2°
    ra_pts   = np.arange(0.0, 361.0, 2.0) / 15.0
    max_abs  = 85.0
    dec_from = -dec_step_deg * int(max_abs // dec_step_deg)
    for dec_d in range(dec_from, int(max_abs) + 1, dec_step_deg):
        if abs(dec_d) > max_abs:
            continue
        start = len(all_ra)
        all_ra.extend(ra_pts.tolist())
        all_dec.extend([float(dec_d)] * len(ra_pts))
        segments.append(slice(start, len(all_ra)))

    if not all_ra:
        return [], []

    ra_arr  = np.array(all_ra)
    dec_arr = np.array(all_dec)

    eph   = _get_eph()
    t_sky = _to_sky_time(t)
    obs   = eph["earth"] + observer.skyfield_location()

    alts, azs = _project_points(ra_arr, dec_arr, obs, t_sky, width, height)
    return _altaz_to_plotly(alts, azs, width, height, segments)
