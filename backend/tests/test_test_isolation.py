"""Guards for the test harness itself (see tests/conftest.py)."""
from pathlib import Path

import pytest
import requests

from app.config.settings import settings, ROOT_DIR


def test_database_is_not_the_runtime_database():
    assert Path(settings.DATABASE_PATH).resolve() != (ROOT_DIR / "data" / "aegis.db").resolve()
    assert "aegis-test-" in settings.DATABASE_PATH


def test_outbound_network_is_blocked():
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get("https://api.open-meteo.com/v1/forecast", timeout=2)


def test_weather_degrades_to_unavailable_offline():
    from app.services.weather_service import weather_service

    weather_service.clear_cache()
    assert weather_service.get_current_weather()["status"] == "unavailable"
