import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
import sync_weather_updates as sync

def lightning(when,flashes):
    return {"schema":1,"source":"NOAA GOES-19 GLM-L2-LCFA",
            "generated_at_utc":when,"flashes_150km":flashes}

def station(when,temp):
    return {"schema":1,"source":"INIA GRAS / La Estanzuela",
            "observed_at_utc":when,"temperature_c":temp,"observation":True}

class MergeWeatherTests(unittest.TestCase):
    def test_newer_replaces_and_older_does_not(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder)
            old,new=root/"old",root/"new";old.mkdir();new.mkdir()
            (old/"lightning.json").write_text(json.dumps(lightning("2026-10-30T17:30:00Z",20)))
            (new/"lightning.json").write_text(json.dumps(lightning("2026-10-30T17:20:00Z",7)))
            self.assertEqual(sync.merge(new,old),[])
            self.assertEqual(json.loads((old/"lightning.json").read_text())["flashes_150km"],20)
            (new/"lightning.json").write_text(json.dumps(lightning("2026-10-30T17:45:00Z",50)))
            self.assertEqual(sync.merge(new,old),["lightning.json"])
            self.assertEqual(json.loads((old/"lightning.json").read_text())["flashes_150km"],50)

    def test_station_uses_observation_timestamp_not_download_time(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);old,new=root/"old",root/"new"
            old.mkdir();new.mkdir()
            (old/"current_station.json").write_text(json.dumps(station("2026-10-30T17:05:00Z",18)))
            (new/"current_station.json").write_text(json.dumps(station("2026-10-30T17:02:00Z",16)))
            sync.merge(new,old)
            self.assertEqual(json.loads((old/"current_station.json").read_text())["temperature_c"],18)

    def test_invalid_data_cannot_replace(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);old,new=root/"old",root/"new"
            old.mkdir();new.mkdir()
            (old/"lightning.json").write_text(json.dumps(lightning("2026-10-30T17:20:00Z",20)))
            (new/"lightning.json").write_text(json.dumps({"schema":1,"source":"GOES-16","generated_at_utc":"2026-10-30T17:30:00Z"}))
            with self.assertRaises(ValueError):sync.merge(new,old)
            self.assertEqual(json.loads((old/"lightning.json").read_text())["flashes_150km"],20)

    def test_missing_temperature_is_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);old,new=root/"old",root/"new"
            old.mkdir();new.mkdir()
            self.assertEqual(sync.merge(new,old),[])
            self.assertFalse((old/"current_station.json").exists())

if __name__=="__main__":unittest.main()
