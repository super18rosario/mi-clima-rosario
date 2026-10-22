import datetime as dt
import pathlib
import sys
import unittest
from unittest.mock import patch
import urllib.error
import io
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import collect

class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.now=dt.datetime(2026,10,22,12,23,tzinfo=dt.timezone.utc)

    def mock_api(self, code):
        return {'daily': {
            'time':['2026-10-22','2026-10-23','2026-10-24'],
            'temperature_2m_max':[20,21,22],
            'temperature_2m_min':[11,12,13],
            'precipitation_sum':[0,2.4,0.8]}}

    def test_three_models_and_dates(self):
        out=collect.build_capture(fetcher=self.mock_api,now=self.now)
        self.assertEqual(out['collection_local_date'],'2026-10-22')
        self.assertEqual(out['target_tomorrow'],'2026-10-23')
        self.assertEqual(set(out['days']['2026-10-23']),{'ecmwf','gfs','icon'})
        self.assertEqual(out['days']['2026-10-23']['icon']['rain_mm'],2.4)
        self.assertEqual(out['verification']['status'],'pending')

    def test_failing_source_not_faked(self):
        def fail_gfs(code):
            if code=='ncep_gfs_global':raise ConnectionError('outage')
            return self.mock_api(code)
        out=collect.build_capture(fetcher=fail_gfs,now=self.now)
        self.assertNotIn('gfs',out['days']['2026-10-23'])
        self.assertIn('gfs',out['errors'])

    def test_total_outage_preserves_stored_data(self):
        def fail(code):raise ConnectionError('off')
        with self.assertRaises(RuntimeError):collect.build_capture(fetcher=fail,now=self.now)

    def test_invalid_data_rejected(self):
        with self.assertRaises(ValueError):collect.parse_daily({'daily':{'time':['2026-10-23'],'temperature_2m_max':[20]}})
        self.assertIsNone(collect.safe_number(float('nan'),-70,65))

    def test_dates_uruguay_not_utc(self):
        before_midnight=dt.datetime(2026,10,23,1,0,tzinfo=dt.timezone.utc)
        out=collect.build_capture(fetcher=self.mock_api,now=before_midnight)
        self.assertEqual(out['collection_local_date'],'2026-10-22')

class ApiRetryTests(unittest.TestCase):
    def test_retry_after_temporary_network_failure(self):
        payload=b'{"daily":{"time":["2026-10-22"],"temperature_2m_max":[20],"temperature_2m_min":[10],"precipitation_sum":[0]}}'
        class Response:
            def __enter__(self): return io.BytesIO(payload)
            def __exit__(self,*args): return False
        state={'calls':0}
        def fake_fetch(*args,**kwargs):
            state['calls']+=1
            if state['calls']==1: raise urllib.error.URLError('fallo temporal')
            return Response()
        with patch.object(collect.urllib.request,'urlopen',side_effect=fake_fetch), patch.object(collect.time,'sleep') as sleeper:
            out=collect.fetch_model('icon_global')
        self.assertIn('daily',out)
        self.assertEqual(state['calls'],2)
        sleeper.assert_called_once_with(1)

    def test_permanent_http_error_not_retried(self):
        request_error=urllib.error.HTTPError('https://example.org',400,'bad request',{},None)
        with patch.object(collect.urllib.request,'urlopen',side_effect=request_error) as fake, patch.object(collect.time,'sleep') as sleeper:
            with self.assertRaises(urllib.error.HTTPError):collect.fetch_model('icon_global')
        fake.assert_called_once()
        sleeper.assert_not_called()

if __name__=='__main__':unittest.main()
