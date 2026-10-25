#!/usr/bin/env python3
"""Diagnóstico autorizado de login GDA Spymovil.

Credentials are injected by GitHub Actions secrets only; never logged or saved.
This script does not publish authenticated pages or private measurements.
"""
import http.cookiejar
import html.parser
import os
import sys
import urllib.parse
import urllib.request

BASE="https://gda.spymovil.com/"
HOST="gda.spymovil.com"
MAX_BYTES=300_000

class Forms(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms=[]
        self.active=None
        self.titles=[]
        self.in_title=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="form":
            self.active={"action":a.get("action",""),"method":a.get("method","get").lower(),"fields":[]}
        elif tag=="input" and self.active is not None:
            self.active["fields"].append({"name":a.get("name"),"type":a.get("type","text").lower(),"value":a.get("value","")})
        elif tag=="title":self.in_title=True
    def handle_endtag(self,tag):
        if tag=="form" and self.active is not None:
            self.forms.append(self.active)
            self.active=None
        if tag=="title":self.in_title=False
    def handle_data(self,data):
        if self.in_title:self.titles.append(data.strip())

class Overview(html.parser.HTMLParser):
    """Only collect technical navigation structure, never private page text or input values."""
    def __init__(self):
        super().__init__()
        self.links=[]
        self.scripts=[]
        self.tables=0
        self.forms=0
        self.hidden_endpoints=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="a" and a.get("href"):
            self.links.append(a["href"])
        elif tag=="script" and a.get("src"):
            self.scripts.append(a["src"])
        elif tag=="table":
            self.tables+=1
        elif tag=="form":
            self.forms+=1
        for k in a:
            if k.startswith("data-") and any(x in k for x in ("url","api","endpoint")):
                self.hidden_endpoints+=1

def path_only(base,href):
    try:
        p=urllib.parse.urlsplit(urllib.parse.urljoin(base,href))
        if p.scheme!="https" or p.hostname!=HOST or p.username or p.password:
            return None
        if any(x in p.path.lower() for x in ("logout","salir","delete","borrar","eliminar")):
            return None
        if not p.path.startswith("/") or len(p.path)>120:
            return None
        # Do not expose station identifiers or embedded credentials in public Actions logs.
        import re
        return re.sub(r"[a-zA-Z0-9_-]{16,}", "<redacted>",p.path)
    except (ValueError,TypeError):
        return None

def safe_url(url):
    p=urllib.parse.urlsplit(url)
    if p.scheme!="https" or p.hostname!=HOST or p.username or p.password or p.port not in (None,443):
        raise ValueError("Login destination is not expected HTTPS GDA host")
    return url

def decode(response):
    if "text/html" not in response.headers.get("Content-Type","").lower():
        raise ValueError("Unexpected content type (expected HTML)")
    b=response.read(MAX_BYTES+1)
    if len(b)>MAX_BYTES:raise ValueError("Login page too large")
    return b.decode("utf-8","replace")

def login(user,password):
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    request=urllib.request.Request(BASE,headers={"User-Agent":"Mozilla/5.0 (authorized system compatibility check)"})
    with opener.open(request,timeout=22) as r:
        page=decode(r)
        safe_url(r.url)
    doc=Forms();doc.feed(page)
    candidates=[f for f in doc.forms if f["method"]=="post" and any(v["type"]=="password" for v in f["fields"])]
    if len(candidates)!=1:
        raise ValueError("Expected exactly one password login form")
    form=candidates[0]
    text_fields=[v for v in form["fields"] if v["type"] in ("text","email") and v["name"]]
    pass_fields=[v for v in form["fields"] if v["type"]=="password" and v["name"]]
    if len(text_fields)!=1 or len(pass_fields)!=1:
        raise ValueError("Unexpected login form schema")
    payload={f["name"]:f["value"] for f in form["fields"] if f["name"] and f["type"] in ("hidden","submit")}
    payload[text_fields[0]["name"]]=user
    payload[pass_fields[0]["name"]]=password
    action=safe_url(urllib.parse.urljoin(BASE,form["action"]))
    req=urllib.request.Request(action,data=urllib.parse.urlencode(payload).encode(),method="POST",headers={"User-Agent":"Mozilla/5.0 (authorized system compatibility check)","Content-Type":"application/x-www-form-urlencoded"})
    with opener.open(req,timeout=25) as r:
        end=safe_url(r.url)
        result=decode(r)
        status=r.status
    parsed=Forms();parsed.feed(result)
    password_forms=sum(1 for f in parsed.forms for v in f["fields"] if v["type"]=="password")
    print("Portal HTTPS reachable: yes")
    print("Login POST HTTP status:",status)
    print("Final path:",urllib.parse.urlsplit(end).path)
    print("Password forms on response:",password_forms)
    print("Login diagnostic:", "possible success - manual post-login schema inspection still needed" if password_forms==0 else "login form remains (not authenticated or more steps required)")
    overview=Overview()
    overview.feed(result)
    paths=sorted({x for href in overview.links if (x:=path_only(end,href))})
    static_scripts=sorted({x for href in overview.scripts if (x:=path_only(end,href))})
    print("Private page structural diagnostics only:")
    print("Internal navigation paths:",paths[:30])
    print("Navigation link count:",len(overview.links))
    print("Tables detected:",overview.tables,"forms:",overview.forms)
    print("Static script paths:",static_scripts[:14])
    print("Declared data endpoint attributes:",overview.hidden_endpoints)
    # No page text, station data, cookies, tokens or query parameters are written or logged.
    # NEVER print HTML, cookies, URLs with querystrings, account records, usernames or passwords.

if __name__=="__main__":
    username=os.environ.get("GDA_USERNAME")
    password=os.environ.get("GDA_PASSWORD")
    if not username or not password:
        print("Missing GitHub Actions secrets GDA_USERNAME and GDA_PASSWORD. No login attempted.")
        sys.exit(0)
    try: login(username,password)
    except Exception as e:
        print("Authenticated source diagnostic unsuccessful:",type(e).__name__,str(e)[:120])
        sys.exit(1)
