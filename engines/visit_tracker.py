import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta


def _geolocate(ip: str) -> dict:
    if not ip or ip.startswith("127.") or ip.startswith("10.") or ip.startswith("192.168.") or ip.startswith("172."):
        return {}
    try:
        import requests
        r = requests.get(
            f"https://ip-api.com/json/{ip}",
            params={"fields": "country,countryCode,city,region,lat,lon,org"},
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "success":
                return data
    except Exception:
        pass
    return {}


def get_client_ip_js() -> str | None:
    """Retourne l'IP cliente via JS (None = pas encore prêt, str = IP obtenue)."""
    try:
        from streamlit_javascript import st_javascript
        result = st_javascript(
            "await fetch('https://api.ipify.org?format=json')"
            ".then(r => r.json()).then(d => d.ip).catch(() => '')"
        )
        if result == 0:  # composant pas encore prêt (1er render)
            return None
        return str(result) if result else ""
    except Exception:
        return ""


def track_visit(client_ip: str) -> None:
    if st.session_state.get("visit_tracked"):
        return
    if client_ip is None:  # JS pas encore prêt
        return
    st.session_state["visit_tracked"] = True
    try:
        from supabase import create_client
        url = st.secrets["SUPABASE_URL"].strip()
        key = st.secrets["SUPABASE_ANON_KEY"].strip()
        supabase = create_client(url, key)

        geo = _geolocate(client_ip)

        supabase.table("visits").insert({
            "ip":           client_ip or None,
            "country":      geo.get("country"),
            "country_code": geo.get("countryCode"),
            "city":         geo.get("city"),
            "region":       geo.get("region"),
            "lat":          geo.get("lat"),
            "lon":          geo.get("lon"),
            "org":          geo.get("org"),
        }).execute()
        st.session_state["_visit_error"] = None
    except Exception as e:
        st.session_state["_visit_error"] = str(e)


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
