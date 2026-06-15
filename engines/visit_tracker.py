import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, timezone, timedelta


def track_visit() -> None:
    """Render un composant JS invisible qui gère tout le tracking côté navigateur."""
    if st.session_state.get("visit_tracked"):
        return
    st.session_state["visit_tracked"] = True

    try:
        supabase_url = st.secrets["SUPABASE_URL"].strip()
        supabase_key = st.secrets["SUPABASE_ANON_KEY"].strip()
    except Exception:
        return

    # Le JS s'exécute dans le navigateur du visiteur :
    # 1) fetch la vraie IP publique via api.ipify.org
    # 2) géolocalise via ip-api.com
    # 3) insère dans Supabase via l'API REST (fetch direct, pas de lib)
    html = f"""
<script>
(async () => {{
  try {{
    // ipwho.is : CORS permissif, geolocate automatiquement le requêtant
    const geo = await fetch('https://ipwho.is/')
      .then(r => r.json())
      .catch(e => {{ console.warn('[noctilum] geo failed:', e); return {{}}; }});

    console.log('[noctilum] geo:', JSON.stringify(geo));

    const ok = geo.success === true;
    const resp = await fetch('{supabase_url}/rest/v1/visits', {{
      method: 'POST',
      headers: {{
        'apikey': '{supabase_key}',
        'Authorization': 'Bearer {supabase_key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
      }},
      body: JSON.stringify({{
        ip:           geo.ip                        || null,
        country:      ok ? geo.country              : null,
        country_code: ok ? geo.country_code         : null,
        city:         ok ? geo.city                 : null,
        region:       ok ? geo.region               : null,
        lat:          ok ? geo.latitude             : null,
        lon:          ok ? geo.longitude            : null,
        org:          ok ? (geo.connection?.org || null) : null,
      }})
    }});
    console.log('[noctilum] insert:', resp.status);
  }} catch(e) {{ console.warn('[noctilum] tracker error:', e); }}
}})();
</script>
"""
    components.html(html, height=0)


@st.cache_data(ttl=300, show_spinner=False)
def get_visit_stats(days: int = 30) -> dict:
    try:
        from supabase import create_client
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_ANON_KEY"]
        supabase = create_client(url, key)

        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        recent = (
            supabase.table("visits")
            .select("ts,country,country_code,city,region,lat,lon,org")
            .gte("ts", since)
            .order("ts", desc=True)
            .execute()
        )
        total_resp = (
            supabase.table("visits")
            .select("id", count="exact")
            .execute()
        )
        total = total_resp.count if total_resp.count is not None else 0

        visits_df = pd.DataFrame(recent.data or [])
        if not visits_df.empty and "ts" in visits_df.columns:
            visits_df["ts"] = pd.to_datetime(visits_df["ts"], utc=True)

        unique_countries = int(visits_df["country"].nunique()) if not visits_df.empty else 0
        top_countries = (
            visits_df.groupby("country")
            .size()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
            .values.tolist()
            if not visits_df.empty else []
        )

        return {
            "total": total,
            "unique_countries": unique_countries,
            "visits_df": visits_df,
            "top_countries": top_countries,
        }
    except Exception:
        return {
            "total": 0,
            "unique_countries": 0,
            "visits_df": pd.DataFrame(),
            "top_countries": [],
        }
