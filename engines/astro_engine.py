"""
Moteur astronomique principal — Skyfield / JPL DE440s.

Point d'entrée public :
  Observer          – lieu d'observation (défaut : Roscoff)
  get_altaz()       – altitude / azimut d'un corps
  get_planets_data()– tableau complet des planètes + Soleil + Lune
  local_sidereal_time() – TSL en heures décimales
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from skyfield import almanac as sky_almanac
from skyfield.api import Loader, load_file, wgs84

# ---------------------------------------------------------------------------
# Chargement lazy des ressources Skyfield
# ---------------------------------------------------------------------------

_DATA_DIR     = Path(__file__).parent.parent / "data"
_BSP_FILENAME = "de440s.bsp"
_BSP_PATH     = _DATA_DIR / _BSP_FILENAME

_loader: Optional[Loader] = None
_eph = None
_ts  = None


def _get_loader() -> Loader:
    global _loader
    if _loader is None:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _loader = Loader(str(_DATA_DIR))
    return _loader


def _get_eph():
    """Charge de440s.bsp depuis data/ via load_file (retourne un SpiceKernel)."""
    global _eph
    if _eph is None:
        if not _BSP_PATH.exists():
            raise FileNotFoundError(
                f"Fichier introuvable : {_BSP_PATH}\n"
                "Télécharge de440s.bsp et place-le dans data/."
            )
        _eph = load_file(str(_BSP_PATH))
    return _eph


def _get_ts():
    global _ts
    if _ts is None:
        _ts = _get_loader().timescale(builtin=True)
    return _ts


# ---------------------------------------------------------------------------
# Observer
# ---------------------------------------------------------------------------

class Observer:
    """Point d'observation géographique."""

    def __init__(
        self,
        lat: float = 48.7262,
        lon: float = -3.9860,
        elevation: float = 10.0,
        name: str = "Roscoff",
    ) -> None:
        if not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Latitude invalide : {lat}")
        if not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Longitude invalide : {lon}")
        self.lat = lat
        self.lon = lon
        self.elevation = elevation  # mètres
        self.name = name

    def skyfield_location(self):
        return wgs84.latlon(self.lat, self.lon, elevation_m=self.elevation)

    def __repr__(self) -> str:
        return f"Observer({self.name!r}, lat={self.lat}, lon={self.lon})"


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _to_sky_time(t: Optional[datetime]):
    """Convertit un datetime Python (UTC) en Time Skyfield ; None → maintenant."""
    ts = _get_ts()
    if t is None:
        t = datetime.now(timezone.utc)
    elif t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return ts.from_datetime(t)


# Corps suivis : nom affiché → clé de121.bsp
_BODIES: dict[str, str] = {
    "Mercure": "mercury",
    "Vénus": "venus",
    "Mars": "mars barycenter",
    "Jupiter": "jupiter barycenter",
    "Saturne": "saturn barycenter",
    "Uranus": "uranus barycenter",
    "Neptune": "neptune barycenter",
    "Soleil": "sun",
    "Lune": "moon",
}

# Magnitudes visuelles de repli (moyennes)
_MAG_FALLBACK: dict[str, float] = {
    "Soleil": -26.74,
    "Lune": -12.60,
    "Mercure": 0.23,
    "Vénus": -4.14,
    "Mars": 0.71,
    "Jupiter": -2.20,
    "Saturne": 0.46,
    "Uranus": 5.68,
    "Neptune": 7.78,
}

# Corps pour lesquels planetary_magnitude() est disponible (planètes)
_PLANETS_FOR_MAG = {
    "Mercure", "Vénus", "Mars", "Jupiter", "Saturne", "Uranus", "Neptune"
}


def _apparent_position(body_key: str, observer: Observer, t_sky):
    eph = _get_eph()
    location = observer.skyfield_location()
    astrometric = (eph["earth"] + location).at(t_sky).observe(eph[body_key])
    return astrometric.apparent()


def _compute_magnitude(name: str, body_key: str, observer: Observer, t_sky) -> float:
    if name in _PLANETS_FOR_MAG:
        try:
            from skyfield.magnitudelib import planetary_magnitude
            app = _apparent_position(body_key, observer, t_sky)
            return float(planetary_magnitude(app))
        except Exception:
            pass
    return _MAG_FALLBACK.get(name, float("nan"))


def _fmt_utc(t_sky) -> str:
    return t_sky.utc_datetime().strftime("%H:%M")


def _rise_set_times(body_key: str, observer: Observer, t_sky) -> tuple[str, str]:
    """Lever et coucher UTC (HH:MM) pour le jour courant ; '—' si indisponible."""
    eph = _get_eph()
    ts = _get_ts()

    dt = t_sky.utc_datetime()
    midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    t0 = ts.from_datetime(midnight)
    t1 = ts.from_datetime(midnight + timedelta(days=1))

    location = observer.skyfield_location()

    try:
        f = sky_almanac.risings_and_settings(eph, eph[body_key], location)
        times, events = sky_almanac.find_discrete(t0, t1, f)
    except Exception:
        return "—", "—"

    rise_str = "—"
    set_str = "—"
    for ti, ev in zip(times, events):
        if ev == 1 and rise_str == "—":   # 1 = lever
            rise_str = _fmt_utc(ti)
        elif ev == 0 and set_str == "—":  # 0 = coucher
            set_str = _fmt_utc(ti)

    return rise_str, set_str


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def get_altaz(
    body_key: str,
    observer: Observer,
    t: Optional[datetime] = None,
) -> tuple[float, float]:
    """
    Retourne (altitude_deg, azimuth_deg) pour un corps Skyfield.

    La réfraction atmosphérique standard est appliquée via apparent().altaz('standard').
    Les altitudes négatives (sous l'horizon) sont retournées telles quelles.
    """
    t_sky = _to_sky_time(t)
    app = _apparent_position(body_key, observer, t_sky)
    alt, az, _ = app.altaz("standard")
    return alt.degrees, az.degrees


def get_planets_data(
    observer: Optional[Observer] = None,
    t: Optional[datetime] = None,
) -> list[dict]:
    """
    Retourne une liste de dicts pour chaque corps suivi :

      name          str    – nom français
      alt           float  – altitude (degrés, réfraction incluse)
      az            float  – azimut (degrés, N=0°, E=90°)
      magnitude     float  – magnitude visuelle (None si inconnue)
      rise          str    – heure UTC de lever HH:MM (ou '—')
      set           str    – heure UTC de coucher HH:MM (ou '—')
      above_horizon bool   – True si alt ≥ 0°
    """
    if observer is None:
        observer = Observer()

    eph = _get_eph()
    t_sky = _to_sky_time(t)
    location = observer.skyfield_location()
    earth = eph["earth"]

    results: list[dict] = []
    for name, body_key in _BODIES.items():
        astrometric = (earth + location).at(t_sky).observe(eph[body_key])
        apparent = astrometric.apparent()
        alt, az, _ = apparent.altaz("standard")

        alt_deg = alt.degrees
        az_deg = az.degrees
        above = alt_deg >= 0.0

        mag = _compute_magnitude(name, body_key, observer, t_sky)
        rise_str, set_str = _rise_set_times(body_key, observer, t_sky)

        results.append(
            {
                "name": name,
                "alt": round(alt_deg, 3),
                "az": round(az_deg, 3),
                "magnitude": round(mag, 2) if not math.isnan(mag) else None,
                "rise": rise_str,
                "set": set_str,
                "above_horizon": above,
            }
        )

    return results


def local_sidereal_time(
    observer: Optional[Observer] = None,
    t: Optional[datetime] = None,
) -> float:
    """
    Retourne le Temps Sidéral Local Apparent (TSLA) en heures décimales [0, 24[.

    TSL = TSMG (Greenwich Apparent Sidereal Time) + λ/15
    """
    if observer is None:
        observer = Observer()
    t_sky = _to_sky_time(t)
    gast = t_sky.gast                   # heures
    last = (gast + observer.lon / 15.0) % 24.0
    return last
