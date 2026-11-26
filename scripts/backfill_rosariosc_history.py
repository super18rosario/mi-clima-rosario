#!/usr/bin/env python3
"""Recupera lecturas de Rosario SC desde el historial git de data/rosariosc.json.

Uso único (o tras una interrupción): requiere historial completo
(git clone sin --depth, o `git fetch --unshallow`). No usa red ni claves.
Solo agrega lecturas válidas que falten en data/rosariosc_history/.
"""
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from merge_rosariosc import append_history  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def backfill(history_dir=ROOT / "data" / "rosariosc_history"):
    added = 0
    for commit in git("log", "--format=%H", "--", "data/rosariosc.json").split():
        try:
            record = json.loads(git("show", f"{commit}:data/rosariosc.json"))
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        temp = record.get("temperature_c")
        if (record.get("station_id") != "IROSAR145" or record.get("observation") is not True
                or not isinstance(temp, (int, float)) or not -40 <= temp <= 55):
            continue
        try:
            added += append_history(record, history_dir)
        except (KeyError, ValueError):
            continue
    # Ordenar cada archivo mensual por hora de observación.
    for path in pathlib.Path(history_dir).glob("????-??.csv"):
        header, *rows = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join([header, *sorted(set(rows))]) + "\n", encoding="utf-8")
    print("Lecturas recuperadas:", added)
    return added


if __name__ == "__main__":
    backfill()
