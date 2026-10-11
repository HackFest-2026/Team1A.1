import os
import threading
import networkx as nx
import osmnx as ox
from app.config import routing_policy
from app.config.settings import settings
from app.services.terrain_service import terrain_service
from app.services.hazard_scoring import summarize_risks
from app.services.threat.zones import ThreatZoneIndex, active_threat_zones, edge_multiplier, haversine_m


class OutsideCoverageError(Exception):
    """An input coordinate is farther from the loaded road network than MAX_SNAP_DISTANCE_M."""

    def __init__(self, message, details):
        super().__init__(message)
        self.details = details

    def to_dict(self):
        return {"status": "outside_coverage", "code": "OUTSIDE_COVERAGE", "message": str(self), **self.details}


class NoSafeRouteError(Exception):
    """A path exists in the road graph, but none avoids the hard-blocked edges
    (blocking threat zones and/or CRITICAL hazard segments)."""

    def __init__(self, message, blocking_threat_ids=None, blocked_hazard_edges=0, route_mode="STANDARD"):
        super().__init__(message)
        self.blocking_threat_ids = sorted(blocking_threat_ids or [])
        self.blocked_hazard_edges = blocked_hazard_edges
        self.route_mode = route_mode

    def to_dict(self):
        return {
            "status": "no_safe_route",
            "message": str(self),
            "route_mode": self.route_mode,
            "blocking_threat_ids": self.blocking_threat_ids,
            "blocked_hazard_edges": self.blocked_hazard_edges,
        }


class RoutingService:
    def __init__(self):
        self.graph_path = settings.OSM_GRAPH_PATH
        self.G = None
        self.nodes_count = 0
        self.edges_count = 0
        self._load_lock = threading.Lock()

    def load_graph(self):
        """Load the road graph once, even under concurrent requests.

        FastAPI runs sync endpoints in a thread pool. Without the lock, the burst of
        requests on a cold start each loaded the graph (~600 MB apiece), exhausting
        memory. The graph is fully prepared (speeds, travel times) before it is
        published to self.G, so readers never see a half-built graph.
        """
        if self.G is not None:
            return True
        with self._load_lock:
            if self.G is not None:
                return True
            if not os.path.exists(self.graph_path):
                return False
            graph = ox.load_graphml(self.graph_path)
            graph = ox.add_edge_speeds(graph)
            graph = ox.add_edge_travel_times(graph)
            self.nodes_count = len(graph.nodes)
            self.edges_count = len(graph.edges)
            self.G = graph
        return True

    def get_status(self):
        is_loaded = self.load_graph()
        if not is_loaded:
            return {
                "status": "not_ready",
                "graph_available": False
            }
        return {
            "status": "ready",
            "graph_available": True,
            "source": "cached_openstreetmap",
            "region": "Hubballi-Dharwad",
            "nodes": self.nodes_count,
            "edges": self.edges_count
        }

    def nodes_to_geometry(self, node_ids):
        """GeoJSON LineString for a node sequence, or None if the graph or any node is unavailable."""
        if not node_ids or len(node_ids) < 2 or not self.load_graph():
            return None
        coordinates = []
        for node in node_ids:
            if node not in self.G.nodes:
                return None
            node_data = self.G.nodes[node]
            coordinates.append([node_data['x'], node_data['y']])
        return {"type": "LineString", "coordinates": coordinates}

    def snap(self, lat: float, lon: float, label: str = "point", enforce: bool = True):
        """Nearest graph node and its distance in metres.

        With enforce=True, raises OutsideCoverageError when the distance exceeds
        settings.MAX_SNAP_DISTANCE_M instead of silently snapping to a far road.
        """
        if not self.load_graph():
            raise Exception("Graph is missing. Cannot snap coordinate.")
        node = ox.nearest_nodes(self.G, X=lon, Y=lat)
        node_data = self.G.nodes[node]
        dist = haversine_m(lat, lon, node_data['y'], node_data['x'])
        limit = settings.MAX_SNAP_DISTANCE_M
        if enforce and dist > limit:
            raise OutsideCoverageError(
                f"The {label} ({lat:.5f}, {lon:.5f}) is {dist:.0f} m from the nearest road in the "
                f"loaded network; the limit is {limit:.0f} m. The location is outside the supported coverage.",
                {"label": label, "lat": lat, "lon": lon,
                 "nearest_node_distance_m": round(dist, 1), "max_snap_distance_m": limit},
            )
        return node, dist

    def edge_coordinates(self, u, v, data):
        """[lon, lat] coordinates of one edge: OSM geometry when present, else the endpoint nodes."""
        geom = data.get('geometry')
        if geom is not None:
            return [list(c) for c in geom.coords]
        return [[self.G.nodes[u]['x'], self.G.nodes[u]['y']], [self.G.nodes[v]['x'], self.G.nodes[v]['y']]]

    def route_edge_coordinates(self, node_ids):
        """Per-edge coordinates along a node path (fastest parallel edge), or None if unavailable."""
        if not node_ids or len(node_ids) < 2 or not self.load_graph():
            return None
        edges_coords = []
        for u, v in zip(node_ids[:-1], node_ids[1:]):
            if not self.G.has_edge(u, v):
                return None
            edges = self.G[u][v]
            k = min(edges, key=lambda kk: edges[kk].get('travel_time', float('inf')))
            edges_coords.append(self.edge_coordinates(u, v, edges[k]))
        return edges_coords

    def calculate_route(self, origin_lat: float, origin_lon: float, destination_lat: float, destination_lon: float,
                        hazard_aware: bool = False, avoid_threats: bool = True):
        """Shortest travel-time route under the threat-zone policy (ADR-007).

        Edges inside blocking threat zones and (in hazard-aware mode) CRITICAL hazard
        segments are skipped. If that leaves no path while the plain graph has one,
        NoSafeRouteError is raised instead of returning a path through blocked edges.
        """
        if not self.load_graph():
            raise Exception("Graph is missing. Cannot calculate route.")

        orig_node, orig_snap_m = self.snap(origin_lat, origin_lon, "origin")
        dest_node, dest_snap_m = self.snap(destination_lat, destination_lon, "destination")
        route_mode = "HAZARD_AWARE" if hazard_aware else "STANDARD"

        zone_index = ThreatZoneIndex(active_threat_zones() if avoid_threats else [])
        endpoint_points = [(self.G.nodes[n]['y'], self.G.nodes[n]['x']) for n in (orig_node, dest_node)]
        endpoint_zone_ids = {
            z.threat_id for z in zone_index.zones
            if z.is_blocking and any(z.contains_point(lat, lon) for lat, lon in endpoint_points)
        }

        if hazard_aware:
            from .road_hazard_service import road_hazard_service

        edge_cost = {}       # (u, v, k) -> cost, or None when blocked
        edge_threats = {}    # (u, v, k) -> [(zone, distance_m)]
        hazard_details = {}  # (u, v, k) -> hazard summary for hazard-aware mode
        blocking_hits = set()
        blocked_hazard_edges = set()

        def cost_of(u, v, k, d):
            key = (u, v, k)
            if key in edge_cost:
                return edge_cost[key]
            cost = d.get('travel_time', 1.0)  # same default NetworkX applies to a missing weight

            if hazard_aware:
                hazard_info = road_hazard_service.assess_road_segment(u, v, k)
                risk = hazard_info.get("risk", {})
                score = risk.get("score")
                level = risk.get("level", "UNKNOWN")
                # Cost uses the known-component score only: unknown weather/terrain is
                # reported (score_basis, data_gaps) but neither penalised nor treated as safe.
                penalty = 4.0 if level == "CRITICAL" else 4.0 * ((score or 0.0) / 100.0)
                hazard_details[key] = {
                    "u": u, "v": v, "key": k,
                    "hazard_score": score,
                    "hazard_level": level,
                    "score_upper_bound": risk.get("score_upper_bound"),
                    "score_basis": risk.get("score_basis"),
                    "completeness": risk.get("completeness"),
                    "data_gaps": risk.get("data_gaps", []),
                    "terrain_score": hazard_info.get("terrain", {}).get("segment_score"),
                    "weather_score": hazard_info.get("weather", {}).get("score"),
                    "hazard_penalty": penalty,
                }
                if level == "CRITICAL":
                    blocked_hazard_edges.add(key)
                    edge_cost[key] = None
                    return None
                cost = cost * (1.0 + penalty)

            if zone_index:
                hits = zone_index.intersecting(self.edge_coordinates(u, v, d))
                edge_threats[key] = hits
                multiplier = edge_multiplier(hits, endpoint_zone_ids)
                if multiplier is None:
                    blocking_hits.update(z.threat_id for z, _ in hits
                                         if z.is_blocking and z.threat_id not in endpoint_zone_ids)
                    edge_cost[key] = None
                    return None
                cost *= multiplier

            if key in hazard_details:
                hazard_details[key]["dynamic_cost"] = cost
            edge_cost[key] = cost
            return cost

        def weight(u, v, edges):
            # Returning None makes NetworkX skip the edge entirely (hard block).
            best = None
            for k, d in edges.items():
                c = cost_of(u, v, k, d)
                if c is not None and (best is None or c < best):
                    best = c
            return best

        use_plain_weight = not hazard_aware and not zone_index
        try:
            route = nx.shortest_path(self.G, orig_node, dest_node,
                                     weight='travel_time' if use_plain_weight else weight)
        except nx.NetworkXNoPath:
            if (blocking_hits or blocked_hazard_edges) and nx.has_path(self.G, orig_node, dest_node):
                raise NoSafeRouteError(
                    "No route avoids the blocking threat zones and CRITICAL hazard segments.",
                    blocking_threat_ids=blocking_hits,
                    blocked_hazard_edges=len(blocked_hazard_edges),
                    route_mode=route_mode,
                )
            raise Exception("No route exists between the given locations.")

        distance_m = 0
        estimated_time_s = 0
        route_edges = []
        for u, v in zip(route[:-1], route[1:]):
            edges = self.G[u][v]
            if use_plain_weight:
                k = min(edges, key=lambda kk: edges[kk].get('travel_time', 0))
            else:
                usable = [(edge_cost[(u, v, kk)], kk) for kk in edges if edge_cost.get((u, v, kk)) is not None]
                k = min(usable, key=lambda t: t[0])[1]
            edge_data = edges[k]
            distance_m += edge_data.get('length', 0)
            estimated_time_s += edge_data.get('travel_time', 0)
            route_edges.append((u, v, k))

        coordinates = [[self.G.nodes[n]['x'], self.G.nodes[n]['y']] for n in route]

        result = {
            "source": "cached_openstreetmap",
            "route_mode": route_mode,
            "origin": {"lat": origin_lat, "lon": origin_lon},
            "destination": {"lat": destination_lat, "lon": destination_lon},
            "distance_m": round(distance_m, 2),
            "estimated_time_s": round(estimated_time_s, 2),
            "route_nodes": route,
            "route": {"type": "LineString", "coordinates": coordinates},
            "threat_exposure": self._summarize_threat_exposure(
                route_edges, zone_index, edge_threats, endpoint_zone_ids, avoid_threats),
            "coverage": self._route_coverage(route_edges, orig_snap_m, dest_snap_m),
        }

        if hazard_aware:
            segments = [hazard_details.get(key, {}) for key in route_edges]
            scores = [seg.get("hazard_score") or 0.0 for seg in segments]
            critical_segments = sum(1 for seg in segments if seg.get("hazard_level") == "CRITICAL")
            high_risk_segments = sum(1 for seg in segments if seg.get("hazard_level") == "HIGH")
            overall_score = max(scores, default=0.0)
            result["hazard_summary"] = {
                "overall_score": overall_score,
                "overall_level": "CRITICAL" if critical_segments > 0 else ("HIGH" if high_risk_segments > 0 else ("LOW" if overall_score >= 25 else "SAFE")),
                "critical_segments": critical_segments,
                "high_risk_segments": high_risk_segments,
                "lowest_segment_score": min(scores) if scores else 0.0,
                "highest_segment_score": overall_score,
                **summarize_risks(segments),
                "weather": road_hazard_service._get_weather_evidence()["summary"],
            }
            result["segments"] = segments

        return result

    def _route_coverage(self, route_edges, orig_snap_m, dest_snap_m):
        """Snap distances and how much of the route the DEM covers (by bounds)."""
        total = len(route_edges)
        without_terrain = 0
        if terrain_service.is_available:
            for key in route_edges:
                coords = self.edge_coordinates(key[0], key[1], self.G.edges[key])
                if not all(terrain_service.contains(lat, lon) for lon, lat in coords):
                    without_terrain += 1
        else:
            without_terrain = total
        return {
            "origin_snap_distance_m": round(orig_snap_m, 1),
            "destination_snap_distance_m": round(dest_snap_m, 1),
            "max_snap_distance_m": settings.MAX_SNAP_DISTANCE_M,
            "terrain_available": terrain_service.is_available,
            "terrain_unavailable_reason": terrain_service.unavailable_reason(),
            "edges_total": total,
            "edges_without_terrain": without_terrain,
            "terrain_coverage_pct": round(100.0 * (total - without_terrain) / total, 1) if total else 0.0,
        }

    def _summarize_threat_exposure(self, route_edges, zone_index, edge_threats, endpoint_zone_ids, avoid_threats):
        affected = {}
        for key in route_edges:
            hits = edge_threats.get(key)
            if hits is None:
                hits = zone_index.intersecting(self.edge_coordinates(key[0], key[1], self.G.edges[key]))
            for zone, dist in hits:
                entry = affected.setdefault(zone.threat_id, {
                    "threat_id": zone.threat_id,
                    "title": zone.title,
                    "severity": zone.severity,
                    "effect": ("ENDPOINT_UNAVOIDABLE" if zone.threat_id in endpoint_zone_ids
                               else "PENALIZED"),
                    "travel_time_multiplier": (routing_policy.ENDPOINT_ZONE_MULTIPLIER if zone.is_blocking
                                               else routing_policy.SEVERITY_MULTIPLIERS[zone.severity]),
                    "min_distance_m": dist,
                    "edges": 0,
                })
                entry["edges"] += 1
                entry["min_distance_m"] = min(entry["min_distance_m"], dist)
        for entry in affected.values():
            entry["min_distance_m"] = round(entry["min_distance_m"], 1)
        return {
            "avoid_threats": avoid_threats,
            "policy": {
                "safety_buffer_m": routing_policy.THREAT_SAFETY_BUFFER_M,
                "blocking_severities": sorted(routing_policy.BLOCKING_SEVERITIES),
                "severity_multipliers": dict(routing_policy.SEVERITY_MULTIPLIERS),
                "calibrated": False,
            },
            "active_zone_count": len(zone_index.zones),
            "exposed": bool(affected),
            "affected_threats": list(affected.values()),
            "endpoint_zone_ids": sorted(endpoint_zone_ids),
        }

routing_service = RoutingService()
