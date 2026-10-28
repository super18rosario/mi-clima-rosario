#!/usr/bin/env python3
"""Diagnóstico sin credenciales: identifica la página pública INIA en tiempo real."""
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
import re

START="https://gras.inia.uy/agroclima/INIA_WN/index.htm"
class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values=[]
    def handle_starttag(self, tag, attrs):
        values=dict(attrs)
        for key in ("href","src","data","action"):
            val=values.get(key)
            if val and not val.startswith(("data:","javascript:","#")):
                self.values.append((tag,val))
def read(url):
    p=urlparse(url)
    if p.scheme!="https" or p.netloc.lower() not in {"gras.inia.uy","www.inia.uy","inia.uy"}:
        raise ValueError("El enlace no es oficial INIA")
    with urlopen(Request(url,headers={"User-Agent":"MiClimaRosario/1.0 (public source verification)"}),timeout=25) as r:
        raw=r.read(300_001)
        if len(raw)>300_000: raise ValueError("Página demasiado grande")
        return r.url,raw.decode("utf-8",errors="replace")
def probe():
    url,body=read(START)
    print("Origen:",url,"caracteres:",len(body))
    parser=Links();parser.feed(body)
    seen=set()
    for kind,item in parser.values:
        dest=urljoin(url,item)
        if dest in seen:continue
        seen.add(dest)
        print("Referencia",kind,":",dest[:220])
    for term in ("Estanzuela","estanzuela","LA ESTANZUELA","La Estanzuela","LE.htm","le.htm"):
        pos=body.find(term)
        if pos>=0:
            chunk=re.sub(r"\\s+"," ",body[max(0,pos-170):pos+260])
            print("Texto relevante:",chunk[:430])
            break
    if not seen:
        print("Sin enlaces HTML; página puede emplear JavaScript o mapa dinámico")
if __name__=="__main__":probe()
