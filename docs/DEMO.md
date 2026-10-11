# AEGIS-COP: demo runbook (deterministic, offline)

The steps below were run in headless Chrome against an offline backend on fresh
databases (seed → mission → simulated report → reject → recompute → approve, plus the
no-safe-route case). Each repeat produced the same routes and metrics as the table.
The latest rehearsal date and results are in
[project/IMPLEMENTATION_STATUS.md](project/IMPLEMENTATION_STATUS.md).

**What is real and what is simulated:**
- **Real:** routing, threat-zone logic, persistence and the audit trail all run on the
  backend.
- **Simulated:** the field and sensor reports. Every one is labelled **SIMULATED**.
- **Heuristic:** hazard scores are uncalibrated.
- **Coverage:** Hubballi-Dharwad only.

## 0. Prerequisites (once)

```bash
# repo root
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt -c backend/requirements.lock.txt
cd frontend && npm ci --ignore-scripts --no-audit --no-fund && cd ..
```

Optional terrain: put a CartoDEM tile on disk (see `data/terrain/README.md`) and add
`DEM_PATH=/path/to/cdnd43d.tif` to the backend command. Without it the demo still runs.
Terrain shows as unknown and the hazard numbers differ from the ones below; route
geometry and the workflow are the same.

## 1. Start (three terminals, from the repo root)

**Terminal 1: backend, offline, on a fresh demo database**

```bash
cd backend
export AEGIS_DEMO_DIR=$(mktemp -d /tmp/aegis-demo-XXXX)
DATABASE_PATH=$AEGIS_DEMO_DIR/demo.db \
HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 NO_PROXY=localhost,127.0.0.1 \
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- **Why the proxy variables:** they send the backend's outbound calls (Open-Meteo, IMD)
  to a closed local port. Weather is then reliably *unavailable* and the demo does not
  depend on venue internet.
- **Map tiles still need internet** in the browser.
- **Bind to `127.0.0.1` only:** the API has no authentication.

**Terminal 2: frontend**

```bash
cd frontend
npm run dev            # http://localhost:5173
```

**Terminal 3: seed and warm up (wait until the backend answers `/api/health`)**

```bash
.venv/bin/python scripts/demo/seed_demo.py     # refuses to run if the database already has threats
curl -s -o /dev/null -w "warm-up %{http_code} %{time_total}s\n" \
  "http://127.0.0.1:8000/api/route?origin_lat=15.4030&origin_lon=75.0800&destination_lat=15.3647&destination_lon=75.1240"
```

The seed creates:
- 3 active **DEMO** threats and 1 closed one;
- 4 demo field units;
- 3 active **SIMULATED** evidence records and 1 archived one.

The warm-up loads the road graph (about 10 s cold), so **START MISSION** answers in under
a second (0.36 s measured warm). Open http://localhost:5173 on the **Overview** tab.

## 2. Click-by-click script (about 4 minutes)

All values below come from the offline rehearsal with the DEM present.

| # | Click | Expected result | What is happening technically |
|---|---|---|---|
| 1 | Nothing; Overview (dark theme by default; Dark/Light/System in the header) | Operational summary and **data sources** (Backend CONNECTED, Road graph LOADED, Terrain AVAILABLE or UNAVAILABLE, Weather UNAVAILABLE, "Sensor / field feeds: NONE CONNECTED — simulated reports only", "Unit positions: MANUAL / SEEDED"). **Decision chain** with 7 pending stages, mission "NOT STARTED" and the hint "Start the mission". Map with the dashed **mission area** rectangle, 3 DEMO threat zones, unit and evidence markers | `GET /api/cop` every 10 s, `GET /api/system/status`. The rectangle is the road-graph extent from `GET /api/geo/coverage`. The chain is derived from backend records only |
| 2 | **Active Mission → START MISSION** | Blue route with **Mission origin / Mission destination** markers. Panel: **ACTIVE**, 6.9 km · 17 min, "Hazard (heuristic): LOW (36.4) · partial data, up to 96.4 · confidence LIMITED". Log: "Mission route planned and monitoring started". Chain header: Mission ACTIVE | `GET /api/route` (threat-aware shortest path on the OSM graph), then `POST /api/route-monitor/register` (persisted). With weather unknown the score keeps an explicit upper bound instead of being re-weighted |
| 3 | **SIMULATE SENSOR REPORT** | Toast "SIMULATED report → threat … (CRITICAL); mission route INVALIDATED". Route turns **red**; a new CRITICAL zone appears on it. **Threat assessment** card: SIMULATED, severity CRITICAL, Road Flooding, radius 75 m, confidence MEDIUM, source SIMULATED_REPORT, timestamp, evidence `EVD-…` (SENSOR SIM-WLS-07), "Source-declared confidence 80% (fixed by the simulation profile, not measured)", and the rule text. **Why the route is INVALIDATED** box quotes the persisted reason. Chain: ✓ Observation received (SIMULATED) → ✓ Evidence linked → ✓ Threat identified → red Route impact assessed (INVALIDATED) | `POST /api/simulation/field-report` creates evidence (`provenance.is_simulation=true`) and a linked threat at the route's midpoint. Confidence MEDIUM comes from the single-source rule (≥ 0.5 → MEDIUM, never HIGH). The route monitor reassesses: CRITICAL = hard exclusion (radius + 25 m buffer) → INVALIDATED, with the threat id in the reason |
| 4 | Nothing (proposal appears in about 15 s) | **Dashed green** alternative on the map. Comparison at the top of Active Mission: distance 6.9 → 7.9 km, time 17 → 21 min, hazard 36.4 → 30.7, threat zones crossed 1 → 0. "Trade-off: +1.0 km, +4 min to cross 0 instead of 1 known threat zone(s)", the engine's rationale, and "not a guarantee that the road is safe". **APPROVE / REJECT** buttons. Chain: ✓ Alternative generated, Operator decision "Awaiting approve / reject" | `POST /api/route-monitor/{id}/replacement/recommend`. The threat-aware engine excludes blocking zones; metrics come from the backend for both routes |
| 5 | **REJECT** | Toast "Replacement route rejected by operator — route remains compromised". Proposal disappears; log "Operator REJECTED the alternative (Rejected by operator)". Chain: Operator decision REJECTED (amber) | `…/replacement/reject` persists the decision and reason. Status stays INVALIDATED |
| 6 | **COMPUTE ALTERNATIVE ROUTE** | Same proposal again (deterministic) | New persisted recommendation |
| 7 | **APPROVE** | Status **REPLACED**; the route on the map is now the green alternative (7.9 km · 21 min); log "Operator APPROVED the alternative" and "INVALIDATED → REPLACED"; **Operator decision recorded** box. Chain: all 7 stages ✓, impact shown as "INVALIDATED (resolved)" | `…/replacement/approve` swaps the monitored route's nodes and records the transition |
| 8 | Reload the page (F5) | Same REPLACED mission and the full log | Everything shown is read back from SQLite |
| 9 | **INCIDENTS** tab, select the SIMULATED threat | "Official Warning: None linked", "Severity score 80/100 (fixed per severity level, not a calibrated risk)", **LINKED EVIDENCE RECORDS** with the SIMULATED badge | `GET /api/evidence?threat_id=…` |
| 10 | *(optional)* **GENERATE RESPONSE PLAN → APPROVE RESPONSE PLAN → RECORD SIMULATED DISPATCH** | Matched resources with distance-based match scores; after dispatch the action is DISPATCHED and the incident timeline gains "SIMULATED_DISPATCH" | Response-plan endpoints. The backend replies "SIMULATED RESPONSE. NO REAL RESOURCE HAS BEEN DISPATCHED." |
| 11 | *(optional)* **FIELD OPERATIONS → SIMULATE FIELD REPORT: ROAD BLOCKED** | Second simulated report (field team, 40 m blockage) on the *new* route → mission INVALIDATED again; **COMPUTE ALTERNATIVE ROUTE** on Overview proposes 11.1 km · 34 min | Same pipeline with the `FIELD_TEAM_BLOCKAGE` profile |
| 12 | *(optional)* **FIELD OPERATIONS → START TRIP**, then **COMPLETE** | First: "Field unit status recorded by backend: EN_ROUTE". Second: "Status change rejected: Invalid transition from EN_ROUTE to COMPLETED" | The backend state machine validates transitions; the UI only shows success after the backend accepts |

**Safe to claim:**
- threat-aware routing with hard CRITICAL exclusion, and an explicit no-safe-route
  result;
- simulated reports turned into canonical, linked evidence and threats with provenance;
- persisted, audited route state and operator decisions;
- a COP built from canonical stores, with demo and simulation labelling;
- explicit coverage and data-gap reporting;
- automated offline tests.

**Do not claim:**
- real sensors, YOLO/CV or sensor fusion;
- real-time unit tracking;
- calibrated flood prediction;
- portability to other regions.

### The "no safe route" case (optional, about 1 minute)

The demo convoy always has a detour, so this case uses a second mission to a dead-end
street whose only access road is blocked:

```bash
.venv/bin/python scripts/demo/no_safe_route_case.py
```

The script registers the mission (Hubballi city centre → a dead end, 4.3 km) and
reports a SIMULATED CRITICAL washout on the access road, with linked SIMULATED
evidence. The Active Mission panel follows the newest mission. Within 10 s it shows
"Mission: (15.3647, 75.1240) → (15.3531, 75.0932)". Then:

1. The route is already INVALIDATED: recording the washout re-checked it automatically,
   and the reason names the washout threat. CHECK ROUTE is not needed.
2. **COMPUTE ALTERNATIVE ROUTE** → "No safe alternative exists: every path to the
   destination crosses a CRITICAL zone."
   - Chain: Alternative generated — "No safe route exists" (red).
   - If the rain scenario was run earlier, its incidents can already cover the route
     at registration; the panel then says "INVALIDATED since registration" and lists
     the zones it currently crosses.
   - There is no APPROVE button and no invented route.

Backend result: `NO_SAFE_AVAILABLE_ROUTE`. No recommendation is created, but the
attempt is saved in the mission record. After a reload the chain still shows "No safe
route exists", and the log has "Alternative search: no safe route exists (blocked by
THREAT-…)". The same case is covered by
`backend/tests/test_mission_workflow.py::test_no_safe_alternative_is_reported_honestly`.

### Automatic re-check from an external client (optional)

After the main story, run
`.venv/bin/python scripts/demo/post_external_report.py --at 0.5`.
- **What it is:** a test client that posts a SIMULATED evidence record and a linked
  CRITICAL threat on the newest mission route, through the public API.
- **What happens:** within ~10 s, with no click, the route turns INVALIDATED. The log
  shows "… (automatic re-check)".

Run this at the end of the demo, or on a fresh database: the convoy mission is no
longer the newest one afterwards.

## 3. Reset and repeat

1. Stop terminal 1 (Ctrl+C).
2. Create a new demo directory: `export AEGIS_DEMO_DIR=$(mktemp -d /tmp/aegis-demo-XXXX)`.
3. Start the backend again (same command as before).
4. Re-run the seed and the warm-up.
5. Reload the browser.

Nothing in the repository or in `data/aegis.db` is touched.

## 4. Recovery

| Problem | Do this |
|---|---|
| Header shows **BACKEND UNREACHABLE** / panel shows **STALE**; chain steps show "unknown" | The backend stopped. Restart terminal 1 with the *same* `DATABASE_PATH` (state persists), then reload |
| START MISSION is slow (> 10 s) | First route after start loads the graph; run the warm-up next time |
| Proposal does not appear after the report | Click **COMPUTE ALTERNATIVE ROUTE** (if the automatic request failed, a toast shows the backend error) |
| Seed refuses to run | The database is not empty: use a fresh `AEGIS_DEMO_DIR` (section 3) |
| Blank map tiles (no venue internet) | Layers, routes and panels still render on a blank background |
| Frontend broken | Show the API at http://127.0.0.1:8000/docs (`/api/cop`, `/api/route-monitor/{id}`) |
| DEM missing | Start without `DEM_PATH`: everything runs; terrain is reported unknown |

## 5. Limitations to mention if asked

- **Reports:** there is no live sensor or field-app ingestion. Reports come from fixed
  simulation profiles.
- **Placement:** the report location is the midpoint of the current mission route,
  chosen so the demo is reproducible.
- **Hazard scores and penalties:** uncalibrated heuristics.
- **Weather:** one point for the whole city (unavailable offline).
- **Unit positions:** seeded, not tracked.

See [LIMITATIONS.md](LIMITATIONS.md).
