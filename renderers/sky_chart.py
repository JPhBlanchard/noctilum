"""
Carte du ciel interactive — Plotly.

Point d'entrée unique : build_sky_chart().
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

import pandas as pd
import plotly.graph_objects as go

from engines.astro_engine import Observer
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
_PLANET_CLR    = '#FFD700'   # planètes
_SUN_CLR       = '#FFF5A0'   # Soleil
_MOON_CLR      = '#E8E8D0'   # Lune
_LABEL_CLR     = '#FFFFFF'   # labels planètes

# ---------------------------------------------------------------------------
# Constantes de mise en page
# ---------------------------------------------------------------------------

_MARGIN_PX = 20          # doit correspondre à projection._MARGIN
_PARALLELS  = (30, 60)   # altitudes des cercles de parallèles

_CARDINALS = (
    (0,   'N'),  (45,  'NE'), (90,  'E'),  (135, 'SE'),
    (180, 'S'),  (225, 'SO'), (270, 'O'),  (315, 'NO'),
)

_PLANET_NAMES = frozenset(
    {'Mercure', 'Vénus', 'Mars', 'Jupiter', 'Saturne', 'Uranus', 'Neptune'}
)

_CONST_LINE_COLOR  = 'rgba(80, 100, 180, 0.35)'
_CONST_BOUND_COLOR = 'rgba(60,  80, 130, 0.22)'
_ECLIPTIC_COLOR    = 'rgba(255, 210, 60, 0.55)'
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

    # Points cardinaux
    for az_deg, label in _CARDINALS:
        az_rad = math.radians(az_deg)
        x = cx + label_r * math.sin(az_rad)
        y = cy - label_r * math.cos(az_rad)
        principal = label in ('N', 'E', 'S', 'O')
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
            line=dict(color=_CONST_LINE_COLOR, width=0.8),
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
            line=dict(color=_CONST_BOUND_COLOR, width=0.7, dash='dot'),
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
    xs, ys, colors, sizes = [], [], [], []
    custom: list[tuple] = []

    for _, row in stars_df.iterrows():
        xy = altaz_to_xy(float(row['alt_deg']), float(row['az_deg']), width, height)
        if xy is None:
            continue
        x, y = xy
        opacity   = magnitude_to_opacity(float(row['magnitude']))
        color_hex = spectral_color(str(row['spectral_type']))

        xs.append(x)
        ys.append(y)
        colors.append(_rgba(color_hex, opacity))
        sizes.append(magnitude_to_size(float(row['magnitude'])))
        custom.append((
            row['name'],
            float(row['magnitude']),
            float(row['alt_deg']),
            float(row['az_deg']),
        ))

    return go.Scatter(
        x=xs, y=ys,
        mode='markers',
        marker=dict(color=colors, size=sizes, line=dict(width=0)),
        customdata=custom,
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
    size = 16 if (mag is not None and mag < 0) else 12
    return go.Scatter(
        x=[x], y=[y],
        mode='markers+text',
        marker=dict(
            symbol='circle-cross',
            size=size,
            color=_PLANET_CLR,
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


def _planet_traces(planets_list: list[dict], width: int, height: int) -> list[go.Scatter]:
    traces: list[go.Scatter] = []

    for body in planets_list:
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
            traces.append(_unicode_body_trace(
                x, y, '☀', _SUN_CLR, 24, name, alt, az, mag))
        elif name == 'Lune':
            traces.append(_unicode_body_trace(
                x, y, '●', _MOON_CLR, 20, name, alt, az, mag))
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
    "show_ecliptic":     False,
    "show_grid":         False,
    "show_messier":      False,
}


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


def build_sky_chart(
    stars_df: pd.DataFrame,
    planets_list: list[dict],
    observer: Observer,
    t: Optional[datetime] = None,
    width: int = 800,
    height: int = 800,
    options: Optional[dict[str, bool]] = None,
    messier_df: Optional[pd.DataFrame] = None,
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

    # Grille céleste (couche la plus basse)
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

    # Objets de Messier
    if opts["show_messier"] and messier_df is not None and not messier_df.empty:
        for tr in _messier_traces(messier_df, width, height):
            fig.add_trace(tr)

    # Planètes
    if opts["show_planets"]:
        for trace in _planet_traces(planets_list, width, height):
            fig.add_trace(trace)

    fig.update_layout(
        width=width,
        height=height,
        paper_bgcolor=_BG_OUTER,
        plot_bgcolor=_BG_OUTER,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(
            range=[0, width],
            visible=False,
            showgrid=False,
            zeroline=False,
            fixedrange=True,
        ),
        yaxis=dict(
            range=[height, 0],    # y croît vers le bas → nord en haut du disque
            visible=False,
            showgrid=False,
            zeroline=False,
            scaleanchor='x',
            scaleratio=1,
            fixedrange=True,
        ),
        shapes=_make_shapes(cx, cy, chart_r),
        annotations=_make_annotations(cx, cy, chart_r),
        showlegend=False,
        hovermode='closest',
    )

    return fig
