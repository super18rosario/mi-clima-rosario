#!/usr/bin/env python3
"""Verifica disponibilidad de observación Colonia G3 desde INUMET público, sin alteraciones."""
import json
from current_inia import fetch, PATTERN
def main():
    html=fetch()
    m=PATTERN.search(html)
    if not m:
        print("Sin estructura estadoActual")
        return
    obj=json.loads(m.group(1))
    stations=obj.get("estaciones",[])
    vars=obj.get("variables",[])
    obs=obj.get("observaciones",[])
    dates=obj.get("fechas",[])
    print("Tamaños de datos",len(stations),len(vars),len(obs),len(dates))
    station_idx=None
    for i,row in enumerate(stations):
        if isinstance(row,dict) and ("colonia" in str(row).lower() or "estanzuela" in str(row).lower()):
            print("Estación candidata",i,str(row)[:250])
            if "colonia" in str(row).lower() and "estanzuela" not in str(row).lower():
                station_idx=i
    print("Colonia indice",station_idx)
    for row in vars:
        if isinstance(row,dict) and ("temp" in str(row).lower()):
            print("Variable temperatura",str(row)[:180])
    if station_idx is not None:
        for row in obs:
            if not isinstance(row,dict):continue
            iFechas=row.get("iFechas",[])
            values=row.get("datos",[])
            if (isinstance(iFechas,list) and len(iFechas)==1 and
                isinstance(values,list) and len(values)>station_idx and
                isinstance(values[station_idx],list) and len(values[station_idx])==1 and
                len(dates)>iFechas[0]):
                val=values[station_idx][0]
                print("Dato Colonia índice",obs.index(row),"fecha",dates[iFechas[0]],"presente",val is not None,
                      "valor",str(val)[:24])
if __name__=="__main__":main()
