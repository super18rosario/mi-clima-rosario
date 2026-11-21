"""Preserve the newest Rosario SC reading across overlapping GitHub Actions runs."""
import json
import pathlib
import sys

def merge(incoming_path, destination_path):
    incoming_path = pathlib.Path(incoming_path)
    destination_path = pathlib.Path(destination_path)
    incoming = json.loads(incoming_path.read_text(encoding="utf-8"))
    if incoming.get("station_id") != "IROSAR145" or not incoming.get("observation"):
        raise ValueError("Invalid incoming station")
    if destination_path.exists():
        current = json.loads(destination_path.read_text(encoding="utf-8"))
        if current.get("observed_at_utc", "") >= incoming.get("observed_at_utc", ""):
            print("Preserved existing equal/newer Rosario SC reading")
            return False
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(incoming_path.read_text(encoding="utf-8"), encoding="utf-8")
    return True

if __name__ == "__main__":
    merge(sys.argv[1], sys.argv[2])
