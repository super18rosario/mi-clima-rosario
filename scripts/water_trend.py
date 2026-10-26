"""Cálculos locales de altura y velocidad. No se conecta a Spymovil ni modifica alarmas."""
from datetime import datetime, timezone
from math import isfinite

TOLERANCE_CM = 5.0

def visible_cm(raw_cm):
    if isinstance(raw_cm,bool) or not isinstance(raw_cm,(int,float)) or not isfinite(raw_cm) or raw_cm < 0:
        raise ValueError("Lectura inválida")
    return 0.0 if raw_cm <= TOLERANCE_CM else float(raw_cm)

def trend(readings):
    """Datos privados en memoria: lista de dicts {'at': datetime, 'cm': valor}.
    No modifica lecturas originales, no emite alertas ni determina cortes."""
    data=[]
    for row in readings:
        at=row["at"]
        if not isinstance(at,datetime) or at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("Fecha y hora con zona horaria requeridas")
        raw=row["cm"]
        data.append((at.astimezone(timezone.utc), raw, visible_cm(raw)))
    if not data:
        return {"status":"sin_datos","altura_original_cm":None,"altura_visible_cm":None,"velocidad_cm_h":None}
    data.sort(key=lambda x:x[0])
    if len(set(v[0] for v in data))!=len(data):
        raise ValueError("Horarios duplicados")
    last=data[-1]
    result={"status":"sin_historial","altura_original_cm":last[1],"altura_visible_cm":last[2],
            "hora_utc":last[0].isoformat(),"velocidad_cm_h":None,"cambio_cm":None,"ventana_min":None}
    candidates=[]
    for at,raw,visible in data[:-1]:
        elapsed=(last[0]-at).total_seconds()/60
        if 10<=elapsed<=90:candidates.append((elapsed,visible))
    if not candidates:return result
    elapsed,earlier=min(candidates,key=lambda p:abs(p[0]-30))
    change=round(last[2]-earlier,2)
    result.update({"status":"subiendo" if change>0 else "bajando" if change<0 else "sin_cambio",
                   "velocidad_cm_h":round(change*60/elapsed,2),
                   "cambio_cm":change,"ventana_min":round(elapsed,2)})
    return result
