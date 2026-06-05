"""
Silhouette de la Voie Lactée — polygones depuis mw.json (d3-celestial).
5 couches de densité croissante (mw-1 = bords → mw-5 = noyau brillant).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
import requests

from engines.astro_engine import Observer, _get_eph, _to_sky_time

# ---------------------------------------------------------------------------
# Chemins et source
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent.parent / "data"
_MW_PATH  = _DATA_DIR / "mw.json"
_MW_URL   = (
    "https://raw.githubusercontent.com/ofrohn/d3-celestial"
    "/master/data/mw.json"
)

# Opacité de remplissage par couche (du bord vers le centre)
_LAYER_OPACITY: dict[str, float] = {
    "ol1": 0.06,
    "ol2": 0.12,
    "ol3": 0.22,
    "ol4": 0.32,
    "ol5": 0.48,
}

# Couleur de base (blanc-bleuté, subtil)
MW_COLOR = (200, 215, 245)

# Cache global : liste de ([(ra_h, dec_deg), …], opacity)
_raw_polygons: Optional[list[tuple[list, float]]] = None


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------

def _ra_deg_to_hours(ra_deg: float) -> float:
    return (float(ra_deg) % 360.0) / 15.0


def _load_polygons() -> list[tuple[list, float]]:
    """Charge mw.json, retourne liste de (verts_radec, opacity)."""
    global _raw_polygons
    if _raw_polygons is not None:
        return _raw_polygons

    if not _MW_PATH.exists():
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        resp = requests.get(_MW_URL, timeout=30)
        resp.raise_for_status()
        _MW_PATH.write_bytes(resp.content)

    with _MW_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)

    _raw_polygons = []
    for feat in data.get("features", []):
        lid     = feat.get("id") or feat.get("properties", {}).get("id", "mw-1")
        opacity = _LAYER_OPACITY.get(lid, 0.10)
        geom    = feat.get("geometry", {})
        gtype   = geom.get("type", "")
        coords  = geom.get("coordinates", [])

        rings: list = []
        if gtype == "Polygon":
            rings = list(coords)          # tous les anneaux (outer + trous)
        elif gtype == "MultiPolygon":
            for poly in coords:
                rings.extend(poly)        # tous les anneaux de chaque polygone

        for ring in rings:
            if len(ring) < 4:
                continue
            verts = [(_ra_deg_to_hours(p[0]), float(p[1])) for p in ring]
            _raw_polygons.append((verts, opacity))

    return _raw_polygons


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def get_milkyway_polygons_altaz(
    observer: Observer,
    t=None,
) -> list[tuple[list[tuple[float, float]], float]]:
    """
    Retourne [([(alt°, az°), …], opacity), …] — un tuple par polygone.
    Les coordonnées sont converties en une seule passe Skyfield.
    """
    from skyfield.api import Star

    polys = _load_polygons()
    if not polys:
        return []

    # Batch de tous les sommets en un seul appel Skyfield
    all_ra:  list[float] = []
    all_dec: list[float] = []
    slices:  list[tuple[slice, float]] = []

    for verts, opacity in polys:
        start = len(all_ra)
        for ra_h, dec_d in verts:
            all_ra.append(ra_h)
            all_dec.append(dec_d)
        slices.append((slice(start, len(all_ra)), opacity))

    ra_arr  = np.array(all_ra)
    dec_arr = np.array(all_dec)

    eph   = _get_eph()
    t_sky = _to_sky_time(t)
    obs   = eph["earth"] + observer.skyfield_location()

    stars = Star(ra_hours=ra_arr, dec_degrees=dec_arr)
    alt_a, az_a, _ = obs.at(t_sky).observe(stars).apparent().altaz("standard")
    alts = alt_a.degrees
    azs  = az_a.degrees

    result = []
    for sl, opacity in slices:
        verts_altaz = list(zip(alts[sl], azs[sl]))
        result.append((verts_altaz, opacity))

    return result
