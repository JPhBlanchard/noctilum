import streamlit as st
import streamlit.components.v1 as _components
import pandas as pd
from datetime import datetime, timezone, timedelta


def track_visit() -> None:
    if st.session_state.get("visit_tracked"):
        return
    try:
        supabase_url = st.secrets["SUPABASE_URL"]
        supabase_key = st.secrets["SUPABASE_ANON_KEY"]
    except Exception:
        return

    html = f"""<script>
(async () => {{
    try {{
        const ipRes = await fetch('https://api.ipify.org?format=json');
        const {{ ip }} = await ipRes.json();
        const geoRes = await fetch(
            'https://ip-api.com/json/' + ip + '?fields=country,countryCode,city,region,lat,lon,org'
        );
        const geo = await geoRes.json();
        await fetch('{supabase_url}/rest/v1/visits', {{
            method: 'POST',
            headers: {{
                'apikey': '{supabase_key}',
                'Content-Type': 'application/json'
            }},
            body: JSON.stringify({{
                ip: ip,
                country: geo.country,
                country_code: geo.countryCode,
                city: geo.city,
                region: geo.region,
                lat: geo.lat,
                lon: geo.lon,
                org: geo.org
            }})
        }});
    }} catch(e) {{}}
}})();
</script>"""

    _components.html(html, height=0)
    st.session_state["visit_tracked"] = True


@st.cache_data(ttl=300, show_spinner=False)
def get_visit_stats(days: int = 30) -> dict:
    try:
        from supabase import create_client
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_ANON_KEY"]
        client = create_client(url, key)

        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        recent = (
            client.table("visits")
            .select("ts,country,country_code,city,region,lat,lon,org")
            .gte("ts", since)
            .order("ts", desc=True)
            .execute()
        )
        total_resp = (
            client.table("visits")
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
