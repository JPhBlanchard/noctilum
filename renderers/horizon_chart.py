"""
Vue horizon panoramique — projection équirectangulaire.
X = azimut, Y = altitude. Horizon en bas, zénith en haut.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

import pandas as pd
import plotly.graph_objects as go

from engines.astro_engine import Observer
from engines.projection import magnitude_to_opacity, magnitude_to_size
from engines.star_catalog import spectral_color

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

_BG_SKY           = '#050510'
_BG_GROUND        = '#141008'
_HORIZON_CLR      = '#445566'
_GRID_LINE_CLR    = 'rgba(55, 75, 105, 0.40)'
_GRID_LABEL_CLR   = '#445566'
_CARDINAL_CLR     = '#8899aa'
_PLANET_CLR       = '#FFD700'
_SUN_CLR          = '#FFF5A0'
_MOON_CLR         = '#E8E8D0'
_LABEL_CLR        = '#FFFFFF'
_CONST_LINE_COLOR  = 'rgba(80, 100, 180, 0.40)'
_CONST_BOUND_COLOR = 'rgba(60,  80, 130, 0.22)'
_ECLIPTIC_COLOR    = 'rgba(255, 210, 60, 0.55)'
_GRID_COLOR        = 'rgba(80, 120, 200, 0.55)'

_PLANET_NAMES = frozenset(
    {'Mercure', 'Vénus', 'Mars', 'Jupiter', 'Saturne', 'Uranus', 'Neptune'}
)

_CARDINAL_MAP = {
    0: 'N', 30: 'NNE', 45: 'NE', 60: 'ENE',
    90: 'E', 120: 'ESE', 135: 'SE', 150: 'SSE',
    180: 'S', 210: 'SSO', 225: 'SO', 240: 'OSO',
    270: 'O', 300: 'ONO', 315: 'NO', 330: 'NNO',
}

# ---------------------------------------------------------------------------
# Projection équirectangulaire
# ---------------------------------------------------------------------------

def _daz(az: float, az_center: float) -> float:
    """Différence azimutale normalisée dans [-180, 180]."""
    return ((az - az_center + 180.0) % 360.0) - 180.0


def _project(
    alt: float,
    az: float,
    az_center: float,
    az_fov: float,
    alt_min: float,
    alt_max: float,
    width: int,
    height: int,
    clip: bool = True,
) -> Optional[tuple[float, float]]:
    """
    Projection équirectangulaire (alt, az) → (x_px, y_px).
    clip=True : retourne None si hors du champ visible.
    clip=False : projette hors-champ (Plotly clippe aux axes).
    """
    d = _daz(az, az_center)
    if clip and (abs(d) > az_fov / 2 + 0.5 or alt < alt_min - 0.5 or alt > alt_max + 0.5):
        return None
    x = (d / (az_fov / 2) + 1.0) * (width / 2.0)
    y = height - ((alt - alt_min) / (alt_max - alt_min)) * height
    return x, y


def _rgba(hex_color: str, alpha: float) -> str:
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f'rgba({r},{g},{b},{alpha:.3f})'


def _horizon_y(alt_min: float, alt_max: float, height: int) -> float:
    """Ordonnée en pixels de la ligne d'horizon."""
    return height - ((0.0 - alt_min) / (alt_max - alt_min)) * height

# ---------------------------------------------------------------------------
# Fond, grille, annotations
# ---------------------------------------------------------------------------

def _make_shapes(
    width: int,
    height: int,
    alt_min: float,
    alt_max: float,
) -> list[dict]:
    shapes = []
    hy = _horizon_y(alt_min, alt_max, height)

    # Fond ciel
    shapes.append(dict(
        type='rect', x0=0, y0=0, x1=width, y1=height,
        fillcolor=_BG_SKY, line=dict(width=0), layer='below',
    ))

    # Sol (sous l'horizon)
    if alt_min < 0:
        shapes.append(dict(
            type='rect', x0=0, y0=hy, x1=width, y1=height,
            fillcolor=_BG_GROUND, line=dict(width=0), layer='below',
        ))

    # Lignes d'altitude (tous les 15°)
    for alt_tick in range(0, int(alt_max) + 1, 15):
        if alt_tick < alt_min:
            continue
        y_tick = height - ((alt_tick - alt_min) / (alt_max - alt_min)) * height
        shapes.append(dict(
            type='line', x0=0, y0=y_tick, x1=width, y1=y_tick,
            line=dict(color=_GRID_LINE_CLR, width=0.8, dash='dot'),
            layer='below',
        ))

    # Ligne d'horizon (plus marquée)
    shapes.append(dict(
        type='line', x0=0, y0=hy, x1=width, y1=hy,
        line=dict(color=_HORIZON_CLR, width=1.5),
        layer='above',
    ))

    return shapes


def _make_annotations(
    az_center: float,
    az_fov: float,
    alt_min: float,
    alt_max: float,
    width: int,
    height: int,
) -> list[dict]:
    annotations = []
    hy = _horizon_y(alt_min, alt_max, height)
    az_left = az_center - az_fov / 2

    # Labels azimutaux sous l'horizon (tous les 30°)
    az_step = 30
    az_cur = math.ceil(az_left / az_step) * az_step
    while az_cur <= az_center + az_fov / 2:
        az_mod = int(az_cur % 360)
        label = _CARDINAL_MAP.get(az_mod, f'{az_mod}°')
        x_tick = (az_cur - az_left) / az_fov * width
        if 0 <= x_tick <= width:
            annotations.append(dict(
                x=x_tick, y=hy + 4,
                xref='x', yref='y',
                text=label,
                showarrow=False,
                font=dict(color=_CARDINAL_CLR, size=10),
                xanchor='center', yanchor='top',
            ))
        az_cur += az_step

    # Labels d'altitude à gauche
    for alt_tick in range(0, int(alt_max) + 1, 15):
        if alt_tick < alt_min:
            continue
        y_tick = height - ((alt_tick - alt_min) / (alt_max - alt_min)) * height
        label = 'Horiz.' if alt_tick == 0 else f'{alt_tick}°'
        clr   = _HORIZON_CLR if alt_tick == 0 else _GRID_LABEL_CLR
        annotations.append(dict(
            x=4, y=y_tick - 3,
            xref='x', yref='y',
            text=label,
            showarrow=False,
            font=dict(color=clr, size=8),
            xanchor='left', yanchor='bottom',
        ))

    return annotations

# ---------------------------------------------------------------------------
# Traces
# ---------------------------------------------------------------------------

def _project_altaz_curve(
    alts,
    azs,
    az_center: float,
    az_fov: float,
    alt_min: float,
    alt_max: float,
    width: int,
    height: int,
) -> tuple[list, list]:
    """
    Projette une courbe (alts, azs) en (xs, ys) Plotly pour la vue horizon.
    Insère des None aux coupures (horizon, discontinuité azimutale).
    """
    xs: list = []
    ys: list = []
    prev_d: Optional[float] = None

    for alt, az in zip(alts, azs):
        if alt < alt_min - 0.5:
            if xs and xs[-1] is not None:
                xs.append(None); ys.append(None)
            prev_d = None
            continue

        d = _daz(az, az_center)

        # Coupure si saut azimutaux > 60° (passage derrière l'observateur)
        if prev_d is not None and abs(d - prev_d) > 60.0:
            xs.append(None); ys.append(None)

        x = (d / (az_fov / 2) + 1.0) * (width / 2.0)
        y = height - ((alt - alt_min) / (alt_max - alt_min)) * height
        xs.append(x); ys.append(y)
        prev_d = d

    return xs, ys


def _stars_trace(
    stars_df: pd.DataFrame,
    az_center: float,
    az_fov: float,
    alt_min: float,
    alt_max: float,
    width: int,
    height: int,
) -> Optional[go.Scatter]:
    xs, ys, colors, sizes, custom = [], [], [], [], []

    for _, row in stars_df.iterrows():
        alt, az = float(row['alt_deg']), float(row['az_deg'])
        xy = _project(alt, az, az_center, az_fov, alt_min, alt_max, width, height)
        if xy is None:
            continue
        opacity = magnitude_to_opacity(float(row['magnitude']))
        xs.append(xy[0])
        ys.append(xy[1])
        colors.append(_rgba(spectral_color(str(row['spectral_type'])), opacity))
        sizes.append(magnitude_to_size(float(row['magnitude'])))
        custom.append((row['name'], float(row['magnitude']), alt, az))

    if not xs:
        return None

    return go.Scatter(
        x=xs, y=ys,
        mode='markers',
        marker=dict(color=colors, size=sizes, line=dict(width=0)),
        customdata=custom,
        hovertemplate=(
            '<b>%{customdata[0]}</b><br>'
            'Mag : %{customdata[1]:.1f}<br>'
            'Alt : %{customdata[2]:.1f}°  Az : %{customdata[3]:.1f}°'
            '<extra></extra>'
        ),
        name='Étoiles',
        showlegend=False,
    )


def _constellation_lines_trace(
    observer: Observer,
    t,
    az_center: float,
    az_fov: float,
    alt_min: float,
    alt_max: float,
    width: int,
    height: int,
) -> Optional[go.Scatter]:
    try:
        from engines.constellation_lines import get_constellation_altaz_segments
        segs = get_constellation_altaz_segments(observer, t)
        if not segs:
            return None

        xs, ys = [], []
        half = az_fov / 2 + 10.0   # marge pour inclure les segments qui croisent le bord

        for (alt1, az1), (alt2, az2) in segs:
            # Exclure si les deux points sont hors du champ élargi
            if abs(_daz(az1, az_center)) > half and abs(_daz(az2, az_center)) > half:
                continue
            # Projeter sans clipping — Plotly coupe aux limites des axes
            xy1 = _project(alt1, az1, az_center, az_fov, alt_min, alt_max, width, height, clip=False)
            xy2 = _project(alt2, az2, az_center, az_fov, alt_min, alt_max, width, height, clip=False)
            xs.extend([xy1[0], xy2[0], None])
            ys.extend([xy1[1], xy2[1], None])

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


def _constellation_labels_trace(
    observer: Observer,
    t,
    az_center: float,
    az_fov: float,
    alt_min: float,
    alt_max: float,
    width: int,
    height: int,
) -> Optional[go.Scatter]:
    try:
        from engines.constellation_lines import get_constellation_altaz_labels
        labels = get_constellation_altaz_labels(observer, t)
        if not labels:
            return None

        xs, ys, texts = [], [], []
        alt_floor = max(5.0, alt_min)
        for alt, az, name in labels:
            if alt < alt_floor:
                continue
            xy = _project(alt, az, az_center, az_fov, alt_min, alt_max, width, height)
            if xy is None:
                continue
            xs.append(xy[0])
            ys.append(xy[1])
            texts.append(name)

        if not xs:
            return None

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


def _planet_traces(
    planets_list: list[dict],
    az_center: float,
    az_fov: float,
    alt_min: float,
    alt_max: float,
    width: int,
    height: int,
) -> list[go.Scatter]:
    traces = []

    for body in planets_list:
        if not body.get('above_horizon'):
            continue
        alt, az = float(body['alt']), float(body['az'])
        xy = _project(alt, az, az_center, az_fov, alt_min, alt_max, width, height)
        if xy is None:
            continue
        x, y = xy
        name    = body['name']
        mag     = body.get('magnitude')
        mag_str = f'{mag:.1f}' if mag is not None else '—'
        tmpl    = (
            f'<b>{name}</b><br>'
            f'Mag : {mag_str}<br>'
            f'Alt : {alt:.1f}°  Az : {az:.1f}°'
            '<extra></extra>'
        )

        if name == 'Soleil':
            traces.append(go.Scatter(
                x=[x], y=[y],
                mode='markers+text',
                marker=dict(symbol='circle', size=24, color='rgba(0,0,0,0)', opacity=0),
                text=['☀'],
                textfont=dict(color=_SUN_CLR, size=24),
                textposition='middle center',
                name=name, hovertemplate=tmpl, showlegend=False,
            ))
        elif name == 'Lune':
            traces.append(go.Scatter(
                x=[x], y=[y],
                mode='markers+text',
                marker=dict(symbol='circle', size=20, color='rgba(0,0,0,0)', opacity=0),
                text=['●'],
                textfont=dict(color=_MOON_CLR, size=20),
                textposition='middle center',
                name=name, hovertemplate=tmpl, showlegend=False,
            ))
        elif name in _PLANET_NAMES:
            size = 16 if (mag is not None and mag < 0) else 12
            traces.append(go.Scatter(
                x=[x], y=[y],
                mode='markers+text',
                marker=dict(
                    symbol='circle-cross', size=size, color=_PLANET_CLR,
                    line=dict(color='rgba(255,255,255,0.35)', width=1),
                ),
                text=[name],
                textfont=dict(color=_LABEL_CLR, size=9),
                textposition='top center',
                name=name, hovertemplate=tmpl, showlegend=False,
            ))

    return traces


def _boundary_trace_h(
    observer: Observer,
    t,
    az_center: float,
    az_fov: float,
    alt_min: float,
    alt_max: float,
    width: int,
    height: int,
) -> Optional[go.Scatter]:
    try:
        from engines.constellation_lines import get_constellation_altaz_boundaries
        segs = get_constellation_altaz_boundaries(observer, t)
        if not segs:
            return None

        xs, ys = [], []
        half = az_fov / 2 + 10.0
        for (alt1, az1), (alt2, az2) in segs:
            if abs(_daz(az1, az_center)) > half and abs(_daz(az2, az_center)) > half:
                continue
            xy1 = _project(alt1, az1, az_center, az_fov, alt_min, alt_max, width, height, clip=False)
            xy2 = _project(alt2, az2, az_center, az_fov, alt_min, alt_max, width, height, clip=False)
            xs.extend([xy1[0], xy2[0], None])
            ys.extend([xy1[1], xy2[1], None])

        if not xs:
            return None

        return go.Scatter(
            x=xs, y=ys, mode='lines',
            line=dict(color=_CONST_BOUND_COLOR, width=0.7, dash='dot'),
            hoverinfo='skip', showlegend=False,
        )
    except Exception:
        return None


def _ecliptic_trace_h(
    observer: Observer,
    t,
    az_center: float,
    az_fov: float,
    alt_min: float,
    alt_max: float,
    width: int,
    height: int,
) -> Optional[go.Scatter]:
    try:
        from engines.sky_overlay import get_ecliptic_altaz
        alts, azs = get_ecliptic_altaz(observer, t)
        xs, ys = _project_altaz_curve(alts, azs, az_center, az_fov, alt_min, alt_max, width, height)
        if not xs:
            return None
        return go.Scatter(
            x=xs, y=ys, mode='lines',
            line=dict(color=_ECLIPTIC_COLOR, width=1.2),
            hoverinfo='skip', showlegend=False,
        )
    except Exception:
        return None


def _grid_trace_h(
    observer: Observer,
    t,
    az_center: float,
    az_fov: float,
    alt_min: float,
    alt_max: float,
    width: int,
    height: int,
) -> Optional[go.Scatter]:
    try:
        from engines.sky_overlay import get_celestial_grid_altaz
        segments = get_celestial_grid_altaz(observer, t)
        xs_all, ys_all = [], []
        for alts, azs in segments:
            xs, ys = _project_altaz_curve(alts, azs, az_center, az_fov, alt_min, alt_max, width, height)
            if xs:
                xs_all.extend(xs + [None])
                ys_all.extend(ys + [None])
        if not xs_all:
            return None
        return go.Scatter(
            x=xs_all, y=ys_all, mode='lines',
            line=dict(color=_GRID_COLOR, width=1.5),
            hoverinfo='skip', showlegend=False,
        )
    except Exception:
        return None


def _sh_clip_viewport_h(
    verts: list,
    az_center: float,
    az_fov: float,
    alt_min: float,
    alt_max: float,
) -> list[tuple[float, float]]:
    """
    Sutherland-Hodgman 4 plans (gauche/droite azimut + bas/haut altitude) pour la vue paysage.
    Travaille en espace (daz, alt) ; gère le wrap azimuthal en déroulant les angles.
    Retourne [(alt, az), ...] clippé au viewport.
    """
    if len(verts) < 3:
        return []
    half = az_fov / 2.0

    # Normalise le premier sommet en [-180, 180] par rapport à az_center,
    # puis déroule les suivants pour éviter les sauts > 180° entre voisins.
    # Sans cette normalisation, les polygones croisant N (0°/360°) ont leurs
    # daz autour de 300-400 et ne sont jamais clippés correctement.
    first_alt, first_az = verts[0]
    first_daz = ((first_az - az_center + 180) % 360) - 180
    poly: list[tuple[float, float]] = [(first_daz, first_alt)]
    prev_daz = first_daz

    for alt, az in verts[1:]:
        curr_daz = ((az - az_center + 180) % 360) - 180
        diff = curr_daz - prev_daz
        if diff > 180:
            curr_daz -= 360
        elif diff < -180:
            curr_daz += 360
        poly.append((curr_daz, alt))
        prev_daz = curr_daz

    def _clip_one(polygon: list, inside, t_calc) -> list:
        if not polygon:
            return []
        out = []
        n = len(polygon)
        for i in range(n):
            curr = polygon[i]
            prev = polygon[(i - 1) % n]
            ci, pi = inside(curr), inside(prev)
            if ci:
                if not pi:
                    tc = t_calc(prev, curr)
                    out.append((prev[0] + tc * (curr[0] - prev[0]),
                                prev[1] + tc * (curr[1] - prev[1])))
                out.append(curr)
            elif pi:
                tc = t_calc(prev, curr)
                out.append((prev[0] + tc * (curr[0] - prev[0]),
                            prev[1] + tc * (curr[1] - prev[1])))
        return out

    # Plan gauche : daz >= -half
    poly = _clip_one(poly, lambda p: p[0] >= -half,
                     lambda p1, p2: (-half - p1[0]) / (p2[0] - p1[0]))
    # Plan droit : daz <= +half
    poly = _clip_one(poly, lambda p: p[0] <= half,
                     lambda p1, p2: (half - p1[0]) / (p2[0] - p1[0]))
    # Plan bas : alt >= alt_min
    poly = _clip_one(poly, lambda p: p[1] >= alt_min,
                     lambda p1, p2: (alt_min - p1[1]) / (p2[1] - p1[1]))
    # Plan haut : alt <= alt_max
    poly = _clip_one(poly, lambda p: p[1] <= alt_max,
                     lambda p1, p2: (alt_max - p1[1]) / (p2[1] - p1[1]))

    if len(poly) < 3:
        return []
    # Reconvertir en (alt, az)
    return [(alt, (az_center + daz) % 360) for daz, alt in poly]


def _milkyway_traces_h(
    observer: Observer,
    t,
    az_center: float,
    az_fov: float,
    alt_min: float,
    alt_max: float,
    width: int,
    height: int,
) -> list[go.Scatter]:
    """Voie Lactée image-réelle (Stellarium) — vue paysage."""
    try:
        from engines.milky_way import get_milky_way_scatter, get_galactic_center_altaz
        mw = get_milky_way_scatter(
            observer, t, mode="landscape",
            width=width, height=height,
            az_center=az_center, az_fov=az_fov,
            alt_min=alt_min, alt_max=alt_max,
        )
        traces = []
        if mw["x"]:
            traces.append(go.Scatter(
                x=mw["x"], y=mw["y"],
                mode="markers",
                marker=dict(size=mw["size"], color=mw["rgba"]),
                hoverinfo="skip",
                showlegend=False,
            ))
        gc_alt, gc_az = get_galactic_center_altaz(observer, t)
        gc_xy = _project(gc_alt, gc_az, az_center, az_fov, alt_min, alt_max, width, height)
        if gc_xy:
            traces.append(go.Scatter(
                x=[gc_xy[0]], y=[gc_xy[1]],
                mode="markers",
                marker=dict(symbol="cross-thin", size=14, color="red",
                            line=dict(color="red", width=2)),
                hovertemplate="Centre galactique<br>Alt %.1f°  Az %.1f°<extra></extra>" % (gc_alt, gc_az),
                showlegend=False,
            ))
        return traces
    except Exception:
        return []


def _messier_traces(
    messier_df: pd.DataFrame,
    az_center: float,
    az_fov: float,
    alt_min: float,
    alt_max: float,
    width: int,
    height: int,
) -> list[go.Scatter]:
    if messier_df is None or messier_df.empty:
        return []

    from engines.messier_catalog import TYPE_INFO, _DEFAULT_TYPE
    traces = []

    for typ, grp in messier_df.groupby('type'):
        sym, color = grp['symbol'].iloc[0], grp['color'].iloc[0]
        _, _, type_fr = TYPE_INFO.get(typ, _DEFAULT_TYPE)
        xs, ys, labels, customs = [], [], [], []

        for _, row in grp.iterrows():
            xy = _project(
                row['alt_deg'], row['az_deg'],
                az_center, az_fov, alt_min, alt_max, width, height,
            )
            if xy is None:
                continue
            xs.append(xy[0])
            ys.append(xy[1])
            labels.append(row['label'])
            customs.append((row['label'], row['name'], row['mag'],
                            row['alt_deg'], row['az_deg']))

        if not xs:
            continue

        traces.append(go.Scatter(
            x=xs, y=ys,
            mode='markers+text',
            marker=dict(
                symbol=sym, size=12, color=color, opacity=0.9,
                line=dict(width=1.5, color=color),
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
    "show_milkyway":     False,
}


def build_horizon_chart(
    stars_df: pd.DataFrame,
    planets_list: list[dict],
    observer: Observer,
    t: Optional[datetime] = None,
    az_center: float = 180.0,
    az_fov: float = 120.0,
    alt_min: float = -5.0,
    alt_max: float = 90.0,
    width: int = 1200,
    height: int = 980,
    options: Optional[dict[str, bool]] = None,
    messier_df: Optional[pd.DataFrame] = None,
) -> go.Figure:
    """
    Vue horizon panoramique en projection équirectangulaire.

    Parameters
    ----------
    az_center : azimut central du champ (degrés, 0=N / 90=E / 180=S / 270=O)
    az_fov    : champ horizontal total en degrés (défaut 120°)
    alt_min   : altitude minimale affichée (peut être légèrement négatif)
    alt_max   : altitude maximale affichée
    """
    opts = {**_DEFAULT_OPTIONS, **(options or {})}
    fig  = go.Figure()

    # Ancre invisible — fixe l'espace de coordonnées à [0, width] × [0, height]
    fig.add_trace(go.Scatter(
        x=[0, width], y=[0, height],
        mode='markers',
        marker=dict(opacity=0, size=0.1),
        hoverinfo='skip',
        showlegend=False,
    ))

    if opts['show_milkyway']:
        for tr in _milkyway_traces_h(observer, t, az_center, az_fov, alt_min, alt_max, width, height):
            fig.add_trace(tr)

    if opts['show_grid']:
        tr = _grid_trace_h(observer, t, az_center, az_fov, alt_min, alt_max, width, height)
        if tr is not None:
            fig.add_trace(tr)

    if opts['show_const_bounds']:
        tr = _boundary_trace_h(observer, t, az_center, az_fov, alt_min, alt_max, width, height)
        if tr is not None:
            fig.add_trace(tr)

    if opts['show_ecliptic']:
        tr = _ecliptic_trace_h(observer, t, az_center, az_fov, alt_min, alt_max, width, height)
        if tr is not None:
            fig.add_trace(tr)

    if opts['show_const_lines']:
        tr = _constellation_lines_trace(
            observer, t, az_center, az_fov, alt_min, alt_max, width, height)
        if tr is not None:
            fig.add_trace(tr)

    if opts['show_const_names']:
        tr = _constellation_labels_trace(
            observer, t, az_center, az_fov, alt_min, alt_max, width, height)
        if tr is not None:
            fig.add_trace(tr)

    if opts['show_stars'] and not stars_df.empty:
        tr = _stars_trace(stars_df, az_center, az_fov, alt_min, alt_max, width, height)
        if tr is not None:
            fig.add_trace(tr)

    if opts['show_messier']:
        for tr in _messier_traces(messier_df, az_center, az_fov, alt_min, alt_max, width, height):
            fig.add_trace(tr)

    if opts['show_planets']:
        for tr in _planet_traces(planets_list, az_center, az_fov, alt_min, alt_max, width, height):
            fig.add_trace(tr)

    fig.update_layout(
        width=width,
        height=height,
        paper_bgcolor=_BG_SKY,
        plot_bgcolor=_BG_SKY,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(
            range=[0, width],
            visible=False, showgrid=False, zeroline=False, fixedrange=True,
        ),
        yaxis=dict(
            range=[height, 0],
            visible=False, showgrid=False, zeroline=False, fixedrange=True,
        ),
        shapes=_make_shapes(width, height, alt_min, alt_max),
        annotations=_make_annotations(az_center, az_fov, alt_min, alt_max, width, height),
        showlegend=False,
        hovermode='closest',
    )

    return fig
