"""Validación acotada de navegación GDA con navegador real.

Solo se permite iniciar sesión y peticiones GET/HEAD. Se bloquea cualquier otra
petición POST/PUT/PATCH/DELETE, y no se guarda HTML, capturas, cookies, tokens,
mediciones ni nombres de estaciones. Uso exclusivamente manual (workflow_dispatch).
"""
import os
import re
from urllib.parse import urljoin, urlsplit
from playwright.sync_api import sync_playwright

BASE="https://gda.spymovil.com/"
HOST="gda.spymovil.com"
FORBIDDEN_PATH_PARTS=("/borrar","/eliminar","/delete","/remove",
                      "/desactivar","/activar","/edit","/editar","/configur",
                      "/alarma","/guardar","/update","/logout","/salir")

def permitted_url(url):
    p=urlsplit(url)
    return (p.scheme=="https" and p.hostname==HOST and
            p.port in (None,443) and not p.username and not p.password)

def route_label(url):
    if not permitted_url(url):return "other"
    p=urlsplit(url).path
    seg=next((x for x in p.split("/") if x),"home")
    if not re.fullmatch(r"[a-zA-Z_-]{1,22}",seg):return "dynamic"
    return seg.lower()

def main():
    username=os.environ.get("GDA_USERNAME")
    password=os.environ.get("GDA_PASSWORD")
    if not username or not password:
        print("Credentials not configured: no attempt made.")
        return 1
    calls=set()
    counts={"blocked_non_login_write":0,"blocked_unsafe_path":0,"external":0}
    login_post={"url":None,"used":False}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(ignore_https_errors=False,accept_downloads=False)
        page=context.new_page()
        page.set_default_timeout(12000)
        def restrict(route):
            request=route.request
            target=request.url
            parsed=urlsplit(target)
            if not permitted_url(target):
                counts["external"]+=1
                return route.abort()
            path=parsed.path.lower()
            if any(term in path for term in FORBIDDEN_PATH_PARTS):
                counts["blocked_unsafe_path"]+=1
                return route.abort()
            if request.method in ("GET","HEAD"):
                calls.add(route_label(target))
                return route.continue_()
            if (request.method=="POST" and login_post["url"]==target
                    and not login_post["used"] and request.is_navigation_request()):
                login_post["used"]=True
                return route.continue_()
            counts["blocked_non_login_write"]+=1
            return route.abort()
        context.route("**/*",restrict)
        page.goto(BASE,wait_until="domcontentloaded",timeout=25000)
        form=page.locator("form:has(input[type=password])")
        if form.count()!=1:
            raise RuntimeError("No se encontró un formulario de acceso único")
        action=form.get_attribute("action") or ""
        target=urljoin(page.url,action)
        if not permitted_url(target):
            raise RuntimeError("Acción de ingreso externa o insegura")
        login_post["url"]=target
        user_input=form.locator('input[type="text"], input[type="email"]')
        password_input=form.locator('input[type="password"]')
        if user_input.count()!=1 or password_input.count()!=1:
            raise RuntimeError("Formato de ingreso no reconocido")
        user_input.fill(username)
        password_input.fill(password)
        # Solo envía el formulario de login; la ruta de ejecución bloquea escrituras adicionales.
        with page.expect_navigation(wait_until="domcontentloaded",timeout=22000):
            password_input.press("Enter")
        page.wait_for_timeout(3500)
        final_path=route_label(page.url)
        tables=page.locator("table").count()
        rows=page.locator("table tbody tr").count()
        anchors=page.locator("a[href]").count()
        login_fields=page.locator("input[type=password]").count()
        # Solo estadísticas de estructura, nunca texto protegido o URLs con parámetros.
        print("Browser destination category:",final_path)
        print("Login POST submitted:",login_post["used"])
        print("Page structure counts:",{"tables":min(tables,500),"rows":min(rows,500),
                                         "links":min(anchors,500),"password_fields":login_fields})
        print("Observed safe route categories:",sorted(calls)[:20])
        print("Blocked additional non-login writes:",counts["blocked_non_login_write"])
        print("Blocked potentially modifying routes:",counts["blocked_unsafe_path"])
        print("Login appears to reach station list:",login_fields==0 and rows>0)
        context.close()
        browser.close()
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception as error:
        # Mensaje genérico. Los errores de red podrían contener tokens/paths privados.
        print("Browser diagnostic unsuccessful:",type(error).__name__)
        raise SystemExit(1)
