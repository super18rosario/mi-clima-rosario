#!/usr/bin/env python3
"""Diagnóstico de HTML público INIA. No realiza escrituras ni usa credenciales."""
import re
import urllib.request
from html.parser import HTMLParser

URL="https://gras.inia.uy/agroclima/INIA_WN/cargo_datos_le.htm"
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        for key in ("src","href","data"):
            if attrs.get(key):self.links.append((tag,key,attrs[key]))
with urllib.request.urlopen(urllib.request.Request(URL,headers={"User-Agent":"MiClimaRosario/1.0 (public meteorological data)"}),timeout=24) as response:
    raw=response.read(400_001)
if len(raw)>400_000:raise ValueError("La pagina supera limite")
s=raw.decode("utf-8",errors="replace")
print("INIA length",len(s),"title",re.findall(r"<title[^>]*>(.*?)</title>",s,re.I|re.S)[:2])
p=Links();p.feed(s)
for item in p.links[:65]:print("ENLACE",item)
for term in ("Temperatura del Aire","Temperatura","Última Actualización","Ultima Actualizacion","Actualización","Actualizacion","Air Temperature","9.2","fecha","Last Update","Celsius"):
  for m in list(re.finditer(re.escape(term),s,re.I))[:2]:
    t=re.sub(r"\s+"," ",s[max(m.start()-180,0):m.end()+230])
    print("CAMPO",term,":",t[:430])
print("INICIO HTML",re.sub(r"\s+"," ",s[:1800])[:1700])
