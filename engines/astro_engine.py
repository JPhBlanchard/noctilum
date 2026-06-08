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
    "Pluton": "pluto barycenter",
    "Soleil": "sun",
    "Lune": "moon",
}

# Rayons équatoriaux (km) pour le diamètre apparent
_RADII_KM: dict[str, float] = {
    "Mercure": 2439.7, "Vénus": 6051.8, "Mars": 3396.2,
    "Jupiter": 71492.0, "Saturne": 60268.0, "Uranus": 25559.0,
    "Neptune": 24764.0, "Pluton": 1188.3, "Soleil": 695700.0, "Lune": 1737.4,
}
_AU_KM = 149_597_870.7

# Pôle IAU de Saturne (J2000) pour le calcul de l'inclinaison des anneaux
_SAT_POLE_RA_RAD  = math.radians(40.589)
_SAT_POLE_DEC_RAD = math.radians(83.537)

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
    "Pluton": 14.3,
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


def _transit_time(body_key: str, observer: Observer, t_sky) -> str:
    """Heure UTC du passage au méridien (HH:MM) pour la journée courante."""
    try:
        eph = _get_eph()
        location = observer.skyfield_location()
        app = (eph["earth"] + location).at(t_sky).observe(eph[body_key]).apparent()
        ra, _, _ = app.radec()
        gast = t_sky.gast
        last = (gast + observer.lon / 15.0) % 24.0
        ha = (last - ra.hours) % 24.0   # angle horaire courant en heures (0-24)
        # décalage jusqu'au transit en heures sidérales
        delta_sid = (24.0 - ha) if ha > 12.0 else -ha
        # 1 heure sidérale = 3590.17 secondes solaires
        t_utc = t_sky.utc_datetime() + timedelta(seconds=delta_sid * 3590.17)
        return t_utc.strftime("%H:%M")
    except Exception:
        return "—"


def _elongation_deg(body_key: str, observer: Observer, t_sky) -> float | None:
    """Élongation en degrés (séparation angulaire au Soleil vue depuis l'observateur)."""
    if body_key == "sun":
        return None
    try:
        eph = _get_eph()
        location = observer.skyfield_location()
        earth_at_t = (eph["earth"] + location).at(t_sky)
        sun_pos = earth_at_t.observe(eph["sun"])
        body_pos = earth_at_t.observe(eph[body_key])
        return float(sun_pos.separation_from(body_pos).degrees)
    except Exception:
        return None


def _angular_diameter_arcsec(name: str, distance_au: float) -> float | None:
    """Diamètre apparent en secondes d'arc."""
    radius_km = _RADII_KM.get(name)
    if radius_km is None or distance_au <= 0:
        return None
    dist_km = distance_au * _AU_KM
    return 2.0 * math.degrees(math.atan2(radius_km, dist_km)) * 3600.0


def _illumination_pct(name: str, body_key: str, observer: Observer, t_sky) -> float | None:
    """Fraction illuminée en % (phase). None pour le Soleil."""
    if name == "Soleil":
        return None
    try:
        eph = _get_eph()
        location = observer.skyfield_location()
        if name == "Lune":
            from skyfield import almanac as _alm
            return round(float(_alm.fraction_illuminated(eph, "moon", t_sky)) * 100.0, 1)
        # Planètes : angle de phase via loi des cosinus
        earth_at_t = (eph["earth"] + location).at(t_sky)
        d_ep = earth_at_t.observe(eph[body_key]).distance().au
        d_es = earth_at_t.observe(eph["sun"]).distance().au
        d_sp = eph[body_key].at(t_sky).observe(eph["sun"]).distance().au
        denom = 2.0 * d_ep * d_sp
        if denom == 0:
            return None
        cos_phase = (d_ep**2 + d_sp**2 - d_es**2) / denom
        cos_phase = max(-1.0, min(1.0, cos_phase))
        return round((1.0 + cos_phase) / 2.0 * 100.0, 1)
    except Exception:
        return None


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
        transit_str = _transit_time(body_key, observer, t_sky)
        distance_au = round(astrometric.distance().au, 4)
        elongation  = _elongation_deg(body_key, observer, t_sky)
        ang_diam    = _angular_diameter_arcsec(name, distance_au)
        illumination = _illumination_pct(name, body_key, observer, t_sky)

        ring_B_deg = ring_P_deg = parallactic_angle_deg = None
        if name == "Saturne":
            try:
                ra_obj, dec_obj, _ = apparent.radec()
                ra_r  = math.radians(ra_obj.degrees)
                dec_r = math.radians(dec_obj.degrees)
                lst_deg = local_sidereal_time(observer, t)
                H_rad   = math.radians(lst_deg * 15.0 - ra_obj.degrees)
                lat_r   = math.radians(observer.lat)
                q = math.atan2(
                    math.sin(H_rad),
                    math.tan(lat_r) * math.cos(dec_r) - math.sin(dec_r) * math.cos(H_rad),
                )
                a0, d0 = _SAT_POLE_RA_RAD, _SAT_POLE_DEC_RAD
                B = math.asin(
                    math.sin(d0) * math.sin(dec_r)
                    + math.cos(d0) * math.cos(dec_r) * math.cos(a0 - ra_r)
                )
                P = math.atan2(
                    math.cos(d0) * math.sin(a0 - ra_r),
                    math.sin(d0) * math.cos(dec_r) - math.cos(d0) * math.sin(dec_r) * math.cos(a0 - ra_r),
                )
                ring_B_deg            = round(math.degrees(B), 2)
                ring_P_deg            = round(math.degrees(P), 1)
                parallactic_angle_deg = round(math.degrees(q), 1)
            except Exception:
                pass

        results.append(
            {
                "name":          name,
                "alt":           round(alt_deg, 3),
                "az":            round(az_deg, 3),
                "magnitude":     round(mag, 2) if not math.isnan(mag) else None,
                "rise":          rise_str,
                "set":           set_str,
                "transit":       transit_str,
                "distance_au":   distance_au,
                "elongation":    round(elongation, 1) if elongation is not None else None,
                "ang_diam_arcsec": round(ang_diam, 2) if ang_diam is not None else None,
                "illumination":  illumination,
                "above_horizon": above,
                "ring_B_deg":            ring_B_deg,
                "ring_P_deg":            ring_P_deg,
                "parallactic_angle_deg": parallactic_angle_deg,
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
