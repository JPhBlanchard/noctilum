"""
Catalogue de Messier — 110 objets du ciel profond.

Coordonnées J2000 (RA en heures décimales, Dec en degrés).
Source : catalogue officiel IAU / SEDS.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from engines.astro_engine import Observer, _get_eph, _to_sky_time
from engines.projection import altaz_to_xy

# ---------------------------------------------------------------------------
# Données du catalogue
# (num, ra_hours, dec_deg, mag, type_code, nom_commun_fr)
# Types : Gx=Galaxie  OC=Amas ouvert  Gb=Amas globulaire
#         Nb=Nébuleuse  Pl=Nébuleuse planétaire  SNR=Rémanent de supernova
# ---------------------------------------------------------------------------

_CATALOG: list[tuple] = [
    (1,    5.5753,   22.0167,  8.4,  'SNR', 'Nébuleuse du Crabe'),
    (2,   21.5583,   -0.8233,  6.5,  'Gb',  ''),
    (3,   13.7050,   28.3767,  6.2,  'Gb',  ''),
    (4,   16.3933,  -26.5250,  5.9,  'Gb',  ''),
    (5,   15.3100,    2.0817,  5.8,  'Gb',  ''),
    (6,   17.6717,  -32.2133,  4.2,  'OC',  'Amas du Papillon'),
    (7,   17.8983,  -34.8167,  3.3,  'OC',  ''),
    (8,   18.0617,  -24.3800,  6.0,  'Nb',  'Nébuleuse Lagune'),
    (9,   17.3200,  -18.5150,  7.7,  'Gb',  ''),
    (10,  16.9517,   -4.1000,  6.6,  'Gb',  ''),
    (11,  18.8517,   -6.2700,  5.8,  'OC',  'Amas du Canard Sauvage'),
    (12,  16.7867,   -1.9467,  6.7,  'Gb',  ''),
    (13,  16.6950,   36.4600,  5.8,  'Gb',  "Grand Amas d'Hercule"),
    (14,  17.6267,   -3.2467,  7.6,  'Gb',  ''),
    (15,  21.4997,   12.1667,  6.2,  'Gb',  ''),
    (16,  18.3133,  -13.7800,  6.0,  'Nb',  "Nébuleuse de l'Aigle"),
    (17,  18.3450,  -16.1833,  7.0,  'Nb',  'Nébuleuse Oméga'),
    (18,  18.3333,  -17.1333,  6.9,  'OC',  ''),
    (19,  17.0433,  -26.2667,  6.8,  'Gb',  ''),
    (20,  18.0283,  -23.0333,  9.0,  'Nb',  'Nébuleuse Trifide'),
    (21,  18.0767,  -22.5000,  5.9,  'OC',  ''),
    (22,  18.6050,  -23.9033,  5.1,  'Gb',  ''),
    (23,  17.9500,  -19.0167,  5.5,  'OC',  ''),
    (24,  18.2867,  -18.5500,  4.5,  'OC',  'Nuage stellaire du Sagittaire'),
    (25,  18.5250,  -19.2333,  4.6,  'OC',  ''),
    (26,  18.7550,   -9.3833,  8.0,  'OC',  ''),
    (27,  19.9933,   22.7167,  7.5,  'Pl',  'Nébuleuse Dumbbell'),
    (28,  18.4100,  -24.8700,  6.8,  'Gb',  ''),
    (29,  20.3983,   38.5233,  6.6,  'OC',  ''),
    (30,  21.6733,  -23.1800,  7.2,  'Gb',  ''),
    (31,   0.7117,   41.2700,  3.4,  'Gx',  "Galaxie d'Andromède"),
    (32,   0.7117,   40.8667,  8.7,  'Gx',  ''),
    (33,   1.5633,   30.6600,  5.7,  'Gx',  'Galaxie du Triangle'),
    (34,   2.7017,   42.7167,  5.2,  'OC',  ''),
    (35,   6.1483,   24.3500,  5.1,  'OC',  ''),
    (36,   5.5983,   34.1333,  6.0,  'OC',  ''),
    (37,   5.8733,   32.5500,  5.6,  'OC',  ''),
    (38,   5.4783,   35.8500,  6.4,  'OC',  ''),
    (39,  21.5317,   48.4333,  4.6,  'OC',  ''),
    (40,  12.3717,   58.0833,  9.0,  'OC',  ''),
    (41,   6.7800,  -20.7167,  4.5,  'OC',  ''),
    (42,   5.5883,   -5.3900,  4.0,  'Nb',  "Grande Nébuleuse d'Orion"),
    (43,   5.5917,   -5.2667,  9.0,  'Nb',  ''),
    (44,   8.6717,   19.9833,  3.1,  'OC',  'Praesepe / La Ruche'),
    (45,   3.7833,   24.1167,  1.6,  'OC',  'Pléiades'),
    (46,   7.6967,  -14.8167,  6.1,  'OC',  ''),
    (47,   7.6100,  -14.5000,  4.4,  'OC',  ''),
    (48,   8.2317,   -5.8000,  5.8,  'OC',  ''),
    (49,  12.3317,    8.0000,  8.4,  'Gx',  ''),
    (50,   7.0483,   -8.3833,  5.9,  'OC',  ''),
    (51,  13.4983,   47.1950,  8.4,  'Gx',  'Galaxie du Tourbillon'),
    (52,  23.4017,   61.5933,  6.9,  'OC',  ''),
    (53,  13.2150,   18.1667,  7.7,  'Gb',  ''),
    (54,  18.9183,  -30.4783,  7.6,  'Gb',  ''),
    (55,  19.6667,  -30.9617,  6.3,  'Gb',  ''),
    (56,  19.2767,   30.1833,  8.3,  'Gb',  ''),
    (57,  18.8933,   33.0283,  8.8,  'Pl',  'Nébuleuse de la Lyre'),
    (58,  12.6283,   11.8183,  9.8,  'Gx',  ''),
    (59,  12.7000,   11.6467, 10.6,  'Gx',  ''),
    (60,  12.7267,   11.5533,  8.8,  'Gx',  ''),
    (61,  12.3683,    4.4733,  9.7,  'Gx',  ''),
    (62,  17.0217,  -30.1133,  6.5,  'Gb',  ''),
    (63,  13.2633,   42.0317,  8.6,  'Gx',  'Galaxie du Tournesol'),
    (64,  12.9467,   21.6817,  8.5,  'Gx',  "Galaxie de l'Œil Noir"),
    (65,  11.3150,   13.0933,  9.3,  'Gx',  ''),
    (66,  11.3367,   12.9917,  8.9,  'Gx',  ''),
    (67,   8.8500,   11.8167,  6.9,  'OC',  ''),
    (68,  12.6600,  -26.7450,  7.3,  'Gb',  ''),
    (69,  18.5233,  -32.3483,  7.7,  'Gb',  ''),
    (70,  18.7217,  -32.2950,  7.9,  'Gb',  ''),
    (71,  19.8967,   18.7783,  6.1,  'Gb',  ''),
    (72,  20.8917,  -12.5367,  9.3,  'Gb',  ''),
    (73,  20.9883,  -12.6333,  9.0,  'OC',  ''),
    (74,   1.6117,   15.7833,  9.4,  'Gx',  ''),
    (75,  20.1017,  -21.9217,  8.5,  'Gb',  ''),
    (76,   1.7050,   51.5767, 10.1,  'Pl',  ''),
    (77,   2.7117,   -0.0133,  8.9,  'Gx',  ''),
    (78,   5.7783,    0.3833,  8.3,  'Nb',  ''),
    (79,   5.4017,  -24.5233,  7.7,  'Gb',  ''),
    (80,  16.2850,  -22.9767,  7.3,  'Gb',  ''),
    (81,   9.9258,   69.0650,  6.9,  'Gx',  'Galaxie de Bode'),
    (82,   9.9317,   69.6800,  8.4,  'Gx',  'Galaxie du Cigare'),
    (83,  13.6167,  -29.8650,  7.6,  'Gx',  ''),
    (84,  12.4167,   12.8867, 10.1,  'Gx',  ''),
    (85,  12.4217,   18.1917,  9.2,  'Gx',  ''),
    (86,  12.4267,   12.9450,  9.8,  'Gx',  ''),
    (87,  12.5133,   12.3917,  8.6,  'Gx',  'Virgo A'),
    (88,  12.5317,   14.4200,  9.6,  'Gx',  ''),
    (89,  12.5933,   12.5567, 10.7,  'Gx',  ''),
    (90,  12.6133,   13.1633,  9.5,  'Gx',  ''),
    (91,  12.5917,   14.4967, 10.2,  'Gx',  ''),
    (92,  17.2850,   43.1367,  6.4,  'Gb',  ''),
    (93,   7.7433,  -23.8667,  6.2,  'OC',  ''),
    (94,  12.8500,   41.1200,  8.2,  'Gx',  ''),
    (95,  10.7300,   11.7033,  9.7,  'Gx',  ''),
    (96,  10.7800,   11.8200,  9.2,  'Gx',  ''),
    (97,  11.2483,   55.0183,  9.9,  'Pl',  'Nébuleuse du Hibou'),
    (98,  12.2317,   14.9000, 10.1,  'Gx',  ''),
    (99,  12.3167,   14.4167,  9.9,  'Gx',  ''),
    (100, 12.3817,   15.8233,  9.3,  'Gx',  ''),
    (101, 14.0533,   54.3500,  7.9,  'Gx',  'Galaxie Moulinet'),
    (102, 15.1017,   55.7633, 10.7,  'Gx',  ''),
    (103,  1.5567,   60.6583,  7.4,  'OC',  ''),
    (104, 12.6667,  -11.6233,  8.0,  'Gx',  'Galaxie Sombrero'),
    (105, 10.7967,   12.5817,  9.8,  'Gx',  ''),
    (106, 12.3167,   47.3033,  8.4,  'Gx',  ''),
    (107, 16.5417,  -13.0533,  7.8,  'Gb',  ''),
    (108, 11.1917,   55.6733, 10.0,  'Gx',  ''),
    (109, 11.9600,   53.3750,  9.8,  'Gx',  ''),
    (110,  0.6783,   41.6850,  8.5,  'Gx',  ''),
]

# Type → (symbole Plotly, couleur hex, nom français)
TYPE_INFO: dict[str, tuple[str, str, str]] = {
    'Gx':  ('circle-open',   '#FFB347', 'Galaxie'),
    'OC':  ('asterisk-open', '#90EE90', 'Amas ouvert'),
    'Gb':  ('circle-cross',  '#7CFC00', 'Amas globulaire'),
    'Nb':  ('diamond-open',  '#87CEEB', 'Nébuleuse'),
    'Pl':  ('circle-dot',    '#DDA0DD', 'Nébuleuse planétaire'),
    'SNR': ('triangle-up-open', '#FF7F7F', 'Rémanent de supernova'),
}
_DEFAULT_TYPE = ('x-thin-open', '#CCCCCC', 'Autre')


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def get_messier_visible(
    observer: Observer,
    t: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Retourne un DataFrame des objets de Messier au-dessus de l'horizon.

    Colonnes : num, label, name, mag, type, symbol, color, alt_deg, az_deg
    """
    from skyfield.api import Star

    ra_arr  = np.array([row[1] for row in _CATALOG])
    dec_arr = np.array([row[2] for row in _CATALOG])

    eph      = _get_eph()
    t_sky    = _to_sky_time(t)
    location = observer.skyfield_location()
    obs      = eph["earth"] + location

    stars = Star(ra_hours=ra_arr, dec_degrees=dec_arr)
    alt_a, az_a, _ = obs.at(t_sky).observe(stars).apparent().altaz("standard")

    rows = []
    for i, entry in enumerate(_CATALOG):
        num, ra, dec, mag, typ, name_fr = entry
        alt = alt_a.degrees[i]
        az  = az_a.degrees[i]
        if alt <= 0.0:
            continue
        sym, col, _ = TYPE_INFO.get(typ, _DEFAULT_TYPE)
        rows.append({
            'num':     num,
            'label':   f'M{num}',
            'name':    name_fr or f'M{num}',
            'mag':     mag,
            'type':    typ,
            'symbol':  sym,
            'color':   col,
            'alt_deg': round(alt, 3),
            'az_deg':  round(az,  3),
        })

    return pd.DataFrame(rows)
