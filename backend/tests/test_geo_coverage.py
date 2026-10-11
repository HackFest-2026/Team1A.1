"""Explicit geographic coverage and DEM CRS handling (ADR-008)."""
import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

from app.config.settings import settings
from app.main import app
from app.services.routing_service import routing_service
from app.services.terrain_service import TerrainService

client = TestClient(app)

DELHI = (28.6139, 77.2090)
HUBBALLI = (15.3647, 75.1240)
DEM_WEST_EDGE = 74.99986111111112


def _west_of_dem_node():
    routing_service.load_graph()
    for node, d in routing_service.G.nodes(data=True):
        if d["x"] < DEM_WEST_EDGE - 0.01 and 15.40 < d["y"] < 15.50:
            return node, d["y"], d["x"]
    pytest.skip("no graph node west of the DEM edge")


# --- Rejection outside the road network -------------------------------------

@pytest.mark.requires_graph
@pytest.mark.parametrize("url", [
    "/api/route?origin_lat={o[0]}&origin_lon={o[1]}&destination_lat={d[0]}&destination_lon={d[1]}",
    "/api/geo/route-context?origin_lat={o[0]}&origin_lon={o[1]}&destination_lat={d[0]}&destination_lon={d[1]}",
    "/api/route/flood-safe?origin_lat={o[0]}&origin_lon={o[1]}&destination_lat={d[0]}&destination_lon={d[1]}",
])
def test_routes_reject_destination_outside_coverage(url):
    res = client.get(url.format(o=HUBBALLI, d=DELHI))
    assert res.status_code == 422, res.text
    detail = res.json()["detail"]
    assert detail["code"] == "OUTSIDE_COVERAGE"
    assert detail["label"] == "destination"
    assert detail["nearest_node_distance_m"] > 1_000_000


@pytest.mark.requires_graph
def test_snap_rejects_outside_coverage():
    res = client.get(f"/api/geo/snap?lat={DELHI[0]}&lon={DELHI[1]}")
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "OUTSIDE_COVERAGE"


@pytest.mark.requires_graph
def test_snap_limit_is_configurable(monkeypatch):
    node_lat, node_lon = 15.3647, 75.1240
    assert client.get(f"/api/geo/snap?lat={node_lat}&lon={node_lon}").status_code == 200
    monkeypatch.setattr(settings, "MAX_SNAP_DISTANCE_M", 0.01)
    assert client.get(f"/api/geo/snap?lat={node_lat}&lon={node_lon}").status_code == 422


@pytest.mark.requires_graph
@pytest.mark.requires_dem  # the terrain reason is OUTSIDE_DEM_COVERAGE only when a DEM is loaded
def test_point_context_reports_limitations_instead_of_snapping():
    body = client.get(f"/api/geo/point?lat={DELHI[0]}&lon={DELHI[1]}").json()
    assert body["road_coverage_status"] == "OUTSIDE_COVERAGE"
    assert body["nearest_node_id"] is None
    assert body["distance_to_nearest_node_m"] > 1_000_000
    assert body["terrain_status"] == "unavailable"
    assert body["terrain_reason"] == "OUTSIDE_DEM_COVERAGE"


# --- DEM coverage -----------------------------------------------------------

@pytest.mark.requires_graph
@pytest.mark.requires_dem
def test_point_on_road_west_of_dem_is_outside_dem_coverage():
    _, lat, lon = _west_of_dem_node()
    body = client.get(f"/api/geo/point?lat={lat}&lon={lon}").json()
    assert body["road_coverage_status"] == "WITHIN_COVERAGE"
    assert body["terrain_reason"] == "OUTSIDE_DEM_COVERAGE"


@pytest.mark.requires_graph
@pytest.mark.requires_dem
def test_route_reports_terrain_coverage():
    inside = client.get(f"/api/route?origin_lat=15.365&origin_lon=75.125"
                        f"&destination_lat=15.370&destination_lon=75.130").json()
    assert inside["coverage"]["terrain_coverage_pct"] == 100.0
    assert inside["coverage"]["edges_without_terrain"] == 0

    _, lat, lon = _west_of_dem_node()
    west = client.get(f"/api/route?origin_lat=15.4589&origin_lon=75.0078"
                      f"&destination_lat={lat}&destination_lon={lon}").json()
    assert west["status"] == "success"
    assert west["coverage"]["edges_without_terrain"] > 0
    assert west["coverage"]["terrain_coverage_pct"] < 100.0


# --- DEM CRS / NoData / missing ---------------------------------------------

def _write_raster(path, crs, transform, data, nodata=None):
    with rasterio.open(path, "w", driver="GTiff", height=data.shape[0], width=data.shape[1],
                       count=1, dtype=data.dtype, crs=crs, transform=transform, nodata=nodata) as dst:
        dst.write(data, 1)


def test_projected_dem_is_refused_not_sampled_as_lonlat(tmp_path):
    path = tmp_path / "utm.tif"
    # UTM 43N metres around Hubballi; lon/lat lookups would silently miss it.
    _write_raster(path, "EPSG:32643", from_origin(510000, 1700000, 30, 30),
                  np.full((20, 20), 550, dtype="int16"))
    svc = TerrainService(dem_path=str(path))
    assert svc.is_available is False
    assert svc.unavailable_reason() == "DEM_CRS_INCOMPATIBLE"
    res = svc.get_terrain_susceptibility(15.3647, 75.1240)
    assert res["reason"] == "DEM_CRS_INCOMPATIBLE"
    svc.close()


def test_nodata_is_distinguished_from_outside_coverage(tmp_path):
    path = tmp_path / "geo.tif"
    data = np.full((20, 20), 600, dtype="int16")
    data[10, 10] = -32768
    _write_raster(path, "EPSG:4326", from_origin(75.0, 15.5, 0.001, 0.001), data, nodata=-32768)
    svc = TerrainService(dem_path=str(path))
    assert svc.is_available is True
    assert svc.get_terrain_susceptibility(15.4895, 75.0105)["reason"] == "NODATA"
    assert svc.get_terrain_susceptibility(15.30, 75.01)["reason"] == "OUTSIDE_DEM_COVERAGE"
    ok = svc.get_terrain_susceptibility(15.495, 75.005)
    assert ok["status"] == "success" and ok["elevation_m"] == 600.0
    svc.close()


def test_missing_dem_is_reported(tmp_path):
    svc = TerrainService(dem_path=str(tmp_path / "absent.tif"))
    assert svc.unavailable_reason() == "DEM_UNAVAILABLE"
    assert svc.get_terrain_susceptibility(15.36, 75.12)["reason"] == "DEM_UNAVAILABLE"


# --- Manifest ---------------------------------------------------------------

@pytest.mark.requires_graph
@pytest.mark.requires_dem
def test_coverage_manifest_matches_measured_data():
    m = client.get("/api/geo/coverage").json()
    assert m["validated"] is False
    assert m["policy"]["max_snap_distance_m"] == settings.MAX_SNAP_DISTANCE_M
    graph = m["road_graph"]
    assert graph["nodes"] == 25471
    assert graph["crs"] == "epsg:4326"
    assert graph["bounds"]["min_lon"] == pytest.approx(74.9203, abs=1e-3)
    dem = m["dem"]
    assert dem["crs"] == "EPSG:4326" and dem["available"] is True
    assert dem["bounds"]["min_lon"] == pytest.approx(DEM_WEST_EDGE, abs=1e-6)
    assert dem["bounds"]["min_lat"] == pytest.approx(15.000139, abs=1e-5)
    assert dem["nodata"] is None
    assert m["drainage"]["network_type"] == "SYNTHETIC/PROTOTYPE"
    assert m["weather"]["spatial_model"] == "SINGLE_POINT"


@pytest.mark.requires_graph
@pytest.mark.requires_dem
def test_system_status_reflects_actual_components():
    body = client.get("/api/system/status").json()
    assert body["osm"] == "LOADED"
    assert body["terrain"] == "AVAILABLE"
    assert body["drainage"] == "SYNTHETIC"


@pytest.mark.requires_graph
@pytest.mark.requires_dem
def test_flood_safe_route_reports_drainage_coverage():
    res = client.get("/api/route/flood-safe?origin_lat=15.36&origin_lon=75.12"
                     "&destination_lat=15.4589&destination_lon=75.0078&rainfall_mm_hr=60&blockage_percent=25")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "success"
    assert body["coverage"]["drainage_model"] == "SYNTHETIC/PROTOTYPE"
    # Dharwad lies outside the synthetic grid; those roads are unassessed (treated SAFE).
    assert body["coverage"]["route_points_outside_drainage_grid_pct"] > 0
