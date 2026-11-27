import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

SEARCH_PROMPTS = {
    'all': (
        'RIDI professional lighting for non-residential buildings: {topic}. Find evidence across '
        'customer needs, renovation/market demand, technology, regulation, labour, '
        'research/adjacent industries, and market structure/trade.'
    ),
    'customer-needs': (
        'RIDI professional lighting for non-residential buildings: {topic}. Find customer, planner, '
        'operator and user needs, procurement criteria, and buying requirements.'
    ),
    'renovation-demand': (
        'RIDI professional lighting for non-residential buildings: {topic}. Find renovation and '
        'retrofit demand, building segments, investment, financing, energy costs, and market signals.'
    ),
    'technology': (
        'RIDI professional lighting for non-residential buildings: {topic}. Find lighting technology, '
        'controls, sensors, components, interoperability, performance, and commercial readiness.'
    ),
    'regulation': (
        'RIDI professional lighting for non-residential buildings: {topic}. Find relevant laws, '
        'standards, procurement rules, deadlines, and product requirements; separate mandatory from voluntary.'
    ),
    'labour': (
        'RIDI professional lighting for non-residential buildings: {topic}. Find workforce constraints '
        'affecting installation, commissioning, maintenance, and customer operations.'
    ),
    'research-adjacent': (
        'RIDI professional lighting for non-residential buildings: {topic}. Find research evidence and '
        'transferable findings from adjacent industries, including practical applicability.'
    ),
    'market-trade': (
        'RIDI professional lighting for non-residential buildings: {topic}. Find market structure, '
        'distribution, trade, contractors, supply chains, and financial conditions.'
    ),
}
SEARCH_GUIDANCE = (
    ' Prioritize direct RIDI application fit, observable change, authoritative accessible and '
    'actionable evidence; prefer higher-ranked category entries; exclude competitor-only monitoring.'
)
SOURCE_ASSIGNMENT_DATA = json.loads(
    Path(__file__).with_name('source_assignments.json').read_text(encoding='utf-8')
)
DOMAIN_SOURCE_ASSIGNMENTS = SOURCE_ASSIGNMENT_DATA['domains']
SOURCE_REVIEW_PENDING_COUNT = sum(
    status in ('unchecked', 'needs_team_decision')
    for status in SOURCE_ASSIGNMENT_DATA['review_status_by_id'].values()
)
DOMAIN_SOURCE_PAGE_SIZE = 10
RADAR_BROWSE_CATEGORIES = {
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


def build_search_prompt(question, category='all'):
    """Turn a user's topic into a concise, RIDI-focused Qdrant retrieval query."""
    if category not in SEARCH_PROMPTS:
        raise ValueError('Unknown research category.')
    topic = ' '.join(question.split())
    if not topic:
        raise ValueError('A research topic is required.')
    template = SEARCH_PROMPTS[category] + SEARCH_GUIDANCE
    topic_limit = 500 - len(template.format(topic=''))
    if topic_limit < 1:
        raise ValueError('Research prompt is too long.')
    if len(topic) > topic_limit:
        topic = topic[:topic_limit].rsplit(' ', 1)[0].strip() or topic[:topic_limit]
    return template.format(topic=topic)


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
        items.append({'title': str(p.get('title') or p.get('ranked_entry_title') or ''),
                      'source': str(p.get('source') or p.get('publisher') or ''),
                      'url': str(p.get('source_url') or p.get('url') or ''),
                      'page': p.get('page') or p.get('pdf_page'),
                      'text': str(p.get('text') or p.get('content') or p.get('description') or '')[:360]})
    return items


def browse_sources(category_id, offset=None):
    categories = RADAR_BROWSE_CATEGORIES[category_id]
    params = {'categories': json.dumps(categories)}
    if offset is not None:
        params['offset'] = json.dumps(offset)
    req = Request(
        DATA_SOURCES_URL + '/api/category-sources?' + urlencode(params),
        headers={'Accept': 'application/json'},
    )
    with build_opener(NoRedirect()).open(req, timeout=25) as response:
        result = json.load(response)
    items = []
    for point in result.get('items', []):
        payload = point.get('payload') or {}
        items.append({
            'title': str(payload.get('title') or payload.get('ranked_entry_title') or ''),
            'publisher': str(payload.get('source') or payload.get('publisher') or ''),
            'url': str(payload.get('source_url') or payload.get('url') or ''),
            'text': str(payload.get('text') or payload.get('content') or payload.get('description') or '')[:360],
            'category': str(payload.get('category') or ''),
        })
    return {'items': items, 'next_offset': result.get('next_offset'), 'categories': categories}


def retrieve_sources(source_ids):
    req = Request(
        DATA_SOURCES_URL + '/api/points/retrieve',
        data=json.dumps({'ids': source_ids}).encode(),
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
    )
    with build_opener(NoRedirect()).open(req, timeout=25) as response:
        return json.load(response).get('items', [])


def browse_domain_sources(domain_id, offset=0, query=''):
    """Return only confirmed source IDs, preserving the reviewed mapping order."""
    if domain_id not in DOMAIN_SOURCE_ASSIGNMENTS:
        raise ValueError('Unknown category.')
    if type(offset) is not int or offset < 0:
        raise ValueError('Invalid page offset.')
    entries = DOMAIN_SOURCE_ASSIGNMENTS[domain_id]
    placements = {
        entry['id']: entry.get('placement', 'main')
        for entry in entries
    }
    source_ids = [entry['id'] for entry in entries]
    source_ids.sort(key=lambda source_id: placements[source_id] == 'supporting')
    query = ' '.join(query.split())
    if query:
        points = []
        for start in range(0, len(source_ids), 100):
            points.extend(retrieve_sources(source_ids[start:start + 100]))
        by_id = {point.get('id'): point for point in points}
        if set(by_id) != set(source_ids):
            raise ValueError('Qdrant returned a different source ID set.')
        tokens = re.findall(r'[^\W_]+', query.casefold(), flags=re.UNICODE)
        matches = []
        for index, source_id in enumerate(source_ids):
            point = by_id[source_id]
            payload = point.get('payload') or {}
            text = ' '.join(str(payload.get(key) or '') for key in (
                'title', 'ranked_entry_title', 'source', 'text', 'description',
            )).casefold()
            score = sum(text.count(token) for token in tokens)
            if tokens and all(token in text for token in tokens):
                matches.append((placements[source_id] == 'supporting', score, index, point))
        matches.sort(key=lambda hit: (hit[0], -hit[1], hit[2]))
        ordered_points = [point for _, _, _, point in matches]
    else:
        page_ids = source_ids[offset:offset + DOMAIN_SOURCE_PAGE_SIZE]
        if not page_ids:
            ordered_points = []
        else:
            points = retrieve_sources(page_ids)
            by_id = {point.get('id'): point for point in points}
            if set(by_id) != set(page_ids):
                raise ValueError('Qdrant returned a different source ID set.')
            ordered_points = [by_id[source_id] for source_id in page_ids]

    total = len(ordered_points) if query else len(source_ids)
    page = (
        ordered_points[offset:offset + DOMAIN_SOURCE_PAGE_SIZE]
        if query else ordered_points
    )
    items = []
    reasons = {entry['id']: entry['reason'] for entry in DOMAIN_SOURCE_ASSIGNMENTS[domain_id]}
    for point in page:
        payload = point.get('payload') or {}
        source_id = point['id']
        items.append({
            'id': source_id,
            'title': str(payload.get('title') or payload.get('ranked_entry_title') or ''),
            'publisher': str(payload.get('source') or payload.get('publisher') or ''),
            'url': str(payload.get('source_url') or payload.get('url') or ''),
            'text': str(payload.get('text') or payload.get('content') or payload.get('description') or '')[:360],
            'assignment_reason': reasons[source_id],
            'placement': placements[source_id],
        })
    next_offset = offset + len(page)
    if next_offset >= total:
        next_offset = None
    return {
        'items': items,
        'next_offset': next_offset,
        'total': total,
        'domain_id': domain_id,
        'query': query,
        'review_pending_count': SOURCE_REVIEW_PENDING_COUNT,
    }


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
        if self.path not in ('/api/qdrant/search', '/api/qdrant/category-sources'):
            return self.send_json(404, {'error': 'Not found'})
        if self.headers.get('Origin') not in (None, 'http://127.0.0.1:8000', 'http://localhost:8000'):
            return self.send_json(403, {'error': 'Invalid origin'})
        if self.headers.get_content_type() != 'application/json':
            return self.send_json(415, {'error': 'Expected JSON'})
        try:
            n = int(self.headers.get('Content-Length', '0'))
            if not 0 < n <= 8192:
                raise ValueError
            body = json.loads(self.rfile.read(n))
            if self.path == '/api/qdrant/category-sources':
                category_id = body.get('categoryId')
                offset = body.get('offset')
                if not isinstance(category_id, str) or category_id not in RADAR_BROWSE_CATEGORIES:
                    raise ValueError
                if offset is not None and (type(offset) not in (int, str) or len(str(offset)) > 100 or (type(offset) is int and offset < 0)):
                    raise ValueError
                query = None
            else:
                q = body.get('q')
                if not isinstance(q, str) or len(q.strip()) > 500:
                    raise ValueError
                domain_id = body.get('domainId')
                if domain_id is not None:
                    if not isinstance(domain_id, str) or domain_id not in DOMAIN_SOURCE_ASSIGNMENTS:
                        raise ValueError
                    offset = body.get('offset', 0)
                    if type(offset) is not int or offset < 0:
                        raise ValueError
                    query = None
                else:
                    category = body.get('category', 'all')
                    if not q.strip() or not isinstance(category, str):
                        raise ValueError
                    query = build_search_prompt(q.strip(), category)
        except (ValueError, AttributeError):
            message = (
                'Choose a valid category and enter no more than 500 characters'
                if self.path == '/api/qdrant/search'
                else 'Enter a valid radar category and page offset'
            )
            return self.send_json(400, {'error': message})
        if self.path == '/api/qdrant/category-sources':
            try:
                result = browse_sources(category_id, offset)
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                self.log_error('Qdrant browse failed: %s %s', type(exc).__name__, getattr(exc, 'code', ''))
                return self.send_json(502, {'error': 'Qdrant sources unavailable'})
            return self.send_json(200, result)
        if domain_id is not None:
            try:
                result = browse_domain_sources(domain_id, offset, q.strip())
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                self.log_error('Qdrant domain browse failed: %s %s', type(exc).__name__, getattr(exc, 'code', ''))
                return self.send_json(502, {'error': 'Qdrant sources unavailable'})
            return self.send_json(200, result)
        try:
            items = search(query)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            self.log_error('Qdrant request failed: %s %s', type(exc).__name__, getattr(exc, 'code', ''))
            return self.send_json(502, {'error': 'Qdrant search unavailable'})
        self.send_json(200, {'items': items, 'query': query})

if __name__ == '__main__':
    DATA_SOURCES_URL = os.environ.get('DATA_SOURCES_URL', 'http://127.0.0.1:8001').strip().rstrip('/')
    parsed = urlsplit(DATA_SOURCES_URL)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise SystemExit('DATA_SOURCES_URL must be a valid HTTP or HTTPS URL.')
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8000'))
    print(f'MarktRadar listening on http://{host}:{port}; Data Sources: {DATA_SOURCES_URL}')
    ThreadingHTTPServer((host, port), Handler).serve_forever()
