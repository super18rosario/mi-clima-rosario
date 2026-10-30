#!/usr/bin/env python3
"""Fusionar datos meteorológicos públicos, conservando el registro más reciente.

Pensado para reintentos de publicación de GitHub Actions. Solo escribe los
archivos públicos data/lightning.json y data/current_station.json.
No accede a Spymovil ni a otros archivos.
"""
import datetime as dt
import json
import pathlib
import sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
ALLOWED={
 "lightning.json":("schema","source","generated_at_utc"),
 "current_station.json":("schema","source","observed_at_utc"),
}

def timestamp(value):
    if not isinstance(value,str):raise ValueError("Fecha ausente")
    date=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    if date.utcoffset() is None:raise ValueError("Fecha sin zona")
    return date.astimezone(dt.timezone.utc)

def validated(file,data):
    if not isinstance(data,dict) or data.get("schema")!=1:
        raise ValueError("Formato no válido")
    if file=="lightning.json":
        if data.get("source")!="NOAA GOES-19 GLM-L2-LCFA":
            raise ValueError("Satélite inesperado")
        # El instante de la última escena no sustituye la fecha de generación.
        return timestamp(data["generated_at_utc"])
    if file=="current_station.json":
        if data.get("observation") is not True or not isinstance(data.get("temperature_c"),(int,float)):
            raise ValueError("Estación sin observación")
        return timestamp(data["observed_at_utc"])
    raise ValueError("Archivo no permitido")

def merge(incoming_dir,output_dir):
    changes=[]
    for filename in ALLOWED:
        incoming=pathlib.Path(incoming_dir)/filename
        if not incoming.is_file():continue
        next_bytes=incoming.read_bytes()
        data=json.loads(next_bytes)
        at=validated(filename,data)
        dest=pathlib.Path(output_dir)/filename
        if dest.exists():
            old=json.loads(dest.read_text(encoding="utf-8"))
            old_time=validated(filename,old)
            if at<old_time:
                print(filename,": descartado por ser más antiguo")
                continue
            if at==old_time and filename=="current_station.json":
                # Para una medición de igual instante, no inventar un cambio.
                continue
        if not dest.exists() or dest.read_bytes()!=next_bytes:
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(next_bytes)
            changes.append(filename)
    print("Archivos actualizados:",", ".join(changes) if changes else "ninguno")
    return changes

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("Uso: sync_weather_updates.py <carpeta temporal>")
    merge(sys.argv[1],ROOT/"data")
