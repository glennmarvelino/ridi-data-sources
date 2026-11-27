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

`source_assignments.json` records confirmed source IDs and reasons, plus an
explicit review status for every point in the 1,435-record catalogue. The full
catalogue has been reviewed against the team category definitions: 972 sources
are assigned, 88 are out of scope, 375 need a team decision, and 0 remain
unchecked. The app's “in Prüfung” count is calculated as unchecked plus
team-decision records; out-of-scope records are excluded. Only confirmed
assignments appear in category results.

Current confirmed category counts are T1 Licht & Elektronik 89, T2 Vernetzung
& Sensorik 136, T3 Material & Fertigung 43, M1 Nachfrage 198, M2 Kundenbedarf
173, M3 Geschäftsmodelle 21, L Regulierung 225, S Arbeitswelt 106, E
Lieferkette 137, and CI Andere Branchen 0. These are 1,128 category
assignments across 972 unique confirmed sources; a source can belong to
multiple categories. The 375 records awaiting a team decision have individual
reasons in `source_assignments.json` and remain excluded from results.

The 202 Qdrant records in the legacy “Research and adjacent industries”
category were checked against UC-Q12 (“Technology Transfer”). No record
documents a qualifying transfer to commercial lighting with all three
requirements: originating industry, specific technology, and concrete
application. The remaining cross-industry discovery profiles and indirect
signals are not treated as confirmed assignments; CI remains empty. Team
category definitions are embedded in the category reference block in
`index.html`.

Domain pages retrieve only their assigned Qdrant point IDs through the existing
read-only Data Sources API. Empty-text results follow assignment order; optional
text filters and ranks only those fetched records. Qdrant credentials remain in
Data Sources and are not stored in MarktRadar. No Qdrant records, legacy
category labels, or rankings are modified.

For local development without Docker:
1. Start Data Sources with `py interface_server.py` in dataSources.
2. Start MarktRadar with `py server.py` in marktRadar.
3. Open http://127.0.0.1:8000.
