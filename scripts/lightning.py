#!/usr/bin/env python3
"""NOAA GOES-19 GLM: resumen observacional de destellos próximos a Rosario.

Un barrido GLM detecta actividad eléctrica total (también entre nubes).
NO equivale a un aviso oficial, pronóstico de tormenta ni medición de lluvia.
Solo permite "sin detecciones" si las escenas consultadas están completas y recientes.
"""
import concurrent.futures
import datetime as dt
import json
import math
import pathlib
import re
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"data"/"lightning.json"
BASE="https://noaa-goes19.s3.amazonaws.com/"
CENTER=(-34.312,-57.351)
WINDOW_MINUTES=10
MAX_SCENE_BYTES=3_500_000
MIN_SCENES=24
MAX_AGE_MINUTES=35
NAME=re.compile(r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})\d_")
UTC=dt.timezone.utc

def iso(x):
    return x.astimezone(UTC).isoformat().replace("+00:00","Z")

def scene_time(key):
    match=NAME.search(key)
    if not match:raise ValueError("Nombre GLM sin tiempo")
    y,doy,hh,mm,ss=match.groups()
    return dt.datetime.strptime(y+doy+hh+mm+ss,"%Y%j%H%M%S").replace(tzinfo=UTC)

def distance_km(lat,lon):
    y,x=CENTER
    a=math.sin(math.radians(lat-y)/2)**2+math.cos(math.radians(y))*math.cos(math.radians(lat))*math.sin(math.radians(lon-x)/2)**2
    return 12742*math.asin(math.sqrt(max(0,min(1,a))))

def list_hour(when,opener=urllib.request.urlopen):
    prefix=f"GLM-L2-LCFA/{when.year}/{when.timetuple().tm_yday:03}/{when.hour:02}/"
    url=BASE+"?"+urllib.parse.urlencode({"list-type":"2","prefix":prefix,"max-keys":1000})
    with opener(url,timeout=30) as response:
        data=response.read(900000)
    root=ET.fromstring(data)
    if root.findtext(".//{*}IsTruncated","false").lower()=="true":
        raise ValueError("Listado incompleto de NOAA")
    return [el.text for el in root.findall(".//{*}Contents/{*}Key") if el.text and el.text.endswith(".nc")]

def choose_recent(keys,now):
    timed=[]
    for key in set(keys):
        try: t=scene_time(key)
        except ValueError:continue
        if t<=now+dt.timedelta(minutes=1):timed.append((t,key))
    if not timed:return [],None
    timed.sort()
    last=timed[-1][0]
    start=last-dt.timedelta(minutes=WINDOW_MINUTES)
    selected=[key for t,key in timed if start<=t<=last]
    return selected,last

def read_flashes(key,opener=urllib.request.urlopen):
    import netCDF4
    with opener(BASE+urllib.parse.quote(key,safe="/"),timeout=35) as res:
        raw=res.read(MAX_SCENE_BYTES+1)
    if len(raw)>MAX_SCENE_BYTES:raise ValueError("Escena GLM supera límite")
    with tempfile.TemporaryDirectory() as directory:
        file=pathlib.Path(directory)/"scene.nc"
        file.write_bytes(raw)
        with netCDF4.Dataset(file,"r") as data:
            lat=data.variables["flash_lat"][:]
            lon=data.variables["flash_lon"][:]
            quality=data.variables["flash_quality_flag"][:]
            if len(lat)!=len(lon) or len(lat)!=len(quality):
                raise ValueError("Arreglos GLM inconsistentes")
            values=[]
            for a,b,q in zip(lat,lon,quality):
                if int(q)!=0:continue
                a=float(a);b=float(b)
                if -90<=a<=90 and -180<=b<=180:
                    distance=distance_km(a,b)
                    if distance<=150: values.append(distance)
            return values

def build_summary(keys,now,reader=read_flashes):
    selected,last=choose_recent(keys,now)
    base={"schema":1,"source":"NOAA GOES-19 GLM-L2-LCFA","location":"Rosario, Colonia, Uruguay",
          "radius_km":[50,150],"window_minutes":WINDOW_MINUTES,
          "generated_at_utc":iso(now),"last_scene_utc":iso(last) if last else None,
          "expected_scenes":30,"available_scenes":len(selected),"readable_scenes":0,
          "flashes_50km":None,"flashes_150km":None,"closest_flash_km":None,
          "status":"unavailable",
          "notice":"GLM detecta rayos entre nubes y hacia tierra. No es aviso de INUMET."}
    if not selected:return base
    values=[]
    # Small concurrency limit: avoid overloading the official public dataset.
    def load(key):
        try:return reader(key),True
        except (OSError,ValueError,RuntimeError,KeyError,IndexError,TypeError) as exc:
            print("GLM scene failure:",type(exc).__name__,str(exc)[:130],flush=True)
            return [],False
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for found,ok in pool.map(load,selected):
            if ok:
                base["readable_scenes"]+=1
                values.extend(found)
    age=(now-last).total_seconds()/60
    enough=base["readable_scenes"]>=MIN_SCENES and base["readable_scenes"]>=len(selected)*0.8
    fresh=-2<=age<=MAX_AGE_MINUTES
    base["status"]="ok" if enough and fresh else ("stale" if not fresh else "partial")
    if base["readable_scenes"]:
        base["flashes_150km"]=len(values)
        base["flashes_50km"]=sum(v<=50 for v in values)
        base["closest_flash_km"]=round(min(values),1) if values else None
    return base

def collect(now=None):
    now=now or dt.datetime.now(UTC)
    keys=[]
    try:
        for h in range(4):
            keys+=list_hour(now-dt.timedelta(hours=h))
        result=build_summary(keys,now)
    except Exception as exc:
        print("GLM unavailable:",type(exc).__name__,str(exc)[:180],flush=True)
        result=build_summary([],now)
        result["status"]="unavailable"
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    tmp=OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    tmp.replace(OUTPUT)
    print("GLM status",result["status"],"files",result["readable_scenes"],"flashes 150km",result["flashes_150km"],flush=True)
    return result

if __name__=="__main__":
    collect()
