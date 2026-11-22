MARKTRADAR — LOCAL QDRANT SEARCH

1. Extract the ZIP. In PowerShell, open the marktradar folder.
2. Run: py server.py
3. Paste the Qdrant Cluster Endpoint, then a new read-only API key.
   The key will not be visible as you paste it. Press Enter.
4. Open http://127.0.0.1:8000 in your browser (keep PowerShell open).
5. Press Ctrl+K, type "smart lighting", and press Enter. Check a source link.

The existing local search stays available. Pressing Enter retrieves
up to five live source matches. Dashboard analysis is separate.
This server is intended for local demos. It does not store the key.
