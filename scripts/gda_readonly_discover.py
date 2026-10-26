"""Diagnóstico mínimo y privado de navegación tras login autorizado a GDA.

NO guarda respuestas protegidas, lecturas, cookies ni estaciones.
SOLO GET en dos páginas conocidas; se limita la salida a contadores y banderas.
"""
import html.parser
import os
import sys
import urllib.parse
import urllib.request

from gda_probe import BASE, decode, login, safe_url

class SafeStructure(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=0
        self.tables=0
        self.forms=0
        self.scripts=0
        self.inline_scripts=0
        self.meta_refresh=False
        self.script_mode=False
        self.js_parts=[]
        self.visible_parts=[]
        self.body=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="a":self.links+=1
        if tag=="table":self.tables+=1
        if tag=="form":self.forms+=1
        if tag=="script":
            self.scripts+=1
            self.script_mode=True
            if not a.get("src"):self.inline_scripts+=1
        if tag=="meta" and a.get("http-equiv","").lower()=="refresh":
            self.meta_refresh=True
        if tag=="body":self.body=True
    def handle_endtag(self,tag):
        if tag=="script":self.script_mode=False
        if tag=="body":self.body=False
    def handle_data(self,data):
        if self.script_mode:self.js_parts.append(data)
        elif self.body:self.visible_parts.append(data)

def inspect(name,page):
    p=SafeStructure()
    p.feed(page)
    js=" ".join(p.js_parts).lower()
    visible=" ".join(p.visible_parts).lower()
    flags={
        "js_redirect":any(s in js for s in ("window.location","location.href","location.replace")),
        "js_network":any(s in js for s in ("ajax(","fetch(","xmlhttprequest","websocket")),
        "html_meta_refresh":p.meta_refresh,
        "permissions_word": "permiso" in visible,
        "denied_word":any(s in visible for s in ("denegado","sin autorización","no autorizado","no tiene permiso","acceso restringido")),
        "login_word":any(s in visible for s in ("iniciar sesión","ingresar","contraseña")),
        "list_word":any(s in visible for s in ("listado","tabla","columna")),
    }
    print("Checked page:",name)
    print("HTML structure:",{"links":p.links,"tables":p.tables,"forms":p.forms,
        "script_tags":p.scripts,"inline_scripts":p.inline_scripts})
    print("Limited text and navigation indicators:",flags)
    # No raw HTML, JavaScript, redirects, cookies, URLs with parameters or data.

def main():
    username=os.getenv("GDA_USERNAME")
    password=os.getenv("GDA_PASSWORD")
    if not username or not password:
        print("GDA secrets not configured; authenticated inspection not attempted.")
        return 1
    opener,url,page=login(username,password)
    inspect("login_redirect",page)
    # GET ONLY: existing site entrypoints, no guessed APIs or mutable URLs.
    for name,path in (("authenticated_home","/"),("permissions_page","/permisos/")):
        target=safe_url(urllib.parse.urljoin(BASE,path))
        req=urllib.request.Request(target,headers={"User-Agent":"Mozilla/5.0 (readonly compatibility check)","Accept":"text/html"})
        with opener.open(req,timeout=20) as resp:
            safe_url(resp.url)
            page=decode(resp)
        inspect(name,page)
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except Exception as exc:
        # Printing generic type only avoids exposing private URLs/tokens in errors.
        print("Safe diagnostic failed:",type(exc).__name__)
        sys.exit(1)
