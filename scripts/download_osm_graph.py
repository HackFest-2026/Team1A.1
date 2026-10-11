import os
import sys
import osmnx as ox

def download_graph():
    # Define the area of interest
    place_names = ["Hubballi, Karnataka, India", "Dharwad, Karnataka, India"]
    
    # Path to save the graph
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "osm")
    os.makedirs(output_dir, exist_ok=True)
    graph_path = os.path.join(output_dir, "hubballi_dharwad_drive.graphml")
    
    if os.path.exists(graph_path):
        print(f"Cached data is being used. Graph already exists at: {graph_path}")
        return
        
    print(f"Downloading drivable road network around Hubballi-Dharwad midpoint...")
    try:
        # Download the graph using a center point and distance (15km radius)
        # Hubballi-Dharwad midpoint is roughly 15.41, 75.06
        G = ox.graph_from_point((15.41, 75.06), dist=15000, network_type="drive")
        
        # Print statistics
        nodes, edges = ox.graph_to_gdfs(G)
        print(f"Download complete.")
        print(f"Number of nodes: {len(nodes)}")
        print(f"Number of edges: {len(edges)}")
        bounds = nodes.total_bounds
        print(f"Geographic bounds (minx, miny, maxx, maxy): {bounds}")
        print(f"Saving graph to {graph_path}...")
        
        # Save graph
        ox.save_graphml(G, filepath=graph_path)
        print("Save complete.")
    except Exception as e:
        print(f"Error: Could not download the graph. Details: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    download_graph()
