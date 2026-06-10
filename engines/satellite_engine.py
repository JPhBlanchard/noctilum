"""
Moteur satellite — TLE depuis Celestrak, trajectoires via Skyfield.

Données cachées dans data/tle_<groupe>.txt, rafraîchies toutes les 6 heures.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from skyfield.api import EarthSatellite

from engines.astro_engine import _get_ts

# ── Configuration des groupes ─────────────────────────────────────────────────

GROUPS: dict[str, str] = {
    "ISS / Stations":  "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle",
    "Lumineux (100+)": "https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=tle",
    "Starlink":        "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle",
    "OneWeb":          "https://celestrak.org/NORAD/elements/gp.php?GROUP=oneweb&FORMAT=tle",
    "Météo (NOAA)":    "https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle",
    "Science":         "https://celestrak.org/NORAD/elements/gp.php?GROUP=science&FORMAT=tle",
    "Amateur (AMSAT)": "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=tle",
    "GPS":             "https://celestrak.org/NORAD/elements/gp.php?GROUP=gps-ops&FORMAT=tle",
}

def _writable_data_dir() -> Path:
    candidate = Path(__file__).parent.parent / "data"
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        test = candidate / ".write_test"
        test.touch(); test.unlink()
        return candidate
    except (PermissionError, OSError):
        import tempfile
        p = Path(tempfile.gettempdir()) / "noctilum_data"
        p.mkdir(parents=True, exist_ok=True)
        return p

_DATA_DIR = _writable_data_dir()
_CACHE_TTL_H = 6   # heures avant de retélécharger
_DL_TIMEOUT  = 8   # secondes


# ── TLE cache ─────────────────────────────────────────────────────────────────

def _cache_path(group: str) -> Path:
    slug = group.replace("/", "_").replace(" ", "_").replace("(", "").replace(")", "")
    return _DATA_DIR / f"tle_{slug}.txt"


def _tle_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age_h = (time.time() - path.stat().st_mtime) / 3600
    return age_h < _CACHE_TTL_H


def _fetch_tle(group: str) -> str:
    import requests as _req
    url = GROUPS[group]
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Noctilum/1.0)"}
    resp = _req.get(url, headers=headers, timeout=_DL_TIMEOUT)
    if resp.status_code == 403:
        body = resp.text
        if "not updated" in body or "GP data has not" in body:
            raise _NotUpdatedError()
        resp.raise_for_status()
    resp.raise_for_status()
    return resp.text


class _NotUpdatedError(Exception):
    """Celestrak indique que les données n'ont pas changé depuis le dernier téléchargement."""


def _load_tle_text(group: str) -> str:
    path = _cache_path(group)
    if not _tle_fresh(path):
        try:
            text = _fetch_tle(group)
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except _NotUpdatedError:
            # Données inchangées selon Celestrak — garder le cache existant même s'il est vieux
            if path.exists():
                return path.read_text(encoding="utf-8")
            raise RuntimeError(f"Aucun cache local pour '{group}' et Celestrak indique que les données n'ont pas changé.")
        except Exception:
            if path.exists():
                return path.read_text(encoding="utf-8")
            raise
    return path.read_text(encoding="utf-8")


def _parse_tle(text: str) -> dict[str, tuple[str, str]]:
    """Retourne {nom: (ligne1, ligne2)} à partir d'un bloc TLE 3-lignes."""
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    sats: dict[str, tuple[str, str]] = {}
    i = 0
    while i + 2 < len(lines):
        name = lines[i].strip()
        l1   = lines[i + 1]
        l2   = lines[i + 2]
        if l1.startswith("1 ") and l2.startswith("2 "):
            sats[name] = (l1, l2)
            i += 3
        else:
            i += 1
    return sats


# ── API publique ──────────────────────────────────────────────────────────────

def list_satellites(group: str) -> list[str]:
    """Liste les noms de satellites disponibles pour un groupe."""
    return sorted(_parse_tle(_load_tle_text(group)).keys())


def get_satellites_data(
    observer,
    t: datetime,
    group: str,
    selected: list[str],
    trail_min: float = 5.0,
    trail_step_sec: int = 30,
) -> list[dict]:
    """
    Calcule la position courante et la trajectoire (passé + futur) pour
    chaque satellite sélectionné.

    Retourne une liste de dicts :
      {name, alt, az, above_horizon,
       past_alts, past_azs, future_alts, future_azs}

    past_*  : points de t-trail_min à t (inclus)
    future_*: points de t à t+trail_min (inclus)
    """
    if not selected:
        return []

    try:
        catalog = _parse_tle(_load_tle_text(group))
    except Exception:
        return []

    ts       = _get_ts()
    topos    = observer.skyfield_location()
    results  = []

    # Grille de temps : passé + futur
    n_steps  = max(1, int(trail_min * 60 / trail_step_sec))
    dt_sec   = np.linspace(-trail_min * 60, trail_min * 60, 2 * n_steps + 1)
    t_utc    = t if t.tzinfo else t.replace(tzinfo=timezone.utc)

    t_sky_arr = ts.from_datetimes([
        t_utc + timedelta(seconds=float(s)) for s in dt_sec
    ])
    mid_idx = n_steps  # indice de l'instant courant

    for name in selected:
        if name not in catalog:
            continue
        l1, l2 = catalog[name]
        try:
            sat  = EarthSatellite(l1, l2, name, ts)
            diff = sat - topos
            pos  = diff.at(t_sky_arr)
            alts, azs, _ = pos.altaz()
            alts_deg = alts.degrees
            azs_deg  = azs.degrees

            results.append({
                "name":         name,
                "alt":          float(alts_deg[mid_idx]),
                "az":           float(azs_deg[mid_idx]),
                "above_horizon": float(alts_deg[mid_idx]) >= 0.0,
                "past_alts":   alts_deg[:mid_idx + 1].tolist(),
                "past_azs":    azs_deg[:mid_idx + 1].tolist(),
                "future_alts": alts_deg[mid_idx:].tolist(),
                "future_azs":  azs_deg[mid_idx:].tolist(),
            })
        except Exception:
            continue

    return results
