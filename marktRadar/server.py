import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def search(q):
    req = Request(
        DATA_SOURCES_URL + '/api/search',
        data=json.dumps({'q': q}).encode(),
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
    )
    with build_opener(NoRedirect()).open(req, timeout=25) as response:
        points = json.load(response).get('items', [])
    items = []
    for point in points:
        p = point.get('payload') or {}
        items.append({'title': str(p.get('title') or ''), 'source': str(p.get('source') or ''),
                      'url': str(p.get('source_url') or p.get('url') or ''),
                      'page': p.get('page') or p.get('pdf_page'), 'text': str(p.get('text') or '')[:360]})
    return items

class Handler(BaseHTTPRequestHandler):
    def send_data(self, status, mime, data):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status, value):
        self.send_data(status, 'application/json', json.dumps(value).encode())

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self.send_data(200, 'text/html; charset=utf-8', Path(__file__).with_name('index.html').read_bytes())
        elif self.path == '/api/health':
            self.send_json(200, {'status': 'ok'})
        else:
            self.send_json(404, {'error': 'Not found'})

    def do_POST(self):
        if self.path != '/api/qdrant/search':
            return self.send_json(404, {'error': 'Not found'})
        if self.headers.get('Origin') not in (None, 'http://127.0.0.1:8000', 'http://localhost:8000'):
            return self.send_json(403, {'error': 'Invalid origin'})
        if self.headers.get_content_type() != 'application/json':
            return self.send_json(415, {'error': 'Expected JSON'})
        try:
            n = int(self.headers.get('Content-Length', '0'))
            if not 0 < n <= 8192:
                raise ValueError
            q = json.loads(self.rfile.read(n)).get('q')
            if not isinstance(q, str) or not 1 <= len(q.strip()) <= 500:
                raise ValueError
        except (ValueError, AttributeError):
            return self.send_json(400, {'error': 'Enter 1–500 characters'})
        try:
            items = search(q.strip())
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            self.log_error('Qdrant request failed: %s %s', type(exc).__name__, getattr(exc, 'code', ''))
            return self.send_json(502, {'error': 'Qdrant search unavailable'})
        self.send_json(200, {'items': items})

if __name__ == '__main__':
    DATA_SOURCES_URL = os.environ.get('DATA_SOURCES_URL', 'http://127.0.0.1:8001').strip().rstrip('/')
    parsed = urlsplit(DATA_SOURCES_URL)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise SystemExit('DATA_SOURCES_URL must be a valid HTTP or HTTPS URL.')
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8000'))
    print(f'MarktRadar listening on http://{host}:{port}; Data Sources: {DATA_SOURCES_URL}')
    ThreadingHTTPServer((host, port), Handler).serve_forever()
