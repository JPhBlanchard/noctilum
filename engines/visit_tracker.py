import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta


def _get_client_ip() -> str:
    try:
        headers = st.context.headers
        forwarded = headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return headers.get("X-Real-IP", "")
    except Exception:
        return ""


def _geolocate(ip: str) -> dict:
    if not ip or ip.startswith("127.") or ip.startswith("192.168."):
        return {}
    try:
        import requests
        r = requests.get(
            f"https://ip-api.com/json/{ip}",
            params={"fields": "country,countryCode,city,region,lat,lon,org"},
            timeout=5,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def track_visit() -> None:
    if st.session_state.get("visit_tracked"):
        return
    st.session_state["visit_tracked"] = True
    try:
        from supabase import create_client
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_ANON_KEY"]
        client = create_client(url, key)

        ip = _get_client_ip()
        geo = _geolocate(ip)

        client.table("visits").insert({
            "ip":           ip or None,
            "country":      geo.get("country"),
            "country_code": geo.get("countryCode"),
            "city":         geo.get("city"),
            "region":       geo.get("region"),
            "lat":          geo.get("lat"),
            "lon":          geo.get("lon"),
            "org":          geo.get("org"),
        }).execute()
    except Exception:
        pass


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
