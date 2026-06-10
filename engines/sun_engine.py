"""
Rendu photographique du Soleil (image SDO/SOHO).

API publique :
  render_sun_image(size) → bytes PNG  (masque circulaire, pas d'orientation)
"""
from __future__ import annotations

from pathlib import Path

_SUN_PHOTO = Path(__file__).parent.parent / "data" / "sun.gif"
_cache: dict[int, bytes] = {}


def render_sun_image(size: int = 64) -> bytes:
    """
    Retourne les bytes PNG du Soleil avec masque circulaire.
    Pas de rotation (surface uniformément chaotique).
    """
    if size in _cache:
        return _cache[size]

    import io
    import numpy as np
    from PIL import Image

    img = Image.open(_SUN_PHOTO).convert("RGB")
    w, h = img.size
    s = min(w, h)
    img = img.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
    img = img.resize((size, size), Image.LANCZOS)

    arr = np.asarray(img, dtype=np.uint8)

    R  = size / 2.0
    ys, xs = np.mgrid[0:size, 0:size]
    nx = (xs - R + 0.5) / R
    ny = (R - 0.5 - ys) / R
    on_disk = (nx ** 2 + ny ** 2) <= 1.0

    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    rgba[:, :, :3] = arr
    rgba[:, :, 3]  = np.where(on_disk, 255, 0).astype(np.uint8)

    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG")
    png = buf.getvalue()
    _cache[size] = png
    return png
