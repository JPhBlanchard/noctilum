"""
Carte du ciel interactive — Plotly.

Point d'entrée unique : build_sky_chart().
"""

from __future__ import annotations

import base64
import math
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import plotly.graph_objects as go

from engines.astro_engine import Observer
from engines.i18n import compass_dirs as _compass_dirs
from engines.projection import (
    CHART_RADIUS,
    altaz_to_xy,
    magnitude_to_opacity,
    magnitude_to_size,
)
from engines.star_catalog import spectral_color

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

_BG_OUTER      = '#0a0a1a'   # fond papier (hors disque)
_BG_SKY        = '#050510'   # fond du disque céleste
_HORIZON_LINE  = '#445566'   # cercle horizon
_PARALLEL_LINE = '#333355'   # cercles de parallèles (pointillés)
_CARDINAL_CLR  = '#8899aa'   # texte cardinaux
_PLANET_COLOR = {
    'Mercure': '#b8a898',   # gris-brun (surface rocheuse)
    'Vénus':   '#e8c87a',   # jaune-doré (nuages H₂SO₄)
    'Mars':    '#c1440e',   # rouge-brun (oxyde de fer)
    'Jupiter': '#c88b3a',   # ocre-orangé (bandes nuageuses)
    'Saturne': '#e8d5a0',   # or pâle (anneaux glacés)
    'Uranus':  '#7de8d8',   # cyan-vert (méthane)
    'Neptune': '#4b70dd',   # bleu profond (méthane)
    'Pluton':  '#b8956a',   # brun-rougeâtre (tholine)
}
_SUN_CLR       = '#FFF5A0'   # Soleil
_MOON_CLR      = '#E8E8D0'   # Lune
_LABEL_CLR     = '#FFFFFF'   # labels planètes

# ---------------------------------------------------------------------------
# Constantes de mise en page
# ---------------------------------------------------------------------------

_MARGIN_PX = 20          # doit correspondre à projection._MARGIN
_PARALLELS  = (30, 60)   # altitudes des cercles de parallèles

_CARDINAL8_ANGLES = (0, 45, 90, 135, 180, 225, 270, 315)
_CARDINAL4_ANGLES = (0, 90, 180, 270)

_PLANET_NAMES = frozenset(
    {'Mercure', 'Vénus', 'Mars', 'Jupiter', 'Saturne', 'Uranus', 'Neptune', 'Pluton'}
)

_CONST_LINE_COLOR  = 'rgba(100, 130, 220, 0.65)'
_CONST_BOUND_COLOR = 'rgba(80,  110, 180, 0.45)'
_ECLIPTIC_COLOR    = 'rgba(255, 210, 60, 0.55)'
_ECLIPTIC_GRID_COLOR = 'rgba(255, 190, 40, 0.55)'
_GRID_COLOR        = 'rgba(80, 120, 200, 0.55)'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rgba(hex_color: str, alpha: float) -> str:
    """Hex #rrggbb + alpha → chaîne 'rgba(r,g,b,a)' pour Plotly."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f'rgba({r},{g},{b},{alpha:.3f})'


def _effective_radius(width: int, height: int) -> float:
    """Rayon du disque en pixels (cohérent avec projection._MARGIN)."""
    return min(width, height) / 2.0 - _MARGIN_PX


def _parallel_radius_px(alt_deg: float, chart_r: float) -> float:
    """Rayon en pixels d'un cercle de parallèle (projection stéréographique)."""
    return chart_r * math.tan(math.radians((90.0 - alt_deg) / 2.0))


# ---------------------------------------------------------------------------
# Shapes Plotly (disque + parallèles)
# ---------------------------------------------------------------------------

def _make_shapes(cx: float, cy: float, chart_r: float) -> list[dict]:
    shapes: list[dict] = []

    # Disque du ciel
    shapes.append(dict(
        type='circle',
        x0=cx - chart_r, y0=cy - chart_r,
        x1=cx + chart_r, y1=cy + chart_r,
        fillcolor=_BG_SKY,
        line=dict(color=_HORIZON_LINE, width=2),
        layer='below',
    ))

    # Cercles de parallèles
    for alt in _PARALLELS:
        rp = _parallel_radius_px(alt, chart_r)
        shapes.append(dict(
            type='circle',
            x0=cx - rp, y0=cy - rp,
            x1=cx + rp, y1=cy + rp,
            fillcolor='rgba(0,0,0,0)',
            line=dict(color=_PARALLEL_LINE, width=1, dash='dot'),
            layer='below',
        ))

    return shapes


# ---------------------------------------------------------------------------
# Annotations Plotly (cardinaux + labels de parallèles)
# ---------------------------------------------------------------------------

def _make_annotations(cx: float, cy: float, chart_r: float) -> list[dict]:
    annotations: list[dict] = []
    label_r = chart_r + 18   # légèrement à l'extérieur de l'horizon

    # Points cardinaux (langue courante)
    _cmap = {angle: label for angle, label in _compass_dirs()}
    for az_deg in _CARDINAL8_ANGLES:
        label = _cmap.get(az_deg, str(az_deg))
        az_rad = math.radians(az_deg)
        x = cx + label_r * math.sin(az_rad)
        y = cy - label_r * math.cos(az_rad)
        principal = az_deg in _CARDINAL4_ANGLES
        annotations.append(dict(
            x=x, y=y,
            text=f'<b>{label}</b>' if principal else label,
            showarrow=False,
            font=dict(color=_CARDINAL_CLR, size=12 if principal else 10),
            xanchor='center',
            yanchor='middle',
        ))

    # Labels d'altitude sur l'axe est de chaque parallèle
    for alt in _PARALLELS:
        rp = _parallel_radius_px(alt, chart_r)
        annotations.append(dict(
            x=cx + rp + 4, y=cy,
            text=f'{alt}°',
            showarrow=False,
            font=dict(color=_PARALLEL_LINE, size=9),
            xanchor='left',
            yanchor='middle',
        ))

    return annotations


# ---------------------------------------------------------------------------
# Trace : lignes de constellations
# ---------------------------------------------------------------------------

def _constellation_trace(
    observer: Observer,
    t,
    width: int,
    height: int,
) -> Optional[go.Scatter]:
    """Trace des lignes de constellations, ou None si données indisponibles."""
    try:
        from engines.constellation_lines import get_constellation_segments
        xs, ys = get_constellation_segments(observer, t, width, height)
        if not xs:
            return None
        return go.Scatter(
            x=xs, y=ys,
            mode='lines',
            line=dict(color=_CONST_LINE_COLOR, width=1.0),
            hoverinfo='skip',
            showlegend=False,
        )
    except Exception:
        return None


def _constellation_label_trace(
    observer: Observer,
    t,
    width: int,
    height: int,
) -> Optional[go.Scatter]:
    """Trace des noms de constellations, ou None si données indisponibles."""
    try:
        from engines.constellation_lines import get_constellation_labels
        labels = get_constellation_labels(observer, t, width, height)
        if not labels:
            return None
        xs    = [pt[0] for pt in labels]
        ys    = [pt[1] for pt in labels]
        texts = [pt[2] for pt in labels]
        return go.Scatter(
            x=xs, y=ys,
            mode='text',
            text=texts,
            textfont=dict(color='rgba(140,160,230,0.65)', size=9),
            hoverinfo='skip',
            showlegend=False,
        )
    except Exception:
        return None


def _boundary_trace(
    observer: Observer,
    t,
    width: int,
    height: int,
) -> Optional[go.Scatter]:
    """Trace des limites IAU de constellations."""
    try:
        from engines.constellation_lines import get_constellation_boundaries
        xs, ys = get_constellation_boundaries(observer, t, width, height)
        if not xs:
            return None
        return go.Scatter(
            x=xs, y=ys,
            mode='lines',
            line=dict(color=_CONST_BOUND_COLOR, width=0.9, dash='dot'),
            hoverinfo='skip',
            showlegend=False,
        )
    except Exception:
        return None


def _ecliptic_trace(
    observer: Observer,
    t,
    width: int,
    height: int,
) -> Optional[go.Scatter]:
    """Trace du plan de l'écliptique."""
    try:
        from engines.sky_overlay import get_ecliptic
        xs, ys = get_ecliptic(observer, t, width, height)
        if not xs:
            return None
        return go.Scatter(
            x=xs, y=ys,
            mode='lines',
            line=dict(color=_ECLIPTIC_COLOR, width=1.2),
            hoverinfo='skip',
            showlegend=False,
        )
    except Exception:
        return None


def _ecliptic_grid_trace(
    observer: Observer,
    t,
    width: int,
    height: int,
) -> Optional[go.Scatter]:
    """Grille de coordonnées écliptiques."""
    try:
        from engines.sky_overlay import get_ecliptic_grid
        xs, ys = get_ecliptic_grid(observer, t, width, height)
        if not xs:
            return None
        return go.Scatter(
            x=xs, y=ys,
            mode='lines',
            line=dict(color=_ECLIPTIC_GRID_COLOR, width=0.7, dash='dot'),
            hoverinfo='skip',
            showlegend=False,
        )
    except Exception:
        return None


def _grid_trace(
    observer: Observer,
    t,
    width: int,
    height: int,
) -> Optional[go.Scatter]:
    """Trace de la grille équatoriale (méridiens + parallèles)."""
    try:
        from engines.sky_overlay import get_celestial_grid
        xs, ys = get_celestial_grid(observer, t, width, height)
        if not xs:
            return None
        return go.Scatter(
            x=xs, y=ys,
            mode='lines',
            line=dict(color=_GRID_COLOR, width=1.5),
            hoverinfo='skip',
            showlegend=False,
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Trace : étoiles
# ---------------------------------------------------------------------------

def _stars_trace(stars_df: pd.DataFrame, width: int, height: int) -> go.Scatter:
    import numpy as np

    alt  = stars_df['alt_deg'].to_numpy(dtype=float)
    az   = stars_df['az_deg'].to_numpy(dtype=float)
    mag  = stars_df['magnitude'].to_numpy(dtype=float)
    names = stars_df['name'].to_numpy(dtype=str)

    # Projection stéréographique vectorisée (les étoiles sont déjà alt > 0)
    from engines.projection import _MARGIN
    R      = min(width, height) / 2.0 - _MARGIN
    cx, cy = width / 2.0, height / 2.0
    r      = R * np.tan(np.radians(90.0 - alt) / 2.0)
    xs     = (cx + r * np.sin(np.radians(az))).tolist()
    ys     = (cy - r * np.cos(np.radians(az))).tolist()

    # Taille : mag ∈ [−2, 5] → px ∈ [8, 1.5]
    sizes = np.clip(8.0 + (mag + 2.0) * (1.5 - 8.0) / 7.0, 1.5, 8.0).tolist()

    # Opacité : mag ∈ [1, 4] → [1.0, 0.5]
    opacities = np.clip(1.0 + (mag - 1.0) * (0.5 - 1.0) / 3.0, 0.5, 1.0)

    # Couleurs spectrales (vectorisé pour BSC5, gris uniforme pour Hipparcos)
    if 'spectral_type' in stars_df.columns:
        sptypes = stars_df['spectral_type'].to_numpy(dtype=str)
        colors = [_rgba(spectral_color(sp), op) for sp, op in zip(sptypes, opacities)]
    else:
        colors = [_rgba('#CCCCCC', op) for op in opacities]

    customdata = list(zip(names, mag.tolist(), alt.tolist(), az.tolist()))

    return go.Scatter(
        x=xs, y=ys,
        mode='markers',
        marker=dict(color=colors, size=sizes, line=dict(width=0)),
        customdata=customdata,
        hovertemplate=(
            '<b>%{customdata[0]}</b><br>'
            'Mag : %{customdata[1]:.1f}<br>'
            'Alt : %{customdata[2]:.1f}°  '
            'Az : %{customdata[3]:.1f}°'
            '<extra></extra>'
        ),
        name='Étoiles',
        showlegend=False,
    )


# ---------------------------------------------------------------------------
# Traces : corps du système solaire
# ---------------------------------------------------------------------------

def _unicode_body_trace(
    x: float,
    y: float,
    char: str,
    color: str,
    font_size: int,
    name: str,
    alt: float,
    az: float,
    mag: Optional[float],
) -> go.Scatter:
    """Trace pour un corps affiché avec un caractère Unicode (Soleil ☀, Lune ●)."""
    mag_str = f'{mag:.1f}' if mag is not None else '—'
    return go.Scatter(
        x=[x], y=[y],
        mode='markers+text',
        # Marker invisible — sert uniquement de zone de capture hover
        marker=dict(symbol='circle', size=font_size,
                    color='rgba(0,0,0,0)', opacity=0),
        text=[char],
        textfont=dict(color=color, size=font_size),
        textposition='middle center',
        name=name,
        hovertemplate=(
            f'<b>{name}</b><br>'
            f'Mag : {mag_str}<br>'
            f'Alt : {alt:.1f}°  Az : {az:.1f}°'
            '<extra></extra>'
        ),
        showlegend=False,
    )


def _planet_marker_trace(
    x: float,
    y: float,
    name: str,
    alt: float,
    az: float,
    mag: Optional[float],
) -> go.Scatter:
    """Trace pour une planète classique : cercle-croix doré + label direct."""
    mag_str = f'{mag:.1f}' if mag is not None else '—'
    size = int(max(6, min(10, round(9.0 - (mag if mag is not None else 2.0) * 0.5))))
    return go.Scatter(
        x=[x], y=[y],
        mode='markers+text',
        marker=dict(
            symbol='circle-cross',
            size=size,
            color=_PLANET_COLOR.get(name, '#e8c87a'),
            line=dict(color='rgba(255,255,255,0.35)', width=1),
        ),
        text=[name],
        textfont=dict(color=_LABEL_CLR, size=9),
        textposition='top center',
        name=name,
        hovertemplate=(
            f'<b>{name}</b><br>'
            f'Mag : {mag_str}<br>'
            f'Alt : {alt:.1f}°  Az : {az:.1f}°'
            '<extra></extra>'
        ),
        showlegend=False,
    )


def _saturn_ring_traces(
    x: float, y: float, ring_P: float, ring_B: float,
) -> tuple[go.Scatter, go.Scatter]:
    """Deux demi-arcs d'anneaux de Saturne (fond + face) autour du marqueur."""
    # PA de l'axe majeur = pôle + 90° (anneau ⊥ au pôle)
    # Dans la carte (N=haut, E=droite), PA se mesure de N vers E CW.
    ring_pa_rad = math.radians(ring_P + 90.0)
    semi_major = 12.0   # px symbolique (A-ring outer)
    semi_minor = max(1.0, semi_major * abs(math.sin(math.radians(ring_B))))

    # Vecteurs axes en coordonnées data (y décroît vers le haut)
    maj_dx =  math.sin(ring_pa_rad)
    maj_dy = -math.cos(ring_pa_rad)
    min_dx =  math.cos(ring_pa_rad)
    min_dy =  math.sin(ring_pa_rad)

    def arc(t0: float, t1: float) -> tuple[list, list]:
        n = 36
        xs, ys = [], []
        for i in range(n + 1):
            θ = t0 + (t1 - t0) * i / n
            xs.append(x + semi_major * math.cos(θ) * maj_dx + semi_minor * math.sin(θ) * min_dx)
            ys.append(y + semi_major * math.cos(θ) * maj_dy + semi_minor * math.sin(θ) * min_dy)
        return xs, ys

    # B > 0 → pôle N vers observateur → arc +minor (sin θ > 0) = face avant
    if ring_B >= 0:
        back_xs,  back_ys  = arc(math.pi, 2 * math.pi)
        front_xs, front_ys = arc(0.0, math.pi)
    else:
        back_xs,  back_ys  = arc(0.0, math.pi)
        front_xs, front_ys = arc(math.pi, 2 * math.pi)

    back = go.Scatter(
        x=back_xs, y=back_ys, mode='lines',
        line=dict(color='rgba(200,170,106,0.35)', width=1.2),
        hoverinfo='skip', showlegend=False,
    )
    front = go.Scatter(
        x=front_xs, y=front_ys, mode='lines',
        line=dict(color='rgba(200,170,106,0.85)', width=1.5),
        hoverinfo='skip', showlegend=False,
    )
    return back, front


def _planet_traces(planets_list: list[dict], width: int, height: int) -> list[go.Scatter]:
    traces: list[go.Scatter] = []

    # Farthest first → closer objects rendered on top (correct z-order)
    sorted_planets = sorted(planets_list, key=lambda b: b.get('distance_au') or 0, reverse=True)
    for body in sorted_planets:
        if not body.get('above_horizon'):
            continue
        xy = altaz_to_xy(float(body['alt']), float(body['az']), width, height)
        if xy is None:
            continue
        x, y = xy
        name  = body['name']
        alt   = float(body['alt'])
        az    = float(body['az'])
        mag   = body.get('magnitude')

        if name == 'Soleil':
            mag_str = f'{mag:.1f}' if mag is not None else '—'
            traces.append(go.Scatter(
                x=[x], y=[y],
                mode='markers',
                marker=dict(symbol='circle', size=30,
                            color='rgba(0,0,0,0)', opacity=0),
                name='Soleil',
                hovertemplate=(
                    '<b>Soleil</b><br>'
                    f'Mag : {mag_str}<br>'
                    f'Alt : {alt:.1f}°  Az : {az:.1f}°'
                    '<extra></extra>'
                ),
                showlegend=False,
            ))
        elif name == 'Lune':
            # Marqueur invisible pour hover — l'image est ajoutée en layout_image
            mag_str = f'{mag:.1f}' if mag is not None else '—'
            traces.append(go.Scatter(
                x=[x], y=[y],
                mode='markers',
                marker=dict(symbol='circle', size=34,
                            color='rgba(0,0,0,0)', opacity=0),
                name='Lune',
                hovertemplate=(
                    '<b>Lune</b><br>'
                    f'Mag : {mag_str}<br>'
                    f'Alt : {alt:.1f}°  Az : {az:.1f}°'
                    '<extra></extra>'
                ),
                showlegend=False,
            ))
        elif name == 'Saturne':
            ring_P = body.get('ring_P_deg')
            ring_B = body.get('ring_B_deg')
            if ring_P is not None and ring_B is not None:
                back, front = _saturn_ring_traces(x, y, ring_P, ring_B)
                traces.append(back)
                traces.append(_planet_marker_trace(x, y, name, alt, az, mag))
                traces.append(front)
            else:
                traces.append(_planet_marker_trace(x, y, name, alt, az, mag))
        elif name in _PLANET_NAMES:
            traces.append(_planet_marker_trace(x, y, name, alt, az, mag))

    return traces


# ---------------------------------------------------------------------------
# Point d'entrée public
# ---------------------------------------------------------------------------

_DEFAULT_OPTIONS: dict[str, bool] = {
    "show_stars":        True,
    "show_planets":      True,
    "show_const_lines":  True,
    "show_const_names":  True,
    "show_const_bounds": False,
    "show_ecliptic":      False,
    "show_ecliptic_grid": False,
    "show_grid":          False,
    "show_messier":       False,
    "show_milkyway":          False,
    "show_milkyway_guide":    False,
    "show_galactic_points":   False,
    "show_ecliptic_points":   False,
}


def _sh_clip_alt(verts: list, alt_min: float) -> list:
    """Sutherland-Hodgman : clip le polygone en conservant les sommets alt >= alt_min."""
    if len(verts) < 3:
        return []
    result = []
    n = len(verts)
    for i in range(n):
        curr_alt, curr_az = verts[i]
        prev_alt, prev_az = verts[(i - 1) % n]
        curr_in = curr_alt >= alt_min
        prev_in = prev_alt >= alt_min
        if curr_in:
            if not prev_in:
                t   = (alt_min - prev_alt) / (curr_alt - prev_alt)
                daz = ((curr_az - prev_az + 180) % 360) - 180
                result.append((alt_min, (prev_az + t * daz) % 360))
            result.append((curr_alt, curr_az))
        elif prev_in:
            t   = (alt_min - prev_alt) / (curr_alt - prev_alt)
            daz = ((curr_az - prev_az + 180) % 360) - 180
            result.append((alt_min, (prev_az + t * daz) % 360))
    return result


def _fill_horizon_arcs(clipped: list, alt_min: float, step_deg: float = 5.0) -> list:
    """
    Insère des points intermédiaires à alt_min entre des sommets consécutifs tous deux
    à l'horizon quand l'écart azimuthal est grand.  Cela ferme correctement le polygone
    le long du bord du cercle horizon au lieu d'une corde rectiligne qui traverserait
    le disque et remplirait la mauvaise région.
    """
    if len(clipped) < 3:
        return clipped
    result: list = []
    n = len(clipped)
    tol = 0.02
    for i in range(n):
        alt, az = clipped[i]
        result.append((alt, az))
        next_alt, next_az = clipped[(i + 1) % n]
        if abs(alt - alt_min) < tol and abs(next_alt - alt_min) < tol:
            daz = ((next_az - az + 180) % 360) - 180   # diff signée (chemin court)
            if abs(daz) > step_deg * 2:
                steps = max(2, int(abs(daz) / step_deg))
                for k in range(1, steps):
                    result.append((alt_min, (az + daz * k / steps) % 360))
    return result


def _milkyway_traces(
    observer: Observer,
    t,
    width: int,
    height: int,
) -> list[go.Scatter]:
    """Voie Lactée image-réelle (Stellarium) — vue zénith."""
    try:
        from engines.milky_way import get_milky_way_scatter, get_galactic_center_altaz
        mw = get_milky_way_scatter(observer, t, mode="zenith", width=width, height=height)
        traces = []
        if mw["x"]:
            traces.append(go.Scatter(
                x=mw["x"], y=mw["y"],
                mode="markers",
                marker=dict(size=mw["size"], color=mw["rgba"]),
                hoverinfo="skip",
                showlegend=False,
            ))
        return traces
    except Exception:
        return []


def _milkyway_guide_traces(
    observer, t, width: int, height: int, lang: str = "fr"
) -> list[go.Scatter]:
    """Annotations des structures remarquables de la Voie Lactée (nuages, rifts, bras)."""
    try:
        from engines.milky_way import get_milkyway_guide_altaz
        traces = []
        for pt in get_milkyway_guide_altaz(observer, t, lang=lang):
            xy = altaz_to_xy(pt["alt"], pt["az"], width, height)
            if xy is None:
                continue
            traces.append(go.Scatter(
                x=[xy[0]], y=[xy[1]],
                mode="markers+text",
                marker=dict(symbol="circle", size=6,
                            color=pt["color"], opacity=0.85),
                text=[f"{pt['symbol']} {pt['label']}"],
                textfont=dict(size=9, color=pt["color"]),
                textposition="top center",
                hovertemplate=(
                    f"{pt['label']}<br>"
                    f"Alt {pt['alt']:.1f}°  Az {pt['az']:.1f}°<extra></extra>"
                ),
                showlegend=False,
            ))
        return traces
    except Exception:
        return []


def _galactic_points_traces(
    observer, t, width: int, height: int
) -> list[go.Scatter]:
    """Points de référence galactiques : centre, anticentre, pôles N/S."""
    try:
        from engines.milky_way import get_galactic_points_altaz
        traces = []
        for pt in get_galactic_points_altaz(observer, t):
            xy = altaz_to_xy(pt["alt"], pt["az"], width, height)
            if xy is None:
                continue
            traces.append(go.Scatter(
                x=[xy[0]], y=[xy[1]],
                mode="markers+text",
                marker=dict(symbol="circle", size=pt["size"],
                            color="rgba(0,0,0,0)", opacity=0),
                text=[pt["symbol"]],
                textfont=dict(size=pt["size"], color=pt["color"]),
                textposition="middle center",
                hovertemplate=(
                    f"{pt['label']}<br>"
                    f"Alt {pt['alt']:.1f}°  Az {pt['az']:.1f}°<extra></extra>"
                ),
                showlegend=False,
            ))
        return traces
    except Exception:
        return []


def _ecliptic_points_traces(
    observer, t, width: int, height: int
) -> list[go.Scatter]:
    """Points cardinaux de l'écliptique : équinoxes ♈♎ et solstices ♋♑."""
    try:
        from engines.sky_overlay import get_ecliptic_points_altaz
        traces = []
        for pt in get_ecliptic_points_altaz(observer, t):
            xy = altaz_to_xy(pt["alt"], pt["az"], width, height)
            if xy is None:
                continue
            traces.append(go.Scatter(
                x=[xy[0]], y=[xy[1]],
                mode="markers+text",
                marker=dict(symbol="circle", size=pt["size"],
                            color="rgba(0,0,0,0)", opacity=0),
                text=[pt["symbol"]],
                textfont=dict(size=pt["size"], color=pt["color"]),
                textposition="middle center",
                hovertemplate=(
                    f"{pt['label']}<br>"
                    f"Alt {pt['alt']:.1f}°  Az {pt['az']:.1f}°<extra></extra>"
                ),
                showlegend=False,
            ))
        return traces
    except Exception:
        return []


def _hex_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f'rgba({r},{g},{b},{alpha})'


def _extended_halo_traces(messier_df: pd.DataFrame, width: int, height: int) -> list[go.Scatter]:
    """Ellipses translucides pour les objets étendus (galaxies, nébuleuses…)."""
    import math
    traces = []
    for _, row in messier_df.iterrows():
        a = row.get('major_deg', 0)
        b = row.get('minor_deg', 0)
        if a < 0.05:
            continue
        b = b if b > 0 else a
        alt_c, az_c = row['alt_deg'], row['az_deg']
        color = row['color']
        pa_rad = math.radians(row.get('pa_deg', 0))
        cos_alt = math.cos(math.radians(max(1.0, alt_c)))

        for scale, opacity in ((1.0, 0.22), (0.5, 0.42)):
            xs, ys = [], []
            for i in range(49):
                theta = 2 * math.pi * i / 48
                sa, sb = scale * a, scale * b
                dalt    = sa * math.cos(theta) * math.cos(pa_rad) - sb * math.sin(theta) * math.sin(pa_rad)
                daz_sky = sa * math.cos(theta) * math.sin(pa_rad) + sb * math.sin(theta) * math.cos(pa_rad)
                pt_alt = max(0.1, alt_c + dalt)
                pt_az  = (az_c + daz_sky / cos_alt) % 360
                xy = altaz_to_xy(pt_alt, pt_az, width, height)
                if xy:
                    xs.append(xy[0])
                    ys.append(xy[1])
            if len(xs) > 2:
                traces.append(go.Scatter(
                    x=xs, y=ys,
                    mode='lines',
                    fill='toself',
                    fillcolor=f'rgba(160,160,160,{opacity})',
                    line=dict(color='rgba(0,0,0,0)', width=0),
                    hoverinfo='skip',
                    showlegend=False,
                ))

        # Marqueur invisible au centre pour le tooltip
        cxy = altaz_to_xy(alt_c, az_c, width, height)
        if cxy:
            from engines.messier_catalog import TYPE_INFO, _DEFAULT_TYPE
            _, _, type_fr = TYPE_INFO.get(row['type'], _DEFAULT_TYPE)
            name = row['name'] if row['name'] != row['label'] else ''
            traces.append(go.Scatter(
                x=[cxy[0]], y=[cxy[1]],
                mode='markers',
                marker=dict(size=max(12, int(a * 380 / 90)), opacity=0, color='rgba(0,0,0,0)'),
                hovertemplate=(
                    f"<b>{row['label']}</b>{' — ' + name if name else ''}<br>"
                    f"{type_fr} · mag {row['mag']:.1f}<br>"
                    f"Alt {alt_c:.1f}°  Az {az_c:.1f}°"
                    "<extra></extra>"
                ),
                showlegend=False,
            ))
    return traces


def _messier_traces(messier_df: pd.DataFrame, width: int, height: int) -> list[go.Scatter]:
    """Un trace Plotly par type d'objet Messier (symboles distincts)."""
    if messier_df.empty:
        return []

    traces = []
    for typ, grp in messier_df.groupby('type'):
        sym   = grp['symbol'].iloc[0]
        color = grp['color'].iloc[0]

        xs, ys, labels, customs = [], [], [], []
        for _, row in grp.iterrows():
            xy = altaz_to_xy(row['alt_deg'], row['az_deg'], width, height)
            if xy is None:
                continue
            xs.append(xy[0])
            ys.append(xy[1])
            labels.append(row['label'])
            customs.append((row['label'], row['name'], row['mag'],
                            row['alt_deg'], row['az_deg']))

        if not xs:
            continue

        from engines.messier_catalog import TYPE_INFO, _DEFAULT_TYPE
        _, _, type_fr = TYPE_INFO.get(typ, _DEFAULT_TYPE)

        traces.append(go.Scatter(
            x=xs, y=ys,
            mode='markers+text',
            marker=dict(
                symbol=sym,
                size=14,
                color=color,
                opacity=0.9,
                line=dict(width=2.0, color=color),
            ),
            text=labels,
            textfont=dict(color=color, size=8),
            textposition='top center',
            customdata=customs,
            hovertemplate=(
                '<b>%{customdata[1]}</b>  (%{customdata[0]})<br>'
                f'Type : {type_fr}<br>'
                'Mag : %{customdata[2]:.1f}<br>'
                'Alt : %{customdata[3]:.1f}°  Az : %{customdata[4]:.1f}°'
                '<extra></extra>'
            ),
            name=type_fr,
            showlegend=False,
        ))

    return traces


def _satellite_traces(
    satellites_data: list[dict],
    width: int,
    height: int,
) -> list[go.Scatter]:
    """Traces satellites : trajectoire passé (tireté) + futur (trait) + point courant."""
    traces = []
    for sat in satellites_data:
        # Trajectoire passée
        px, py = [], []
        for alt, az in zip(sat["past_alts"], sat["past_azs"]):
            xy = altaz_to_xy(alt, az, width, height)
            if xy:
                px.append(xy[0]); py.append(xy[1])
            else:
                px.append(None); py.append(None)
        if any(v is not None for v in px):
            traces.append(go.Scatter(
                x=px, y=py, mode="lines",
                line=dict(color="rgba(255,220,80,0.45)", width=1.2, dash="dot"),
                hoverinfo="skip", showlegend=False,
            ))
        # Trajectoire future
        fx, fy = [], []
        for alt, az in zip(sat["future_alts"], sat["future_azs"]):
            xy = altaz_to_xy(alt, az, width, height)
            if xy:
                fx.append(xy[0]); fy.append(xy[1])
            else:
                fx.append(None); fy.append(None)
        if any(v is not None for v in fx):
            traces.append(go.Scatter(
                x=fx, y=fy, mode="lines",
                line=dict(color="rgba(255,220,80,0.80)", width=1.5),
                hoverinfo="skip", showlegend=False,
            ))
        # Position courante
        xy = altaz_to_xy(sat["alt"], sat["az"], width, height)
        if xy:
            traces.append(go.Scatter(
                x=[xy[0]], y=[xy[1]],
                mode="markers+text",
                marker=dict(symbol="triangle-up", size=10,
                            color="#ffdc50", line=dict(color="#000", width=0.6)),
                text=[sat["name"].split("(")[0].strip()],
                textposition="top center",
                textfont=dict(color="#ffdc50", size=9),
                hovertemplate=(
                    f"<b>{sat['name']}</b><br>"
                    f"Alt {sat['alt']:.1f}°  Az {sat['az']:.1f}°<extra></extra>"
                ),
                showlegend=False,
            ))
    return traces


def _sun_layout_image(
    planets_list: list[dict],
    width: int,
    height: int,
) -> Optional[dict]:
    """Image Soleil photographique pour le layout Plotly (vue zénith)."""
    from engines.sun_engine import render_sun_image

    sun = next(
        (b for b in planets_list if b['name'] == 'Soleil' and b.get('above_horizon')),
        None,
    )
    if sun is None:
        return None

    alt = float(sun['alt'])
    xy = altaz_to_xy(alt, float(sun['az']), width, height)
    if xy is None:
        return None
    x_s, y_s = xy

    cx, cy  = width / 2.0, height / 2.0
    chart_r = _effective_radius(width, height)

    diam_arcsec = sun.get('ang_diam_arcsec') or 1919.0
    diam_deg    = diam_arcsec / 3600.0
    display_px  = max(12, min(20, int(chart_r / 90.0 * diam_deg * 8)))

    if math.sqrt((x_s - cx) ** 2 + (y_s - cy) ** 2) > chart_r:
        return None

    png = render_sun_image(size=64)
    b64 = base64.b64encode(png).decode()

    return dict(
        source=f'data:image/png;base64,{b64}',
        x=x_s, y=y_s,
        sizex=display_px, sizey=display_px,
        xanchor='center', yanchor='middle',
        xref='x', yref='y',
        layer='above',
    )


def _moon_layout_image(
    planets_list: list[dict],
    observer: Observer,
    t: Optional[datetime],
    width: int,
    height: int,
) -> Optional[dict]:
    """Image Lune orientée 'zénith en haut' pour le layout Plotly."""
    from engines.moon_engine import render_moon_image

    moon = next(
        (b for b in planets_list if b['name'] == 'Lune' and b.get('above_horizon')),
        None,
    )
    if moon is None:
        return None

    alt = float(moon['alt'])
    xy = altaz_to_xy(alt, float(moon['az']), width, height)
    if xy is None:
        return None
    x_m, y_m = xy

    cx, cy    = width / 2.0, height / 2.0
    chart_r   = _effective_radius(width, height)

    diam_arcsec = moon.get('ang_diam_arcsec') or 1842.0
    diam_deg    = diam_arcsec / 3600.0
    display_px  = max(12, min(20, int(chart_r / 90.0 * diam_deg * 8)))

    if math.sqrt((x_m - cx) ** 2 + (y_m - cy) ** 2) > chart_r:
        return None

    # Rotation PIL CCW = atan2(x_m-cx, y_m-cy) — aligne Nord équatorial → zénith
    # Dérivation : vecteur vers zénith dans l'espace image = (cx-x_m, cy-y_m) screen,
    # angle CCW depuis "haut" = atan2(x_m-cx, y_m-cy).
    chart_angle = math.degrees(math.atan2(x_m - cx, y_m - cy))

    t_dt = t or datetime.now(timezone.utc)

    png = render_moon_image(
        t_dt=t_dt,
        observer_lat=observer.lat,
        observer_lon=observer.lon,
        size=64,
        flip=False,
        rotation_deg=chart_angle,
    )
    b64 = base64.b64encode(png).decode()

    return dict(
        source=f'data:image/png;base64,{b64}',
        x=x_m, y=y_m,
        sizex=display_px, sizey=display_px,
        xanchor='center', yanchor='middle',
        xref='x', yref='y',
        layer='above',
    )


def build_sky_chart(
    stars_df: pd.DataFrame,
    planets_list: list[dict],
    observer: Observer,
    t: Optional[datetime] = None,
    width: int = 800,
    height: int = 800,
    options: Optional[dict[str, bool]] = None,
    messier_df: Optional[pd.DataFrame] = None,
    satellites_data: list[dict] | None = None,
    lang: str = "fr",
    highlight: Optional[tuple[float, float, str]] = None,
    halo_mag_limit: float = 6.5,
) -> go.Figure:
    """
    Construit et retourne la carte du ciel interactive (go.Figure Plotly).

    Parameters
    ----------
    stars_df     : DataFrame de StarCatalog.get_visible() — colonnes alt_deg/az_deg requises
    planets_list : liste de dicts retournée par get_planets_data()
    observer     : lieu d'observation
    t            : instant UTC (None → maintenant)
    width/height : dimensions de la figure en pixels
    options      : dict de booléens pour activer/désactiver les couches (voir _DEFAULT_OPTIONS)
    """
    opts = {**_DEFAULT_OPTIONS, **(options or {})}

    cx = width  / 2.0
    cy = height / 2.0
    chart_r = _effective_radius(width, height)

    fig = go.Figure()

    # Ancre invisible — garantit que l'espace de coordonnées couvre [0,width]×[0,height]
    fig.add_trace(go.Scatter(
        x=[0, width], y=[0, height],
        mode='markers',
        marker=dict(opacity=0, size=0.1),
        hoverinfo='skip',
        showlegend=False,
    ))

    # Voie Lactée (couche la plus basse — derrière tout le reste)
    if opts["show_milkyway"]:
        for tr in _milkyway_traces(observer, t, width, height):
            fig.add_trace(tr)

    # Guide Voie Lactée (nuages stellaires, rifts, bras spiraux)
    if opts.get("show_milkyway_guide"):
        for tr in _milkyway_guide_traces(observer, t, width, height, lang=lang):
            fig.add_trace(tr)

    # Points de référence galactiques
    if opts.get("show_galactic_points"):
        for tr in _galactic_points_traces(observer, t, width, height):
            fig.add_trace(tr)

    # Points cardinaux écliptiques
    if opts.get("show_ecliptic_points"):
        for tr in _ecliptic_points_traces(observer, t, width, height):
            fig.add_trace(tr)

    # Grille céleste
    if opts["show_grid"]:
        tr = _grid_trace(observer, t, width, height)
        if tr is not None:
            fig.add_trace(tr)

    # Limites de constellations
    if opts["show_const_bounds"]:
        tr = _boundary_trace(observer, t, width, height)
        if tr is not None:
            fig.add_trace(tr)

    # Écliptique
    if opts["show_ecliptic"]:
        tr = _ecliptic_trace(observer, t, width, height)
        if tr is not None:
            fig.add_trace(tr)

    # Grille écliptique
    if opts.get("show_ecliptic_grid"):
        tr = _ecliptic_grid_trace(observer, t, width, height)
        if tr is not None:
            fig.add_trace(tr)

    # Lignes de constellations
    if opts["show_const_lines"]:
        tr = _constellation_trace(observer, t, width, height)
        if tr is not None:
            fig.add_trace(tr)

    # Noms de constellations
    if opts["show_const_names"]:
        tr = _constellation_label_trace(observer, t, width, height)
        if tr is not None:
            fig.add_trace(tr)

    # Étoiles
    if opts["show_stars"] and not stars_df.empty:
        fig.add_trace(_stars_trace(stars_df, width, height))

    # Halos étendus — affichés jusqu'à halo_mag_limit (couplé au curseur étoiles)
    if messier_df is not None and not messier_df.empty:
        _halo_df = messier_df[messier_df['mag'] <= halo_mag_limit]
        for tr in _extended_halo_traces(_halo_df, width, height):
            fig.add_trace(tr)
    # Symboles Messier complets — seulement si l'option est cochée
    if opts["show_messier"] and messier_df is not None and not messier_df.empty:
        for tr in _messier_traces(messier_df, width, height):
            fig.add_trace(tr)

    # Planètes
    if opts["show_planets"]:
        for trace in _planet_traces(planets_list, width, height):
            fig.add_trace(trace)
        _imgs = []
        sun_img = _sun_layout_image(planets_list, width, height)
        if sun_img is not None:
            _imgs.append(sun_img)
        moon_img = _moon_layout_image(planets_list, observer, t, width, height)
        if moon_img is not None:
            _imgs.append(moon_img)
        if _imgs:
            fig.update_layout(images=_imgs)

    # Satellites
    if opts.get("show_satellites") and satellites_data:
        for trace in _satellite_traces(satellites_data, width, height):
            fig.add_trace(trace)

    fig.update_layout(
        width=width,
        height=height,
        paper_bgcolor=_BG_OUTER,
        plot_bgcolor=_BG_OUTER,
        margin=dict(l=0, r=0, t=0, b=0),
        dragmode='pan',
        xaxis=dict(
            range=[0, width],
            visible=False,
            showgrid=False,
            zeroline=False,
            fixedrange=False,
        ),
        yaxis=dict(
            range=[height, 0],    # y croît vers le bas → nord en haut du disque
            visible=False,
            showgrid=False,
            zeroline=False,
            scaleanchor='x',
            scaleratio=1,
            fixedrange=False,
        ),
        shapes=_make_shapes(cx, cy, chart_r),
        annotations=_make_annotations(cx, cy, chart_r),
        showlegend=False,
        hovermode='closest',
    )

    if highlight is not None:
        h_alt, h_az, h_label = highlight
        xy = altaz_to_xy(h_alt, h_az, width, height)
        if xy is not None:
            hx, hy = xy
            s = 18
            fig.add_trace(go.Scatter(
                x=[hx - s, hx + s, None, hx, hx, None],
                y=[hy, hy, None, hy - s, hy + s, None],
                mode="lines",
                line=dict(color="#ffcc00", width=2),
                hoverinfo="skip", showlegend=False,
            ))
            fig.add_trace(go.Scatter(
                x=[hx], y=[hy],
                mode="markers+text",
                marker=dict(symbol="circle-open", size=22, color="#ffcc00", line=dict(width=2)),
                text=[h_label], textposition="top center",
                textfont=dict(color="#ffcc00", size=12),
                hovertemplate=f"{h_label}<br>Alt {h_alt:.1f}° Az {h_az:.1f}°<extra></extra>",
                showlegend=False,
            ))

    return fig
