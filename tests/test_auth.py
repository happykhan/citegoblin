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
            self.assertEqual(options['trigger_onepick'],'true');self.assertEqual(options['include_granted_scopes'],'false')
            store.save.assert_called_once_with('synthetic-token-json')

    def test_noninteractive_run_does_not_launch_browser(self):
        with patch.object(auth,'client_config') as config:
            with self.assertRaisesRegex(ValueError,'interactive terminal'):auth.sign_in(MagicMock(),interactive=False)
            config.assert_not_called()

    def test_partial_consent_not_saved(self):
        store=MagicMock();credential=MagicMock();credential.granted_scopes=[]
        with patch.object(auth,'client_config',return_value=CLIENT),patch('google_auth_oauthlib.flow.InstalledAppFlow') as installed:
            installed.from_client_config.return_value.run_local_server.return_value=credential
            with self.assertRaisesRegex(ValueError,'permission'):auth.sign_in(store)
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

class PerFileAuthTests(unittest.TestCase):
    def test_only_drive_file_is_requested(self):
        self.assertEqual(auth.SCOPES,('https://www.googleapis.com/auth/drive.file',))

    def test_targeted_picker_uses_document_filter_and_excludes_old_grants(self):
        store=MagicMock();credential=MagicMock();credential.granted_scopes=list(auth.SCOPES);credential.refresh_token='synthetic';credential.to_json.return_value='{}'
        with patch.object(auth,'client_config',return_value=CLIENT),patch.object(auth,'remember_storage'),patch('google_auth_oauthlib.flow.InstalledAppFlow')as installed:
            installed.from_client_config.return_value.run_local_server.return_value=credential
            auth.sign_in(store,document_id='example-document-id')
            options=installed.from_client_config.return_value.run_local_server.call_args.kwargs
            self.assertEqual(options['file_ids'],'example-document-id');self.assertEqual(options['allow_multiple'],'false')
            self.assertEqual(options['mimetypes'],'application/vnd.google-apps.document');self.assertEqual(options['include_granted_scopes'],'false')

    def test_broader_granted_token_is_not_saved(self):
        store=MagicMock();credential=MagicMock();credential.granted_scopes=[*auth.SCOPES,'https://www.googleapis.com/auth/drive']
        with patch.object(auth,'client_config',return_value=CLIENT),patch('google_auth_oauthlib.flow.InstalledAppFlow')as installed:
            installed.from_client_config.return_value.run_local_server.return_value=credential
            with self.assertRaisesRegex(ValueError,'only the per-file'):auth.sign_in(store)
        store.save.assert_not_called()

    def test_existing_broad_grant_is_revoked_without_logging_its_token(self):
        store=MagicMock();store.load.return_value=json.dumps({'scopes':['https://www.googleapis.com/auth/drive'],'refresh_token':'synthetic-private-refresh'})
        with patch('requests.post')as request:
            request.return_value.ok=True;auth.revoke_saved_broad_grant(store)
            self.assertEqual(request.call_args.args[0],'https://oauth2.googleapis.com/revoke')
            self.assertEqual(request.call_args.kwargs['data'],{'token':'synthetic-private-refresh'})
            store.delete.assert_called_once()

    def test_per_file_grants_are_not_revoked_when_connecting_another_file(self):
        store=MagicMock();store.load.return_value=json.dumps({'scopes':list(auth.SCOPES),'refresh_token':'synthetic'})
        with patch('requests.post')as request:auth.revoke_saved_broad_grant(store)
        request.assert_not_called();store.delete.assert_not_called()

    def test_failed_revocation_preserves_the_old_local_token(self):
        store=MagicMock();store.load.return_value=json.dumps({'scopes':['https://www.googleapis.com/auth/drive'],'refresh_token':'synthetic-private-refresh'})
        with patch('requests.post')as request:
            request.return_value.ok=False
            with self.assertRaisesRegex(ValueError,'could not revoke'):auth.revoke_saved_broad_grant(store)
        store.delete.assert_not_called()

    def test_cached_scope_superset_requires_new_consent(self):
        store=MagicMock();store.load.return_value=json.dumps({'scopes':[*auth.SCOPES,'https://www.googleapis.com/auth/documents']})
        credential=MagicMock();credential.valid=True
        with patch.dict('os.environ',{},clear=True),patch.object(auth,'token_store',return_value=store),patch('google.oauth2.credentials.Credentials.from_authorized_user_info',return_value=credential),patch.object(auth,'sign_in',return_value='new-minimal-token')as login:
            self.assertEqual(auth.credentials(interactive=False),'new-minimal-token');login.assert_called_once()

    def test_connect_checks_read_access_to_the_requested_document(self):
        from test_manager import fixture
        client=MagicMock();client.document.return_value=fixture()
        with patch.object(auth,'sign_in')as signin,patch.object(auth,'token_store'),patch('citegoblin.google.Google',return_value=client):
            result=auth.connect_document('https://docs.google.com/document/d/example-document-id/edit?tab=t.test')
        signin.assert_called_once();self.assertEqual(signin.call_args.kwargs['document_id'],'example-document-id')
        client.document.assert_called_once_with('example-document-id');self.assertTrue(result['connected'])


if __name__=='__main__':unittest.main()
