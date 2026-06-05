"""
NOCTILUM — Interface Streamlit principale.
Mini planétarium interactif basé sur Skyfield / BSC5.
"""

import time
from datetime import date as dt_date
from datetime import datetime, time as dt_time, timezone

import folium
import pandas as pd
import requests
import streamlit as st
from streamlit_folium import st_folium

from engines.astro_engine import Observer, get_planets_data, local_sidereal_time
from engines.messier_catalog import get_messier_visible
from engines.star_catalog import StarCatalog
from renderers.horizon_chart import build_horizon_chart
from renderers.sky_chart import build_sky_chart

# ─── Configuration de la page ────────────────────────────────────────────────

st.set_page_config(
    page_title="NOCTILUM",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS — thème sombre ──────────────────────────────────────────────────────

st.markdown(
    """
    <style>
        /* Fond global */
        .stApp { background-color: #0a0a1a; color: #cccccc; }

        /* Sidebar */
        section[data-testid="stSidebar"] {
            background-color: #0d0d22;
            border-right: 1px solid #1a2a4a;
        }

        /* Labels widgets */
        .stSlider label, .stNumberInput label,
        .stDateInput label, .stTimeInput label,
        .stCheckbox label { color: #8899bb !important; }

        /* Boutons */
        .stButton > button {
            background-color: #1a1a3a;
            color: #7799ff;
            border: 1px solid #2a3a6a;
            border-radius: 4px;
            width: 100%;
        }
        .stButton > button:hover { background-color: #22224a; }

        /* Tableau */
        .stDataFrame { background-color: #050510; }
        [data-testid="stDataFrameResizable"] { background-color: #050510; }

        /* Caption */
        .stCaption { color: #556688; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Helpers interface ───────────────────────────────────────────────────────

def _az_to_compass(az: int) -> str:
    _DIRS = [
        (0, 'N'), (22, 'NNE'), (45, 'NE'), (67, 'ENE'),
        (90, 'E'), (112, 'ESE'), (135, 'SE'), (157, 'SSE'),
        (180, 'S'), (202, 'SSO'), (225, 'SO'), (247, 'OSO'),
        (270, 'O'), (292, 'ONO'), (315, 'NO'), (337, 'NNO'),
    ]
    az_mod = az % 360
    return min(_DIRS, key=lambda d: min(abs(d[0] - az_mod), 360 - abs(d[0] - az_mod)))[1]

# ─── Catalogue BSC5 mis en cache ─────────────────────────────────────────────

@st.cache_resource(show_spinner="Chargement du catalogue BSC5…")
def _load_catalog() -> StarCatalog:
    cat = StarCatalog()
    cat.load()
    return cat

# ─── Session state — initialisation des valeurs par défaut ───────────────────

_now = datetime.now(timezone.utc)

_DEFAULTS: dict = {
    "lat":      48.8362,
    "lon":       2.3362,
    "elev":     60,
    "realtime": False,
    "obs_date": _now.date(),
    "obs_time": _now.time().replace(second=0, microsecond=0),
    # Affichage
    "show_stars":        True,
    "show_planets":      True,
    "show_const_lines":  True,
    "show_const_names":  True,
    "show_const_bounds": False,
    "show_ecliptic":     False,
    "show_grid":         False,
    "show_messier":      False,
    # Vue
    "view_mode": "🔭 Zénith",
    "az_center": 180,
    "place_label":       "Observatoire de Paris",
    "_last_click_id":    None,   # tuple (lat, lon) du dernier clic traité
}
# Version d'état — changer cette valeur force une réinitialisation complète
_STATE_VERSION = "3.0-horizon"
if st.session_state.get("_noctilum_v") != _STATE_VERSION:
    for _k, _v in _DEFAULTS.items():
        st.session_state[_k] = _v
    st.session_state["_noctilum_v"] = _STATE_VERSION
    st.rerun()  # relance avant que les widgets puissent cacher leurs anciennes valeurs

# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙ Paramètres")
    st.divider()

    # ── Lieu d'observation ──
    st.subheader("📍 Lieu")

    # ── Carte interactive ──
    with st.expander("🗺 Choisir sur la carte", expanded=False):

        def _reverse_geocode(lat: float, lon: float) -> str:
            try:
                r = requests.get(
                    "https://nominatim.openstreetmap.org/reverse",
                    params={"lat": lat, "lon": lon, "format": "json", "zoom": 10},
                    headers={"User-Agent": "NOCTILUM/1.0"},
                    timeout=6,
                ).json()
                addr = r.get("address", {})
                return (
                    addr.get("city") or addr.get("town") or addr.get("village")
                    or addr.get("county")
                    or r.get("display_name", "").split(",")[0] or ""
                )
            except Exception:
                return ""

        def _get_elevation(lat: float, lon: float) -> int:
            try:
                r = requests.get(
                    "https://api.open-meteo.com/v1/elevation",
                    params={"latitude": lat, "longitude": lon},
                    timeout=5,
                ).json()
                val = r.get("elevation", [None])[0]
                return max(0, int(round(val))) if val is not None else 0
            except Exception:
                return 0

        # Recherche Nominatim
        search_col, btn_col = st.columns([3, 1])
        with search_col:
            search_q = st.text_input(
                "Lieu",
                value=st.session_state.get("place_label", ""),
                placeholder="Paris, Londres, Tokyo…",
                label_visibility="collapsed",
            )
        with btn_col:
            do_search = st.button("🔍", use_container_width=True)

        if do_search and search_q.strip():
            try:
                geo = requests.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": search_q, "format": "json", "limit": 1},
                    headers={"User-Agent": "NOCTILUM/1.0"},
                    timeout=8,
                ).json()
                if geo:
                    _slat = round(float(geo[0]["lat"]), 4)
                    _slon = round(float(geo[0]["lon"]), 4)
                    st.session_state.lat         = _slat
                    st.session_state.lon         = _slon
                    st.session_state.elev        = _get_elevation(_slat, _slon)
                    st.session_state.place_label = (
                        geo[0].get("display_name", "").split(",")[0].strip()
                        or search_q.strip().title()
                    )
                    # Pas de st.rerun() : le clic sur 🔍 est déjà une interaction
                    # widget qui déclenche un rerun complet naturellement.
                else:
                    st.caption("Lieu non trouvé.")
            except Exception:
                st.caption("Erreur de géocodage.")

        # Carte Folium (tuiles sombres CartoDB, sans attribution Leaflet)
        _clat = float(st.session_state.lat)
        _clon = float(st.session_state.lon)
        _fmap = folium.Map(
            location=[_clat, _clon],
            zoom_start=5,
            tiles=None,
        )
        _fmap.options["attributionControl"] = False
        folium.TileLayer(
            tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
            attr=" ",
            control=False,
        ).add_to(_fmap)
        folium.Marker(
            [_clat, _clon],
            tooltip=st.session_state.place_label or f"{_clat:.4f}°, {_clon:.4f}°",
            icon=folium.Icon(color="blue", icon="star", prefix="fa"),
        ).add_to(_fmap)

        # Clé fixe : le composant Leaflet persiste entre les reruns,
        # pas d'événement d'initialisation parasite.
        _result = st_folium(
            _fmap,
            height=300,
            use_container_width=True,
            returned_objects=["last_clicked"],
            key="folium_map",
        )
        _clicked = (_result or {}).get("last_clicked")
        if _clicked:
            _nlat = round(_clicked["lat"], 4)
            _nlon = round(_clicked["lng"], 4)
            _click_id = (_nlat, _nlon)
            # Ne traiter que les clics NON encore traités — pas de st.rerun() :
            # st_folium déclenche déjà son propre rerun ; on met à jour le session
            # state ici pour que les widgets suivants (lat/lon/chart) se rendent
            # directement avec les nouvelles valeurs dans cette même passe.
            if _click_id != st.session_state.get("_last_click_id"):
                st.session_state._last_click_id = _click_id
                st.session_state.lat         = _nlat
                st.session_state.lon         = _nlon
                st.session_state.elev        = _get_elevation(_nlat, _nlon)
                st.session_state.place_label = _reverse_geocode(_nlat, _nlon) or f"{_nlat:.4f}°, {_nlon:.4f}°"
                st.rerun()

    _cl, _cm, _cr = st.columns(3)
    with _cl:
        lat = st.number_input("Lat °N", key="lat", min_value=-90.0, max_value=90.0,
                              step=0.0001, format="%.4f")
    with _cm:
        lon = st.number_input("Lon °E", key="lon", min_value=-180.0, max_value=180.0,
                              step=0.0001, format="%.4f")
    with _cr:
        elev = st.number_input("Alt m", key="elev", min_value=0, max_value=8848,
                               step=1, format="%d")

    st.divider()

    # ── Date & Heure ──
    st.subheader("🕐 Date & Heure (UTC)")
    realtime = st.checkbox("⏱ Temps réel", key="realtime")

    now_utc = datetime.now(timezone.utc)

    if realtime:
        obs_dt = now_utc
        st.caption(f"UTC : {now_utc.strftime('%Y-%m-%d  %H:%M:%S')}")
    else:
        obs_date = st.date_input("Date", key="obs_date")
        obs_time = st.time_input("Heure", key="obs_time", step=60)
        obs_dt = datetime.combine(obs_date, obs_time, tzinfo=timezone.utc)

    st.divider()

    # ── Étoiles ──
    st.subheader("🔭 Étoiles")
    mag_limit = st.slider(
        "Magnitude limite",
        min_value=1.0,
        max_value=7.0,
        value=5.0,
        step=0.5,
        help="Ciel parfait ≈ 6.5 · Ciel urbain ≈ 4.0–5.0",
    )

    st.divider()

    # ── Vue ──
    st.subheader("👁 Vue")
    view_mode = st.radio(
        "Mode",
        ["🔭 Zénith", "🌄 Paysage"],
        horizontal=True,
        key="view_mode",
        label_visibility="collapsed",
    )
    if view_mode == "🌄 Paysage":
        az_center = st.slider("Direction (az.)", 0, 359, key="az_center", format="%d°")
        st.caption(f"↗ {az_center}° — {_az_to_compass(az_center)}")

    st.divider()

    # ── Affichage ──
    st.subheader("🗺 Affichage")
    st.checkbox("Étoiles",                    key="show_stars")
    st.checkbox("Planètes",                   key="show_planets")
    st.checkbox("Lignes de constellations",   key="show_const_lines")
    st.checkbox("Noms de constellations",     key="show_const_names")
    st.checkbox("Limites de constellations",  key="show_const_bounds")
    st.checkbox("Plan de l'écliptique",       key="show_ecliptic")
    st.checkbox("Méridiens & parallèles",     key="show_grid")
    st.checkbox("Objets de Messier",          key="show_messier")
    if st.session_state.get("show_messier"):
        st.markdown(
            """
            <div style="font-size:11px; line-height:2; padding-left:22px; color:#999">
              <span style="color:#FFB347; font-size:14px">○</span>&nbsp; Galaxie<br>
              <span style="color:#90EE90; font-size:14px">✳</span>&nbsp; Amas ouvert<br>
              <span style="color:#7CFC00; font-size:14px">⊕</span>&nbsp; Amas globulaire<br>
              <span style="color:#87CEEB; font-size:14px">◇</span>&nbsp; Nébuleuse<br>
              <span style="color:#DDA0DD; font-size:14px">⊙</span>&nbsp; Nébuleuse planétaire<br>
              <span style="color:#FF7F7F; font-size:14px">△</span>&nbsp; Rémanent de supernova
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()
    st.button("🔄 Actualiser")

# ─── Calculs ─────────────────────────────────────────────────────────────────

try:
    with st.spinner("Calcul en cours…"):
        observer     = Observer(lat=float(lat), lon=float(lon),
                                elevation=float(elev),
                                name=st.session_state.place_label or "Lieu personnalisé")
        t            = obs_dt
        planets_data = get_planets_data(observer, t)
        catalog      = _load_catalog()
        stars_df     = catalog.get_visible(observer, t, mag_limit=float(mag_limit))
        messier_df   = (
            get_messier_visible(observer, t)
            if st.session_state.show_messier else None
        )

        _display_options = {
            "show_stars":        bool(st.session_state.show_stars),
            "show_planets":      bool(st.session_state.show_planets),
            "show_const_lines":  bool(st.session_state.show_const_lines),
            "show_const_names":  bool(st.session_state.show_const_names),
            "show_const_bounds": bool(st.session_state.show_const_bounds),
            "show_ecliptic":     bool(st.session_state.show_ecliptic),
            "show_grid":         bool(st.session_state.show_grid),
            "show_messier":      bool(st.session_state.show_messier),
        }

        _is_horizon = st.session_state.get("view_mode") == "🌄 Paysage"
        _az_center  = int(st.session_state.get("az_center", 180))

        if _is_horizon:
            sky_fig = build_horizon_chart(
                stars_df, planets_data, observer, t,
                az_center=float(_az_center),
                messier_df=messier_df,
                options=_display_options,
            )
        else:
            sky_fig = build_sky_chart(
                stars_df, planets_data, observer, t,
                messier_df=messier_df,
                options=_display_options,
            )

        # TSL en heures, minutes, secondes
        tsl   = local_sidereal_time(observer, t)
        tsl_h = int(tsl)
        tsl_m = int((tsl % 1) * 60)
        tsl_s = int(((tsl % 1) * 60 % 1) * 60)

except Exception as exc:
    import traceback
    st.error(f"Erreur de calcul : {exc}")
    st.code(traceback.format_exc())
    st.stop()

# ─── En-tête centré ──────────────────────────────────────────────────────────

st.markdown(
    f"""
    <div style="text-align:center; padding:10px 0 6px 0;">
        <h1 style="color:#8899ff; letter-spacing:0.35em; margin:0; font-size:2.4rem;">
            NOCTILUM
        </h1>
        <p style="color:#6677aa; margin:5px 0 0 0; font-size:0.88em; letter-spacing:0.05em;">
            TSL&nbsp;
            {tsl_h:02d}<sup>h</sup>{tsl_m:02d}<sup>m</sup>{tsl_s:02d}<sup>s</sup>
            &nbsp;&nbsp;·&nbsp;&nbsp;
            UTC&nbsp;{t.strftime('%Y-%m-%d&nbsp;&nbsp;%H:%M')}
            &nbsp;&nbsp;·&nbsp;&nbsp;
            {observer.name}&nbsp;
            ({abs(observer.lat):.4f}°{'N' if observer.lat >= 0 else 'S'},&nbsp;{abs(observer.lon):.4f}°{'E' if observer.lon >= 0 else 'W'},&nbsp;{int(observer.elevation)}&nbsp;m)
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

# ─── Colonnes principales ─────────────────────────────────────────────────────

col_chart, col_table = st.columns([2, 1], gap="medium")

# ── Carte du ciel ──
with col_chart:
    st.plotly_chart(
        sky_fig,
        use_container_width=True,
        config={"displayModeBar": False, "scrollZoom": False},
        key=f"sky_{observer.lat:.4f}_{observer.lon:.4f}_{_is_horizon}_{_az_center}",
    )
    with st.popover("ℹ️ À propos", use_container_width=False):
        st.markdown(
            """
**NOCTILUM** — Mini-planétarium interactif

---

**Spécifications fonctionnelles**
Jean-Philippe Blanchard

**Développement logiciel**
Claude Sonnet 4.6 — Anthropic

---

**Framework & bibliothèques**
Python · Streamlit · Plotly · NumPy · Pandas · Folium

**Astronomie**
Skyfield · Éphéméride JPL DE440s

---

**Sources de données**
- Catalogue d'étoiles : *Yale Bright Star Catalogue* (BSC5) — brettonw / Yale
- Constellations & limites IAU : *d3-celestial* — Olaf Frohn
- Catalogue Messier : données IAU / SEDS
- Fond cartographique : CartoDB Dark Matter · © OpenStreetMap contributors
- Géocodage : Nominatim (OpenStreetMap)
            """
        )

# ── Tableau éphémérides ──
with col_table:
    st.subheader("Éphémérides")

    # Corps triés : visibles d'abord, puis par altitude décroissante
    sorted_bodies = sorted(
        planets_data,
        key=lambda b: (not b["above_horizon"], -b["alt"]),
    )

    planet_rows = []
    for body in sorted_bodies:
        above  = body["above_horizon"]
        prefix = "" if above else "↓ "
        icon   = ("☀" if body["name"] == "Soleil"
                  else "🌙" if body["name"] == "Lune"
                  else "⬤")
        mag    = body["magnitude"]

        planet_rows.append({
            "Astre":   prefix + icon + " " + body["name"],
            "Altitude": f"{body['alt']:+.1f}°",
            "Azimut":   f"{body['az']:.1f}°",
            "Magnitude": f"{mag:.1f}" if mag is not None else "—",
            "Lever":    body["rise"],
            "Coucher":  body["set"],
        })

    planet_df = pd.DataFrame(planet_rows)

    st.dataframe(
        planet_df,
        use_container_width=True,
        hide_index=True,
        height=390,
    )

    # Résumé rapide
    nb_visible_bodies = sum(1 for b in planets_data if b["above_horizon"])
    st.caption(
        f"🌟 {len(stars_df)} étoiles visibles (mag ≤ {mag_limit:.1f})  ·  "
        f"🪐 {nb_visible_bodies}/9 corps au-dessus de l'horizon"
    )

# ─── Rafraîchissement automatique (temps réel) ───────────────────────────────

if realtime:
    time.sleep(30)
    st.rerun()
