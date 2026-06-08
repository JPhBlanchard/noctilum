"""
Vue oculaire circulaire — vraie projection gnomique (plan tangent local).

Propriété clé : les grands cercles (méridiens AR, écliptique) apparaissent
comme des droites dans cette projection.

Convention écran :
  up    = +altitude (vers le zénith)
  right = +azimut   (Est, azimut croissant)
"""

from __future__ import annotations

import base64
import math as _math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timezone

_BG = "#000000"

_PLANET_COLOR = {
    'Mercure': '#b8a898',
    'Vénus':   '#e8c87a',
    'Mars':    '#c1440e',
    'Jupiter': '#c88b3a',
    'Saturne': '#e8d5a0',
    'Uranus':  '#7de8d8',
    'Neptune': '#4b70dd',
    'Pluton':  '#b8956a',
}


# ── Projection gnomique ───────────────────────────────────────────────────────

def _gnomonic(
    alts: np.ndarray,
    azs:  np.ndarray,
    alt_c: float,
    az_c:  float,
    half:  float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Vraie projection gnomique (tangentielle).
    Les grands cercles (méridiens AR, écliptique) apparaissent comme des droites.

    Retourne (xn, yn, dist_n) normalisés : dist_n=1 correspond au bord du FOV.
    Pixels : xpx = cx + xn*R, ypx = cy - yn*R.
    """
    a_r  = np.radians(np.asarray(alts, dtype=float))
    az_r = np.radians(np.asarray(azs,  dtype=float))
    a_c  = float(np.radians(alt_c))
    azc  = float(np.radians(az_c))
    daz  = az_r - azc

    denom = np.sin(a_c) * np.sin(a_r) + np.cos(a_c) * np.cos(a_r) * np.cos(daz)
    safe  = np.where(denom > 1e-6, denom, 1e-6)

    xg =  np.cos(a_r) * np.sin(daz) / safe
    yg = (np.cos(a_c) * np.sin(a_r) - np.sin(a_c) * np.cos(a_r) * np.cos(daz)) / safe

    tan_h = np.tan(np.radians(half))
    xn = xg / tan_h
    yn = yg / tan_h
    return xn, yn, np.sqrt(xn ** 2 + yn ** 2)


def _ep_xy(
    alts: np.ndarray,
    azs:  np.ndarray,
    alt_c: float, az_c: float,
    half: float, R: float, cx: float, cy: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Wrapper gnomique → pixels. dist_n=1 = bord du FOV."""
    xn, yn, dn = _gnomonic(alts, azs, alt_c, az_c, half)
    return cx + xn * R, cy - yn * R, dn


def _segment_traces(
    segments: list,
    alt_c: float, az_c: float,
    half: float, R: float, cx: float, cy: float,
    clip: float = 1.8,
) -> tuple[list, list]:
    """
    Projette des segments [((alt1,az1),(alt2,az2))] dans l'oculaire (gnomique).
    clip : distance normalisée au-delà de laquelle un point est exclu.
    """
    if not segments:
        return [], []
    a1 = np.array([s[0][0] for s in segments])
    az1 = np.array([s[0][1] for s in segments])
    a2 = np.array([s[1][0] for s in segments])
    az2 = np.array([s[1][1] for s in segments])

    xn1, yn1, d1 = _gnomonic(a1, az1, alt_c, az_c, half)
    xn2, yn2, d2 = _gnomonic(a2, az2, alt_c, az_c, half)

    mask = (d1 <= clip) | (d2 <= clip)
    xs, ys = [], []
    for i in np.where(mask)[0]:
        xs += [cx + xn1[i]*R, cx + xn2[i]*R, None]
        ys += [cy - yn1[i]*R, cy - yn2[i]*R, None]
    return xs, ys


# ── Utilitaires ───────────────────────────────────────────────────────────────

def _mag_to_size(mag: float) -> float:
    return float(np.clip(8.0 - mag * 0.9, 0.8, 11.0))


def _circle(cx: float, cy: float, r: float, n: int = 361):
    θ = np.linspace(0, 2 * np.pi, n)
    return (cx + r * np.cos(θ)).tolist(), (cy + r * np.sin(θ)).tolist()


# ── Figure principale ─────────────────────────────────────────────────────────

def build_eyepiece_chart(
    target_alt: float,
    target_az: float,
    target_label: str,
    stars_df: pd.DataFrame,
    fov_deg: float = 15.0,
    width: int = 750,
    height: int = 750,
    options: dict | None = None,
    planets_data: list | None = None,
    messier_df: pd.DataFrame | None = None,
    observer=None,
    t=None,
    satellites_data: list | None = None,
) -> go.Figure:
    opts  = options or {}
    R     = min(width, height) / 2.0 - 50
    cx    = width  / 2.0
    cy    = height / 2.0
    half  = fov_deg / 2.0

    fig = go.Figure()
    fig.update_layout(
        width=width, height=height,
        paper_bgcolor=_BG,
        plot_bgcolor=_BG,
        margin=dict(l=40, r=40, t=50, b=40),
        xaxis=dict(visible=False, range=[0, width],  fixedrange=False),
        yaxis=dict(visible=False, range=[0, height], scaleanchor="x", fixedrange=False),
        showlegend=False,
    )

    # ── Fond du disque (bord seulement — pas de fill pour ne pas couvrir les traces)
    xc, yc = _circle(cx, cy, R)
    fig.add_trace(go.Scatter(
        x=xc, y=yc, mode="lines",
        line=dict(color="#2a2a4a", width=1.5),
        hoverinfo="skip", showlegend=False,
    ))

    # ── Anneau de référence (50 % du FOV) ─────────────────────────────────────
    xh, yh = _circle(cx, cy, R * 0.5)
    fig.add_trace(go.Scatter(
        x=xh, y=yh, mode="lines",
        line=dict(color="#151528", width=0.8),
        hoverinfo="skip", showlegend=False,
    ))

    # ── Limites de constellations ─────────────────────────────────────────────
    if opts.get("show_const_bounds", False) and observer is not None:
        from engines.constellation_lines import get_constellation_altaz_boundaries
        xs, ys = _segment_traces(
            get_constellation_altaz_boundaries(observer, t),
            target_alt, target_az, half, R, cx, cy,
        )
        if xs:
            fig.add_trace(go.Scatter(
                x=xs, y=ys, mode="lines",
                line=dict(color="#253525", width=0.7, dash="dot"),
                hoverinfo="skip", showlegend=False,
            ))

    # ── Plan de l'écliptique ──────────────────────────────────────────────────
    if opts.get("show_ecliptic", False) and observer is not None:
        from engines.sky_overlay import get_ecliptic_altaz
        ec_alts, ec_azs = get_ecliptic_altaz(observer, t, step_deg=1)
        xpx, ypx, dn = _ep_xy(ec_alts, ec_azs, target_alt, target_az, half, R, cx, cy)
        ec_x, ec_y = [], []
        prev_in = False
        for i in range(len(xpx)):
            in_fov = dn[i] <= 1.8 and ec_alts[i] > 0
            if in_fov:
                if not prev_in:
                    ec_x.append(None); ec_y.append(None)
                ec_x.append(float(xpx[i])); ec_y.append(float(ypx[i]))
            prev_in = in_fov
        if any(v is not None for v in ec_x):
            fig.add_trace(go.Scatter(
                x=ec_x, y=ec_y, mode="lines",
                line=dict(color="#665500", width=1.2),
                hoverinfo="skip", showlegend=False,
            ))

    # ── Lignes de constellations ──────────────────────────────────────────────
    if opts.get("show_const_lines", False) and observer is not None:
        from engines.constellation_lines import get_constellation_altaz_segments
        xs, ys = _segment_traces(
            get_constellation_altaz_segments(observer, t),
            target_alt, target_az, half, R, cx, cy,
        )
        if xs:
            fig.add_trace(go.Scatter(
                x=xs, y=ys, mode="lines",
                line=dict(color="#1e3a4a", width=1.0),
                hoverinfo="skip", showlegend=False,
            ))

    # ── Voie Lactée ───────────────────────────────────────────────────────────
    if opts.get("show_milkyway", False) and observer is not None:
        from engines.milky_way import (_get_grid_points, _compute_altaz,
                                       _display_lum, _lum_to_rgba)
        l_m, b_m, lum = _get_grid_points()
        alts_mw, azs_mw = _compute_altaz(observer, t, l_m, b_m)
        vis = alts_mw > 0.0
        if vis.any():
            xpx, ypx, dn = _ep_xy(
                alts_mw[vis], azs_mw[vis], target_alt, target_az, half, R, cx, cy
            )
            mask = dn <= 1.0
            if mask.any():
                lum_d = _display_lum(lum[vis][mask])
                fig.add_trace(go.Scatter(
                    x=xpx[mask].tolist(), y=ypx[mask].tolist(),
                    mode="markers",
                    marker=dict(size=(1.0 + lum_d).tolist(),
                                color=_lum_to_rgba(lum_d)),
                    hoverinfo="skip", showlegend=False,
                ))

    # ── Objets de Messier ─────────────────────────────────────────────────────
    if opts.get("show_messier", False) and messier_df is not None and not messier_df.empty:
        xpx, ypx, dn = _ep_xy(
            messier_df["alt_deg"].values, messier_df["az_deg"].values,
            target_alt, target_az, half, R, cx, cy,
        )
        mask = dn <= 1.0
        if mask.any():
            fig.add_trace(go.Scatter(
                x=xpx[mask].tolist(), y=ypx[mask].tolist(),
                mode="markers+text",
                marker=dict(
                    symbol=[s for s, ok in zip(messier_df["symbol"].values, mask) if ok],
                    color =[c for c, ok in zip(messier_df["color"].values,  mask) if ok],
                    size=10, opacity=0.85,
                    line=dict(width=1.0, color="rgba(0,0,0,0.4)"),
                ),
                text=[lb for lb, ok in zip(messier_df["label"].values, mask) if ok],
                textposition="top center",
                textfont=dict(color="#aaaacc", size=9),
                customdata=[(lb, mg) for lb, mg, ok in zip(
                    messier_df["label"].values, messier_df["mag"].values, mask) if ok],
                hovertemplate="<b>%{customdata[0]}</b> · mag %{customdata[1]:.1f}<extra></extra>",
                showlegend=False,
            ))

    # ── Étoiles ───────────────────────────────────────────────────────────────
    if opts.get("show_stars", True) and not stars_df.empty:
        xpx, ypx, dn = _ep_xy(
            stars_df["alt_deg"].values, stars_df["az_deg"].values,
            target_alt, target_az, half, R, cx, cy,
        )
        mask = dn <= 1.0
        if mask.any():
            mags  = stars_df["magnitude"].values[mask]
            names = stars_df["name"].values[mask]
            alts  = stars_df["alt_deg"].values[mask]
            azs   = stars_df["az_deg"].values[mask]
            fig.add_trace(go.Scatter(
                x=xpx[mask].tolist(), y=ypx[mask].tolist(),
                mode="markers",
                marker=dict(
                    size=np.vectorize(_mag_to_size)(mags).tolist(),
                    color="white", opacity=0.92,
                    line=dict(width=0),
                ),
                customdata=list(zip(names, mags, alts, azs)),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Mag %{customdata[1]:.1f}<br>"
                    "Alt %{customdata[2]:.2f}°  Az %{customdata[3]:.2f}°"
                    "<extra></extra>"
                ),
                showlegend=False,
            ))

    # ── Planètes ──────────────────────────────────────────────────────────────
    _moon_ep: dict | None = None   # infos Lune pour le layout image
    _sun_ep:  dict | None = None   # infos Soleil pour le layout image
    if opts.get("show_planets", True) and planets_data:
        for p in sorted(planets_data, key=lambda b: b.get('distance_au') or 0, reverse=True):
            p_alt, p_az = float(p["alt"]), float(p["az"])
            xn, yn, dn = _gnomonic(
                np.array([p_alt]), np.array([p_az]),
                target_alt, target_az, half,
            )
            if dn[0] > 1.0:
                continue
            xpp = float(cx + xn[0] * R)
            ypp = float(cy - yn[0] * R)
            mag = p.get("magnitude")

            if p["name"] == "Lune":
                # Taille proportionnelle au diamètre apparent dans ce FOV
                # R pixels = half degrés → taille réelle = R * diam_deg / half
                diam_arcsec = p.get("ang_diam_arcsec") or 1842.0
                diam_deg    = diam_arcsec / 3600.0
                moon_px     = max(8, min(int(1.9 * R), int(R * diam_deg / half)))
                _moon_ep    = {"xpp": xpp, "ypp": ypp, "moon_px": moon_px, "p": p}
                # Marqueur invisible — sert de zone de capture hover
                fig.add_trace(go.Scatter(
                    x=[xpp], y=[ypp],
                    mode="markers",
                    marker=dict(symbol="circle", size=moon_px,
                                color="rgba(0,0,0,0)", opacity=0),
                    hovertemplate=(
                        "<b>Lune</b><br>"
                        f"Alt {p_alt:.1f}°  Az {p_az:.1f}°"
                        + (f"<br>Mag {mag:.1f}" if mag is not None else "")
                        + "<extra></extra>"
                    ),
                    showlegend=False,
                ))
                continue

            if p["name"] == "Soleil":
                diam_arcsec = p.get("ang_diam_arcsec") or 1919.0
                diam_deg    = diam_arcsec / 3600.0
                sun_px      = max(8, min(int(1.9 * R), int(R * diam_deg / half)))
                _sun_ep     = {"xpp": xpp, "ypp": ypp, "sun_px": sun_px}
                fig.add_trace(go.Scatter(
                    x=[xpp], y=[ypp],
                    mode="markers",
                    marker=dict(symbol="circle", size=sun_px,
                                color="rgba(0,0,0,0)", opacity=0),
                    hovertemplate=(
                        "<b>Soleil</b><br>"
                        f"Alt {p_alt:.1f}°  Az {p_az:.1f}°"
                        + (f"<br>Mag {mag:.1f}" if mag is not None else "")
                        + "<extra></extra>"
                    ),
                    showlegend=False,
                ))
                continue

            col = _PLANET_COLOR.get(p["name"], "#ffcc88")
            sz  = float(np.clip(10.0 - (mag or 0) * 0.8, 6.0, 18.0))
            ring_P = p.get("ring_P_deg")
            ring_B = p.get("ring_B_deg")
            ring_q = float(p.get("parallactic_angle_deg") or 0.0)

            if p["name"] == "Saturne" and ring_P is not None and ring_B is not None:
                # Vue oculaire : haut = altitude, référence = zénith → correction par q
                ring_pa_rad = _math.radians(float(ring_P) - ring_q + 90.0)
                semi_major = 12.0
                semi_minor = max(1.0, semi_major * abs(_math.sin(_math.radians(float(ring_B)))))
                maj_dx =  _math.sin(ring_pa_rad)
                maj_dy = -_math.cos(ring_pa_rad)
                min_dx =  _math.cos(ring_pa_rad)
                min_dy =  _math.sin(ring_pa_rad)

                def _ep_arc(t0, t1):
                    n = 36
                    xs2, ys2 = [], []
                    for i in range(n + 1):
                        θ = t0 + (t1 - t0) * i / n
                        xs2.append(xpp + semi_major * _math.cos(θ) * maj_dx + semi_minor * _math.sin(θ) * min_dx)
                        ys2.append(ypp + semi_major * _math.cos(θ) * maj_dy + semi_minor * _math.sin(θ) * min_dy)
                    return xs2, ys2

                if float(ring_B) >= 0:
                    bx, by = _ep_arc(_math.pi, 2 * _math.pi)
                    fx, fy = _ep_arc(0.0, _math.pi)
                else:
                    bx, by = _ep_arc(0.0, _math.pi)
                    fx, fy = _ep_arc(_math.pi, 2 * _math.pi)

                fig.add_trace(go.Scatter(
                    x=bx, y=by, mode="lines",
                    line=dict(color="rgba(200,170,106,0.35)", width=1.2),
                    hoverinfo="skip", showlegend=False,
                ))

            # Disque planète en coordonnées data → zoome avec la roulette
            r_disk = sz / 2.0
            _n = 36
            _disk_xs = [xpp + r_disk * _math.cos(2 * _math.pi * i / _n) for i in range(_n + 1)]
            _disk_ys = [ypp + r_disk * _math.sin(2 * _math.pi * i / _n) for i in range(_n + 1)]
            _htmpl = (
                f"<b>{p['name']}</b><br>"
                f"Alt {p_alt:.1f}°  Az {p_az:.1f}°"
                + (f"<br>Mag {mag:.1f}" if mag is not None else "")
                + "<extra></extra>"
            )
            fig.add_trace(go.Scatter(
                x=_disk_xs, y=_disk_ys,
                mode="lines",
                fill="toself",
                fillcolor=col,
                line=dict(color="rgba(255,255,255,0.27)", width=0.8),
                name=p["name"],
                hovertemplate=_htmpl,
                showlegend=False,
            ))
            # Label texte (position fixe au-dessus du disque)
            fig.add_trace(go.Scatter(
                x=[xpp], y=[ypp],
                mode="text",
                text=[p["name"]],
                textposition="top center",
                textfont=dict(color=col, size=10),
                hoverinfo="skip",
                showlegend=False,
            ))

            if p["name"] == "Saturne" and ring_P is not None and ring_B is not None:
                fig.add_trace(go.Scatter(
                    x=fx, y=fy, mode="lines",
                    line=dict(color="rgba(200,170,106,0.85)", width=1.5),
                    hoverinfo="skip", showlegend=False,
                ))

    # ── Images Soleil + Lune (une seule mise à jour layout) ──────────────────
    _ep_images = []

    if _sun_ep is not None:
        from engines.sun_engine import render_sun_image
        sun_px   = _sun_ep["sun_px"]
        render_s = max(64, min(320, sun_px))
        png = render_sun_image(size=render_s)
        b64 = base64.b64encode(png).decode()
        _ep_images.append(dict(
            source=f"data:image/png;base64,{b64}",
            x=_sun_ep["xpp"], y=_sun_ep["ypp"],
            sizex=sun_px, sizey=sun_px,
            xanchor="center", yanchor="middle",
            xref="x", yref="y",
            layer="above",
        ))

    if _moon_ep is not None and observer is not None:
        from engines.moon_engine import render_moon_image
        xpp     = _moon_ep["xpp"]
        ypp     = _moon_ep["ypp"]
        moon_px = _moon_ep["moon_px"]
        t_dt    = t if isinstance(t, datetime) else (t.utc_datetime() if t is not None else datetime.now(timezone.utc))
        render_s = max(64, min(320, moon_px))
        png = render_moon_image(
            t_dt=t_dt,
            observer_lat=observer.lat,
            observer_lon=observer.lon,
            size=render_s,
            flip=False,
            rotation_deg=None,
        )
        b64 = base64.b64encode(png).decode()
        _ep_images.append(dict(
            source=f"data:image/png;base64,{b64}",
            x=xpp, y=ypp,
            sizex=moon_px, sizey=moon_px,
            xanchor="center", yanchor="middle",
            xref="x", yref="y",
            layer="above",
        ))

    if _ep_images:
        fig.update_layout(images=_ep_images)

    # ── Noms de constellations ────────────────────────────────────────────────
    if opts.get("show_const_names", False) and observer is not None:
        from engines.constellation_lines import get_constellation_altaz_labels
        labels = get_constellation_altaz_labels(observer, t)
        lx, ly, lt = [], [], []
        for (lalt, laz, lname) in labels:
            xn, yn, dn = _gnomonic(
                np.array([lalt]), np.array([laz]),
                target_alt, target_az, half,
            )
            if dn[0] > 1.0:
                continue
            lx.append(float(cx + xn[0] * R))
            ly.append(float(cy - yn[0] * R))
            lt.append(lname.upper())
        if lx:
            fig.add_trace(go.Scatter(
                x=lx, y=ly, mode="text",
                text=lt,
                textfont=dict(color="#4a6699", size=10, family="monospace"),
                hoverinfo="skip", showlegend=False,
            ))

    # ── Grille équatoriale (méridiens AR + parallèles Déc) ───────────────────
    # Propriété gnomique : les méridiens AR (grands cercles passant par les pôles)
    # apparaissent comme des droites dans cette projection.
    if opts.get("show_grid", False) and observer is not None:
        from engines.sky_overlay import get_celestial_grid_altaz
        grid_lines = get_celestial_grid_altaz(observer, t,
                                              ra_step_h=1, dec_step_deg=15)
        gxs, gys = [], []
        for alts_g, azs_g in grid_lines:
            xn_g, yn_g, dn_g = _gnomonic(alts_g, azs_g, target_alt, target_az, half)
            seg_x, seg_y = [], []
            for xn, yn, dn in zip(xn_g, yn_g, dn_g):
                if dn <= 1.0:
                    seg_x.append(float(cx + xn * R))
                    seg_y.append(float(cy - yn * R))
                else:
                    if seg_x:
                        gxs += seg_x + [None]
                        gys += seg_y + [None]
                    seg_x, seg_y = [], []
            if seg_x:
                gxs += seg_x + [None]
                gys += seg_y + [None]
        if any(v is not None for v in gxs):
            fig.add_trace(go.Scatter(
                x=gxs, y=gys, mode="lines",
                line=dict(color="#4488ff", width=1.5),
                visible=True,
                hoverinfo="skip", showlegend=False,
            ))

    # ── Satellites ───────────────────────────────────────────────────────────
    if opts.get("show_satellites") and satellites_data:
        for sat in satellites_data:
            def _trail_px(alts_list, azs_list):
                tx, ty = [], []
                for a, z in zip(alts_list, azs_list):
                    xn, yn, dn = _gnomonic(np.array([a]), np.array([z]),
                                           target_alt, target_az, half)
                    if dn[0] <= 1.8:
                        tx.append(float(cx + xn[0] * R))
                        ty.append(float(cy - yn[0] * R))
                    else:
                        tx.append(None); ty.append(None)
                return tx, ty

            px, py = _trail_px(sat["past_alts"], sat["past_azs"])
            if any(v is not None for v in px):
                fig.add_trace(go.Scatter(
                    x=px, y=py, mode="lines",
                    line=dict(color="rgba(255,220,80,0.40)", width=1.0, dash="dot"),
                    hoverinfo="skip", showlegend=False,
                ))
            fx, fy = _trail_px(sat["future_alts"], sat["future_azs"])
            if any(v is not None for v in fx):
                fig.add_trace(go.Scatter(
                    x=fx, y=fy, mode="lines",
                    line=dict(color="rgba(255,220,80,0.85)", width=1.5),
                    hoverinfo="skip", showlegend=False,
                ))
            xn, yn, dn = _gnomonic(np.array([sat["alt"]]), np.array([sat["az"]]),
                                   target_alt, target_az, half)
            if dn[0] <= 1.0:
                fig.add_trace(go.Scatter(
                    x=[float(cx + xn[0] * R)], y=[float(cy - yn[0] * R)],
                    mode="markers+text",
                    marker=dict(symbol="triangle-up", size=10, color="#ffdc50",
                                line=dict(color="#000", width=0.6)),
                    text=[sat["name"].split("(")[0].strip()],
                    textposition="top center",
                    textfont=dict(color="#ffdc50", size=9),
                    hovertemplate=(
                        f"<b>{sat['name']}</b><br>"
                        f"Alt {sat['alt']:.1f}°  Az {sat['az']:.1f}°<extra></extra>"
                    ),
                    showlegend=False,
                ))

    # ── Réticule ─────────────────────────────────────────────────────────────
    g = R * 0.08
    for xs, ys in [
        ([cx - R, cx - g, None, cx + g, cx + R], [cy] * 5),
        ([cx] * 5, [cy - R, cy - g, None, cy + g, cy + R]),
    ]:
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines",
            line=dict(color="#991111", width=0.8),
            hoverinfo="skip", showlegend=False,
        ))

    # ── Marqueur cible ────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=[cx], y=[cy],
        mode="markers",
        marker=dict(
            symbol="circle-open", size=22,
            color="#ffdd33",
            line=dict(width=1.8, color="#ffdd33"),
        ),
        hovertemplate=(
            f"<b>{target_label}</b><br>"
            f"Alt {target_alt:.2f}°  Az {target_az:.2f}°"
            "<extra></extra>"
        ),
        showlegend=False,
    ))

    # ── Indicateur Nord céleste (corrigé de l'angle parallactique) ───────────
    # Le Pôle Nord Céleste est à alt = lat, az = 0° (quelle que soit l'heure).
    # Sa projection gnomique depuis le centre du champ donne la vraie direction N,
    # qui diffère du zénith ("haut") selon l'angle parallactique.
    if observer is not None:
        _ncp_alt = float(observer.lat)
        _ncp_az  = 0.0
        _xn_ncp, _yn_ncp, _dn_ncp = _gnomonic(
            np.array([_ncp_alt]), np.array([_ncp_az]),
            target_alt, target_az, half,
        )
        _dnp = float(_math.sqrt(_xn_ncp[0] ** 2 + _yn_ncp[0] ** 2))
        if _dnp > 1e-4:                      # éviter la singularité si on pointe le pôle
            _ndx = float(_xn_ncp[0]) / _dnp  # vecteur unitaire → Nord céleste
            _ndy = float(_yn_ncp[0]) / _dnp

            # Tick de 12 % de R rentrant depuis le bord du cercle-champ
            _r0 = R * 1.00
            _r1 = R * 0.88
            fig.add_trace(go.Scatter(
                x=[cx + _ndx * _r0, cx + _ndx * _r1],
                y=[cy - _ndy * _r0, cy - _ndy * _r1],
                mode="lines",
                line=dict(color="#5577dd", width=2.2),
                hoverinfo="skip", showlegend=False,
            ))
            # Tick opposé (Sud)
            fig.add_trace(go.Scatter(
                x=[cx - _ndx * _r0, cx - _ndx * _r1],
                y=[cy + _ndy * _r0, cy + _ndy * _r1],
                mode="lines",
                line=dict(color="#334466", width=1.2),
                hoverinfo="skip", showlegend=False,
            ))
            # Label "N☆"
            fig.add_annotation(
                x=cx + _ndx * (R * 1.16), y=cy - _ndy * (R * 1.16),
                text="<b>N☆</b>", showarrow=False,
                font=dict(color="#5577dd", size=10),
                xanchor="center", yanchor="middle",
            )

    # ── Annotations ───────────────────────────────────────────────────────────
    lc = dict(color="#334466", size=10)
    fig.add_annotation(x=cx, y=cy + R + 8,
                       text="↑ Zénith", showarrow=False,
                       font=lc, yanchor="bottom")
    fig.add_annotation(x=cx - R - 8, y=cy,
                       text="az −", showarrow=False,
                       font=lc, xanchor="right")
    fig.add_annotation(x=cx + R + 8, y=cy,
                       text="az +", showarrow=False,
                       font=lc, xanchor="left")
    fig.add_annotation(
        x=cx, y=cy - R - 20,
        text=f"<b>{target_label}</b>  ·  FOV {fov_deg:.0f}°  "
             f"·  alt {target_alt:.1f}°  az {target_az:.1f}°",
        showarrow=False,
        font=dict(color="#6677aa", size=12),
        yanchor="top",
    )

    return fig
