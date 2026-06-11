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
from engines.i18n import t as _t, tr_body, tr_event, tr_phase, tr_eclipse_type, compass_dirs, months as _months
from renderers.eyepiece_chart import build_eyepiece_chart
from renderers.horizon_chart import build_horizon_chart

# ─── Configuration de la page ────────────────────────────────────────────────

st.set_page_config(
    page_title="NOCTILUM",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CSS — thème sombre ──────────────────────────────────────────────────────

st.markdown(
    """
    <style>
        /* Fond global */
        .stApp { background-color: #0a0a1a; color: #cccccc; }

        /* Masquer le bouton hamburger sidebar */
        [data-testid="collapsedControl"] { display: none !important; }
        section[data-testid="stSidebar"] { display: none !important; }

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
# ce qui permet à width="stretch" de recalculer la largeur correcte.
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
    "show_ecliptic":      False,
    "show_ecliptic_grid": False,
    "show_grid":          False,
    "show_messier":       False,
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
    "view_mode": "🌌 Zénith",
    "az_center": 180,
    # Langue
    "lang": "fr",
    "place_label":       "Observatoire de Paris",
    "_last_click_id":    None,
}
# Version d'état — changer cette valeur force une réinitialisation complète
_STATE_VERSION = "5.0-notabs"
if st.session_state.get("_noctilum_v") != _STATE_VERSION:
    for _k, _v in _DEFAULTS.items():
        st.session_state[_k] = _v
    st.session_state["_noctilum_v"] = _STATE_VERSION
    st.rerun()  # relance avant que les widgets puissent cacher leurs anciennes valeurs

# ─── Lecture des paramètres depuis session_state ─────────────────────────────
    # ── Sélecteur de langue ──


# Coordonnées du lieu
lat  = float(st.session_state.get("lat",  48.8362))
lon  = float(st.session_state.get("lon",   2.3362))
elev = float(st.session_state.get("elev", 60))

# Datetime d'observation (depuis session_state, avant le rendu des widgets)
_now_utc  = datetime.now(timezone.utc)
realtime  = bool(st.session_state.get("realtime", False))
_time_mode = st.session_state.get("time_mode", "UTC")

from engines.time_engine import get_timezone_name as _get_tz
from zoneinfo import ZoneInfo as _ZoneInfo
_tz_name = _get_tz(lat, lon)
_tz_zone = _ZoneInfo(_tz_name)

if realtime:
    obs_dt = _now_utc
elif _time_mode == "UTC":
    _d  = st.session_state.get("obs_date", _now_utc.date())
    _tm = st.session_state.get("obs_time", _now_utc.time().replace(second=0, microsecond=0))
    obs_dt = datetime.combine(_d, _tm, tzinfo=timezone.utc)
else:
    _d  = st.session_state.get("obs_date_loc", _now_utc.date())
    _tm = st.session_state.get("obs_time_loc", _now_utc.time().replace(second=0, microsecond=0))
    obs_dt = datetime.combine(_d, _tm).replace(tzinfo=_tz_zone).astimezone(timezone.utc)

# Catalogue d'étoiles + limite de magnitude
import engines.hipparcos_catalog as _hip
_hip_ok        = _hip.is_available()
_cat_choice    = st.session_state.get("star_catalog", "BSC5 (9 096 ★, mag ≤ 8)")
_use_hipparcos = _cat_choice.startswith("Hipparcos")
_max_mag       = 12.0 if _use_hipparcos else 8.0
mag_limit      = float(min(st.session_state.get("mag_limit_slider", 5.0), _max_mag))

# Sélection satellites
_sat_selected = []
_sat_trail    = float(st.session_state.get("sat_trail_min", 5))
if bool(st.session_state.get("show_satellites", False)):
    from engines.satellite_engine import GROUPS, list_satellites as _ls_pre
    _sg_pre    = st.session_state.get("sat_group", "ISS / Stations")
    _snames    = _ls_pre(_sg_pre)
    _SAT_PS    = 200
    if _snames:
        if st.session_state.get("sat_all", False):
            _pg = int(st.session_state.get("sat_page", 0))
            _npg = max(1, (len(_snames) - 1) // _SAT_PS + 1)
            _pg = max(0, min(_pg, _npg - 1))
            _sat_selected = _snames[_pg * _SAT_PS : (_pg + 1) * _SAT_PS]
        else:
            _sat_selected = list(st.session_state.get("sat_selected", []))


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
            if st.session_state.get("show_messier", False) else None
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
            "show_stars":        bool(st.session_state.get("show_stars",        True)),
            "show_planets":      bool(st.session_state.get("show_planets",      True)),
            "show_const_lines":  bool(st.session_state.get("show_const_lines",  True)),
            "show_const_names":  bool(st.session_state.get("show_const_names",  True)),
            "show_const_bounds": bool(st.session_state.get("show_const_bounds", False)),
            "show_ecliptic":      bool(st.session_state.get("show_ecliptic",      False)),
            "show_ecliptic_grid": bool(st.session_state.get("show_ecliptic_grid", False)),
            "show_grid":          bool(st.session_state.get("show_grid",          False)),
            "show_messier":       bool(st.session_state.get("show_messier",       False)),
            "show_milkyway":     bool(st.session_state.get("show_milkyway",     False)),
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

# ─── En-tête : titre + langue ────────────────────────────────────────────────

_hcol1, _hcol2 = st.columns([5, 3])
with _hcol1:
    st.markdown(
        f"""<div style="padding:6px 0 2px 0;">
            <span style="color:#8899ff; letter-spacing:0.3em; font-size:1.9rem; font-weight:700;">
                NOCTILUM
            </span>
            <span style="color:#6677aa; font-size:0.82em; margin-left:18px; letter-spacing:0.03em;">
                TSL&nbsp;{tsl_h:02d}<sup>h</sup>{tsl_m:02d}<sup>m</sup>{tsl_s:02d}<sup>s</sup>
                &nbsp;·&nbsp;UTC&nbsp;{t.strftime('%Y‑%m‑%d&nbsp;%H:%M')}
                &nbsp;·&nbsp;{observer.name}
            </span>
        </div>""",
        unsafe_allow_html=True,
    )
with _hcol2:
    st.radio(
        "🌐",
        ["fr", "en", "es", "zh", "hi"],
        format_func=lambda x: {"fr": "🇫🇷 fr", "en": "🇬🇧 en",
                                "es": "🇪🇸 es", "zh": "🇨🇳 中", "hi": "🇮🇳 हि"}[x],
        horizontal=True,
        key="lang",
        label_visibility="collapsed",
    )

# ─── Colonnes principales : carte (gauche) + onglets (droite) ────────────────

_VIEW_OPTS = ["🌌 Zénith", "🌄 Paysage", "🔭 Oculaire"]

col_chart, col_tabs = st.columns([3, 2], gap="medium")

# ── Carte du ciel ─────────────────────────────────────────────────────────────
with col_chart:
    # Barre vue
    _vc1, _vc2 = st.columns([3, 4])
    with _vc1:
        st.radio(
            "view", _VIEW_OPTS,
            format_func=lambda x: {
                "🌌 Zénith": _t("view_zenith"),
                "🌄 Paysage": _t("view_landscape"),
                "🔭 Oculaire": _t("view_eyepiece"),
            }[x],
            horizontal=True, key="view_mode", label_visibility="collapsed",
        )
    with _vc2:
        if _is_horizon:
            _vaz1, _vaz2 = st.columns([5, 2])
            with _vaz1:
                st.slider(_t("direction_label"), 0, 359, key="az_center",
                          format="%d°", label_visibility="collapsed")
            with _vaz2:
                st.markdown(
                    f"<div style='padding-top:8px;color:#8899aa;font-size:0.85em;'>"
                    f"↗ {_az_center}° {_az_to_compass(_az_center)}</div>",
                    unsafe_allow_html=True,
                )

    sky_fig = None
    try:
        if _is_eyepiece:
            sky_fig = build_eyepiece_chart(
                _alt_ep, _az_ep, _lbl_ep, _stars_ep, fov_deg=_fov,
                options=_display_options, planets_data=planets_data,
                messier_df=_messier_ep, observer=observer, t=t,
                satellites_data=_sat_data,
            )
        elif _is_horizon:
            sky_fig = build_horizon_chart(
                stars_df, planets_data, observer, t,
                az_center=float(_az_center), messier_df=messier_df,
                options=_display_options, satellites_data=_sat_data,
            )
        else:
            from renderers.sky_chart import build_sky_chart
            sky_fig = build_sky_chart(
                stars_df, planets_data, observer, t,
                messier_df=messier_df, options=_display_options,
                satellites_data=_sat_data,
            )
    except Exception as _fig_exc:
        import traceback as _tb
        st.error(_t("render_error", e=_fig_exc))
        st.code(_tb.format_exc())

    if sky_fig is not None:
        sky_fig.update_layout(width=None)
        _ep_key_suffix = (
            f"_ep_{_gross:.0f}_{_alt_ep:.2f}_{_az_ep:.2f}" if _is_eyepiece else ""
        )
        st.plotly_chart(
            sky_fig,
            width="stretch",
            config={"displayModeBar": False, "scrollZoom": _is_eyepiece},
            key=f"sky_{observer.lat:.4f}_{observer.lon:.4f}_{_view}_{_az_center}_{''.join(str(int(v)) for v in _display_options.values())}{_ep_key_suffix}",
        )

    with st.popover(_t("about_btn")):
        st.markdown(_t("about_text"))

# ── Onglets (colonne droite) ──────────────────────────────────────────────────
with col_tabs:
    # Corps triés : visibles d'abord, puis par altitude décroissante
    sorted_bodies = sorted(planets_data, key=lambda b: (not b["above_horizon"], -b["alt"]))

    (tab_lieu, tab_temps, tab_vue,
     tab_eph, tab_coord, tab_ecl, tab_moon, tab_conj, tab_crep) = st.tabs([
        _t("tab_lieu"), _t("tab_temps"), _t("tab_vue"),
        _t("tab_eph"), _t("tab_coord"), _t("tab_ecl"),
        _t("tab_moon"), _t("tab_conj"), _t("tab_crep"),
    ])

    # ── Onglet Lieu ──────────────────────────────────────────────────────────────

    with tab_lieu:

        def _reverse_geocode(_rlat: float, _rlon: float) -> str:
            try:
                _r = requests.get(
                    "https://nominatim.openstreetmap.org/reverse",
                    params={"lat": _rlat, "lon": _rlon, "format": "json", "zoom": 10},
                    headers={"User-Agent": "NOCTILUM/1.0"}, timeout=6,
                ).json()
                _a = _r.get("address", {})
                return (_a.get("city") or _a.get("town") or _a.get("village")
                        or _a.get("county")
                        or _r.get("display_name", "").split(",")[0] or "")
            except Exception:
                return ""

        def _get_elevation(_elat: float, _elon: float) -> int:
            try:
                _r = requests.get(
                    "https://api.open-meteo.com/v1/elevation",
                    params={"latitude": _elat, "longitude": _elon}, timeout=5,
                ).json()
                _v = _r.get("elevation", [None])[0]
                return max(0, int(round(_v))) if _v is not None else 0
            except Exception:
                return 0

        # Recherche Nominatim
        _lc1, _lc2 = st.columns([5, 1])
        with _lc1:
            _search_q = st.text_input(
                "Lieu", value=st.session_state.get("place_label", ""),
                placeholder="Paris, Londres, Tokyo…", label_visibility="collapsed",
            )
        with _lc2:
            _do_search = st.button("🔍", width="stretch")

        if _do_search and _search_q.strip():
            try:
                _geo = requests.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": _search_q, "format": "json", "limit": 1},
                    headers={"User-Agent": "NOCTILUM/1.0"}, timeout=8,
                ).json()
                if _geo:
                    _slat = round(float(_geo[0]["lat"]), 4)
                    _slon = round(float(_geo[0]["lon"]), 4)
                    st.session_state.lat         = _slat
                    st.session_state.lon         = _slon
                    st.session_state.elev        = _get_elevation(_slat, _slon)
                    st.session_state.place_label = (
                        _geo[0].get("display_name", "").split(",")[0].strip()
                        or _search_q.strip().title()
                    )
                else:
                    st.caption(_t("place_not_found"))
            except Exception:
                st.caption(_t("geocode_error"))

        # Carte Folium
        _clat = float(st.session_state.lat)
        _clon = float(st.session_state.lon)
        _fmap = folium.Map(location=[_clat, _clon], zoom_start=5, tiles=None)
        _fmap.options["attributionControl"] = False
        folium.TileLayer(
            tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
            attr=" ", control=False,
        ).add_to(_fmap)
        folium.Marker(
            [_clat, _clon],
            tooltip=st.session_state.place_label or f"{_clat:.4f}°, {_clon:.4f}°",
            icon=folium.Icon(color="blue", icon="star", prefix="fa"),
        ).add_to(_fmap)
        _map_result = st_folium(
            _fmap, height=380, use_container_width=True,
            returned_objects=["last_clicked"], key="folium_map",
        )
        _clicked = (_map_result or {}).get("last_clicked")
        if _clicked:
            _nlat = round(_clicked["lat"], 4)
            _nlon = round(((float(_clicked["lng"]) + 180) % 360) - 180, 4)
            _cid  = (_nlat, _nlon)
            if _cid != st.session_state.get("_last_click_id"):
                st.session_state._last_click_id = _cid
                st.session_state.lat         = _nlat
                st.session_state.lon         = _nlon
                st.session_state.elev        = _get_elevation(_nlat, _nlon)
                st.session_state.place_label = _reverse_geocode(_nlat, _nlon) or f"{_nlat:.4f}°, {_nlon:.4f}°"
                st.rerun()

        _lc3, _lc4, _lc5 = st.columns(3)
        with _lc3:
            st.number_input("Lat °N", key="lat", min_value=-90.0, max_value=90.0,
                            step=0.0001, format="%.4f")
        with _lc4:
            st.number_input("Lon °E", key="lon", min_value=-180.0, max_value=180.0,
                            step=0.0001, format="%.4f")
        with _lc5:
            st.number_input("Alt m", key="elev", min_value=0, max_value=8848,
                            step=1, format="%d")
        st.button(_t("btn_refresh"))

    # ── Onglet Vue ────────────────────────────────────────────────────────────────

    with tab_vue:
        _vc_l, _vc_r = st.columns(2)

        with _vc_l:
            st.subheader(_t("section_stars"))
            _cat_opts = ["BSC5 (9 096 ★, mag ≤ 8)"]
            if _hip_ok:
                _cat_opts.append("Hipparcos (118 218 ★, mag ≤ 12)")
            st.radio("Catalogue", _cat_opts, key="star_catalog", label_visibility="collapsed")
            if not _hip_ok:
                if st.button(_t("btn_download_hip")):
                    _prog = st.progress(0.0, text=_t("downloading"))
                    try:
                        _hip.download(progress_cb=lambda f: _prog.progress(f, text=f"{_t('downloading')} {f*100:.0f}%"))
                        _prog.empty()
                        st.success(_t("hip_downloaded"))
                    except Exception as _e:
                        _prog.empty()
                        st.error(_t("error_prefix", e=_e))
            st.slider(
                _t("mag_limit_label"), min_value=1.0, max_value=_max_mag,
                value=float(min(st.session_state.get("mag_limit_slider", 5.0), _max_mag)),
                step=0.5, key="mag_limit_slider",
                help=_t("mag_help") + (_t("mag_help_eyepiece") if _use_hipparcos else ""),
            )
            if _is_eyepiece:
                st.divider()
                st.subheader(_t("section_view"))
                _ep_target_now = st.session_state.get("_eyepiece_target")
                _ep_label_v = getattr(_ep_target_now, "label", "") if _ep_target_now else ""
                _ep_ll = _ep_label_v.lower()
                if "lune" in _ep_ll or "moon" in _ep_ll:
                    _bc = next((p for p in st.session_state.get("_planets_cache", []) if p["name"] == "Lune"), None)
                    _dd = 1842.0
                elif "soleil" in _ep_ll or "sun" in _ep_ll:
                    _bc = next((p for p in st.session_state.get("_planets_cache", []) if p["name"] == "Soleil"), None)
                    _dd = 1919.0
                else:
                    _bc, _dd = None, None
                if _dd is not None:
                    _diam_d = ((_bc.get("ang_diam_arcsec") or _dd) / 3600.0) if _bc else (_dd / 3600.0)
                    _mg = max(10, (int(60.0 / _diam_d) // 5) * 5)
                else:
                    _mg = 300
                _cg = int(st.session_state.get("eyepiece_gross", 80))
                if _cg > _mg:
                    st.session_state["eyepiece_gross"] = _mg
                st.slider(_t("magnification_label"), 10, _mg, min(80, _mg), step=5,
                          key="eyepiece_gross", format="×%d")
                _fov_p = 60.0 / st.session_state.get("eyepiece_gross", 80)
                st.caption(_t("fov_caption", fov=_fov_p))
                st.text_input(_t("search_object"), key="search_query",
                              placeholder="Sirius, M42, Andromède, Jupiter…")
                _sq = st.session_state.get("search_query", "").strip()
                if _sq:
                    from engines.search_catalog import search as _search
                    _cp = st.session_state.get("_planets_cache", [])
                    _res = _search(_sq, _cp)
                    if _res:
                        _oi = [f"{tr_body(r.label)} — {r.description}" for r in _res]
                        _ch = st.selectbox("", _oi, key="search_choice", label_visibility="collapsed")
                        st.session_state["_eyepiece_target"] = _res[_oi.index(_ch)]
                    else:
                        st.caption(_t("no_results"))

        with _vc_r:
            st.subheader(_t("section_display"))
            st.checkbox(_t("show_stars_label"),        key="show_stars")
            st.checkbox(_t("show_planets_label"),      key="show_planets")
            st.checkbox(_t("show_milkyway_label"),     key="show_milkyway")
            st.checkbox(_t("show_const_lines_label"),  key="show_const_lines")
            st.checkbox(_t("show_const_names_label"),  key="show_const_names")
            st.checkbox(_t("show_const_bounds_label"), key="show_const_bounds")
            st.checkbox(_t("show_ecliptic_label"),     key="show_ecliptic")
            st.checkbox(_t("show_ecliptic_grid_label"), key="show_ecliptic_grid")
            st.checkbox(_t("show_grid_label"),         key="show_grid")

        # ── Messier ──────────────────────────────────────────────────────────
        st.divider()
        st.checkbox(_t("show_messier_label"), key="show_messier")
        if st.session_state.get("show_messier"):
            st.markdown(
                f"""<div style="font-size:11px;line-height:2;padding-left:20px;color:#999">
                  <span style="color:#FFB347;font-size:14px">○</span>&nbsp;{_t("messier_galaxy")}<br>
                  <span style="color:#90EE90;font-size:14px">✳</span>&nbsp;{_t("messier_open")}<br>
                  <span style="color:#7CFC00;font-size:14px">⊕</span>&nbsp;{_t("messier_globular")}<br>
                  <span style="color:#87CEEB;font-size:14px">◇</span>&nbsp;{_t("messier_nebula")}<br>
                  <span style="color:#DDA0DD;font-size:14px">⊙</span>&nbsp;{_t("messier_planetary")}<br>
                  <span style="color:#FF7F7F;font-size:14px">△</span>&nbsp;{_t("messier_snr")}
                </div>""",
                unsafe_allow_html=True,
            )

        # ── Satellites ───────────────────────────────────────────────────────
        st.subheader(_t("section_satellites"))
        st.checkbox(_t("show_satellites_label"), key="show_satellites")
        if st.session_state.get("show_satellites"):
            from engines.satellite_engine import GROUPS, list_satellites
            _sat_g = st.selectbox(_t("sat_group_label"), list(GROUPS.keys()), key="sat_group")
            st.slider(_t("sat_trail_label"), 1, 15, 5, key="sat_trail_min")
            if st.session_state.get("_prev_sat_group") != _sat_g:
                st.session_state["sat_page"] = 0
                st.session_state["_prev_sat_group"] = _sat_g
            with st.spinner("Chargement TLE…"):
                try:
                    _sn = list_satellites(_sat_g)
                except Exception:
                    _sn = []
            if _sn:
                _sl = len(_sn) > 200
                st.checkbox(_t("sat_all_label"), key="sat_all")
                if st.session_state.get("sat_all") and _sl:
                    _np = (len(_sn) - 1) // 200 + 1
                    _pg2 = max(0, min(int(st.session_state.get("sat_page", 0)), _np - 1))
                    st.caption(_t("sat_page_info", n=len(_sn), p=_pg2+1, total=_np))
                    _bc1, _bc2 = st.columns(2)
                    if _bc1.button(_t("sat_prev_btn"), disabled=_pg2 == 0, width="stretch"):
                        st.session_state["sat_page"] = _pg2 - 1; st.rerun()
                    if _bc2.button(_t("sat_next_btn"), disabled=_pg2 == _np - 1, width="stretch"):
                        st.session_state["sat_page"] = _pg2 + 1; st.rerun()
                elif not st.session_state.get("sat_all"):
                    st.multiselect(_t("sat_selection_label"), _sn, default=[],
                                   key="sat_selected", placeholder=_t("sat_placeholder"))
            else:
                st.caption(_t("sat_load_error"))



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
                _t("col_body"):    prefix + icon + " " + tr_body(body["name"]),
                "Alt":            f"{body['alt']:+.1f}°",
                "Az":             f"{body['az']:.1f}°",
                "Mag":            f"{mag:.1f}" if mag is not None else "—",
                _t("col_rise"):    body["rise"],
                _t("col_transit"): body.get("transit", "—"),
                _t("col_set"):     body["set"],
                _t("col_elong"):   f"{elong:.0f}°" if elong is not None else "—",
            })

            dist   = body.get("distance_au")
            diam   = body.get("ang_diam_arcsec")
            illum  = body.get("illumination")
            detail_rows.append({
                _t("col_body"):   icon + " " + tr_body(body["name"]),
                _t("col_dist"):   f"{dist:.4f}" if dist is not None else "—",
                _t("col_diam"):   f"{diam:.1f}\"" if diam is not None else "—",
                _t("col_phase"):  f"{illum:.1f}" if illum is not None else "—",
            })

        st.dataframe(
            pd.DataFrame(main_rows),
            width="stretch",
            hide_index=True,
            height=374,
        )

        st.caption(_t("caption_detail"))
        st.dataframe(
            pd.DataFrame(detail_rows),
            width="stretch",
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
            width="stretch",
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
        st.markdown(_t("solar_eclipses_title"))
        _TYPE_ICON = {
            "Totale": "⬛", "Annulaire": "🔴", "Hybride": "🟠",
            "Partielle": "🌗", "Partielle (rasante)": "🌘",
        }
        if _solar:
            _sol_rows = []
            for e in _solar:
                _sol_rows.append({
                    _t("col_date"): e.dt_max.strftime("%Y-%m-%d"),
                    _t("col_time"): e.dt_max.strftime("%H:%M") + " UTC",
                    _t("col_type"): _TYPE_ICON.get(e.type, "") + " " + tr_eclipse_type(e.type),
                })
            st.dataframe(pd.DataFrame(_sol_rows), width="stretch",
                         hide_index=True)
        else:
            st.caption(_t("no_solar_eclipse"))

        # ── Lunaires ──────────────────────────────────────────────────
        st.markdown(_t("lunar_eclipses_title"))
        _LTYPE_ICON = {"Totale": "🔴", "Partielle": "🌗", "Pénombrale": "🌑"}
        if _lunar:
            _lun_rows = []
            for e in _lunar:
                tot = (f"{int(e.totality_min)} min"
                       if e.totality_min is not None else "—")
                _lun_rows.append({
                    _t("col_date"):     e.dt_max.strftime("%Y-%m-%d"),
                    _t("col_time"):     e.dt_max.strftime("%H:%M") + " UTC",
                    _t("col_type"):     _LTYPE_ICON.get(e.type, "") + " " + tr_eclipse_type(e.type),
                    _t("col_totality"): tot,
                })
            st.dataframe(pd.DataFrame(_lun_rows), width="stretch",
                         hide_index=True)
        else:
            st.caption(_t("no_lunar_eclipse"))

        st.caption(_t("eclipse_caption"))

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
            st.caption(_t("moon_zenith_caption"))
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
                        {_t("moon_illumination")}&nbsp;&nbsp;<b style="color:#99aacc">{_mi['illumination']:.1f}&nbsp;%</b><br>
                        {_t("moon_age")}&nbsp;&nbsp;<b style="color:#99aacc">{_mi['age_days']:.1f}&nbsp;j</b><br>
                        {_t("moon_elong")}&nbsp;&nbsp;<b style="color:#99aacc">{_mi['elong_deg']:.1f}°</b>
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
            st.caption(_t("phases_caption"))
            st.dataframe(
                pd.DataFrame([
                    {_t("col_phase_name"): f"{p.icon} {tr_phase(p.name)}",
                     _t("col_date"):       p.dt.strftime("%Y-%m-%d"),
                     _t("col_utc"):        p.dt.strftime("%H:%M")}
                    for p in _phases
                ]),
                width="stretch",
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
            st.caption(_t("conj_caption"))
            st.dataframe(
                pd.DataFrame([
                    {
                        _t("col_date"):   e.dt.strftime("%Y-%m-%d"),
                        _t("col_utc"):    e.dt.strftime("%H:%M"),
                        _t("col_bodies"): (
                            f"{_PLANET_ICONS.get(e.body1,'⬤')} {tr_body(e.body1)}"
                            "  ·  "
                            f"{_PLANET_ICONS.get(e.body2,'⬤')} {tr_body(e.body2)}"
                        ),
                        _t("col_sep"):    f"{e.separation_deg:.1f}°",
                    }
                    for e in _conjs
                ]),
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption(_t("no_conj"))

    with tab_temps:
        from engines.time_engine import equation_of_time_curve as _eot_curve, gmst_hours as _gmst_hours
        import plotly.graph_objects as go

        # ── Contrôles date / heure ─────────────────────────────────────
        _tc1, _tc2, _tc3 = st.columns([2, 3, 3])
        with _tc1:
            st.checkbox(_t("realtime_label"), key="realtime")
        if not realtime:
            # Détection changement UTC ↔ Locale
            _prev_mode = st.session_state.get("_prev_time_mode", "UTC")
            _cur_mode  = st.session_state.get("time_mode", "UTC")
            if _prev_mode != _cur_mode:
                if _cur_mode == "Locale":
                    _us = datetime.combine(st.session_state["obs_date"],
                                           st.session_state["obs_time"], tzinfo=timezone.utc)
                    _li = _us.astimezone(_tz_zone)
                    st.session_state["obs_date_loc"] = _li.date()
                    st.session_state["obs_time_loc"] = _li.time().replace(second=0, microsecond=0)
                else:
                    _ls = datetime.combine(st.session_state["obs_date_loc"],
                                           st.session_state["obs_time_loc"]
                                           ).replace(tzinfo=_tz_zone).astimezone(timezone.utc)
                    st.session_state["obs_date"] = _ls.date()
                    st.session_state["obs_time"] = _ls.time().replace(second=0, microsecond=0)
                st.session_state["_prev_time_mode"] = _cur_mode

            with _tc2:
                st.radio("ref", ["UTC", "Locale"],
                         format_func=lambda x: x if x == "UTC" else _t("time_local_option"),
                         horizontal=True, key="time_mode", label_visibility="collapsed")
            with _tc3:
                if st.session_state.get("time_mode", "UTC") == "UTC":
                    _dc1, _dc2 = st.columns(2)
                    with _dc1:
                        st.date_input(_t("date_utc"), key="obs_date", label_visibility="collapsed")
                    with _dc2:
                        st.time_input(_t("time_utc"), key="obs_time", step=60, label_visibility="collapsed")
                else:
                    _dc1, _dc2 = st.columns(2)
                    with _dc1:
                        st.date_input(f"Date ({_tz_name})", key="obs_date_loc", label_visibility="collapsed")
                    with _dc2:
                        st.time_input(f"Heure ({_tz_name})", key="obs_time_loc", step=60, label_visibility="collapsed")
        else:
            with _tc2:
                _now_l = _now_utc.astimezone(_tz_zone)
                st.caption(f"UTC {_now_utc.strftime('%Y-%m-%d %H:%M:%S')}  ·  {_tz_name} {_now_l.strftime('%H:%M:%S %Z')}")

        st.divider()

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
            {_t("col_quantity"): _t("time_utc_row"),
             _t("col_value"):    ti.dt_utc.strftime("%Y-%m-%d  %H:%M:%S UTC")},
            {_t("col_quantity"): _t("time_local_row", loc=_loc_label),
             _t("col_value"):    ti.dt_local.strftime("%Y-%m-%d  %H:%M:%S %Z")},
            {_t("col_quantity"): _t("jd_utc_row"),
             _t("col_value"):    f"{ti.jd_utc:.6f}"},
            {_t("col_quantity"): _t("jd_tt_row"),
             _t("col_value"):    f"{ti.jd_tt:.6f}"},
            {_t("col_quantity"): _t("delta_t_row"),
             _t("col_value"):    f"{ti.delta_t_s:.2f} s"},
            {_t("col_quantity"): _t("gmst_row"),
             _t("col_value"):    f"{int(ti.gmst_h):02d}h {int((ti.gmst_h % 1)*60):02d}m {int(((ti.gmst_h % 1)*60 % 1)*60):02d}s"},
            {_t("col_quantity"): _t("lst_row"),
             _t("col_value"):    f"{tsl_h:02d}h {tsl_m:02d}m {tsl_s:02d}s"},
            {_t("col_quantity"): _t("eot_row"),
             _t("col_value"):    f"{ti.eot_min:+.4f} min"},
        ]
        st.dataframe(
            pd.DataFrame(_time_rows),
            width="stretch",
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
            name=_t("eot_row"),
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
            name=_t("eot_marker_label"),
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
                text=_t("eot_chart_title", year=_year_sim),
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
                tickvals=[f"{_year_sim}-{m:02d}-01" for m in range(1, 13)],
                ticktext=_months(),
                tickfont=dict(size=10),
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor="#111133",
                title=_t("eot_y_axis"),
                tickfont=dict(size=10),
                zeroline=False,
            ),
            showlegend=False,
            hovermode="x unified",
        )
        st.plotly_chart(_fig_eot, width="stretch", config={"displayModeBar": False})
        st.caption(_t("eot_caption"))

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
                        _t("col_event"):               tr_event(ev.label),
                        _t("col_utc"):                 "—",
                        _t("col_local_time", off=utc_offset_str): "—",
                        _t("col_azimuth"):             "—",
                        _t("col_altitude"):            "—",
                    })
                else:
                    dt_loc = ev.dt_utc.astimezone(tz)
                    az_s = f"{ev.az:.1f}°" if ev.az is not None else "—"
                    _is_transit = "méridien" in ev.label.lower() or "transit" in ev.label.lower()
                    alt_s = f"{ev.alt:+.1f}°" if ev.alt is not None and _is_transit else "—"
                    rows.append({
                        _t("col_event"):               tr_event(ev.label),
                        _t("col_utc"):                 ev.dt_utc.strftime("%H:%M"),
                        _t("col_local_time", off=utc_offset_str): dt_loc.strftime("%H:%M"),
                        _t("col_azimuth"):             az_s,
                        _t("col_altitude"):            alt_s,
                    })
            return rows

        _off = _ti.utc_offset
        st.markdown(_t("solar_events_title"))
        st.dataframe(
            pd.DataFrame(_fmt_event_rows(_solar_evts, _tz_crep, _off)),
            width="stretch",
            hide_index=True,
        )
        st.markdown(_t("lunar_events_title"))
        st.dataframe(
            pd.DataFrame(_fmt_event_rows(_lunar_evts, _tz_crep, _off)),
            width="stretch",
            hide_index=True,
        )
        st.caption(_t("twilight_caption"))

    # Résumé rapide (hors onglet)
    nb_visible_bodies = sum(1 for b in planets_data if b["above_horizon"])
    nb_total_bodies   = len(planets_data)
    st.caption(_t("summary_caption", n_stars=len(stars_df), mag=f"{mag_limit:.1f}",
                  n_vis=nb_visible_bodies, n_tot=nb_total_bodies))

# ─── Rafraîchissement automatique (temps réel) ───────────────────────────────

if realtime:
    time.sleep(30)
    st.rerun()
