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
    for name in ("tabla_estaciones.js","main.js"):
        child=urljoin(url,name)
        try:
            _,code=read(child)
            print("JS",name,"longitud",len(code))
            hits=[m for m in re.finditer("estanzuela|La Estanzuela|href|link|url|location",code,re.I)]
            if name=="main.js":
                at=code.find("var zonaLE")
                if at>=0:
                    print("Zona La Estanzuela:",code[at:at+1350].replace("\\n"," "))
            for m in hits[:10]:
                snippet=re.sub(r"\\s+"," ",code[max(0,m.start()-120):m.end()+160])
                print("JS contexto:",snippet[:310])
        except Exception as exc:
            print("No se pudo consultar",name,type(exc).__name__)
    station="https://gras.inia.uy/agroclima/INIA_WN/inia_le.htm"
    page,raw=read(station)
    print("Estación real:",page,"HTML chars",len(raw))
    class TextOnly(HTMLParser):
        def __init__(self):
            super().__init__();self.parts=[]
        def handle_data(self,data):
            value=data.strip()
            if value:self.parts.append(value)
    parse=TextOnly();parse.feed(raw)
    visible=" | ".join(parse.parts)
    print("Texto visible:",visible[:2200])
    for key in ("Última Actualización","Ultima Actualizacion","Temperatura del Aire","temperatura del aire"):
        pos=raw.find(key)
        if pos>=0:
            print("Contexto HTML",key,":",raw[max(0,pos-220):pos+420].replace(chr(10)," ")[:650])
    from urllib.request import Request, urlopen
    from html import unescape
    url_ema="https://www.inumet.gub.uy/tiempo/estaciones-meteorologicas-automaticas"
    try:
        with urlopen(Request(url_ema,headers={"User-Agent":"Mozilla/5.0 MiClimaRosario/1.0"}),timeout=25) as resp:
            raw=resp.read(800_001)
            print("INUMET EMA status",resp.status,"bytes",len(raw))
        source=raw.decode("utf-8",errors="replace")
        for key in ("var estadoActual", "estadoActual =", "estadoActual=", "var estaciones", "variables", "fechas", "EMA_INIA_LaEstanzuela"):
            pos=source.find(key)
            if pos>=0:
                print("INUMET origen",key,":",source[max(0,pos-120):pos+900].replace(chr(10)," ")[:1000])
        p=Links();p.feed(source)
        for tag,value in p.values:
            absolute=urljoin(url_ema,value)
            if tag in ("script","iframe","frame"):
                print("INUMET referencia",tag,":",absolute[:220])
        for term in ("INIA La Estanzuela","La Estanzuela","Datos correspondientes","automatica"):
            pos=source.lower().find(term.lower())
            if pos>=0:
                chunk=re.sub(r"\\s+"," ",unescape(source[max(0,pos-250):pos+400]))
                print("INUMET fragmento",term,":",chunk[:670])
    except Exception as e:
        print("INUMET consulta no disponible:",type(e).__name__,str(e)[:160])
    js_url="https://www.inumet.gub.uy/modules/custom/externas/js/estadoActualEMA.js?v=1.x"
    try:
        with urlopen(Request(js_url,headers={"User-Agent":"Mozilla/5.0 MiClimaRosario/1.0"}),timeout=20) as resp:
            code=resp.read(180_001).decode("utf-8",errors="replace")
        print("INUMET frontend JS bytes:",len(code))
        print("INUMET JS completo:",code[:9500].replace(chr(10)," "))
        for line in code.splitlines():
            if any(x in line.lower() for x in ("fetch(","ajax","url:",".json","getjson","api/","observa","endpoint","fecha_ult_actualizacion","hora_ult_actualizacion")):
                print("INUMET JS:",line.strip()[:360])
    except Exception as e:print("INUMET JS inaccesible:",type(e).__name__,str(e)[:130])
    if not seen:
        print("Sin enlaces HTML; página puede emplear JavaScript o mapa dinámico")
if __name__=="__main__":probe()
