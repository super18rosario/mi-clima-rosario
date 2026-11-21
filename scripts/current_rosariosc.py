"""Read current Rosario SC observation using the official Weather Underground PWS API."""
import datetime as dt
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
import urllib.error
import time

STATION = "IROSAR145"
OUTPUT = Path("data/rosariosc.json")

def parse(payload, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    observations = payload.get("observations", [])
    if not isinstance(observations, list) or not observations:
        raise ValueError("No recent station observation")
    obs = observations[0]
    if obs.get("stationID", "").upper() != STATION:
        raise ValueError("Station ID mismatch")
    value = obs.get("metric", {}).get("temp")
    if type(value) not in (float, int) or not -40 <= value <= 55:
        raise ValueError("Invalid temperature")
    stamp = obs.get("obsTimeUtc")
    if not isinstance(stamp, str):
        raise ValueError("Missing timestamp")
    observed = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    age = (now - observed).total_seconds() / 60
    if not -5 <= age <= 30:
        raise ValueError("Stale or future observation")
    return {
        "schema": 1, "station_id": STATION, "station_name": "Rosario SC",
        "source": "Weather Underground PWS", "temperature_c": value,
        "observed_at_utc": observed.isoformat().replace("+00:00", "Z"),
        "collected_at_utc": now.isoformat().replace("+00:00", "Z"),
        "observation": True
    }

def main():
    key = os.environ.get("WU_API_KEY", "")
    if not key:
        print("Weather Underground API key not configured")
        raise SystemExit(1)
    params = urllib.parse.urlencode({
        "stationId": STATION, "format": "json", "units": "m",
        "numericPrecision": "decimal", "apiKey": key
    })
    request = urllib.request.Request(
        "https://api.weather.com/v2/pws/observations/current?" + params,
        headers={"User-Agent": "MiClimaRosario/1.0"}
    )
    record = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                record = parse(json.load(response))
            break
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            retryable = not isinstance(error, urllib.error.HTTPError) or error.code == 429 or 500 <= error.code <= 599
            if not retryable or attempt == 1:
                print("Weather Underground unavailable:", type(error).__name__)
                raise SystemExit(1)
            time.sleep(3)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            print("Weather Underground invalid observation:", type(error).__name__)
            raise SystemExit(1)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("Rosario SC: valid observation saved")

if __name__ == "__main__":
    main()
