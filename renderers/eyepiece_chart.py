"""
Vue oculaire circulaire — projection gnomique (plan tangent local).

up    = +altitude (vers le zénith)
right = +azimut   (Est local)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go


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
    fov_deg: float = 5.0,
    width: int = 750,
    height: int = 750,
) -> go.Figure:
    """
    Construit la vue oculaire centrée sur (target_alt, target_az).

    stars_df doit contenir les colonnes : alt_deg, az_deg, magnitude, name.
    La projection gnomique est exacte pour FOV ≤ 20°.
    """
    R    = min(width, height) / 2.0 - 50
    cx   = width  / 2.0
    cy   = height / 2.0
    half = fov_deg / 2.0
    cos_alt = np.cos(np.radians(target_alt))

    fig = go.Figure()
    fig.update_layout(
        width=width, height=height,
        paper_bgcolor="#000010",
        plot_bgcolor="#000010",
        margin=dict(l=40, r=40, t=50, b=40),
        xaxis=dict(visible=False, range=[0, width],  fixedrange=True),
        yaxis=dict(visible=False, range=[0, height], scaleanchor="x", fixedrange=True),
        showlegend=False,
    )

    # ── Fond du disque ────────────────────────────────────────────────────────
    xc, yc = _circle(cx, cy, R)
    fig.add_trace(go.Scatter(
        x=xc, y=yc,
        mode="lines", fill="toself",
        fillcolor="#000010",
        line=dict(color="#2a2a4a", width=1.5),
        hoverinfo="skip", showlegend=False,
    ))

    # ── Cercle à mi-rayon (repère 50 % du FOV) ────────────────────────────────
    xh, yh = _circle(cx, cy, R * 0.5)
    fig.add_trace(go.Scatter(
        x=xh, y=yh,
        mode="lines",
        line=dict(color="#151530", width=0.8),
        hoverinfo="skip", showlegend=False,
    ))

    # ── Réticule ─────────────────────────────────────────────────────────────
    g = R * 0.12
    for xs, ys in [
        ([cx - R, cx - g, None, cx + g, cx + R], [cy] * 5),
        ([cx] * 5, [cy - R, cy - g, None, cy + g, cy + R]),
    ]:
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines",
            line=dict(color="#991111", width=0.8),
            hoverinfo="skip", showlegend=False,
        ))

    # ── Étoiles ───────────────────────────────────────────────────────────────
    if not stars_df.empty:
        daz  = ((stars_df["az_deg"].values  - target_az  + 180) % 360) - 180
        dalt =   stars_df["alt_deg"].values - target_alt
        xf   = daz * cos_alt          # correction cos(alt) pour les cercles az
        yf   = dalt
        dist = np.sqrt(xf ** 2 + yf ** 2)
        mask = dist <= half

        if mask.any():
            xpx   = cx + xf[mask] / half * R
            ypx   = cy - yf[mask] / half * R    # y inversé : nord = haut
            mags  = stars_df["magnitude"].values[mask]
            names = stars_df["name"].values[mask]
            alts  = stars_df["alt_deg"].values[mask]
            azs   = stars_df["az_deg"].values[mask]
            sizes = np.vectorize(_mag_to_size)(mags)

            fig.add_trace(go.Scatter(
                x=xpx.tolist(), y=ypx.tolist(),
                mode="markers",
                marker=dict(
                    size=sizes.tolist(),
                    color="white",
                    opacity=0.92,
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

    # ── Marqueur cible ────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=[cx], y=[cy],
        mode="markers",
        marker=dict(
            symbol="circle-open",
            size=22,
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

    # ── Annotations ───────────────────────────────────────────────────────────
    lc = dict(color="#445577", size=10)
    fig.add_annotation(x=cx, y=cy - R - 20,
                       text="↑  +alt (zénith)", showarrow=False,
                       font=lc, yanchor="top")
    fig.add_annotation(x=cx - R - 8, y=cy,
                       text="az −", showarrow=False,
                       font=lc, xanchor="right")
    fig.add_annotation(x=cx + R + 8, y=cy,
                       text="az +", showarrow=False,
                       font=lc, xanchor="left")
    fig.add_annotation(
        x=cx, y=cy + R + 22,
        text=f"<b>{target_label}</b>  ·  FOV {fov_deg:.0f}°  "
             f"·  alt {target_alt:.1f}°  az {target_az:.1f}°",
        showarrow=False,
        font=dict(color="#8899cc", size=12),
        yanchor="bottom",
    )

    return fig
