import datetime as dt
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
import lightning

NOW=dt.datetime(2026,10,25,12,32,tzinfo=dt.timezone.utc)
def filename(t):
    return f"GLM-L2-LCFA/2026/298/12/OR_GLM-L2-LCFA_G19_s{t.strftime('%Y%j%H%M%S')}0_e000_c000.nc"

class LightningTests(unittest.TestCase):
    def test_coordinates_and_distance(self):
        self.assertLess(lightning.distance_km(-34.312,-57.351),0.001)
        self.assertGreater(lightning.distance_km(-34.312,-55),200)

    def test_select_latest_ten_minutes(self):
        keys=[filename(NOW-dt.timedelta(seconds=20*i)) for i in range(50)]
        selected,last=lightning.choose_recent(keys,NOW)
        self.assertEqual(len(selected),31)
        self.assertEqual(last,NOW)

    def test_good_fresh_observations(self):
        keys=[filename(NOW-dt.timedelta(seconds=20*i)) for i in range(29)]
        result=lightning.build_summary(keys,NOW,reader=lambda k:[10,100])
        self.assertEqual(result["status"],"ok")
        self.assertEqual(result["flashes_50km"],29)
        self.assertEqual(result["flashes_150km"],58)

    def test_insufficient_cannot_claim_no_lightning(self):
        keys=[filename(NOW-dt.timedelta(seconds=20*i)) for i in range(6)]
        result=lightning.build_summary(keys,NOW,reader=lambda k:[])
        self.assertEqual(result["status"],"partial")

    def test_stale_observations_are_marked(self):
        keys=[filename(NOW-dt.timedelta(minutes=70,seconds=20*i)) for i in range(30)]
        result=lightning.build_summary(keys,NOW,reader=lambda k:[])
        self.assertEqual(result["status"],"stale")

    def test_missing_data_are_unknown(self):
        result=lightning.build_summary([],NOW)
        self.assertEqual(result["status"],"unavailable")
        self.assertIsNone(result["flashes_150km"])

if __name__=="__main__":unittest.main()
