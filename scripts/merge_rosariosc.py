"""Preserve the newest Rosario SC reading across overlapping GitHub Actions runs
and keep a monthly CSV history of every valid reading (no duplicates)."""
import csv
import datetime as dt
import io
import json
import pathlib
import sys

HISTORY_FIELDS = ("observed_at_utc", "temperature_c", "humidity_pct", "dewpoint_c",
                  "pressure_hpa", "precip_rate_mm_h", "precip_total_mm",
                  "wind_speed_kmh", "wind_gust_kmh")


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp must include timezone')
    return parsed.astimezone(dt.timezone.utc)


def append_history(record, history_dir):
    """Add one reading to data/rosariosc_history/YYYY-MM.csv unless already present."""
    at = timestamp(record["observed_at_utc"])
    if not isinstance(record.get("temperature_c"), (int, float)):
        raise ValueError("Reading without temperature")
    stamp = at.strftime("%Y-%m-%dT%H:%M:%SZ")
    path = pathlib.Path(history_dir) / f"{at:%Y-%m}.csv"
    if path.exists():
        with path.open(encoding="utf-8", newline="") as handle:
            if any(row.get("observed_at_utc") == stamp for row in csv.DictReader(handle)):
                return False
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=HISTORY_FIELDS, lineterminator="\n")
    if new_file:
        writer.writeheader()
    row = {key: record.get(key) for key in HISTORY_FIELDS}
    row["observed_at_utc"] = stamp
    writer.writerow({k: "" if v is None else v for k, v in row.items()})
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(buffer.getvalue())
    return True


def merge(incoming_path, destination_path, history_dir=None):
    incoming_path = pathlib.Path(incoming_path)
    destination_path = pathlib.Path(destination_path)
    incoming = json.loads(incoming_path.read_text(encoding="utf-8"))
    if incoming.get("station_id") != "IROSAR145" or not incoming.get("observation"):
        raise ValueError("Invalid incoming station")
    incoming_time = timestamp(incoming['observed_at_utc'])
    if history_dir is not None and "temperature_c" in incoming:
        # Una lectura retrasada no reemplaza la actual, pero sí completa el histórico.
        append_history(incoming, history_dir)
    if destination_path.exists():
        current = json.loads(destination_path.read_text(encoding="utf-8"))
        if timestamp(current['observed_at_utc']) >= incoming_time:
            print("Preserved existing equal/newer Rosario SC reading")
            return False
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(incoming_path.read_text(encoding="utf-8"), encoding="utf-8")
    return True

if __name__ == "__main__":
    merge(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
