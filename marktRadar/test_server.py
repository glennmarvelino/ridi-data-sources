import io
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

from server import Handler, RADAR_BROWSE_CATEGORIES, SEARCH_PROMPTS, browse_sources, build_search_prompt


class TestSearchPrompts(unittest.TestCase):
    def test_builds_category_specific_prompts(self):
        question = '  DALI-2 in office tenders  '
        prompts = {
            category: build_search_prompt(question, category)
            for category in SEARCH_PROMPTS
        }

        self.assertEqual(len(prompts), 8)
        self.assertIn('RIDI professional lighting for non-residential buildings', prompts['all'])
        self.assertIn('procurement criteria', prompts['customer-needs'])
        self.assertIn('retrofit demand', prompts['renovation-demand'])
        self.assertIn('interoperability', prompts['technology'])
        self.assertIn('mandatory from voluntary', prompts['regulation'])
        self.assertIn('workforce constraints', prompts['labour'])
        self.assertIn('adjacent industries', prompts['research-adjacent'])
        self.assertIn('supply chains', prompts['market-trade'])
        self.assertIn('DALI-2 in office tenders', prompts['technology'])
        self.assertIn('higher-ranked category entries', prompts['all'])
        self.assertIn('exclude competitor-only monitoring', prompts['labour'])

    def test_prompt_is_bounded_and_rejects_invalid_categories(self):
        for category in SEARCH_PROMPTS:
            prompt = build_search_prompt('lighting ' * 500, category)
            self.assertLessEqual(len(prompt), 500)
        with self.assertRaises(ValueError):
            build_search_prompt('lighting', 'unknown')
        with self.assertRaises(ValueError):
            build_search_prompt('  ')

    def test_radar_domain_ids_map_to_live_qdrant_categories(self):
        expected = {
            'T1': 'Technology',
            'T2': 'Technology',
            'T3': 'Technology',
            'M1': 'Renovation and market demand',
            'M2': 'Customer needs',
            'M3': 'Market structure and trade',
            'L': 'Future regulation/product requirements',
            'S': 'Labour-related customer needs',
            'E': 'Market structure and trade',
            'CI': 'Research and adjacent industries',
        }
        self.assertEqual(
            {domain: RADAR_BROWSE_CATEGORIES[domain][0] for domain in expected},
            expected,
        )


class TestSearchEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.url = 'http://127.0.0.1:' + str(cls.app.server_port)
        threading.Thread(target=cls.app.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.app.shutdown()
        cls.app.server_close()

    def post(self, value, path='/api/qdrant/search'):
        req = Request(
            self.url + path,
            data=json.dumps(value).encode(),
            headers={'Content-Type': 'application/json'},
        )
        try:
            with urlopen(req) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_search_sends_and_returns_generated_query(self):
        with patch('server.search', return_value=[]) as search:
            status, body = self.post({'q': 'DALI-2 office tenders', 'category': 'customer-needs'})

        self.assertEqual(status, 200)
        self.assertEqual(search.call_args.args[0], body['query'])
        self.assertIn('procurement criteria', body['query'])
        self.assertEqual(body['items'], [])

    def test_rejects_unknown_category(self):
        status, _ = self.post({'q': 'lighting', 'category': 'unknown'})
        self.assertEqual(status, 400)

    def test_category_browse_returns_page_without_a_search_query(self):
        page = {
            'items': [{'title': 'Technology source', 'category': 'Technology'}],
            'next_offset': 11,
            'categories': ['Technology'],
        }
        with patch('server.browse_sources', return_value=page) as browse:
            status, body = self.post({'categoryId': 'T1'}, '/api/qdrant/category-sources')

        self.assertEqual(status, 200)
        self.assertEqual(browse.call_args.args, ('T1', None))
        self.assertEqual(body, page)

    def test_category_browse_passes_the_same_category_and_offset(self):
        with patch('server.browse_sources', return_value={
            'items': [], 'next_offset': None, 'categories': ['Technology'],
        }) as browse:
            status, _ = self.post({'categoryId': 'T2', 'offset': 11}, '/api/qdrant/category-sources')

        self.assertEqual(status, 200)
        self.assertEqual(browse.call_args.args, ('T2', 11))

    def test_category_browse_rejects_unknown_radar_id(self):
        status, _ = self.post({'categoryId': 'unknown'}, '/api/qdrant/category-sources')
        self.assertEqual(status, 400)

    def test_browse_maps_radar_group_to_exact_live_categories_and_keeps_offset(self):
        response = io.BytesIO(json.dumps({
            'items': [{'payload': {
                'title': 'Customer source',
                'source': 'Publisher',
                'source_url': 'https://example.test/source',
                'text': 'A short excerpt.',
                'category': 'Customer needs',
            }}],
            'next_offset': 21,
        }).encode())
        with patch('server.DATA_SOURCES_URL', 'http://datasources:8001', create=True), patch('server.build_opener') as opener:
            opener.return_value.open.return_value = response
            page = browse_sources('markt', 11)

        request = opener.return_value.open.call_args.args[0]
        params = parse_qs(urlsplit(request.full_url).query)
        self.assertEqual(json.loads(params['categories'][0]), [
            'Customer needs',
            'Renovation and market demand',
            'Market structure and trade',
        ])
        self.assertEqual(json.loads(params['offset'][0]), 11)
        self.assertEqual(page['items'][0]['category'], 'Customer needs')
        self.assertEqual(page['items'][0]['publisher'], 'Publisher')
        self.assertEqual(page['next_offset'], 21)


if __name__ == '__main__':
    unittest.main()
