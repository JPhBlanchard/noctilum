"""
Internationalisation — NOCTILUM.
Langues : fr (défaut), en, es, zh, hi.

API publique :
  t(key, **kwargs)            – chaîne UI traduite
  tr_body(fr_name)            – nom de corps céleste traduit
  tr_event(fr_label)          – label d'événement (crépuscule) traduit
  tr_phase(fr_name)           – phase lunaire traduite
  tr_eclipse_type(fr_type)    – type d'éclipse traduit
  compass_dirs()              – liste des 16 points cardinaux [(angle, label)]
"""

from __future__ import annotations
import streamlit as st

# ─── Points cardinaux ────────────────────────────────────────────────────────

_COMPASS: dict[str, list[tuple[int, str]]] = {
    "fr": [
        (0,"N"),(22,"NNE"),(45,"NE"),(67,"ENE"),
        (90,"E"),(112,"ESE"),(135,"SE"),(157,"SSE"),
        (180,"S"),(202,"SSO"),(225,"SO"),(247,"OSO"),
        (270,"O"),(292,"ONO"),(315,"NO"),(337,"NNO"),
    ],
    "en": [
        (0,"N"),(22,"NNE"),(45,"NE"),(67,"ENE"),
        (90,"E"),(112,"ESE"),(135,"SE"),(157,"SSE"),
        (180,"S"),(202,"SSW"),(225,"SW"),(247,"WSW"),
        (270,"W"),(292,"WNW"),(315,"NW"),(337,"NNW"),
    ],
    "es": [
        (0,"N"),(22,"NNE"),(45,"NE"),(67,"ENE"),
        (90,"E"),(112,"ESE"),(135,"SE"),(157,"SSE"),
        (180,"S"),(202,"SSO"),(225,"SO"),(247,"OSO"),
        (270,"O"),(292,"ONO"),(315,"NO"),(337,"NNO"),
    ],
    "zh": [
        (0,"北"),(22,"北北东"),(45,"东北"),(67,"东北东"),
        (90,"东"),(112,"东南东"),(135,"东南"),(157,"南南东"),
        (180,"南"),(202,"南南西"),(225,"西南"),(247,"西南西"),
        (270,"西"),(292,"西北西"),(315,"西北"),(337,"北北西"),
    ],
    "hi": [
        (0,"उ"),(22,"उउपू"),(45,"उपू"),(67,"पूउ"),
        (90,"पू"),(112,"पूद"),(135,"दपू"),(157,"ददपू"),
        (180,"द"),(202,"ददप"),(225,"दप"),(247,"पद"),
        (270,"प"),(292,"पउ"),(315,"उप"),(337,"उउप"),
    ],
}

# ─── Traductions principales ─────────────────────────────────────────────────

_T: dict[str, dict[str, str]] = {

# ══════════════════════════════════════════════════════════════════════════════
"fr": {
    # Sélecteur de langue
    "lang_label": "🌐 Langue",
    # Sidebar
    "settings_title":       "⚙ Paramètres",
    "section_location":     "📍 Lieu",
    "map_picker":           "🗺 Choisir sur la carte",
    "place_not_found":      "Lieu non trouvé.",
    "geocode_error":        "Erreur de géocodage.",
    "btn_refresh":          "🔄 Actualiser",
    "section_datetime":     "🕐 Date & Heure",
    "realtime_label":       "⏱ Temps réel",
    "time_local_option":    "Locale",
    "date_utc":             "Date (UTC)",
    "time_utc":             "Heure (UTC)",
    "section_stars":        "🔭 Étoiles",
    "btn_download_hip":     "⬇ Télécharger Hipparcos (~55 Mo)",
    "downloading":          "Téléchargement…",
    "hip_downloaded":       "Hipparcos téléchargé — rechargez la page.",
    "error_prefix":         "Échec : {e}",
    "mag_limit_label":      "Magnitude limite",
    "mag_help":             "Ciel parfait ≈ 6.5 · Ciel urbain ≈ 4.0–5.0",
    "mag_help_eyepiece":    " · Oculaire ≈ 10–12",
    "section_view":         "👁 Vue",
    "view_zenith":          "🌌 Zénith",
    "view_landscape":       "🌄 Paysage",
    "view_eyepiece":        "🔭 Oculaire",
    "direction_label":      "Direction (az.)",
    "magnification_label":  "Grossissement ×",
    "fov_caption":          "Champ réel ≈ {fov:.2f}°  (champ apparent 60°)",
    "search_object":        "🔍 Objet",
    "no_results":           "Aucun résultat.",
    "section_display":      "🗺 Affichage",
    "show_stars_label":     "Étoiles",
    "show_planets_label":   "Planètes",
    "show_milkyway_label":  "Voie Lactée",
    "show_const_lines_label":  "Lignes de constellations",
    "show_const_names_label":  "Noms de constellations",
    "show_const_bounds_label": "Limites de constellations",
    "show_ecliptic_label":       "Plan de l'écliptique",
    "show_ecliptic_grid_label":  "Grille écliptique",
    "show_grid_label":           "Méridiens & parallèles",
    "show_messier_label":   "Objets de Messier",
    "messier_galaxy":       "Galaxie",
    "messier_open":         "Amas ouvert",
    "messier_globular":     "Amas globulaire",
    "messier_nebula":       "Nébuleuse",
    "messier_planetary":    "Nébuleuse planétaire",
    "messier_snr":          "Rémanent de supernova",
    "section_satellites":   "🛰 Satellites",
    "show_satellites_label":"Satellites artificiels",
    "sat_group_label":      "Groupe",
    "sat_trail_label":      "Trajectoire (±min)",
    "sat_all_label":        "Tous les satellites du groupe",
    "sat_prev_btn":         "◀ Préc.",
    "sat_next_btn":         "Suiv. ▶",
    "sat_page_info":        "{n} satellites · page {p}/{total}",
    "sat_large_warning":    "⚠ Groupe volumineux ({n} satellites) — limité aux {cap} premiers.",
    "sat_selection_label":  "Satellites",
    "sat_placeholder":      "Choisir… (vide = aucun)",
    "sat_load_error":       "Impossible de charger les TLE.",
    # Onglets
    "tab_lieu":     "📍 Lieu",
    "tab_temps":    "🕐 Temps",
    "tab_vue":      "👁 Vue",
    "tab_eph":      "Éphémérides",
    "tab_coord":    "Coordonnées",
    "tab_ecl":      "Éclipses",
    "tab_moon":     "Lune",
    "tab_conj":     "Rapprochements",
    "tab_crep":     "Crépuscules",
    # Éphémérides
    "col_body":     "Astre",
    "col_rise":     "Lever",
    "col_transit":  "Transit",
    "col_set":      "Coucher",
    "col_elong":    "Élong.",
    "col_dist":     "Dist. (UA)",
    "col_diam":     "Diam. (\")",
    "col_phase":    "Phase (%)",
    "caption_detail": "Distance · Diamètre apparent · Phase",
    # Éclipses
    "solar_eclipses_title": "**☀ Éclipses solaires** — 3 prochaines années",
    "lunar_eclipses_title": "**🌕 Éclipses lunaires** — 3 prochaines années",
    "col_date":     "Date",
    "col_time":     "Heure",
    "col_type":     "Type",
    "col_totality": "Totalité",
    "no_solar_eclipse": "Aucune éclipse solaire détectée sur la période.",
    "no_lunar_eclipse": "Aucune éclipse lunaire détectée sur la période.",
    "eclipse_caption": "Heures UTC du maximum · éclipses solaires visibles sur une partie du globe seulement",
    # Lune
    "moon_zenith_caption": "Zénith ↑ (angle parallactique)",
    "moon_illumination":   "Illumination",
    "moon_age":            "Âge",
    "moon_elong":          "Élongation",
    "phases_caption":      "Phases — 3 prochains mois",
    "col_phase_name":      "Phase",
    "col_utc":             "UTC",
    # Rapprochements
    "col_bodies":   "Corps",
    "col_sep":      "Sep.",
    "conj_caption": "Lune–planète (< 5°) · planète–planète (< 2°) — 3 prochains mois",
    "no_conj":      "Aucun rapprochement notable sur 3 mois.",
    # Temps
    "col_quantity": "Grandeur",
    "col_value":    "Valeur",
    "time_utc_row":    "Date & Heure UTC",
    "time_local_row":  "Date & Heure locale ({loc})",
    "jd_utc_row":      "Jour Julien (JD UTC)",
    "jd_tt_row":       "Jour Julien (JD TT)",
    "delta_t_row":     "ΔT  (TT − UTC)",
    "gmst_row":        "TSMG — Temps Sidéral Moyen Greenwich",
    "lst_row":         "TSL — Temps Sidéral Local",
    "eot_row":         "Équation du temps",
    "eot_chart_title": "Équation du temps — {year}",
    "eot_y_axis":      "minutes",
    "eot_marker_label":"Date simulée",
    "eot_caption":     "EoT positive → le Soleil transit avant 12h00 solaire moyen · Formule analytique (Meeus) · précision ≈ 0.5 min",
    # Crépuscules
    "solar_events_title": "**☀ Soleil**",
    "lunar_events_title": "**🌙 Lune**",
    "col_event":    "Événement",
    "col_local_time": "Locale ({off})",
    "col_azimuth":  "Azimut",
    "col_altitude": "Hauteur",
    "twilight_caption": "Civil −6° · Nautique −12° · Astronomique −18° · Hauteur affichée uniquement au passage du méridien",
    # Résumé
    "summary_caption": "🌟 {n_stars} étoiles visibles (mag ≤ {mag})  ·  🪐 {n_vis}/{n_tot} corps au-dessus de l'horizon",
    # Erreurs / spinners
    "render_error":       "Erreur de rendu : {e}",
    "loading_bsc5":       "Chargement du catalogue BSC5…",
    "computing_eclipses": "Calcul des éclipses…",
    "computing_conj":     "Calcul des rapprochements…",
    # À propos
    "about_btn": "ℹ️ À propos",
    "about_text": """\
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
- Voie Lactée : *mw.json* (polygones de densité galactique) — d3-celestial / Olaf Frohn
- Catalogue Messier : données IAU / SEDS
- Satellites artificiels : TLE Celestrak (stations, Starlink, OneWeb, météo, science, amateur, GPS) — rafraîchis toutes les 6 h
- Fond cartographique : CartoDB Dark Matter · © OpenStreetMap contributors
- Géocodage : Nominatim (OpenStreetMap)

---

**Vues disponibles**
- 🌌 Zénith — projection stéréographique azimutale centrée sur le zénith
- 🌄 Paysage — projection équirectangulaire (azimut × altitude) vers l'horizon
- 🔭 Oculaire — champ télescopique centré sur une cible, projection gnomonique vraie

**Satellites artificiels**
Positions et trajectoires calculées en temps réel via Skyfield à partir des TLE Celestrak.
La trajectoire affichée couvre ±5 min autour de l'instant courant (paramétrable).
Seuls les satellites au-dessus de l'horizon sont visibles sur les cartes.

---

> ⚠️ **Redimensionnement de la fenêtre** — le graphique s'adapte automatiquement
> lors de chaque recalcul. Si la mise en page ne suit pas après un changement de
> taille de fenêtre, modifiez n'importe quel paramètre (magnitude, heure…)
> ou activez le mode **Temps réel** pour forcer le recalcul.
""",
},  # /fr

# ══════════════════════════════════════════════════════════════════════════════
"en": {
    "lang_label": "🌐 Language",
    "settings_title":       "⚙ Settings",
    "section_location":     "📍 Location",
    "map_picker":           "🗺 Choose on map",
    "place_not_found":      "Place not found.",
    "geocode_error":        "Geocoding error.",
    "btn_refresh":          "🔄 Refresh",
    "section_datetime":     "🕐 Date & Time",
    "realtime_label":       "⏱ Real time",
    "time_local_option":    "Local",
    "date_utc":             "Date (UTC)",
    "time_utc":             "Time (UTC)",
    "section_stars":        "🔭 Stars",
    "btn_download_hip":     "⬇ Download Hipparcos (~55 MB)",
    "downloading":          "Downloading…",
    "hip_downloaded":       "Hipparcos downloaded — reload the page.",
    "error_prefix":         "Failed: {e}",
    "mag_limit_label":      "Magnitude limit",
    "mag_help":             "Perfect sky ≈ 6.5 · Urban sky ≈ 4.0–5.0",
    "mag_help_eyepiece":    " · Eyepiece ≈ 10–12",
    "section_view":         "👁 View",
    "view_zenith":          "🌌 Zenith",
    "view_landscape":       "🌄 Landscape",
    "view_eyepiece":        "🔭 Eyepiece",
    "direction_label":      "Direction (az.)",
    "magnification_label":  "Magnification ×",
    "fov_caption":          "True FoV ≈ {fov:.2f}°  (apparent FoV 60°)",
    "search_object":        "🔍 Object",
    "no_results":           "No results.",
    "section_display":      "🗺 Display",
    "show_stars_label":     "Stars",
    "show_planets_label":   "Planets",
    "show_milkyway_label":  "Milky Way",
    "show_const_lines_label":  "Constellation lines",
    "show_const_names_label":  "Constellation names",
    "show_const_bounds_label": "Constellation boundaries",
    "show_ecliptic_label":       "Ecliptic plane",
    "show_ecliptic_grid_label":  "Ecliptic grid",
    "show_grid_label":           "Grid lines",
    "show_messier_label":        "Messier objects",
    "messier_galaxy":       "Galaxy",
    "messier_open":         "Open cluster",
    "messier_globular":     "Globular cluster",
    "messier_nebula":       "Nebula",
    "messier_planetary":    "Planetary nebula",
    "messier_snr":          "Supernova remnant",
    "section_satellites":   "🛰 Satellites",
    "show_satellites_label":"Artificial satellites",
    "sat_group_label":      "Group",
    "sat_trail_label":      "Trail (±min)",
    "sat_all_label":        "All satellites in group",
    "sat_prev_btn":         "◀ Prev.",
    "sat_next_btn":         "Next ▶",
    "sat_page_info":        "{n} satellites · page {p}/{total}",
    "sat_large_warning":    "⚠ Large group ({n} satellites) — limited to first {cap}.",
    "sat_selection_label":  "Satellites",
    "sat_placeholder":      "Choose… (empty = none)",
    "sat_load_error":       "Unable to load TLE data.",
    "tab_lieu":     "📍 Location",
    "tab_temps":    "🕐 Time",
    "tab_vue":      "👁 View",
    "tab_eph":      "Ephemeris",
    "tab_coord":    "Coordinates",
    "tab_ecl":      "Eclipses",
    "tab_moon":     "Moon",
    "tab_conj":     "Conjunctions",
    "tab_crep":     "Twilight",
    "col_body":     "Body",
    "col_rise":     "Rise",
    "col_transit":  "Transit",
    "col_set":      "Set",
    "col_elong":    "Elong.",
    "col_dist":     "Dist. (AU)",
    "col_diam":     "Diam. (\")",
    "col_phase":    "Phase (%)",
    "caption_detail": "Distance · Apparent diameter · Phase",
    "solar_eclipses_title": "**☀ Solar eclipses** — next 3 years",
    "lunar_eclipses_title": "**🌕 Lunar eclipses** — next 3 years",
    "col_date":     "Date",
    "col_time":     "Time",
    "col_type":     "Type",
    "col_totality": "Totality",
    "no_solar_eclipse": "No solar eclipse detected in the period.",
    "no_lunar_eclipse": "No lunar eclipse detected in the period.",
    "eclipse_caption": "UTC times of maximum · solar eclipses visible from part of the globe only",
    "moon_zenith_caption": "Zenith ↑ (parallactic angle)",
    "moon_illumination":   "Illumination",
    "moon_age":            "Age",
    "moon_elong":          "Elongation",
    "phases_caption":      "Phases — next 3 months",
    "col_phase_name":      "Phase",
    "col_utc":             "UTC",
    "col_bodies":   "Bodies",
    "col_sep":      "Sep.",
    "conj_caption": "Moon–planet (< 5°) · planet–planet (< 2°) — next 3 months",
    "no_conj":      "No notable conjunction in 3 months.",
    "col_quantity": "Quantity",
    "col_value":    "Value",
    "time_utc_row":    "Date & Time UTC",
    "time_local_row":  "Date & Local Time ({loc})",
    "jd_utc_row":      "Julian Day (JD UTC)",
    "jd_tt_row":       "Julian Day (JD TT)",
    "delta_t_row":     "ΔT  (TT − UTC)",
    "gmst_row":        "GMST — Greenwich Mean Sidereal Time",
    "lst_row":         "LST — Local Sidereal Time",
    "eot_row":         "Equation of time",
    "eot_chart_title": "Equation of time — {year}",
    "eot_y_axis":      "minutes",
    "eot_marker_label":"Simulated date",
    "eot_caption":     "Positive EoT → Sun transits before mean solar noon · Analytical formula (Meeus) · accuracy ≈ 0.5 min",
    "solar_events_title": "**☀ Sun**",
    "lunar_events_title": "**🌙 Moon**",
    "col_event":    "Event",
    "col_local_time": "Local ({off})",
    "col_azimuth":  "Azimuth",
    "col_altitude": "Altitude",
    "twilight_caption": "Civil −6° · Nautical −12° · Astronomical −18° · Altitude shown at meridian only",
    "summary_caption": "🌟 {n_stars} visible stars (mag ≤ {mag})  ·  🪐 {n_vis}/{n_tot} bodies above horizon",
    "render_error":       "Render error: {e}",
    "loading_bsc5":       "Loading BSC5 catalogue…",
    "computing_eclipses": "Computing eclipses…",
    "computing_conj":     "Computing conjunctions…",
    "about_btn": "ℹ️ About",
    "about_text": """\
**NOCTILUM** — Interactive mini-planetarium

---

**Functional specifications**
Jean-Philippe Blanchard

**Software development**
Claude Sonnet 4.6 — Anthropic

---

**Framework & libraries**
Python · Streamlit · Plotly · NumPy · Pandas · Folium

**Astronomy**
Skyfield · JPL DE440s ephemeris

---

**Data sources**
- Star catalogue: *Yale Bright Star Catalogue* (BSC5) — brettonw / Yale
- Constellations & IAU boundaries: *d3-celestial* — Olaf Frohn
- Milky Way: *mw.json* (galactic density polygons) — d3-celestial / Olaf Frohn
- Messier catalogue: IAU / SEDS data
- Artificial satellites: TLE Celestrak (stations, Starlink, OneWeb, weather, science, amateur, GPS) — refreshed every 6h
- Map background: CartoDB Dark Matter · © OpenStreetMap contributors
- Geocoding: Nominatim (OpenStreetMap)

---

**Available views**
- 🌌 Zenith — azimuthal stereographic projection centered on zenith
- 🌄 Landscape — equirectangular projection (azimuth × altitude) toward the horizon
- 🔭 Eyepiece — telescopic field centered on a target, true gnomonic projection

**Artificial satellites**
Positions and trajectories computed in real time via Skyfield from Celestrak TLEs.
The displayed trajectory covers ±5 min around the current instant (configurable).
Only satellites above the horizon are visible on the charts.

---

> ⚠️ **Window resizing** — the chart adjusts automatically with each recalculation.
> If the layout doesn't follow after a size change, modify any parameter
> (magnitude, time…) or enable **Real time** mode to force a recalculation.
""",
},  # /en

# ══════════════════════════════════════════════════════════════════════════════
"es": {
    "lang_label": "🌐 Idioma",
    "settings_title":       "⚙ Ajustes",
    "section_location":     "📍 Ubicación",
    "map_picker":           "🗺 Elegir en el mapa",
    "place_not_found":      "Lugar no encontrado.",
    "geocode_error":        "Error de geocodificación.",
    "btn_refresh":          "🔄 Actualizar",
    "section_datetime":     "🕐 Fecha y Hora",
    "realtime_label":       "⏱ Tiempo real",
    "time_local_option":    "Local",
    "date_utc":             "Fecha (UTC)",
    "time_utc":             "Hora (UTC)",
    "section_stars":        "🔭 Estrellas",
    "btn_download_hip":     "⬇ Descargar Hipparcos (~55 MB)",
    "downloading":          "Descargando…",
    "hip_downloaded":       "Hipparcos descargado — recargue la página.",
    "error_prefix":         "Error: {e}",
    "mag_limit_label":      "Magnitud límite",
    "mag_help":             "Cielo perfecto ≈ 6.5 · Cielo urbano ≈ 4.0–5.0",
    "mag_help_eyepiece":    " · Ocular ≈ 10–12",
    "section_view":         "👁 Vista",
    "view_zenith":          "🌌 Cenit",
    "view_landscape":       "🌄 Paisaje",
    "view_eyepiece":        "🔭 Ocular",
    "direction_label":      "Dirección (az.)",
    "magnification_label":  "Magnificación ×",
    "fov_caption":          "Campo real ≈ {fov:.2f}°  (campo aparente 60°)",
    "search_object":        "🔍 Objeto",
    "no_results":           "Sin resultados.",
    "section_display":      "🗺 Visualización",
    "show_stars_label":     "Estrellas",
    "show_planets_label":   "Planetas",
    "show_milkyway_label":  "Vía Láctea",
    "show_const_lines_label":  "Líneas de constelaciones",
    "show_const_names_label":  "Nombres de constelaciones",
    "show_const_bounds_label": "Límites de constelaciones",
    "show_ecliptic_label":       "Plano de la eclíptica",
    "show_ecliptic_grid_label":  "Cuadrícula eclíptica",
    "show_grid_label":           "Meridianos y paralelos",
    "show_messier_label":   "Objetos de Messier",
    "messier_galaxy":       "Galaxia",
    "messier_open":         "Cúmulo abierto",
    "messier_globular":     "Cúmulo globular",
    "messier_nebula":       "Nebulosa",
    "messier_planetary":    "Nebulosa planetaria",
    "messier_snr":          "Remanente de supernova",
    "section_satellites":   "🛰 Satélites",
    "show_satellites_label":"Satélites artificiales",
    "sat_group_label":      "Grupo",
    "sat_trail_label":      "Trayectoria (±min)",
    "sat_all_label":        "Todos los satélites del grupo",
    "sat_prev_btn":         "◀ Ant.",
    "sat_next_btn":         "Sig. ▶",
    "sat_page_info":        "{n} satélites · página {p}/{total}",
    "sat_large_warning":    "⚠ Grupo grande ({n} satélites) — limitado a los primeros {cap}.",
    "sat_selection_label":  "Satélites",
    "sat_placeholder":      "Elegir… (vacío = ninguno)",
    "sat_load_error":       "No se pueden cargar los TLE.",
    "tab_lieu":     "📍 Ubicación",
    "tab_temps":    "🕐 Tiempo",
    "tab_vue":      "👁 Vista",
    "tab_eph":      "Efemérides",
    "tab_coord":    "Coordenadas",
    "tab_ecl":      "Eclipses",
    "tab_moon":     "Luna",
    "tab_conj":     "Conjunciones",
    "tab_crep":     "Crepúsculos",
    "col_body":     "Astro",
    "col_rise":     "Salida",
    "col_transit":  "Tránsito",
    "col_set":      "Puesta",
    "col_elong":    "Elon.",
    "col_dist":     "Dist. (UA)",
    "col_diam":     "Diám. (\")",
    "col_phase":    "Fase (%)",
    "caption_detail": "Distancia · Diámetro aparente · Fase",
    "solar_eclipses_title": "**☀ Eclipses solares** — próximos 3 años",
    "lunar_eclipses_title": "**🌕 Eclipses lunares** — próximos 3 años",
    "col_date":     "Fecha",
    "col_time":     "Hora",
    "col_type":     "Tipo",
    "col_totality": "Totalidad",
    "no_solar_eclipse": "No se detectó ningún eclipse solar en el período.",
    "no_lunar_eclipse": "No se detectó ningún eclipse lunar en el período.",
    "eclipse_caption": "Hora UTC del máximo · eclipses solares visibles solo desde parte del globo",
    "moon_zenith_caption": "Cenit ↑ (ángulo paraláctico)",
    "moon_illumination":   "Iluminación",
    "moon_age":            "Edad",
    "moon_elong":          "Elongación",
    "phases_caption":      "Fases — próximos 3 meses",
    "col_phase_name":      "Fase",
    "col_utc":             "UTC",
    "col_bodies":   "Cuerpos",
    "col_sep":      "Sep.",
    "conj_caption": "Luna–planeta (< 5°) · planeta–planeta (< 2°) — próximos 3 meses",
    "no_conj":      "Ninguna conjunción notable en 3 meses.",
    "col_quantity": "Magnitud",
    "col_value":    "Valor",
    "time_utc_row":    "Fecha y Hora UTC",
    "time_local_row":  "Fecha y Hora local ({loc})",
    "jd_utc_row":      "Día Juliano (JD UTC)",
    "jd_tt_row":       "Día Juliano (JD TT)",
    "delta_t_row":     "ΔT  (TT − UTC)",
    "gmst_row":        "TMSG — Tiempo Sidéreo Medio de Greenwich",
    "lst_row":         "TSL — Tiempo Sidéreo Local",
    "eot_row":         "Ecuación del tiempo",
    "eot_chart_title": "Ecuación del tiempo — {year}",
    "eot_y_axis":      "minutos",
    "eot_marker_label":"Fecha simulada",
    "eot_caption":     "EoT positivo → el Sol transita antes del mediodía solar · Fórmula analítica (Meeus) · precisión ≈ 0.5 min",
    "solar_events_title": "**☀ Sol**",
    "lunar_events_title": "**🌙 Luna**",
    "col_event":    "Evento",
    "col_local_time": "Local ({off})",
    "col_azimuth":  "Azimut",
    "col_altitude": "Altura",
    "twilight_caption": "Civil −6° · Náutico −12° · Astronómico −18° · Altura mostrada solo en el meridiano",
    "summary_caption": "🌟 {n_stars} estrellas visibles (mag ≤ {mag})  ·  🪐 {n_vis}/{n_tot} cuerpos sobre el horizonte",
    "render_error":       "Error de renderizado: {e}",
    "loading_bsc5":       "Cargando catálogo BSC5…",
    "computing_eclipses": "Calculando eclipses…",
    "computing_conj":     "Calculando conjunciones…",
    "about_btn": "ℹ️ Acerca de",
    "about_text": """\
**NOCTILUM** — Mini-planetario interactivo

---

**Especificaciones funcionales**
Jean-Philippe Blanchard

**Desarrollo de software**
Claude Sonnet 4.6 — Anthropic

---

**Marco & bibliotecas**
Python · Streamlit · Plotly · NumPy · Pandas · Folium

**Astronomía**
Skyfield · Efeméride JPL DE440s

---

**Fuentes de datos**
- Catálogo estelar: *Yale Bright Star Catalogue* (BSC5) — brettonw / Yale
- Constelaciones y límites IAU: *d3-celestial* — Olaf Frohn
- Vía Láctea: *mw.json* (polígonos de densidad galáctica) — d3-celestial / Olaf Frohn
- Catálogo Messier: datos IAU / SEDS
- Satélites artificiales: TLE Celestrak (estaciones, Starlink, OneWeb, meteorología, ciencia, amateur, GPS) — actualizados cada 6h
- Fondo cartográfico: CartoDB Dark Matter · © OpenStreetMap contributors
- Geocodificación: Nominatim (OpenStreetMap)

---

**Vistas disponibles**
- 🌌 Cenit — proyección estereográfica azimutal centrada en el cenit
- 🌄 Paisaje — proyección equirectangular (azimut × altura) hacia el horizonte
- 🔭 Ocular — campo telescópico centrado en un objetivo, proyección gnomónica verdadera

**Satélites artificiales**
Posiciones y trayectorias calculadas en tiempo real con Skyfield desde TLE de Celestrak.
La trayectoria mostrada cubre ±5 min alrededor del instante actual (configurable).
Solo los satélites sobre el horizonte son visibles en los gráficos.

---

> ⚠️ **Redimensionamiento** — el gráfico se adapta automáticamente en cada recálculo.
> Si el diseño no sigue tras un cambio de tamaño, modifique cualquier parámetro
> (magnitud, hora…) o active el modo **Tiempo real** para forzar el recálculo.
""",
},  # /es

# ══════════════════════════════════════════════════════════════════════════════
"zh": {
    "lang_label": "🌐 语言",
    "settings_title":       "⚙ 设置",
    "section_location":     "📍 位置",
    "map_picker":           "🗺 在地图上选择",
    "place_not_found":      "未找到地点。",
    "geocode_error":        "地理编码错误。",
    "btn_refresh":          "🔄 刷新",
    "section_datetime":     "🕐 日期与时间",
    "realtime_label":       "⏱ 实时",
    "time_local_option":    "当地时间",
    "date_utc":             "日期 (UTC)",
    "time_utc":             "时间 (UTC)",
    "section_stars":        "🔭 星星",
    "btn_download_hip":     "⬇ 下载 Hipparcos (~55 MB)",
    "downloading":          "下载中…",
    "hip_downloaded":       "Hipparcos 已下载 — 请重新加载页面。",
    "error_prefix":         "失败：{e}",
    "mag_limit_label":      "星等极限",
    "mag_help":             "完美天空 ≈ 6.5 · 城市天空 ≈ 4.0–5.0",
    "mag_help_eyepiece":    " · 目镜 ≈ 10–12",
    "section_view":         "👁 视图",
    "view_zenith":          "🌌 天顶",
    "view_landscape":       "🌄 地景",
    "view_eyepiece":        "🔭 目镜",
    "direction_label":      "方向（方位角）",
    "magnification_label":  "放大倍率 ×",
    "fov_caption":          "真实视场 ≈ {fov:.2f}°（表观视场 60°）",
    "search_object":        "🔍 天体",
    "no_results":           "无结果。",
    "section_display":      "🗺 显示",
    "show_stars_label":     "星星",
    "show_planets_label":   "行星",
    "show_milkyway_label":  "银河",
    "show_const_lines_label":  "星座连线",
    "show_const_names_label":  "星座名称",
    "show_const_bounds_label": "星座边界",
    "show_ecliptic_label":       "黄道面",
    "show_ecliptic_grid_label":  "黄道坐标网",
    "show_grid_label":           "网格线",
    "show_messier_label":   "梅西耶天体",
    "messier_galaxy":       "星系",
    "messier_open":         "疏散星团",
    "messier_globular":     "球状星团",
    "messier_nebula":       "星云",
    "messier_planetary":    "行星状星云",
    "messier_snr":          "超新星遗迹",
    "section_satellites":   "🛰 卫星",
    "show_satellites_label":"人造卫星",
    "sat_group_label":      "分组",
    "sat_trail_label":      "轨迹（±分钟）",
    "sat_all_label":        "该组全部卫星",
    "sat_prev_btn":         "◀ 上一页",
    "sat_next_btn":         "下一页 ▶",
    "sat_page_info":        "{n} 颗卫星 · 第 {p}/{total} 页",
    "sat_large_warning":    "⚠ 分组较大（{n} 颗卫星）— 仅显示前 {cap} 颗。",
    "sat_selection_label":  "卫星",
    "sat_placeholder":      "选择…（空 = 无）",
    "sat_load_error":       "无法加载TLE数据。",
    "tab_lieu":     "📍 地点",
    "tab_temps":    "🕐 时间",
    "tab_vue":      "👁 视图",
    "tab_eph":      "星历",
    "tab_coord":    "坐标",
    "tab_ecl":      "食",
    "tab_moon":     "月亮",
    "tab_conj":     "会合",
    "tab_crep":     "曙暮光",
    "col_body":     "天体",
    "col_rise":     "升起",
    "col_transit":  "中天",
    "col_set":      "落下",
    "col_elong":    "距角",
    "col_dist":     "距离 (AU)",
    "col_diam":     "角径 (\")",
    "col_phase":    "相位 (%)",
    "caption_detail": "距离 · 角径 · 相位",
    "solar_eclipses_title": "**☀ 日食** — 未来3年",
    "lunar_eclipses_title": "**🌕 月食** — 未来3年",
    "col_date":     "日期",
    "col_time":     "时间",
    "col_type":     "类型",
    "col_totality": "全食时长",
    "no_solar_eclipse": "该时期内未检测到日食。",
    "no_lunar_eclipse": "该时期内未检测到月食。",
    "eclipse_caption": "最大值的UTC时间 · 日食仅在部分地区可见",
    "moon_zenith_caption": "天顶 ↑（视差角）",
    "moon_illumination":   "照明度",
    "moon_age":            "月龄",
    "moon_elong":          "距角",
    "phases_caption":      "月相 — 未来3个月",
    "col_phase_name":      "月相",
    "col_utc":             "UTC",
    "col_bodies":   "天体",
    "col_sep":      "间距",
    "conj_caption": "月亮–行星 (< 5°) · 行星–行星 (< 2°) — 未来3个月",
    "no_conj":      "3个月内无显著会合。",
    "col_quantity": "量",
    "col_value":    "值",
    "time_utc_row":    "UTC 日期时间",
    "time_local_row":  "当地日期时间 ({loc})",
    "jd_utc_row":      "儒略日 (JD UTC)",
    "jd_tt_row":       "儒略日 (JD TT)",
    "delta_t_row":     "ΔT  (TT − UTC)",
    "gmst_row":        "GMST — 格林威治平恒星时",
    "lst_row":         "LST — 本地恒星时",
    "eot_row":         "时差",
    "eot_chart_title": "时差 — {year}",
    "eot_y_axis":      "分钟",
    "eot_marker_label":"模拟日期",
    "eot_caption":     "EoT 为正 → 太阳在平均太阳正午之前过中天 · 解析公式 (Meeus) · 精度 ≈ 0.5 分钟",
    "solar_events_title": "**☀ 太阳**",
    "lunar_events_title": "**🌙 月亮**",
    "col_event":    "事件",
    "col_local_time": "当地 ({off})",
    "col_azimuth":  "方位角",
    "col_altitude": "高度",
    "twilight_caption": "民用 −6° · 航海 −12° · 天文 −18° · 仅在子午线显示高度",
    "summary_caption": "🌟 {n_stars} 颗可见星（星等 ≤ {mag}）  ·  🪐 {n_vis}/{n_tot} 天体在地平线以上",
    "render_error":       "渲染错误：{e}",
    "loading_bsc5":       "正在加载BSC5星表…",
    "computing_eclipses": "正在计算食…",
    "computing_conj":     "正在计算会合…",
    "about_btn": "ℹ️ 关于",
    "about_text": """\
**NOCTILUM** — 互动迷你天文馆

---

**功能规格**
Jean-Philippe Blanchard

**软件开发**
Claude Sonnet 4.6 — Anthropic

---

**框架与库**
Python · Streamlit · Plotly · NumPy · Pandas · Folium

**天文学**
Skyfield · JPL DE440s 历书

---

**数据来源**
- 星表：*耶鲁亮星星表* (BSC5) — brettonw / Yale
- 星座与IAU边界：*d3-celestial* — Olaf Frohn
- 银河：*mw.json*（银河密度多边形）— d3-celestial / Olaf Frohn
- 梅西耶星表：IAU / SEDS 数据
- 人造卫星：TLE Celestrak（空间站、Starlink、OneWeb、气象、科学、业余、GPS）— 每6小时更新
- 地图背景：CartoDB Dark Matter · © OpenStreetMap 贡献者
- 地理编码：Nominatim (OpenStreetMap)

---

**可用视图**
- 🌌 天顶 — 以天顶为中心的方位球心投影
- 🌄 地景 — 等距柱状投影（方位角 × 仰角），朝向地平线
- 🔭 目镜 — 以目标为中心的望远镜视野，真实球心投影

**人造卫星**
通过Skyfield从Celestrak TLE实时计算位置和轨迹。
显示的轨迹覆盖当前时刻前后±5分钟（可调）。
仅地平线以上的卫星在图表上可见。

---

> ⚠️ **调整窗口大小** — 图表在每次重新计算时自动调整。如果更改大小后
> 布局不跟随，请修改任意参数（星等、时间……）或启用**实时**模式强制重新计算。
""",
},  # /zh

# ══════════════════════════════════════════════════════════════════════════════
"hi": {
    "lang_label": "🌐 भाषा",
    "settings_title":       "⚙ सेटिंग्स",
    "section_location":     "📍 स्थान",
    "map_picker":           "🗺 मानचित्र पर चुनें",
    "place_not_found":      "स्थान नहीं मिला।",
    "geocode_error":        "जियोकोडिंग त्रुटि।",
    "btn_refresh":          "🔄 ताज़ा करें",
    "section_datetime":     "🕐 दिनांक और समय",
    "realtime_label":       "⏱ वास्तविक समय",
    "time_local_option":    "स्थानीय",
    "date_utc":             "दिनांक (UTC)",
    "time_utc":             "समय (UTC)",
    "section_stars":        "🔭 तारे",
    "btn_download_hip":     "⬇ Hipparcos डाउनलोड करें (~55 MB)",
    "downloading":          "डाउनलोड हो रहा है…",
    "hip_downloaded":       "Hipparcos डाउनलोड हुआ — पृष्ठ पुनः लोड करें।",
    "error_prefix":         "विफल: {e}",
    "mag_limit_label":      "परिमाण सीमा",
    "mag_help":             "उत्तम आकाश ≈ 6.5 · शहरी आकाश ≈ 4.0–5.0",
    "mag_help_eyepiece":    " · आइपीस ≈ 10–12",
    "section_view":         "👁 दृश्य",
    "view_zenith":          "🌌 खगोल",
    "view_landscape":       "🌄 क्षितिज",
    "view_eyepiece":        "🔭 आइपीस",
    "direction_label":      "दिशा (दिगंश)",
    "magnification_label":  "आवर्धन ×",
    "fov_caption":          "वास्तविक दृश्य ≈ {fov:.2f}°  (आभासी दृश्य 60°)",
    "search_object":        "🔍 खगोल पिंड",
    "no_results":           "कोई परिणाम नहीं।",
    "section_display":      "🗺 प्रदर्शन",
    "show_stars_label":     "तारे",
    "show_planets_label":   "ग्रह",
    "show_milkyway_label":  "आकाशगंगा",
    "show_const_lines_label":  "नक्षत्र रेखाएं",
    "show_const_names_label":  "नक्षत्र नाम",
    "show_const_bounds_label": "नक्षत्र सीमाएं",
    "show_ecliptic_label":       "क्रांतिवृत्त",
    "show_ecliptic_grid_label":  "क्रांतिवृत्त ग्रिड",
    "show_grid_label":           "ग्रिड रेखाएं",
    "show_messier_label":   "मेसियर पिंड",
    "messier_galaxy":       "आकाशगंगा",
    "messier_open":         "खुला समूह",
    "messier_globular":     "गोलाकार समूह",
    "messier_nebula":       "निहारिका",
    "messier_planetary":    "ग्रहीय निहारिका",
    "messier_snr":          "सुपरनोवा अवशेष",
    "section_satellites":   "🛰 उपग्रह",
    "show_satellites_label":"कृत्रिम उपग्रह",
    "sat_group_label":      "समूह",
    "sat_trail_label":      "पथ (±मिनट)",
    "sat_all_label":        "समूह के सभी उपग्रह",
    "sat_prev_btn":         "◀ पिछला",
    "sat_next_btn":         "अगला ▶",
    "sat_page_info":        "{n} उपग्रह · पृष्ठ {p}/{total}",
    "sat_large_warning":    "⚠ बड़ा समूह ({n} उपग्रह) — प्रदर्शन के लिए पहले {cap} तक सीमित।",
    "sat_selection_label":  "उपग्रह",
    "sat_placeholder":      "चुनें… (खाली = कोई नहीं)",
    "sat_load_error":       "TLE डेटा लोड नहीं हो सका।",
    "tab_lieu":     "📍 स्थान",
    "tab_temps":    "🕐 समय",
    "tab_vue":      "👁 दृश्य",
    "tab_eph":      "ग्रह-स्थिति",
    "tab_coord":    "निर्देशांक",
    "tab_ecl":      "ग्रहण",
    "tab_moon":     "चंद्रमा",
    "tab_conj":     "युति",
    "tab_crep":     "संध्याकाल",
    "col_body":     "पिंड",
    "col_rise":     "उदय",
    "col_transit":  "पारगमन",
    "col_set":      "अस्त",
    "col_elong":    "दीर्घता",
    "col_dist":     "दूरी (AU)",
    "col_diam":     "व्यास (\")",
    "col_phase":    "कला (%)",
    "caption_detail": "दूरी · कोणीय व्यास · कला",
    "solar_eclipses_title": "**☀ सूर्य ग्रहण** — अगले 3 वर्ष",
    "lunar_eclipses_title": "**🌕 चंद्र ग्रहण** — अगले 3 वर्ष",
    "col_date":     "दिनांक",
    "col_time":     "समय",
    "col_type":     "प्रकार",
    "col_totality": "पूर्णता",
    "no_solar_eclipse": "इस अवधि में कोई सूर्य ग्रहण नहीं।",
    "no_lunar_eclipse": "इस अवधि में कोई चंद्र ग्रहण नहीं।",
    "eclipse_caption": "अधिकतम का UTC समय · सूर्य ग्रहण केवल पृथ्वी के कुछ भाग से दृश्य",
    "moon_zenith_caption": "खगोल ↑ (समानान्तर कोण)",
    "moon_illumination":   "प्रदीप्ति",
    "moon_age":            "आयु",
    "moon_elong":          "दीर्घता",
    "phases_caption":      "चरण — अगले 3 महीने",
    "col_phase_name":      "चरण",
    "col_utc":             "UTC",
    "col_bodies":   "पिंड",
    "col_sep":      "पृथकता",
    "conj_caption": "चंद्र–ग्रह (< 5°) · ग्रह–ग्रह (< 2°) — अगले 3 महीने",
    "no_conj":      "3 महीने में कोई उल्लेखनीय युति नहीं।",
    "col_quantity": "राशि",
    "col_value":    "मान",
    "time_utc_row":    "UTC दिनांक और समय",
    "time_local_row":  "स्थानीय दिनांक और समय ({loc})",
    "jd_utc_row":      "जूलियन दिवस (JD UTC)",
    "jd_tt_row":       "जूलियन दिवस (JD TT)",
    "delta_t_row":     "ΔT  (TT − UTC)",
    "gmst_row":        "GMST — ग्रीनविच माध्य नाक्षत्र समय",
    "lst_row":         "LST — स्थानीय नाक्षत्र समय",
    "eot_row":         "समय समीकरण",
    "eot_chart_title": "समय समीकरण — {year}",
    "eot_y_axis":      "मिनट",
    "eot_marker_label":"अनुकरण तिथि",
    "eot_caption":     "धनात्मक EoT → सूर्य माध्य दोपहर से पहले मध्याह्न रेखा पार करता है · विश्लेषणात्मक सूत्र (Meeus) · सटीकता ≈ 0.5 मिनट",
    "solar_events_title": "**☀ सूर्य**",
    "lunar_events_title": "**🌙 चंद्रमा**",
    "col_event":    "घटना",
    "col_local_time": "स्थानीय ({off})",
    "col_azimuth":  "दिगंश",
    "col_altitude": "ऊंचाई",
    "twilight_caption": "नागरिक −6° · नौवहन −12° · खगोलीय −18° · केवल मध्याह्न पर ऊंचाई दिखाएं",
    "summary_caption": "🌟 {n_stars} दृश्य तारे (परिमाण ≤ {mag})  ·  🪐 {n_vis}/{n_tot} पिंड क्षितिज के ऊपर",
    "render_error":       "रेंडरिंग त्रुटि: {e}",
    "loading_bsc5":       "BSC5 कैटलॉग लोड हो रहा है…",
    "computing_eclipses": "ग्रहण की गणना हो रही है…",
    "computing_conj":     "युति की गणना हो रही है…",
    "about_btn": "ℹ️ परिचय",
    "about_text": """\
**NOCTILUM** — इंटरैक्टिव मिनी तारामंडल

---

**कार्यात्मक विशिष्टताएं**
Jean-Philippe Blanchard

**सॉफ्टवेयर विकास**
Claude Sonnet 4.6 — Anthropic

---

**फ्रेमवर्क और लाइब्रेरी**
Python · Streamlit · Plotly · NumPy · Pandas · Folium

**खगोल विज्ञान**
Skyfield · JPL DE440s पंचांग

---

**डेटा स्रोत**
- तारा कैटलॉग: *येल ब्राइट स्टार कैटलॉग* (BSC5) — brettonw / Yale
- नक्षत्र और IAU सीमाएं: *d3-celestial* — Olaf Frohn
- आकाशगंगा: *mw.json* (गैलेक्टिक घनत्व बहुभुज) — d3-celestial / Olaf Frohn
- मेसियर कैटलॉग: IAU / SEDS डेटा
- कृत्रिम उपग्रह: TLE Celestrak (स्टेशन, Starlink, OneWeb, मौसम, विज्ञान, शौकिया, GPS) — हर 6 घंटे में अपडेट
- मानचित्र पृष्ठभूमि: CartoDB Dark Matter · © OpenStreetMap योगदानकर्ता
- जियोकोडिंग: Nominatim (OpenStreetMap)

---

**उपलब्ध दृश्य**
- 🌌 खगोल — शिखर बिंदु पर केंद्रित आज़िमुथल स्टेरियोग्राफिक प्रक्षेपण
- 🌄 क्षितिज — समभुज आयताकार प्रक्षेपण (दिगंश × ऊंचाई) क्षितिज की ओर
- 🔭 आइपीस — लक्ष्य पर केंद्रित दूरबीन दृश्य, वास्तविक ग्नोमोनिक प्रक्षेपण

**कृत्रिम उपग्रह**
Celestrak TLE से Skyfield के माध्यम से वास्तविक समय में स्थिति और पथ की गणना।
प्रदर्शित पथ वर्तमान क्षण के ±5 मिनट को कवर करता है (कॉन्फ़िगर करने योग्य)।
केवल क्षितिज के ऊपर के उपग्रह चार्ट पर दिखाई देते हैं।

---

> ⚠️ **विंडो का आकार बदलना** — चार्ट प्रत्येक पुनर्गणना पर स्वचालित रूप से समायोजित होता है।
> यदि लेआउट नहीं बदले, तो कोई भी पैरामीटर (परिमाण, समय…) बदलें
> या पुनर्गणना के लिए **वास्तविक समय** मोड सक्रिय करें।
""",
},  # /hi

}  # /_T


# ─── Noms de corps célestes ───────────────────────────────────────────────────

_BODIES: dict[str, dict[str, str]] = {
    "fr": {},  # identité
    "en": {
        "Mercure":"Mercury","Vénus":"Venus","Mars":"Mars",
        "Jupiter":"Jupiter","Saturne":"Saturn","Uranus":"Uranus",
        "Neptune":"Neptune","Pluton":"Pluto","Soleil":"Sun","Lune":"Moon",
    },
    "es": {
        "Mercure":"Mercurio","Vénus":"Venus","Mars":"Marte",
        "Jupiter":"Júpiter","Saturne":"Saturno","Uranus":"Urano",
        "Neptune":"Neptuno","Pluton":"Plutón","Soleil":"Sol","Lune":"Luna",
    },
    "zh": {
        "Mercure":"水星","Vénus":"金星","Mars":"火星",
        "Jupiter":"木星","Saturne":"土星","Uranus":"天王星",
        "Neptune":"海王星","Pluton":"冥王星","Soleil":"太阳","Lune":"月亮",
    },
    "hi": {
        "Mercure":"बुध","Vénus":"शुक्र","Mars":"मंगल",
        "Jupiter":"बृहस्पति","Saturne":"शनि","Uranus":"अरुण",
        "Neptune":"वरुण","Pluton":"यम","Soleil":"सूर्य","Lune":"चन्द्रमा",
    },
}

# ─── Labels d'événements (crépuscules) ────────────────────────────────────────

_EVENTS: dict[str, dict[str, str]] = {
    "fr": {},
    "en": {
        "Aube astronomique":   "Astronomical Dawn",
        "Aube nautique":       "Nautical Dawn",
        "Aube civile":         "Civil Dawn",
        "Lever du Soleil":     "Sunrise",
        "Passage au méridien": "Solar Noon",
        "Coucher du Soleil":   "Sunset",
        "Crépuscule civil":    "Civil Twilight",
        "Crépuscule nautique": "Nautical Twilight",
        "Crépuscule astron.":  "Astron. Twilight",
        "Lever de la Lune":    "Moonrise",
        "Transit de la Lune":  "Moon Transit",
        "Coucher de la Lune":  "Moonset",
    },
    "es": {
        "Aube astronomique":   "Amanecer astronómico",
        "Aube nautique":       "Amanecer náutico",
        "Aube civile":         "Amanecer civil",
        "Lever du Soleil":     "Salida del Sol",
        "Passage au méridien": "Mediodía solar",
        "Coucher du Soleil":   "Puesta del Sol",
        "Crépuscule civil":    "Crepúsculo civil",
        "Crépuscule nautique": "Crepúsculo náutico",
        "Crépuscule astron.":  "Crepúsculo astronómico",
        "Lever de la Lune":    "Salida de la Luna",
        "Transit de la Lune":  "Tránsito lunar",
        "Coucher de la Lune":  "Puesta de la Luna",
    },
    "zh": {
        "Aube astronomique":   "天文黎明",
        "Aube nautique":       "航海黎明",
        "Aube civile":         "民用黎明",
        "Lever du Soleil":     "日出",
        "Passage au méridien": "太阳过子午线",
        "Coucher du Soleil":   "日落",
        "Crépuscule civil":    "民用黄昏",
        "Crépuscule nautique": "航海黄昏",
        "Crépuscule astron.":  "天文黄昏",
        "Lever de la Lune":    "月出",
        "Transit de la Lune":  "月过子午线",
        "Coucher de la Lune":  "月落",
    },
    "hi": {
        "Aube astronomique":   "खगोलीय भोर",
        "Aube nautique":       "नौवहन भोर",
        "Aube civile":         "नागरिक भोर",
        "Lever du Soleil":     "सूर्योदय",
        "Passage au méridien": "सूर्य मध्याह्न",
        "Coucher du Soleil":   "सूर्यास्त",
        "Crépuscule civil":    "नागरिक संध्या",
        "Crépuscule nautique": "नौवहन संध्या",
        "Crépuscule astron.":  "खगोलीय संध्या",
        "Lever de la Lune":    "चंद्रोदय",
        "Transit de la Lune":  "चंद्र पारगमन",
        "Coucher de la Lune":  "चंद्रास्त",
    },
}

# ─── Phases lunaires ──────────────────────────────────────────────────────────

_PHASES: dict[str, dict[str, str]] = {
    "fr": {},
    "en": {
        "Nouvelle Lune":        "New Moon",
        "Croissant montant":    "Waxing Crescent",
        "Premier Quartier":     "First Quarter",
        "Gibbeuse montante":    "Waxing Gibbous",
        "Pleine Lune":          "Full Moon",
        "Gibbeuse décroissante":"Waning Gibbous",
        "Dernier Quartier":     "Last Quarter",
        "Croissant décroissant":"Waning Crescent",
    },
    "es": {
        "Nouvelle Lune":        "Luna Nueva",
        "Croissant montant":    "Cuarto creciente",
        "Premier Quartier":     "Cuarto Creciente",
        "Gibbeuse montante":    "Gibosa creciente",
        "Pleine Lune":          "Luna Llena",
        "Gibbeuse décroissante":"Gibosa menguante",
        "Dernier Quartier":     "Cuarto Menguante",
        "Croissant décroissant":"Cuarto menguante",
    },
    "zh": {
        "Nouvelle Lune":        "新月",
        "Croissant montant":    "眉月",
        "Premier Quartier":     "上弦月",
        "Gibbeuse montante":    "盈凸月",
        "Pleine Lune":          "满月",
        "Gibbeuse décroissante":"亏凸月",
        "Dernier Quartier":     "下弦月",
        "Croissant décroissant":"残月",
    },
    "hi": {
        "Nouvelle Lune":        "अमावस्या",
        "Croissant montant":    "शुक्ल द्वितीया",
        "Premier Quartier":     "शुक्ल अष्टमी",
        "Gibbeuse montante":    "शुक्ल पक्ष",
        "Pleine Lune":          "पूर्णिमा",
        "Gibbeuse décroissante":"कृष्ण पक्ष",
        "Dernier Quartier":     "कृष्ण अष्टमी",
        "Croissant décroissant":"कृष्ण द्वितीया",
    },
}

# ─── Types d'éclipses ────────────────────────────────────────────────────────

_ECLIPSE_TYPES: dict[str, dict[str, str]] = {
    "fr": {},
    "en": {
        "Totale":"Total","Annulaire":"Annular","Hybride":"Hybrid",
        "Partielle":"Partial","Partielle (rasante)":"Partial (grazing)",
        "Pénombrale":"Penumbral",
    },
    "es": {
        "Totale":"Total","Annulaire":"Anular","Hybride":"Híbrido",
        "Partielle":"Parcial","Partielle (rasante)":"Parcial (rasante)",
        "Pénombrale":"Penumbral",
    },
    "zh": {
        "Totale":"全食","Annulaire":"环食","Hybride":"混合食",
        "Partielle":"偏食","Partielle (rasante)":"掠食",
        "Pénombrale":"半影食",
    },
    "hi": {
        "Totale":"पूर्ण","Annulaire":"वलयाकार","Hybride":"संकर",
        "Partielle":"आंशिक","Partielle (rasante)":"आंशिक (तिरछी)",
        "Pénombrale":"उपछाया",
    },
}


# ─── API publique ─────────────────────────────────────────────────────────────

def _lang() -> str:
    return st.session_state.get("lang", "fr")


def t(key: str, **kwargs) -> str:
    """Retourne la chaîne traduite pour la langue courante."""
    lang = _lang()
    text = _T.get(lang, _T["fr"]).get(key) or _T["fr"].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text


def tr_body(fr_name: str) -> str:
    """Traduit un nom de corps céleste depuis le français."""
    lang = _lang()
    return _BODIES.get(lang, {}).get(fr_name, fr_name)


def tr_event(fr_label: str) -> str:
    """Traduit un label d'événement astronomique depuis le français."""
    lang = _lang()
    return _EVENTS.get(lang, {}).get(fr_label, fr_label)


def tr_phase(fr_name: str) -> str:
    """Traduit un nom de phase lunaire depuis le français."""
    lang = _lang()
    return _PHASES.get(lang, {}).get(fr_name, fr_name)


def tr_eclipse_type(fr_type: str) -> str:
    """Traduit un type d'éclipse depuis le français."""
    lang = _lang()
    return _ECLIPSE_TYPES.get(lang, {}).get(fr_type, fr_type)


_MONTHS: dict[str, list[str]] = {
    "fr": ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"],
    "en": ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
    "es": ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"],
    "zh": ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"],
    "hi": ["जन","फर","मार","अप्र","मई","जून","जुल","अग","सित","अक्त","नव","दिस"],
}


def compass_dirs() -> list[tuple[int, str]]:
    """Retourne les 16 points cardinaux pour la langue courante."""
    return _COMPASS.get(_lang(), _COMPASS["fr"])


def cardinal_map() -> dict[int, str]:
    """Retourne {angle: label} pour les 16 points cardinaux (langue courante)."""
    return {angle: label for angle, label in compass_dirs()}


def months() -> list[str]:
    """Retourne les 12 abréviations de mois pour la langue courante."""
    return _MONTHS.get(_lang(), _MONTHS["fr"])
