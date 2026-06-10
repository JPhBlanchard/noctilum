"""
Voie Lactée — rendu basé sur image réelle (Stellarium milkyway.png).
Panorama 4096×2048, projection équirectangulaire galactique, licence GPL.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from engines.astro_engine import Observer

_DATA_DIR = Path(__file__).parent.parent / "data"
_IMG_PATH = _DATA_DIR / "milkyway.png"
_IMG_URL  = (
    "https://raw.githubusercontent.com/Stellarium/stellarium"
    "/master/textures/milkyway.png"
)

# ── Cache mémoire global ──────────────────────────────────────────────────────
_texture:    np.ndarray | None = None   # 512×1024 float32 luminosité
_grid_cache: dict              = {}     # resolution → (l°, b°, lum)
_altaz_cache: dict             = {}     # (lat, lon, elev, t_key, n) → (alts°, azs°)


# ── Texture ───────────────────────────────────────────────────────────────────

def _load_texture() -> np.ndarray:
    """Charge milkyway.png → tableau 512×1024 de luminosité [0, 1]."""
    global _texture
    if _texture is not None:
        return _texture

    if not _IMG_PATH.exists():
        from engines.data_download import download as _dl
        _dl("milkyway.png")

    from PIL import Image
    img      = Image.open(_IMG_PATH).convert("RGBA")
    img      = img.resize((1024, 512), Image.LANCZOS)
    arr      = np.array(img, dtype=np.float32) / 255.0
    _texture = (arr[:, :, 0] + arr[:, :, 1] + arr[:, :, 2]) / 3.0
    return _texture


# ── Grille galactique ─────────────────────────────────────────────────────────

def _get_grid_points(
    resolution: float = 0.4,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Grille (l°, b°, lum) filtrée lum ≥ 0.03 — mise en cache par résolution."""
    if resolution in _grid_cache:
        return _grid_cache[resolution]

    texture = _load_texture()

    l_vals  = np.arange(0.0, 360.0, resolution)
    b_vals  = np.arange(-90.0, 90.0 + resolution, resolution)
    l_grid, b_grid = np.meshgrid(l_vals, b_vals)
    l_flat  = l_grid.ravel().copy()
    b_flat  = b_grid.ravel().copy()

    # Jitter aléatoire à graine fixe — casse la régularité de la grille
    # qui crée l'effet de moiré une fois projetée en stéréographique/équirectangulaire.
    rng    = np.random.default_rng(42)
    jitter = resolution * 0.45
    l_flat = (l_flat + rng.uniform(-jitter, jitter, len(l_flat))) % 360.0
    b_flat = np.clip(b_flat + rng.uniform(-jitter, jitter, len(b_flat)), -90.0, 90.0)

    px  = (l_flat / 360.0 * 1024).astype(int) % 1024
    py  = ((90.0 - b_flat) / 180.0 * 512).astype(int).clip(0, 511)
    lum = texture[py, px]

    mask   = lum >= 0.03
    result = (l_flat[mask], b_flat[mask], lum[mask])
    _grid_cache[resolution] = result
    return result


# ── Conversion AltAz ─────────────────────────────────────────────────────────

def _t_key(t) -> str:
    """Clé de cache arrondie à 5 min."""
    if isinstance(t, datetime):
        mins = (t.hour * 60 + t.minute) // 5 * 5
        return f"{t.date()}T{mins // 60:02d}:{mins % 60:02d}"
    return str(t)


def _compute_altaz(
    observer: Observer,
    t,
    l_m: np.ndarray,
    b_m: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Conversion vectorisée galactic → AltAz via astropy."""
    from astropy.coordinates import SkyCoord, EarthLocation, AltAz
    from astropy.time import Time
    import astropy.units as u

    loc = EarthLocation(
        lat=observer.lat * u.deg,
        lon=observer.lon * u.deg,
        height=observer.elevation * u.m,
    )
    if isinstance(t, datetime):
        t_ap = Time(t if t.tzinfo else t.replace(tzinfo=timezone.utc))
    else:
        t_ap = Time(t)

    gal   = SkyCoord(l=l_m * u.deg, b=b_m * u.deg, frame="galactic")
    frame = AltAz(obstime=t_ap, location=loc)
    ac    = gal.transform_to(frame)
    return ac.alt.deg, ac.az.deg


# ── Normalisation + rendu ─────────────────────────────────────────────────────

def _display_lum(lum: np.ndarray) -> np.ndarray:
    """
    Normalise la luminosité des points visibles et applique une correction gamma
    pour révéler les nuances même quand le centre galactique est sous l'horizon.
    """
    if len(lum) < 5:
        return lum
    p5  = np.percentile(lum, 5)
    p99 = np.percentile(lum, 99)
    lum_n = np.clip((lum - p5) / (p99 - p5 + 1e-9), 0.0, 1.0)
    return lum_n ** 0.6    # gamma < 1 booste les tons clairs de façon non-linéaire


def _lum_to_rgba(lum_d: np.ndarray, opacity_boost: float = 1.0) -> list[str]:
    """Couleur + opacité encodées en RGBA. opacity_boost > 1 pour le mode paysage."""
    r = np.select([lum_d > 0.75, lum_d > 0.45, lum_d > 0.20], [255, 221, 204], default=170)
    g = np.select([lum_d > 0.75, lum_d > 0.45, lum_d > 0.20], [255, 232, 214], default=187)
    b = np.select([lum_d > 0.75, lum_d > 0.45, lum_d > 0.20], [255, 255, 240], default=221)
    a = np.clip((0.03 + lum_d * 0.22) * opacity_boost, 0.0, 0.40)
    return [
        f'rgba({ri},{gi},{bi},{ai:.3f})'
        for ri, gi, bi, ai in zip(r.astype(int), g.astype(int), b.astype(int), a)
    ]


# ── API publique ──────────────────────────────────────────────────────────────

def get_milky_way_scatter(
    observer: Observer,
    t,
    mode: str         = "zenith",
    resolution: float = 0.4,
    *,
    width: int        = 800,
    height: int       = 800,
    az_center: float  = 180.0,
    az_fov: float     = 120.0,
    alt_min: float    = -5.0,
    alt_max: float    = 90.0,
) -> dict:
    """
    Retourne dict {x, y, opacity, size, color} prêt pour go.Scatter(mode='markers').

    La conversion AltAz (~15 k points à 1°) est mise en cache par tranches de 5 min.
    La normalisation locale garantit un rendu visible quelle que soit la saison/lieu.
    """
    l_m, b_m, lum = _get_grid_points(resolution)

    cache_key = (
        round(observer.lat, 2),
        round(observer.lon, 2),
        observer.elevation,
        _t_key(t),
        len(l_m),
    )
    if cache_key in _altaz_cache:
        alts, azs = _altaz_cache[cache_key]
    else:
        alts, azs = _compute_altaz(observer, t, l_m, b_m)
        _altaz_cache.clear()
        _altaz_cache[cache_key] = (alts, azs)

    # Filtrage altitude — léger débordement toléré pour lisser la limite d'horizon
    vis  = alts > 0.0
    alts = alts[vis]
    azs  = azs[vis]
    lum  = lum[vis]

    if len(lum) == 0:
        return {"x": [], "y": [], "opacity": [], "size": [], "color": []}

    # Projection vectorisée
    if mode == "zenith":
        _MARGIN = 20
        radius  = min(width, height) / 2.0 - _MARGIN
        cx, cy  = width / 2.0, height / 2.0
        z_rad   = np.radians(90.0 - alts)
        az_rad  = np.radians(azs)
        r       = radius * np.tan(z_rad / 2.0)
        xs      = (cx + r * np.sin(az_rad)).tolist()
        ys      = (cy - r * np.cos(az_rad)).tolist()
        lum_out = lum

    else:  # landscape
        half    = az_fov / 2.0
        daz     = ((azs - az_center + 180.0) % 360.0) - 180.0
        in_view = (
            (daz  >= -half)   & (daz  <= half) &
            (alts >= alt_min) & (alts <= alt_max)
        )
        daz     = daz[in_view]
        alts_v  = alts[in_view]
        lum_out = lum[in_view]
        if len(lum_out) == 0:
            return {"x": [], "y": [], "opacity": [], "size": [], "color": []}
        xs = ((daz / half + 1.0) * (width / 2.0)).tolist()
        ys = (height - ((alts_v - alt_min) / (alt_max - alt_min)) * height).tolist()

    # Normalisation locale + gamma pour rendu visible quelle que soit la config
    lum_d         = _display_lum(np.asarray(lum_out))
    opacity_boost = 1.4 if mode == "landscape" else 1.0

    return {
        "x":    xs,
        "y":    ys,
        "rgba": _lum_to_rgba(lum_d, opacity_boost),
        "size": (1.0 + lum_d * 1.0).tolist(),
    }


def get_galactic_center_altaz(observer: Observer, t) -> tuple[float, float]:
    """Retourne (alt°, az°) du centre galactique (l=0°, b=0°)."""
    alts, azs = _compute_altaz(observer, t, np.array([0.0]), np.array([0.0]))
    return float(alts[0]), float(azs[0])
