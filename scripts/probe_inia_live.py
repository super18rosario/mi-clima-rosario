#!/usr/bin/env python3
"""Lectura diagnóstica de la página meteorológica pública INIA, solo GET."""
from html.parser import HTMLParser
from urllib.request import urlopen,Request
from urllib.parse import urljoin,urlparse
import re
PAGE="https://gras.inia.uy/agroclima/INIA_WN/cargo_datos_le.htm"
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  for k in ("src","href","data"):
   if d.get(k) and not d[k].startswith(("#","javascript:","data:")):
    self.links.append(urljoin(PAGE,d[k]))
def get(url):
 if urlparse(url).scheme!="https" or urlparse(url).netloc!="gras.inia.uy":
  raise ValueError("Dominio INIA inválido")
 with urlopen(Request(url,headers={"User-Agent":"MiClimaRosario/INIA-ReadOnly"}),timeout=20) as response:
  raw=response.read(350001)
 if len(raw)>350000:raise ValueError("Documento demasiado largo")
 return raw.decode("latin-1",errors="replace")
if __name__=="__main__":
 doc=get(PAGE)
 print("Página:",PAGE,"caracteres:",len(doc))
 p=Links();p.feed(doc)
 print("Referencias internas:",[x for x in p.links if urlparse(x).netloc=="gras.inia.uy"][:30])
 # HTML público con instrumentos y encabezados, sin tokens ni cookies.
 for term in ["Temperatura del Aire","Temperatura","Última Actualización","Última Actualizacion","Air Temperature","Actualización","<!--","iframe","refresh","http","Fahrenheit"]:
  hit=re.search(re.escape(term),doc,re.I)
  if hit:
   snippet=doc[max(0,hit.start()-120):min(len(doc),hit.end()+850)]
   print("FRAGMENTO",term,repr(snippet[:990]))
 print("HTML PRINCIPAL:",repr(doc[:30000]))
