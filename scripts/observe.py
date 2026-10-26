#!/usr/bin/env python3
"""Observaciones horarias INUMET y evaluación provisional contra Colonia G3.
La estación NO está en Rosario. Horarios INUMET en UTC. Nunca completar huecos con 0.
"""
import csv
import datetime as dt
import io
import json
import pathlib
import time
import urllib.error
import urllib.request
from collections import defaultdict
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ZONE = ZoneInfo("America/Montevideo")
UTC = dt.timezone.utc
STATION = "Colonia G3"
TEMP_URL = ("https://catalogodatos.gub.uy/dataset/accd0e24-76be-4101-904b-81bb7d41ee88/"
            "resource/f800fc53-556b-4d1c-8bd6-28b41f9cf146/download/inumet_temperatura_del_aire.csv")
RAIN_URL = ("https://catalogodatos.gub.uy/dataset/fd896b11-4c04-4807-bae4-5373d65beea2/"
            "resource/cc785e9e-d9c8-4706-b013-9a6a5b0f7d01/download/inumet_precipitacion_acumulada_horaria.csv")
FIELDS = {"temperature": "temp_aire", "rain": "precip_horario"}
MAX_BYTES = 30_000_000
MAX_DAYS = 95

def utc_date(s):
    s = s.strip().replace("Z", "+00:00")
    result = dt.datetime.fromisoformat(s)
    if result.tzinfo is None:
        # INUMET: metadata specifies UTC, including naive timestamps.
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)

def parse_csv(content, kind, now=None):
    """UTC measurements -> local civil day; hourly rain is trailing interval."""
    now = now or dt.datetime.now(UTC)
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")), delimiter=";")
    required = {"fecha", "estacion_id", FIELDS[kind]}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError(f"Unexpected INUMET {kind} columns: {reader.fieldnames}")
    cutoff = now - dt.timedelta(days=MAX_DAYS)
    obs = defaultdict(dict)
    conflict = set()
    for line in reader:
        if line.get("estacion_id", "").strip() != STATION:
            continue
        try:
            timestamp = utc_date(line["fecha"])
            if timestamp < cutoff or timestamp > now + dt.timedelta(hours=3):
                continue
            reading = float(line[FIELDS[kind]].strip().replace(",", "."))
            if kind == "rain":
                if not (0 <= reading <= 300):
                    continue
                local = (timestamp - dt.timedelta(seconds=1)).astimezone(ZONE)
            else:
                if not (-60 <= reading <= 60):
                    continue
                local = timestamp.astimezone(ZONE)
            key = timestamp.isoformat()
            date = local.date().isoformat()
            if (date, key) in conflict:
                continue
            if key in obs[date] and obs[date][key] != reading:
                del obs[date][key]
                conflict.add((date, key))
            else:
                obs[date][key] = reading
        except (ValueError, TypeError, KeyError, OverflowError):
            continue
    return obs

def fetch_csv(url):
    req = urllib.request.Request(url, headers={"User-Agent":"MiClimaRosario/6.2 (public INUMET data)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=85) as response:
                size = int(response.headers.get("Content-Length") or 0)
                if size > MAX_BYTES:
                    raise ValueError(f"INUMET file too large: {size}")
                raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("INUMET file exceeds safe size")
            return raw.decode("utf-8-sig")
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            if isinstance(error, urllib.error.HTTPError) and error.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == 2:
                raise
            print(f"INUMET: retry {attempt+1}/2 after {type(error).__name__}", flush=True)
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("No INUMET response")

def build_observations(temp, rain, now):
    today = now.astimezone(ZONE).date()
    records = {}
    dates = sorted(set(temp) | set(rain))
    for date in dates:
        if dt.date.fromisoformat(date) >= today:
            continue
        ts, rs = list(temp.get(date, {}).values()), list(rain.get(date, {}).values())
        # Require essentially full days for extrema; complete 24 hours for rain.
        t_ok = len(ts) >= 23
        r_ok = len(rs) == 24
        records[date] = {
            "temperature_hours": len(ts), "rain_hours": len(rs),
            "tmax_hourly": round(max(ts),1) if t_ok else None,
            "tmin_hourly": round(min(ts),1) if t_ok else None,
            "rain_mm": round(sum(rs),2) if r_ok else None,
            "temperature_usable": t_ok, "rain_usable": r_ok
        }
    return {
        "schema":1, "source":"INUMET", "station":STATION,
        "reference_scope":"Estación cercana; NO es observación en Rosario",
        "station_observations":"temperatura muestreada por hora; lluvia acumulada por hora",
        "time_convention":"UTC timestamps, aggregated to midnight-midnight America/Montevideo; rain timestamp closes previous hour",
        "fetched_at_utc":now.isoformat().replace("+00:00","Z"),
        "source_urls":{"temperature":TEMP_URL,"rain":RAIN_URL},
        "days":dict(sorted(records.items())[-MAX_DAYS:])
    }

def evaluate(observations, archive_dir):
    accum = {name: {
        "rain":{"n":0,"correct":0,"hits":0,"false_alarms":0,"misses":0,"correct_dry":0,"observed_wet_days":0,"sum_abs_error_mm":0.0},
        "tmax":{"n":0,"sum_abs_error":0.0},
        "tmin":{"n":0,"sum_abs_error":0.0}
    } for name in ("ecmwf","gfs","icon","aifs")}
    eligible_dates = []
    for path in sorted(archive_dir.glob("????-??-??.json")):
        try:
            snapshot=json.loads(path.read_text(encoding="utf-8"))
            target=snapshot.get("target_tomorrow")
            if target != (dt.date.fromisoformat(snapshot["collection_local_date"])+dt.timedelta(days=1)).isoformat():
                continue
            observed=observations["days"].get(target)
            if not observed:
                continue
            vals=snapshot.get("days",{}).get(target,{})
            if not vals:
                continue
            any_used=False
            for model, forecast in vals.items():
                if model not in accum:
                    continue
                stats=accum[model]
                for field,obs_key in (("tmax","tmax_hourly"),("tmin","tmin_hourly")):
                    value=forecast.get(field)
                    truth=observed.get(obs_key)
                    if isinstance(value,(int,float)) and isinstance(truth,(int,float)):
                        stats[field]["n"]+=1
                        stats[field]["sum_abs_error"]+=abs(value-truth)
                        any_used=True
                rain_fc=forecast.get("rain_mm")
                rain_ob=observed.get("rain_mm")
                if isinstance(rain_fc,(int,float)) and isinstance(rain_ob,(int,float)):
                    wet_f=rain_fc>=0.2
                    wet_o=rain_ob>=0.2
                    st=stats["rain"]
                    st["n"]+=1
                    st["sum_abs_error_mm"]+=abs(rain_fc-rain_ob)
                    st["correct"]+=int(wet_f==wet_o)
                    st["observed_wet_days"]+=int(wet_o)
                    if wet_f and wet_o: st["hits"]+=1
                    elif wet_f and not wet_o: st["false_alarms"]+=1
                    elif not wet_f and wet_o: st["misses"]+=1
                    else: st["correct_dry"]+=1
                    any_used=True
            if any_used:
                eligible_dates.append(target)
        except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError):
            continue
    per_model={}
    for model,metrics in accum.items():
        rain=metrics["rain"]
        per_model[model]={
            "rain":{**{k:v for k,v in rain.items() if k!="sum_abs_error_mm"},
                    "accuracy_pct":round(100*rain["correct"]/rain["n"],1) if rain["n"] else None,
                    "mae_mm":round(rain["sum_abs_error_mm"]/rain["n"],2) if rain["n"] else None},
            "tmax":{"n":metrics["tmax"]["n"],"mae_c":round(metrics["tmax"]["sum_abs_error"]/metrics["tmax"]["n"],2) if metrics["tmax"]["n"] else None},
            "tmin":{"n":metrics["tmin"]["n"],"mae_c":round(metrics["tmin"]["sum_abs_error"]/metrics["tmin"]["n"],2) if metrics["tmin"]["n"] else None},
        }
    return {
        "schema":1, "observation_station":STATION,
        "provisional":True, "scope":"Comparación provisional con Colonia G3, no exactitud en Rosario",
        "rain_threshold_mm":0.2, "minimum_days_for_ranking":30,
        "ranking_enabled":False, "reason":"Sin muestra suficiente, y referencia fuera de Rosario",
        "eligible_dates":eligible_dates, "models":per_model
    }

def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    tmp.replace(path)

def run(fetcher=fetch_csv,now=None):
    now=now or dt.datetime.now(UTC)
    try:
        temp=parse_csv(fetcher(TEMP_URL),"temperature",now)
        rain=parse_csv(fetcher(RAIN_URL),"rain",now)
        result=build_observations(temp,rain,now)
        if not any(d["rain_usable"] or d["temperature_usable"] for d in result["days"].values()):
            raise ValueError("No complete observation days from Colonia G3")
        dump(DATA/"observations.json",result)
        dump(DATA/"skill.json",evaluate(result,DATA/"forecast_archive"))
        usable_temp=sum(x["temperature_usable"] for x in result["days"].values())
        usable_rain=sum(x["rain_usable"] for x in result["days"].values())
        print(f"INUMET {STATION}: {usable_temp} temp-days, {usable_rain} rain-days; scores provisional")
    except Exception as error:
        # This optional input MUST NEVER block existing forecast publication.
        print(f"INUMET unavailable or incomplete: {type(error).__name__}: {error}")
        if (DATA/"observations.json").exists():
            old=json.loads((DATA/"observations.json").read_text(encoding="utf-8"))
            dump(DATA/"skill.json",evaluate(old,DATA/"forecast_archive"))

if __name__=="__main__":
    run()
