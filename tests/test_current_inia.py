import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
import current_inia

NOW=dt.datetime(2026,10,29,17,40,tzinfo=dt.timezone.utc)

def page(inia=9.2,colonia=19.0,when="2026-10-29T13:00:00-03:00",
         include_inia=True, include_colonia=True,field=47):
    stations=[
        {"id":594 if include_colonia else 599,
         "Estacion":"U560","NombreEstacion":"Colonia G3"},
        {"id":584 if include_inia else 599,
         "Estacion":"EMA_INIA_LaEstanzuela",
         "NombreEstacion":"INIA La Estanzuela (Automática)"}
    ]
    payload={
       "estaciones":stations,
       "variables":[{"idInt":29,"variable":"IntViento"},
                    {"idInt":field,"variable":"TempAire"}],
       "fechas":[when],
       "observaciones":[{"iFechas":[0],"datos":[[2],[1]]},
                        {"iFechas":[0],"datos":[[colonia],[inia]]}]}
    return '<html><script>var estadoActual = '+json.dumps(payload)+'; var estaciones = {};</script></html>'

class CurrentStationTests(unittest.TestCase):
    def test_prefer_estanzuela_when_available(self):
        d=current_inia.parse(page(),NOW)
        self.assertEqual(d["temperature_c"],9.2)
        self.assertEqual(d["station_id"],584)
        self.assertEqual(d["observed_at_utc"],"2026-10-29T16:00:00Z")
        self.assertTrue(d["observation"])

    def test_colonia_fallback_for_missing_inia(self):
        d=current_inia.parse(page(inia=None),NOW)
        self.assertEqual(d["temperature_c"],19.0)
        self.assertEqual(d["station_id"],594)
        self.assertEqual(d["station_name"],"Colonia G3")
        self.assertEqual(d["source"],"INUMET / Colonia G3")
        self.assertNotIn("Estanzuela",d["source"])

    def test_colonia_fallback_for_outlying_inia(self):
        d=current_inia.parse(page(inia=500),NOW)
        self.assertEqual(d["station_id"],594)

    def test_reject_unverified_station_variable_or_no_temperature(self):
        for html in (
            page(include_inia=False,include_colonia=False),
            page(field=18),
            page(inia=None,colonia=None),
            '<html></html>',
        ):
            with self.assertRaises(ValueError):current_inia.parse(html,NOW)

    def test_reject_old_and_future_values(self):
        for when in ("2026-10-29T10:00:00-03:00",
                     "2026-10-29T17:00:00-03:00"):
            with self.assertRaises(ValueError):current_inia.parse(page(when=when),NOW)

    def test_nan_and_outliers_not_published(self):
        for val in (float("nan"),None,500,True):
            with self.assertRaises(ValueError):current_inia.parse(page(inia=val,colonia=val),NOW)

    def test_failed_read_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)/"current.json"
            path.write_text("known_good")
            record=current_inia.run(get_html=lambda:page(inia=None,colonia=None),
                                    now=NOW,output=path)
            self.assertIsNone(record)
            self.assertEqual(path.read_text(),"known_good")

    def test_fallback_written_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)/"current.json"
            record=current_inia.run(get_html=lambda:page(inia=None),
                                    now=NOW,output=path)
            self.assertEqual(record["temperature_c"],19.0)
            self.assertEqual(json.loads(path.read_text())["station_id"],594)


def sample_xml(temp="16.2", when="30/10/2026 13:02:50", unit="°C", station="INIA_LE"):
    return (f'<webdata><stations><station name="{station}"><fields>'
            f'<field><name>TimeStampString</name><value>{when}</value><units></units></field>'
            f'<field><name>Air Temperature</name><value>{temp}</value>'
            f'<units>{unit}</units></field></fields></station></stations></webdata>').encode("utf-8")

class DirectINIAReadTests(unittest.TestCase):
    def setUp(self):
        self.now=dt.datetime(2026,10,30,16,19,tzinfo=dt.timezone.utc)

    def test_direct_source_and_local_timestamp(self):
        record=current_inia.parse_direct_xml(sample_xml(),self.now)
        self.assertEqual(record["station_id"],584)
        self.assertEqual(record["source"],"INIA GRAS / La Estanzuela")
        self.assertEqual(record["temperature_c"],16.2)
        self.assertEqual(record["observed_at_utc"],"2026-10-30T16:02:50Z")

    def test_reject_bad_source_timestamp_and_values(self):
        for sample in (sample_xml(when="30/10/2026 09:00:00"),
                       sample_xml(when="31/10/2026 09:00:00"),
                       sample_xml(temp="nan"),sample_xml(temp="-500"),
                       sample_xml(unit="F"),sample_xml(station="not_INIA_LE"),
                       b"<html>Not meteorological XML</html>"):
            with self.assertRaises(ValueError):
                current_inia.parse_direct_xml(sample,self.now)

    def test_direct_preferred_and_fallback_to_existing_colonia(self):
        with tempfile.TemporaryDirectory() as folder:
            output=pathlib.Path(folder)/"current.json"
            fallback=lambda:page(inia=None,colonia=17,when="2026-10-30T13:00:00-03:00")
            first=current_inia.run(get_html=fallback,get_direct_xml=lambda:sample_xml(),
                                  output=output,now=self.now)
            self.assertEqual(first["temperature_c"],16.2)
            self.assertEqual(first["source"],"INIA GRAS / La Estanzuela")
            second=current_inia.run(get_html=fallback,get_direct_xml=lambda:sample_xml(temp="nan"),
                                   output=output,now=self.now)
            self.assertEqual(second["station_id"],594)
            self.assertEqual(second["temperature_c"],17.0)

if __name__=="__main__":unittest.main()
