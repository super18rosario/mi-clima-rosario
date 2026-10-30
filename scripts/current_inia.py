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
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"data"/"current_station.json"
URL="https://www.inumet.gub.uy/tiempo/estaciones-meteorologicas-automaticas"
DIRECT_URL="https://gras.inia.uy/agroclima/INIA_WN/WebData.xml"
DIRECT_PAGE="https://gras.inia.uy/agroclima/INIA_WN/inia_le.htm"
STATIONS=(
    (584,"EMA_INIA_LaEstanzuela","INIA La Estanzuela (Automática)","INUMET / INIA La Estanzuela"),
    (594,"U560","Colonia G3","INUMET / Colonia G3"),
)
TEMPERATURE_ID=47
MAX_HTML_BYTES=1_200_000
MAX_AGE_MIN=120
LOCAL=ZoneInfo("America/Montevideo")
PATTERN=re.compile(r"\bvar\s+estadoActual\s*=\s*(\{.*?\})\s*;\s*var\s+estaciones\s*=",re.S)

def parse_direct_xml(raw, now=None):
    """Medición instantánea INIA_LE; lectura de campos y horario publicados."""
    now=now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Hora sin zona")
    try:
        root=ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("XML INIA inválido") from exc
    if root.tag!="webdata":
        raise ValueError("Raíz INIA desconocida")
    station=root.find("./stations/station[@name='INIA_LE']")
    if station is None:raise ValueError("Sin estación INIA_LE")
    values={}
    for field in station.findall("./fields/field"):
        key=field.findtext("name")
        if key in ("TimeStampString","Air Temperature"):
            if key in values:raise ValueError("Campo INIA duplicado")
            values[key]=(field.findtext("value"),field.findtext("units"))
    if set(values)!={"TimeStampString","Air Temperature"}:
        raise ValueError("Campos INIA incompletos")
    time_text,time_unit=values["TimeStampString"]
    temp_text,temp_unit=values["Air Temperature"]
    if time_unit not in ("",None) or temp_unit!="°C":
        raise ValueError("Unidades INIA inesperadas")
    if not isinstance(time_text,str) or not re.fullmatch(
        r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}",time_text
    ):
        raise ValueError("Hora INIA inválida")
    at=dt.datetime.strptime(time_text,"%d/%m/%Y %H:%M:%S").replace(tzinfo=LOCAL)
    age=(now-at).total_seconds()/60
    if not -5<=age<=MAX_AGE_MIN:
        raise ValueError("Medición INIA antigua o futura")
    try:
        temperature=float(temp_text)
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError("Temperatura INIA no numérica") from exc
    if not math.isfinite(temperature) or not -40<=temperature<=55:
        raise ValueError("Temperatura INIA fuera de rango")
    return {
        "schema":1, "source":"INIA GRAS / La Estanzuela",
        "station_id":584, "station_name":"INIA La Estanzuela",
        "location":"La Estanzuela, Colonia, Uruguay", "source_url":DIRECT_PAGE,
        "observed_at_utc":at.astimezone(dt.timezone.utc).isoformat().replace("+00:00","Z"),
        "collected_at_utc":now.astimezone(dt.timezone.utc).isoformat().replace("+00:00","Z"),
        "temperature_c":round(temperature,1), "observation":True
    }

def fetch_direct_xml():
    request=urllib.request.Request(
        DIRECT_URL,headers={"User-Agent":"MiClimaRosario/1.0 (public INIA data)"})
    with urllib.request.urlopen(request,timeout=18) as response:
        if int(response.headers.get("Content-Length") or 0)>200_000:
            raise ValueError("XML INIA demasiado grande")
        raw=response.read(200_001)
    if len(raw)>200_000:raise ValueError("XML INIA demasiado grande")
    return raw

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

def run(get_html=fetch, now=None, output=OUTPUT, get_direct_xml=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    # Mantener las pruebas existentes desconectadas de internet.
    if get_direct_xml is None and get_html is fetch:
        get_direct_xml=fetch_direct_xml
    record=None
    if get_direct_xml is not None:
        try:
            record=parse_direct_xml(get_direct_xml(),now)
        except (OSError,ValueError,TypeError,KeyError,OverflowError) as exc:
            print("INIA directa: sin lectura válida:",type(exc).__name__,str(exc)[:100])
    if record is None:
        try:
            record=parse(get_html(),now)
        except (OSError,ValueError,TypeError,KeyError,OverflowError,json.JSONDecodeError) as exc:
            print("INUMET respaldo: sin lectura válida:",type(exc).__name__,str(exc)[:100])
            return None
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_name(output.name+".tmp")
    temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temporary.replace(output)
    print("TEMPERATURA:",record["source"],record["temperature_c"],"°C",record["observed_at_utc"])
    return record

if __name__=="__main__":
    run()
