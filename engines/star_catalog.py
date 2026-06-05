"""
Catalogue BSC5 — Yale Bright Star Catalogue.

Source  : brettonw/YaleBrightStarCatalog (bsc5-all.json, 9 096 étoiles)
Cache   : data/bsc5.json  (téléchargement unique)

Note : l'URL catalog.json référencée dans la spec est absente du dépôt ;
       bsc5-all.json est utilisé car il contient noms communs et désignations Bayer.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from engines.astro_engine import Observer, _get_eph, _to_sky_time

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

CATALOG_URL = (
    "https://raw.githubusercontent.com/brettonw/YaleBrightStarCatalog"
    "/master/bsc5-all.json"
)
CATALOG_PATH = Path(__file__).parent.parent / "data" / "bsc5.json"

_SPECTRAL_COLORS: dict[str, str] = {
    "O": "#AABFFF",
    "B": "#AABFFF",
    "A": "#FFFFFF",
    "F": "#FFF4EA",
    "G": "#FFD966",
    "K": "#FFAA44",
    "M": "#FF6644",
}

# ---------------------------------------------------------------------------
# Fonctions utilitaires de parsing (format BSC5-all)
# ---------------------------------------------------------------------------

def _parse_ra(entry: dict) -> float:
    """RA J2000 en heures décimales depuis les champs RAh/RAm/RAs."""
    h = float(entry.get("RAh") or 0)
    m = float(entry.get("RAm") or 0)
    s = float(entry.get("RAs") or 0)
    return h + m / 60.0 + s / 3600.0


def _parse_dec(entry: dict) -> float:
    """Déclinaison J2000 en degrés depuis DE-/DEd/DEm/DEs."""
    sign = -1.0 if entry.get("DE-") == "-" else 1.0
    d = float(entry.get("DEd") or 0)
    m = float(entry.get("DEm") or 0)
    s = float(entry.get("DEs") or 0)
    return sign * (d + m / 60.0 + s / 3600.0)


def _display_name(entry: dict) -> str:
    """Nom d'affichage : nom commun > désignation Bayer > code BSC > HR n."""
    return (
        entry.get("Common", "").strip()
        or entry.get("BayerF", "").strip()
        or entry.get("Name", "").strip()
        or f"HR {entry.get('HR', '?')}"
    )


# ---------------------------------------------------------------------------
# Couleur spectrale (fonction module + méthode statique sur StarCatalog)
# ---------------------------------------------------------------------------

def spectral_color(spectral_type: str) -> str:
    """Retourne la couleur hex associée au type spectral OBAFGKM."""
    if spectral_type:
        return _SPECTRAL_COLORS.get(spectral_type[0].upper(), "#CCCCCC")
    return "#CCCCCC"


# ---------------------------------------------------------------------------
# StarCatalog
# ---------------------------------------------------------------------------

class StarCatalog:
    """Chargement et interrogation du catalogue Yale Bright Star (BSC5)."""

    def __init__(self) -> None:
        self._df: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # Téléchargement & chargement
    # ------------------------------------------------------------------

    def _download(self) -> None:
        """Télécharge bsc5-all.json et le stocke dans data/bsc5.json."""
        CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(CATALOG_URL, timeout=30)
        response.raise_for_status()
        CATALOG_PATH.write_bytes(response.content)

    def load(self) -> pd.DataFrame:
        """
        Retourne le DataFrame complet du catalogue BSC5.

        Colonnes : name, ra_hours, dec_deg, magnitude, spectral_type, bayer.
        Le fichier est téléchargé une seule fois, le DataFrame mis en cache.
        """
        if self._df is not None:
            return self._df

        if not CATALOG_PATH.exists():
            self._download()

        with CATALOG_PATH.open(encoding="utf-8") as fh:
            raw: list[dict] = json.load(fh)

        rows: list[dict] = []
        for entry in raw:
            # Magnitude obligatoire et numérique
            try:
                mag = float(entry.get("Vmag") or "nan")
            except (ValueError, TypeError):
                continue
            if math.isnan(mag):
                continue

            # Coordonnées
            try:
                ra = _parse_ra(entry)
                dec = _parse_dec(entry)
            except (ValueError, TypeError):
                continue

            rows.append(
                {
                    "name": _display_name(entry),
                    "ra_hours": ra,
                    "dec_deg": dec,
                    "magnitude": mag,
                    "spectral_type": entry.get("SpType", "").strip(),
                    "bayer": entry.get("Bayer", "").strip(),
                }
            )

        self._df = pd.DataFrame(rows)
        return self._df

    # ------------------------------------------------------------------
    # Visibilité
    # ------------------------------------------------------------------

    def get_visible(
        self,
        observer: Observer,
        t: Optional[datetime] = None,
        mag_limit: float = 5.0,
    ) -> pd.DataFrame:
        """
        Retourne les étoiles visibles (alt > 0°) sous la limite de magnitude.

        Colonnes supplémentaires : alt_deg, az_deg.
        Le calcul est vectorisé via Skyfield Star (un seul appel pour toutes
        les étoiles candidates).
        """
        from skyfield.api import Star

        df = self.load()
        candidates = df[df["magnitude"] <= mag_limit].reset_index(drop=True)
        if candidates.empty:
            return candidates.assign(
                alt_deg=pd.Series(dtype=float),
                az_deg=pd.Series(dtype=float),
            )

        eph = _get_eph()
        t_sky = _to_sky_time(t)
        location = observer.skyfield_location()

        stars = Star(
            ra_hours=candidates["ra_hours"].to_numpy(),
            dec_degrees=candidates["dec_deg"].to_numpy(),
        )
        astrometric = (eph["earth"] + location).at(t_sky).observe(stars)
        apparent = astrometric.apparent()
        alt, az, _ = apparent.altaz("standard")

        candidates = candidates.copy()
        candidates["alt_deg"] = alt.degrees
        candidates["az_deg"] = az.degrees

        return candidates[candidates["alt_deg"] > 0.0].reset_index(drop=True)

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    @staticmethod
    def spectral_color(spectral_type: str) -> str:
        """Couleur hex du type spectral (O/B→bleu, A→blanc, F→jaune-blanc,
        G→jaune, K→orange, M→rouge, défaut→gris)."""
        return spectral_color(spectral_type)
