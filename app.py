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
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as _components
from streamlit_folium import st_folium

_resize_trigger = _components.declare_component(
    "width_detector",
    path=str(Path(__file__).parent / "components" / "width_detector"),
)

from engines.astro_engine import Observer, get_planets_data, local_sidereal_time
from engines.messier_catalog import get_messier_visible
from engines.star_catalog import StarCatalog
from engines.i18n import t, tr_body, tr_event, tr_phase, tr_eclipse_type, compass_dirs
from renderers.eyepiece_chart import build_eyepiece_chart
from renderers.horizon_chart import build_horizon_chart

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

        /* Composant détecteur de resize — invisible mais actif */
        iframe[title="app.width_detector"] {
            visibility: hidden !important;
            position: absolute !important;
            width: 1px !important;
            height: 1px !important;
            top: -9999px !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Resize trigger : déclenche un re-run Streamlit quand la fenêtre change de taille,
# ce qui permet à use_container_width=True de recalculer la largeur correcte.
_resize_trigger(default=None, key="_resize_w")

# ─── Helpers interface ───────────────────────────────────────────────────────

def _az_to_compass(az: int) -> str:
    dirs = compass_dirs()
    az_mod = az % 360
    return min(dirs, key=lambda d: min(abs(d[0] - az_mod), 360 - abs(d[0] - az_mod)))[1]

# ─── Catalogue BSC5 mis en cache ─────────────────────────────────────────────

@st.cache_resource(show_spinner=True)
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
    # obs_date / obs_time : TOUJOURS en UTC
    "obs_date": _now.date(),
    "obs_time": _now.time().replace(second=0, microsecond=0),
    # obs_date_loc / obs_time_loc : heure locale (clés séparées, jamais mélangées avec UTC)
    "obs_date_loc": _now.date(),
    "obs_time_loc": _now.time().replace(second=0, microsecond=0),
    "time_mode": "UTC",       # "UTC" ou "Locale"
    "_prev_time_mode": "UTC", # pour détecter le changement de mode
    # Affichage
    "show_stars":        True,
    "show_planets":      True,
    "show_const_lines":  True,
    "show_const_names":  True,
    "show_const_bounds": False,
    "show_ecliptic":     False,
    "show_grid":         False,
    "show_messier":      False,
    "show_milkyway":     False,
    "show_satellites":   False,
    # Satellites
    "sat_group":     "ISS / Stations",
    "sat_trail_min": 5,
    "sat_selected":  [],
    "sat_all":       False,
    "sat_page":      0,
    "_prev_sat_group": "ISS / Stations",
    # Vue
    "view_mode": "🔭 Zénith",
    "az_center": 180,
    # Langue
    "lang": "fr",
    "place_label":       "Observatoire de Paris",
    "_last_click_id":    None,
}
# Version d'état — changer cette valeur force une réinitialisation complète
_STATE_VERSION = "4.0-i18n"
if st.session_state.get("_noctilum_v") != _STATE_VERSION:
    for _k, _v in _DEFAULTS.items():
        st.session_state[_k] = _v
    st.session_state["_noctilum_v"] = _STATE_VERSION
    st.rerun()  # relance avant que les widgets puissent cacher leurs anciennes valeurs

# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    # ── Sélecteur de langue ──
    st.selectbox(
        "🌐",
        ["fr", "en", "es", "zh", "hi"],
        format_func=lambda x: {
            "fr": "🇫🇷 Français", "en": "🇬🇧 English",
            "es": "🇪🇸 Español",  "zh": "🇨🇳 中文", "hi": "🇮🇳 हिन्दी",
        }[x],
        key="lang",
        label_visibility="collapsed",
    )

    st.title(t("settings_title"))
    st.divider()

    # ── Lieu d'observation ──
    st.subheader(t("section_location"))

    # ── Carte interactive ──
    with st.expander(t("map_picker"), expanded=False):

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
                    st.caption(t("place_not_found"))
            except Exception:
                st.caption(t("geocode_error"))

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

    st.button(t("btn_refresh"))
    st.divider()

    # ── Date & Heure ──
    st.subheader(t("section_datetime"))
    realtime = st.checkbox(t("realtime_label"), key="realtime")

    now_utc = datetime.now(timezone.utc)

    # Choix UTC / heure locale
    time_mode = st.radio(
        "ref",
        ["UTC", "Locale"],
        format_func=lambda x: x if x == "UTC" else t("time_local_option"),
        horizontal=True,
        key="time_mode",
        label_visibility="collapsed",
    )

    # Fuseau du lieu courant (utilisé si mode Locale)
    _cur_lat = float(st.session_state.get("lat", 48.8362))
    _cur_lon = float(st.session_state.get("lon",  2.3362))
    from engines.time_engine import get_timezone_name as _get_tz, local_datetime as _to_local
    from zoneinfo import ZoneInfo as _ZoneInfo
    _tz_name = _get_tz(_cur_lat, _cur_lon)
    _tz_zone = _ZoneInfo(_tz_name)

    if realtime:
        obs_dt = now_utc
        if time_mode == "UTC":
            st.caption(f"UTC : {now_utc.strftime('%Y-%m-%d  %H:%M:%S')}")
        else:
            _now_local = now_utc.astimezone(_tz_zone)
            st.caption(f"{_tz_name} : {_now_local.strftime('%Y-%m-%d  %H:%M:%S %Z')}")
    else:
        # Détection du changement de mode UTC ↔ Locale
        _prev_mode = st.session_state.get("_prev_time_mode", "UTC")
        if _prev_mode != time_mode:
            if time_mode == "Locale":
                # Passage UTC → Locale : convertir les valeurs UTC stockées en local
                _utc_stored = datetime.combine(
                    st.session_state["obs_date"],
                    st.session_state["obs_time"],
                    tzinfo=timezone.utc,
                )
                _loc_init = _utc_stored.astimezone(_tz_zone)
                st.session_state["obs_date_loc"] = _loc_init.date()
                st.session_state["obs_time_loc"] = _loc_init.time().replace(second=0, microsecond=0)
            else:
                # Passage Locale → UTC : convertir les valeurs locales stockées en UTC
                _loc_stored = datetime.combine(
                    st.session_state["obs_date_loc"],
                    st.session_state["obs_time_loc"],
                ).replace(tzinfo=_tz_zone).astimezone(timezone.utc)
                st.session_state["obs_date"] = _loc_stored.date()
                st.session_state["obs_time"] = _loc_stored.time().replace(second=0, microsecond=0)
            st.session_state["_prev_time_mode"] = time_mode

        if time_mode == "UTC":
            # Clés UTC — obs_date/obs_time contiennent toujours du temps UTC
            obs_date = st.date_input(t("date_utc"), key="obs_date")
            obs_time = st.time_input(t("time_utc"), key="obs_time", step=60)
            obs_dt = datetime.combine(obs_date, obs_time, tzinfo=timezone.utc)
        else:
            # Clés séparées — obs_date_loc/obs_time_loc contiennent l'heure locale
            obs_date_loc = st.date_input(f"Date ({_tz_name})", key="obs_date_loc")
            obs_time_loc = st.time_input(f"Heure ({_tz_name})", key="obs_time_loc", step=60)
            obs_dt = (
                datetime.combine(obs_date_loc, obs_time_loc)
                .replace(tzinfo=_tz_zone)
                .astimezone(timezone.utc)
            )

    st.divider()

    # ── Étoiles ──
    st.subheader(t("section_stars"))

    import engines.hipparcos_catalog as _hip
    _hip_ok = _hip.is_available()
    _cat_options = ["BSC5 (9 096 ★, mag ≤ 8)"]
    if _hip_ok:
        _cat_options.append("Hipparcos (118 218 ★, mag ≤ 12)")
    cat_choice = st.radio(
        "Catalogue",
        _cat_options,
        key="star_catalog",
        label_visibility="collapsed",
    )
    _use_hipparcos = cat_choice.startswith("Hipparcos")

    if not _hip_ok:
        if st.button(t("btn_download_hip")):
            _prog = st.progress(0.0, text=t("downloading"))
            try:
                _hip.download(progress_cb=lambda f: _prog.progress(f, text=f"{t('downloading')} {f*100:.0f}%"))
                _prog.empty()
                st.success(t("hip_downloaded"))
            except Exception as _e:
                _prog.empty()
                st.error(t("error_prefix", e=_e))

    _max_mag = 12.0 if _use_hipparcos else 8.0
    _default_mag = min(st.session_state.get("mag_limit_val", 5.0), _max_mag)
    mag_limit = st.slider(
        t("mag_limit_label"),
        min_value=1.0,
        max_value=_max_mag,
        value=_default_mag,
        step=0.5,
        help=t("mag_help") + (t("mag_help_eyepiece") if _use_hipparcos else ""),
        key="mag_limit_slider",
    )
    st.session_state["mag_limit_val"] = mag_limit

    st.divider()

    # ── Vue ──
    st.subheader(t("section_view"))
    _VIEW_OPTS = ["🌌 Zénith", "🌄 Paysage", "🔭 Oculaire"]
    view_mode = st.radio(
        "view",
        _VIEW_OPTS,
        format_func=lambda x: {
            "🌌 Zénith": t("view_zenith"),
            "🌄 Paysage": t("view_landscape"),
            "🔭 Oculaire": t("view_eyepiece"),
        }[x],
        horizontal=True,
        key="view_mode",
        label_visibility="collapsed",
    )
    if view_mode == "🌄 Paysage":
        az_center = st.slider(t("direction_label"), 0, 359, key="az_center", format="%d°")
        st.caption(f"↗ {az_center}° — {_az_to_compass(az_center)}")
    if view_mode == "🔭 Oculaire":
        # Grossissement max = 60° / diam_lunaire quand la Lune est la cible
        _ep_target_now = st.session_state.get("_eyepiece_target")
        _ep_label = getattr(_ep_target_now, "label", "") if _ep_target_now else ""
        _ep_label_l = _ep_label.lower()
        if "lune" in _ep_label_l or "moon" in _ep_label_l:
            _body_c = next(
                (p for p in st.session_state.get("_planets_cache", [])
                 if p["name"] == "Lune"), None)
            _default_diam = 1842.0
        elif "soleil" in _ep_label_l or "sun" in _ep_label_l:
            _body_c = next(
                (p for p in st.session_state.get("_planets_cache", [])
                 if p["name"] == "Soleil"), None)
            _default_diam = 1919.0
        else:
            _body_c = None
            _default_diam = None

        if _default_diam is not None:
            _diam_deg = ((_body_c.get("ang_diam_arcsec") or _default_diam) / 3600.0) if _body_c else (_default_diam / 3600.0)
            _max_gross = max(10, (int(60.0 / _diam_deg) // 5) * 5)
        else:
            _max_gross = 300
        # Verrouiller la valeur courante si elle dépasse le nouveau max
        _cur_gross = int(st.session_state.get("eyepiece_gross", 80))
        if _cur_gross > _max_gross:
            st.session_state["eyepiece_gross"] = _max_gross
        _gross = st.slider(t("magnification_label"), 10, _max_gross,
                           min(80, _max_gross), step=5,
                           key="eyepiece_gross", format="×%d")
        _fov_preview = 60.0 / _gross
        st.caption(t("fov_caption", fov=_fov_preview))
        st.text_input(t("search_object"), key="search_query",
                      placeholder="Sirius, M42, Andromède, Jupiter…")
        _q = st.session_state.get("search_query", "").strip()
        if _q:
            from engines.search_catalog import search as _search
            _cached_planets = st.session_state.get("_planets_cache", [])
            _results = _search(_q, _cached_planets)
            if _results:
                _opts = [f"{r.label} — {r.description}" for r in _results]
                _choice = st.selectbox("", _opts, key="search_choice",
                                       label_visibility="collapsed")
                st.session_state["_eyepiece_target"] = _results[_opts.index(_choice)]
            else:
                st.caption(t("no_results"))

    st.divider()

    # ── Affichage ──
    st.subheader(t("section_display"))
    st.checkbox(t("show_stars_label"),           key="show_stars")
    st.checkbox(t("show_planets_label"),         key="show_planets")
    st.checkbox(t("show_milkyway_label"),        key="show_milkyway")
    st.checkbox(t("show_const_lines_label"),     key="show_const_lines")
    st.checkbox(t("show_const_names_label"),     key="show_const_names")
    st.checkbox(t("show_const_bounds_label"),    key="show_const_bounds")
    st.checkbox(t("show_ecliptic_label"),        key="show_ecliptic")
    st.checkbox(t("show_grid_label"),            key="show_grid")
    st.checkbox(t("show_messier_label"),         key="show_messier")
    if st.session_state.get("show_messier"):
        st.markdown(
            f"""
            <div style="font-size:11px; line-height:2; padding-left:22px; color:#999">
              <span style="color:#FFB347; font-size:14px">○</span>&nbsp; {t("messier_galaxy")}<br>
              <span style="color:#90EE90; font-size:14px">✳</span>&nbsp; {t("messier_open")}<br>
              <span style="color:#7CFC00; font-size:14px">⊕</span>&nbsp; {t("messier_globular")}<br>
              <span style="color:#87CEEB; font-size:14px">◇</span>&nbsp; {t("messier_nebula")}<br>
              <span style="color:#DDA0DD; font-size:14px">⊙</span>&nbsp; {t("messier_planetary")}<br>
              <span style="color:#FF7F7F; font-size:14px">△</span>&nbsp; {t("messier_snr")}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Satellites ──
    st.subheader(t("section_satellites"))
    st.checkbox(t("show_satellites_label"), key="show_satellites")
    if st.session_state.get("show_satellites"):
        from engines.satellite_engine import GROUPS, list_satellites
        _sat_group = st.selectbox(
            t("sat_group_label"), list(GROUPS.keys()),
            key="sat_group",
        )
        _sat_trail = st.slider(
            t("sat_trail_label"), 1, 15, 5,
            key="sat_trail_min",
        )
        # Réinitialise la page si le groupe a changé
        if st.session_state.get("_prev_sat_group") != _sat_group:
            st.session_state["sat_page"] = 0
            st.session_state["_prev_sat_group"] = _sat_group

        with st.spinner("Chargement TLE…"):
            _sat_names = list_satellites(_sat_group)
        if _sat_names:
            _SAT_PAGE_SIZE = 200
            _sat_large = len(_sat_names) > _SAT_PAGE_SIZE
            st.checkbox(t("sat_all_label"), key="sat_all")
            _sat_use_all = st.session_state.get("sat_all", False)
            if _sat_use_all:
                if _sat_large:
                    _n_pages = (len(_sat_names) - 1) // _SAT_PAGE_SIZE + 1
                    _page = int(st.session_state.get("sat_page", 0))
                    _page = max(0, min(_page, _n_pages - 1))
                    st.caption(t("sat_page_info", n=len(_sat_names), p=_page+1, total=_n_pages))
                    _c1, _c2 = st.columns(2)
                    if _c1.button(t("sat_prev_btn"), disabled=_page == 0, use_container_width=True):
                        st.session_state["sat_page"] = _page - 1
                        st.rerun()
                    if _c2.button(t("sat_next_btn"), disabled=_page == _n_pages - 1, use_container_width=True):
                        st.session_state["sat_page"] = _page + 1
                        st.rerun()
                    _sat_selected = _sat_names[
                        _page * _SAT_PAGE_SIZE : (_page + 1) * _SAT_PAGE_SIZE
                    ]
                else:
                    _sat_selected = _sat_names
            else:
                _sat_selected = st.multiselect(
                    t("sat_selection_label"),
                    _sat_names,
                    default=[],
                    key="sat_selected",
                    placeholder=t("sat_placeholder"),
                )
        else:
            st.caption(t("sat_load_error"))
            _sat_selected = []
    else:
        _sat_selected = []
        _sat_trail = 5


# ─── Calculs ─────────────────────────────────────────────────────────────────

try:
    with st.spinner("Calcul en cours…"):
        observer     = Observer(lat=float(lat), lon=float(lon),
                                elevation=float(elev),
                                name=st.session_state.place_label or "Lieu personnalisé")
        t            = obs_dt
        planets_data = get_planets_data(observer, t)
        if _use_hipparcos:
            stars_df = _hip.get_visible(observer, t, mag_limit=float(mag_limit))
        else:
            catalog  = _load_catalog()
            stars_df = catalog.get_visible(observer, t, mag_limit=float(mag_limit))
        messier_df   = (
            get_messier_visible(observer, t)
            if st.session_state.show_messier else None
        )

        # Satellites
        _show_sat = bool(st.session_state.get("show_satellites", False))
        _sat_data = []
        if _show_sat and _sat_selected:
            from engines.satellite_engine import get_satellites_data
            _sat_group_key = st.session_state.get("sat_group", "ISS / Stations")
            _sat_trail_min = float(st.session_state.get("sat_trail_min", 5))
            _sat_data = get_satellites_data(
                observer, t,
                group=_sat_group_key,
                selected=_sat_selected,
                trail_min=_sat_trail_min,
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
            "show_milkyway":     bool(st.session_state.show_milkyway),
            "show_satellites":   _show_sat,
        }

        # Mettre en cache les planètes pour la recherche (sidebar rendu avant calcul)
        st.session_state["_planets_cache"] = [
            {"name": p["name"], "alt": p["alt"], "az": p["az"],
             "magnitude": p.get("magnitude"), "above_horizon": p.get("above_horizon", True),
             "ang_diam_arcsec": p.get("ang_diam_arcsec"),
             "distance_au": p.get("distance_au"),
             "ring_B_deg": p.get("ring_B_deg"),
             "ring_P_deg": p.get("ring_P_deg"),
             "parallactic_angle_deg": p.get("parallactic_angle_deg")}
            for p in planets_data
        ]

        _view      = st.session_state.get("view_mode", "🌌 Zénith")
        _is_horizon  = _view == "🌄 Paysage"
        _is_eyepiece = _view == "🔭 Oculaire"
        _az_center   = int(st.session_state.get("az_center", 180))

        if _is_eyepiece:
            from engines.search_catalog import resolve_target
            _gross  = float(st.session_state.get("eyepiece_gross", 80))
            _fov    = 60.0 / _gross     # champ réel (60° champ apparent standard)
            _target = st.session_state.get("_eyepiece_target")
            _ep_mag = max(mag_limit, 8.0) if _use_hipparcos else 8.0
            if _use_hipparcos:
                _stars_ep = _hip.get_visible(observer, t, mag_limit=_ep_mag, min_alt=-_fov / 2)
            else:
                _stars_ep = catalog.get_visible(observer, t, mag_limit=_ep_mag, min_alt=-_fov / 2)
            _messier_ep = (
                get_messier_visible(observer, t)
                if _display_options.get("show_messier") else None
            )
            if _target is None:
                _alt_ep, _az_ep, _lbl_ep = 90.0, 0.0, "Zénith"
            else:
                _alt_ep, _az_ep = resolve_target(_target, observer, t, planets_data)
                _lbl_ep = _target.label

        # TSL en heures, minutes, secondes
        tsl   = local_sidereal_time(observer, t)
        tsl_h = int(tsl)
        tsl_m = int((tsl % 1) * 60)
        tsl_s = int(((tsl % 1) * 60 % 1) * 60)

        # Informations temporelles complètes (onglet Temps)
        from engines.time_engine import compute_time_info as _compute_time_info
        _time_info = _compute_time_info(t, float(lat), float(lon))

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
    sky_fig = None
    try:
        if _is_eyepiece:
            sky_fig = build_eyepiece_chart(
                _alt_ep, _az_ep, _lbl_ep,
                _stars_ep, fov_deg=_fov,
                options=_display_options,
                planets_data=planets_data,
                messier_df=_messier_ep,
                observer=observer,
                t=t,
                satellites_data=_sat_data,
            )
        elif _is_horizon:
            sky_fig = build_horizon_chart(
                stars_df, planets_data, observer, t,
                az_center=float(_az_center),
                messier_df=messier_df,
                options=_display_options,
                satellites_data=_sat_data,
            )
        else:
            from renderers.sky_chart import build_sky_chart
            sky_fig = build_sky_chart(
                stars_df, planets_data, observer, t,
                messier_df=messier_df,
                options=_display_options,
                satellites_data=_sat_data,
            )
    except Exception as _fig_exc:
        import traceback as _tb
        st.error(t("render_error", e=_fig_exc))
        st.code(_tb.format_exc())

    if sky_fig is not None:
        # Effacer la largeur fixe du layout : use_container_width=True la remplace
        # par la vraie largeur de la colonne à chaque re-run.
        sky_fig.update_layout(width=None)
        _ep_key_suffix = (
            f"_ep_{_gross:.0f}_{_alt_ep:.2f}_{_az_ep:.2f}"
            if _is_eyepiece else ""
        )
        st.plotly_chart(
            sky_fig,
            use_container_width=True,
            config={"displayModeBar": False, "scrollZoom": _is_eyepiece},
            key=f"sky_{observer.lat:.4f}_{observer.lon:.4f}_{_view}_{_az_center}_{''.join(str(int(v)) for v in _display_options.values())}{_ep_key_suffix}",
        )
    with st.popover(t("about_btn"), use_container_width=False):
        st.markdown(t("about_text"))

# ── Tableau éphémérides ──
with col_table:
    # Corps triés : visibles d'abord, puis par altitude décroissante
    sorted_bodies = sorted(
        planets_data,
        key=lambda b: (not b["above_horizon"], -b["alt"]),
    )

    tab_temps, tab_eph, tab_coord, tab_ecl, tab_moon, tab_conj, tab_crep = st.tabs([
        t("tab_temps"), t("tab_eph"), t("tab_coord"), t("tab_ecl"),
        t("tab_moon"), t("tab_conj"), t("tab_crep"),
    ])

    with tab_eph:
        main_rows = []
        detail_rows = []
        for body in sorted_bodies:
            above  = body["above_horizon"]
            prefix = "" if above else "↓ "
            icon   = ("☀" if body["name"] == "Soleil"
                      else "🌙" if body["name"] == "Lune"
                      else "⬤")
            mag    = body["magnitude"]
            elong  = body.get("elongation")

            main_rows.append({
                t("col_body"):    prefix + icon + " " + tr_body(body["name"]),
                "Alt":            f"{body['alt']:+.1f}°",
                "Az":             f"{body['az']:.1f}°",
                "Mag":            f"{mag:.1f}" if mag is not None else "—",
                t("col_rise"):    body["rise"],
                t("col_transit"): body.get("transit", "—"),
                t("col_set"):     body["set"],
                t("col_elong"):   f"{elong:.0f}°" if elong is not None else "—",
            })

            dist   = body.get("distance_au")
            diam   = body.get("ang_diam_arcsec")
            illum  = body.get("illumination")
            detail_rows.append({
                t("col_body"):   icon + " " + tr_body(body["name"]),
                t("col_dist"):   f"{dist:.4f}" if dist is not None else "—",
                t("col_diam"):   f"{diam:.1f}\"" if diam is not None else "—",
                t("col_phase"):  f"{illum:.1f}" if illum is not None else "—",
            })

        st.dataframe(
            pd.DataFrame(main_rows),
            use_container_width=True,
            hide_index=True,
            height=374,
        )

        st.caption(t("caption_detail"))
        st.dataframe(
            pd.DataFrame(detail_rows),
            use_container_width=True,
            hide_index=True,
            height=374,
        )

    with tab_coord:
        from engines.coords_engine import get_all_coordinates as _get_coords, coords_to_rows as _coords_to_rows

        @st.cache_data(ttl=60, show_spinner=False)
        def _cached_coords(_lat, _lon, _elev, _name, _ts):
            _obs = Observer(lat=_lat, lon=_lon, elevation=_elev, name=_name)
            _t   = datetime.fromisoformat(_ts)
            return _coords_to_rows(_get_coords(_obs, _t))

        _coord_key = t.isoformat()
        _coord_rows = _cached_coords(
            float(lat), float(lon), float(elev),
            st.session_state.place_label or "Lieu", _coord_key
        )
        st.dataframe(
            pd.DataFrame(_coord_rows),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "Écliptiques de date · ICRF J2000 · Alt/Az topocentrique"
        )

    with tab_ecl:
        from engines.eclipse_engine import find_eclipses as _find_eclipses

        @st.cache_data(ttl=86400, show_spinner=True)
        def _cached_eclipses():
            return _find_eclipses()

        _solar, _lunar = _cached_eclipses()

        # ── Solaires ──────────────────────────────────────────────────
        st.markdown(t("solar_eclipses_title"))
        _TYPE_ICON = {
            "Totale": "⬛", "Annulaire": "🔴", "Hybride": "🟠",
            "Partielle": "🌗", "Partielle (rasante)": "🌘",
        }
        if _solar:
            _sol_rows = []
            for e in _solar:
                _sol_rows.append({
                    t("col_date"): e.dt_max.strftime("%Y-%m-%d"),
                    t("col_time"): e.dt_max.strftime("%H:%M") + " UTC",
                    t("col_type"): _TYPE_ICON.get(e.type, "") + " " + tr_eclipse_type(e.type),
                })
            st.dataframe(pd.DataFrame(_sol_rows), use_container_width=True,
                         hide_index=True)
        else:
            st.caption(t("no_solar_eclipse"))

        # ── Lunaires ──────────────────────────────────────────────────
        st.markdown(t("lunar_eclipses_title"))
        _LTYPE_ICON = {"Totale": "🔴", "Partielle": "🌗", "Pénombrale": "🌑"}
        if _lunar:
            _lun_rows = []
            for e in _lunar:
                tot = (f"{int(e.totality_min)} min"
                       if e.totality_min is not None else "—")
                _lun_rows.append({
                    t("col_date"):     e.dt_max.strftime("%Y-%m-%d"),
                    t("col_time"):     e.dt_max.strftime("%H:%M") + " UTC",
                    t("col_type"):     _LTYPE_ICON.get(e.type, "") + " " + tr_eclipse_type(e.type),
                    t("col_totality"): tot,
                })
            st.dataframe(pd.DataFrame(_lun_rows), use_container_width=True,
                         hide_index=True)
        else:
            st.caption(t("no_lunar_eclipse"))

        st.caption(t("eclipse_caption"))

    with tab_moon:
        from engines.moon_engine import (
            get_moon_info as _get_moon_info,
            find_moon_phases as _find_moon_phases,
        )

        # ── Phase courante ────────────────────────────────────────────
        from engines.moon_engine import render_moon_image as _render_moon
        _mi = _get_moon_info(t)

        # Rendu à midi UTC du jour sélectionné (cache module-level dans moon_engine)
        _moon_png = _render_moon(
            datetime(t.year, t.month, t.day, 12, 0, tzinfo=timezone.utc),
            observer_lat=observer.lat,
            observer_lon=observer.lon,
            size=300,
        )
        _col_img, _col_info = st.columns([1, 1], gap="small")
        with _col_img:
            st.image(_moon_png, width=300)
            st.caption(t("moon_zenith_caption"))
        with _col_info:
            st.markdown(
                f"""
                <div style="
                    padding:16px 12px; background:#06061a;
                    border-radius:8px; border:1px solid #1a2a4a;
                    height:100%; box-sizing:border-box;">
                    <div style="font-size:1.3rem; color:#aabbdd; margin-bottom:8px;">
                        {_mi['icon']}&nbsp; {tr_phase(_mi['phase_name'])}
                    </div>
                    <div style="color:#6677aa; font-size:0.88rem; line-height:1.9;">
                        {t("moon_illumination")}&nbsp;&nbsp;<b style="color:#99aacc">{_mi['illumination']:.1f}&nbsp;%</b><br>
                        {t("moon_age")}&nbsp;&nbsp;<b style="color:#99aacc">{_mi['age_days']:.1f}&nbsp;j</b><br>
                        {t("moon_elong")}&nbsp;&nbsp;<b style="color:#99aacc">{_mi['elong_deg']:.1f}°</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ── Prochaines phases ─────────────────────────────────────────
        @st.cache_data(ttl=1800, show_spinner=False)
        def _c_phases(_day: str) -> list:
            from datetime import date
            y, mo, d = [int(x) for x in _day.split("-")]
            t0 = datetime(y, mo, d, tzinfo=timezone.utc)
            return _find_moon_phases(t0, months=3)

        _phases = _c_phases(t.strftime("%Y-%m-%d"))
        if _phases:
            st.caption(t("phases_caption"))
            st.dataframe(
                pd.DataFrame([
                    {t("col_phase_name"): f"{p.icon} {tr_phase(p.name)}",
                     t("col_date"):       p.dt.strftime("%Y-%m-%d"),
                     t("col_utc"):        p.dt.strftime("%H:%M")}
                    for p in _phases
                ]),
                use_container_width=True,
                hide_index=True,
            )

    with tab_conj:
        from engines.moon_engine import (
            find_conjunctions as _find_conjunctions,
            PLANET_ICONS as _PLANET_ICONS,
        )

        @st.cache_data(ttl=3600, show_spinner=True)
        def _c_conj(_day: str) -> list:
            y, mo, d = [int(x) for x in _day.split("-")]
            t0 = datetime(y, mo, d, tzinfo=timezone.utc)
            return _find_conjunctions(t0)

        _conjs = _c_conj(t.strftime("%Y-%m-%d"))
        if _conjs:
            st.caption(t("conj_caption"))
            st.dataframe(
                pd.DataFrame([
                    {
                        t("col_date"):   e.dt.strftime("%Y-%m-%d"),
                        t("col_utc"):    e.dt.strftime("%H:%M"),
                        t("col_bodies"): (
                            f"{_PLANET_ICONS.get(e.body1,'⬤')} {tr_body(e.body1)}"
                            "  ·  "
                            f"{_PLANET_ICONS.get(e.body2,'⬤')} {tr_body(e.body2)}"
                        ),
                        t("col_sep"):    f"{e.separation_deg:.1f}°",
                    }
                    for e in _conjs
                ]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption(t("no_conj"))

    with tab_temps:
        from engines.time_engine import equation_of_time_curve as _eot_curve, gmst_hours as _gmst_hours
        import plotly.graph_objects as go

        ti = _time_info

        # ── Formateur heures décimales → H h MM m SS s ────────────────
        def _fmt_h(h: float) -> str:
            hh = int(h)
            mm = int((h % 1) * 60)
            ss = int(((h % 1) * 60 % 1) * 60)
            return f"{hh:02d}<sup>h</sup>{mm:02d}<sup>m</sup>{ss:02d}<sup>s</sup>"

        # Offset UTC de l'heure locale
        _loc_label = f"{ti.tz_name} (UTC{ti.utc_offset})"

        # ── Tableau des temps ──────────────────────────────────────────
        _time_rows = [
            {t("col_quantity"): t("time_utc_row"),
             t("col_value"):    ti.dt_utc.strftime("%Y-%m-%d  %H:%M:%S UTC")},
            {t("col_quantity"): t("time_local_row", loc=_loc_label),
             t("col_value"):    ti.dt_local.strftime("%Y-%m-%d  %H:%M:%S %Z")},
            {t("col_quantity"): t("jd_utc_row"),
             t("col_value"):    f"{ti.jd_utc:.6f}"},
            {t("col_quantity"): t("jd_tt_row"),
             t("col_value"):    f"{ti.jd_tt:.6f}"},
            {t("col_quantity"): t("delta_t_row"),
             t("col_value"):    f"{ti.delta_t_s:.2f} s"},
            {t("col_quantity"): t("gmst_row"),
             t("col_value"):    f"{int(ti.gmst_h):02d}h {int((ti.gmst_h % 1)*60):02d}m {int(((ti.gmst_h % 1)*60 % 1)*60):02d}s"},
            {t("col_quantity"): t("lst_row"),
             t("col_value"):    f"{tsl_h:02d}h {tsl_m:02d}m {tsl_s:02d}s"},
            {t("col_quantity"): t("eot_row"),
             t("col_value"):    f"{ti.eot_min:+.4f} min"},
        ]
        st.dataframe(
            pd.DataFrame(_time_rows),
            use_container_width=True,
            hide_index=True,
        )

        # ── Graphique équation du temps (courbe annuelle) ──────────────
        @st.cache_data(ttl=86400, show_spinner=False)
        def _cached_eot_curve(_year: int):
            return _eot_curve(_year)

        _year_sim = ti.dt_utc.year
        _eot_dates, _eot_vals = _cached_eot_curve(_year_sim)

        # Marqueur à la date de simulation
        _today_str = ti.dt_utc.strftime("%Y-%m-%d")
        _marker_eot = ti.eot_min

        _fig_eot = go.Figure()

        # Zone positive / négative (remplissage)
        _fig_eot.add_trace(go.Scatter(
            x=_eot_dates, y=_eot_vals,
            fill="tozeroy",
            fillcolor="rgba(100, 150, 255, 0.12)",
            line=dict(color="#6699ff", width=1.5),
            name=t("eot_row"),
            hovertemplate="%{x}<br>EoT : %{y:.2f} min<extra></extra>",
        ))

        # Ligne zéro
        _fig_eot.add_hline(y=0, line_color="#334466", line_width=1)

        # Marqueur date courante
        _fig_eot.add_trace(go.Scatter(
            x=[_today_str], y=[_marker_eot],
            mode="markers+text",
            marker=dict(color="#ffcc44", size=10, symbol="circle"),
            text=[f"  {_marker_eot:+.2f} min"],
            textposition="top right",
            textfont=dict(color="#ffcc44", size=11),
            name=t("eot_marker_label"),
            hovertemplate=f"{_today_str}<br>EoT : {_marker_eot:.2f} min<extra></extra>",
        ))

        # Ligne verticale date courante
        _fig_eot.add_vline(
            x=_today_str,
            line_color="#ffcc44",
            line_width=1,
            line_dash="dot",
        )

        _fig_eot.update_layout(
            title=dict(
                text=t("eot_chart_title", year=_year_sim),
                font=dict(color="#8899ff", size=14),
                x=0.5,
            ),
            paper_bgcolor="#05050f",
            plot_bgcolor="#07071a",
            font=dict(color="#8899bb"),
            margin=dict(l=50, r=20, t=50, b=40),
            height=280,
            xaxis=dict(
                showgrid=True,
                gridcolor="#111133",
                tickformat="%b",
                tickfont=dict(size=10),
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor="#111133",
                title=t("eot_y_axis"),
                tickfont=dict(size=10),
                zeroline=False,
            ),
            showlegend=False,
            hovermode="x unified",
        )
        st.plotly_chart(_fig_eot, use_container_width=True, config={"displayModeBar": False})
        st.caption(t("eot_caption"))

    with tab_crep:
        from engines.twilight_engine import get_solar_events as _get_solar, get_lunar_events as _get_lunar
        from zoneinfo import ZoneInfo as _ZI

        @st.cache_data(ttl=300, show_spinner=False)
        def _c_solar_events(_lat, _lon, _elev, _name, _day_str):
            _obs = Observer(lat=_lat, lon=_lon, elevation=_elev, name=_name)
            _dt = datetime.strptime(_day_str, "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
            return _get_solar(_obs, _dt), _get_lunar(_obs, _dt)

        _ti = _time_info
        _tz_crep = _ZI(_ti.tz_name)
        _day_key = t.strftime("%Y-%m-%d")
        _solar_evts, _lunar_evts = _c_solar_events(
            float(lat), float(lon), float(elev),
            st.session_state.place_label or "Lieu", _day_key
        )

        def _fmt_event_rows(events, tz, utc_offset_str):
            rows = []
            for ev in events:
                if ev.dt_utc is None:
                    rows.append({
                        t("col_event"):               tr_event(ev.label),
                        t("col_utc"):                 "—",
                        t("col_local_time", off=utc_offset_str): "—",
                        t("col_azimuth"):             "—",
                        t("col_altitude"):            "—",
                    })
                else:
                    dt_loc = ev.dt_utc.astimezone(tz)
                    az_s = f"{ev.az:.1f}°" if ev.az is not None else "—"
                    _is_transit = "méridien" in ev.label.lower() or "transit" in ev.label.lower()
                    alt_s = f"{ev.alt:+.1f}°" if ev.alt is not None and _is_transit else "—"
                    rows.append({
                        t("col_event"):               tr_event(ev.label),
                        t("col_utc"):                 ev.dt_utc.strftime("%H:%M"),
                        t("col_local_time", off=utc_offset_str): dt_loc.strftime("%H:%M"),
                        t("col_azimuth"):             az_s,
                        t("col_altitude"):            alt_s,
                    })
            return rows

        _off = _ti.utc_offset
        st.markdown(t("solar_events_title"))
        st.dataframe(
            pd.DataFrame(_fmt_event_rows(_solar_evts, _tz_crep, _off)),
            use_container_width=True,
            hide_index=True,
        )
        st.markdown(t("lunar_events_title"))
        st.dataframe(
            pd.DataFrame(_fmt_event_rows(_lunar_evts, _tz_crep, _off)),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(t("twilight_caption"))

    # Résumé rapide (hors onglet)
    nb_visible_bodies = sum(1 for b in planets_data if b["above_horizon"])
    nb_total_bodies   = len(planets_data)
    st.caption(t("summary_caption", n_stars=len(stars_df), mag=f"{mag_limit:.1f}",
                  n_vis=nb_visible_bodies, n_tot=nb_total_bodies))

# ─── Rafraîchissement automatique (temps réel) ───────────────────────────────

if realtime:
    time.sleep(30)
    st.rerun()
