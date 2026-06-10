"""
Téléchargement centralisé des données statiques Noctilum.

Source primaire : GitLab Package Registry (release data-v1.0)
  → deploy token read-only embarqué (données publiques, pas de risque)
Sources de repli : URLs originales (GitHub, NASA, etc.)
"""

from __future__ import annotations

import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional

_DATA_DIR = Path(__file__).parent.parent / "data"

# Deploy token read-only — uniquement lecture du package registry
_GL_USER  = "gitlab+deploy-token-13996330"
_GL_TOKEN = "gldt-i7r9Xsz_6LNSGdUdn_BG"
_GL_BASE  = (
    "https://gitlab.com/api/v4/projects/82911818"
    "/packages/generic/noctilum-data/1.0"
)

_SOURCES: dict[str, list[str]] = {
    "de440s.bsp": [
        f"{_GL_BASE}/de440s.bsp",
        "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp",
    ],
    "hip_main.dat": [
        f"{_GL_BASE}/hip_main.dat",
        "https://cdsarc.cds.unistra.fr/ftp/cats/I/239/hip_main.dat",
    ],
    "bsc5.json": [
        f"{_GL_BASE}/bsc5.json",
        "https://raw.githubusercontent.com/brettonw/YaleBrightStarCatalog/master/bsc5-all.json",
    ],
    "milkyway.png": [
        f"{_GL_BASE}/milkyway.png",
        "https://raw.githubusercontent.com/Stellarium/stellarium/master/textures/milkyway.png",
    ],
    "mw.json": [
        f"{_GL_BASE}/mw.json",
        "https://raw.githubusercontent.com/ofrohn/d3-celestial/master/data/mw.json",
    ],
    "mw_density_n128.npy": [
        f"{_GL_BASE}/mw_density_n128.npy",
    ],
    "constellations.lines.json": [
        f"{_GL_BASE}/constellations.lines.json",
        "https://raw.githubusercontent.com/ofrohn/d3-celestial/master/data/constellations.lines.json",
    ],
    "constellations.json": [
        f"{_GL_BASE}/constellations.json",
        "https://raw.githubusercontent.com/ofrohn/d3-celestial/master/data/constellations.json",
    ],
    "constellations.bounds.json": [
        f"{_GL_BASE}/constellations.bounds.json",
        "https://raw.githubusercontent.com/ofrohn/d3-celestial/master/data/constellations.bounds.json",
    ],
}


def _gl_request(url: str) -> urllib.request.Request:
    """Requête avec authentification deploy token si URL GitLab."""
    req = urllib.request.Request(url, headers={"User-Agent": "Noctilum/1.0"})
    if _GL_BASE in url:
        import base64
        creds = base64.b64encode(f"{_GL_USER}:{_GL_TOKEN}".encode()).decode()
        req.add_header("Authorization", f"Basic {creds}")
    return req


def download(
    filename: str,
    progress_cb: Optional[Callable[[float], None]] = None,
    timeout: int = 60,
) -> Path:
    """
    Télécharge `filename` dans data/ depuis la première source disponible.
    Retourne le chemin local du fichier.
    Lève FileNotFoundError si toutes les sources échouent.
    """
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest = _DATA_DIR / filename
    urls = _SOURCES.get(filename, [])
    if not urls:
        raise FileNotFoundError(f"Aucune source connue pour : {filename}")

    last_err: Exception = FileNotFoundError(filename)
    for url in urls:
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        try:
            req = _gl_request(url)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(tmp, "wb") as fout:
                    while True:
                        buf = resp.read(65536)
                        if not buf:
                            break
                        fout.write(buf)
                        downloaded += len(buf)
                        if progress_cb and total:
                            progress_cb(min(downloaded / total, 1.0))
            tmp.rename(dest)
            if progress_cb:
                progress_cb(1.0)
            return dest
        except Exception as exc:
            last_err = exc
            if tmp.exists():
                tmp.unlink()

    raise FileNotFoundError(
        f"Impossible de télécharger {filename}.\n"
        f"Dernière erreur : {last_err}\n"
        f"Sources tentées : {urls}"
    )


def ensure(
    filename: str,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> Path:
    """Retourne le chemin local ; télécharge si absent."""
    path = _DATA_DIR / filename
    if path.exists():
        return path
    return download(filename, progress_cb=progress_cb)
