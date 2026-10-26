import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
import inia

NOW=dt.datetime(2026,10,26,14,tzinfo=dt.timezone.utc)

def csv_example(delim=","):
    rows=[delim.join(("fecha","temperaturaMaximaCorregida","temperaturaMinimaCorregida","pluviometro"))]
    for n in range(1,8):
        rows.append(delim.join((f"2026-10-{n:02d}","21.5","10.2","0.0")))
    return "\n".join(rows)

class IniATests(unittest.TestCase):
    def test_valid_data_and_no_calendar_scores(self):
        data=inia.parse_csv(csv_example(),NOW)
        self.assertEqual(data["count_2026"],7)
        self.assertFalse(data["calendar_day_comparable"])
        self.assertFalse(data["scores_enabled"])
        self.assertEqual(data["latest_date"],"2026-10-07")
        self.assertEqual(data["days"]["2026-10-03"]["rain_mm"],0.0)

    def test_semicolon_bom_and_missing(self):
        content="\ufeff"+csv_example(";").replace("21.5;10.2;0.0",";10.2;")
        data=inia.parse_csv(content,NOW)
        self.assertIsNone(data["days"]["2026-10-07"]["rain_mm"])
        self.assertIsNone(data["days"]["2026-10-07"]["tmax_c"])

    def test_invalid_schema_never_published(self):
        with tempfile.TemporaryDirectory() as path:
            output=pathlib.Path(path)/"ina.json"
            output.write_text("original")
            result=inia.run(fetcher=lambda:"fecha,lluvia\n2026-10-07,0\n",now=NOW,output=output)
            self.assertIsNone(result)
            self.assertEqual(output.read_text(),"original")

    def test_conflicting_duplicate_is_excluded(self):
        contents=csv_example()+"\n2026-10-03,21.5,10.2,12\n"
        data=inia.parse_csv(contents,NOW)
        self.assertNotIn("2026-10-03",data["days"])

    def test_date_ignores_future_and_bad_values(self):
        content=csv_example()+"\n2026-12-03,19,10,4\n2026-10-08,20,11,nan\n2026-10-09,-500,20,0\n"
        data=inia.parse_csv(content,NOW)
        self.assertNotIn("2026-12-03",data["days"])
        self.assertIsNone(data["days"]["2026-10-08"]["rain_mm"])
        self.assertEqual(data["days"]["2026-10-09"]["tmax_c"],None)

    def test_stays_independent_of_spymovil(self):
        data=inia.parse_csv(csv_example(),NOW)
        self.assertNotIn("nivel_cm",data)
        self.assertNotIn("alarmas",data)

if __name__=="__main__":
    unittest.main()
