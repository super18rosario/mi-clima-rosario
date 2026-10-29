#!/usr/bin/env python3
"""Temperatura observada de INIA La Estanzuela o Colonia G3 vía INUMET.

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
STATIONS=(\n    (584,"EMA_INIA_LaEstanzuela","INIA La Estanzuela (Automática)","INUMET / INIA La Estanzuela"),\n    (594,"U560","Colonia G3","INUMET / Colonia G3"),\n)
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
    temp_idx=next((i for i,row in enumerate(variables) if isinstance(row,dict) and
                   row.get("idInt")==TEMPERATURE_ID and row.get("variable")=="TempAire"),None)
    if temp_idx is None or len(observations)<=temp_idx:
        raise ValueError("INUMET: variable temperatura no verificada")
    item=observations[temp_idx]
    if not isinstance(item,dict):raise ValueError("INUMET: serie inválida")
    values=item.get("datos")
    date_indices=item.get("iFechas")
    if not isinstance(values,list) or not isinstance(date_indices,list) or len(date_indices)!=1:
        raise ValueError("INUMET: horario de observación ambiguo")
    dateidx=date_indices[0]
    if not isinstance(dateidx,int) or isinstance(dateidx,bool) or not 0<=dateidx<len(times):
        raise ValueError("INUMET: fecha inválida")
    at=dt.datetime.fromisoformat(times[dateidx].replace("Z","+00:00"))
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("INUMET: fecha sin zona horaria")
    age=(now-at).total_seconds()/60
    if not -5<=age<=MAX_AGE_MIN:
        raise ValueError("INUMET: observación desactualizada o futura")
    # Primero La Estanzuela; si su temperatura es nula, probar Colonia G3.
    # Las estaciones son distintas: nunca se rotula Colonia como La Estanzuela.
    for station_id,station_code,station_name,source in STATIONS:
        station_idx=next((i for i,row in enumerate(stations) if isinstance(row,dict) and
                          row.get("id")==station_id and row.get("Estacion")==station_code and
                          row.get("NombreEstacion")==station_name),None)
        if station_idx is None or len(values)<=station_idx:continue
        series=values[station_idx]
        if not isinstance(series,list) or len(series)!=1:continue
        raw=series[0]
        if isinstance(raw,bool) or not isinstance(raw,(int,float,str)):continue
        try:
            temperature=float(raw)
        except (TypeError,ValueError,OverflowError):
            continue
        if not math.isfinite(temperature) or not -40<=temperature<=55:continue
        return {
            "schema":1,
            "source":source,
            "station_id":station_id,
            "station_name":station_name,
            "location":("La Estanzuela, Colonia" if station_id==584 else "Colonia")+" , Uruguay",
            "source_url":URL,
            "observed_at_utc":at.astimezone(dt.timezone.utc).isoformat().replace("+00:00","Z"),
            "collected_at_utc":now.astimezone(dt.timezone.utc).isoformat().replace("+00:00","Z"),
            "temperature_c":round(temperature,1),
            "observation":True
        }
    raise ValueError("INUMET: ambas estaciones sin temperatura reciente válida")

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
        print("INUMET:",record["station_name"],"observación horaria válida:",record["temperature_c"],"°C",
              record["observed_at_utc"])
        return record
    except (OSError,ValueError,TypeError,KeyError,OverflowError,json.JSONDecodeError) as exc:
        print("INUMET estación de respaldo: sin lectura válida:",type(exc).__name__,str(exc)[:135])
        return None

if __name__=="__main__":
    run()
