"""Comparación pronóstico vs Rosario SC con datos sintéticos (sin red)."""
import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import verify_rosariosc as v

UTC = dt.timezone.utc


def write_history(folder, start, hours, temp_at, step=10, skip=()):
    folder.mkdir(parents=True, exist_ok=True)
    lines = ["observed_at_utc,temperature_c"]
    t = start
    while t < start + dt.timedelta(hours=hours):
        if t not in skip:
            lines.append(f"{t:%Y-%m-%dT%H:%M:%SZ},{temp_at(t)}")
        t += dt.timedelta(minutes=step)
    (folder / f"{start:%Y-%m}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def snapshot(folder, issue, target, offset, with_hourly=True):
    hourly = {}
    if with_hourly:
        start = dt.datetime(2026, 11, int(target[-2:]), 3, tzinfo=UTC)  # 00 h local
        for model, delta in offset.items():
            hourly[model] = {f"{start + dt.timedelta(hours=h):%Y-%m-%dT%H:%MZ}": 20 + delta
                             for h in range(24)}
    data = {"collection_local_date": issue, "target_tomorrow": target,
            "days": {target: {m: {"tmax": 20 + d, "tmin": 20 + d, "rain_mm": 0}
                              for m, d in offset.items()}},
            "hourly_temperature_c": hourly}
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{issue}.json").write_text(json.dumps(data), encoding="utf-8")


class VerifyRosarioSCTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)

    def test_bias_and_mae_for_hourly_and_extremes(self):
        write_history(self.root / "h", dt.datetime(2026, 11, 23, 3, tzinfo=UTC), 24, lambda t: 20.0)
        snapshot(self.root / "a", "2026-11-22", "2026-11-23", {"ecmwf": 1.0, "gfs": -2.0, "icon": 0.5})
        result = v.evaluate(v.load_history(self.root / "h"), self.root / "a")
        self.assertEqual(result["evaluated_dates"], ["2026-11-23"])
        self.assertEqual(result["models"]["ecmwf"]["hourly"]["n"], 24)
        self.assertEqual(result["models"]["ecmwf"]["hourly"]["bias_c"], 1.0)
        self.assertEqual(result["models"]["gfs"]["tmax"]["bias_c"], -2.0)
        self.assertEqual(result["models"]["icon"]["tmin"]["mae_c"], 0.5)
        self.assertEqual(result["models"]["aifs"]["hourly"]["n"], 0)

    def test_incomplete_day_is_not_scored_for_extremes(self):
        start = dt.datetime(2026, 11, 23, 3, tzinfo=UTC)
        gap = {start + dt.timedelta(minutes=m) for m in range(600, 720, 10)}  # 2 h sin datos
        write_history(self.root / "h", start, 24, lambda t: 20.0, skip=gap)
        snapshot(self.root / "a", "2026-11-22", "2026-11-23", {"ecmwf": 1.0}, with_hourly=False)
        result = v.evaluate(v.load_history(self.root / "h"), self.root / "a")
        self.assertEqual(result["models"]["ecmwf"]["tmax"]["n"], 0)
        self.assertEqual(result["evaluated_dates"], [])

    def test_hourly_match_uses_tolerance(self):
        readings = [(dt.datetime(2026, 11, 23, 12, 7, tzinfo=UTC), 25.0)]
        self.assertEqual(v.nearest(readings, dt.datetime(2026, 11, 23, 12, tzinfo=UTC)), 25.0)
        self.assertIsNone(v.nearest(readings, dt.datetime(2026, 11, 23, 11, 50, tzinfo=UTC)))

    def test_same_day_forecast_is_ignored(self):
        write_history(self.root / "h", dt.datetime(2026, 11, 23, 3, tzinfo=UTC), 24, lambda t: 20.0)
        snapshot(self.root / "a", "2026-11-23", "2026-11-23", {"ecmwf": 1.0})
        result = v.evaluate(v.load_history(self.root / "h"), self.root / "a")
        self.assertEqual(result["evaluated_dates"], [])

    def test_no_winner_with_few_days(self):
        daily = {m: {f"d{i}": e for i in range(10)} for m, e in (("ecmwf", 1.0), ("gfs", 2.0), ("icon", 3.0))}
        result = v.compare(daily, "hourly")
        self.assertEqual(result["best"], "ecmwf")
        self.assertFalse(result["ranking_supported"])

    def test_winner_requires_clear_difference(self):
        clear = {m: {f"d{i}": e + (i % 3) * 0.1 for i in range(40)}
                 for m, e in (("ecmwf", 1.0), ("gfs", 2.0), ("icon", 2.5))}
        self.assertTrue(v.compare(clear, "hourly")["ranking_supported"])
        tie = {m: {f"d{i}": (1.0 if (i + k) % 2 else 2.0) for i in range(40)}
               for k, m in enumerate(("ecmwf", "gfs", "icon"))}
        self.assertFalse(v.compare(tie, "hourly")["ranking_supported"])

    def test_run_without_history_writes_nothing(self):
        (self.root / "forecast_archive").mkdir()
        self.assertIsNone(v.run(self.root))
        self.assertFalse((self.root / "skill_rosariosc.json").exists())

    def test_filled_model_keeps_its_own_issue_time(self):
        write_history(self.root / "h", dt.datetime(2026, 11, 23, 3, tzinfo=UTC), 24, lambda t: 20.0)
        snapshot(self.root / "a", "2026-11-22", "2026-11-23", {"ecmwf": 1.0, "gfs": 0.5, "icon": 0.0})
        path = self.root / "a" / "2026-11-22.json"
        data = json.loads(path.read_text())
        data["collected_at_utc"] = "2026-11-23T00:23:00Z"          # toma general: 21:23
        data["late_fills"] = {"gfs": "2026-11-22T12:23:00Z"}       # GFS vino de las 09:23
        path.write_text(json.dumps(data))
        result = v.evaluate(v.load_history(self.root / "h"), self.root / "a")
        self.assertEqual(result["issue_local_times"]["2026-11-23"],
                         {"ecmwf": "21:23", "gfs": "09:23", "icon": "21:23"})
        self.assertEqual(result["fixed_time_dates"]["ecmwf"], ["2026-11-23"])
        self.assertEqual(result["fixed_time_dates"]["gfs"], [])
        self.assertEqual(result["fixed_time_dates"]["aifs"], [])

    def test_issue_time_without_collection_stamp_is_none(self):
        self.assertIsNone(v.model_issue_local({}, "ecmwf"))
        self.assertEqual(v.model_issue_local({"collected_at_utc": "2026-11-23T00:23:00Z"}, "icon"), "21:23")

if __name__ == "__main__":
    unittest.main()
