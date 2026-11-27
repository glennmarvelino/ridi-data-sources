import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
from interface_server import Handler
from qdrant_gateway import QdrantGateway

class Upstream(BaseHTTPRequestHandler):
    seen = []
    fail = False
    category_page_size = 5
    catalogue = [
        {'id': point_id, 'payload': {
            'title': 'Source ' + str(point_id),
            'category': 'Technology' if point_id <= 12 else 'Customer needs',
        }}
        for point_id in range(1, 21)
    ]
    def log_message(self, *args): pass
    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.seen.append((self.path, data, self.headers.get('api-key')))
        if self.fail:
            self.send_response(403); self.end_headers(); return
        if self.path.endswith('/scroll'):
            if data.get('with_payload') == ['category']:
                start = 0
                if data.get('offset') is not None:
                    start = next(index + 1 for index, point in enumerate(self.catalogue)
                                 if point['id'] == data['offset'])
                end = start + self.category_page_size
                points = self.catalogue[start:end]
                result = {
                    'points': [{'id': point['id'], 'payload': {'category': point['payload']['category']}}
                               for point in points],
                    'next_page_offset': points[-1]['id'] if end < len(self.catalogue) else None,
                }
            else:
                result = {'points': [{'id': 1, 'payload': {'title': 'Test source', 'text': '<script>bad()</script>'}}], 'next_page_offset': 11}
        elif self.path.endswith('/points'):
            result = [next(
                ({'id': point['id'], 'payload': {'title': 'Retrieved source', 'category': point['payload']['category']}}
                 for point in self.catalogue if point['id'] == point_id),
                {'id': point_id, 'payload': {'title': 'Retrieved source'}},
            ) for point_id in data['ids']]
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
    def test_category_browse_filters_unindexed_category_and_pages_without_gaps(self):
        Upstream.seen.clear()
        query = urlencode({'categories': json.dumps(['Technology'])})
        status, body = self.request('/api/category-sources?' + query)
        self.assertEqual(status, 200)
        first = json.loads(body)
        self.assertEqual([point['id'] for point in first['items']], list(range(1, 11)))
        self.assertEqual(first['next_offset'], 10)

        query = urlencode({
            'categories': json.dumps(['Technology']),
            'offset': json.dumps(first['next_offset']),
        })
        status, body = self.request('/api/category-sources?' + query)
        self.assertEqual(status, 200)
        second = json.loads(body)
        self.assertEqual([point['id'] for point in second['items']], [11, 12])
        self.assertIsNone(second['next_offset'])
        self.assertEqual(len({point['id'] for point in first['items'] + second['items']}), 12)

        scrolls = [(path, data) for path, data, _ in Upstream.seen if path.endswith('/scroll')]
        self.assertTrue(scrolls)
        self.assertTrue(all('filter' not in data for _, data in scrolls))
        self.assertTrue(all(data['with_payload'] == ['category'] for _, data in scrolls))
        self.assertTrue(all(data['limit'] == 256 for _, data in scrolls))
    def test_category_browse_rejects_unknown_categories_without_querying_qdrant(self):
        query = urlencode({'categories': json.dumps(['not-a-category'])})
        before = len(Upstream.seen)
        self.assertEqual(self.request('/api/category-sources?' + query)[0], 400)
        query = urlencode({
            'categories': json.dumps(['Technology']),
            'offset': json.dumps('not-a-page-index'),
        })
        self.assertEqual(self.request('/api/category-sources?' + query)[0], 400)
        self.assertEqual(len(Upstream.seen), before)
    def test_query_contract(self):
        status, body = self.request('/api/search', {'q':'smart lighting'})
        self.assertEqual(status, 200)
        path, data, _ = Upstream.seen[-1]
        self.assertTrue(path.endswith('/query'))
        self.assertEqual(data['query']['text'], 'query: smart lighting')
        self.assertEqual(data['query']['model'], 'intfloat/multilingual-e5-small')
        self.assertEqual(data['limit'], 5)
        self.assertEqual(json.loads(body)['items'][0]['id'], 2)
    def test_retrieve_uses_only_requested_ids(self):
        status, body = self.request('/api/points/retrieve', {'ids': [7, 9]})
        self.assertEqual(status, 200)
        path, data, _ = Upstream.seen[-1]
        self.assertTrue(path.endswith('/points'))
        self.assertEqual(data, {'ids': [7, 9], 'with_payload': True, 'with_vector': False})
        self.assertEqual([point['id'] for point in json.loads(body)['items']], [7, 9])
    def test_invalid_inputs_and_no_write_routes(self):
        before = len(Upstream.seen)
        for path, data in [('/api/search', {'q':' '}), ('/api/search', []), ('/api/search', {'q':'a'*501})]:
            self.assertEqual(self.request(path, data)[0], 400)
        for value in ([], {'ids': []}, {'ids': [1, 1]}, {'ids': [True]}, {'ids': list(range(101))}):
            self.assertEqual(self.request('/api/points/retrieve', value)[0], 400)
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
