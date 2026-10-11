import osmnx as ox
from shapely.geometry import LineString
from app.services.routing_service import routing_service
from app.services.terrain_service import terrain_service
from .drainage_service import drainage_service

class InundationService:
    def calculate_flood_score(self, rainfall_mm_hr, terrain_susceptibility, drainage_utilization, drainage_overflow_ratio):
        rainfall_factor = min(rainfall_mm_hr / 100.0, 1.0) * 100
        terrain_factor = terrain_susceptibility
        drainage_factor = min(drainage_utilization, 2.0) / 2.0 * 100
        
        score = 0.25 * rainfall_factor + 0.30 * terrain_factor + 0.45 * drainage_factor
        return int(max(0, min(100, score)))
        
    def estimate_depth_cm(self, overflow_mm_hr, duration_hr, terrain_susceptibility):
        terrain_factor = 1.0 + terrain_susceptibility / 100.0
        retention = 0.70
        
        depth_cm = overflow_mm_hr * duration_hr * terrain_factor * retention / 10.0
        return round(max(0, min(200, depth_cm)), 1)
        
    def classify(self, score):
        if score < 20: return "SAFE"
        elif score < 40: return "LOW"
        elif score < 60: return "MODERATE"
        elif score < 80: return "HIGH"
        else: return "CRITICAL"
        
    def assess_roads(self, rainfall_mm_hr, blockage_percent, duration_minutes=0):
        drainage_state = drainage_service.simulate(rainfall_mm_hr, blockage_percent)
        edges_to_assess = set()
        
        if not routing_service.G:
            routing_service.load_graph()
            
        if not routing_service.G:
            return []
            
        X = []
        Y = []
        # Target high-risk drainage areas
        for n_id, n_data in drainage_state["nodes"].items():
            if n_data["status"] in ["HIGH", "NEAR_CAPACITY", "OVERLOADED"]:
                X.append(n_data["lon"])
                Y.append(n_data["lat"])
                
        if X:
            try:
                nearest_list = ox.distance.nearest_edges(routing_service.G, X, Y, return_dist=False)
                for edge in nearest_list:
                    edges_to_assess.add(tuple(edge))
            except:
                pass
                
        results = []
        coords_list = []
        edge_centers = []
        
        for u, v, key in list(edges_to_assess)[:150]:
            edge_data = routing_service.G.get_edge_data(u, v, key)
            if not edge_data: continue
            
            u_node = routing_service.G.nodes[u]
            v_node = routing_service.G.nodes[v]
            
            if 'geometry' in edge_data:
                geom = edge_data['geometry']
                center = geom.centroid
                clon, clat = center.x, center.y
                coords = list(geom.coords)
                coords = [[c[0], c[1]] for c in coords]
            else:
                clon, clat = (u_node['x'] + v_node['x']) / 2.0, (u_node['y'] + v_node['y']) / 2.0
                coords = [[u_node['x'], u_node['y']], [v_node['x'], v_node['y']]]
                
            coords_list.append((clat, clon))
            edge_centers.append({
                "u": u, "v": v, "key": key,
                "name": edge_data.get("name", "Unknown Road"),
                "highway": edge_data.get("highway", "unclassified"),
                "length_m": edge_data.get("length", 0.0),
                "coords": coords,
                "clat": clat,
                "clon": clon
            })
            
        terrain_results = terrain_service.get_terrain_susceptibility_batch(coords_list)
        
        for i, edge in enumerate(edge_centers):
            ts_res = terrain_results[i]
            ts = ts_res.get("susceptibility_score", 50) if ts_res.get("status") == "success" else 50
            
            nearest_dn = drainage_service.get_nearest_node(edge["clat"], edge["clon"])
            dn_utilization = 0.5
            overflow_lps = 0.0
            dn_status = "NORMAL"
            
            if nearest_dn and nearest_dn["id"] in drainage_state["nodes"]:
                dn_data = drainage_state["nodes"][nearest_dn["id"]]
                dn_utilization = dn_data["utilization"]
                overflow_lps = dn_data["overflow_lps"]
                dn_status = dn_data["status"]
                
            cell_area_m2 = 1210000
            overflow_mm_hr = overflow_lps * 3600.0 / cell_area_m2
                
            score = self.calculate_flood_score(rainfall_mm_hr, ts, dn_utilization, overflow_mm_hr)
            depth = self.estimate_depth_cm(overflow_mm_hr, duration_minutes/60.0, ts)
            level = self.classify(score)
            
            results.append({
                "u": edge["u"],
                "v": edge["v"],
                "key": edge["key"],
                "name": edge["name"],
                "highway": edge["highway"],
                "length_m": edge["length_m"],
                "flood_score": score,
                "flood_level": level,
                "estimated_depth_cm": depth,
                "drainage_status": dn_status,
                "coordinates": edge["coords"]
            })
            
        return results

inundation_service = InundationService()
