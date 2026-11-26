#!/usr/bin/env python3
"""Compara pronósticos archivados con la estación propia Rosario SC (IROSAR145).

Sin red y sin claves. Lee data/rosariosc_history/*.csv y data/forecast_archive/*.json
y escribe data/skill_rosariosc.json.

Criterios:
- Solo pronósticos emitidos el día anterior (target_tomorrow), igual que observe.py.
- Temperatura horaria: lectura de Rosario SC más cercana a la hora en punto (±10 min).
- Máxima/mínima: muestreadas a la hora en punto (comparables con el máximo horario
  de los modelos) y solo en días con cobertura casi completa.
- Un modelo se declara "más preciso" solo con >= 30 días comunes y un intervalo de
  confianza del 95 % (bootstrap por días) que excluya el empate frente a cada rival.
"""
import csv
import datetime as dt
import json
import pathlib
import random
import statistics
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ZONE = ZoneInfo("America/Montevideo")
UTC = dt.timezone.utc
MODELS = ("ecmwf", "gfs", "icon", "aifs")
MAIN = ("ecmwf", "gfs", "icon")
MATCH_MINUTES = 10
MIN_DAY_READINGS = 120     # de ~144 lecturas cada 10 min
MAX_GAP_MINUTES = 40
MIN_DAYS_FOR_RANKING = 30
BUCKETS = (("madrugada", 0, 6), ("mañana", 6, 12), ("tarde", 12, 18), ("noche", 18, 24))


def parse_time(text):
    value = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("Hora sin zona")
    return value.astimezone(UTC)


def load_history(folder):
    readings = {}
    for path in sorted(pathlib.Path(folder).glob("????-??.csv")):
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                try:
                    at = parse_time(row["observed_at_utc"])
                    temp = float(row["temperature_c"])
                except (KeyError, TypeError, ValueError):
                    continue
                if -40 <= temp <= 55:
                    readings[at] = temp
    return sorted(readings.items())


def nearest(readings, when, minutes=MATCH_MINUTES):
    """Búsqueda binaria de la lectura más cercana dentro de la tolerancia."""
    lo, hi = 0, len(readings)
    while lo < hi:
        mid = (lo + hi) // 2
        if readings[mid][0] < when:
            lo = mid + 1
        else:
            hi = mid
    best = None
    for i in (lo - 1, lo):
        if 0 <= i < len(readings):
            gap = abs((readings[i][0] - when).total_seconds()) / 60
            if gap <= minutes and (best is None or gap < best[0]):
                best = (gap, readings[i][1])
    return None if best is None else best[1]


def day_extremes(readings, date):
    """Máx./mín. del día civil local; None si la cobertura no es suficiente."""
    start = dt.datetime.combine(date, dt.time(), ZONE).astimezone(UTC)
    end = start + dt.timedelta(days=1)
    inside = [(t, v) for t, v in readings if start <= t < end]
    if len(inside) < MIN_DAY_READINGS:
        return None
    marks = [start] + [t for t, _ in inside] + [end]
    if max((b - a).total_seconds() / 60 for a, b in zip(marks, marks[1:])) > MAX_GAP_MINUTES:
        return None
    hourly = [nearest(readings, start + dt.timedelta(hours=h)) for h in range(24)]
    hourly = [v for v in hourly if v is not None]
    if len(hourly) < 23:
        return None
    values = [v for _, v in inside]
    return {"readings": len(inside), "tmax_hourly": max(hourly), "tmin_hourly": min(hourly),
            "tmax_10min": max(values), "tmin_10min": min(values)}


def summary(errors):
    if not errors:
        return {"n": 0, "bias_c": None, "mae_c": None, "rmse_c": None}
    return {"n": len(errors),
            "bias_c": round(statistics.fmean(errors), 2) + 0.0,
            "mae_c": round(statistics.fmean(abs(e) for e in errors), 2),
            "rmse_c": round(statistics.fmean(e * e for e in errors) ** 0.5, 2)}


def bootstrap_difference(a, b, draws=2000, seed=1):
    """Diferencia media de error absoluto diario (a - b) con IC 95 % por remuestreo de días."""
    diffs = [x - y for x, y in zip(a, b)]
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(diffs, k=len(diffs))) for _ in range(draws))
    return (round(statistics.fmean(diffs), 3),
            round(means[int(0.025 * draws)], 3), round(means[int(0.975 * draws) - 1], 3))


def compare(daily_abs, label):
    """daily_abs: modelo -> {día: error absoluto}. Solo días comunes a los modelos principales."""
    models = [m for m in MAIN if daily_abs.get(m)]
    if len(models) < 2:
        return {"metric": label, "common_days": 0, "best": None, "ranking_supported": False}
    days = sorted(set.intersection(*(set(daily_abs[m]) for m in models)))
    if len(days) < 3:
        return {"metric": label, "common_days": len(days), "best": None, "ranking_supported": False}
    mae = {m: statistics.fmean(daily_abs[m][d] for d in days) for m in models}
    best = min(models, key=mae.get)
    rivals, supported = [], len(days) >= MIN_DAYS_FOR_RANKING
    for other in models:
        if other == best:
            continue
        mean, low, high = bootstrap_difference([daily_abs[best][d] for d in days],
                                               [daily_abs[other][d] for d in days])
        rivals.append({"rival": other, "mean_diff_c": mean, "ci95_c": [low, high]})
        supported = supported and high < 0
    return {"metric": label, "common_days": len(days), "best": best,
            "mae_c": {m: round(v, 2) for m, v in mae.items()},
            "versus": rivals, "ranking_supported": supported}


def model_issue_local(snap, model):
    """Hora local de emisión de UN modelo. Un modelo completado desde otra toma del
    mismo día (late_fills) conserva la hora de esa toma, no la general del archivo."""
    stamp = (snap.get("late_fills") or {}).get(model) or snap.get("collected_at_utc")
    try:
        return parse_time(stamp).astimezone(ZONE).strftime("%H:%M")
    except (AttributeError, TypeError, ValueError):
        return None


def evaluate(readings, archive_dir):
    errors = {m: {"tmax": [], "tmin": [], "hourly": []} for m in MODELS}
    buckets = {m: {name: [] for name, _, _ in BUCKETS} for m in MODELS}
    daily_abs = {"tmax": {}, "tmin": {}, "hourly": {}}
    days_used, extremes_by_day, issued = [], {}, {}
    for path in sorted(pathlib.Path(archive_dir).glob("????-??-??.json")):
        try:
            snap = json.loads(path.read_text(encoding="utf-8"))
            target = dt.date.fromisoformat(snap["target_tomorrow"])
            if target != dt.date.fromisoformat(snap["collection_local_date"]) + dt.timedelta(days=1):
                continue
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
        used = set()
        extremes = day_extremes(readings, target)
        if extremes:
            extremes_by_day[target.isoformat()] = extremes
            for model, fc in snap.get("days", {}).get(target.isoformat(), {}).items():
                if model not in errors:
                    continue
                for field in ("tmax", "tmin"):
                    if isinstance(fc.get(field), (int, float)):
                        err = fc[field] - extremes[field + "_hourly"]
                        errors[model][field].append(err)
                        daily_abs[field].setdefault(model, {})[target.isoformat()] = abs(err)
                        used.add(model)
        for model, series in (snap.get("hourly_temperature_c") or {}).items():
            if model not in errors or not isinstance(series, dict):
                continue
            day_errors = []
            for stamp, value in series.items():
                try:
                    at = parse_time(stamp)
                except (TypeError, ValueError):
                    continue
                local = at.astimezone(ZONE)
                if local.date() != target or not isinstance(value, (int, float)):
                    continue
                obs = nearest(readings, at)
                if obs is None:
                    continue
                err = value - obs
                day_errors.append(err)
                errors[model]["hourly"].append(err)
                for name, lo, hi in BUCKETS:
                    if lo <= local.hour < hi:
                        buckets[model][name].append(err)
            if len(day_errors) >= 20:   # día horario casi completo
                daily_abs["hourly"].setdefault(model, {})[target.isoformat()] = \
                    statistics.fmean(abs(e) for e in day_errors)
                used.add(model)
        if used:
            days_used.append(target.isoformat())
            issued[target.isoformat()] = {m: model_issue_local(snap, m) for m in sorted(used)}
    models = {}
    for model in MODELS:
        models[model] = {field: summary(values) for field, values in errors[model].items()}
        models[model]["hourly_bias_by_period_c"] = {
            name: (round(statistics.fmean(v), 2) + 0.0 if v else None) for name, v in buckets[model].items()}
    first = readings[0][0].isoformat().replace("+00:00", "Z") if readings else None
    last = readings[-1][0].isoformat().replace("+00:00", "Z") if readings else None
    return {
        "schema": 1, "station_id": "IROSAR145", "station_name": "Rosario SC",
        "scope": "Pronóstico emitido el día anterior contra la estación propia en Rosario",
        "method": ("Horaria: lectura más cercana a la hora en punto (±10 min). Máx./mín.: "
                   "muestreo horario, días con cobertura casi completa. Error = pronóstico - medido."),
        "history_readings": len(readings), "history_from_utc": first, "history_to_utc": last,
        "minimum_days_for_ranking": MIN_DAYS_FOR_RANKING,
        "evaluated_dates": days_used, "station_extremes": extremes_by_day,
        # Hora local de emisión por día y por modelo; desde la hora fija debería quedar
        # entre 15:00 y 24:00 (referencia 21:00). Un día cuenta como "hora fija" para un
        # modelo solo si la toma de ESE modelo está en la ventana.
        "issue_local_times": issued,
        "fixed_time_dates": {m: sorted(d for d, by in issued.items()
                                       if by.get(m) and by[m] >= "15:00") for m in MODELS},
        "models": models,
        "comparisons": [compare(daily_abs[k], k) for k in ("hourly", "tmax", "tmin")],
        "note": ("Estación doméstica: su ubicación y protección solar pueden sesgar la máxima. "
                 "AIFS se informa pero no participa en la comparación principal."),
    }


def dump(path, data):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def run(data=DATA):
    readings = load_history(data / "rosariosc_history")
    if not readings:
        print("Rosario SC: sin histórico; no se modifica la evaluación")
        return None
    result = evaluate(readings, data / "forecast_archive")
    dump(data / "skill_rosariosc.json", result)
    print("Rosario SC:", len(readings), "lecturas;", len(result["evaluated_dates"]), "día(s) evaluados")
    return result


if __name__ == "__main__":
    run()
