# ridi-data-sources

Load information from web pages and local or remote data files, then search the
extracted text for matching chunks.

## Supported formats

- Website articles: HTML pages over HTTP or HTTPS
- Documents: PDF, plain text, and Markdown
- Machine-readable data: CSV, JSON, and XML

The loaders use Python's standard library except for PDF extraction, which uses
`pypdf`.

## Setup

```powershell
python -m pip install -r requirements.txt
```

## Search sources

Pass one or more URLs or local file paths. The program prompts for a search term
if `--query` is omitted.

```powershell
python main.py https://example.org/article.html data/population.csv report.pdf
python main.py data/dataset.json --query "population growth"
python main.py report.pdf --query emissions --chunk-size 75
```

Results include the source and matching text chunk so retrieved information can
be traced back to its origin. Search is currently case-insensitive keyword or
phrase matching; answering natural-language questions will need a later
retrieval and answer-generation step.


## New: Qdrant Data Sources interface

The original main.py, sources.py and retrieval.py are preserved unchanged.
The Qdrant REST gateway was adapted from the supplied Marktradar server.
This interface is independent of Marktradar and does not modify the database.

### Docker quick start

Fill `dataSources/.env` with `QDRANT_URL` and `QDRANT_API_KEY`, then run from the repository root:

```powershell
docker compose up --build
```

Open http://localhost:8001 for the Data Sources UI. MarktRadar runs on
http://localhost:8000 and sends searches to Data Sources over the Docker network.

### Windows quick start

Open PowerShell in this folder:

    py interface_server.py

Paste the HTTPS Qdrant cluster endpoint, then a read-only key at the prompts.
Key input is hidden. Open http://127.0.0.1:8001.
No extra packages are required for the new interface.
Keep PowerShell running. Ctrl+C stops the server.

On startup it fetches 10 points. Next/Previous browse further pages.
Search sends a text query using intfloat/multilingual-e5-small, with the
"query: " prefix, and returns up to five results. Full payloads are expandable.
Source links open in a new tab. Similarity does not establish factual accuracy.

### Backend routes for Justin

GET /api/points
GET /api/points?offset=<URL-encoded JSON next_offset>
Response: {"items": [Qdrant points including id and payload], "next_offset": ...}

POST /api/search
Content-Type: application/json
Body: {"q": "smart lighting"}
Response: {"items": [Qdrant points including score], "next_offset": null}

Only the backend knows the Qdrant credentials. No write endpoints exist.
QDRANT_URL and QDRANT_API_KEY may alternatively be provided as environment
variables. `.env.example` is a template; this server automatically loads
`dataSources/.env`. Do not commit keys, `.env`, or database exports.

### Scope and validation

For local development only: bound to 127.0.0.1:8001. No authentication for
remote clients is implemented. Justin can handle Docker and later connect
Marktradar to this service. No Marktradar files are overwritten.
When containerizing, configure binding, network access and trusted origins.

Automated tests use a local mock HTTP upstream: they check real REST request
paths/bodies, paging, read-only behavior, validation, and upstream failures.
Live Qdrant and browser UI still need testing with your current key.
Try browse, next, previous, search "smart lighting", payload details and links.
