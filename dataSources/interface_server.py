"""Local interface for ridi-data-sources. Does not modify Qdrant."""
import json
import os
from getpass import getpass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urlsplit, parse_qs
from qdrant_gateway import QdrantGateway, GatewayError

class Handler(BaseHTTPRequestHandler):
    gateway = None

    def reply(self, code, value, mime='application/json; charset=utf-8'):
        data = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urlsplit(self.path)
        if p.path == '/':
            return self.reply(200, Path(__file__).with_name('data_sources.html').read_bytes(), 'text/html; charset=utf-8')
        if p.path == '/api/health':
            return self.reply(200, {'status': 'ok'})
        if p.path != '/api/points':
            return self.reply(404, {'error': 'Not found'})
        try:
            raw = parse_qs(p.query).get('offset', [None])[0]
            offset = json.loads(raw) if raw is not None else None
            if offset is not None and (type(offset) not in (int, str) or len(str(offset)) > 100 or (type(offset) is int and offset < 0)):
                raise ValueError
        except ValueError:
            return self.reply(400, {'error': 'Invalid page offset'})
        try:
            self.reply(200, self.gateway.browse(offset))
        except GatewayError as e:
            self.reply(502, {'error': str(e)})

    def do_POST(self):
        if self.path != '/api/search':
            return self.reply(404, {'error': 'Not found'})
        if self.headers.get('Origin') not in (None, 'http://localhost:8001', 'http://127.0.0.1:8001'):
            return self.reply(403, {'error': 'Invalid origin'})
        if self.headers.get_content_type() != 'application/json':
            return self.reply(415, {'error': 'Expected JSON'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 8192:
                raise ValueError
            q = json.loads(self.rfile.read(length)).get('q')
            if not isinstance(q, str) or not 1 <= len(q.strip()) <= 500:
                raise ValueError
        except (ValueError, AttributeError):
            return self.reply(400, {'error': 'Enter a query of 1–500 characters'})
        try:
            self.reply(200, self.gateway.search(q.strip()))
        except GatewayError as e:
            self.reply(502, {'error': str(e)})

if __name__ == '__main__':
    load_dotenv(Path(__file__).with_name(".env"))
    endpoint = os.getenv('QDRANT_URL', '').strip()
    key = os.getenv('QDRANT_API_KEY', '').strip()
    if not endpoint:
        try:
            endpoint = input('Qdrant Cluster Endpoint: ').strip()
        except EOFError:
            raise SystemExit('Set QDRANT_URL in dataSources/.env before starting the server.')
    if not key:
        try:
            key = getpass('Qdrant read-only API key: ').strip()
        except EOFError:
            raise SystemExit('Set QDRANT_API_KEY in dataSources/.env before starting the server.')
    try:
        Handler.gateway = QdrantGateway(endpoint, key)
    except ValueError as e:
        raise SystemExit(str(e))
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8001'))
    print(f'Data Sources listening on http://{host}:{port} — Ctrl+C to stop')
    ThreadingHTTPServer((host, port), Handler).serve_forever()
