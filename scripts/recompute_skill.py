#!/usr/bin/env python3
"""Recalcula aciertos con observaciones públicas previamente guardadas.

No hace solicitudes de red, no lee credenciales y no modifica sensores ni
alarmas. Sirve aunque INUMET no esté disponible durante una publicación.
"""
import json

from observe import DATA, dump, evaluate

def recompute():
    obs_path=DATA/"observations.json"
    if not obs_path.is_file():
        print("Sin observaciones oficiales guardadas: no se modifica el resumen.")
        return
    try:
        observed=json.loads(obs_path.read_text(encoding="utf-8"))
        if observed.get("schema")!=1 or observed.get("station")!="Colonia G3" or not isinstance(observed.get("days"),dict):
            raise ValueError("Fuente o formato de observaciones no verificado")
        summary=evaluate(observed,DATA/"forecast_archive")
        dump(DATA/"skill.json",summary)
        print("Evaluación actualizada sobre",len(summary["eligible_dates"]),"día(s) comparables")
    except (OSError,ValueError,KeyError,TypeError) as error:
        print("No se actualizó la evaluación por falta de datos válidos:",type(error).__name__)

if __name__=="__main__":
    recompute()
