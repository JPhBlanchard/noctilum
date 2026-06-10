"""
Lignes et noms de constellations.

Source : d3-celestial (ofrohn/d3-celestial)
  - constellations.lines.json : MultiLineString [RA°, Dec°] J2000
  - constellations.json       : centres [RA°, Dec°] + noms (fr/latin)
Cache : data/ (téléchargement unique)

Convention RA dans les deux fichiers : degrés, négatif pour > 180°
  → ra_h = (ra_deg % 360) / 15
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
import requests

from engines.astro_engine import Observer, _get_eph, _to_sky_time
from engines.projection import altaz_to_xy

# ---------------------------------------------------------------------------
# Chemins et URLs
# ---------------------------------------------------------------------------

_DATA_DIR     = Path(__file__).parent.parent / "data"
_LINES_PATH   = _DATA_DIR / "constellations.lines.json"
_CENTERS_PATH = _DATA_DIR / "constellations.json"
_BOUNDS_PATH  = _DATA_DIR / "constellations.bounds.json"

_LINES_URL   = (
    "https://raw.githubusercontent.com/ofrohn/d3-celestial"
    "/master/data/constellations.lines.json"
)
_CENTERS_URL = (
    "https://raw.githubusercontent.com/ofrohn/d3-celestial"
    "/master/data/constellations.json"
)
_BOUNDS_URL  = (
    "https://raw.githubusercontent.com/ofrohn/d3-celestial"
    "/master/data/constellations.bounds.json"
)

# Caches globaux
_pairs:   Optional[list[tuple[tuple[float, float], tuple[float, float]]]] = None
_centers: Optional[list[tuple[float, float, str]]] = None   # (ra_h, dec°, nom)
_bounds:  Optional[list[tuple[tuple[float, float], tuple[float, float]]]] = None


def _ra_deg_to_hours(ra_deg: float) -> float:
    """Convertit RA en degrés (éventuellement négatif) en heures décimales."""
    return (ra_deg % 360.0) / 15.0


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------

def _fetch(url: str, path: Path) -> None:
    from engines.data_download import download as _dl
    _dl(path.name)


def _load_pairs() -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """
    Charge les lignes depuis constellations.lines.json.
    Retourne liste de paires ((ra1_h, dec1°), (ra2_h, dec2°)).
    """
    global _pairs
    if _pairs is not None:
        return _pairs

    if not _LINES_PATH.exists():
        _fetch(_LINES_URL, _LINES_PATH)

    with _LINES_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)

    _pairs = []
    for feat in data.get("features", []):
        geom = feat.get("geometry", {})
        if geom.get("type") != "MultiLineString":
            continue
        for sequence in geom.get("coordinates", []):
            for i in range(len(sequence) - 1):
                _pairs.append((
                    (_ra_deg_to_hours(sequence[i][0]),     sequence[i][1]),
                    (_ra_deg_to_hours(sequence[i + 1][0]), sequence[i + 1][1]),
                ))

    return _pairs


def _load_bounds() -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """
    Charge les limites de constellations depuis constellations.bounds.json.
    Format : Polygon avec une liste de sommets [RA°, Dec°].
    Retourne liste de paires ((ra1_h, dec1°), (ra2_h, dec2°)) comme _load_pairs.
    """
    global _bounds
    if _bounds is not None:
        return _bounds

    if not _BOUNDS_PATH.exists():
        _fetch(_BOUNDS_URL, _BOUNDS_PATH)

    with _BOUNDS_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)

    _bounds = []
    for feat in data.get("features", []):
        geom = feat.get("geometry", {})
        if geom.get("type") != "Polygon":
            continue
        # Polygon : premier anneau = contour extérieur
        ring = geom.get("coordinates", [[]])[0]
        for i in range(len(ring) - 1):
            _bounds.append((
                (_ra_deg_to_hours(ring[i][0]),     ring[i][1]),
                (_ra_deg_to_hours(ring[i + 1][0]), ring[i + 1][1]),
            ))

    return _bounds


def _load_centers() -> list[tuple[float, float, str]]:
    """
    Charge les centres depuis constellations.json.
    Retourne liste de (ra_h, dec°, nom_fr).
    """
    global _centers
    if _centers is not None:
        return _centers

    if not _CENTERS_PATH.exists():
        _fetch(_CENTERS_URL, _CENTERS_PATH)

    with _CENTERS_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)

    _centers = []
    for feat in data.get("features", []):
        geom  = feat.get("geometry", {})
        props = feat.get("properties", {})
        if geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue

        ra_h  = _ra_deg_to_hours(coords[0])
        dec   = float(coords[1])
        # Nom français en priorité, sinon latin, sinon abréviation
        name  = (
            props.get("fr", "").replace(" ", " ").strip()
            or props.get("name", "").strip()
            or props.get("desig", "").strip()
        )
        if name:
            _centers.append((ra_h, dec, name))

    return _centers


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def get_constellation_segments(
    observer: Observer,
    t=None,
    width: int = 800,
    height: int = 800,
) -> tuple[list, list]:
    """
    Retourne (xs, ys) prêts pour un go.Scatter(mode='lines').

    Les segments sont séparés par None (convention Plotly multi-segments).
    Seuls les segments dont les deux extrémités sont au-dessus de l'horizon
    sont inclus.
    """
    from skyfield.api import Star

    pairs = _load_pairs()
    if not pairs:
        return [], []

    ra1  = np.array([p[0][0] for p in pairs])
    dec1 = np.array([p[0][1] for p in pairs])
    ra2  = np.array([p[1][0] for p in pairs])
    dec2 = np.array([p[1][1] for p in pairs])

    eph      = _get_eph()
    t_sky    = _to_sky_time(t)
    location = observer.skyfield_location()
    obs      = eph["earth"] + location

    s1 = Star(ra_hours=ra1, dec_degrees=dec1)
    s2 = Star(ra_hours=ra2, dec_degrees=dec2)

    alt1_a, az1_a, _ = obs.at(t_sky).observe(s1).apparent().altaz("standard")
    alt2_a, az2_a, _ = obs.at(t_sky).observe(s2).apparent().altaz("standard")

    xs: list = []
    ys: list = []

    for alt1, az1, alt2, az2 in zip(
        alt1_a.degrees, az1_a.degrees,
        alt2_a.degrees, az2_a.degrees,
    ):
        if alt1 < 0.0 or alt2 < 0.0:
            continue
        xy1 = altaz_to_xy(alt1, az1, width, height)
        xy2 = altaz_to_xy(alt2, az2, width, height)
        if xy1 is None or xy2 is None:
            continue
        xs.extend([xy1[0], xy2[0], None])
        ys.extend([xy1[1], xy2[1], None])

    return xs, ys


def get_constellation_boundaries(
    observer: Observer,
    t=None,
    width: int = 800,
    height: int = 800,
) -> tuple[list, list]:
    """
    Retourne (xs, ys) pour les limites de constellations (IAU).
    Même convention que get_constellation_segments.
    """
    from skyfield.api import Star

    pairs = _load_bounds()
    if not pairs:
        return [], []

    ra1  = np.array([p[0][0] for p in pairs])
    dec1 = np.array([p[0][1] for p in pairs])
    ra2  = np.array([p[1][0] for p in pairs])
    dec2 = np.array([p[1][1] for p in pairs])

    eph      = _get_eph()
    t_sky    = _to_sky_time(t)
    location = observer.skyfield_location()
    obs      = eph["earth"] + location

    s1 = Star(ra_hours=ra1, dec_degrees=dec1)
    s2 = Star(ra_hours=ra2, dec_degrees=dec2)

    alt1_a, az1_a, _ = obs.at(t_sky).observe(s1).apparent().altaz("standard")
    alt2_a, az2_a, _ = obs.at(t_sky).observe(s2).apparent().altaz("standard")

    xs: list = []
    ys: list = []

    for alt1, az1, alt2, az2 in zip(
        alt1_a.degrees, az1_a.degrees,
        alt2_a.degrees, az2_a.degrees,
    ):
        if alt1 < 0.0 or alt2 < 0.0:
            continue
        xy1 = altaz_to_xy(alt1, az1, width, height)
        xy2 = altaz_to_xy(alt2, az2, width, height)
        if xy1 is None or xy2 is None:
            continue
        xs.extend([xy1[0], xy2[0], None])
        ys.extend([xy1[1], xy2[1], None])

    return xs, ys


def get_constellation_labels(
    observer: Observer,
    t=None,
    width: int = 800,
    height: int = 800,
) -> list[tuple[float, float, str]]:
    """
    Retourne la liste des labels de constellations visibles.
    Format : [(x_px, y_px, nom), …] pour les centres au-dessus de l'horizon.
    """
    from skyfield.api import Star

    centers = _load_centers()
    if not centers:
        return []

    ra_arr  = np.array([c[0] for c in centers])
    dec_arr = np.array([c[1] for c in centers])
    names   = [c[2] for c in centers]

    eph      = _get_eph()
    t_sky    = _to_sky_time(t)
    location = observer.skyfield_location()
    obs      = eph["earth"] + location

    stars = Star(ra_hours=ra_arr, dec_degrees=dec_arr)
    alt_a, az_a, _ = obs.at(t_sky).observe(stars).apparent().altaz("standard")

    result = []
    for alt, az, name in zip(alt_a.degrees, az_a.degrees, names):
        if alt < 5.0:   # petite marge — évite les labels collés à l'horizon
            continue
        xy = altaz_to_xy(alt, az, width, height)
        if xy is None:
            continue
        result.append((xy[0], xy[1], name))

    return result


# ---------------------------------------------------------------------------
# API pour la vue paysage (retourne alt/az bruts, sans projection)
# ---------------------------------------------------------------------------

def get_constellation_altaz_boundaries(
    observer: Observer,
    t=None,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """
    Retourne les segments de limites IAU au-dessus de l'horizon.
    Format : [((alt1, az1), (alt2, az2)), …]
    """
    from skyfield.api import Star

    pairs = _load_bounds()
    if not pairs:
        return []

    ra1  = np.array([p[0][0] for p in pairs])
    dec1 = np.array([p[0][1] for p in pairs])
    ra2  = np.array([p[1][0] for p in pairs])
    dec2 = np.array([p[1][1] for p in pairs])

    eph      = _get_eph()
    t_sky    = _to_sky_time(t)
    location = observer.skyfield_location()
    obs      = eph["earth"] + location

    s1 = Star(ra_hours=ra1, dec_degrees=dec1)
    s2 = Star(ra_hours=ra2, dec_degrees=dec2)

    alt1_a, az1_a, _ = obs.at(t_sky).observe(s1).apparent().altaz("standard")
    alt2_a, az2_a, _ = obs.at(t_sky).observe(s2).apparent().altaz("standard")

    result = []
    for alt1, az1, alt2, az2 in zip(
        alt1_a.degrees, az1_a.degrees,
        alt2_a.degrees, az2_a.degrees,
    ):
        if alt1 < 0.0 or alt2 < 0.0:
            continue
        result.append(((alt1, az1), (alt2, az2)))

    return result


def get_constellation_altaz_segments(
    observer: Observer,
    t=None,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """
    Retourne les segments de constellations au-dessus de l'horizon.
    Format : [((alt1, az1), (alt2, az2)), …]
    """
    from skyfield.api import Star

    pairs = _load_pairs()
    if not pairs:
        return []

    ra1  = np.array([p[0][0] for p in pairs])
    dec1 = np.array([p[0][1] for p in pairs])
    ra2  = np.array([p[1][0] for p in pairs])
    dec2 = np.array([p[1][1] for p in pairs])

    eph      = _get_eph()
    t_sky    = _to_sky_time(t)
    location = observer.skyfield_location()
    obs      = eph["earth"] + location

    s1 = Star(ra_hours=ra1, dec_degrees=dec1)
    s2 = Star(ra_hours=ra2, dec_degrees=dec2)

    alt1_a, az1_a, _ = obs.at(t_sky).observe(s1).apparent().altaz("standard")
    alt2_a, az2_a, _ = obs.at(t_sky).observe(s2).apparent().altaz("standard")

    result = []
    for alt1, az1, alt2, az2 in zip(
        alt1_a.degrees, az1_a.degrees,
        alt2_a.degrees, az2_a.degrees,
    ):
        if alt1 < 0.0 or alt2 < 0.0:
            continue
        result.append(((alt1, az1), (alt2, az2)))

    return result


def get_constellation_altaz_labels(
    observer: Observer,
    t=None,
) -> list[tuple[float, float, str]]:
    """
    Retourne les centres de constellations au-dessus de l'horizon.
    Format : [(alt, az, nom), …]
    """
    from skyfield.api import Star

    centers = _load_centers()
    if not centers:
        return []

    ra_arr  = np.array([c[0] for c in centers])
    dec_arr = np.array([c[1] for c in centers])
    names   = [c[2] for c in centers]

    eph      = _get_eph()
    t_sky    = _to_sky_time(t)
    location = observer.skyfield_location()
    obs      = eph["earth"] + location

    stars = Star(ra_hours=ra_arr, dec_degrees=dec_arr)
    alt_a, az_a, _ = obs.at(t_sky).observe(stars).apparent().altaz("standard")

    return [
        (alt, az, name)
        for alt, az, name in zip(alt_a.degrees, az_a.degrees, names)
        if alt >= 5.0
    ]
