import folium
import folium.plugins
import pandas as pd


def build_community_map(visits_df: pd.DataFrame) -> folium.Map:
    m = folium.Map(location=[20, 0], zoom_start=2, tiles=None)
    m.options["attributionControl"] = False
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr=" ",
        control=False,
    ).add_to(m)

    if visits_df.empty:
        return m

    cluster = folium.plugins.MarkerCluster()
    for _, row in visits_df.iterrows():
        lat = row.get("lat")
        lon = row.get("lon")
        if pd.isna(lat) or pd.isna(lon):
            continue
        ts = row.get("ts")
        date_str = ts.strftime("%Y-%m-%d %H:%M") if hasattr(ts, "strftime") else str(ts)
        tooltip = f"{row.get('city', '?')}, {row.get('country', '?')} — {date_str}"
        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            color="#4fc3f7",
            fill=True,
            fill_color="#4fc3f7",
            fill_opacity=0.6,
            tooltip=tooltip,
        ).add_to(cluster)

    cluster.add_to(m)
    return m
