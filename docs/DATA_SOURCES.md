# AEGIS-COP: data sources

This file is a summary register. Measured properties, coverage facts and validation
notes are in [project/GEO_DATA_AND_VALIDATION.md](project/GEO_DATA_AND_VALIDATION.md).

| Source | Type | In the repository? | Licence / terms | Used for |
|---|---|---|---|---|
| OpenStreetMap drive network, Hubballi-Dharwad (`data/osm/hubballi_dharwad_drive.graphml`) | Public, derived database (OSMnx 2.1.1) | **Yes** (26.9 MB) | ODbL 1.0: attribution "© OpenStreetMap contributors"; share-alike for derived databases ([data/osm/README.md](../data/osm/README.md)) | Routing, coverage, mission area |
| CartoDEM V3 R1 tile D43D (NRSC/ISRO) | Public portal, registration required | **No — never committed** (`.gitignore`: `data/terrain/*`) | NRSC single-user, non-transferable licence; excludes Internet hosting. Each user downloads their own copy ([data/terrain/README.md](../data/terrain/README.md)) | Terrain elevation and relative-elevation heuristic (optional, via `DEM_PATH`) |
| Open-Meteo forecast API | Public web API, no key | Not stored | Free for non-commercial use; check terms before commercial use | Single-point weather when the backend has internet |
| OpenStreetMap standard tiles | Public tile service | Not stored | OSM tile usage policy; attribution shown on the map | Browser basemap |
| NASA GIBS (VIIRS SNPP true colour) | Public WMTS | Not stored | NASA open data; attribution shown | Satellite tab overlay |
| Nominatim (OSM geocoder) | Public web API | Not stored | Nominatim usage policy (low volume) | Place search in the ad-hoc planner |
| IMD, MOSDAC, NASA FIRMS | Public / registered APIs | Not stored | Provider terms | **Not active**: disabled or stubbed unless you configure your own access |
| Drainage grid (`services/flood/drainage_service.py`) | **Synthetic** | Generated in code | n/a | Prototype flood heuristics (labelled SYNTHETIC) |
| Demo seed (`scripts/demo/seed_demo.py`) and simulated reports (`/api/simulation/field-report`, `scripts/demo/no_safe_route_case.py`) | **Simulated** | Generated at runtime | n/a | Demo threats, evidence, unit roster and positions. All labelled DEMO / SIMULATED |
| Screenshots (`docs/screenshots/`) | Captured from this app | Yes | Contain OSM map tiles (© OpenStreetMap contributors) | Documentation |

## Not in the repository

These are excluded deliberately:
- CartoDEM rasters, archives and metadata (`data/terrain/*`, except its README).
- Local SQLite databases (`*.db`, including `data/aegis.db`).
- `.env` files and any API keys.
- `node_modules/`, build output, caches and virtual environments.

## Running without the DEM

Everything starts without it:
- terrain lookups return `status: "unavailable"` with reason `DEM_UNAVAILABLE`;
- hazard scores become partial with an upper bound;
- the Overview data-source strip shows `Terrain (CartoDEM): UNAVAILABLE (DEM_UNAVAILABLE)`.

Threat-zone routing, monitoring and the mission workflow do not need the DEM.
