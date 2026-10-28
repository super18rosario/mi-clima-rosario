import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
import current_inia

NOW=dt.datetime(2026,10,28,9,20,tzinfo=dt.timezone.utc)
def page(temp=9.2,when="2026-10-28T06:00:00.000-03:00",station_id=584,field=47):
    payload={"estaciones":[
                 {"id":594,"Estacion":"U560"},
                 {"id":station_id,"Estacion":"EMA_INIA_LaEstanzuela"}],
             "variables":[{"idInt":29,"variable":"IntViento"},
                          {"idInt":field,"variable":"TempAire"}],
             "fechas":[when],
             "observaciones":[{"iFechas":[0],"datos":[[[2]],[[1]]]},
                             {"iFechas":[0],"datos":[[[12.3]],[[temp]]]}]}
    return '<html><script>var estadoActual = '+json.dumps(payload)+'; var estaciones = {};</script></html>'

class CurrentINIA(unittest.TestCase):
    def test_live_measurement_is_observation_and_attributed(self):
        result=current_inia.parse(page(),NOW)
        self.assertEqual(result["temperature_c"],9.2)
        self.assertEqual(result["observed_at_utc"],"2026-10-28T09:00:00Z")
        self.assertEqual(result["station_id"],584)
        self.assertTrue(result["observation"])
        self.assertIn("INUMET",result["source"])

    def test_wrong_station_or_variable_rejected(self):
        for html in [page(station_id=599),page(field=18),"<html></html>"]:
            with self.assertRaises(ValueError):current_inia.parse(html,NOW)

    def test_old_and_future_values_rejected(self):
        for when in ("2026-10-28T03:00:00-03:00","2026-10-28T10:00:00-03:00"):
            with self.assertRaises(ValueError):current_inia.parse(page(when=when),NOW)

    def test_missing_outlying_and_nan_rejected(self):
        for value in (None,500,float("nan"),True):
            with self.assertRaises((ValueError,TypeError)):
                current_inia.parse(page(temp=value),NOW)

    def test_failed_read_never_replaces_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)/"current.json"
            path.write_text("known_good")
            record=current_inia.run(get_html=lambda:page(when="2026-10-27T07:00:00-03:00"),now=NOW,output=path)
            self.assertIsNone(record)
            self.assertEqual(path.read_text(),"known_good")

    def test_good_data_written_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)/"current.json"
            result=current_inia.run(get_html=lambda:page(),now=NOW,output=path)
            self.assertEqual(json.loads(path.read_text())["temperature_c"],9.2)
            self.assertEqual(result["observed_at_utc"],"2026-10-28T09:00:00Z")

if __name__=="__main__":unittest.main()
