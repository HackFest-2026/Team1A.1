# Terrain data (not distributed with this repository)

The terrain features use an ISRO/NRSC CartoDEM tile. **The original files must not be
committed or redistributed.** The NRSC licence (shipped as `policy.txt` inside the
download) grants a single-user, non-transferable licence and expressly excludes
Internet-based hosting. Each developer must download the tile under their own
registration.

## Expected local layout

```
data/terrain/cdnd43d_v3r1/cdnd43d.tif     # default DEM_PATH
```

Any other location can be used by setting `DEM_PATH` in `backend/.env`.

## Dataset

| Field | Value |
|---|---|
| Product | CartoDEM Version 3 R1 (Cartosat-1 stereo), tile D43D |
| Source | NRSC Bhuvan Open Earth Data portal (bhuvan-noeda.nrsc.gov.in), registration required |
| Original archive name | `C1_DEM_16B_2005-2014_v3_R-1_75E15N_d43d.zip` |
| Coverage | 75°E–76°E, 15°N–16°N (lon 74.99986–75.99986, lat 15.00014–16.00014) |
| Resolution | 1 arc-second (~30 m), 3600 × 3600 px, int16, metres |
| CRS | Geographic WGS 84 (EPSG:4326) |
| Surface type | Metadata topic category: Digital Surface Model (includes buildings/vegetation) |
| Citation | "CartoDEM, National Remote Sensing Centre, ISRO, Government of India, Hyderabad, India" |

Without the file the backend still starts; terrain lookups return
`status: "unavailable"` with `reason: "DEM_UNAVAILABLE"`. Hazard scores then treat
terrain as unknown: weather keeps its normal 60% weight, completeness and confidence
drop, and an upper bound is reported. Tests that need the DEM are skipped with an explicit reason.

Known limitation: roughly 12.6% of the Hubballi-Dharwad road graph lies west of
75°E and is outside this tile. See `docs/project/GEO_DATA_AND_VALIDATION.md`.
