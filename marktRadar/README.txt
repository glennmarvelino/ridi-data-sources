MARKTRADAR — DATA SOURCES SEARCH

The recommended setup is Docker Compose from the repository root:

1. Fill dataSources/.env with QDRANT_URL and QDRANT_API_KEY.
2. Run: docker compose up --build
3. Open http://localhost:8000 in your browser.
4. Press Ctrl+K, enter a research topic, choose one of the seven categories (or
   search across all categories), and press Enter. Changing the category while a
   topic is present immediately refreshes the Qdrant query and source results;
   no Enter key is needed. Typing alone does not trigger a search.

MarktRadar turns the topic into a short, RIDI-focused Qdrant retrieval query.
The query scopes results to professional lighting in non-residential buildings
and to the selected category; the generated query is shown with the results.
The all-categories option covers customer needs, renovation/market demand,
technology, regulation/product requirements, labour-related customer needs,
research/adjacent industries, and market structure/trade. Competitor-only
monitoring is excluded because it is covered by Lichtblick.

MarktRadar forwards the generated query to the Data Sources container. Data
Sources communicates with Qdrant, so Qdrant credentials are not stored or used
in MarktRadar. Qdrant retrieval supplies context only; final answer generation
with an LLM is a separate downstream step and is not implemented here.

For local development without Docker:
1. Start Data Sources with `py interface_server.py` in dataSources.
2. Start MarktRadar with `py server.py` in marktRadar.
3. Open http://127.0.0.1:8000.
