#!/usr/bin/env python3
"""Solo diagnóstico XML público de INIA La Estanzuela, consulta GET."""
from urllib.request import Request,urlopen
import xml.etree.ElementTree as ET
URL="https://gras.inia.uy/agroclima/INIA_WN/WebData.xml"
with urlopen(Request(URL,headers={"User-Agent":"MiClimaRosario/1.0 (public INIA weather data)"}),timeout=24) as response:
 raw=response.read(200_001)
if len(raw)>200_000:raise ValueError("XML excesivo")
root=ET.fromstring(raw)
station=next((x for x in root.findall(".//station") if x.attrib.get("name")=="INIA_LE"),None)
if station is None:raise ValueError("Estacion INIA_LE ausente")
print("ELEMENTOS RAIZ",[x.tag for x in root])
print("ELEMENTOS ESTACION",[(c.tag,c.attrib,len(c)) for c in station])
print("SUBELEMENTOS",[(x.tag,x.attrib,len(x)) for x in station if x.tag!="reports"])
for branch in station:
 if branch.tag=="reports":continue
 for child in list(branch)[:24]:
  print("ELEMENTO",child.tag,"attrs",child.attrib,"text",repr((child.text or "").strip()[:180]),
   "hijos",[(x.tag,x.attrib,repr((x.text or "").strip()[:95])) for x in list(child)[:5]])
print("ETIQUETAS",sorted({x.tag for x in station.iter()}))
