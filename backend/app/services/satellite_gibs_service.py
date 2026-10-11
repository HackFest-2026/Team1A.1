import time
from typing import Dict, Any, List

class GibsService:
    def __init__(self):
        pass

    def get_status(self) -> str:
        return "AVAILABLE"

    def get_layers(self) -> List[Dict[str, Any]]:
        # GIBS imagery does not provide a strict instantaneous "now" timestamp via the simple tile API.
        # It rolls over daily. We use "today" but NASA may return empty tiles if not fully processed.
        # A more robust implementation would fetch the WMTS capabilities XML, but for this Phase 
        # we will provide the "latest available" daily layer.
        
        # We'll just define the layer template without a hardcoded day, or we use a "latest" 
        # semantic if supported by our specific tile client, but GIBS typically requires YYYY-MM-DD.
        # We'll use time.gmtime() to build a YYYY-MM-DD string for the standard Daily mosaic.
        
        # However, to avoid 'generating acquisition timestamps using datetime.now()' as a substitute for 
        # provider metadata, we must set acquisition_time to null or UNKNOWN unless we explicitly parse 
        # the provider's metadata endpoint.
        
        fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time()))
        
        return [
            {
                "id": "gibs_true_color",
                "name": "Satellite (True Color)",
                "source": "NASA GIBS",
                "provider": "gibs",
                # NOTE: We use Suomi-NPP by default.
                # Alternative products such as NOAA-20 (VIIRS_NOAA20_CorrectedReflectance_TrueColor)
                # or NOAA-21 (VIIRS_NOAA21_CorrectedReflectance_TrueColor) can be easily
                # configured here as additional or alternative layers by matching their respective
                # WMTS paths in the tile_template below.
                "product": "VIIRS_SNPP_CorrectedReflectance_TrueColor",
                "image_url": None,
                # Leaflet allows substituting {time} if TimeDimension is used, or we just rely on standard layer.
                # Since GIBS requires a date, and we don't have a metadata scraper here, 
                # we'll omit the explicit date and let the frontend TimeDimension plugin handle it, 
                # OR we just provide a default.
                # Actually, many GIBS layers allow omitting the date or using a specific default.
                "tile_template": "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_SNPP_CorrectedReflectance_TrueColor/default/{time}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg",
                "acquisition_time": None,
                "published_time": None,
                "fetched_at": fetched_at,
                "bbox": [-180, -90, 180, 90],
                "center_latitude": 0.0,
                "center_longitude": 0.0,
                "resolution": "250m",
                "status": "success",
                "mode": "AVAILABLE",
                "freshness": "UNKNOWN",
                "attribution": "NASA Global Imagery Browse Services (GIBS)"
            },
            {
                "id": "gibs_cloud",
                "name": "Cloud Liquid Water (AMSR2 Passive Microwave)",
                "source": "NASA GIBS",
                "provider": "gibs",
                "product": "AMSR2_Cloud_Liquid_Water_Day",
                "image_url": None,
                "tile_template": "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/AMSR2_Cloud_Liquid_Water_Day/default/{time}/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png",
                "acquisition_time": None,
                "published_time": None,
                "fetched_at": fetched_at,
                "bbox": [-180, -90, 180, 90],
                "center_latitude": 0.0,
                "center_longitude": 0.0,
                "resolution": "2km",
                "status": "success",
                "mode": "AVAILABLE",
                "freshness": "UNKNOWN",
                "attribution": "NASA Global Imagery Browse Services (GIBS)"
            }
        ]

satellite_gibs_service = GibsService()
