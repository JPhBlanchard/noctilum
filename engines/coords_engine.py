"""
Coordonnées complètes pour chaque corps du système solaire :
  - Topocentriques horizontales  (Alt, Az)
  - Géocentriques équatoriales   (RA, Dec)
  - Géocentriques écliptiques    (Lon, Lat)
  - Distances et grandeurs dérivées
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from skyfield.framelib import ecliptic_frame  # écliptique de date (correspond aux éphémérides classiques)

from engines.astro_engine import (
    Observer, _BODIES, _get_eph, _get_ts, _to_sky_time,
    _compute_magnitude, _angular_diameter_arcsec, _illumination_pct,
    _elongation_deg, _RADII_KM,
)

_AU_KM = 149_597_870.7

_ICONS = {
    "Soleil": "☀", "Lune": "🌙",
}


# ---------------------------------------------------------------------------
# Formateurs
# ---------------------------------------------------------------------------

def _dms(deg: float, signed: bool = True) -> str:
    """Degrés → D° M' S.ss" (signé si signed=True)."""
    sign = "-" if deg < 0 and signed else ("+" if deg >= 0 and signed else "")
    d = abs(deg)
    d_int = int(d)
    m_frac = (d - d_int) * 60.0
    m_int = int(m_frac)
    s = (m_frac - m_int) * 60.0
    return f"{sign}{d_int}° {m_int:02d}' {s:05.2f}\""


def _hms(hours: float) -> str:
    """Heures décimales → Hh MMm SS.sss."""
    h = hours % 24.0
    h_int = int(h)
    m_frac = (h - h_int) * 60.0
    m_int = int(m_frac)
    s = (m_frac - m_int) * 60.0
    return f"{h_int}h{m_int:02d}m{s:06.3f}s"


def _arcms(arcsec: float) -> str:
    """Secondes d'arc → M' S.ss" ou juste SS.ss" si < 60"."""
    if arcsec >= 60.0:
        m = int(arcsec // 60)
        s = arcsec - m * 60
        return f"{m}' {s:05.2f}\""
    return f"{arcsec:.2f}\""


# ---------------------------------------------------------------------------
# Dataclass résultat
# ---------------------------------------------------------------------------

@dataclass
class BodyCoords:
    name: str
    icon: str
    # Horizontales topocentriques
    alt_deg: float
    az_deg: float
    # Équatoriales géocentriques
    ra_hours: float
    dec_deg: float
    # Écliptiques géocentriques (J2000)
    ecl_lon_deg: float
    ecl_lat_deg: float
    # Distances
    dist_earth_au: float
    dist_earth_km: float
    dist_sun_au: Optional[float]
    # Dérivées
    elongation_deg: Optional[float]
    ang_diam_arcsec: Optional[float]
    illumination_pct: Optional[float]
    magnitude: Optional[float]


# ---------------------------------------------------------------------------
# Calcul principal
# ---------------------------------------------------------------------------

def get_all_coordinates(observer: Observer, t: datetime) -> list[BodyCoords]:
    eph = _get_eph()
    ts = _get_ts()
    t_sky = _to_sky_time(t)
    earth = eph["earth"]
    location = observer.skyfield_location()
    earth_obs = earth + location

    results: list[BodyCoords] = []

    for name, body_key in _BODIES.items():
        body = eph[body_key]

        # ── Topocentrique ──────────────────────────────────────────
        topo_app = earth_obs.at(t_sky).observe(body).apparent()
        alt, az, _ = topo_app.altaz("standard")

        # ── Géocentrique apparent ──────────────────────────────────
        geo_app = earth.at(t_sky).observe(body).apparent()

        # Équatoriales J2000
        ra, dec, dist = geo_app.radec()

        # Écliptiques J2000
        ecl_lat, ecl_lon, _ = geo_app.frame_latlon(ecliptic_frame)

        dist_au = dist.au
        dist_km = dist_au * _AU_KM

        # Distance au Soleil (héliocentric) — None pour le Soleil lui-même
        if body_key == "sun":
            dist_sun = None
        else:
            try:
                dist_sun = body.at(t_sky).observe(eph["sun"]).distance().au
            except Exception:
                dist_sun = None

        # Grandeurs physiques
        mag = _compute_magnitude(name, body_key, observer, t_sky)
        elong = _elongation_deg(body_key, observer, t_sky)
        ang_diam = _angular_diameter_arcsec(name, dist_au)
        illum = _illumination_pct(name, body_key, observer, t_sky)

        results.append(BodyCoords(
            name=name,
            icon=_ICONS.get(name, "⬤"),
            alt_deg=round(alt.degrees, 3),
            az_deg=round(az.degrees, 3),
            ra_hours=ra.hours,
            dec_deg=dec.degrees,
            ecl_lon_deg=ecl_lon.degrees,
            ecl_lat_deg=ecl_lat.degrees,
            dist_earth_au=dist_au,
            dist_earth_km=dist_km,
            dist_sun_au=dist_sun,
            elongation_deg=round(elong, 1) if elong is not None else None,
            ang_diam_arcsec=round(ang_diam, 2) if ang_diam is not None else None,
            illumination_pct=illum,
            magnitude=round(mag, 2) if mag is not None and not math.isnan(mag) else None,
        ))

    return results


# ---------------------------------------------------------------------------
# Formateurs pour l'affichage tableau
# ---------------------------------------------------------------------------

def coords_to_rows(coords: list[BodyCoords]) -> list[dict]:
    rows = []
    for c in coords:
        rows.append({
            "Corps":           c.icon + " " + c.name,
            "Lon. éclip. (λ)": _dms(c.ecl_lon_deg, signed=False),
            "Lat. éclip. (β)": _dms(c.ecl_lat_deg, signed=True),
            "Hauteur":         f"{c.alt_deg:+.2f}°",
            "Azimut":          f"{c.az_deg:.2f}°",
            "Asc. droite (α)": _hms(c.ra_hours),
            "Déclinaison (δ)": _dms(c.dec_deg, signed=True),
            "Dist. Terre":     f"{c.dist_earth_au:.7f} UA",
            "Dist. Soleil":    f"{c.dist_sun_au:.5f} UA" if c.dist_sun_au else "—",
            "Élongation":      f"{c.elongation_deg:.1f}°" if c.elongation_deg is not None else "—",
            "Diam. app.":      _arcms(c.ang_diam_arcsec) if c.ang_diam_arcsec else "—",
            "Phase (%)":       f"{c.illumination_pct:.1f}" if c.illumination_pct is not None else "—",
            "Mag.":            f"{c.magnitude:.2f}" if c.magnitude is not None else "—",
        })
    return rows
