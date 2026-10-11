import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.routing_service import routing_service

def test():
    print("Testing GIS routing service...")
    
    status = routing_service.get_status()
    print(f"Status: {status}")
    
    if not status.get("graph_available"):
        print("Graph not available!")
        sys.exit(1)
        
    print("Calculating test route...")
    # Hubballi (origin) to Dharwad (destination)
    origin_lat = 15.3647
    origin_lon = 75.1240
    destination_lat = 15.4589
    destination_lon = 75.0078
    
    try:
        route = routing_service.calculate_route(
            origin_lat, origin_lon, destination_lat, destination_lon
        )
        print("Route calculated successfully!")
        print(f"Distance: {route['distance_m']} m")
        print(f"Estimated Time: {route['estimated_time_s']} s")
        print(f"Coordinates length: {len(route['route']['coordinates'])}")
    except Exception as e:
        print(f"Routing failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test()
