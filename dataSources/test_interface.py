import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from interface_server import Handler
from qdrant_gateway import QdrantGateway

class Upstream(BaseHTTPRequestHandler):
    seen = []
    fail = False
    def log_message(self, *args): pass
    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.seen.append((self.path, data, self.headers.get('api-key')))
        if self.fail:
            self.send_response(403); self.end_headers(); return
        if self.path.endswith('/scroll'):
            result = {'points': [{'id': 1, 'payload': {'title': 'Test source', 'text': '<script>bad()</script>'}}], 'next_page_offset': 11}
        else:
            result = {'points': [{'id': 2, 'score': .8, 'payload': {'title': 'Smart lighting'}}]}
        self.send_response(200); self.end_headers()
        self.wfile.write(json.dumps({'result': result}).encode())

class TestInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.up = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        cls.gateway = QdrantGateway('https://example.test', 'TEST_ONLY')
        # Test HTTP transport locally; production endpoint validation requires HTTPS.
        cls.gateway.endpoint = 'http://127.0.0.1:' + str(cls.up.server_port)
        Handler.gateway = cls.gateway
        cls.app = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.url = 'http://127.0.0.1:' + str(cls.app.server_port)
        for server in [cls.up, cls.app]:
            threading.Thread(target=server.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls):
        for server in [cls.app, cls.up]:
            server.shutdown(); server.server_close()
    def request(self, path, value=None):
        req = Request(self.url + path, data=json.dumps(value).encode() if value is not None else None,
                      headers={'Content-Type': 'application/json'} if value is not None else {})
        try:
            with urlopen(req) as r: return r.status, r.read()
        except HTTPError as e: return e.code, e.read()
    def test_browse_and_offset(self):
        status, body = self.request('/api/points?offset=11')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['next_offset'], 11)
        path, data, key = Upstream.seen[-1]
        self.assertEqual(path, '/collections/ridi_documents/points/scroll')
        self.assertEqual(data, {'offset': 11, 'limit': 10, 'with_payload': True, 'with_vector': False})
        self.assertEqual(key, 'TEST_ONLY')
        self.assertNotIn(b'TEST_ONLY', body)
    def test_query_contract(self):
        status, body = self.request('/api/search', {'q':'smart lighting'})
        self.assertEqual(status, 200)
        path, data, _ = Upstream.seen[-1]
        self.assertTrue(path.endswith('/query'))
        self.assertEqual(data['query']['text'], 'query: smart lighting')
        self.assertEqual(data['query']['model'], 'intfloat/multilingual-e5-small')
        self.assertEqual(data['limit'], 5)
        self.assertEqual(json.loads(body)['items'][0]['id'], 2)
    def test_invalid_inputs_and_no_write_routes(self):
        before = len(Upstream.seen)
        for path, data in [('/api/search', {'q':' '}), ('/api/search', []), ('/api/search', {'q':'a'*501})]:
            self.assertEqual(self.request(path, data)[0], 400)
        self.assertEqual(self.request('/api/points?offset=%7B%7D')[0], 400)
        self.assertEqual(self.request('/api/delete', {})[0], 404)
        self.assertEqual(len(Upstream.seen), before)
    def test_upstream_error(self):
        Upstream.fail=True
        try:
            status, body=self.request('/api/points')
            self.assertEqual(status, 502)
            self.assertIn(b'403', body)
            self.assertNotIn(b'TEST_ONLY', body)
        finally: Upstream.fail=False
    def test_page_served(self):
        status, body=self.request('/')
        self.assertEqual(status, 200)
        self.assertIn(b'Full payload', body)
        self.assertNotIn(b'TEST_ONLY', body)
    def test_config_validation(self):
        for url in ['http://example.test','https://example.test/dashboard','https://user:pw@example.test']:
            with self.assertRaises(ValueError): QdrantGateway(url,'test')

if __name__ == '__main__':
    unittest.main()
