MARKTRADAR — DATA SOURCES SEARCH

The recommended setup is Docker Compose from the repository root:

1. Fill dataSources/.env with QDRANT_URL and QDRANT_API_KEY.
2. Run: docker compose up --build
3. Open http://localhost:8000 in your browser.
4. Press Ctrl+K, type "smart lighting", and press Enter.

MarktRadar forwards search requests to the Data Sources container. Data Sources
communicates with Qdrant, so Qdrant credentials are not stored or used in MarktRadar.

For local development without Docker:
1. Start Data Sources with `py interface_server.py` in dataSources.
2. Start MarktRadar with `py server.py` in marktRadar.
3. Open http://127.0.0.1:8000.
