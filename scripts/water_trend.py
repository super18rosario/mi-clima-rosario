"""Análisis independiente de niveles de agua: no modifica Spymovil ni envía alertas.

Las mediciones originales se conservan y el análisis se realiza en memoria.
Las lecturas hasta 5 cm se muestran como 0; velocidad calculada con lecturas reales
cuando se supera la tolerancia, para evitar saltos artificiales de 0 a 5.01.
"""
from datetime import datetime, timezone
from math import isfinite

TOLERANCE_CM = 5.0

def visible_cm(raw_cm):
    if isinstance(raw_cm, bool) or not isinstance(raw_cm, (int,float)) or not isfinite(raw_cm) or raw_cm < 0:
        raise ValueError("Lectura inválida")
    return 0.0 if raw_cm <= TOLERANCE_CM else float(raw_cm)

def trend(readings):
    """Calcula el cambio y la tasa de subida en copias de datos privados.

    readings: dicts {'at': datetime con zona, 'cm': lectura sin modificar}
    Este módulo NO establece cortes, riesgos ni umbrales de alarmas.
    """
    data=[]
    for row in readings:
        at=row["at"]
        if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("Fecha y hora con zona horaria requeridas")
        raw=row["cm"]
        data.append((at.astimezone(timezone.utc), raw, visible_cm(raw)))
    if not data:
        return {"status":"sin_datos","altura_original_cm":None,"altura_visible_cm":None,
                "velocidad_cm_h":None}
    data.sort(key=lambda x:x[0])
    if len({x[0] for x in data})!=len(data):
        raise ValueError("Horarios duplicados")
    last=data[-1]
    result={"status":"sin_historial","altura_original_cm":last[1],"altura_visible_cm":last[2],
            "hora_utc":last[0].isoformat(),"velocidad_cm_h":None,"cambio_cm":None,
            "ventana_min":None,"requiere_confirmacion":True}
    pairs=[]
    for at,raw,shown in data[:-1]:
        elapsed=(last[0]-at).total_seconds()/60
        if 10<=elapsed<=90:
            pairs.append((elapsed,raw,shown))
    if not pairs:return result
    elapsed,prev_raw,prev_shown=min(pairs,key=lambda x:abs(x[0]-30))
    if last[1] <= TOLERANCE_CM and prev_raw <= TOLERANCE_CM:
        delta=0.0
    else:
        # Los valores visibles no sirven para calcular la tasa al cruzar los 5 cm.
        delta=round(float(last[1])-float(prev_raw),2)
    rate=round(delta*60/elapsed,2)
    crossed=prev_raw<=TOLERANCE_CM<last[1]
    result.update({"status":"subida_pendiente_confirmacion" if crossed and delta>0 else
                             "subiendo" if delta>0 else "bajando" if delta<0 else "sin_cambio",
                   "velocidad_cm_h":rate,"cambio_cm":delta,"ventana_min":round(elapsed,2),
                   "requiere_confirmacion":crossed})
    return result
