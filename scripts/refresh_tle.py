import requests
import pathlib
import time

GROUPS = {
    'ISS___Stations': 'https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle',
    'Lumineux_100+':  'https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=tle',
    'Starlink':       'https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle',
    'OneWeb':         'https://celestrak.org/NORAD/elements/gp.php?GROUP=oneweb&FORMAT=tle',
    'Météo_NOAA':     'https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle',
    'Science':        'https://celestrak.org/NORAD/elements/gp.php?GROUP=science&FORMAT=tle',
    'Amateur_AMSAT':  'https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=tle',
    'GPS':            'https://celestrak.org/NORAD/elements/gp.php?GROUP=gps-ops&FORMAT=tle',
}

headers = {'User-Agent': 'Mozilla/5.0 (compatible; Noctilum/1.0)'}
data_dir = pathlib.Path('data')
data_dir.mkdir(exist_ok=True)

for slug, url in GROUPS.items():
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        (data_dir / f'tle_{slug}.txt').write_text(r.text, encoding='utf-8')
        print(f'OK  {slug}')
        time.sleep(1)
    except Exception as e:
        print(f'ERR {slug}: {e}')
