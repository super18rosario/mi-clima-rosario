#!/usr/bin/env python3
"""Recopila pronósticos independientes para Rosario y archiva, para cada día local, la toma
más cercana a la hora fija de evaluación (21:00 de Uruguay, ventana 15:00-24:00).
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
# Hora fija de emisión del pronóstico evaluado para el día siguiente. Coincide con la
# ejecución programada de las 00:23 UTC (21:23 en Uruguay). Si GitHub la demora u omite,
# vale la toma más cercana dentro de la ventana; fuera de ella solo como último recurso.
EVAL_REFERENCE_LOCAL = dt.time(21, 0)
EVAL_WINDOW_START_LOCAL = dt.time(15, 0)

def api_url(model_code):
    args = {
        'latitude': COORDS[0], 'longitude': COORDS[1],
        'timezone': 'America/Montevideo', 'daily': ','.join(FIELDS),
        'forecast_days': 3, 'models': model_code,
        # Misma consulta: agrega temperatura horaria para comparar con Rosario SC.
        'hourly': 'temperature_2m',
    }
    return 'https://api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(args)

def fetch_model(model_code):
    """Tres intentos solo para fallas de transporte temporales; nunca inventar datos."""
    request = urllib.request.Request(
        api_url(model_code),
        headers={'User-Agent': 'MiClimaRosario/6.1 (weather observer)', 'Accept': 'application/json'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
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

def parse_hourly(payload):
    """Temperatura horaria del modelo con claves UTC. Opcional: si falta, devuelve {}."""
    hourly = payload.get('hourly') or {}
    times, temps = hourly.get('time'), hourly.get('temperature_2m')
    if not isinstance(times, list) or not isinstance(temps, list) or len(times) != len(temps):
        return {}
    output = {}
    for stamp, value in zip(times, temps):
        value = safe_number(value, -70, 65)
        if value is None:
            continue
        try:
            local = dt.datetime.fromisoformat(stamp)
        except (TypeError, ValueError):
            continue
        if local.tzinfo is None:
            local = local.replace(tzinfo=ZONE)
        output[local.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ')] = value
    return output

def dump_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(path)

def issue_info(collected_at_utc):
    """Ubicación de una toma respecto de la hora fija de evaluación (mismo día local)."""
    local = dt.datetime.fromisoformat(collected_at_utc.replace('Z', '+00:00')).astimezone(ZONE)
    reference = dt.datetime.combine(local.date(), EVAL_REFERENCE_LOCAL, ZONE)
    return {
        'reference_local': EVAL_REFERENCE_LOCAL.strftime('%H:%M'),
        'window_local': EVAL_WINDOW_START_LOCAL.strftime('%H:%M') + '-24:00',
        'issued_local': local.strftime('%H:%M'),
        'in_window': local.time() >= EVAL_WINDOW_START_LOCAL,
        'minutes_from_reference': round(abs((local - reference).total_seconds()) / 60),
    }

def build_capture(fetcher=fetch_model, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    local = now.astimezone(ZONE)
    today = local.date().isoformat()
    tomorrow = (local.date() + dt.timedelta(days=1)).isoformat()
    day_after = (local.date() + dt.timedelta(days=2)).isoformat()
    dates = (today, tomorrow, day_after)
    days = {date: {} for date in dates}
    failed = {}
    hourly = {}
    for name, (_, code) in MODELS.items():
        try:
            payload = fetcher(code)
            parsed = parse_daily(payload)
            series = parse_hourly(payload)
            if series:
                hourly[name] = series
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
        'hourly_temperature_c': hourly,
        'evaluation_issue': issue_info(now.isoformat()),
        'verification': {'status':'pending', 'note':'Sin mediciones independientes verificadas; no hay ranking de precisión.'},
        'sources_note': 'Modelo meteorológico de Open-Meteo. No es medición de una estación ni porcentaje de probabilidad.'
    }

def fill_archive(archived, record):
    """Completa modelos que faltaron en la primera toma del día con una toma posterior
    del MISMO día local (sigue siendo pronóstico emitido antes del día siguiente).
    Nunca reemplaza valores ya archivados. Devuelve None si no hay cambios."""
    if archived.get('collection_local_date') != record['collection_local_date']:
        return None
    target = archived.get('target_tomorrow')
    have = archived.get('days', {}).get(target, {})
    missing = [m for m in record['days'].get(target, {}) if m not in have]
    if not missing:
        return None
    for date, models in record['days'].items():
        for model in missing:
            if model in models:
                archived.setdefault('days', {}).setdefault(date, {})[model] = models[model]
    for model in missing:
        if model in record.get('hourly_temperature_c', {}):
            archived.setdefault('hourly_temperature_c', {})[model] = record['hourly_temperature_c'][model]
        archived.get('errors', {}).pop(model, None)
        archived.get('sources', {}).get(model, {})['available'] = True
    previous = record.get('late_fills', {})
    archived.setdefault('late_fills', {}).update(
        {model: previous.get(model, record['collected_at_utc']) for model in missing})
    return archived

def prefer_capture(new, old):
    """True si la toma nueva está más cerca de la hora fija que la archivada."""
    a, b = issue_info(new['collected_at_utc']), issue_info(old['collected_at_utc'])
    if not a['in_window']:
        return False
    return not b['in_window'] or a['minutes_from_reference'] < b['minutes_from_reference']

def update_archive(archived, record):
    """Devuelve el archivo diario actualizado, o None si no cambia.
    - Toma más cercana a las 21:00 (dentro de la ventana): reemplaza a la archivada y
      conserva de ella solo los modelos que la nueva no trae (anotados en late_fills).
    - En otro caso: solo completa modelos faltantes; nunca reemplaza valores."""
    if archived.get('collection_local_date') != record['collection_local_date']:
        return None
    if prefer_capture(record, archived):
        chosen = json.loads(json.dumps(record))
        fill_archive(chosen, archived)
        chosen['replaced_capture_utc'] = archived.get('collected_at_utc')
        return chosen
    return fill_archive(archived, record)

def run():
    record = build_capture()
    DATA.mkdir(parents=True, exist_ok=True)
    archive = DATA / 'forecast_archive' / f"{record['collection_local_date']}.json"
    if not archive.exists():
        dump_json(archive, record)
    else:
        updated = update_archive(json.loads(archive.read_text(encoding='utf-8')), record)
        if updated is not None:
            dump_json(archive, updated)
    dump_json(DATA / 'latest.json', record)
    files = sorted(p.stem for p in (DATA / 'forecast_archive').glob('????-??-??.json'))
    dump_json(DATA / 'archive_index.json', {'schema':1, 'collection_days':len(files), 'dates':files})
    print(f"Recopilado {record['collection_local_date']}: {len(record['days'][record['target_tomorrow']])}/{len(MODELS)} modelos; archivo {archive.name}; fallos {record['errors']}")

if __name__ == '__main__':
    run()
