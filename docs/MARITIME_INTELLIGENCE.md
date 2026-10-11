# Maritime Intelligence & AIS Tracking — User & Architecture Guide

## 1. Overview
The **Maritime Intelligence** module is an advanced coastal surveillance, historical AIS tracking, and sea-route planning capability added to the AEGIS-COP platform. It provides maritime situational awareness for the Indian Ocean, Arabian Sea, and Bay of Bengal sectors while keeping all existing emergency operations, threat detection, video intelligence, and road-routing services fully operational.

---

## 2. Core Features

### A. Historical AIS Dataset Import
- **CSV Import Support**: Ingest historical vessel observation archives via file upload or single-click demonstration dataset loading.
- **Header Normalization**: Automatically normalizes varied column naming conventions across different international AIS datasets:
  - **MMSI**: `mmsi`, `MMSI`, `vessel_mmsi`, `vessel_id`
  - **Timestamp**: `timestamp`, `BaseDateTime`, `datetime`, `date_time`, `TIMESTAMP`
  - **Coordinates**: `lat` / `LAT` / `latitude`, `lon` / `LON` / `longitude`
  - **Telemetry**: `sog` / `SOG` / `speed` (knots), `cog` / `COG` / `course` (degrees), `heading`
  - **Metadata**: `ship_name` / `VesselName`, `ship_type` / `VesselType`
- **Validation & Diagnostics**: Rejects invalid coordinates (outside `[-90, 90]` or `[-180, 180]`), corrupt timestamps, or non-numeric telemetry without crashing. Reports rejected row counts and diagnostic error messages.
- **Dynamic Bounding Box**: Detects and displays the actual geographic coverage bounding box from imported data (never hardcodes geographic assumptions).

### B. Vessel Tracking on the Nautical Map
- Renders vessel markers color-coded by ship category:
  - ⚓ **Naval & Coast Guard / Patrol**: Saffron (`#FF9933`)
  - 🛢️ **Crude Tanker / Liquid Cargo**: Coral Red (`#EF4444`)
  - 🚢 **Commercial Cargo / Container**: Ocean Blue (`#3B82F6`)
  - 🐟 **Deep Sea Fishing Craft**: Emerald Green (`#10B981`)
  - 🔬 **Research / Survey**: Purple (`#8B5CF6`)
- Rotates vessel markers by Course Over Ground (COG).
- Displays vessel details, speed over ground, true heading, and timestamps in popup inspectors.

### C. Historical Vessel Track Playback
- Groups observations by MMSI and sorts chronologically.
- Resolves duplicate timestamps and reconstructs movement trajectories.
- **Time Gap Detection**: Detects large time gaps (> 6 hours) and breaks polylines into distinct segments to prevent misleading straight lines across data outages.
- **Interactive Controls**: Play, Pause, Reset, scrubbable timeline slider, and speed multipliers (`1x`, `2x`, `5x`, `10x`).
- Dynamic pulsing vessel position marker advancing along the track with real-time telemetry display.

### D. Topological Maritime Sea-Route Planner
- Graph-based routing algorithm (**Dijkstra**) calculating shortest navigable sea routes over validated deepwater corridors in Nautical Miles ($1\text{ NM} \approx 1.852\text{ km}$).
- Connects verified Indian Ocean ports (e.g. Mumbai, Marmagao, Mangalore, Kochi, Tuticorin, Colombo, Galle, Chennai, Visakhapatnam, Paradip, Haldia, Port Blair, Singapore, Karachi, Salalah, Djibouti).
- Avoids land crossings by routing strictly through verified maritime corridors and pilot fairway waypoints.
- Calculates total nautical distance, estimated transit time in days and hours based on vessel cruising speed in knots.

---

## 3. How to Start Backend & Frontend

### Backend (FastAPI)
```powershell
# From project root
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- API Documentation (Swagger): `http://127.0.0.1:8000/docs`
- Health Check: `http://127.0.0.1:8000/api/health`
- Maritime Endpoints: `http://127.0.0.1:8000/api/maritime/ais/summary`

### Frontend (React + Vite)
```powershell
# From project root
cd frontend
npm run dev
```
- Access application in browser: `http://localhost:5173`

---

## 4. How to Use the Feature

1. **Accessing the Workstation**:
   - In the left navigation rail of AEGIS-COP, click on **Maritime Intelligence** (compass icon).
2. **Importing an AIS Dataset**:
   - Click **Import AIS CSV** in the header to upload any custom historical CSV file.
   - Alternatively, click **Load Demo Dataset** to instantly load the bundled Arabian Sea & Indian Ocean demonstration archive.
   - Switch to the **Dataset Diagnostics** sub-tab to inspect total rows, accepted valid rows, rejected rows, and detected geographic bounds.
3. **Filtering & Inspecting Vessels**:
   - In the **AIS Vessels** panel, filter by vessel name, MMSI, or ship type (Cargo, Tanker, Fishing, etc.).
   - Click on any vessel card or map marker to view detailed telemetry.
   - Click **Inspect Track →** to open historical playback.
4. **Playing Back Historical Tracks**:
   - In the **Track Playback** sub-tab, review the total track distance in NM and observation points.
   - Click **▶ PLAY TRACK** to start animated playback.
   - Use the slider to scrub to any historical timestamp $T+n$.
   - Select speed multipliers (`1x`, `2x`, `5x`, `10x`).
5. **Planning a Sea Route**:
   - Switch to the **Sea-Route Planner** sub-tab.
   - Select an **Origin Port** (e.g., *Port of Mumbai / JNPT*) and a **Destination Port** (e.g., *Port of Colombo*).
   - Adjust cruising speed in knots (e.g., 14 kts).
   - Click **CALCULATE SEA ROUTE**.
   - Review total distance in NM, transit duration in days, and ordered fairway waypoints drawn on the nautical chart.

---

## 5. How to Configure the Waypoint Network Graph
The maritime graph is stored in [`data/maritime/maritime_network.json`](file:///c:/Users/Lenovo/Downloads/aegis-cop-backup-master/data/maritime/maritime_network.json).

### Adding a New Port or Sea Waypoint
Add an entry to the `"nodes"` object:
```json
"new_port_id": {
  "id": "new_port_id",
  "name": "Port Name",
  "type": "PORT",
  "country": "India",
  "lat": 15.0000,
  "lon": 73.0000
}
```

### Adding a Navigable Edge
Add a bidirectional connection to the `"connections"` array:
```json
["new_port_id", "adjacent_waypoint_id"]
```
Edge weights are automatically calculated at runtime using geodesic Haversine distance in Nautical Miles.

---

## 6. Critical Distinctions and Limitations

### Historical AIS vs Live AIS
- **Historical AIS**: Records represent timestamped transponder observations broadcast in the past. They reflect historical vessel movements and trajectories.
- **Live AIS / Radar Correlation**: Live tactical contact tracking is handled separately in the Naval Awareness view (`/api/naval`). Historical AIS observations are never misrepresented as real-time live positions.

### Prototype Routing Caveats
- **Topological Deepwater Routes**: The sea-route planner computes the shortest path along validated open-water corridors.
- **What it does NOT validate**:
  - Real-time bathymetric depth / vessel draft clearance.
  - Tidal currents, wind drift, and swell conditions.
  - Dynamic Traffic Separation Schemes (TSS) and port pilotage rules.
  - Restricted military exclusion zones or temporary firing ranges.
- Official navigational planning must always rely on certified ECDIS electronic charts and Admiralty sailing directions.
