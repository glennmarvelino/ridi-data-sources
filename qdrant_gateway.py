"""Read-only REST gateway, extracted from the working Marktradar server."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

class GatewayError(Exception):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

class QdrantGateway:
    def __init__(self, endpoint, key, collection='ridi_documents'):
        endpoint = endpoint.strip().rstrip('/')
        p = urlsplit(endpoint)
        if p.scheme != 'https' or not p.hostname or p.path or p.query or p.fragment or p.username:
            raise ValueError('Use an HTTPS cluster endpoint without a dashboard path.')
        if not key.strip():
            raise ValueError('Read-only API key is required.')
        self.endpoint, self.key = endpoint, key.strip()
        self.base = '/collections/' + quote(collection, safe='') + '/points'

    def request(self, suffix, body):
        req = Request(self.endpoint + self.base + suffix,
                      data=json.dumps(body).encode(),
                      headers={'Content-Type': 'application/json', 'api-key': self.key})
        try:
            with build_opener(NoRedirect()).open(req, timeout=25) as response:
                return json.load(response)['result']
        except HTTPError as e:
            raise GatewayError(f'Qdrant returned HTTP {e.code}. Check key permissions, endpoint and inference access.') from None
        except (URLError, TimeoutError, OSError):
            raise GatewayError('Could not reach Qdrant. Check the connection and endpoint.') from None
        except (ValueError, KeyError, TypeError):
            raise GatewayError('Unexpected response from Qdrant.') from None

    def browse(self, offset=None):
        body = {'limit': 10, 'with_payload': True, 'with_vector': False}
        if offset is not None:
            body['offset'] = offset
        result = self.request('/scroll', body)
        return {'items': result['points'], 'next_offset': result.get('next_page_offset')}

    def search(self, q):
        result = self.request('/query', {
            'query': {'text': 'query: ' + q, 'model': 'intfloat/multilingual-e5-small'},
            'limit': 5, 'with_payload': True, 'with_vector': False})
        return {'items': result['points'], 'next_offset': None}
