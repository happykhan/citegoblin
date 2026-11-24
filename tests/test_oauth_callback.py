from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import urlopen

from citegoblin.oauth_callback import run_callback


class CallbackPageTests(unittest.TestCase):
    def test_success_page_requires_matching_state_and_saved_credentials(self):
        for save_succeeds in (True, False):
            with self.subTest(save_succeeds=save_succeeds):
                self.check_callback(save_succeeds)

    def check_callback(self, save_succeeds):
        flow = Mock()
        flow.authorization_url.return_value = ('https://example.com/sign-in', 'expected')
        saved = Mock(return_value=flow.credentials)
        if not save_succeeds:
            saved.side_effect = ValueError('Could not save authorisation')

        def simulate_google():
            with self.assertRaises(HTTPError) as mismatch:
                urlopen(flow.redirect_uri + '?state=wrong&code=invalid', timeout=3).close()
            with mismatch.exception as response:
                self.assertEqual(response.code, 404)
            flow.fetch_token.assert_not_called()
            request = flow.redirect_uri + '?state=expected&code=synthetic'
            if save_succeeds:
                with urlopen(request, timeout=3) as response:
                    self.assertEqual(response.headers.get_content_type(), 'text/html')
                    self.assertEqual(response.headers['Cache-Control'], 'no-store')
                    body = response.read().decode()
                self.assertIn('Google sign-in complete', body)
                self.assertIn('return to your terminal', body)
                self.assertNotIn('synthetic', body)
            else:
                with self.assertRaises(HTTPError) as rejected:
                    urlopen(request, timeout=3).close()
                with rejected.exception as response:
                    self.assertEqual(response.code, 400)
                    self.assertNotIn(b'Google sign-in complete', response.read())

        with ThreadPoolExecutor(max_workers=1) as pool, redirect_stdout(StringIO()):
            pending = []
            with patch('citegoblin.oauth_callback.webbrowser.open',
                       side_effect=lambda *_args, **_kwargs: pending.append(pool.submit(simulate_google))):
                if save_succeeds:
                    self.assertIs(run_callback(flow, saved, timeout=5), flow.credentials)
                else:
                    with self.assertRaisesRegex(ValueError, 'Could not save'):
                        run_callback(flow, saved, timeout=5)
            pending[0].result(timeout=5)
        flow.fetch_token.assert_called_once_with(code='synthetic', timeout=30)
        saved.assert_called_once_with(flow.credentials)
