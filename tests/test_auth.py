import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from citegoblin import auth

CLIENT={'installed':{'client_id':'synthetic-client','client_secret':'synthetic-secret',
        'auth_uri':'https://accounts.google.com/o/oauth2/auth','token_uri':'https://oauth2.googleapis.com/token'}}


class AuthTests(unittest.TestCase):
    def test_no_api_key_or_service_account_accepted_as_desktop_client(self):
        self.assertEqual(auth.validate_client(CLIENT),CLIENT)
        for bad in [{'api_key':'not-oauth'},{'web':CLIENT['installed']},{'type':'service_account'}]:
            with self.assertRaisesRegex(ValueError,'Desktop app'):auth.validate_client(bad)
        wrong=json.loads(json.dumps(CLIENT));wrong['installed']['token_uri']='https://example.org/token'
        with self.assertRaises(ValueError):auth.validate_client(wrong)

    def test_file_tokens_are_private_and_replaced_atomically(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'token.json';store=auth.TokenStore(path)
            self.assertIsNone(store.load())
            store.save('synthetic-first-token');self.assertEqual(store.load(),'synthetic-first-token')
            store.save('synthetic-second-token');self.assertEqual(store.load(),'synthetic-second-token')
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            self.assertEqual(len(list(Path(root).iterdir())),1)
            store.delete();self.assertFalse(path.exists())

    def test_first_login_opens_loopback_pkce_and_saves_without_printing_token(self):
        store=MagicMock();credential=MagicMock()
        credential.granted_scopes=list(auth.SCOPES);credential.refresh_token='synthetic-refresh';credential.to_json.return_value='synthetic-token-json'
        with patch.object(auth,'client_config',return_value=CLIENT),patch.object(auth,'remember_storage'),\
                patch('google_auth_oauthlib.flow.InstalledAppFlow') as installed:
            flow=installed.from_client_config.return_value;flow.run_local_server.return_value=credential
            self.assertIs(auth.sign_in(store),credential)
            self.assertTrue(installed.from_client_config.call_args.kwargs['autogenerate_code_verifier'])
            options=flow.run_local_server.call_args.kwargs
            self.assertEqual(options['host'],'127.0.0.1');self.assertEqual(options['port'],0)
            self.assertTrue(options['open_browser']);self.assertEqual(options['access_type'],'offline')
            store.save.assert_called_once_with('synthetic-token-json')

    def test_noninteractive_run_does_not_launch_browser(self):
        with patch.object(auth,'client_config') as config:
            with self.assertRaisesRegex(ValueError,'interactive terminal'):auth.sign_in(MagicMock(),interactive=False)
            config.assert_not_called()

    def test_partial_consent_not_saved(self):
        store=MagicMock();credential=MagicMock();credential.granted_scopes=[auth.SCOPES[0]]
        with patch.object(auth,'client_config',return_value=CLIENT),patch('google_auth_oauthlib.flow.InstalledAppFlow') as installed:
            installed.from_client_config.return_value.run_local_server.return_value=credential
            with self.assertRaisesRegex(ValueError,'permissions'):auth.sign_in(store)
        store.save.assert_not_called()

    def test_missing_tokens_trigger_first_run_sign_in(self):
        store=MagicMock();store.load.return_value=None
        with patch.dict('os.environ',{},clear=True),patch.object(auth,'token_store',return_value=store),patch.object(auth,'sign_in',return_value='signed-in') as login:
            self.assertEqual(auth.credentials(interactive=True),'signed-in')
            login.assert_called_once_with(store,interactive=True)

    def test_valid_saved_credentials_do_not_prompt(self):
        store=MagicMock();store.load.return_value='{}';credential=MagicMock();credential.valid=True
        with patch.dict('os.environ',{},clear=True),patch.object(auth,'token_store',return_value=store),\
                patch('google.oauth2.credentials.Credentials.from_authorized_user_info',return_value=credential),\
                patch.object(auth,'sign_in') as login:
            self.assertIs(auth.credentials(interactive=False),credential)
            login.assert_not_called();credential.refresh.assert_not_called()

    def test_expired_token_refreshes_and_is_saved(self):
        store=MagicMock();store.load.return_value='{}';credential=MagicMock();credential.valid=False;credential.to_json.return_value='refreshed'
        with patch.dict('os.environ',{},clear=True),patch.object(auth,'token_store',return_value=store),\
                patch('google.oauth2.credentials.Credentials.from_authorized_user_info',return_value=credential),\
                patch.object(auth,'sign_in') as login:
            self.assertIs(auth.credentials(interactive=False),credential)
            credential.refresh.assert_called_once();store.save.assert_called_once_with('refreshed');login.assert_not_called()

    def test_revoked_token_requires_login_but_transient_failure_does_not(self):
        from google.auth.exceptions import RefreshError, TransportError
        for failure,should_login in [(RefreshError('revoked'),True),(RefreshError('unavailable',retryable=True),False),(TransportError('offline'),False)]:
            store=MagicMock();store.load.return_value='{}';credential=MagicMock();credential.valid=False;credential.refresh.side_effect=failure
            with patch.dict('os.environ',{},clear=True),patch.object(auth,'token_store',return_value=store),\
                    patch('google.oauth2.credentials.Credentials.from_authorized_user_info',return_value=credential),\
                    patch.object(auth,'sign_in',return_value='new-login') as login:
                if should_login:
                    self.assertEqual(auth.credentials(interactive=True),'new-login');login.assert_called_once()
                else:
                    with self.assertRaises(ValueError):auth.credentials(interactive=True)
                    login.assert_not_called()

    def test_status_never_returns_tokens(self):
        store=MagicMock();store.path=None;store.load.return_value=json.dumps({'token':'secret','refresh_token':'secret','client_secret':'secret','scopes':list(auth.SCOPES),'expiry':'2030'})
        with patch.object(auth,'token_store',return_value=store):
            result=auth.status()
        self.assertTrue(result['signedIn']);self.assertNotIn('secret',json.dumps(result))

    def test_keychain_does_not_silently_fall_back_to_plaintext(self):
        backend=MagicMock();backend.__class__=type('Plain',(),{'__module__':'keyrings.alt.file'})
        with patch('keyring.get_keyring',return_value=backend):
            with self.assertRaisesRegex(ValueError,'keychain'):auth.TokenStore().load()


if __name__=='__main__':unittest.main()
