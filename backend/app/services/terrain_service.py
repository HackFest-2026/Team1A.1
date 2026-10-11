import os
import threading
import functools

import rasterio
from rasterio.windows import Window

from app.config.settings import settings

# Reasons reported with status "unavailable" (ADR-008): callers must be able to
# tell missing data, NoData and out-of-coverage apart.
REASON_DEM_UNAVAILABLE = "DEM_UNAVAILABLE"
REASON_CRS_INCOMPATIBLE = "DEM_CRS_INCOMPATIBLE"
REASON_OUTSIDE_COVERAGE = "OUTSIDE_DEM_COVERAGE"
REASON_NODATA = "NODATA"
REASON_READ_ERROR = "DEM_READ_ERROR"

WINDOW_SIZE = 9  # pixels; ~270 m at 1 arc-second


class TerrainService:
    """Point sampling of a geographic (EPSG:4326) DEM.

    Coordinates are looked up as lon/lat directly in the raster, so a DEM in any
    other CRS is refused with DEM_CRS_INCOMPATIBLE instead of being sampled wrongly.
    """

    def __init__(self, dem_path: str = None):
        self.dem_path = dem_path or settings.DEM_PATH
        self.file_exists = os.path.exists(self.dem_path)
        self.source = "ISRO/NRSC CartoDEM V3 R1 - D43D"
        self._src = None
        self._lock = threading.Lock()
        self._open_error = None

    # ------------------------------------------------------------------
    # Dataset access and metadata
    # ------------------------------------------------------------------
    def _get_dataset(self):
        if not self.file_exists:
            return None
        if self._src is None and self._open_error is None:
            with self._lock:
                if self._src is None and self._open_error is None:
                    try:
                        self._src = rasterio.open(self.dem_path)
                    except Exception as e:  # unreadable file
                        self._open_error = str(e)
        return self._src

    @property
    def crs_compatible(self) -> bool:
        src = self._get_dataset()
        return src is not None and src.crs is not None and src.crs.to_epsg() == 4326

    @property
    def is_available(self) -> bool:
        """True when the DEM exists, opens, and is in EPSG:4326."""
        return self.crs_compatible

    def unavailable_reason(self):
        if not self.file_exists:
            return REASON_DEM_UNAVAILABLE
        if self._get_dataset() is None:
            return REASON_READ_ERROR
        if not self.crs_compatible:
            return REASON_CRS_INCOMPATIBLE
        return None

    def metadata(self) -> dict:
        """Dataset facts for the coverage manifest; read from the file, not assumed."""
        src = self._get_dataset()
        info = {
            "path_configured": self.dem_path,
            "file_exists": self.file_exists,
            "available": self.is_available,
            "unavailable_reason": self.unavailable_reason(),
            "source": self.source,
        }
        if src is not None:
            info.update({
                "crs": src.crs.to_string() if src.crs else None,
                "bounds": {"min_lon": src.bounds.left, "min_lat": src.bounds.bottom,
                           "max_lon": src.bounds.right, "max_lat": src.bounds.top},
                "resolution": list(src.res),
                "width": src.width,
                "height": src.height,
                "dtype": src.dtypes[0],
                "nodata": src.nodata,
            })
        return info

    def contains(self, lat: float, lon: float) -> bool:
        if not self.is_available:
            return False
        b = self._src.bounds
        return b.left <= lon <= b.right and b.bottom <= lat <= b.top

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------
    def _unavailable(self, reason, message):
        return {
            "status": "unavailable",
            "reason": reason,
            "source": self.source if reason != REASON_DEM_UNAVAILABLE else "UNAVAILABLE",
            "error": message,
        }

    def _sample_point_from_raster(self, src, lat, lon):
        """Sample one point from an open, CRS-checked dataset. Caller holds the lock."""
        try:
            if not (src.bounds.left <= lon <= src.bounds.right and src.bounds.bottom <= lat <= src.bounds.top):
                return self._unavailable(REASON_OUTSIDE_COVERAGE, "Coordinate is outside DEM bounds")

            row, col = src.index(lon, lat)
            offset = WINDOW_SIZE // 2
            row_start = max(0, row - offset)
            row_end = min(src.height, row + offset + 1)
            col_start = max(0, col - offset)
            col_end = min(src.width, col + offset + 1)

            window = Window.from_slices((row_start, row_end), (col_start, col_end))
            data = src.read(1, window=window)
            mask = src.read_masks(1, window=window)
            valid_data = data[mask != 0]

            if len(valid_data) == 0 or mask[row - row_start, col - col_start] == 0:
                return self._unavailable(REASON_NODATA, "Target coordinate is NoData/masked")

            target_elevation = float(data[row - row_start, col - col_start])
            mean_neighborhood = float(valid_data.mean())
            local_relative_elevation = target_elevation - mean_neighborhood

            # Susceptibility (0-100): uncalibrated linear map, <= -5 m -> 100, >= +2 m -> 0
            if local_relative_elevation <= -5.0:
                score = 100
            elif local_relative_elevation >= 2.0:
                score = 0
            else:
                normalized = (local_relative_elevation - (-5.0)) / 7.0
                score = int(100 - (normalized * 100))

            result = {
                "status": "success",
                "source": self.source,
                "elevation_m": target_elevation,
                "local_relative_elevation_m": round(local_relative_elevation, 2),
                "mean_neighborhood_m": round(mean_neighborhood, 2),
                "susceptibility_score": score,
            }
            if (row_end - row_start) < WINDOW_SIZE or (col_end - col_start) < WINDOW_SIZE:
                result["window_truncated"] = True  # near the DEM edge; neighbourhood is partial
            return result
        except Exception as e:
            return self._unavailable(REASON_READ_ERROR, f"Failed to process DEM: {e}")

    @functools.lru_cache(maxsize=100000)
    def get_terrain_susceptibility(self, lat: float, lon: float):
        reason = self.unavailable_reason()
        if reason == REASON_DEM_UNAVAILABLE:
            return self._unavailable(reason, "DEM file not found")
        if reason == REASON_READ_ERROR:
            return self._unavailable(reason, f"DEM could not be opened: {self._open_error}")
        if reason == REASON_CRS_INCOMPATIBLE:
            return self._unavailable(reason, f"DEM CRS is {self._src.crs}, expected EPSG:4326")
        with self._lock:
            return self._sample_point_from_raster(self._src, lat, lon)

    def get_terrain_susceptibility_batch(self, coords_list):
        """Query terrain susceptibility for multiple (lat, lon) pairs."""
        return [self.get_terrain_susceptibility(lat, lon) for lat, lon in coords_list]

    def close(self):
        with self._lock:
            if self._src is not None:
                self._src.close()
                self._src = None


terrain_service = TerrainService()
