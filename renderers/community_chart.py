import folium
import pandas as pd

# Centroïdes approximatifs par code pays ISO 3166-1
_CENTERS: dict[str, tuple[float, float]] = {
    "FR": (46.2, 2.2),   "US": (38.0, -97.0),  "GB": (54.0, -2.0),
    "DE": (51.2, 10.5),  "ES": (40.4, -3.7),   "IT": (41.9, 12.6),
    "CA": (56.1, -106.3),"AU": (-25.3, 133.8),  "JP": (36.2, 138.3),
    "CN": (35.9, 104.2), "IN": (20.6, 78.9),    "BR": (-14.2, -51.9),
    "RU": (61.5, 105.3), "MX": (23.6, -102.6),  "ZA": (-30.6, 22.9),
    "AR": (-38.4, -63.6),"BE": (50.5, 4.5),     "NL": (52.1, 5.3),
    "PT": (39.4, -8.2),  "SE": (60.1, 18.6),    "NO": (60.5, 8.5),
    "DK": (56.3, 9.5),   "FI": (61.9, 25.7),    "CH": (46.8, 8.2),
    "AT": (47.5, 14.5),  "PL": (51.9, 19.1),    "CZ": (49.8, 15.5),
    "RO": (45.9, 24.9),  "GR": (39.1, 21.8),    "TR": (38.9, 35.2),
    "IL": (31.0, 34.9),  "SA": (23.9, 45.1),    "AE": (23.4, 53.8),
    "KR": (35.9, 127.8), "TH": (15.9, 100.9),   "SG": (1.4, 103.8),
    "NZ": (-40.9, 174.9),"EG": (26.8, 30.8),    "MA": (31.8, -7.1),
    "NG": (9.1, 8.7),    "KE": (-0.0, 37.9),    "TN": (33.9, 9.6),
    "HU": (47.2, 19.5),  "UA": (48.4, 31.2),    "CL": (-35.7, -71.5),
    "CO": (4.6, -74.1),  "PE": (-9.2, -75.0),   "VE": (6.4, -66.6),
    "PK": (30.4, 69.3),  "ID": (-0.8, 113.9),   "MY": (4.2, 108.0),
    "PH": (12.9, 121.8), "VN": (14.1, 108.3),   "LU": (49.8, 6.1),
    "IE": (53.4, -8.2),  "SK": (48.7, 19.7),    "HR": (45.1, 15.2),
}


def _flag(code: str) -> str:
    try:
        return "".join(chr(0x1F1E0 + ord(c) - ord("A")) for c in code.upper()[:2])
    except Exception:
        return "🌍"


def build_community_map(visits_df: pd.DataFrame) -> folium.Map:
    m = folium.Map(
        location=[20, 0],
        zoom_start=2,
        min_zoom=2,
        max_zoom=2,
        max_bounds=True,
        zoom_control=False,
        tiles=None,
    )
    m.options["attributionControl"] = False
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr=" ",
        control=False,
        no_wrap=True,
    ).add_to(m)

    if visits_df.empty:
        return m

    # Compter les visites par pays
    col = "country" if "country" in visits_df.columns else "country_code"
    counts = visits_df[col].dropna().value_counts()
    if counts.empty:
        return m

    max_n = int(counts.iloc[0])

    for code, n in counts.items():
        # Coordonnées : moyenne des positions réelles, ou centroïde
        rows = visits_df[visits_df[col] == code]
        valid = rows.dropna(subset=["lat", "lon"])
        if not valid.empty:
            lat = float(valid["lat"].mean())
            lon = float(valid["lon"].mean())
        elif code in _CENTERS:
            lat, lon = _CENTERS[code]
        else:
            continue

        size = 16 + int(20 * n / max_n)  # 16–36 px
        label = f"{_flag(code)} {code}"
        tooltip = f"{label} — {n} visite{'s' if n > 1 else ''}"

        folium.Marker(
            location=[lat, lon],
            tooltip=tooltip,
            icon=folium.DivIcon(
                html=(
                    f'<div style="'
                    f'width:{size}px;height:{size}px;border-radius:50%;'
                    f'background:rgba(79,195,247,0.25);border:2px solid #4fc3f7;'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'font-size:{max(9, size//3)}px;font-weight:bold;color:#e0f7ff;'
                    f'margin-left:-{size//2}px;margin-top:-{size//2}px;'
                    f'">{n}</div>'
                ),
                icon_size=(size, size),
                icon_anchor=(size // 2, size // 2),
            ),
        ).add_to(m)

    return m
