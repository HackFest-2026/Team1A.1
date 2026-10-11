# AEGIS-COP System & Architecture Guide

**Adaptive Edge Geospatial Intelligence System — Common Operating Picture (India)**  
*Comprehensive Technical Manual & Algorithmic Blueprint for HackFest 2026*

---

## Table of Contents
1. [System Overview & High-Level Architecture](#1-system-overview--high-level-architecture)
2. [Page 1: Naval Video Detection (Main Landing Page)](#2-page-1-naval-video-detection-main-landing-page)
3. [Page 2: Maritime Intelligence & AIS Tracking](#3-page-2-maritime-intelligence--ais-tracking)
4. [Page 3: Naval Awareness & Radar Correlation](#4-page-3-naval-awareness--radar-correlation)
5. [Page 4: Tactical Route Command & Common Operating Picture](#5-page-4-tactical-route-command--common-operating-picture)
6. [Page 5: Incident Review & Tactical Dispatch](#6-page-5-incident-review--tactical-dispatch)
7. [Page 6: System Status & Diagnostic Observability](#7-page-6-system-status--diagnostic-observability)
8. [Cross-Cutting Algorithmic & Mathematical Models](#8-cross-cutting-algorithmic--mathematical-models)
9. [Data Integrity, Security & Defense Compliance](#9-data-integrity-security--defense-compliance)

---

## 1. System Overview & High-Level Architecture

### 1.1 Mission & Purpose
**AEGIS-COP** is a tactical-edge, multimodal Common Operating Picture (COP) engineered for maritime domain awareness and coastal defense across India's **7,516 km coastline** and strategic sea lanes in the **Arabian Sea, Bay of Bengal, and Indian Ocean Region (IOR)**.

The system fuses four disparate intelligence streams into one auditable operational workstation:
1. **Computer Vision & Video Reconnaissance** (drone / coastal camera feeds detecting vessels, smoke, fire, and missiles).
2. **Historical & Tactical AIS Telemetry** (vessel tracking, animated playback, gap detection, and coverage bounds).
3. **Topological Deepwater Sea-Lane Routing** (anti-land-crossing graph routing between strategic Indian and regional ports).
4. **Tactical Edge Common Operating Picture & Convoy Routing** (threat-aware road routing with human-in-the-loop review).

```
┌────────────────────────────────────────────────────────────────────────┐
│                   AEGIS-COP FRONTEND (React 19 + Vite)                 │
│  Indian Naval Command Aesthetic (#071522) · Leaflet (Keyless OSM)      │
│  ├─ Naval Video Detection      (Main Landing Page · YOLOv8 + ByteTrack)│
│  ├─ Maritime Intelligence      (Historical AIS Playback & Sea Lanes)   │
│  ├─ Naval Awareness            (Radar-to-AIS Dark Vessel Correlation)  │
│  ├─ Tactical Route Command     (Decision Chain & Threat-Aware Routing) │
│  ├─ Incident Review            (Emergency Lifecycle & Resource C2)     │
│  └─ System Status              (Subsystem Health & Pipeline Diagnostics│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ REST API (/api/*)
┌───────────────────────────────────▼────────────────────────────────────┐
│                  AEGIS-COP BACKEND (FastAPI + Python 3.13)             │
│  ├─ routes/vision.py      (Video upload, multi-model threat pipeline)  │
│  ├─ routes/maritime.py    (AIS import, positions, playback, route)     │
│  ├─ routes/naval.py       (Tactical contacts, radar/AIS correlation)   │
│  ├─ routes/cop.py         (10s polling Common Operating Picture state) │
│  ├─ routes/incidents.py   (Incident lifecycle & tactical response)     │
│  ├─ services/vision/      (YOLOv8, ByteTrack, trajectory tracking)     │
│  ├─ services/maritime_ais (CSV normalization, track playback, Dijkstra)│
│  ├─ services/routing_service.py (OSMnx/NetworkX threat-aware routing)  │
│  └─ database/connection   (SQLite persistent schema & audit logs)      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Page 1: Naval Video Detection (Main Landing Page)

### 2.1 Purpose & Role
**Naval Video Detection** serves as the primary operational centerpiece of AEGIS-COP. It transforms raw, unstructured coastal camera feeds or drone video into structured, trackable tactical intelligence and automated threat ratings without requiring manual frame-by-frame analysis by operators.

### 2.2 Functional Capabilities
- **Video Footage Ingest**: Uploads MP4/AVI/MOV/MKV surveillance recordings (up to 150 MB) with tactical metadata (geographic sector coordinates, patrol sector description, AIS correlation flag, restricted area flag).
- **Automated Video Processing & Extraction**: Deconstructs video streams at configurable frame rates (default: $3.0\text{ fps}$) for edge efficiency.
- **Annotated HUD Video Playback**: Renders an in-browser media player featuring bounding box overlays, track IDs, category color tags, confidence percentages, and visual alerts.
- **Interactive Detections Gallery**: Filter detections by category (`VESSEL`, `FIRE / SMOKE`, `PROJECTILE`, `SUSPICIOUS`).
- **Telemetry Timeline Chart**: Displays frame-by-frame object counts and confidence evolution over time.
- **Human-in-the-Loop Review**: Commander modal to **APPROVE** or **REJECT** the video threat assessment with an auditable reason before escalating to the Common Operating Picture.
- **Exportable Video Artifact**: Direct download link to the compiled, annotated MP4 video (`/api/vision/download/{run_id}`).

### 2.3 Technical Aspects & Algorithms
- **Object Detection Architecture**: Powered by **Ultralytics YOLOv8** (`yolov8n.pt`) optimized for edge inference. Detects standard maritime surface craft (boats, ships, tenders) along with specialized classifiers for smoke plumes and structural fire.
- **Multi-Object Tracking (ByteTrack)**:
  - Uses **ByteTrack** for persistent target association across consecutive frames.
  - Formulates tracking as a bipartite matching problem solved via the **Hungarian Algorithm** on bounding box Intersection over Union (IoU), with motion prediction modeled via a **Kalman Filter**.
  - Eliminates identity switches during temporary occlusions (e.g., vessel passing behind waves or spray).
- **Projectile / Fast Mover Heuristic**:
  - Analyzes bounding box displacement vectors $\vec{v} = (\Delta x / \Delta t, \Delta y / \Delta t)$.
  - Triggers projectile / missile classification when target acceleration and velocity exceed acoustic / surface vessel thresholds ($> 80\text{ pixels/frame}$ with linear trajectory coherence).
- **Threat Scoring Engine (`threat_assessment.py`)**:
  - Dynamically calculates a quantitative threat score $S \in [0, 100]$ based on:
    $$S = w_{\text{class}} C_{\text{det}} + w_{\text{prox}} P_{\text{zone}} + w_{\text{AIS}} A_{\text{dark}} + w_{\text{acc}} M_{\text{traj}}$$
    where:
    - $w_{\text{class}}$ = Category weight (Missile/Projectile = 40, Fire = 30, Boat = 15).
    - $C_{\text{det}}$ = Detection confidence ($0.0$ to $1.0$).
    - $P_{\text{zone}}$ = Proximity bonus if inside designated military restricted waters (+25).
    - $A_{\text{dark}}$ = Dark vessel bonus if transponder is missing (+20).
    - $M_{\text{traj}}$ = High-speed vector bonus (+15).
  - Categorizes threat level:
    - $S \ge 75 \implies \text{CRITICAL}$
    - $50 \le S < 75 \implies \text{HIGH}$
    - $30 \le S < 50 \implies \text{MEDIUM}$
    - $S < 30 \implies \text{LOW}$
- **Canonical Evidence Serialization**: Creates an immutable JSON evidence artifact stored with a SHA-256 integrity hash linking the video detection to the central COP.

---

## 3. Page 2: Maritime Intelligence & AIS Tracking

### 3.1 Purpose & Role
**Maritime Intelligence** delivers historical Automatic Identification System (AIS) transponder tracking, animated vessel movement playback, and topological deepwater sea-route planning for the Indian Ocean, Arabian Sea, and Bay of Bengal.

### 3.2 Functional Capabilities
- **Flexible CSV Ingestion**: Accepts user-selected CSV archives with automatic column header aliasing:
  - MMSI: `mmsi`, `MMSI`, `vessel_mmsi`, `vessel_id`
  - Timestamp: `timestamp`, `BaseDateTime`, `datetime`, `date_time`, `TIMESTAMP`
  - Coordinates: `lat` / `LAT` / `latitude`, `lon` / `LON` / `longitude`
  - Telemetry: `sog` / `SOG` (knots), `cog` / `COG` (degrees), `heading`
  - Vessel Metadata: `ship_name` / `VesselName`, `ship_type` / `VesselType`
- **Dynamic Bounding Box & Rejection Reporting**:
  - Detects and displays actual dataset bounds without assuming Indian Ocean coordinates.
  - Rejects invalid coordinates (outside $[-90, 90]$ or $[-180, 180]$) and corrupt timestamps without crashing, displaying an error diagnostics log.
- **Historical Movement Playback**:
  - Groups records by MMSI and sorts observations chronologically.
  - Resolves duplicate timestamps and reconstructs historical polylines.
  - **Gap Detection**: Splits polylines into distinct segments if time gaps between observations exceed 6 hours, preventing misleading straight lines across transponder outages.
  - Transport controls: Play, Pause, Reset, scrubbable timeline slider, and speed multipliers ($1\text{x}$, $2\text{x}$, $5\text{x}$, $10\text{x}$).
  - Pulsing vessel marker moving along the polyline showing instantaneous SOG, COG, and distance.
- **Topological Sea-Route Planner**:
  - Select origin port, destination port, and cruising speed in knots.
  - Calculates shortest navigable path over verified open deepwater corridors.
  - Returns total distance in Nautical Miles, transit ETA (days and hours), and step-by-step waypoints.
- **Keyless Nautical Map**: Uses open OpenStreetMap tiles styled with dark tactical CSS classes, requiring **zero external API keys or tokens**.

### 3.3 Technical Aspects & Algorithms
- **Haversine Geodesic Distance Formula**:
  All distances are calculated across the spherical Earth in Nautical Miles ($R = 3440.065\text{ NM}$):
  $$d = 2 R \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)}\right)$$
  where $\phi$ is latitude and $\lambda$ is longitude in radians.
- **Dijkstra's Shortest Path Algorithm on Topological Graph**:
  - Graph $G = (V, E)$ consists of 45 verified marine nodes: major ports (Mumbai, Marmagao, Mangalore, Kochi, Tuticorin, Colombo, Galle, Chennai, Visakhapatnam, Paradip, Haldia, Port Blair, Singapore, Karachi, Salalah, Djibouti) and deep sea transit corridors (Cape Comorin South, Dondra Head, Ten Degree Channel, Six Degree Channel, Malacca Fairway).
  - Graph representation: Adjacency list stored in [`data/maritime/maritime_network.json`](data/maritime/maritime_network.json).
  - Edge weights $w(u, v)$ equal the geodesic distance in NM.
  - Implementation uses a min-priority queue (Fibonacci/binary heap via Python `heapq`):
    $$O((|E| + |V|) \log |V|)$$
  - Enforces anti-land crossing: all edges are manually validated open-ocean corridors (e.g., ships routing between Mumbai and Chennai pass south of Sri Lanka via Dondra Head, avoiding Adam's Bridge / Palk Strait land barriers).
- **Transit Duration Estimation**:
  $$\text{Transit Hours} = \frac{\text{Total Distance (NM)}}{\text{Cruising Speed (knots)}}, \quad \text{Transit Days} = \frac{\text{Transit Hours}}{24}$$

---

## 4. Page 3: Naval Awareness & Radar Correlation

### 4.1 Purpose & Role
**Naval Awareness** models coastal radar-to-AIS correlation for naval command centers (such as Western Naval Command and Indian Coast Guard stations). It correlates radar contacts with commercial transponder broadcasts to detect **dark vessels** and transponder spoofing.

### 4.2 Functional Capabilities
- **Tactical Contact Monitoring**: Displays real-time surface contacts with status tags: `matched` (normal transponder), `missing` (dark vessel), `mismatch` (reported position differs from radar return).
- **Dark Vessel Ingestion**: Coastal radar chains (e.g., IMAC Gurgaon) ingest raw radar/electro-optical tracks with zero AIS broadcast, automatically generating high-priority coastal alerts.
- **Contact Ingest Form**: Operator modal to register new tactical contacts into the live C2 picture (`POST /api/naval/vessels`).
- **Naval Evidence Correlation**: Cross-references optical detections from the Video Intelligence pipeline with active naval contacts in the sector.

### 4.3 Technical Aspects & Algorithms
- **Kinematic Contact Correlation**:
  - Compares radar track vector $(x_r, y_r, \vec{v}_r)$ with broadcast AIS telemetry $(x_a, y_a, \vec{v}_a)$.
  - Position discrepancy threshold:
    $$\Delta d = \text{haversine}(x_r, y_r, x_a, y_a) > 2.5\text{ NM} \implies \text{STATUS: MISMATCH}$$
  - Course discrepancy threshold:
    $$|\text{COG}_r - \text{COG}_a| > 30^\circ \implies \text{TACTICAL ANOMALY}$$
- **Zero-Broadcast Detection**:
  - Coastal radar contacts lacking an associated MMSI within a $5.0\text{ NM}$ radius are automatically categorized as:
    $$\text{is\_dark\_vessel} = \text{True}, \quad \text{ais\_status} = \text{"missing"}$$

---

## 5. Page 4: Tactical Route Command & Common Operating Picture

### 5.1 Purpose & Role
**Tactical Route Command** is the decision-support engine for land and coastal evacuation convoys, emergency logistics, and quick-reaction force (QRF) movements. When threats, flooding, or enemy strikes occur, it automatically analyzes route impact, generates safe alternatives, and presents an explainable decision chain to a human commander.

### 5.2 Functional Capabilities
- **Operational Summary Strip**: Real-time counts of active threats, monitored routes, compromised routes, pending operator decisions, and active evidence records.
- **7-Stage Explainable Decision Chain**:
  1. `Observation received`: Telemetry ingested from field sensors or video.
  2. `Evidence linked`: Canonical evidence record established with provenance.
  3. `Threat identified`: Category, severity, source, and confidence assigned.
  4. `Route impact assessed`: Active route evaluated against threat buffer zones.
  5. `Alternative generated`: Safe detour computed avoiding hazard zones.
  6. `Operator decision`: Human commander **APPROVE** or **REJECT** review.
  7. `Outcome recorded`: Audit log entry persisted to SQLite database.
- **Active Mission Panel**: Shows current route vs. proposed alternative with delta metrics (distance, travel time, heuristic hazard score, threat zones avoided).
- **Threat Queue & Evidence Inspector**: Interactive queue of active threats; selecting any threat displays its linked evidence card, source confidence, and timeline.
- **Ad-Hoc Tactical Route Planner**: Point-to-point planner allowing operators to click any origin and destination on the map to evaluate safety scores ($0$–$100$).

### 5.3 Technical Aspects & Algorithms
- **Road Network Graph Representation**:
  - Loaded via **OSMnx / NetworkX** from local OpenStreetMap XML/Protobuf graphs into a directed multigraph $G = (V, E)$.
  - Edges contain length ($m$), road type (`highway`), speed limit, and one-way constraints.
- **Threat-Aware Pathfinding Algorithm**:
  - Modified Dijkstra / $A^*$ algorithm with dynamic penalty edge weights:
    $$w'(e) = \text{length}(e) \times \left(1 + \sum_{t \in T_{\text{active}}} P(e, t)\right)$$
  - Where $P(e, t)$ is the penalty imposed by threat $t$:
    - For `CRITICAL` threats: Hard exclusion (edge weight set to $\infty$; edge pruned from traversal).
    - For `HIGH` threats: Penalty multiplier $10\text{x}$.
    - For `MEDIUM` threats: Penalty multiplier $3\text{x}$.
  - Threat buffer geometry: Buffer zone radius $R_{\text{threat}} + 25\text{ m}$ buffer margin.
- **Route Compromise Detection (`route_monitor.py`)**:
  - Converts active mission polyline into a shapely `LineString`.
  - For each active threat, constructs a circular spatial polygon $\text{buffer}(\text{Point}(\text{lat}, \text{lon}), R)$.
  - Evaluates spatial intersection:
    $$\text{LineString} \cap \text{Polygon} \neq \emptyset \implies \text{Route Status: INVALIDATED}$$
- **No-Safe-Route Integrity**:
  - If all navigable road corridors are blocked by critical threat exclusion zones, the system returns `NO_SAFE_AVAILABLE_ROUTE` rather than inventing an unsafe path.

---

## 6. Page 5: Incident Review & Tactical Dispatch

### 6.1 Purpose & Role
**Incident Review** coordinates incident lifecycle management, emergency response planning, and multi-agency field unit dispatching (Quick Reaction Teams, ambulances, fire tenders, combat engineers).

### 6.2 Functional Capabilities
- **Incident Registry**: Filterable catalog of active incidents by severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) and lifecycle stage (`NEW`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`).
- **Response Plan Generator**: Generates resource allocation plans recommending appropriate unit types based on incident classification.
- **Field Unit Status Machine**: Tracks operational field teams through valid status transitions:
  $$\text{AVAILABLE} \longrightarrow \text{ASSIGNED} \longrightarrow \text{EN\_ROUTE} \longrightarrow \text{AT\_SCENE} \longrightarrow \text{OPERATING} \longrightarrow \text{COMPLETED} \longrightarrow \text{AVAILABLE}$$
- **Dispatch Action Modal**: Allows operators to execute simulated field dispatches, assigning specific units to active incidents.

### 6.3 Technical Aspects & Algorithms
- **Finite State Machine (FSM) Enforcement**:
  - Validates all status updates in the backend (`/api/national/field-units/{id}/status`).
  - Rejects illegal state jumps (e.g., jumping from `AVAILABLE` directly to `COMPLETED`).
- **Response Plan Rule Matrix**:
  - Maps incident categories to required capability vectors:
    - Coastal Intrusion $\implies$ `QRF_TEAM` (Quick Reaction Force)
    - Structural Fire / Blast $\implies$ `FIRE_TENDER` + `AMBULANCE`
    - Road Inundation / Obstacle $\implies$ `COMBAT_ENGINEERS` (EOD/Sappers)

---

## 7. Page 6: System Status & Diagnostic Observability

### 7.1 Purpose & Role
**System Status** provides transparency and diagnostic observability across all platform subsystems, machine learning pipelines, GIS engines, and sensor feeds. It ensures commanders and technical evaluators know exactly which data sources are live, simulated, or offline.

### 7.2 Functional Capabilities
- **Subsystem Health Grid**: Real-time status cards for FastAPI Backend, OSM Road Graph, CartoDEM Terrain Engine, Weather Provider, Multimodal Vision Pipeline, and Maritime Network Graph.
- **Data Source Truth Matrix**: Transparently labels every data source:
  - `LIVE`: Verified active connection (FastAPI, OSMnx, Maritime Graph).
  - `SIMULATED`: Explicitly simulated scenario feeds (threat queue, sensor reports).
  - `CONTROLLED`: Fixed test scenarios for reproducible evaluation.
  - `UNAVAILABLE`: Graceful fallbacks when offline or missing optional files.
- **GIS Graph Diagnostics**: Node count, edge count, memory footprint, and geographic coverage boundaries.
- **Vision Model Provenance**: Device target (CPU / CUDA), YOLOv8 model loading status, and active class configurations.

### 7.3 Technical Aspects & Algorithms
- **Deterministic Status Probes**: Derived purely from in-memory service state without making blocking outbound network requests during health checks.
- **Graceful Degradation Pattern**: The system remains operational even if optional heavy dependencies (e.g., PyTorch vision models or CartoDEM raster tiles) are missing, falling back to simulated telemetry and documented limitation alerts.

---

## 8. Cross-Cutting Algorithmic & Mathematical Models

| Domain | Algorithm / Formula | Application | Complexity / Equation |
| :--- | :--- | :--- | :--- |
| **Maritime Routing** | Dijkstra's Shortest Path | Finding shortest deepwater corridor | $O((|E| + |V|) \log |V|)$ |
| **Geodesic Distance** | Haversine Formula | Nautical mile calculations across Earth | $d = 2R \arcsin(\sqrt{\sin^2(\Delta\phi/2) + \dots})$ |
| **Computer Vision** | Deep CNN (YOLOv8) | Object detection (vessels, fire, missiles) | $\text{Conv2D} + \text{C2f} + \text{SPPF} + \text{Detect}$ |
| **Target Tracking** | ByteTrack + Kalman Filter | Persistent ID tracking across video frames | State: $[x, y, a, h, \dot{x}, \dot{y}, \dot{a}, \dot{h}]^T$ |
| **Trajectory Match** | Hungarian Algorithm | Bipartite matching on detection IoU | $O(N^3)$ matching cost minimization |
| **Road Pathfinding** | Threat-Penalized $A^*$ | Threat avoidance in evacuation routing | $f(n) = g(n) + h(n) + \text{threat\_penalties}$ |
| **Spatial Proximity** | Spatial Buffer Intersection | Invalidation of routes intersecting hazard zones | $\text{LineString} \cap \text{buffer}(\text{Threat}, r) \neq \emptyset$ |
| **C2 State Machine** | Finite State Machine (FSM) | Field unit dispatch lifecycle validation | Directed graph transition validation |

---

## 9. Data Integrity, Security & Defense Compliance

1. **Human-in-the-Loop Governance**: AI models never take irreversible kinetic or tactical dispatch actions autonomously. All AI detections and automated route recommendations require explicit commander **APPROVE / REJECT** sign-off.
2. **Audit Logging & Provenance**: Every route replacement, threat creation, and operator decision is recorded in an SQLite database with timestamp, operator ID, and rationale.
3. **Keyless Open Architecture**: The nautical and tactical maps run entirely on open OpenStreetMap tiles, requiring no paid API keys, tokens, or external vendor lock-in.
4. **Offline Air-Gapped Readiness**: All core pathfinding algorithms, maritime networks, and demonstration datasets run locally on the edge workstation without requiring continuous Internet connectivity.
5. **Clear Ethical Labeling**: All synthetic demonstration data is explicitly watermarked as `SIMULATED` or `HISTORICAL ARCHIVE`, ensuring simulated alerts are never mistaken for real-world tactical emergencies.

---

*AEGIS-COP Technical Guide · Prepared for HackFest 2026 Evaluation*
