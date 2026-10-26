#!/usr/bin/env python3
"""Observaciones públicas INIA La Estanzuela, independientes de INUMET.

Las máximas, mínimas y precipitaciones de INIA corresponden a intervalos
de 09:00 a 09:00 hora uruguaya. NO se comparan con pronósticos de 00:00 a 00:00.
Nunca utiliza Spymovil ni datos privados.
"""
import csv
import datetime as dt
import io
import json
import pathlib
import urllib.request
import urllib.parse
from zoneinfo import ZoneInfo

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"data"/"inia_la_estanzuela.json"
URL=("https://catalogodatos.gub.uy/dataset/f00a78b3-5617-41cc-959d-bd591a7cc4ec/"
     "resource/d0175da0-9b64-43c1-82ab-e584ec561ec0/download/ppt_tmax_tmin_le_2026.csv")
MAX_BYTES=1_500_000
LOCAL=ZoneInfo("America/Montevideo")
REQUIRED={"fecha","temperaturaMaximaCorregida","temperaturaMinimaCorregida","pluviometro"}

def parse_date(value):
    value=value.strip()
    if "T" in value:
        value=value.split("T",1)[0]
    if " " in value:
        value=value.split(" ",1)[0]
    if "/" in value:
        return dt.datetime.strptime(value,"%d/%m/%Y").date()
    if len(value)==10 and value[2]=="-" and value[5]=="-":
        return dt.datetime.strptime(value,"%d-%m-%Y").date()
    return dt.date.fromisoformat(value)

def number(value,low,high):
    if value is None:
        return None
    raw=value.strip().replace(",",".")
    if not raw or raw.lower() in ("na","n/a","null","nan","s/d","sd","sin dato","-","--"):
        return None
    try:
        parsed=float(raw)
    except (ValueError, OverflowError):
        return None
    from math import isfinite
    if not isfinite(parsed) or not low<=parsed<=high:
        return None
    return round(parsed,2)

def parse_csv(content,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    today=now.astimezone(LOCAL).date()
    sample=content.lstrip("\ufeff")[:4096]
    try:
        delim=csv.Sniffer().sniff(sample,delimiters=",;\t").delimiter
    except csv.Error:
        delim="," if "," in sample.splitlines()[0] else ";"
    reader=csv.DictReader(io.StringIO(content.lstrip("\ufeff")),delimiter=delim)
    headers=set(reader.fieldnames or ())
    if not REQUIRED.issubset(headers):
        raise ValueError("INIA: columnas no verificadas: "+repr(sorted(headers)))
    observations={}
    invalid=set()
    for item in reader:
        try:
            day=parse_date(item["fecha"])
            if day.year!=2026 or day>today:
                continue
        except (TypeError, ValueError):
            continue
        date=day.isoformat()
        data={
            "tmax_c":number(item["temperaturaMaximaCorregida"],-60,65),
            "tmin_c":number(item["temperaturaMinimaCorregida"],-60,65),
            "rain_mm":number(item["pluviometro"],0,500),
        }
        if all(v is None for v in data.values()):
            continue
        if data["tmax_c"] is not None and data["tmin_c"] is not None and data["tmax_c"]<data["tmin_c"]:
            continue
        if date in invalid:
            continue
        if date in observations and observations[date]!=data:
            del observations[date]
            invalid.add(date)
        else:
            observations[date]=data
    if len(observations)<5:
        raise ValueError("INIA: menos de cinco fechas válidas en 2026")
    dates=sorted(observations)
    return {
        "schema":1,
        "source":"INIA GRAS - La Estanzuela",
        "location":"La Estanzuela, Colonia, Uruguay",
        "coordinates":{"latitude":-34.3372222,"longitude":-57.6922222},
        "source_url":URL,
        "observed_interval":"09:00-09:00 America/Montevideo",
        "date_interpretation":"Fecha oficial del registro INIA; no es dia civil 00:00-00:00",
        "calendar_day_comparable":False,
        "scores_enabled":False,
        "fetched_at_utc":now.astimezone(dt.timezone.utc).isoformat().replace("+00:00","Z"),
        "latest_date":dates[-1],
        "count_2026":len(dates),
        "days":{date:observations[date] for date in dates[-60:]},
    }

def run(fetcher=None, now=None, output=OUTPUT):
    now=now or dt.datetime.now(dt.timezone.utc)
    if fetcher is None:
        def fetcher():
            # El CSV oficial a veces demora; usar alternativa oficial CKAN
            # únicamente si contiene campos y registros válidos.
            req=urllib.request.Request(URL,headers={"User-Agent":"MiClimaRosario/INIA-ReadOnly"})
            try:
                with urllib.request.urlopen(req,timeout=22) as response:
                    if int(response.headers.get("Content-Length") or 0)>MAX_BYTES:
                        raise ValueError("INIA archivo demasiado grande")
                    raw=response.read(MAX_BYTES+1)
                if len(raw)>MAX_BYTES:
                    raise ValueError("INIA archivo demasiado grande")
                return raw.decode("utf-8-sig")
            except (OSError,TimeoutError,ValueError,UnicodeError) as exc:
                print("INIA: CSV no disponible; consultando alternativa oficial CKAN:",type(exc).__name__)
            query=urllib.parse.urlencode({
                "resource_id":"d0175da0-9b64-43c1-82ab-e584ec561ec0","limit":1000
            })
            url="https://catalogodatos.gub.uy/api/3/action/datastore_search?"+query
            with urllib.request.urlopen(urllib.request.Request(
                url,headers={"User-Agent":"MiClimaRosario/INIA-ReadOnly"}),timeout=22) as response:
                raw=response.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES:
                raise ValueError("INIA CKAN supera tamaño permitido")
            payload=json.loads(raw)
            if payload.get("success") is not True:
                raise ValueError("INIA CKAN sin resultados")
            result=payload.get("result",{})
            records=result.get("records")
            if not isinstance(records,list) or len(records)>1000 or (
                isinstance(result.get("total"),int) and result["total"]>len(records)
            ):
                raise ValueError("INIA CKAN: listado incompleto")
            if not records:
                raise ValueError("INIA CKAN sin registros")
            columns=["fecha","temperaturaMaximaCorregida","temperaturaMinimaCorregida","pluviometro"]
            if not all(all(col in row for col in columns) for row in records):
                raise ValueError("INIA CKAN: columnas distintas")
            buff=io.StringIO()
            writer=csv.DictWriter(buff,fieldnames=columns)
            writer.writeheader()
            for record in records:
                writer.writerow({col:record[col] if record[col] is not None else "" for col in columns})
            return buff.getvalue()
    try:
        parsed=parse_csv(fetcher(),now)
        output.parent.mkdir(parents=True,exist_ok=True)
        temp=output.with_name(output.name+".tmp")
        temp.write_text(json.dumps(parsed,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        temp.replace(output)
        print("INIA La Estanzuela: observaciones públicas verificadas, último registro",parsed["latest_date"],
              "fechas 2026",parsed["count_2026"],"comparación por días civiles NO activada")
        return parsed
    except (ValueError,UnicodeError,OSError,csv.Error,KeyError,TypeError) as exc:
        print("INIA La Estanzuela: datos no incorporados:",type(exc).__name__,str(exc)[:190])
        return None

if __name__=="__main__":
    run()
