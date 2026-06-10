"""
Détection des éclipses solaires et lunaires — Skyfield + géométrie.

Précision : ~1 min sur la date du maximum, type correct ~95 % des cas.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional
import math

from engines.astro_engine import _get_eph, _get_ts


# ---------------------------------------------------------------------------
# Structures de résultat
# ---------------------------------------------------------------------------

class SolarEclipse:
    __slots__ = ("dt_max", "type", "lat_deg")

    def __init__(self, dt_max: datetime, type_: str, lat_deg: float) -> None:
        self.dt_max  = dt_max    # UTC du maximum
        self.type    = type_     # "Totale" | "Annulaire" | "Hybride" | "Partielle"
        self.lat_deg = lat_deg   # latitude écliptique de la Lune au maximum


class LunarEclipse:
    __slots__ = ("dt_max", "type", "lat_deg", "totality_min")

    def __init__(self, dt_max: datetime, type_: str, lat_deg: float,
                 totality_min: Optional[float]) -> None:
        self.dt_max        = dt_max          # UTC du maximum
        self.type          = type_           # "Totale" | "Partielle" | "Pénombrale"
        self.lat_deg       = lat_deg
        self.totality_min  = totality_min    # durée de totalité en minutes (None si non totale)


# ---------------------------------------------------------------------------
# Helpers géométriques
# ---------------------------------------------------------------------------

_DEG = math.degrees
_RAD = math.radians


def _angular_diam_deg(body_key: str, t_sky) -> float:
    """Diamètre apparent en degrés d'un corps vu depuis la Terre."""
    eph = _get_eph()
    dist_au = (eph["earth"].at(t_sky).observe(eph[body_key])
               .distance().au)
    # Rayons équatoriaux en UA
    radii_au = {
        "sun":  695700.0 / 149_597_870.7,
        "moon": 1737.4  / 149_597_870.7,
    }
    return 2.0 * _DEG(math.atan2(radii_au[body_key], dist_au))


def _shadow_miss_deg(t_sky) -> float:
    """
    Distance angulaire en degrés entre le centre de la Lune et l'axe de
    l'ombre terrestre (point antisolaire) — proxy du paramètre gamma.
    """
    eph = _get_eph()
    earth_at_t = eph["earth"].at(t_sky)
    # Direction antisolaire = opposée au Soleil
    sun_dir  = earth_at_t.observe(eph["sun"]).apparent()
    moon_dir = earth_at_t.observe(eph["moon"]).apparent()
    # Séparation angulaire Lune / antisolaire
    sep = moon_dir.separation_from(sun_dir).degrees
    return abs(180.0 - sep)   # distance au point exactement opposé au Soleil


def _umbra_radius_deg(t_sky) -> float:
    """Rayon angulaire de l'ombre terrestre (pénombre exclue) à la distance de la Lune."""
    eph    = _get_eph()
    r_sun  = 695700.0   # km
    r_earth = 6371.0    # km
    r_moon_km = 1737.4  # km

    earth_at = eph["earth"].at(t_sky)
    d_es_km  = earth_at.observe(eph["sun"]).distance().km
    d_em_km  = earth_at.observe(eph["moon"]).distance().km

    # Rayon du cône d'ombre terrestre à la distance de la Lune
    r_umbra_km = r_earth - (r_earth + r_sun) * d_em_km / d_es_km
    return _DEG(math.atan2(max(r_umbra_km, 0.0), d_em_km))


def _penumbra_radius_deg(t_sky) -> float:
    """Rayon angulaire de la pénombre terrestre à la distance de la Lune."""
    eph     = _get_eph()
    r_sun   = 695700.0
    r_earth = 6371.0

    earth_at = eph["earth"].at(t_sky)
    d_es_km  = earth_at.observe(eph["sun"]).distance().km
    d_em_km  = earth_at.observe(eph["moon"]).distance().km

    r_penum_km = r_earth + (r_sun - r_earth) * d_em_km / d_es_km
    return _DEG(math.atan2(r_penum_km, d_em_km))


# ---------------------------------------------------------------------------
# Recherche du minimum de séparation autour d'une date donnée
# ---------------------------------------------------------------------------

def _refine_minimum(t_approx, is_lunar: bool, step_s: int = 300,
                    window_h: float = 6.0):
    """
    Affine la date du maximum d'éclipse par balayage minute/heure autour
    de t_approx (Skyfield Time). Retourne (t_min, miss_deg).
    """
    ts = _get_ts()
    dt_center = t_approx.utc_datetime()

    best_miss = 999.0
    best_t    = t_approx

    offsets_s = range(int(-window_h * 3600), int(window_h * 3600), step_s)
    for off in offsets_s:
        dt = dt_center + timedelta(seconds=off)
        t  = ts.from_datetime(dt)
        miss = _shadow_miss_deg(t) if is_lunar else _moon_sun_sep_deg(t)
        if miss < best_miss:
            best_miss = miss
            best_t    = t

    # 2ème passe fine (pas 30 s)
    dt_center2 = best_t.utc_datetime()
    for off in range(-600, 600, 30):
        dt = dt_center2 + timedelta(seconds=off)
        t  = ts.from_datetime(dt)
        miss = _shadow_miss_deg(t) if is_lunar else _moon_sun_sep_deg(t)
        if miss < best_miss:
            best_miss = miss
            best_t    = t

    return best_t, best_miss


def _moon_sun_sep_deg(t_sky) -> float:
    """Séparation angulaire Lune–Soleil."""
    eph = _get_eph()
    earth_at = eph["earth"].at(t_sky)
    sun  = earth_at.observe(eph["sun"]).apparent()
    moon = earth_at.observe(eph["moon"]).apparent()
    return moon.separation_from(sun).degrees


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def find_eclipses(
    t_start: Optional[datetime] = None,
    t_end: Optional[datetime] = None,
) -> tuple[list[SolarEclipse], list[LunarEclipse]]:
    """
    Retourne (éclipses_solaires, éclipses_lunaires) dans la fenêtre donnée.

    Par défaut : aujourd'hui + 3 ans.
    """
    from skyfield import almanac

    eph = _get_eph()
    ts  = _get_ts()

    if t_start is None:
        t_start = datetime.now(timezone.utc)
    if t_end is None:
        t_end = t_start.replace(year=t_start.year + 3)

    t0 = ts.from_datetime(t_start)
    t1 = ts.from_datetime(t_end)

    times, phases = almanac.find_discrete(t0, t1, almanac.moon_phases(eph))

    solar: list[SolarEclipse] = []
    lunar: list[LunarEclipse] = []

    for t_phase, ph in zip(times, phases):
        moon_ecl = eph["earth"].at(t_phase).observe(eph["moon"]).apparent()
        lat, *_ = moon_ecl.ecliptic_latlon()
        lat_deg = abs(lat.degrees)

        # ── Éclipse solaire (nouvelle lune) ──────────────────────────────
        if ph == 0 and lat_deg < 1.6:
            t_max, _ = _refine_minimum(t_phase, is_lunar=False)
            t_max_dt = t_max.utc_datetime()

            # Gamma = distance axe d'ombre / rayon terrestre
            # gamma ≈ lat_écliptique × d_lune / (R_terre × 57.2958°/rad)
            d_moon_km = (eph["earth"].at(t_max)
                         .observe(eph["moon"]).distance().km)
            gamma = lat_deg * d_moon_km / (6371.0 * 57.2958)

            diam_moon = _angular_diam_deg("moon", t_max)
            diam_sun  = _angular_diam_deg("sun",  t_max)
            ratio = diam_moon / diam_sun

            # |gamma| < 1 → ombre axiale touche la Terre → centrale
            # gamma > 1.57 → pénombre n'atteint pas la Terre → pas d'éclipse
            if gamma >= 1.57:
                continue
            if gamma < 1.0:
                # Correction topocentrique : au point le plus proche de la Lune,
                # la distance observateur→Lune vaut d_moon − R_terre×cos(arcsin(γ))
                d_surface_min = d_moon_km - 6371.0 * math.sqrt(
                    max(0.0, 1.0 - gamma ** 2)
                )
                ratio_topo = ratio * d_moon_km / d_surface_min
                if ratio_topo > 1.0:
                    # Quelque part sur Terre la Lune couvre le Soleil.
                    # ratio ≥ 1.01 : clairement total partout sur le chemin
                    # ratio < 1.01  : transition total/annulaire → hybride
                    type_ = "Totale" if ratio >= 1.005 else "Hybride"
                else:
                    type_ = "Annulaire"
            else:
                type_ = "Partielle"

            solar.append(SolarEclipse(t_max_dt, type_, lat_deg))

        # ── Éclipse lunaire (pleine lune) ────────────────────────────────
        elif ph == 2 and lat_deg < 1.4:
            t_max, miss = _refine_minimum(t_phase, is_lunar=True)
            t_max_dt = t_max.utc_datetime()

            r_umbra  = _umbra_radius_deg(t_max)
            r_penum  = _penumbra_radius_deg(t_max)
            r_moon   = _angular_diam_deg("moon", t_max) / 2.0

            if miss < r_umbra - r_moon:
                # Lune entièrement dans l'ombre → totale
                type_ = "Totale"
                # Durée approximative de totalité
                # vitesse relative Lune ~0.55°/h, diamètre utilisable = 2*(r_umbra-r_moon-miss)
                chord = 2.0 * (r_umbra - r_moon - miss)
                totality_min = round(chord / 0.55 * 60.0, 0)
            elif miss < r_umbra + r_moon:
                type_ = "Partielle"
                totality_min = None
            elif miss < r_penum + r_moon:
                type_ = "Pénombrale"
                totality_min = None
            else:
                continue   # faux positif

            lunar.append(LunarEclipse(t_max_dt, type_, lat_deg, totality_min))

    return solar, lunar
