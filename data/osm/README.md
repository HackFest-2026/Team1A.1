# Road network data

`hubballi_dharwad_drive.graphml` is a drivable road graph for Hubballi-Dharwad derived
from **OpenStreetMap**.

**Attribution:** © OpenStreetMap contributors. Data available under the
[Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
This file is a derived database; redistribution must keep this attribution and the
ODbL share-alike terms.

| Field | Value |
|---|---|
| Built with | OSMnx 2.1.1, `graph_from_point((15.41, 75.06), dist=15000, network_type="drive")` (`scripts/download_osm_graph.py`) |
| Created | 2026-09-08 (graph attribute `created_date`) |
| Size | 25,471 nodes, 70,723 directed edges |
| Extent | lat 15.2754–15.5449, lon 74.9203–75.1998 |
| CRS | EPSG:4326 |

Travel times are imputed by OSMnx from highway-type speed defaults and are not
validated. Override the path with `OSM_GRAPH_PATH`. See
`docs/project/GEO_DATA_AND_VALIDATION.md`.
