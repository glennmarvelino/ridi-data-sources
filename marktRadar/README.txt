MARKTRADAR — DATA SOURCES SEARCH

The recommended setup is Docker Compose from the repository root:

1. Fill dataSources/.env with QDRANT_URL and QDRANT_API_KEY.
2. Run: docker compose up --build
3. Open http://localhost:8000 in your browser.
4. Press Ctrl+K and choose one of the radar's ten categories. The category
   list loads immediately; optional text searches only that category's confirmed
   source assignments. Use “Weitere Quellen laden” to page through all matches.
5. Click a radar sector to open its popup and immediately load the first page of
   confirmed assignments. The popup and search dropdown use the same IDs and
   order. Radar group labels continue to browse their legacy category groups.

`source_assignments.json` records source IDs, assignment reasons, placement,
and a review status for every point in the 1,435-record catalogue. The full
catalogue has been reviewed against the team category definitions: 1,336
sources are assigned (972 main sources and 364 supporting-only sources), 99
are out of scope, and 0 are unchecked or awaiting a team decision. The app's
“in Prüfung” count is calculated from unchecked and team-decision records, so
it is zero and is not shown. Out-of-scope reasons remain in the internal
mapping and are not displayed in the web app.

Current confirmed category counts are T1 Licht & Elektronik 115, T2 Vernetzung
& Sensorik 201, T3 Material & Fertigung 99, M1 Nachfrage 220, M2 Kundenbedarf
229, M3 Geschäftsmodelle 21, L Regulierung 238, S Arbeitswelt 191, E
Lieferkette 253, and CI Andere Branchen 0. These are 1,567 category
assignments across 1,336 unique confirmed sources; a source can belong to
multiple categories. Supporting assignments are kept after main assignments
and shown under “Ergänzende Quellen” / “Supporting sources”.

The 202 Qdrant records in the legacy “Research and adjacent industries”
category were checked against UC-Q12 (“Technology Transfer”). No record
documents a qualifying transfer to commercial lighting with all three
requirements: originating industry, specific technology, and concrete
application. CI remains empty rather than acting as a catch-all. Profiles
with explicit relevance to another category appear only as supporting sources
there. Team category definitions are embedded in the category reference block
in `index.html`.

Domain pages retrieve only their assigned Qdrant point IDs through the existing
read-only Data Sources API. Empty-text results follow the same mapping order
in the radar popup and search dropdown, with main sources first and supporting
sources last. Optional text filters search only assigned IDs and preserve that
main/supporting order while ranking matches within each section. Qdrant
credentials remain in Data Sources and are not stored in MarktRadar. No Qdrant
records, legacy category labels, or rankings are modified.

For local development without Docker:
1. Start Data Sources with `py interface_server.py` in dataSources.
2. Start MarktRadar with `py server.py` in marktRadar.
3. Open http://127.0.0.1:8000.
