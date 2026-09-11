import io
import json
import unittest
from unittest.mock import patch
import ductool_license as license

HWID = 'DUC-1111-2222-3333'
URL = 'https://script.google.com/macros/s/test-deployment/exec'


class LicenseTests(unittest.TestCase):
    def test_activation_posts_key_and_hwid_and_requires_binding(self):
        result = {'status':'ACTIVE', 'key':'TEST', 'hwid':HWID, 'hwid_bound':True, 'expire_date':'2099-12-31'}
        with patch.object(license, 'get_license_url', return_value=URL), \
             patch.object(license.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(result).encode())) as request, \
             patch.object(license, 'save_license_key') as save_key, patch.object(license, 'save_license_cache') as save_cache:
            self.assertEqual(license.check_license_online(HWID, 'test', activate=True)['status'], 'ACTIVE')
            req = request.call_args.args[0]
            self.assertEqual(req.method, 'POST')
            self.assertEqual(json.loads(req.data), {'action':'activate','key':'TEST','hwid':HWID})
            self.assertNotIn('TEST', req.full_url)
            save_key.assert_called_once_with('TEST')
            save_cache.assert_called_once_with(HWID, 'TEST', '2099-12-31')

    def test_unbound_or_other_machine_response_never_cached(self):
        for extra in ({}, {'hwid_bound':True,'hwid':'DUC-AAAA-BBBB-CCCC'}, {'hwid_bound':True,'hwid':HWID,'key':'WRONG'}):
            result = {'status':'ACTIVE','key':'TEST','expire_date':'2099-12-31', **extra}
            with patch.object(license, 'get_license_url', return_value=URL), \
                 patch.object(license.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(result).encode())), \
                 patch.object(license, 'save_license_cache') as save:
                self.assertEqual(license.check_license_online(HWID, 'test')['status'], 'ERROR')
                save.assert_not_called()

    def test_sheet_keys_and_manual_machine_binding(self):
        import csv
        for assigned, state, expiry, key, expected in [
            ('', 'ACTIVE', '2099-12-31', 'test', 'ACTIVE'),
            (HWID, 'ACTIVE', '2099-12-31', 'test', 'ACTIVE'),
            ('DUC-AAAA-BBBB-CCCC', 'ACTIVE', '2099-12-31', 'test', 'HWID_MISMATCH'),
            ('', 'BLOCKED', '2099-12-31', 'test', 'BLOCKED'),
            ('', 'ACTIVE', '2000-01-01', 'test', 'EXPIRED'),
            (HWID, 'ACTIVE', '2099-12-31', 'wrong', 'NOT_FOUND'),
        ]:
            text = io.StringIO()
            writer = csv.writer(text)
            writer.writerow(['Tên Khách Hàng','Mã Key','Ngày Hết Hạn','Trạng Thái','Ghi Chú','Mã Máy (HWID)'])
            writer.writerow(['Test', 'TEST', expiry, state, 'wrong', assigned])
            response = io.BytesIO(text.getvalue().encode('utf-8-sig'))
            response.headers = {}
            with patch.object(license, 'get_license_url', return_value=license.DEFAULT_LICENSE_URL), \
                 patch.object(license.urllib.request, 'urlopen', return_value=response), \
                 patch.object(license, 'save_license_key'), patch.object(license, 'save_license_cache') as cache:
                result = license.check_license_online(HWID, key, activate=True)
                self.assertEqual(result['status'], expected)
                if expected == 'ACTIVE':
                    self.assertEqual(result['hwid_bound'], bool(assigned))
                    self.assertEqual(cache.call_args.kwargs['hwid_bound'], bool(assigned))
                else:
                    cache.assert_not_called()

    def test_activation_network_failure_does_not_use_old_cache(self):
        with patch.object(license, 'get_license_url', return_value=URL), \
             patch.object(license.urllib.request, 'urlopen', side_effect=OSError('offline')), \
             patch.object(license, 'get_cached_license') as cache:
            self.assertEqual(license.check_license_online(HWID,'test',activate=True)['status'], 'NETWORK_ERROR')
            cache.assert_not_called()


if __name__ == '__main__':
    unittest.main()
