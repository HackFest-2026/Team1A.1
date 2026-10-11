import math
from app.config.settings import settings
from typing import Dict, Any, List, Optional
from app.services.routing_service import routing_service
from app.services.terrain_service import terrain_service
from .models import GeoPointContext, GeoSnapResult, GeoRouteContext, GeoGISStatus

def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two lat/lon points on Earth."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)

class GeoContextService:
    def __init__(self):
        self.routing_service = routing_service
        self.terrain_service = terrain_service

    def get_gis_status(self) -> GeoGISStatus:
        route_status = self.routing_service.get_status()
        dem_available = self.terrain_service.is_available
        
        return GeoGISStatus(
            status="ready" if (route_status.get("graph_available") and dem_available) else "degraded",
            graph_available=route_status.get("graph_available", False),
            dem_available=dem_available,
            dem_source=self.terrain_service.source if dem_available else "UNAVAILABLE",
            region=route_status.get("region", "Hubballi-Dharwad"),
            nodes_count=route_status.get("nodes", 0),
            edges_count=route_status.get("edges", 0)
        )

    def snap_coordinate(self, lat: float, lon: float) -> GeoSnapResult:
        """Snap to the nearest road node; raises OutsideCoverageError beyond MAX_SNAP_DISTANCE_M."""
        node_id, dist_m = self.routing_service.snap(lat, lon, label="point", enforce=True)
        node_data = self.routing_service.G.nodes[node_id]
        return GeoSnapResult(
            input_lat=lat,
            input_lon=lon,
            snapped_node_id=int(node_id),
            snapped_lat=float(node_data['y']),
            snapped_lon=float(node_data['x']),
            distance_m=round(dist_m, 2)
        )

    def get_point_context(self, lat: float, lon: float) -> GeoPointContext:
        terrain_res = self.terrain_service.get_terrain_susceptibility(lat, lon)

        road = {"road_coverage_status": "GRAPH_UNAVAILABLE"}
        if self.routing_service.load_graph():
            node_id, dist_m = self.routing_service.snap(lat, lon, label="point", enforce=False)
            road["distance_to_nearest_node_m"] = round(dist_m, 2)
            if dist_m <= settings.MAX_SNAP_DISTANCE_M:
                node_data = self.routing_service.G.nodes[node_id]
                road.update(
                    road_coverage_status="WITHIN_COVERAGE",
                    nearest_node_id=int(node_id),
                    nearest_node_lat=float(node_data['y']),
                    nearest_node_lon=float(node_data['x']),
                )
            else:
                road["road_coverage_status"] = "OUTSIDE_COVERAGE"

        return GeoPointContext(
            latitude=lat,
            longitude=lon,
            elevation_m=terrain_res.get("elevation_m"),
            susceptibility_score=terrain_res.get("susceptibility_score"),
            local_relative_elevation_m=terrain_res.get("local_relative_elevation_m"),
            terrain_status=terrain_res.get("status", "unavailable"),
            terrain_reason=terrain_res.get("reason"),
            source=terrain_res.get("source", self.terrain_service.source),
            **road,
        )

    def get_coverage_manifest(self) -> Dict[str, Any]:
        """What the loaded data actually covers. Computed from the files, never assumed."""
        from app.services.flood.drainage_service import drainage_service
        from app.services.weather_service import weather_service

        graph = {"available": self.routing_service.load_graph(), "path_configured": self.routing_service.graph_path}
        if graph["available"]:
            G = self.routing_service.G
            xs = [d['x'] for _, d in G.nodes(data=True)]
            ys = [d['y'] for _, d in G.nodes(data=True)]
            graph.update({
                "crs": G.graph.get("crs"),
                "nodes": G.number_of_nodes(),
                "edges": G.number_of_edges(),
                "bounds": {"min_lon": min(xs), "min_lat": min(ys), "max_lon": max(xs), "max_lat": max(ys)},
                "created_with": G.graph.get("created_with"),
                "created_date": G.graph.get("created_date"),
            })
        return {
            "road_graph": graph,
            "dem": self.terrain_service.metadata(),
            "drainage": {**drainage_service.get_network_info(), "bounds": drainage_service.get_bounds()},
            "weather": {
                "provider": "Open-Meteo",
                "spatial_model": "SINGLE_POINT",
                "point": {"lat": float(weather_service.lat), "lon": float(weather_service.lon)},
            },
            "policy": {"max_snap_distance_m": settings.MAX_SNAP_DISTANCE_M, "crs": "EPSG:4326"},
            "validated": False,
        }

    def get_route_context(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
        hazard_aware: bool = False,
        include_elevation_profile: bool = True,
        avoid_threats: bool = True
    ) -> GeoRouteContext:
        route_data = self.routing_service.calculate_route(
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            destination_lat=destination_lat,
            destination_lon=destination_lon,
            hazard_aware=hazard_aware,
            avoid_threats=avoid_threats,
        )
        
        coordinates = route_data.get("route", {}).get("coordinates", [])
        
        elevation_profile = None
        min_elev = None
        max_elev = None
        
        if include_elevation_profile and coordinates and self.terrain_service.is_available:
            # Batch query elevation along route coordinates (lat, lon)
            coords_lat_lon = [(pt[1], pt[0]) for pt in coordinates]
            samples = self.terrain_service.get_terrain_susceptibility_batch(coords_lat_lon)
            
            profile = []
            elevations = []
            for (lon, lat), s in zip(coordinates, samples):
                elev = s.get("elevation_m")
                profile.append({
                    "lat": lat,
                    "lon": lon,
                    "elevation_m": elev,
                    "susceptibility_score": s.get("susceptibility_score")
                })
                if elev is not None:
                    elevations.append(elev)
                    
            if elevations:
                elevation_profile = profile
                min_elev = min(elevations)
                max_elev = max(elevations)
                
        return GeoRouteContext(
            origin=route_data["origin"],
            destination=route_data["destination"],
            distance_m=route_data["distance_m"],
            estimated_time_s=route_data["estimated_time_s"],
            route_mode=route_data.get("route_mode", "STANDARD"),
            route_nodes=route_data.get("route_nodes", []),
            route_geometry=route_data["route"],
            elevation_profile=elevation_profile,
            min_elevation_m=min_elev,
            max_elevation_m=max_elev,
            hazard_summary=route_data.get("hazard_summary"),
            threat_exposure=route_data.get("threat_exposure"),
            coverage=route_data.get("coverage"),
            source=route_data.get("source", "cached_openstreetmap")
        )

geo_context_service = GeoContextService()
