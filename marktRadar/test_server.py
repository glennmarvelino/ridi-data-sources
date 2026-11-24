import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import Handler, SEARCH_PROMPTS, build_search_prompt


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

    def post(self, value):
        req = Request(
            self.url + '/api/qdrant/search',
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


if __name__ == '__main__':
    unittest.main()
