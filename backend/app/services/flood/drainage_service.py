import math
import threading

import networkx as nx
from app.services.terrain_service import terrain_service

class DrainageService:
    def __init__(self):
        self.G = None
        self._lock = threading.Lock()

    def _ensure_network(self):
        # Build once under a lock and publish only when complete (concurrent requests).
        if self.G is not None:
            return
        with self._lock:
            if self.G is not None:
                return
            self.G = self._build_network()

    def _build_network(self):
        G = nx.DiGraph()
        
        # Grid of nodes covering Hubballi-Dharwad urban area
        # Lat: 15.32 to 15.42 (step 0.01), Lon: 75.06 to 75.14 (step 0.01)
        lats = [15.32 + i*0.01 for i in range(11)]
        lons = [75.06 + j*0.01 for j in range(9)]
        
        center_lat = 15.37
        center_lon = 75.10
        
        for r, lat in enumerate(lats):
            for c, lon in enumerate(lons):
                node_id = f"DN_{r:02d}_{c:02d}"
                
                # Elevation
                ts = terrain_service.get_terrain_susceptibility(lat, lon)
                if ts and ts.get("status") == "success":
                    elevation = ts["elevation_m"]
                else:
                    elevation = 680 - (lat - 15.32)*200 - (lon - 75.06)*100
                    
                # Capacity
                # distance from city center (normalized 0-1, max distance approx 0.06 deg)
                dist = math.sqrt((lat - center_lat)**2 + (lon - center_lon)**2)
                dist_factor = min(dist / 0.06, 1.0)
                base_capacity = 25 + 10 * dist_factor
                
                G.add_node(node_id, 
                                lat=lat, 
                                lon=lon, 
                                elevation_m=elevation, 
                                base_drainage_capacity_mm_hr=base_capacity)
                                
        # Edges
        # connect neighbors if downhill
        cell_area_m2 = 1210000 # ~1.1km * 1.1km
        for r in range(len(lats)):
            for c in range(len(lons)):
                u_id = f"DN_{r:02d}_{c:02d}"
                u_data = G.nodes[u_id]
                u_elev = u_data["elevation_m"]
                
                neighbors = []
                if r > 0: neighbors.append(f"DN_{r-1:02d}_{c:02d}")
                if r < len(lats) - 1: neighbors.append(f"DN_{r+1:02d}_{c:02d}")
                if c > 0: neighbors.append(f"DN_{r:02d}_{c-1:02d}")
                if c < len(lons) - 1: neighbors.append(f"DN_{r:02d}_{c+1:02d}")
                
                downhill_neighbors = []
                for v_id in neighbors:
                    v_elev = G.nodes[v_id]["elevation_m"]
                    if u_elev > v_elev:
                        downhill_neighbors.append(v_id)
                        
                n_out = max(len(downhill_neighbors), 1)
                edge_capacity_lps = (u_data["base_drainage_capacity_mm_hr"] * cell_area_m2 / 3600.0) / n_out
                
                for v_id in downhill_neighbors:
                    G.add_edge(u_id, v_id, 
                                    length_m=1100, 
                                    capacity_lps=edge_capacity_lps,
                                    blockage_percent=0)
        return G

    def simulate(self, runoff_mm_hr, blockage_percent=0):
        self._ensure_network()
        
        # Sort nodes by elevation descending
        nodes_sorted = sorted(self.G.nodes(data=True), key=lambda x: x[1]['elevation_m'], reverse=True)
        
        cell_area_m2 = 1210000
        local_inflow_lps = runoff_mm_hr * cell_area_m2 / 3600.0
        
        node_status = {}
        edge_status = {}
        
        # Initialize incoming overflow
        incoming_overflow = {n: 0.0 for n in self.G.nodes()}
        
        overloaded_count = 0
        
        for n_id, n_data in nodes_sorted:
            total_inflow = local_inflow_lps + incoming_overflow[n_id]
            
            effective_capacity = n_data["base_drainage_capacity_mm_hr"] * (1 - blockage_percent/100.0)
            effective_capacity_lps = effective_capacity * cell_area_m2 / 3600.0
            
            overflow = max(0.0, total_inflow - effective_capacity_lps)
            utilization = total_inflow / max(effective_capacity_lps, 1.0)
            
            if utilization < 0.70: status = "NORMAL"
            elif utilization < 0.90: status = "HIGH"
            elif utilization <= 1.00: status = "NEAR_CAPACITY"
            else: 
                status = "OVERLOADED"
                overloaded_count += 1
                
            node_status[n_id] = {
                "id": n_id,
                "lat": n_data["lat"],
                "lon": n_data["lon"],
                "total_inflow_lps": total_inflow,
                "effective_capacity_lps": effective_capacity_lps,
                "overflow_lps": overflow,
                "utilization": utilization,
                "status": status
            }
            
            # distribute overflow to downstream edges
            out_edges = list(self.G.out_edges(n_id, data=True))
            if overflow > 0 and out_edges:
                overflow_per_edge = overflow / len(out_edges)
                for u, v, e_data in out_edges:
                    incoming_overflow[v] += overflow_per_edge
                    edge_status[(u, v)] = {
                        "flow_lps": overflow_per_edge,
                        "capacity_lps": e_data["capacity_lps"] * (1 - blockage_percent/100.0)
                    }
            
        return {
            "summary": {
                "total_nodes": self.G.number_of_nodes(),
                "overloaded_nodes": overloaded_count,
                "runoff_mm_hr": runoff_mm_hr,
                "blockage_percent": blockage_percent
            },
            "nodes": node_status,
            "edges": edge_status,
            "warning": "SYNTHETIC/PROTOTYPE - Not real municipal infrastructure data."
        }
        
    def get_nearest_node(self, lat, lon):
        self._ensure_network()
        
        min_dist = float('inf')
        nearest = None
        
        for n, data in self.G.nodes(data=True):
            dist = (data['lat'] - lat)**2 + (data['lon'] - lon)**2
            if dist < min_dist:
                min_dist = dist
                nearest = n
                
        if nearest:
            return {
                "id": nearest,
                "lat": self.G.nodes[nearest]["lat"],
                "lon": self.G.nodes[nearest]["lon"],
                "status": "NORMAL"  # Default status for isolated query
            }
        return None

    def get_bounds(self):
        """Extent of the synthetic grid, padded by half a cell (each node represents a cell)."""
        self._ensure_network()
        lats = [d['lat'] for _, d in self.G.nodes(data=True)]
        lons = [d['lon'] for _, d in self.G.nodes(data=True)]
        half = 0.005
        return {"min_lon": min(lons) - half, "min_lat": min(lats) - half,
                "max_lon": max(lons) + half, "max_lat": max(lats) + half}

    def contains(self, lat, lon):
        b = self.get_bounds()
        return b["min_lon"] <= lon <= b["max_lon"] and b["min_lat"] <= lat <= b["max_lat"]

    def get_network_info(self):
        self._ensure_network()
        return {
            "total_nodes": self.G.number_of_nodes(),
            "total_edges": self.G.number_of_edges(),
            "network_type": "SYNTHETIC/PROTOTYPE"
        }

drainage_service = DrainageService()
