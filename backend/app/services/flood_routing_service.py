import networkx as nx
import osmnx as ox
from .routing_service import routing_service
from .flood.inundation_service import inundation_service
from .flood.drainage_service import drainage_service

class FloodRoutingService:
    def __init__(self):
        self.flood_penalties = {
            "SAFE": 1.0,
            "LOW": 1.10,
            "MODERATE": 1.35,
            "HIGH": 2.50,
            "CRITICAL": 999999.0  # Or None, handled explicitly
        }

    def _get_baseline_route(self, orig_node, dest_node):
        try:
            route = nx.shortest_path(routing_service.G, orig_node, dest_node, weight='travel_time')
            distance_m = 0
            time_s = 0
            for u, v in zip(route[:-1], route[1:]):
                edge_data = min(routing_service.G.get_edge_data(u, v).values(), key=lambda x: x.get('travel_time', 0))
                distance_m += edge_data.get('length', 0)
                time_s += edge_data.get('travel_time', 0)
            return {
                "route_nodes": route,
                "distance_m": distance_m,
                "estimated_time_s": time_s
            }
        except nx.NetworkXNoPath:
            return None

    def calculate_flood_safe_route(self, origin_lat: float, origin_lon: float, destination_lat: float, destination_lon: float, rainfall_mm_hr: float, blockage_percent: float, forecast_minute: int):
        if not (20 <= rainfall_mm_hr <= 100):
            raise ValueError("rainfall_mm_hr must be between 20 and 100")
        if not (0 <= blockage_percent <= 75):
            raise ValueError("blockage_percent must be between 0 and 75")
        if not (0 <= forecast_minute <= 180):
            raise ValueError("forecast_minute must be between 0 and 180")

        if not routing_service.load_graph():
            raise Exception("Graph is missing.")

        orig_node, _ = routing_service.snap(origin_lat, origin_lon, "origin")
        dest_node, _ = routing_service.snap(destination_lat, destination_lon, "destination")

        # Baseline route
        baseline = self._get_baseline_route(orig_node, dest_node)
        if not baseline:
            raise Exception("No route exists between the given locations in the base graph.")

        # Get flood state for roads
        roads_assessed = inundation_service.assess_roads(rainfall_mm_hr, blockage_percent, forecast_minute)
        
        # Build a lookup for edge flood data
        edge_flood_map = {}
        for r in roads_assessed:
            edge_flood_map[(r['u'], r['v'], r['key'])] = r

        # Dynamic weight function
        def flood_weight(u, v, d):
            # We must handle multigraph by checking if d has 'travel_time' directly
            # NetworkX passes the edge attributes dict as `d`
            base_time = d.get('travel_time', 0.1)
            # We need the key. NetworkX weight function doesn't receive the key directly in standard shortest_path
            # But we can find the max risk among parallel edges or just use the first one if we can't get key
            # Actually, `nx.shortest_path` doesn't pass key to weight function.
            # To be precise, we can precompute the weights or use a subgraph.
            return base_time

        def flood_weight(u, v, edges_dict):
            min_weight = float('inf')
            
            for key, edge_data in edges_dict.items():
                base_time = edge_data.get('travel_time', 0.1)
                
                # Check if this edge has flood data
                flood_info = edge_flood_map.get((u, v, key))
                
                if flood_info:
                    level = flood_info.get("flood_level", "SAFE")
                    if level == "CRITICAL":
                        continue # Edge is unavailable
                    penalty = self.flood_penalties.get(level, 1.0)
                else:
                    penalty = 1.0
                    
                effective_weight = base_time * penalty
                if effective_weight < min_weight:
                    min_weight = effective_weight
                    
            if min_weight == float('inf'):
                # NetworkX requires numeric weights; returning a huge number
                # works better than float('inf') for some internal functions,
                # but let's try infinity. Or we can just use 999999999.
                return 999999999.0
                
            return min_weight

        try:
            route = nx.shortest_path(routing_service.G, orig_node, dest_node, weight=flood_weight)
        except nx.NetworkXNoPath:
            return None # No route exists at all
            
        # Calculate stats for the recommended route
        distance_m = 0
        time_s = 0
        max_depth = 0.0
        route_risk_score = 0
        has_critical = False
        
        coordinates = []
        
        for u, v in zip(route[:-1], route[1:]):
            coordinates.append([routing_service.G.nodes[u]['x'], routing_service.G.nodes[u]['y']])
            
            # Find the best parallel edge that was chosen
            best_key = None
            best_weight = float('inf')
            
            for key, edge_data in routing_service.G.get_edge_data(u, v).items():
                base_time = edge_data.get('travel_time', 0.1)
                flood_info = edge_flood_map.get((u, v, key))
                
                if flood_info:
                    level = flood_info.get("flood_level", "SAFE")
                    penalty = self.flood_penalties.get(level, 1.0) if level != "CRITICAL" else float('inf')
                else:
                    penalty = 1.0
                    
                w = base_time * penalty
                if w < best_weight:
                    best_weight = w
                    best_key = key
                    
            # Check if even the best edge is critical
            best_flood = edge_flood_map.get((u, v, best_key))
            if best_flood:
                if best_flood.get("flood_level") == "CRITICAL":
                    has_critical = True
                route_risk_score = max(route_risk_score, best_flood.get("flood_score", 0))
                max_depth = max(max_depth, best_flood.get("estimated_depth_cm", 0.0))
                
            edge_data = routing_service.G.get_edge_data(u, v)[best_key]
            distance_m += edge_data.get('length', 0)
            time_s += edge_data.get('travel_time', 0)
            
        # Add final node coord
        last_node = route[-1]
        coordinates.append([routing_service.G.nodes[last_node]['x'], routing_service.G.nodes[last_node]['y']])
        
        if has_critical:
            return None # The only path involves a CRITICAL edge
            
        # Calculate baseline stats
        baseline_risk = 0
        for u, v in zip(baseline["route_nodes"][:-1], baseline["route_nodes"][1:]):
            best_key = None
            best_time = float('inf')
            for key, edge_data in routing_service.G.get_edge_data(u, v).items():
                if edge_data.get('travel_time', 0) < best_time:
                    best_time = edge_data.get('travel_time', 0)
                    best_key = key
            
            bf = edge_flood_map.get((u, v, best_key))
            if bf:
                baseline_risk = max(baseline_risk, bf.get("flood_score", 0))

        route_safety = inundation_service.classify(route_risk_score)
        
        is_rerouted = route != baseline["route_nodes"]
        
        reason = ""
        if is_rerouted:
            dist_diff = distance_m - baseline["distance_m"]
            time_diff = time_s - baseline["estimated_time_s"]
            risk_reduction = baseline_risk - route_risk_score
            reason = f"Baseline route contains higher-risk flooded road segments. Recommended route is {dist_diff:.0f}m longer but reduces flood risk score by {risk_reduction}."
        else:
            reason = "Fastest route is also the safest route under current conditions."

        return {
            "status": "success",
            "forecast": {
                "minute": forecast_minute
            },
            "baseline_route": {
                "distance_m": round(baseline["distance_m"], 2),
                "estimated_time_s": round(baseline["estimated_time_s"], 2),
                "flood_risk_score": baseline_risk
            },
            "recommended_route": {
                "distance_m": round(distance_m, 2),
                "estimated_time_s": round(time_s, 2),
                "flood_risk_score": route_risk_score,
                "maximum_depth_cm": max_depth,
                "route_safety": route_safety
            },
            "comparison": {
                "distance_difference_m": round(distance_m - baseline["distance_m"], 2),
                "time_difference_s": round(time_s - baseline["estimated_time_s"], 2),
                "risk_reduction": max(0, baseline_risk - route_risk_score),
                "is_rerouted": is_rerouted
            },
            "decision": {
                "reason": reason
            },
            "coverage": {
                # Roads outside the synthetic drainage grid are never assessed and are
                # treated as SAFE by this model; report how much of the route that is.
                "drainage_model": "SYNTHETIC/PROTOTYPE",
                "drainage_grid_bounds": drainage_service.get_bounds(),
                "route_points_outside_drainage_grid_pct": round(
                    100.0 * sum(1 for lon, lat in coordinates if not drainage_service.contains(lat, lon))
                    / max(len(coordinates), 1), 1),
            },
            "route": {
                "type": "LineString",
                "coordinates": coordinates
            }
        }

flood_routing_service = FloodRoutingService()
