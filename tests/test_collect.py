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

    def test_four_models_and_dates(self):
        out=collect.build_capture(fetcher=self.mock_api,now=self.now)
        self.assertEqual(out['collection_local_date'],'2026-10-22')
        self.assertEqual(out['target_tomorrow'],'2026-10-23')
        self.assertEqual(set(out['days']['2026-10-23']),{'ecmwf','gfs','icon','aifs'})
        self.assertEqual(out['days']['2026-10-23']['icon']['rain_mm'],2.4)
        self.assertEqual(out['verification']['status'],'pending')
        self.assertEqual(out['sources']['aifs']['code'],'ecmwf_aifs025_single')
        self.assertIn('models=ecmwf_aifs025_single', collect.api_url('ecmwf_aifs025_single'))

    def test_failing_source_not_faked(self):
        def fail_gfs(code):
            if code=='ncep_gfs_global':raise ConnectionError('outage')
            return self.mock_api(code)
        out=collect.build_capture(fetcher=fail_gfs,now=self.now)
        self.assertNotIn('gfs',out['days']['2026-10-23'])
        self.assertIn('gfs',out['errors'])

    def test_experimental_aifs_outage_does_not_affect_original_sources(self):
        def fail_aifs(code):
            if code == 'ecmwf_aifs025_single': raise ConnectionError('not available')
            return self.mock_api(code)
        out=collect.build_capture(fetcher=fail_aifs,now=self.now)
        self.assertEqual(set(out['days']['2026-10-23']),{'ecmwf','gfs','icon'})
        self.assertIn('aifs',out['errors'])
        self.assertFalse(out['sources']['aifs']['available'])

    def test_aifs_alone_cannot_replace_main_forecasts(self):
        def only_aifs(code):
            if code != 'ecmwf_aifs025_single': raise ConnectionError('original model outage')
            return self.mock_api(code)
        with self.assertRaises(RuntimeError):
            collect.build_capture(fetcher=only_aifs,now=self.now)

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

class HourlyAndArchiveTests(unittest.TestCase):
    def setUp(self):
        self.now=dt.datetime(2026,10,22,12,23,tzinfo=dt.timezone.utc)
    def api(self, code):
        return {'daily': {'time':['2026-10-22','2026-10-23','2026-10-24'],
                          'temperature_2m_max':[20,21,22],'temperature_2m_min':[11,12,13],
                          'precipitation_sum':[0,2.4,0.8]},
                'hourly': {'time':['2026-10-23T00:00','2026-10-23T01:00','2026-10-23T02:00'],
                           'temperature_2m':[15.0,None,14.2]}}
    def test_hourly_converted_to_utc_and_gaps_not_filled(self):
        out=collect.build_capture(fetcher=self.api,now=self.now)
        series=out['hourly_temperature_c']['icon']
        self.assertEqual(series,{'2026-10-23T03:00Z':15.0,'2026-10-23T05:00Z':14.2})
    def test_missing_hourly_is_optional(self):
        def daily_only(code):
            data=self.api(code); del data['hourly']; return data
        out=collect.build_capture(fetcher=daily_only,now=self.now)
        self.assertEqual(out['hourly_temperature_c'],{})
        self.assertEqual(len(out['days']['2026-10-23']),4)
    def test_later_capture_fills_only_missing_models(self):
        def no_gfs(code):
            if code=='ncep_gfs_global':raise ConnectionError('ssl')
            return self.api(code)
        first=collect.build_capture(fetcher=no_gfs,now=self.now)
        first['days']['2026-10-23']['icon']['tmax']=99.0       # valor archivado original
        later=collect.build_capture(fetcher=self.api,now=self.now+dt.timedelta(hours=3))
        filled=collect.fill_archive(first,later)
        self.assertIn('gfs',filled['days']['2026-10-23'])
        self.assertEqual(filled['days']['2026-10-23']['icon']['tmax'],99.0)
        self.assertNotIn('gfs',filled['errors'])
        self.assertIn('gfs',filled['late_fills'])
        self.assertIsNone(collect.fill_archive(filled,later))
    def test_capture_from_other_day_never_fills(self):
        first=collect.build_capture(fetcher=self.api,now=self.now)
        del first['days']['2026-10-23']['gfs']
        nextday=collect.build_capture(fetcher=self.api,now=self.now+dt.timedelta(days=1))
        self.assertIsNone(collect.fill_archive(first,nextday))


class FixedIssueTimeTests(unittest.TestCase):
    """Hora fija de evaluación: 21:00 de Uruguay (00:00 UTC), ventana 15:00-24:00."""
    def api(self, code):
        return {'daily': {'time':['2026-10-22','2026-10-23','2026-10-24'],
                          'temperature_2m_max':[20,21,22],'temperature_2m_min':[11,12,13],
                          'precipitation_sum':[0,2.4,0.8]}}
    def capture(self, utc_hour, minute=23, fetcher=None, day=22):
        now=dt.datetime(2026,10,day,utc_hour,minute,tzinfo=dt.timezone.utc)
        return collect.build_capture(fetcher=fetcher or self.api,now=now)
    def test_issue_info(self):
        info=collect.issue_info('2026-10-23T00:23:00Z')       # 21:23 del 22/10
        self.assertEqual((info['issued_local'],info['in_window'],info['minutes_from_reference']),('21:23',True,23))
        self.assertFalse(collect.issue_info('2026-10-22T12:23:00Z')['in_window'])   # 09:23
    def test_closer_capture_replaces_morning_capture(self):
        morning=self.capture(12)                               # 09:23 local
        evening=self.capture(21)                               # 18:23 local
        chosen=collect.update_archive(morning,evening)
        self.assertEqual(chosen['collected_at_utc'],evening['collected_at_utc'])
        self.assertEqual(chosen['replaced_capture_utc'],morning['collected_at_utc'])
        night=collect.build_capture(fetcher=self.api,now=dt.datetime(2026,10,23,0,23,tzinfo=dt.timezone.utc))
        chosen2=collect.update_archive(chosen,night)           # 21:23 local, mismo día local
        self.assertEqual(chosen2['collected_at_utc'],night['collected_at_utc'])
    def test_farther_or_out_of_window_capture_never_replaces(self):
        at2123=collect.build_capture(fetcher=self.api,now=dt.datetime(2026,10,23,0,23,tzinfo=dt.timezone.utc))
        at1823=self.capture(21)
        self.assertIsNone(collect.update_archive(at2123,at1823))
        self.assertIsNone(collect.update_archive(self.capture(21),self.capture(12)))
    def test_replacement_keeps_models_only_old_capture_had(self):
        morning=self.capture(12)
        def no_ecmwf(code):
            if code=='ecmwf_ifs':raise ConnectionError('ssl')
            return self.api(code)
        evening=self.capture(21,fetcher=no_ecmwf)
        chosen=collect.update_archive(morning,evening)
        self.assertIn('ecmwf',chosen['days']['2026-10-23'])
        self.assertEqual(chosen['late_fills'],{'ecmwf':morning['collected_at_utc']})
        self.assertNotIn('ecmwf',chosen['errors'])
    def test_other_local_day_never_touches_archive(self):
        self.assertIsNone(collect.update_archive(self.capture(21),self.capture(21,day=23)))

if __name__=='__main__':unittest.main()
