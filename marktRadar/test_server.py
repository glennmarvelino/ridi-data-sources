import io
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

from server import (
    DOMAIN_SOURCE_ASSIGNMENTS,
    SOURCE_ASSIGNMENT_DATA,
    SOURCE_REVIEW_PENDING_COUNT,
    Handler,
    RADAR_BROWSE_CATEGORIES,
    SEARCH_PROMPTS,
    browse_domain_sources,
    browse_sources,
    build_search_prompt,
)


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

    def test_only_group_browsing_uses_legacy_qdrant_categories(self):
        expected = {
            'technik': ('Technology',),
            'markt': (
                'Customer needs',
                'Renovation and market demand',
                'Market structure and trade',
            ),
            'umfeld': (
                'Future regulation/product requirements',
                'Labour-related customer needs',
                'Research and adjacent industries',
            ),
        }
        self.assertEqual(RADAR_BROWSE_CATEGORIES, expected)


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

    def test_domain_search_endpoint_returns_confirmed_sources_and_count(self):
        page = {
            'items': [{'id': 2, 'title': 'D4i', 'assignment_reason': 'Sensors and networks.'}],
            'next_offset': 10,
            'total': 11,
            'domain_id': 'T2',
            'query': '',
            'review_pending_count': SOURCE_REVIEW_PENDING_COUNT,
        }
        with patch('server.browse_domain_sources', return_value=page) as browse:
            status, body = self.post({'domainId': 'T2', 'q': ''})

        self.assertEqual(status, 200)
        self.assertEqual(browse.call_args.args, ('T2', 0, ''))
        self.assertEqual(body, page)

    def test_domain_search_scopes_text_and_offset_to_confirmed_domain_sources(self):
        with patch('server.browse_domain_sources', return_value={
            'items': [], 'next_offset': None, 'total': 0, 'domain_id': 'E', 'query': 'semiconductor shortages',
        }) as browse:
            status, body = self.post({'domainId': 'E', 'q': 'semiconductor shortages', 'offset': 10})

        self.assertEqual(status, 200)
        self.assertEqual(browse.call_args.args, ('E', 10, 'semiconductor shortages'))
        self.assertEqual(body['query'], 'semiconductor shortages')
        self.assertEqual(self.post({'domainId': 'unknown', 'q': ''})[0], 400)
        self.assertEqual(self.post({'domainId': ['T2'], 'q': ''})[0], 400)
        self.assertEqual(self.post({'domainId': 'T2', 'q': '', 'offset': -1})[0], 400)

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
            status, body = self.post({'categoryId': 'technik'}, '/api/qdrant/category-sources')

        self.assertEqual(status, 200)
        self.assertEqual(browse.call_args.args, ('technik', None))
        self.assertEqual(body, page)

    def test_category_browse_passes_the_same_category_and_offset(self):
        with patch('server.browse_sources', return_value={
            'items': [], 'next_offset': None, 'categories': ['Technology'],
        }) as browse:
            status, _ = self.post({'categoryId': 'technik', 'offset': 11}, '/api/qdrant/category-sources')

        self.assertEqual(status, 200)
        self.assertEqual(browse.call_args.args, ('technik', 11))

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


class TestDomainSourceAssignments(unittest.TestCase):
    def test_confirmed_assignments_have_reasons_and_unique_ids_per_domain(self):
        self.assertEqual(len(DOMAIN_SOURCE_ASSIGNMENTS), 10)
        for entries in DOMAIN_SOURCE_ASSIGNMENTS.values():
            ids = [entry['id'] for entry in entries]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertTrue(all(entry['reason'].strip() for entry in entries))

    def test_confirmed_and_pending_ranges_cover_the_catalogue_snapshot(self):
        confirmed = {
            entry['id']
            for entries in DOMAIN_SOURCE_ASSIGNMENTS.values()
            for entry in entries
        }
        unresolved = {
            source_id
            for start, end in SOURCE_ASSIGNMENT_DATA['unresolved_id_ranges']
            for source_id in range(start, end + 1)
        }
        statuses = SOURCE_ASSIGNMENT_DATA['review_status_by_id']
        catalogue_ids = {str(source_id) for source_id in range(1, SOURCE_ASSIGNMENT_DATA['catalogue_snapshot_count'] + 1)}
        self.assertEqual(set(statuses), catalogue_ids)
        self.assertEqual({source_id for source_id, status in statuses.items() if status == 'assigned'}, {str(i) for i in confirmed})
        self.assertEqual({int(source_id) for source_id, status in statuses.items() if status != 'assigned'}, unresolved)
        self.assertEqual(confirmed | unresolved, {int(source_id) for source_id in catalogue_ids})
        self.assertEqual(SOURCE_REVIEW_PENDING_COUNT, sum(status in ('unchecked', 'needs_team_decision') for status in statuses.values()))
        self.assertEqual(sum(status == 'out_of_scope' for status in statuses.values()), 88)
        self.assertEqual(sum(status == 'needs_team_decision' for status in statuses.values()), 375)
        self.assertEqual(sum(status == 'unchecked' for status in statuses.values()), 0)
        self.assertEqual(len(confirmed), 972)
        self.assertEqual(sum(len(entries) for entries in DOMAIN_SOURCE_ASSIGNMENTS.values()), 1128)
        pending_reasons = SOURCE_ASSIGNMENT_DATA['pending_reasons']
        self.assertEqual(set(pending_reasons), {str(source_id) for source_id in unresolved})
        self.assertTrue(all(reason.strip() for reason in pending_reasons.values()))
        for entry in SOURCE_ASSIGNMENT_DATA['reviewed_pending']:
            self.assertIn(entry['id'], unresolved)
            self.assertIn(entry['status'], ('out_of_scope', 'needs_team_decision'))
            self.assertEqual(pending_reasons[str(entry['id'])], entry['reason'])
        self.assertIn([1, 1435], SOURCE_ASSIGNMENT_DATA['reviewed_id_ranges'])

    def test_adjacent_industries_sweep_records_uc_q12_review_without_false_assignments(self):
        sweeps = SOURCE_ASSIGNMENT_DATA['reviewed_category_sweeps']
        sweep = next(
            item for item in sweeps
            if item['domain_id'] == 'CI'
            and item['legacy_category'] == 'Research and adjacent industries'
        )
        self.assertEqual(sweep['definition_ref'], 'UC-Q12')
        self.assertEqual(sweep['reviewed_id_range'], [1021, 1222])
        self.assertEqual(sweep['reviewed_record_count'], 202)
        self.assertEqual(sweep['confirmed_source_ids'], [])
        self.assertEqual(DOMAIN_SOURCE_ASSIGNMENTS['CI'], [])

    def test_uc_q12_global_screen_requires_source_industry_technology_and_application(self):
        review = SOURCE_ASSIGNMENT_DATA['reviewed_uc_q12']
        self.assertEqual(review['definition_ref'], 'UC-Q12')
        self.assertEqual(review['screened_record_count'], SOURCE_ASSIGNMENT_DATA['catalogue_snapshot_count'])
        self.assertEqual(len(review['screened_legacy_categories']), 7)
        self.assertEqual(review['documented_transfer_ids'], [])
        self.assertEqual(review['plausible_candidate_ids'], [])
        self.assertEqual(review['confirmed_source_ids'], [])
        self.assertEqual(DOMAIN_SOURCE_ASSIGNMENTS['CI'], [])
        self.assertTrue(all(
            lead['title']
            and lead['original_industry_evidence']
            and lead['technology']
            and lead['commercial_lighting_application']
            and lead['assessment']
            for lead in review['reviewed_leads']
        ))

    def test_empty_query_pages_in_assignment_order_and_reports_total(self):
        ids = [entry['id'] for entry in DOMAIN_SOURCE_ASSIGNMENTS['T2']]
        points = [{'id': source_id, 'payload': {'title': str(source_id)}} for source_id in ids[:10]]
        with patch('server.retrieve_sources', return_value=points) as retrieve:
            page = browse_domain_sources('T2')

        self.assertEqual(retrieve.call_args.args[0], ids[:10])
        self.assertEqual([item['id'] for item in page['items']], ids[:10])
        self.assertEqual(page['total'], len(ids))
        self.assertEqual(page['next_offset'], 10)

    def test_final_empty_query_page_returns_last_assignment_without_repeating_offset(self):
        ids = [entry['id'] for entry in DOMAIN_SOURCE_ASSIGNMENTS['T2']]
        offset = ((len(ids) - 1) // 10) * 10
        final_ids = ids[offset:]
        with patch('server.retrieve_sources', return_value=[
            {'id': source_id, 'payload': {'title': str(source_id)}} for source_id in final_ids
        ]) as retrieve:
            page = browse_domain_sources('T2', offset)

        self.assertEqual(retrieve.call_args.args[0], final_ids)
        self.assertEqual([item['id'] for item in page['items']], final_ids)
        self.assertEqual(page['total'], len(ids))
        self.assertIsNone(page['next_offset'])

    def test_text_filter_searches_only_assigned_records_and_pages_results(self):
        ids = [entry['id'] for entry in DOMAIN_SOURCE_ASSIGNMENTS['T2']]
        points = [
            {'id': source_id, 'payload': {'title': 'DALI', 'text': 'Bluetooth sensor network'}}
            for source_id in ids[:6]
        ]
        points.extend(
            {'id': source_id, 'payload': {'title': 'Unrelated', 'text': 'No matching text'}}
            for source_id in ids[6:]
        )
        point_batches = [points[:100], points[100:]]
        with patch('server.retrieve_sources', side_effect=point_batches) as retrieve:
            page = browse_domain_sources('T2', 0, 'Bluetooth sensor')

        retrieved_ids = [source_id for call in retrieve.call_args_list for source_id in call.args[0]]
        self.assertEqual(retrieved_ids, ids)
        self.assertEqual(page['total'], 6)
        self.assertEqual([item['id'] for item in page['items']], ids[:6])
        self.assertIsNone(page['next_offset'])


if __name__ == '__main__':
    unittest.main()
