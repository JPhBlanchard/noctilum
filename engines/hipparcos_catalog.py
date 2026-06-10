"""
Catalogue Hipparcos (ESA, 1997) — 118 218 étoiles jusqu'à mag ~12.4.

Interface identique à StarCatalog : get_visible() retourne un DataFrame
avec les colonnes name, magnitude, ra_hours, dec_deg, alt_deg, az_deg.

Le fichier hip_main.dat (~55 Mo) est téléchargé depuis CDS-VizieR à la demande.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Callable, Optional
from datetime import datetime

import pandas as pd

from engines.astro_engine import Observer, _get_eph, _to_sky_time

_DATA_DIR = Path(__file__).parent.parent / "data"
_HIP_PATH = _DATA_DIR / "hip_main.dat"
_HIP_URL  = "https://cdsarc.cds.unistra.fr/ftp/cats/I/239/hip_main.dat"

# Cache module-level (reset si le module est rechargé)
_cache_df: Optional[pd.DataFrame] = None


def is_available() -> bool:
    return _HIP_PATH.exists()


def download(progress_cb: Optional[Callable[[float], None]] = None) -> None:
    """Télécharge hip_main.dat (GitLab release en priorité, CDS en repli)."""
    from engines.data_download import download as _dl
    _dl("hip_main.dat", progress_cb=progress_cb)
    global _cache_df
    _cache_df = None


def load() -> pd.DataFrame:
    """Charge hip_main.dat et le met en cache (module-level)."""
    global _cache_df
    if _cache_df is not None:
        return _cache_df

    if not _HIP_PATH.exists():
        raise FileNotFoundError(
            f"hip_main.dat introuvable dans {_DATA_DIR}. "
            "Utilisez download() ou le bouton de l'interface."
        )

    _COL_NAMES = (
        'Catalog', 'HIP', 'Proxy', 'RAhms', 'DEdms', 'Vmag',
        'VarFlag', 'r_Vmag', 'RAdeg', 'DEdeg', 'AstroRef', 'Plx', 'pmRA',
        'pmDE', 'e_RAdeg', 'e_DEdeg', 'e_Plx', 'e_pmRA', 'e_pmDE', 'DE:RA',
        'Plx:RA', 'Plx:DE', 'pmRA:RA', 'pmRA:DE', 'pmRA:Plx', 'pmDE:RA',
        'pmDE:DE', 'pmDE:Plx', 'pmDE:pmRA', 'F1', 'F2', '---', 'BTmag',
        'e_BTmag', 'VTmag', 'e_VTmag', 'm_BTmag', 'B-V', 'e_B-V', 'r_B-V',
        'V-I', 'e_V-I', 'r_V-I', 'CombMag', 'Hpmag', 'e_Hpmag', 'Hpscat',
        'o_Hpmag', 'm_Hpmag', 'Hpmax', 'HPmin', 'Period', 'HvarType',
        'moreVar', 'morePhoto', 'CCDM', 'n_CCDM', 'Nsys', 'Ncomp',
        'MultFlag', 'Source', 'Qual', 'm_HIP', 'theta', 'rho', 'e_rho',
        'dHp', 'e_dHp', 'Survey', 'Chart', 'Notes', 'HD', 'BD', 'CoD',
        'CPD', '(V-I)red', 'SpType', 'r_SpType',
    )
    df = pd.read_csv(
        _HIP_PATH,
        sep='|',
        names=_COL_NAMES,
        usecols=['HIP', 'Vmag', 'RAdeg', 'DEdeg', 'SpType'],
        na_values=['     ', '       ', '        ', '            '],
    )
    df = df.rename(columns={
        'Vmag':   'magnitude',
        'RAdeg':  'ra_degrees',
        'DEdeg':  'dec_degrees',
        'SpType': 'spectral_type',
    })
    df['ra_hours'] = df['ra_degrees'] / 15.0
    df['spectral_type'] = df['spectral_type'].fillna('').str.strip()
    df = df.set_index('HIP')

    # Nom lisible : "HIP 11767" (Polaris)
    df["name"] = "HIP " + df.index.astype(str)
    # Supprimer les lignes sans magnitude ni coordonnées
    df = df.dropna(subset=["magnitude", "ra_hours", "dec_degrees"])

    _cache_df = df
    return _cache_df


def get_visible(
    observer: Observer,
    t: Optional[datetime] = None,
    mag_limit: float = 5.0,
    min_alt: float = 0.0,
) -> pd.DataFrame:
    """
    Retourne les étoiles Hipparcos au-dessus de min_alt° sous mag_limit.

    Colonnes : name, magnitude, ra_hours, dec_deg, alt_deg, az_deg.
    Le calcul inclut les mouvements propres (époque 1991.25 → J2000).
    """
    from skyfield.api import Star

    df = load()
    candidates = df[df["magnitude"] <= mag_limit].copy()

    if candidates.empty:
        return pd.DataFrame(columns=["name", "magnitude", "ra_hours", "dec_deg",
                                     "alt_deg", "az_deg", "spectral_type"])

    eph      = _get_eph()
    t_sky    = _to_sky_time(t)
    location = observer.skyfield_location()

    stars = Star(
        ra_hours=candidates["ra_hours"].to_numpy(),
        dec_degrees=candidates["dec_degrees"].to_numpy(),
    )
    astrometric = (eph["earth"] + location).at(t_sky).observe(stars)
    apparent    = astrometric.apparent()
    alt, az, _  = apparent.altaz("standard")

    candidates = candidates.copy()
    candidates["alt_deg"] = alt.degrees
    candidates["az_deg"]  = az.degrees
    # Renommage ici seulement (Star.from_dataframe avait besoin de "dec_degrees")
    candidates = candidates.rename(columns={"dec_degrees": "dec_deg"})

    return (
        candidates[candidates["alt_deg"] > min_alt]
        [["name", "magnitude", "ra_hours", "dec_deg", "alt_deg", "az_deg", "spectral_type"]]
        .reset_index(drop=True)
    )
