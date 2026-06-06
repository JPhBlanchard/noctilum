"""
Catalogue de recherche unifié : étoiles nommées, Messier, constellations, planètes.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Optional

_static_catalog: list["CelestialTarget"] | None = None


@dataclass
class CelestialTarget:
    label: str
    category: str            # 'star' | 'messier' | 'constellation' | 'planet'
    description: str
    ra_hours: Optional[float] = None
    dec_deg: Optional[float]  = None
    magnitude: Optional[float] = None
    planet_name: Optional[str] = None


# ── Normalisation ─────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Minuscules + suppression des diacritiques."""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# ── Construction du catalogue statique ───────────────────────────────────────

def _build_static() -> list[CelestialTarget]:
    targets: list[CelestialTarget] = []

    # Étoiles nommées (BSC5)
    from engines.star_catalog import StarCatalog
    df = StarCatalog().load()
    for _, row in df[df["name"].str.len() > 0].iterrows():
        bayer = row["bayer"] or ""
        targets.append(CelestialTarget(
            label=row["name"],
            category="star",
            description=f"Étoile{' ' + bayer if bayer else ''} · mag {row['magnitude']:.1f}",
            ra_hours=float(row["ra_hours"]),
            dec_deg=float(row["dec_deg"]),
            magnitude=float(row["magnitude"]),
        ))
        if bayer:                              # désignation Bayer comme alias
            targets.append(CelestialTarget(
                label=bayer,
                category="star",
                description=f"{row['name']} · mag {row['magnitude']:.1f}",
                ra_hours=float(row["ra_hours"]),
                dec_deg=float(row["dec_deg"]),
                magnitude=float(row["magnitude"]),
            ))

    # Objets Messier
    from engines.messier_catalog import _CATALOG as _MC
    _TYPE_FR = {
        "Gx": "Galaxie", "OC": "Amas ouvert", "Gb": "Amas globulaire",
        "Nb": "Nébuleuse", "Pl": "Nébuleuse planétaire", "SNR": "Rémanent SN",
    }
    for num, ra_h, dec_d, mag, typ, name_fr in _MC:
        type_str = _TYPE_FR.get(typ, typ)
        desc = f"M{num} · {type_str} · mag {mag:.1f}"
        targets.append(CelestialTarget(
            label=f"M{num}", category="messier",
            description=desc, ra_hours=ra_h, dec_deg=dec_d, magnitude=mag,
        ))
        if name_fr:
            targets.append(CelestialTarget(
                label=name_fr, category="messier",
                description=desc, ra_hours=ra_h, dec_deg=dec_d, magnitude=mag,
            ))

    # Centres de constellations
    from engines.constellation_lines import _load_centers
    for ra_h, dec_d, name in _load_centers():
        targets.append(CelestialTarget(
            label=name, category="constellation",
            description="Constellation",
            ra_hours=ra_h, dec_deg=dec_d,
        ))

    return targets


def get_static_catalog() -> list[CelestialTarget]:
    global _static_catalog
    if _static_catalog is None:
        _static_catalog = _build_static()
    return _static_catalog


# ── Recherche ─────────────────────────────────────────────────────────────────

def search(
    query: str,
    planets_data: list[dict] | None = None,
) -> list[CelestialTarget]:
    """
    Retourne jusqu'à 15 CelestialTarget correspondant à la requête.
    Priorité : commence_par > contient, planètes en tête.
    """
    q = _norm(query.strip())
    if not q:
        return []

    catalog = get_static_catalog()
    starts, contains = [], []
    for tgt in catalog:
        n = _norm(tgt.label)
        if n.startswith(q):
            starts.append(tgt)
        elif q in n:
            contains.append(tgt)

    # Planètes / corps du système solaire (position dynamique)
    planet_hits: list[CelestialTarget] = []
    for p in (planets_data or []):
        if q in _norm(p["name"]):
            planet_hits.append(CelestialTarget(
                label=p["name"],
                category="planet",
                description=f"Alt {p['alt']:.1f}°  Az {p['az']:.1f}°",
                magnitude=p.get("magnitude"),
                planet_name=p["name"],
            ))

    # Fusion avec dédoublonnage sur le label normalisé
    seen: set[str] = set()
    results: list[CelestialTarget] = []
    for tgt in planet_hits + starts + contains:
        k = _norm(tgt.label)
        if k not in seen:
            seen.add(k)
            results.append(tgt)
        if len(results) >= 15:
            break

    return results


# ── Résolution en (alt, az) ───────────────────────────────────────────────────

def resolve_target(
    target: CelestialTarget,
    observer,
    t,
    planets_data: list[dict] | None = None,
) -> tuple[float, float]:
    """Retourne (alt°, az°) pour la cible à l'instant t."""
    if target.category == "planet":
        for p in (planets_data or []):
            if p["name"] == target.planet_name:
                return float(p["alt"]), float(p["az"])
        raise ValueError(f"Planète {target.planet_name!r} introuvable")

    if target.ra_hours is None or target.dec_deg is None:
        raise ValueError("ra_hours/dec_deg manquants")

    from skyfield.api import Star
    from engines.astro_engine import _get_eph, _to_sky_time

    eph   = _get_eph()
    t_sky = _to_sky_time(t)
    obs   = eph["earth"] + observer.skyfield_location()
    star  = Star(ra_hours=target.ra_hours, dec_degrees=target.dec_deg)
    alt, az, _ = obs.at(t_sky).observe(star).apparent().altaz("standard")
    return float(alt.degrees), float(az.degrees)
