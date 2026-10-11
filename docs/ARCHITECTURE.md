# AEGIS-COP architecture

This page describes the architecture as implemented, for evaluators and new
contributors. The layer model (A–E), module boundaries and design decisions are in
[project/ARCHITECTURE.md](project/ARCHITECTURE.md) and
[project/DECISIONS_AND_ROADMAP.md](project/DECISIONS_AND_ROADMAP.md).

## 1. Purpose and core chain

AEGIS-COP is an edge-oriented geospatial decision-support **Common Operating Picture**.
Its core chain is:

```
Observation → Evidence → Threat → Geographic context → Route impact → Explainable recommendation → Human review
```

It is human-in-the-loop decision support. The system proposes and explains; an operator
approves or rejects; nothing is executed automatically. It is not an autonomous
targeting or control system.

## 2. Runtime components

```
Browser (React 19 + Leaflet, Vite dev server :5173)
  EocDashboard
   ├─ DataSourceStrip    backend / road graph / terrain / weather / feeds / unit positions
   ├─ DecisionChain      7-step chain derived from the mission record (no own state)
   ├─ ThreatPanel + SelectedThreatEvidence
   ├─ Map + COPLayers    threats, units, evidence, monitored routes, mission area, proposal
   ├─ MissionPanel       start / simulate / check / compute / approve / reject + mission log
   └─ IncidentCenter, field ops, weather, satellite, national tabs
        │  REST/JSON  (/api/*, polled every 10 s via useCOP)
        ▼
FastAPI backend (uvicorn :8000, bind 127.0.0.1)
  routes/        HTTP handlers (cop, threats, evidence, simulation, geo, national/*)
  app/main.py    legacy inline routes: /api/route, /api/route-monitor/*, /api/scenario/*
  services/
   ├─ threat/            threat CRUD, zones (zone_from_threat, ThreatZoneIndex),
   │                     simulated_report (simulated observation → evidence → threat)
   ├─ evidence/          canonical evidence + provenance, threat association
   ├─ cop/               COP snapshot and summary from the canonical stores
   ├─ geo/               coverage manifest, snapping, route geo-context
   ├─ routing_service    OSMnx/NetworkX graph (thread-safe single load), threat-aware weights
   ├─ route_monitor_service / route_replacement_service
   │                     persisted status, transitions, recommendations, approve/reject
   ├─ terrain_service    CartoDEM sampling with explicit "unavailable" reasons
   ├─ hazard_scoring     0.6·weather + 0.4·terrain, unknowns not re-weighted (upper bound)
   └─ weather_adapter    Open-Meteo, single point; AVAILABLE / STALE / UNAVAILABLE / scenario
  repositories/  SQLite persistence (threats, evidence, field units, monitored routes,
                 route recommendations)
  config/routing_policy.py   blocking severities, multipliers, buffer (uncalibrated)
        │
        ▼
Local data: data/osm/hubballi_dharwad_drive.graphml (tracked, ODbL)
            CartoDEM tile at DEM_PATH (optional, never distributed)
            SQLite at DATABASE_PATH
```

## 3. Mission workflow: sequence

| Step | UI action | API call | Backend effect |
|---|---|---|---|
| 1 | START MISSION | `GET /api/route?origin…&destination…` | Threat-aware shortest path on the road graph (inputs > 250 m from the network → 422 `OUTSIDE_COVERAGE`) |
| | | `POST /api/route-monitor/register` | Monitored route persisted with status ACTIVE and a hazard summary |
| 2 | SIMULATE SENSOR REPORT | `POST /api/simulation/field-report {route_id, profile}` | `simulated_report.submit_simulated_report` does four things. (a) It creates evidence at the route midpoint with `provenance.is_simulation=true` and `confidence_basis=DECLARED_BY_SIMULATION_PROFILE`. (b) It creates a threat (`source=SIMULATED_REPORT`, title prefixed `SIMULATED:`) whose `evidence_references` point to that evidence. (c) It associates the evidence with the threat. (d) It reassesses the route. |
| 3 | (automatic) | — | Threat confidence comes from the single-source rule: declared ≥ 0.5 → MEDIUM, otherwise LOW, never HIGH |
| 4 | (automatic) | — | Route segments within radius + 25 m of an active CRITICAL zone → INVALIDATED. The transition is persisted, and its reason contains the threat id. Every monitored route is re-checked like this whenever any threat is created, updated or closed (`route_monitor_service.reassess_all`, `trigger: THREAT_CHANGE`), not only the mission that reported it |
| 5 | (automatic) or COMPUTE ALTERNATIVE ROUTE | `POST /api/route-monitor/{id}/replacement/recommend` | Path that excludes blocking zones. Returns `RECOMMENDATION_READY` (persisted as PENDING) or `NO_SAFE_AVAILABLE_ROUTE` / `NO_ROUTE` / `NO_BETTER_ROUTE` (no recommendation; the attempt is persisted in the route's `replacement_attempts`) |
| 6 | APPROVE / REJECT (with a typed name and reason) | `…/replacement/approve` / `…/replacement/reject` (`actor`, `reason`) | Recommendation APPROVED/REJECTED with time, self-declared actor and reason. Approval swaps the route nodes and records INVALIDATED → REPLACED |
| 7 | (polling) | `GET /api/route-monitor/{id}`, `GET /api/cop` | Mission log and decision chain are rebuilt from transitions and recommendations |

Other observation entry points use the same pipeline:
- Field Operations → **SIMULATE FIELD REPORT: ROAD BLOCKED** (profile `FIELD_TEAM_BLOCKAGE`).
- `scripts/demo/no_safe_route_case.py` (dead-end mission with a blocked access road).

## 4. Single source of truth

- Threats, evidence, field units, monitored routes and recommendations are stored in
  SQLite through `repositories/`. The COP (`GET /api/cop`) is a read model over those
  stores.
- The frontend keeps only view state.
  - The active mission is the most recently created monitored route.
  - The decision chain, mission log, map styling and incident desk are all derived from
    backend responses.
- Replacement searches that produce no recommendation (e.g. `NO_SAFE_AVAILABLE_ROUTE`)
  are persisted as `replacement_attempts` on the route, so they survive a reload.

## 5. Routing and threat policy

| Severity | Effect on routing | Effect on a monitored route |
|---|---|---|
| CRITICAL | Hard exclusion (edge weight removed) within radius + 25 m | INVALIDATED |
| HIGH | Travel-time multiplier ×3.0 | AT_RISK |
| MODERATE | ×1.75 | — (exposure reported) |
| LOW | ×1.25 | — |

- Overlapping zones do not compound.
- A zone that contains the origin or the destination is penalised (×10) rather than
  blocked, so the endpoints stay reachable.
- All values live in `backend/app/config/routing_policy.py` and are **uncalibrated**.

## 6. Degraded operation

| Condition | Behaviour |
|---|---|
| Weather unreachable | Weather is UNKNOWN: scores are marked partial with an upper bound, and confidence is LIMITED. Routing and threat logic are unaffected |
| DEM absent | Terrain is reported `unavailable` with reason `DEM_UNAVAILABLE`, and scores are partial. Tests needing the DEM are skipped |
| Input outside the road network | 422 `OUTSIDE_COVERAGE` (no silent snapping beyond 250 m) |
| Backend unreachable | UI shows BACKEND UNREACHABLE, a STALE snapshot with its time, last-known source statuses, and "unknown" decision-chain steps |

## 7. Testing

- `backend/tests/` is offline. `conftest.py` redirects `DATABASE_PATH` to a temporary
  directory, blocks sockets and resets the service singletons.
- `requires_graph` / `requires_dem` markers skip tests, with a reason, when the data is
  absent.
- `tests/test_mission_workflow.py` covers the full chain, including reject-then-approve
  and the honest no-safe-route case.
- The frontend is checked with `oxlint` and `vite build`. The UI was verified in
  headless Chrome; the results are recorded in
  [project/IMPLEMENTATION_STATUS.md](project/IMPLEMENTATION_STATUS.md).
