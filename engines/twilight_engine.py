"""
Moteur crépuscules — lever/coucher + aube/crépuscule civil/nautique/astronomique.
Retourne des instants UTC avec azimut et altitude pour le Soleil et la Lune.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from skyfield import almanac as sky_almanac
from skyfield.api import wgs84

from engines.astro_engine import Observer, _get_eph, _get_ts, _to_sky_time


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class SkyEvent:
    label: str        # nom de l'événement
    dt_utc: Optional[datetime]   # None si l'événement n'a pas lieu (soleil de minuit, etc.)
    az: Optional[float]          # azimut en degrés au moment de l'événement
    alt: Optional[float]         # altitude en degrés au moment de l'événement


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _altaz_at(body_key: str, observer: Observer, dt: datetime) -> tuple[float, float]:
    """Retourne (alt_deg, az_deg) pour un corps à un instant donné."""
    eph = _get_eph()
    ts = _get_ts()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    t_sky = ts.from_datetime(dt)
    location = observer.skyfield_location()
    app = (eph["earth"] + location).at(t_sky).observe(eph[body_key]).apparent()
    alt, az, _ = app.altaz("standard")
    return round(alt.degrees, 2), round(az.degrees, 2)


def _transit_altaz(body_key: str, observer: Observer, t_sky) -> tuple[Optional[datetime], float, float]:
    """
    Passage au méridien : heure UTC, azimut et altitude.
    Retourne (None, 0, 0) si introuvable.
    """
    try:
        eph = _get_eph()
        ts = _get_ts()
        location = observer.skyfield_location()

        app = (eph["earth"] + location).at(t_sky).observe(eph[body_key]).apparent()
        ra, _, _ = app.radec()
        gast = t_sky.gast
        last = (gast + observer.lon / 15.0) % 24.0
        ha = (last - ra.hours) % 24.0
        delta_sid = (24.0 - ha) if ha > 12.0 else -ha
        dt_transit = t_sky.utc_datetime() + timedelta(seconds=delta_sid * 3590.17)
        dt_transit = dt_transit.replace(tzinfo=timezone.utc)

        alt, az = _altaz_at(body_key, observer, dt_transit)
        return dt_transit, az, alt
    except Exception:
        return None, 0.0, 0.0


# ---------------------------------------------------------------------------
# Crépuscules solaires (+ lever/transit/coucher)
# ---------------------------------------------------------------------------

def get_solar_events(observer: Observer, t: datetime) -> list[SkyEvent]:
    """
    Retourne les 9 événements solaires du jour (UTC) :
      aube astro · aube nautique · aube civile · lever ·
      transit · coucher · crép. civil · crép. nautique · crép. astro.
    """
    eph = _get_eph()
    ts = _get_ts()
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)

    dt_utc = t.astimezone(timezone.utc)
    midnight = dt_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    t0 = ts.from_datetime(midnight)
    t1 = ts.from_datetime(midnight + timedelta(days=1))
    location = observer.skyfield_location()

    # Transition des phases de la journée
    # dark_twilight_day retourne 0-4 : 0=nuit, 1=astro, 2=nautique, 3=civil, 4=jour
    f_twilight = sky_almanac.dark_twilight_day(eph, location)
    times, events = sky_almanac.find_discrete(t0, t1, f_twilight)

    # Index des transitions par valeur de transition (montant/descendant)
    transitions: dict[tuple[int, int], datetime] = {}
    prev = None
    for ti, ev in zip(times, events):
        if prev is not None:
            transitions[(prev, int(ev))] = ti.utc_datetime().replace(tzinfo=timezone.utc)
        prev = int(ev)

    def _ev(label: str, key: tuple[int, int]) -> SkyEvent:
        dt = transitions.get(key)
        if dt is None:
            return SkyEvent(label, None, None, None)
        alt, az = _altaz_at("sun", observer, dt)
        return SkyEvent(label, dt, az, alt)

    # Transit solaire
    t_sky_now = _to_sky_time(t)
    dt_tr, az_tr, alt_tr = _transit_altaz("sun", observer, t_sky_now)

    return [
        _ev("Aube astronomique",  (0, 1)),
        _ev("Aube nautique",       (1, 2)),
        _ev("Aube civile",         (2, 3)),
        _ev("Lever du Soleil",     (3, 4)),
        SkyEvent("Passage au méridien", dt_tr, az_tr, alt_tr),
        _ev("Coucher du Soleil",   (4, 3)),
        _ev("Crépuscule civil",    (3, 2)),
        _ev("Crépuscule nautique", (2, 1)),
        _ev("Crépuscule astron.",  (1, 0)),
    ]


# ---------------------------------------------------------------------------
# Événements lunaires (lever/transit/coucher)
# ---------------------------------------------------------------------------

def get_lunar_events(observer: Observer, t: datetime) -> list[SkyEvent]:
    """Retourne lever, transit et coucher de la Lune pour la journée."""
    eph = _get_eph()
    ts = _get_ts()
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)

    dt_utc = t.astimezone(timezone.utc)
    midnight = dt_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    t0 = ts.from_datetime(midnight)
    t1 = ts.from_datetime(midnight + timedelta(days=1))
    location = observer.skyfield_location()

    f_moon = sky_almanac.risings_and_settings(eph, eph["moon"], location)
    times, events = sky_almanac.find_discrete(t0, t1, f_moon)

    rise_dt = set_dt = None
    for ti, ev in zip(times, events):
        dt = ti.utc_datetime().replace(tzinfo=timezone.utc)
        if ev == 1 and rise_dt is None:
            rise_dt = dt
        elif ev == 0 and set_dt is None:
            set_dt = dt

    def _ev(label: str, dt: Optional[datetime]) -> SkyEvent:
        if dt is None:
            return SkyEvent(label, None, None, None)
        alt, az = _altaz_at("moon", observer, dt)
        return SkyEvent(label, dt, az, alt)

    t_sky_now = _to_sky_time(t)
    dt_tr, az_tr, alt_tr = _transit_altaz("moon", observer, t_sky_now)

    return [
        _ev("Lever de la Lune", rise_dt),
        SkyEvent("Transit de la Lune", dt_tr, az_tr, alt_tr),
        _ev("Coucher de la Lune", set_dt),
    ]
