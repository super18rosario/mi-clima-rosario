"""Regression tests for chronological merge of Rosario SC observations."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.merge_rosariosc import merge


def observation(stamp, station="IROSAR145"):
    return {"station_id": station, "observation": True, "observed_at_utc": stamp}


class MergeRosarioSCTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.incoming = Path(self.tmp.name) / "incoming.json"
        self.destination = Path(self.tmp.name) / "destination.json"

    def write(self, path, stamp, station="IROSAR145"):
        path.write_text(json.dumps(observation(stamp, station)), encoding="utf-8")

    def test_newer_replaces_older(self):
        self.write(self.destination, "2026-11-21T18:00:00Z")
        self.write(self.incoming, "2026-11-21T19:00:00Z")
        self.assertTrue(merge(self.incoming, self.destination))
        self.assertEqual(json.loads(self.destination.read_text())["observed_at_utc"], "2026-11-21T19:00:00Z")

    def test_older_does_not_replace_newer(self):
        self.write(self.destination, "2026-11-21T20:50:00Z")
        self.write(self.incoming, "2026-11-21T18:00:00Z")
        self.assertFalse(merge(self.incoming, self.destination))

    def test_equal_in_different_timezones_does_not_replace(self):
        self.write(self.destination, "2026-11-21T20:00:00Z")
        self.write(self.incoming, "2026-11-21T17:00:00-03:00")
        self.assertFalse(merge(self.incoming, self.destination))

    def test_later_in_different_timezone_replaces(self):
        self.write(self.destination, "2026-11-21T20:00:00Z")
        self.write(self.incoming, "2026-11-21T18:00:00-03:00")
        self.assertTrue(merge(self.incoming, self.destination))

    def test_other_station_rejected(self):
        self.write(self.incoming, "2026-11-21T20:00:00Z", "OTHER")
        with self.assertRaises(ValueError):
            merge(self.incoming, self.destination)

    def test_naive_timestamp_rejected(self):
        self.write(self.incoming, "2026-11-21T20:00:00")
        with self.assertRaises(ValueError):
            merge(self.incoming, self.destination)

    def test_history_appends_once_and_keeps_late_readings(self):
        history = Path(self.tmp.name) / "history"
        def reading(stamp, temp):
            self.incoming.write_text(json.dumps({**observation(stamp), "temperature_c": temp}), encoding="utf-8")
        reading("2026-11-21T19:00:00Z", 25.0)
        self.assertTrue(merge(self.incoming, self.destination, history))
        self.assertFalse(merge(self.incoming, self.destination, history))   # repetida
        reading("2026-11-21T18:50:00Z", 24.5)                                 # llega tarde
        self.assertFalse(merge(self.incoming, self.destination, history))
        lines = (history / "2026-11.csv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("observed_at_utc,temperature_c"))
        self.assertIn("2026-11-21T18:50:00Z,24.5", lines[2])
        self.assertEqual(json.loads(self.destination.read_text())["observed_at_utc"], "2026-11-21T19:00:00Z")

    def test_history_splits_by_month(self):
        history = Path(self.tmp.name) / "history"
        self.incoming.write_text(json.dumps({**observation("2026-12-01T00:05:00Z"), "temperature_c": 20}), encoding="utf-8")
        merge(self.incoming, self.destination, history)
        self.assertTrue((history / "2026-12.csv").exists())


if __name__ == "__main__":
    unittest.main()
