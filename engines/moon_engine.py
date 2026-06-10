"""
Phases lunaires et conjonctions planétaires — Skyfield.

API publique :
  get_moon_info(t_dt)             → dict phase/illumination/âge
  find_moon_phases(t_start, months=3) → list[MoonPhaseEvent]
  find_conjunctions(t_start, t_end)   → list[ConjunctionEvent]
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from engines.astro_engine import _get_eph, _get_ts


# ---------------------------------------------------------------------------
# Constantes de présentation
# ---------------------------------------------------------------------------

_PHASE_NAMES = ["Nouvelle Lune", "Premier Quartier", "Pleine Lune", "Dernier Quartier"]
_PHASE_ICONS = ["🌑", "🌓", "🌕", "🌗"]

# Noms des 8 phases intermédiaires (indexés par tranche de 45°)
_PHASE8_NAMES = [
    "Nouvelle Lune",
    "Croissant croissant",
    "Premier Quartier",
    "Gibbeuse croissante",
    "Pleine Lune",
    "Gibbeuse décroissante",
    "Dernier Quartier",
    "Croissant décroissant",
]
_PHASE8_ICONS = ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"]

# Corps planétaires : nom affiché → clé Skyfield
_PLANET_KEYS: dict[str, str] = {
    "Mercure": "mercury barycenter",
    "Vénus":   "venus barycenter",
    "Mars":    "mars barycenter",
    "Jupiter": "jupiter barycenter",
    "Saturne": "saturn barycenter",
    "Uranus":  "uranus barycenter",
    "Neptune": "neptune barycenter",
}

# Clé Skyfield → nom affiché
_KEY_TO_NAME: dict[str, str] = {
    "moon": "Lune",
    **{v: k for k, v in _PLANET_KEYS.items()},
}

PLANET_ICONS: dict[str, str] = {
    "Lune":    "🌙",
    "Soleil":  "☀",
    "Mercure": "☿",
    "Vénus":   "♀",
    "Mars":    "♂",
    "Jupiter": "♃",
    "Saturne": "♄",
    "Uranus":  "⛢",
    "Neptune": "♆",
}


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _elong_deg(t_sky) -> float:
    """Élongation écliptique Lune–Soleil (0–360°, croissant = 0→180)."""
    eph = _get_eph()
    earth = eph["earth"]
    _, sun_lon,  _ = earth.at(t_sky).observe(eph["sun"]).apparent().ecliptic_latlon()
    _, moon_lon, _ = earth.at(t_sky).observe(eph["moon"]).apparent().ecliptic_latlon()
    return (moon_lon.degrees - sun_lon.degrees) % 360.0


# ---------------------------------------------------------------------------
# Structures de données
# ---------------------------------------------------------------------------

@dataclass
class MoonPhaseEvent:
    dt:    datetime
    phase: int    # 0=NL 1=PQ 2=PL 3=DQ
    name:  str
    icon:  str


@dataclass
class ConjunctionEvent:
    dt:             datetime
    body1:          str   # nom affiché ("Lune", "Mars", …)
    body2:          str
    separation_deg: float


# ---------------------------------------------------------------------------
# Phase courante
# ---------------------------------------------------------------------------

def get_moon_info(t_dt: Optional[datetime] = None) -> dict:
    """
    Phase, illumination et âge de la Lune à l'instant t_dt.

    Retourne :
        icon, phase_name, illumination (%), age_days, elong_deg
    """
    from skyfield import almanac

    eph = _get_eph()
    ts  = _get_ts()
    if t_dt is None:
        t_dt = datetime.now(timezone.utc)
    t = ts.from_datetime(t_dt)

    elong = _elong_deg(t)
    illum = almanac.fraction_illuminated(eph, "moon", t) * 100.0

    idx        = int(elong / 45.0) % 8
    icon       = _PHASE8_ICONS[idx]
    phase_name = _PHASE8_NAMES[idx]
    age_days   = elong / 360.0 * 29.53   # approximation synodique

    return {
        "icon":        icon,
        "phase_name":  phase_name,
        "illumination": illum,
        "age_days":    age_days,
        "elong_deg":   elong,
    }


# ---------------------------------------------------------------------------
# Prochaines phases lunaires
# ---------------------------------------------------------------------------

def find_moon_phases(
    t_start: Optional[datetime] = None,
    months: int = 3,
) -> list[MoonPhaseEvent]:
    """Phases lunaires sur 'months' mois à partir de t_start."""
    from skyfield import almanac

    eph = _get_eph()
    ts  = _get_ts()
    if t_start is None:
        t_start = datetime.now(timezone.utc)
    t_end = t_start + timedelta(days=months * 31)

    times, phases = almanac.find_discrete(
        ts.from_datetime(t_start),
        ts.from_datetime(t_end),
        almanac.moon_phases(eph),
    )
    return [
        MoonPhaseEvent(
            dt=tp.utc_datetime(),
            phase=int(ph),
            name=_PHASE_NAMES[int(ph)],
            icon=_PHASE_ICONS[int(ph)],
        )
        for tp, ph in zip(times, phases)
    ]


# ---------------------------------------------------------------------------
# Conjonctions et rapprochements
# ---------------------------------------------------------------------------

def find_conjunctions(
    t_start: Optional[datetime] = None,
    t_end:   Optional[datetime] = None,
    moon_threshold:   float = 5.0,
    planet_threshold: float = 2.0,
) -> list[ConjunctionEvent]:
    """
    Rapprochements notables :
      • Lune–planète    (séparation < moon_threshold°, défaut 5°)
      • planète–planète (séparation < planet_threshold°, défaut 2°)

    Algorithme : balayage journalier vectorisé → détection de minima locaux
    → raffinement horaire.
    """
    import numpy as np

    eph = _get_eph()
    ts  = _get_ts()
    if t_start is None:
        t_start = datetime.now(timezone.utc)
    if t_end is None:
        t_end = t_start + timedelta(days=90)

    n_days  = max(2, (t_end - t_start).days)
    dt_list = [t_start + timedelta(days=i) for i in range(n_days + 1)]
    t_vec   = ts.from_datetimes(dt_list)

    earth = eph["earth"]

    # ── Positions vectorisées ────────────────────────────────────────────
    _pos: dict[str, object] = {}
    _pos["moon"] = earth.at(t_vec).observe(eph["moon"]).apparent()
    for pkey in _PLANET_KEYS.values():
        _pos[pkey] = earth.at(t_vec).observe(eph[pkey]).apparent()

    def _sep_arr(k1: str, k2: str) -> np.ndarray:
        return _pos[k1].separation_from(_pos[k2]).degrees

    def _sep_single(k1: str, k2: str, t_sky) -> float:
        a1 = earth.at(t_sky).observe(eph[k1]).apparent()
        a2 = earth.at(t_sky).observe(eph[k2]).apparent()
        return float(a1.separation_from(a2).degrees)

    # ── Détection des minima + raffinement ──────────────────────────────
    def _scan(k1: str, k2: str, threshold: float) -> list[ConjunctionEvent]:
        seps = _sep_arr(k1, k2)
        events: list[ConjunctionEvent] = []
        for i in range(1, len(seps) - 1):
            if seps[i] < threshold and seps[i] <= seps[i - 1] and seps[i] <= seps[i + 1]:
                # Minimum local : raffiner par pas d'1 h dans ±18 h
                dt_c     = dt_list[i]
                best_sep = float(seps[i])
                best_t   = t_vec[i]
                for h in range(-18, 19):
                    t2 = ts.from_datetime(dt_c + timedelta(hours=h))
                    s  = _sep_single(k1, k2, t2)
                    if s < best_sep:
                        best_sep = s
                        best_t   = t2
                events.append(ConjunctionEvent(
                    dt=best_t.utc_datetime(),
                    body1=_KEY_TO_NAME.get(k1, k1),
                    body2=_KEY_TO_NAME.get(k2, k2),
                    separation_deg=best_sep,
                ))
        return events

    results: list[ConjunctionEvent] = []

    # Lune – planètes
    for pkey in _PLANET_KEYS.values():
        results.extend(_scan("moon", pkey, moon_threshold))

    # Planète – planète
    pkeys = list(_PLANET_KEYS.values())
    for i in range(len(pkeys)):
        for j in range(i + 1, len(pkeys)):
            results.extend(_scan(pkeys[i], pkeys[j], planet_threshold))

    results.sort(key=lambda e: e.dt)
    return results


# ---------------------------------------------------------------------------
# Rendu photographique de la Lune (phase + orientation)
# ---------------------------------------------------------------------------

_MOON_PHOTO = (
    __import__("pathlib").Path(__file__).parent.parent / "data" / "moon_full.jpg"
)

# Cache module-level : clé (date_str, lat_arrondie, size) → bytes PNG
_moon_img_cache: dict = {}


def render_moon_image(
    t_dt: Optional[datetime] = None,
    observer_lat: float = 45.0,
    observer_lon: float = 0.0,
    size: int = 320,
    flip: bool = True,
    rotation_deg: Optional[float] = None,
) -> bytes:
    """
    Retourne les bytes PNG de la Lune photographique avec masque de phase.

    flip=True  (défaut) : convention œil nu NH — flip H + angle parallactique.
    flip=False          : convention carte (Est=droite) — rotation_deg imposée.
    """
    import numpy as np
    from PIL import Image
    import io

    if t_dt is None:
        t_dt = datetime.now(timezone.utc)

    # Cache module-level
    _rot_key = round(rotation_deg, 1) if rotation_deg is not None else 'auto'
    _cache_key = (t_dt.strftime("%Y-%m-%dT%H"), round(observer_lat, 1), round(observer_lon, 1), size, flip, _rot_key)
    if _cache_key in _moon_img_cache:
        return _moon_img_cache[_cache_key]

    eph = _get_eph()
    ts  = _get_ts()
    t = ts.from_datetime(t_dt)

    earth = eph["earth"]

    # ── Positions Lune et Soleil ────────────────────────────────────────
    moon_app = earth.at(t).observe(eph["moon"]).apparent()
    sun_app  = earth.at(t).observe(eph["sun"]).apparent()

    moon_ra, moon_dec, _ = moon_app.radec()
    sun_ra,  sun_dec,  _ = sun_app.radec()

    # Angle de phase φ ∈ [0°, 180°] : 0° = pleine lune, 180° = nouvelle lune
    elong = _elong_deg(t)
    phase_angle = abs(180.0 - elong)

    # Angle de position du limbe brillant : direction Soleil→Lune depuis Nord vers Est
    cos_dec = math.cos(math.radians(moon_dec.degrees))
    raw_dra = (sun_ra.degrees - moon_ra.degrees + 180.0) % 360.0 - 180.0
    dra_deg  = raw_dra * cos_dec
    ddec_deg = sun_dec.degrees - moon_dec.degrees
    pa_bright = math.degrees(math.atan2(dra_deg, ddec_deg)) % 360.0

    # ── Chargement et préparation de l'image ────────────────────────────
    img = Image.open(_MOON_PHOTO).convert("RGB")
    w, h = img.size
    s = min(w, h)
    img = img.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
    img = img.resize((size, size), Image.LANCZOS)
    if flip:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)  # photo télescope → convention œil nu (Est=gauche)

    arr = np.asarray(img, dtype=np.float32)

    # ── Masque de phase ─────────────────────────────────────────────────
    R  = size / 2.0
    ys, xs = np.mgrid[0:size, 0:size]
    if flip:
        nx = -(xs - R + 0.5) / R     # Est > 0 (gauche, convention œil nu)
    else:
        nx = (xs - R + 0.5) / R      # Est > 0 (droite, convention carte)
    ny = (R - 0.5 - ys) / R          # Nord > 0 (haut)
    r2 = nx ** 2 + ny ** 2
    on_moon = r2 <= 1.0
    nz = np.where(on_moon, np.sqrt(np.maximum(0.0, 1.0 - r2)), 0.0)

    phi = math.radians(phase_angle)
    pa  = math.radians(pa_bright)

    # Vecteur Soleil dans le référentiel image (Nord en haut, Est à gauche)
    sun_x = math.sin(phi) * math.sin(pa)
    sun_y = math.sin(phi) * math.cos(pa)
    sun_z = math.cos(phi)

    dot = nx * sun_x + ny * sun_y + nz * sun_z

    # Gradient progressif au terminateur (~25 px sur 320) — smoothstep
    tw = 0.09   # demi-largeur de transition (unités normalisées)
    frac = np.clip(dot / tw * 0.5 + 0.5, 0.0, 1.0)   # 0=ombre, 1=plein jour
    smooth = frac * frac * (3.0 - 2.0 * frac)         # courbe en S
    shadow = (1.0 - smooth) * 0.97
    shadow[~on_moon] = 0.0

    darkened = arr * (1.0 - shadow[:, :, np.newaxis])
    darkened = np.clip(darkened, 0, 255).astype(np.uint8)

    # ── Masque circulaire (fond transparent) ────────────────────────────
    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    rgba[:, :, :3] = darkened
    rgba[:, :, 3]  = np.where(on_moon, 255, 0).astype(np.uint8)
    result = Image.fromarray(rgba, "RGBA")

    # ── Orientation ──────────────────────────────────────────────────────
    if rotation_deg is not None:
        final_rot = rotation_deg
    else:
        # Angle parallactique q = atan2(sin H, tan φ·cos δ − sin δ·cos H)
        from skyfield.api import wgs84
        loc = wgs84.latlon(observer_lat, observer_lon)
        moon_topo = (earth + loc).at(t).observe(eph["moon"]).apparent()
        ra_topo, dec_topo, _ = moon_topo.radec()
        gast = t.gast
        lst  = gast + observer_lon / 15.0
        ha_h = (lst - ra_topo.hours) % 24.0
        if ha_h > 12.0:
            ha_h -= 24.0
        ha_rad = math.radians(ha_h * 15.0)
        lat_r  = math.radians(observer_lat)
        dec_r  = math.radians(dec_topo.degrees)
        q_deg  = math.degrees(math.atan2(
            math.sin(ha_rad),
            math.tan(lat_r) * math.cos(dec_r) - math.sin(dec_r) * math.cos(ha_rad),
        ))
        final_rot = -q_deg

    if abs(final_rot) > 0.5:
        result = result.rotate(final_rot, resample=Image.BICUBIC, expand=False)

    buf = io.BytesIO()
    result.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    _moon_img_cache[_cache_key] = png_bytes
    return png_bytes
