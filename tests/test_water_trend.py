import datetime as dt
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
from water_trend import visible_cm,trend

T=dt.datetime(2026,10,25,18,tzinfo=dt.timezone.utc)
class WaterTrendTests(unittest.TestCase):
    def test_tolerance_and_exact_raw(self):
        self.assertEqual([visible_cm(x) for x in (1.56,2.24,5,5.01)],[0,0,0,5.01])
        original=[{"at":T,"cm":2.24}]
        self.assertEqual(trend(original)["altura_original_cm"],2.24)
        self.assertEqual(original[0]["cm"],2.24)
    def test_rise_rate(self):
        result=trend([{"at":T,"cm":20},{"at":T+dt.timedelta(minutes=15),"cm":25},{"at":T+dt.timedelta(minutes=30),"cm":30}])
        self.assertEqual(result["status"],"subiendo")
        self.assertEqual(result["velocidad_cm_h"],20)
    def test_decrease(self):
        result=trend([{"at":T,"cm":50},{"at":T+dt.timedelta(minutes=30),"cm":35}])
        self.assertEqual(result["velocidad_cm_h"],-30)
    def test_tolerance_noise(self):
        result=trend([{"at":T,"cm":1.56},{"at":T+dt.timedelta(minutes=30),"cm":2.24}])
        self.assertEqual(result["status"],"sin_cambio")
    def test_long_gap_no_velocity(self):
        result=trend([{"at":T,"cm":1},{"at":T+dt.timedelta(hours=4),"cm":40}])
        self.assertIsNone(result["velocidad_cm_h"])
    def test_no_alarm_side_effect(self):
        result=trend([{"at":T,"cm":70},{"at":T+dt.timedelta(minutes=30),"cm":100}])
        self.assertNotIn("corte",result)
        self.assertNotIn("alarma",result)
    def test_invalid(self):
        for raw in [-1,float("nan"),True,None]:
            with self.assertRaises((ValueError,TypeError)):visible_cm(raw)
    def test_time_zone_required(self):
        with self.assertRaises(ValueError):
            trend([{"at":dt.datetime(2026,10,25,19),"cm":10}])
if __name__=="__main__":unittest.main()
