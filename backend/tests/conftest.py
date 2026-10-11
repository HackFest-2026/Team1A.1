"""Test isolation for the AEGIS backend.

This module runs before any test module imports ``app`` and:

- points ``DATABASE_PATH`` at a fresh temporary directory (never ``data/aegis.db``),
- disables optional external providers (IMD, MOSDAC, FIRMS),
- blocks outbound network access unless a test is marked ``network`` and
  ``--run-network`` is given (weather then reports ``status: unavailable``),
- skips tests whose geospatial data files are absent, with an explicit reason,
- resets the database and module-level service singletons between test modules.
"""
import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path

import pytest

if "app.config.settings" in sys.modules:
    raise RuntimeError(
        "app.config.settings was imported before tests/conftest.py; "
        "test database isolation cannot be guaranteed."
    )

REPO_ROOT = Path(__file__).resolve().parents[2]
_TMP_DIR = tempfile.mkdtemp(prefix="aegis-test-")
os.environ["DATABASE_PATH"] = os.path.join(_TMP_DIR, "aegis-test.db")
for _key in ("IMD_API_KEY", "MOSDAC_API_KEY", "FIRMS_API_KEY"):
    os.environ[_key] = ""
os.environ["IMD_ACCESS_AUTHORIZED"] = "false"
os.environ["DEMO_ALERT_MODE"] = "true"


# ---------------------------------------------------------------------------
# Network guard
# ---------------------------------------------------------------------------
class NetworkBlockedError(OSError):
    """Raised when a test attempts outbound network access."""


_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_getaddrinfo = socket.getaddrinfo


def _blocked_connect(self, address):
    if self.family == getattr(socket, "AF_UNIX", object()):
        return _real_connect(self, address)
    if isinstance(address, tuple) and address[0] in ("127.0.0.1", "localhost", "::1"):
        return _real_connect(self, address)
    raise NetworkBlockedError(f"Network access blocked in tests: {address!r}")


def _blocked_connect_ex(self, address):
    if self.family == getattr(socket, "AF_UNIX", object()):
        return _real_connect_ex(self, address)
    if isinstance(address, tuple) and address[0] in ("127.0.0.1", "localhost", "::1"):
        return _real_connect_ex(self, address)
    raise NetworkBlockedError(f"Network access blocked in tests: {address!r}")


def _blocked_getaddrinfo(host, *args, **kwargs):
    raise NetworkBlockedError(f"DNS lookup blocked in tests: {host!r}")


def _block_network():
    socket.socket.connect = _blocked_connect
    socket.socket.connect_ex = _blocked_connect_ex
    socket.getaddrinfo = _blocked_getaddrinfo


def _allow_network():
    socket.socket.connect = _real_connect
    socket.socket.connect_ex = _real_connect_ex
    socket.getaddrinfo = _real_getaddrinfo


_block_network()


# ---------------------------------------------------------------------------
# Options, markers and data-availability skips
# ---------------------------------------------------------------------------
def pytest_addoption(parser):
    parser.addoption(
        "--run-network",
        action="store_true",
        default=False,
        help="Run tests marked 'network' (real outbound calls).",
    )


def pytest_collection_modifyitems(config, items):
    from app.config.settings import settings

    if Path(settings.DATABASE_PATH).resolve() == (REPO_ROOT / "data" / "aegis.db").resolve():
        raise pytest.UsageError("Refusing to run tests against data/aegis.db")

    graph_missing = not os.path.exists(settings.OSM_GRAPH_PATH)
    dem_missing = not os.path.exists(settings.DEM_PATH)
    run_network = config.getoption("--run-network")

    for item in items:
        if graph_missing and "requires_graph" in item.keywords:
            item.add_marker(pytest.mark.skip(
                reason=f"OSM graph not found at {settings.OSM_GRAPH_PATH} (set OSM_GRAPH_PATH)"))
        if dem_missing and "requires_dem" in item.keywords:
            item.add_marker(pytest.mark.skip(
                reason=f"DEM not found at {settings.DEM_PATH}; see data/terrain/README.md"))
        if "network" in item.keywords and not run_network:
            item.add_marker(pytest.mark.skip(reason="network test; use --run-network"))


@pytest.fixture(autouse=True)
def _network_policy(request):
    if "network" in request.keywords and request.config.getoption("--run-network"):
        _allow_network()
        yield
        _block_network()
    else:
        yield


# ---------------------------------------------------------------------------
# Per-module state reset
# ---------------------------------------------------------------------------
def reset_app_state():
    """Recreate an empty schema and reload every stateful service singleton."""
    from app.database.base import Base
    from app.database.connection import engine, init_db
    from app.services.scenario_service import ScenarioService, scenario_service
    from app.services.weather_service import weather_service
    from app.services.incidents.incident_service import incident_service
    from app.services.field_operations.field_service import field_service
    from app.services.field_operations.evidence_service import evidence_service as legacy_evidence
    from app.services.route_monitor_service import route_monitor_service
    from app.services.route_replacement_service import route_replacement_service

    Base.metadata.drop_all(bind=engine)
    init_db()

    scenario_service.set_active(False)
    scenario_service._config = ScenarioService()._config
    weather_service.clear_cache()
    legacy_evidence.evidence.clear()
    legacy_evidence.reports.clear()
    incident_service._load_from_db()
    field_service._load_from_db()
    route_monitor_service._load_from_db()
    route_replacement_service._audit_log.clear()


@pytest.fixture(autouse=True, scope="module")
def _fresh_app_state():
    reset_app_state()
    yield


def pytest_sessionfinish(session, exitstatus):
    terrain = sys.modules.get("app.services.terrain_service")
    if terrain is not None:
        terrain.terrain_service.close()
    if os.environ.get("AEGIS_KEEP_TEST_DB") != "1":
        shutil.rmtree(_TMP_DIR, ignore_errors=True)
