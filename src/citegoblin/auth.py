"""Desktop Google OAuth with a first-run browser sign-in and local token storage."""
import json
import os
from pathlib import Path
import sys
import tempfile

SCOPES = ('https://www.googleapis.com/auth/documents', 'https://www.googleapis.com/auth/drive')
KEYRING_SERVICE = 'CiteGoblin Google OAuth'
KEYRING_ACCOUNT = 'default'


def config_dir():
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/CiteGoblin'
    if sys.platform == 'win32':
        return Path(os.environ.get('APPDATA', Path.home() / 'AppData/Roaming')) / 'CiteGoblin'
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'citegoblin'


def private_write(path, value):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    handle, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(handle, 'w') as stream:
            stream.write(value)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_client(config):
    client = config.get('installed', {})
    if not client.get('client_id') or not client.get('client_secret'):
        raise ValueError('Use Google OAuth client JSON for a Desktop app, not an API key or service-account file')
    if client.get('auth_uri') != 'https://accounts.google.com/o/oauth2/auth' or client.get('token_uri') != 'https://oauth2.googleapis.com/token':
        raise ValueError('OAuth client must use the standard Google sign-in and token endpoints')
    return config


def install_client(path):
    config = validate_client(json.loads(Path(path).expanduser().read_text()))
    private_write(config_dir() / 'oauth-client.json', json.dumps(config))


def client_config():
    path = Path(os.environ.get('CITEGOBLIN_CLIENT_CONFIG', config_dir() / 'oauth-client.json')).expanduser()
    if not path.exists():
        raise ValueError('Google sign-in needs a Desktop OAuth client configured once. Run: '
                         'citegoblin login --client-secrets /path/to/downloaded-client.json (see README Setup)')
    return validate_client(json.loads(path.read_text()))


class TokenStore:
    """OS keychain by default. Plain file storage requires an explicit choice."""
    def __init__(self, token_file=None):
        self.path = Path(token_file).expanduser() if token_file else None

    def _keyring(self):
        try:
            import keyring
            backend = keyring.get_keyring()
            # Select an OS backend explicitly, never a plaintext fallback in a chain.
            candidates = backend.backends if backend.__class__.__module__ == 'keyring.backends.chainer' else [backend]
            for candidate in candidates:
                if candidate.__class__.__module__.startswith(('keyring.backends.macOS', 'keyring.backends.Windows',
                                                             'keyring.backends.SecretService', 'keyring.backends.kwallet')):
                    return candidate
            raise ValueError('OS keychain unavailable; explicitly choose login --token-file /private/path/token.json')
        except (ImportError, RuntimeError) as error:
            raise ValueError('OS keychain unavailable; install citegoblin[google] or explicitly use '
                             'citegoblin login --token-file /private/path/token.json') from error

    def load(self):
        if self.path:
            return self.path.read_text() if self.path.exists() else None
        try:
            return self._keyring().get_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
        except ValueError:
            raise
        except Exception as error:
            raise ValueError('Could not read the OS keychain; unlock it or use login --token-file') from error

    def save(self, raw):
        if self.path:
            private_write(self.path, raw)
            return
        try:
            self._keyring().set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, raw)
        except Exception as error:
            raise ValueError('Could not save authorisation in the OS keychain; unlock it or use login --token-file') from error

    def delete(self):
        if self.path:
            self.path.unlink(missing_ok=True)
        elif self.load() is not None:
            try:
                self._keyring().delete_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
            except Exception as error:
                raise ValueError('Could not remove authorisation from the OS keychain') from error


def token_store(token_file=None):
    chosen = token_file or os.environ.get('CITEGOBLIN_TOKEN_FILE')
    if not chosen:
        settings = config_dir() / 'auth-settings.json'
        if settings.exists():
            chosen = json.loads(settings.read_text()).get('tokenFile')
    return TokenStore(chosen)


def remember_storage(store):
    private_write(config_dir() / 'auth-settings.json', json.dumps({'tokenFile':str(store.path.resolve()) if store.path else None}))


def sign_in(store, *, interactive=True):
    if not interactive:
        raise ValueError('Google sign-in is required. Run citegoblin login in an interactive terminal first')
    config = client_config()
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as error:
        raise ValueError('Install citegoblin[google] to enable Google sign-in') from error
    try:
        flow = InstalledAppFlow.from_client_config(config, scopes=list(SCOPES), autogenerate_code_verifier=True)
        credentials = flow.run_local_server(host='127.0.0.1', port=0, open_browser=True,
            timeout_seconds=180, prompt='consent select_account', access_type='offline',
            authorization_prompt_message='Sign in to Google in your browser: {url}',
            success_message='CiteGoblin is authorised. You can close this tab and return to your terminal.')
    except Exception as error:
        raise ValueError('Google sign-in did not complete. Run citegoblin login to try again') from error
    granted = credentials.granted_scopes
    if granted is not None and not set(SCOPES).issubset(granted):
        raise ValueError('Google did not grant the document and comment permissions required by CiteGoblin')
    if not credentials.refresh_token:
        raise ValueError('Google did not return a refresh token; revoke the old grant and sign in again')
    store.save(credentials.to_json())
    remember_storage(store)
    return credentials


def login(client_secrets=None, token_file=None):
    if client_secrets:
        install_client(client_secrets)
    return sign_in(token_store(token_file), interactive=True)


def credentials(*, interactive=None):
    if interactive is None:
        interactive = sys.stdin.isatty()
    try:
        import google.auth
        from google.auth.exceptions import RefreshError, TransportError
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as error:
        raise ValueError('Install citegoblin[google] to access Google Docs') from error
    # Explicit server credentials continue to work without opening a browser.
    if os.environ.get('CITEGOBLIN_AUTH') == 'adc' or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        try:
            value, _ = google.auth.default(scopes=list(SCOPES))
            return value
        except google.auth.exceptions.GoogleAuthError as error:
            raise ValueError('Configured Google application credentials could not be loaded') from error
    store = token_store()
    raw = store.load()
    if not raw:
        return sign_in(store, interactive=interactive)
    try:
        value = Credentials.from_authorized_user_info(json.loads(raw))
    except (ValueError, TypeError, KeyError) as error:
        raise ValueError('Saved Google authorisation is invalid; run citegoblin login again') from error
    if not value.has_scopes(SCOPES):
        return sign_in(store, interactive=interactive)
    if not value.valid:
        try:
            value.refresh(Request())
        except TransportError as error:
            raise ValueError('Could not refresh Google authorisation; check your connection and rerun') from error
        except RefreshError as error:
            if getattr(error, 'retryable', False):
                raise ValueError('Google temporarily could not refresh authorisation; rerun later') from error
            return sign_in(store, interactive=interactive)
        store.save(value.to_json())
    return value


def status():
    store = token_store()
    raw = store.load()
    if not raw:
        return {'signedIn':False, 'storage':'file' if store.path else 'OS keychain'}
    try:
        saved = json.loads(raw)
    except ValueError as error:
        raise ValueError('Saved authorisation is invalid; run citegoblin login again') from error
    return {'signedIn':True, 'storage':'file' if store.path else 'OS keychain',
            'scopes':saved.get('scopes', []), 'expiry':saved.get('expiry'),
            'note':'Local authorisation exists; remote access is checked when connecting'}


def logout():
    token_store().delete()
    return {'signedOut':True, 'note':'Local authorisation removed. Google account grants are unchanged.'}
