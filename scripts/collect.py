#!/usr/bin/env python3
"""Recopila pronósticos independientes para Rosario y archiva la primera toma de cada día.
Sin claves, sin dependencias externas. No calcula precisión sin observaciones verificadas.
"""
import datetime as dt
import json
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
ZONE = ZoneInfo('America/Montevideo')
COORDS = (-34.312, -57.351)
MODELS = {
    'ecmwf': ('ECMWF', 'ecmwf_ifs'),
    'gfs': ('GFS', 'ncep_gfs_global'),
    'icon': ('ICON', 'icon_global'),
    # Modelo de inteligencia artificial de ECMWF; solo evaluación, no altera el resumen principal.
    'aifs': ('ECMWF AIFS (IA)', 'ecmwf_aifs025_single'),
}
FIELDS = ('temperature_2m_max', 'temperature_2m_min', 'precipitation_sum')

def api_url(model_code):
    args = {
        'latitude': COORDS[0], 'longitude': COORDS[1],
        'timezone': 'America/Montevideo', 'daily': ','.join(FIELDS),
        'forecast_days': 3, 'models': model_code,
    }
    return 'https://api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(args)

def fetch_model(model_code):
    """Tres intentos solo para fallas de transporte temporales; nunca inventar datos."""
    request = urllib.request.Request(
        api_url(model_code),
        headers={'User-Agent': 'MiClimaRosario/6.1 (weather observer)', 'Accept': 'application/json'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=22) as response:
                payload = json.load(response)
            if 'error' in payload:
                raise ValueError(str(payload.get('reason') or payload['error']))
            return payload
        except urllib.error.HTTPError as exc:
            if exc.code != 429 and not 500 <= exc.code <= 599:
                raise
            if attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionResetError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError('Falló la consulta al modelo')

def safe_number(value, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    if not lo <= value <= hi:
        return None
    return round(value, 2)

def parse_daily(payload):
    daily = payload.get('daily') or {}
    dates = daily.get('time')
    if not isinstance(dates, list) or not dates:
        raise ValueError('Faltan fechas daily.time')
    output = {}
    for i, date in enumerate(dates):
        dt.date.fromisoformat(date)
        vals = {}
        for key in FIELDS:
            arr = daily.get(key)
            if not isinstance(arr, list) or len(arr) != len(dates):
                raise ValueError(f'Faltan valores: {key}')
            bound = (0, 3000) if key == 'precipitation_sum' else (-70, 65)
            vals[key] = safe_number(arr[i], *bound)
        if all(v is None for v in vals.values()):
            continue
        output[date] = {'tmax': vals['temperature_2m_max'],
                        'tmin': vals['temperature_2m_min'],
                        'rain_mm': vals['precipitation_sum']}
    if not output:
        raise ValueError('No se obtuvo ningún día útil')
    return output

def dump_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(path)

def build_capture(fetcher=fetch_model, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    local = now.astimezone(ZONE)
    today = local.date().isoformat()
    tomorrow = (local.date() + dt.timedelta(days=1)).isoformat()
    day_after = (local.date() + dt.timedelta(days=2)).isoformat()
    dates = (today, tomorrow, day_after)
    days = {date: {} for date in dates}
    failed = {}
    for name, (_, code) in MODELS.items():
        try:
            parsed = parse_daily(fetcher(code))
            for date in dates:
                if date in parsed:
                    days[date][name] = parsed[date]
            if tomorrow not in parsed:
                failed[name] = 'El modelo no devolvió el pronóstico de mañana'
        except Exception as error:
            failed[name] = f'{type(error).__name__}: {str(error)[:160]}'
    # La nueva fuente experimental no puede sustituir a todas las fuentes originales.
    if not any(key in days[tomorrow] for key in ('ecmwf','gfs','icon')):
        raise RuntimeError('Ningún modelo principal devolvió pronóstico para mañana; se conservan datos existentes')
    return {
        'schema': 1,
        'location': 'Rosario, Colonia, Uruguay',
        'coordinates': {'latitude': COORDS[0], 'longitude': COORDS[1]},
        'timezone': 'America/Montevideo',
        'collected_at_utc': now.isoformat().replace('+00:00','Z'),
        'collection_local_date': today,
        'target_tomorrow': tomorrow,
        'sources': {key: {'name': label, 'code': code, 'available':key not in failed} for key, (label,code) in MODELS.items()},
        'errors': failed,
        'days': days,
        'verification': {'status':'pending', 'note':'Sin mediciones independientes verificadas; no hay ranking de precisión.'},
        'sources_note': 'Modelo meteorológico de Open-Meteo. No es medición de una estación ni porcentaje de probabilidad.'
    }

def run():
    record = build_capture()
    DATA.mkdir(parents=True, exist_ok=True)
    archive = DATA / 'forecast_archive' / f"{record['collection_local_date']}.json"
    if not archive.exists():
        dump_json(archive, record)
    dump_json(DATA / 'latest.json', record)
    files = sorted(p.stem for p in (DATA / 'forecast_archive').glob('????-??-??.json'))
    dump_json(DATA / 'archive_index.json', {'schema':1, 'collection_days':len(files), 'dates':files})
    print(f"Recopilado {record['collection_local_date']}: {len(record['days'][record['target_tomorrow']])}/{len(MODELS)} modelos; archivo {archive.name}; fallos {record['errors']}")

if __name__ == '__main__':
    run()
