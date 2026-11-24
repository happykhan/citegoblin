"""Serve the desktop OAuth response on a temporary loopback address."""

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import socket
from time import monotonic
from urllib.parse import parse_qs, urlsplit
import webbrowser

HOST = '127.0.0.1'
SUCCESS_PAGE = Path(__file__).with_name('oauth_success.html')



class LoopbackServer(HTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def run_callback(flow, complete, *, timeout=180, **options):
    """Return saved credentials after a Google callback with the expected state."""
    result = None
    failure = None
    page = SUCCESS_PAGE.read_bytes()

    class CallbackHandler(BaseHTTPRequestHandler):
        timeout = 5

        def log_message(self, *_args):
            # The callback URL contains a short-lived authorisation code.
            pass

        def reply(self, status, body, content_type='text/plain; charset=utf-8'):
            try:
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Content-Security-Policy',
                                 "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            nonlocal result, failure
            request = urlsplit(self.path)
            query = parse_qs(request.query)
            if request.path != '/' or not state or query.get('state') != [state]:
                self.reply(404, b'No matching sign-in request.')
                return

            try:
                if 'error' in query or len(query.get('code', [])) != 1:
                    raise ValueError('Google did not authorise CiteGoblin')
                flow.fetch_token(code=query['code'][0], timeout=30)
                result = complete(flow.credentials)
            except Exception as error:
                failure = error
                self.reply(400, b'CiteGoblin sign-in did not complete. Return to your terminal for details.')
                return

            self.reply(200, page, 'text/html; charset=utf-8')

    with LoopbackServer((HOST, 0), CallbackHandler) as server:
        flow.redirect_uri = f'http://{HOST}:{server.server_port}/'
        url, state = flow.authorization_url(**options)
        print(f'Sign in to Google in your browser: {url}', flush=True)
        webbrowser.open(url, new=1, autoraise=True)
        deadline = monotonic() + timeout
        while result is None and failure is None:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError('Timed out waiting for Google sign-in')
            server.timeout = remaining
            server.handle_request()
        if failure is not None:
            raise failure
        return result
