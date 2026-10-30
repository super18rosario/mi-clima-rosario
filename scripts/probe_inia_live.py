#!/usr/bin/env python3
"""Inspección de estructura XML meteorológica publicada por INIA; GET solamente."""
from urllib.request import Request,urlopen
import xml.etree.ElementTree as ET
URL="https://gras.inia.uy/agroclima/INIA_WN/WebData.xml"
with urlopen(Request(URL,headers={"User-Agent":"MiClimaRosario/1.0 (public INIA data)"}),timeout=24) as resp:
 raw=resp.read(200_001)
if len(raw)>200_000:raise ValueError("XML too big")
root=ET.fromstring(raw)
print("ROOT",root.tag,"size",len(raw))
for station in root.findall(".//station"):
 print("STATION name",station.attrib)
 fields=station.findall("field")
 print("FIELDS total",len(fields))
 for i,field in enumerate(fields[:13]):
  print("FIELD",i,"attrs",field.attrib,"text",(field.text or "")[:200],
        "subnodes",[(c.tag,(c.text or "")[:120]) for c in list(field)[:6]])
print("HEAD",raw[:1100].decode("utf-8",errors="replace"))
