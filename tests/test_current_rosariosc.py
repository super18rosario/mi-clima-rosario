"""Regression checks for Rosario SC PWS observations (no network)."""
import datetime as dt
import unittest
from scripts.current_rosariosc import parse

NOW = dt.datetime(2026, 11, 21, 16, 35, tzinfo=dt.timezone.utc)

def sample(**changes):
    observation = {
        "stationID": "IROSAR145",
        "metric": {"temp": 27.6},
        "obsTimeUtc": "2026-11-21T16:32:36Z",
    }
    observation.update(changes)
    return {"observations": [observation]}

class RosarioSCTests(unittest.TestCase):
    def test_valid_temperature(self):
        result = parse(sample(), NOW)
        self.assertEqual(result["temperature_c"], 27.6)
        self.assertEqual(result["station_id"], "IROSAR145")
    def test_reject_other_station(self):
        with self.assertRaises(ValueError):
            parse(sample(stationID="IROSAR171"), NOW)
    def test_reject_stale_reading(self):
        with self.assertRaises(ValueError):
            parse(sample(obsTimeUtc="2026-11-21T15:00:00Z"), NOW)
    def test_reject_future_reading(self):
        with self.assertRaises(ValueError):
            parse(sample(obsTimeUtc="2026-11-21T16:50:00Z"), NOW)
    def test_reject_invalid_temperature(self):
        with self.assertRaises(ValueError):
            parse(sample(metric={"temp": None}), NOW)
    def test_reject_missing_observations(self):
        with self.assertRaises(ValueError):
            parse({"observations": []}, NOW)

    def test_optional_extras_kept_only_when_valid(self):
        result = parse(sample(humidity=55, metric={"temp": 27.6, "precipTotal": 1.2, "pressure": 5000}), NOW)
        self.assertEqual(result["humidity_pct"], 55)
        self.assertEqual(result["precip_total_mm"], 1.2)
        self.assertIsNone(result["pressure_hpa"])
        self.assertIsNone(result["wind_gust_kmh"])


if __name__ == "__main__":
    unittest.main()
