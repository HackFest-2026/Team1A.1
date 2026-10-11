import os
import csv
import io
import math
import json
import heapq
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Earth radius in Nautical Miles (1 NM = 1.852 km; 6371 / 1.852 ~= 3440.065 NM)
EARTH_RADIUS_NM = 3440.065

def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in Nautical Miles."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_NM * c

# Standard column aliases for flexible CSV ingestion
COLUMN_ALIASES = {
    "mmsi": ["mmsi", "MMSI", "vessel_mmsi", "vessel_id", "VesselMMSI", "mmsi_number"],
    "timestamp": ["timestamp", "BaseDateTime", "datetime", "DateTime", "time", "Time", "date_time", "Date_Time", "TIMESTAMP", "msg_time", "observed_at"],
    "lat": ["lat", "LAT", "latitude", "Latitude", "LATITUDE", "y", "Y"],
    "lon": ["lon", "LON", "longitude", "Longitude", "LONGITUDE", "lng", "LNG", "x", "X"],
    "sog": ["sog", "SOG", "speed", "Speed", "SPEED", "speed_over_ground", "speed_kts"],
    "cog": ["cog", "COG", "course", "Course", "COURSE", "course_over_ground"],
    "heading": ["heading", "Heading", "HEADING", "true_heading", "hdg", "HDG"],
    "ship_name": ["ship_name", "ShipName", "vessel_name", "VesselName", "NAME", "name", "vessel"],
    "ship_type": ["ship_type", "ShipType", "vessel_type", "VesselType", "TYPE", "type", "cargo_type"]
}

class MaritimeAISService:
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            # Check root workspace (4 levels up from this file) or backend dir
            cur_file = os.path.abspath(__file__)
            dir_services = os.path.dirname(cur_file)
            dir_app = os.path.dirname(dir_services)
            dir_backend = os.path.dirname(dir_app)
            dir_root = os.path.dirname(dir_backend)
            
            candidates = [
                os.path.join(dir_root, "data", "maritime"),
                os.path.join(dir_backend, "data", "maritime"),
                os.path.join(os.getcwd(), "data", "maritime")
            ]
            self.data_dir = candidates[0]
            for c in candidates:
                if os.path.exists(c):
                    self.data_dir = c
                    break
        else:
            self.data_dir = data_dir

        self.records: List[Dict[str, Any]] = []
        self.vessels_by_mmsi: Dict[str, Dict[str, Any]] = {}
        self.import_metadata: Dict[str, Any] = {
            "source": "None",
            "imported_at": None,
            "total_rows": 0,
            "valid_rows": 0,
            "rejected_rows": 0,
            "vessel_count": 0,
            "bounding_box": None,
            "time_range": None,
            "vessel_types": [],
            "rejections_sample": []
        }

        # Maritime Routing Graph
        self.network_nodes: Dict[str, Dict[str, Any]] = {}
        self.network_adj: Dict[str, List[Tuple[str, float]]] = {}
        self.load_network_graph()

        # Try to preload sample dataset if present
        self.preload_sample_dataset()

    def load_network_graph(self):
        """Loads the verified navigable topological maritime graph."""
        network_path = os.path.join(self.data_dir, "maritime_network.json")
        if os.path.exists(network_path):
            try:
                with open(network_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.network_nodes = data.get("nodes", {})
                    connections = data.get("connections", [])
                    
                    self.network_adj = {node_id: [] for node_id in self.network_nodes}
                    for n1, n2 in connections:
                        if n1 in self.network_nodes and n2 in self.network_nodes:
                            p1 = self.network_nodes[n1]
                            p2 = self.network_nodes[n2]
                            dist_nm = haversine_nm(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
                            self.network_adj[n1].append((n2, dist_nm))
                            self.network_adj[n2].append((n1, dist_nm))
                    logger.info("Loaded maritime network graph: %d nodes, %d connections", len(self.network_nodes), len(connections))
                    return
            except Exception as e:
                logger.error("Failed to load maritime network JSON: %s", e)

        # Fallback embedded minimal graph if file is missing
        self.network_nodes = {
            "mumbai": {"id": "mumbai", "name": "Port of Mumbai", "type": "PORT", "country": "India", "lat": 18.9438, "lon": 72.8656},
            "wp_mumbai_offshore": {"id": "wp_mumbai_offshore", "name": "Mumbai Offshore", "type": "WAYPOINT", "country": "International Waters", "lat": 18.9000, "lon": 72.4000},
            "wp_goa_offshore": {"id": "wp_goa_offshore", "name": "Goa Offshore Corridor", "type": "WAYPOINT", "country": "International Waters", "lat": 15.4000, "lon": 73.3000},
            "marmagao": {"id": "marmagao", "name": "Marmagao Port (Goa)", "type": "PORT", "country": "India", "lat": 15.4100, "lon": 73.7900},
            "kochi": {"id": "kochi", "name": "Cochin / Kochi Port", "type": "PORT", "country": "India", "lat": 9.9667, "lon": 76.2667},
            "wp_kochi_offshore": {"id": "wp_kochi_offshore", "name": "Kochi Fairway Corridor", "type": "WAYPOINT", "country": "International Waters", "lat": 9.9500, "lon": 75.7000},
            "colombo": {"id": "colombo", "name": "Port of Colombo", "type": "PORT", "country": "Sri Lanka", "lat": 6.9400, "lon": 79.8400},
            "wp_colombo_offshore": {"id": "wp_colombo_offshore", "name": "Colombo Outer Fairway", "type": "WAYPOINT", "country": "International Waters", "lat": 6.9500, "lon": 79.4000},
            "chennai": {"id": "chennai", "name": "Chennai Port", "type": "PORT", "country": "India", "lat": 13.0827, "lon": 80.2900},
            "wp_chennai_offshore": {"id": "wp_chennai_offshore", "name": "Chennai Approach Corridor", "type": "WAYPOINT", "country": "International Waters", "lat": 13.1000, "lon": 80.6000}
        }
        self.network_adj = {k: [] for k in self.network_nodes}
        conns = [
            ("mumbai", "wp_mumbai_offshore"),
            ("wp_mumbai_offshore", "wp_goa_offshore"),
            ("wp_goa_offshore", "marmagao"),
            ("wp_goa_offshore", "wp_kochi_offshore"),
            ("wp_kochi_offshore", "kochi"),
            ("wp_kochi_offshore", "wp_colombo_offshore"),
            ("wp_colombo_offshore", "colombo"),
            ("wp_colombo_offshore", "wp_chennai_offshore"),
            ("wp_chennai_offshore", "chennai")
        ]
        for n1, n2 in conns:
            dist = haversine_nm(self.network_nodes[n1]["lat"], self.network_nodes[n1]["lon"],
                                self.network_nodes[n2]["lat"], self.network_nodes[n2]["lon"])
            self.network_adj[n1].append((n2, dist))
            self.network_adj[n2].append((n1, dist))

    def preload_sample_dataset(self):
        """Preloads the bundled demonstration AIS dataset if available."""
        sample_path = os.path.join(self.data_dir, "sample_ais_historical.csv")
        if os.path.exists(sample_path):
            try:
                with open(sample_path, "r", encoding="utf-8") as f:
                    self.import_csv_content(f.read(), source_name="Bundled Demonstration AIS Dataset (Arabian Sea / Indian Ocean)")
                logger.info("Preloaded demonstration AIS dataset (%d records)", len(self.records))
            except Exception as e:
                logger.warning("Could not preload sample AIS dataset: %s", e)

    @staticmethod
    def parse_timestamp(val: Any) -> Optional[str]:
        """Parses various timestamp strings into ISO 8601 UTC format."""
        if not val:
            return None
        val_str = str(val).strip()
        if not val_str:
            return None

        # Clean trailing 'Z' or offset if needed
        formats = [
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y/%m/%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d"
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(val_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.isoformat()
            except ValueError:
                continue

        # Try fromisoformat fallback (Python 3.11+)
        try:
            dt = datetime.fromisoformat(val_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass

        return None

    def map_columns(self, header_row: List[str]) -> Dict[str, int]:
        """Finds matching column indices for standard schema fields."""
        normalized_headers = [h.strip() for h in header_row]
        mapping: Dict[str, int] = {}

        for field, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                # Exact match first
                for idx, h in enumerate(normalized_headers):
                    if h.lower() == alias.lower():
                        mapping[field] = idx
                        break
                if field in mapping:
                    break

        return mapping

    def import_csv_content(self, csv_text: str, source_name: str = "Uploaded CSV") -> Dict[str, Any]:
        """Validates and imports an AIS CSV dataset."""
        f = io.StringIO(csv_text.strip())
        reader = csv.reader(f)

        try:
            header = next(reader)
        except StopIteration:
            raise ValueError("CSV file is empty")

        col_map = self.map_columns(header)
        required_fields = ["mmsi", "lat", "lon"]
        missing_required = [f for f in required_fields if f not in col_map]
        if missing_required:
            raise ValueError(
                f"Missing required columns in CSV: {missing_required}. "
                f"Detected headers: {header}"
            )

        valid_records: List[Dict[str, Any]] = []
        rejections: List[str] = []
        row_num = 1  # 1 is header

        min_lat, max_lat = 90.0, -90.0
        min_lon, max_lon = 180.0, -180.0
        min_time, max_time = None, None
        vessel_map: Dict[str, Dict[str, Any]] = {}
        vessel_types_set = set()

        for row in reader:
            row_num += 1
            if not row or all(not cell.strip() for cell in row):
                continue

            try:
                # 1. MMSI
                raw_mmsi = row[col_map["mmsi"]].strip()
                if not raw_mmsi:
                    if len(rejections) < 20:
                        rejections.append(f"Row {row_num}: Missing MMSI identifier")
                    continue
                mmsi = str(raw_mmsi)

                # 2. Coordinates
                lat_str = row[col_map["lat"]].strip()
                lon_str = row[col_map["lon"]].strip()
                try:
                    lat = float(lat_str)
                    lon = float(lon_str)
                except ValueError:
                    if len(rejections) < 20:
                        rejections.append(f"Row {row_num}: Non-numeric coordinates (lat: '{lat_str}', lon: '{lon_str}')")
                    continue

                if not (-90.0 <= lat <= 90.0):
                    if len(rejections) < 20:
                        rejections.append(f"Row {row_num}: Latitude out of range [-90, 90]: {lat}")
                    continue
                if not (-180.0 <= lon <= 180.0):
                    if len(rejections) < 20:
                        rejections.append(f"Row {row_num}: Longitude out of range [-180, 180]: {lon}")
                    continue

                # 3. Timestamp
                timestamp_str = None
                if "timestamp" in col_map and col_map["timestamp"] < len(row):
                    raw_ts = row[col_map["timestamp"]].strip()
                    timestamp_str = self.parse_timestamp(raw_ts)

                if not timestamp_str:
                    # If timestamp is missing or unparseable, reject row
                    if len(rejections) < 20:
                        rejections.append(f"Row {row_num}: Invalid or missing timestamp in row")
                    continue

                # 4. SOG (Speed over ground, in knots)
                sog = None
                if "sog" in col_map and col_map["sog"] < len(row):
                    sog_val = row[col_map["sog"]].strip()
                    if sog_val != "":
                        try:
                            s = float(sog_val)
                            if 0.0 <= s <= 105.0:
                                sog = round(s, 2)
                        except ValueError:
                            pass

                # 5. COG (Course over ground, 0-360)
                cog = None
                if "cog" in col_map and col_map["cog"] < len(row):
                    cog_val = row[col_map["cog"]].strip()
                    if cog_val != "":
                        try:
                            c = float(cog_val)
                            if 0.0 <= c <= 360.0:
                                cog = round(c, 1)
                        except ValueError:
                            pass

                # 6. Heading (0-360)
                heading = None
                if "heading" in col_map and col_map["heading"] < len(row):
                    hdg_val = row[col_map["heading"]].strip()
                    if hdg_val != "":
                        try:
                            h = float(hdg_val)
                            if 0.0 <= h <= 360.0:
                                heading = round(h, 1)
                        except ValueError:
                            pass

                # 7. Ship name & type
                ship_name = None
                if "ship_name" in col_map and col_map["ship_name"] < len(row):
                    sn = row[col_map["ship_name"]].strip()
                    if sn:
                        ship_name = sn

                ship_type = None
                if "ship_type" in col_map and col_map["ship_type"] < len(row):
                    st = row[col_map["ship_type"]].strip()
                    if st:
                        ship_type = st
                        vessel_types_set.add(st)

                record = {
                    "mmsi": mmsi,
                    "timestamp": timestamp_str,
                    "lat": round(lat, 5),
                    "lon": round(lon, 5),
                    "sog": sog,
                    "cog": cog,
                    "heading": heading,
                    "ship_name": ship_name,
                    "ship_type": ship_type
                }
                valid_records.append(record)

                # Update bounding box
                min_lat = min(min_lat, lat)
                max_lat = max(max_lat, lat)
                min_lon = min(min_lon, lon)
                max_lon = max(max_lon, lon)

                # Update time bounds
                if min_time is None or timestamp_str < min_time:
                    min_time = timestamp_str
                if max_time is None or timestamp_str > max_time:
                    max_time = timestamp_str

                # Update vessel stats
                if mmsi not in vessel_map:
                    vessel_map[mmsi] = {
                        "mmsi": mmsi,
                        "ship_name": ship_name or f"VESSEL-{mmsi[-4:]}",
                        "ship_type": ship_type or "Unknown",
                        "observation_count": 0,
                        "first_seen": timestamp_str,
                        "last_seen": timestamp_str,
                        "latest_position": record
                    }
                v_entry = vessel_map[mmsi]
                v_entry["observation_count"] += 1
                if ship_name and (v_entry["ship_name"].startswith("VESSEL-") or not v_entry["ship_name"]):
                    v_entry["ship_name"] = ship_name
                if ship_type and v_entry["ship_type"] == "Unknown":
                    v_entry["ship_type"] = ship_type
                if timestamp_str > v_entry["last_seen"]:
                    v_entry["last_seen"] = timestamp_str
                    v_entry["latest_position"] = record
                if timestamp_str < v_entry["first_seen"]:
                    v_entry["first_seen"] = timestamp_str

            except Exception as e:
                if len(rejections) < 20:
                    rejections.append(f"Row {row_num}: Parsing exception - {str(e)}")

        total_rows = row_num - 1
        valid_count = len(valid_records)
        rejected_count = total_rows - valid_count

        if valid_count == 0:
            raise ValueError(f"No valid AIS records found in dataset. Total rows: {total_rows}. Errors: {rejections[:5]}")

        # Store in state
        self.records = valid_records
        self.vessels_by_mmsi = vessel_map

        bbox = {
            "min_lat": round(min_lat, 4),
            "max_lat": round(max_lat, 4),
            "min_lon": round(min_lon, 4),
            "max_lon": round(max_lon, 4)
        }

        self.import_metadata = {
            "source": source_name,
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "total_rows": total_rows,
            "valid_rows": valid_count,
            "rejected_rows": rejected_count,
            "vessel_count": len(vessel_map),
            "bounding_box": bbox,
            "time_range": {"min_time": min_time, "max_time": max_time},
            "vessel_types": sorted(list(vessel_types_set)),
            "rejections_sample": rejections,
            "is_historical": True,
            "timezone_note": "Timestamps normalized to UTC (ISO 8601). Displayed in operator's local/IST time."
        }

        return self.import_metadata

    def get_summary(self) -> Dict[str, Any]:
        """Returns import statistics and dataset status."""
        return self.import_metadata

    def list_vessels(
        self,
        search: Optional[str] = None,
        ship_type: Optional[str] = None,
        min_lat: Optional[float] = None,
        max_lat: Optional[float] = None,
        min_lon: Optional[float] = None,
        max_lon: Optional[float] = None,
        limit: int = 200
    ) -> List[Dict[str, Any]]:
        """List tracked vessels matching criteria."""
        results = []
        search_lower = search.lower() if search else None
        type_lower = ship_type.lower() if ship_type else None

        for v in self.vessels_by_mmsi.values():
            if search_lower:
                mmsi_match = search_lower in v["mmsi"].lower()
                name_match = v["ship_name"] and search_lower in v["ship_name"].lower()
                if not (mmsi_match or name_match):
                    continue

            if type_lower and type_lower != "all":
                if not v["ship_type"] or type_lower not in v["ship_type"].lower():
                    continue

            pos = v["latest_position"]
            if min_lat is not None and pos["lat"] < min_lat:
                continue
            if max_lat is not None and pos["lat"] > max_lat:
                continue
            if min_lon is not None and pos["lon"] < min_lon:
                continue
            if max_lon is not None and pos["lon"] > max_lon:
                continue

            results.append(v)
            if len(results) >= limit:
                break

        return results

    def get_positions(
        self,
        mmsi: Optional[str] = None,
        ship_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        min_lat: Optional[float] = None,
        max_lat: Optional[float] = None,
        min_lon: Optional[float] = None,
        max_lon: Optional[float] = None,
        limit: int = 1000,
        sample_step: int = 1
    ) -> Dict[str, Any]:
        """Returns filtered observations suitable for map display."""
        filtered = []
        step_counter = 0

        for r in self.records:
            if mmsi and r["mmsi"] != mmsi:
                continue
            if ship_type and ship_type.lower() != "all":
                if not r["ship_type"] or ship_type.lower() not in r["ship_type"].lower():
                    continue
            if start_time and r["timestamp"] < start_time:
                continue
            if end_time and r["timestamp"] > end_time:
                continue
            if min_lat is not None and r["lat"] < min_lat:
                continue
            if max_lat is not None and r["lat"] > max_lat:
                continue
            if min_lon is not None and r["lon"] < min_lon:
                continue
            if max_lon is not None and r["lon"] > max_lon:
                continue

            step_counter += 1
            if step_counter % max(1, sample_step) != 0:
                continue

            filtered.append(r)
            if len(filtered) >= limit:
                break

        return {
            "total_matching": len(filtered),
            "sampled_step": sample_step,
            "positions": filtered
        }

    def get_vessel_track(self, mmsi: str, max_gap_hours: float = 6.0) -> Dict[str, Any]:
        """
        Retrieves chronological observations for one vessel.
        Deduplicates timestamps and detects large time gaps so polyline rendering does not
        draw misleading straight lines across huge gaps.
        """
        v_records = [r for r in self.records if r["mmsi"] == mmsi]
        if not v_records:
            return {
                "mmsi": mmsi,
                "found": False,
                "total_points": 0,
                "points": [],
                "segments": [],
                "total_distance_nm": 0.0,
                "error": f"No AIS observations recorded for vessel MMSI {mmsi}"
            }

        # Deduplicate identical timestamps keeping the one with more complete telemetry
        unique_by_time: Dict[str, Dict[str, Any]] = {}
        for r in v_records:
            ts = r["timestamp"]
            if ts not in unique_by_time:
                unique_by_time[ts] = r
            else:
                existing = unique_by_time[ts]
                # If existing has null sog/cog but new one has it, replace
                if (existing.get("sog") is None and r.get("sog") is not None) or \
                   (existing.get("heading") is None and r.get("heading") is not None):
                    unique_by_time[ts] = r

        # Chronological sort
        sorted_obs = sorted(unique_by_time.values(), key=lambda x: x["timestamp"])

        total_distance_nm = 0.0
        points_with_telemetry = []
        segments: List[List[Dict[str, Any]]] = []
        current_segment: List[Dict[str, Any]] = []

        last_dt = None
        last_lat, last_lon = None, None

        for idx, obs in enumerate(sorted_obs):
            curr_dt = datetime.fromisoformat(obs["timestamp"].replace("Z", "+00:00"))
            gap_break = False

            if last_dt is not None:
                delta_hours = (curr_dt - last_dt).total_seconds() / 3600.0
                if delta_hours > max_gap_hours:
                    gap_break = True
                    if current_segment:
                        segments.append(current_segment)
                        current_segment = []

                step_dist = haversine_nm(last_lat, last_lon, obs["lat"], obs["lon"])
                if not gap_break:
                    total_distance_nm += step_dist

            point_entry = {
                **obs,
                "index": idx,
                "gap_break": gap_break,
                "cumulative_dist_nm": round(total_distance_nm, 2)
            }
            points_with_telemetry.append(point_entry)
            current_segment.append(point_entry)

            last_dt = curr_dt
            last_lat, last_lon = obs["lat"], obs["lon"]

        if current_segment:
            segments.append(current_segment)

        v_info = self.vessels_by_mmsi.get(mmsi, {})

        return {
            "mmsi": mmsi,
            "found": True,
            "ship_name": v_info.get("ship_name", sorted_obs[0].get("ship_name") or f"MMSI-{mmsi}"),
            "ship_type": v_info.get("ship_type", sorted_obs[0].get("ship_type") or "Unknown"),
            "total_points": len(points_with_telemetry),
            "total_distance_nm": round(total_distance_nm, 2),
            "segment_count": len(segments),
            "first_observed": sorted_obs[0]["timestamp"],
            "last_observed": sorted_obs[-1]["timestamp"],
            "points": points_with_telemetry,
            # Segments contains polyline coordinate arrays [[ [lat, lon], ... ], ...]
            "segment_coordinates": [
                [[p["lat"], p["lon"]] for p in seg] for seg in segments
            ]
        }

    def list_ports(self) -> List[Dict[str, Any]]:
        """Returns verified ports and key waypoints available for route planning."""
        ports = []
        for node_id, data in self.network_nodes.items():
            ports.append({
                "id": node_id,
                "name": data["name"],
                "type": data["type"],
                "country": data.get("country", "International"),
                "lat": data["lat"],
                "lon": data["lon"]
            })
        # Sort ports first, then waypoints
        ports.sort(key=lambda x: (0 if x["type"] == "PORT" else 1, x["name"]))
        return ports

    def plan_sea_route(
        self,
        origin_id: str,
        destination_id: str,
        speed_knots: Optional[float] = 14.0
    ) -> Dict[str, Any]:
        """
        Calculates shortest navigable sea route between origin and destination using Dijkstra's algorithm.
        Edge weights are geodesic distances in Nautical Miles.
        """
        orig_key = origin_id.lower().strip()
        dest_key = destination_id.lower().strip()

        if orig_key not in self.network_nodes:
            raise ValueError(f"Origin port or waypoint '{origin_id}' not found in maritime graph.")
        if dest_key not in self.network_nodes:
            raise ValueError(f"Destination port or waypoint '{destination_id}' not found in maritime graph.")
        if orig_key == dest_key:
            raise ValueError("Origin and destination must be distinct ports.")

        # Dijkstra algorithm
        distances: Dict[str, float] = {node: float("inf") for node in self.network_nodes}
        previous: Dict[str, Optional[str]] = {node: None for node in self.network_nodes}
        distances[orig_key] = 0.0

        pq: List[Tuple[float, str]] = [(0.0, orig_key)]

        while pq:
            curr_dist, curr_node = heapq.heappop(pq)
            if curr_dist > distances[curr_node]:
                continue
            if curr_node == dest_key:
                break

            for neighbor, weight in self.network_adj.get(curr_node, []):
                new_dist = curr_dist + weight
                if new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    previous[neighbor] = curr_node
                    heapq.heappush(pq, (new_dist, neighbor))

        if distances[dest_key] == float("inf"):
            raise ValueError(
                f"No connected navigable sea route found between '{self.network_nodes[orig_key]['name']}' "
                f"and '{self.network_nodes[dest_key]['name']}' in the configured maritime graph."
            )

        # Reconstruct path
        path_ids: List[str] = []
        curr = dest_key
        while curr is not None:
            path_ids.append(curr)
            curr = previous[curr]
        path_ids.reverse()

        waypoints_info = []
        coordinates = []
        for pid in path_ids:
            nd = self.network_nodes[pid]
            waypoints_info.append({
                "id": pid,
                "name": nd["name"],
                "type": nd["type"],
                "country": nd.get("country", "International"),
                "lat": nd["lat"],
                "lon": nd["lon"]
            })
            coordinates.append([nd["lat"], nd["lon"]])

        total_distance_nm = round(distances[dest_key], 2)

        duration_hours = None
        duration_days = None
        if speed_knots and speed_knots > 0:
            duration_hours = round(total_distance_nm / speed_knots, 1)
            duration_days = round(duration_hours / 24.0, 1)

        return {
            "status": "SUCCESS",
            "origin": self.network_nodes[orig_key],
            "destination": self.network_nodes[dest_key],
            "total_distance_nm": total_distance_nm,
            "vessel_speed_knots": speed_knots,
            "estimated_hours": duration_hours,
            "estimated_days": duration_days,
            "waypoint_count": len(waypoints_info),
            "waypoints": waypoints_info,
            "coordinates": coordinates,
            "routing_objective": "SHORTEST_NAVIGABLE_DISTANCE",
            "disclaimer": (
                "PROTOTYPE MARITIME ROUTE: Computed over verified deepwater topological sea lanes. "
                "This prototype does NOT account for dynamic bathymetry, real-time draft restrictions, "
                "tides, Traffic Separation Schemes (TSS), prevailing currents, weather routing, "
                "or restricted naval exclusion zones. Authoritative navigation requires ECDIS and official charts."
            )
        }

# Singleton instance
maritime_ais_service = MaritimeAISService()
