#!/usr/bin/env python3
"""Audita solamente esquema de observaciones públicas INUMET La Estanzuela."""
import current_inia
import json
from collections import Counter
m=current_inia.PATTERN.search(current_inia.fetch())
if not m: raise ValueError("No hay objeto estadoActual")
d=json.loads(m.group(1))
stations=d.get("estaciones",[])
vars=d.get("variables",[])
times=d.get("fechas",[])
rows=d.get("observaciones",[])
target=[(i,s) for i,s in enumerate(stations) if isinstance(s,dict) and ("Estanzuela" in str(s) or s.get("id")==584)]
temp=[(i,v) for i,v in enumerate(vars) if isinstance(v,dict) and ("temp" in str(v).lower() or v.get("idInt")==47)]
print("ESTACIONES TOTAL:",len(stations),"TEMPERATURAS:",temp,"FECHAS:",times[:12])
print("ESTANZUELA:",target)
for i,v in temp:
 if i>=len(rows): continue
 r=rows[i]
 print("VARIABLE",i,"indices tiempos:",r.get("iFechas"),"series totales:",len(r.get("datos",[])))
 for si,s in target:
  data=r.get("datos",[])
  if si<len(data):
   print("LECTURA",si,repr(data[si])[:600])
 print("DISTRIBUCION NULOS:",dict(Counter(str(row) for row in r.get("datos",[])[:12])))
