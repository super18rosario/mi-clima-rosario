import datetime as dt
import io
import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
import observe

NOW=dt.datetime(2026,10,22,13,0,tzinfo=dt.timezone.utc)
BASE=dt.datetime(2026,10,20,3,0,tzinfo=dt.timezone.utc)

class INUMETTests(unittest.TestCase):
    def test_utc_local_temperature_complete_day(self):
        rows=["fecha;estacion_id;temp_aire"]
        for h in range(24):
            ts=BASE+dt.timedelta(hours=h)
            rows.append(f"{ts.strftime('%Y-%m-%d %H:%M')};Colonia G3;{10+h%14}")
        rows.append("2026-10-20 03:00;Mercedes G3;-42")
        dates=observe.parse_csv("\n".join(rows),"temperature",NOW)
        self.assertEqual(len(dates["2026-10-20"]),24)
        result=observe.build_observations(dates,{},NOW)
        self.assertTrue(result["days"]["2026-10-20"]["temperature_usable"])
        self.assertEqual(result["days"]["2026-10-20"]["tmax_hourly"],23.0)

    def test_rain_hour_closes_previous_day(self):
        rows=["fecha;estacion_id;precip_horario"]
        for h in range(24):
            ts=BASE+dt.timedelta(hours=h+1)
            rows.append(f"{ts.strftime('%Y-%m-%d %H:%M')};Colonia G3;{1.3 if h==23 else 0}")
        rain=observe.parse_csv("\n".join(rows),"rain",NOW)
        self.assertEqual(len(rain["2026-10-20"]),24)
        self.assertNotIn("2026-10-21",rain)
        o=observe.build_observations({},rain,NOW)
        self.assertEqual(o["days"]["2026-10-20"]["rain_mm"],1.3)

    def test_missing_hour_never_assumed_zero(self):
        rain={ "2026-10-20":{str(i):0.0 for i in range(23)} }
        obs=observe.build_observations({},rain,NOW)
        self.assertIsNone(obs["days"]["2026-10-20"]["rain_mm"])
        self.assertFalse(obs["days"]["2026-10-20"]["rain_usable"])

    def test_invalid_station_and_conflicting_duplicate(self):
        x="fecha;estacion_id;temp_aire\n2026-10-20 03:00;Mercedes G3;3\n2026-10-20 03:00;Colonia G3;20\n2026-10-20 03:00;Colonia G3;30\n"
        self.assertEqual(sum(len(v) for v in observe.parse_csv(x,"temperature",NOW).values()),0)

    def test_only_prior_day_forecast_evaluated(self):
        dates={"2026-10-20":{"temperature_usable":True,"rain_usable":True,"tmax_hourly":22.0,"tmin_hourly":12.0,"rain_mm":3.0}}
        reference={"days":dates}
        with tempfile.TemporaryDirectory() as folder:
            p=pathlib.Path(folder)
            snapshot={"collection_local_date":"2026-10-19","target_tomorrow":"2026-10-20","days":{"2026-10-20":{"ecmwf":{"tmax":23,"tmin":12,"rain_mm":2},"gfs":{"tmax":20,"tmin":10,"rain_mm":0}}}}
            (p/"2026-10-19.json").write_text(json.dumps(snapshot))
            output=observe.evaluate(reference,p)
        self.assertEqual(output["models"]["ecmwf"]["rain"]["correct"],1)
        self.assertEqual(output["models"]["ecmwf"]["rain"]["mae_mm"],1.0)
        self.assertEqual(output["models"]["gfs"]["rain"]["misses"],1)
        self.assertEqual(output["models"]["gfs"]["rain"]["mae_mm"],3.0)
        self.assertEqual(output["models"]["ecmwf"]["tmax"]["mae_c"],1)
        self.assertFalse(output["ranking_enabled"])
        self.assertEqual(output["eligible_dates"],["2026-10-20"])

    def test_rain_miss_and_false_alarm_counted_separately(self):
        reference={"days":{
            "2026-10-20":{"rain_mm":0.0,"tmax_hourly":16.0,"tmin_hourly":7.0},
            "2026-10-21":{"rain_mm":8.0,"tmax_hourly":15.0,"tmin_hourly":8.0}
        }}
        with tempfile.TemporaryDirectory() as folder:
            p=pathlib.Path(folder)
            for local,target,rain_fc in (("2026-10-19","2026-10-20",5.0),
                                         ("2026-10-20","2026-10-21",0.0)):
                (p/(local+".json")).write_text(json.dumps({
                    "collection_local_date":local,"target_tomorrow":target,
                    "days":{target:{"ecmwf":{"rain_mm":rain_fc,"tmax":15,"tmin":8}}}
                }))
            output=observe.evaluate(reference,p)
        score=output["models"]["ecmwf"]["rain"]
        self.assertEqual(score["n"],2)
        self.assertEqual(score["correct"],0)
        self.assertEqual(score["misses"],1)
        self.assertEqual(score["false_alarms"],1)
        self.assertEqual(score["mae_mm"],6.5)
        self.assertFalse(output["ranking_enabled"])

    def test_missing_rain_is_not_counted_as_dry(self):
        reference={"days":{"2026-10-20":{"rain_mm":None,"tmax_hourly":14.0,"tmin_hourly":6.0}}}
        with tempfile.TemporaryDirectory() as folder:
            p=pathlib.Path(folder)
            (p/"2026-10-19.json").write_text(json.dumps({
                "collection_local_date":"2026-10-19","target_tomorrow":"2026-10-20",
                "days":{"2026-10-20":{"ecmwf":{"rain_mm":0.0,"tmax":15.0,"tmin":6.0}}}
            }))
            output=observe.evaluate(reference,p)
        rain=output["models"]["ecmwf"]["rain"]
        self.assertEqual(rain["n"],0)
        self.assertIsNone(rain["mae_mm"])
        self.assertEqual(output["eligible_dates"],["2026-10-20"])

if __name__=="__main__":
    unittest.main()
