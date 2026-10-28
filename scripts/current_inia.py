#!/usr/bin/env python3
"""Temperatura HORARIA de INIA La Estanzuela vía página pública de INUMET.

Consulta de solo lectura. Conserva la fecha de la observación; NO utiliza
máximas/mínimas diarias ni deriva temperatura de pronósticos. Sin GDA/Spymovil.
"""
import datetime as dt
import json
import math
import pathlib
import re
import urllib.request
from zoneinfo import ZoneInfo

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"data"/"current_station.json"
URL="https://www.inumet.gub.uy/tiempo/estaciones-meteorologicas-automaticas"
STATION_ID=584
TEMPERATURE_ID=47
MAX_HTML_BYTES=1_200_000
MAX_AGE_MIN=120
LOCAL=ZoneInfo("America/Montevideo")
PATTERN=re.compile(r"\bvar\s+estadoActual\s*=\s*(\{.*?\})\s*;\s*var\s+estaciones\s*=",re.S)

def parse(html,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Hora de evaluación requiere zona")
    match=PATTERN.search(html)
    if not match:
        raise ValueError("No se encontró estructura oficial estadoActual")
    data=json.loads(match.group(1))
    stations=data.get("estaciones")
    variables=data.get("variables")
    times=data.get("fechas")
    observations=data.get("observaciones")
    if not all(isinstance(v,list) for v in (stations,variables,times,observations)):
        raise ValueError("INUMET formato incompleto")
    station_idx=next((i for i,row in enumerate(stations) if isinstance(row,dict) and
                      row.get("id")==STATION_ID and row.get("Estacion")=="EMA_INIA_LaEstanzuela"),None)
    temp_idx=next((i for i,row in enumerate(variables) if isinstance(row,dict) and
                   row.get("idInt")==TEMPERATURE_ID and row.get("variable")=="TempAire"),None)
    if station_idx is None or temp_idx is None or len(observations)<=temp_idx:
        raise ValueError("No se confirmó estación o variable")
    item=observations[temp_idx]
    if not isinstance(item,dict):
        raise ValueError("Datos de temperatura inválidos")
    values=item.get("datos")
    date_indices=item.get("iFechas")
    if not isinstance(values,list) or not isinstance(date_indices,list) or station_idx>=len(values) or not date_indices:
        raise ValueError("Observaciones sin índice")
    series=values[station_idx]
    if not isinstance(series,list) or len(series)!=len(date_indices) or len(series)!=1:
        raise ValueError("Serie horaria ambigua")
    dateidx=date_indices[0]
    if not isinstance(dateidx,int) or not 0<=dateidx<len(times):
        raise ValueError("Índice temporal inválido")
    at=dt.datetime.fromisoformat(times[dateidx].replace("Z","+00:00"))
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("INUMET no informó zona de observación")
    raw=series[0]
    if isinstance(raw,bool) or not isinstance(raw,(int,float,str)):
        raise ValueError("Temperatura ausente o inválida")
    temp=float(raw)
    if not math.isfinite(temp) or not -40<=temp<=55:
        raise ValueError("Temperatura fuera de rango")
    age=(now-at).total_seconds()/60
    if not -5<=age<=MAX_AGE_MIN:
        raise ValueError("Observación desactualizada o futura")
    return {
        "schema":1,
        "source":"INUMET / INIA La Estanzuela",
        "station_id":STATION_ID,
        "station_name":"INIA La Estanzuela (Automática)",
        "location":"La Estanzuela, Colonia, Uruguay",
        "source_url":URL,
        "observed_at_utc":at.astimezone(dt.timezone.utc).isoformat().replace("+00:00","Z"),
        "collected_at_utc":now.astimezone(dt.timezone.utc).isoformat().replace("+00:00","Z"),
        "temperature_c":round(temp,1),
        "observation":True
    }

def fetch():
    request=urllib.request.Request(URL,headers={"User-Agent":"MiClimaRosario/1.0 (INUMET public observations)"})
    with urllib.request.urlopen(request,timeout=22) as response:
        if int(response.headers.get("Content-Length") or 0)>MAX_HTML_BYTES:
            raise ValueError("Página INUMET demasiado grande")
        raw=response.read(MAX_HTML_BYTES+1)
    if len(raw)>MAX_HTML_BYTES:
        raise ValueError("Página INUMET demasiado grande")
    return raw.decode("utf-8",errors="replace")

def run(get_html=fetch,now=None,output=OUTPUT):
    now=now or dt.datetime.now(dt.timezone.utc)
    try:
        record=parse(get_html(),now)
        output.parent.mkdir(parents=True,exist_ok=True)
        temporary=output.with_name(output.name+".tmp")
        temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        temporary.replace(output)
        print("INUMET La Estanzuela: observación horaria válida:",record["temperature_c"],"°C",
              record["observed_at_utc"])
        return record
    except (OSError,ValueError,TypeError,KeyError,OverflowError,json.JSONDecodeError) as exc:
        print("INUMET La Estanzuela: sin lectura válida:",type(exc).__name__,str(exc)[:135])
        return None

if __name__=="__main__":
    run()
