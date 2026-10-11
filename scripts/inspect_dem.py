import os
import sys

def inspect_dem():
    tif_path = os.environ.get("DEM_PATH", os.path.join("data", "terrain", "cdnd43d_v3r1", "cdnd43d.tif"))
    
    print("--- DEM INSPECTION SCRIPT ---")
    print(f"1. Exact file path: {tif_path}")
    if not os.path.exists(tif_path):
        print("FAIL: .tif file not found!")
        return
        
    print(f"2. File Size: {os.path.getsize(tif_path) / (1024*1024):.2f} MB")
    
    try:
        import rasterio
        import numpy as np
        
        with rasterio.open(tif_path) as src:
            print(f"3. Raster width: {src.width}")
            print(f"4. Raster height: {src.height}")
            print(f"5. Band count: {src.count}")
            print(f"6. CRS: {src.crs}")
            print(f"7. Bounds: {src.bounds}")
            print(f"8. Pixel resolution: {src.res}")
            print(f"9. Data type: {src.dtypes[0]}")
            print(f"10. NoData value: {src.nodata}")
            
            # Read data and handle nodata/mask
            data = src.read(1)
            # Use rasterio mask, which reads the dataset's native mask (True = valid, False = nodata/masked)
            mask = src.read_masks(1)
            
            valid_data = data[mask != 0]
            
            if len(valid_data) > 0:
                print(f"11. Minimum valid elevation: {valid_data.min()}")
                print(f"12. Maximum valid elevation: {valid_data.max()}")
                print(f"13. Mean valid elevation: {valid_data.mean():.2f}")
                total_pixels = src.width * src.height
                valid_count = len(valid_data)
                print(f"14. Valid Pixels: {valid_count} / {total_pixels} ({valid_count / total_pixels * 100:.2f}%)")
            else:
                print("No valid elevation data found!")
                
            # Sample at 15.41, 75.06 (Hubballi-Dharwad)
            lat = 15.41
            lon = 75.06
            print(f"\n15. Sample elevation at (lat={lat}, lon={lon}):")
            if (src.bounds.left <= lon <= src.bounds.right) and (src.bounds.bottom <= lat <= src.bounds.top):
                row, col = src.index(lon, lat)
                
                # Check if the pixel is valid
                if mask[row, col] != 0:
                    val = data[row, col]
                    print(f"  Hubballi-Dharwad is IN BOUNDS.")
                    print(f"  Elevation at {lat}, {lon}: {val}")
                else:
                    print(f"  Hubballi-Dharwad is IN BOUNDS but elevation is NoData.")
            else:
                print(f"  Hubballi-Dharwad is OUT OF BOUNDS.")

    except ImportError:
        print("\nLIMITATION: rasterio is NOT installed in the backend environment.")
    except Exception as e:
        print(f"Error inspecting raster: {e}")

if __name__ == "__main__":
    inspect_dem()
