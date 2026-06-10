"""
Moteur temps — Jour Julien, ΔT, Équation du temps, GMST, fuseau horaire local.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Jour Julien
# ---------------------------------------------------------------------------

def julian_day(dt: datetime) -> float:
    """Jour Julien (JD) pour un datetime UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    y, m, d = dt.year, dt.month, dt.day
    frac = (dt.hour + dt.minute / 60.0 + dt.second / 3600.0
            + dt.microsecond / 3_600_000_000.0) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    A = int(y / 100)
    B = 2 - A + int(A / 4)
    jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + B - 1524.5
    return jd + frac


def julian_day_tt(dt_utc: datetime, delta_t_s: float) -> float:
    """JD en Temps Terrestre (TT = UTC + ΔT)."""
    return julian_day(dt_utc) + delta_t_s / 86400.0


# ---------------------------------------------------------------------------
# ΔT  (TT − UTC, en secondes)
# Approximations polynomiales de Espenak & Meeus (Five Millenium Canon)
# ---------------------------------------------------------------------------

def delta_t(year_frac: float) -> float:
    """ΔT en secondes pour une année décimale (ex. 2026.43)."""
    y = year_frac

    if y < -500:
        u = (y - 1820) / 100
        return -20 + 32 * u * u

    if y < 500:
        u = y / 100
        return (10583.6 - 1014.41 * u + 33.78311 * u**2
                - 5.952053 * u**3 - 0.1798452 * u**4
                + 0.022174192 * u**5 + 0.0090316521 * u**6)

    if y < 1600:
        u = (y - 1000) / 100
        return (1574.2 - 556.01 * u + 71.23472 * u**2
                + 0.319781 * u**3 - 0.8503463 * u**4
                - 0.005050998 * u**5 + 0.0083572073 * u**6)

    if y < 1700:
        t = y - 1600
        return 120 - 0.9808 * t - 0.01532 * t**2 + t**3 / 7129

    if y < 1800:
        t = y - 1700
        return (8.83 + 0.1603 * t - 0.0059285 * t**2
                + 0.00013336 * t**3 - t**4 / 1174000)

    if y < 1860:
        t = y - 1800
        return (13.72 - 0.332447 * t + 0.0068612 * t**2
                + 0.0041116 * t**3 - 0.00037436 * t**4
                + 0.0000121272 * t**5 - 0.0000001699 * t**6
                + 0.000000000875 * t**7)

    if y < 1900:
        t = y - 1860
        return (7.62 + 0.5737 * t - 0.251754 * t**2
                + 0.01680668 * t**3 - 0.0004473624 * t**4
                + t**5 / 233174)

    if y < 1920:
        t = y - 1900
        return (- 2.79 + 1.494119 * t - 0.0598939 * t**2
                + 0.0061966 * t**3 - 0.000197 * t**4)

    if y < 1941:
        t = y - 1920
        return 21.20 + 0.84493 * t - 0.076100 * t**2 + 0.0020936 * t**3

    if y < 1961:
        t = y - 1950
        return 29.07 + 0.407 * t - t**2 / 233 + t**3 / 2547

    if y < 1986:
        t = y - 1975
        return 45.45 + 1.067 * t - t**2 / 260 - t**3 / 718

    if y < 2005:
        t = y - 2000
        return (63.86 + 0.3345 * t - 0.060374 * t**2
                + 0.0017275 * t**3 + 0.000651814 * t**4
                + 0.00002373599 * t**5)

    if y < 2050:
        t = y - 2000
        return 62.92 + 0.32217 * t + 0.005589 * t**2

    if y < 2150:
        return (-20 + 32 * ((y - 1820) / 100) ** 2
                - 0.5628 * (2150 - y))

    u = (y - 1820) / 100
    return -20 + 32 * u * u


def delta_t_for_datetime(dt: datetime) -> float:
    """ΔT en secondes pour un datetime UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    year_frac = dt.year + (dt.timetuple().tm_yday - 1) / 365.25
    return delta_t(year_frac)


# ---------------------------------------------------------------------------
# GMST (Greenwich Mean Sidereal Time) via formule analytique
# ---------------------------------------------------------------------------

def gmst_hours(dt_utc: datetime) -> float:
    """GMST en heures décimales [0, 24[."""
    jd = julian_day(dt_utc)
    T = (jd - 2451545.0) / 36525.0
    # IAU 1982, en secondes de temps
    gmst_s = (24110.54841
              + 8640184.812866 * T
              + 0.093104 * T * T
              - 6.2e-6 * T * T * T)
    # Ajouter la rotation terrestre depuis le minuit UT
    jd0 = math.floor(jd - 0.5) + 0.5  # midi du jour julien précédent
    ut = (jd - jd0) * 86400.0          # secondes écoulées depuis minuit UT
    gmst_s += ut * 1.00273790935        # facteur sidéral
    gmst_h = (gmst_s / 3600.0) % 24.0
    return gmst_h


# ---------------------------------------------------------------------------
# Équation du temps
# ---------------------------------------------------------------------------

def equation_of_time_minutes(dt_utc: datetime) -> float:
    """
    Équation du temps en minutes (EoT = temps solaire moyen − temps solaire apparent).
    Valeur positive → le Soleil transit avant 12h00 solaire moyen.
    Précision ≈ 0.5 min (formule analytique Spencer 1971 + correction d'équinoxes).
    """
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    jd = julian_day(dt_utc)
    # Temps julien depuis J2000
    T = (jd - 2451545.0) / 36525.0
    # Longitude géométrique moyenne du Soleil
    L0 = (280.46646 + 36000.76983 * T + 0.0003032 * T * T) % 360.0
    # Anomalie moyenne du Soleil
    M = math.radians((357.52911 + 35999.05029 * T - 0.0001537 * T * T) % 360.0)
    # Excentricité de l'orbite terrestre
    e = 0.016708634 - 0.000042037 * T - 0.0000001267 * T * T
    # Équation du centre
    C = ((1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(M)
         + (0.019993 - 0.000101 * T) * math.sin(2 * M)
         + 0.000289 * math.sin(3 * M))
    # Longitude vraie du Soleil
    sun_lon = L0 + C
    # Aberration
    omega = math.radians(125.04 - 1934.136 * T)
    lam = math.radians(sun_lon - 0.00569 - 0.00478 * math.sin(omega))
    # Obliquité corrigée
    eps0 = (23 + 26 / 60.0 + 21.448 / 3600.0
            - (46.8150 / 3600.0) * T
            - (0.00059 / 3600.0) * T * T
            + (0.001813 / 3600.0) * T * T * T)
    eps = math.radians(eps0 + 0.00256 * math.cos(omega))
    # y = tan²(ε/2)
    y = math.tan(eps / 2) ** 2
    L0_r = math.radians(L0)
    M_r = M
    e2 = e
    # Formule Astronomical Algorithms (Meeus), ch.27
    eot_rad = (y * math.sin(2 * L0_r)
               - 2 * e2 * math.sin(M_r)
               + 4 * e2 * y * math.sin(M_r) * math.cos(2 * L0_r)
               - 0.5 * y * y * math.sin(4 * L0_r)
               - 1.25 * e2 * e2 * math.sin(2 * M_r))
    return math.degrees(eot_rad) * 4.0  # 1° = 4 minutes


# ---------------------------------------------------------------------------
# Courbe annuelle de l'équation du temps
# ---------------------------------------------------------------------------

def equation_of_time_curve(year: int) -> tuple[list[str], list[float]]:
    """
    Retourne (dates_iso, eot_minutes) pour toute l'année, un point par jour.
    """
    dates = []
    eots = []
    dt = datetime(year, 1, 1, 12, 0, tzinfo=timezone.utc)
    while dt.year == year:
        dates.append(dt.strftime("%Y-%m-%d"))
        eots.append(round(equation_of_time_minutes(dt), 4))
        dt += timedelta(days=1)
    return dates, eots


# ---------------------------------------------------------------------------
# Fuseau horaire local (basé sur les coordonnées géographiques)
# ---------------------------------------------------------------------------

def get_timezone_name(lat: float, lon: float) -> str:
    """Retourne le nom IANA du fuseau horaire pour des coordonnées."""
    try:
        from timezonefinder import TimezoneFinder
        tf = TimezoneFinder()
        tz = tf.timezone_at(lat=lat, lng=lon)
        return tz or "UTC"
    except Exception:
        # Fallback : offset UTC brut basé sur la longitude
        offset_h = round(lon / 15.0)
        offset_h = max(-12, min(14, offset_h))
        if offset_h == 0:
            return "UTC"
        sign = "+" if offset_h >= 0 else "-"
        return f"Etc/GMT{sign}{abs(offset_h)}"


def local_datetime(dt_utc: datetime, tz_name: str) -> datetime:
    """Convertit un datetime UTC en heure locale."""
    from zoneinfo import ZoneInfo
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(ZoneInfo(tz_name))


def utc_offset_str(dt_local: datetime) -> str:
    """Retourne la chaîne d'offset UTC type '+02:00'."""
    off = dt_local.utcoffset()
    if off is None:
        return "+00:00"
    total = int(off.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    h, rem = divmod(total, 3600)
    m = rem // 60
    return f"{sign}{h:02d}:{m:02d}"


# ---------------------------------------------------------------------------
# Dataclass résumé
# ---------------------------------------------------------------------------

@dataclass
class TimeInfo:
    dt_utc: datetime
    dt_local: datetime
    tz_name: str
    utc_offset: str
    jd_utc: float
    jd_tt: float
    delta_t_s: float
    gmst_h: float
    last_h: float   # Local Apparent Sidereal Time (= GMST + lon/15)
    eot_min: float  # Équation du temps en minutes


def compute_time_info(dt_utc: datetime, lat: float, lon: float) -> TimeInfo:
    """Calcule toutes les grandeurs temporelles pour un instant et un lieu."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)

    tz_name = get_timezone_name(lat, lon)
    dt_local = local_datetime(dt_utc, tz_name)
    off_str = utc_offset_str(dt_local)

    dts = delta_t_for_datetime(dt_utc)
    jd = julian_day(dt_utc)
    jd_tt = julian_day_tt(dt_utc, dts)
    gmst = gmst_hours(dt_utc)
    last = (gmst + lon / 15.0) % 24.0
    eot = equation_of_time_minutes(dt_utc)

    return TimeInfo(
        dt_utc=dt_utc,
        dt_local=dt_local,
        tz_name=tz_name,
        utc_offset=off_str,
        jd_utc=jd,
        jd_tt=jd_tt,
        delta_t_s=dts,
        gmst_h=gmst,
        last_h=last,
        eot_min=eot,
    )
