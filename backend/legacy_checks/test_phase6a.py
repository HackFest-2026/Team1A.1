import os
import sys
import time
import requests
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from app.services.national_weather_service import national_weather_service, IMDService

def run_tests():
    print("============================================================")
    print("  PHASE 6A: NATIONAL EARLY-WARNING DATA TESTS")
    print("============================================================")
    
    # We will test IMDService directly with mocked requests.
    service = IMDService()
    
    print("B. Missing credentials handling")
    service.access_configured = False
    status = service.get_status()
    assert status["status"] == "unavailable"
    assert status["mode"] == "NOT_CONFIGURED"
    
    weather = service.get_weather()
    assert weather["status"] == "unavailable"
    assert weather["mode"] == "NOT_CONFIGURED"
    assert len(weather["records"]) == 0
    print("PASS  Missing credentials -> NOT_CONFIGURED correctly")
    
    print("C. Successful response normalization")
    service.access_configured = True
    
    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self._json = json_data
            self.status_code = status_code
        def json(self):
            return self._json
        def raise_for_status(self):
            if self.status_code != 200:
                raise requests.exceptions.HTTPError("Error")
                
    with patch("requests.get") as mock_get:
        mock_get.return_value = MockResponse({
            "records": [
                {
                    "id": "KA-DWR", "state": "Karnataka", "district": "Dharwad", "city": "Hubballi",
                    "latitude": 15.36, "longitude": 75.12, "temperature": 28.5, "rainfall": 10.0,
                    "warning_level": "WARNING"
                }
            ]
        })
        
        res = service.get_weather(state="Karnataka")
        assert res["status"] == "success"
        assert res["mode"] == "LIVE - IMD"
        assert len(res["records"]) == 1
        record = res["records"][0]
        
        # Verify schema
        assert record["country"] == "India"
        assert record["state"] == "Karnataka"
        assert record["district"] == "Dharwad"
        assert record["weather"]["temperature_c"] == 28.5
        assert record["weather"]["precipitation_mm"] == 10.0
        assert record["warning"]["level"] == "WARNING"
        assert record["source"] == "IMD"
        assert record["mode"] == "LIVE - IMD"
        print("PASS  Normalization matches strict schema rules")
        
        print("F. Cache behavior and H. source/mode preservation")
        # Call again without mock updating
        res_cached = service.get_weather(state="Karnataka")
        assert res_cached["mode"] == "CACHED - IMD"
        assert res_cached["records"][0]["mode"] == "CACHED - IMD"
        print("PASS  Cache correctly relabels as CACHED - IMD")
        
        print("I. Geographic filtering")
        # The mock returns Karnataka, so filtering for Maharashtra should yield 0 records
        res_mh = service.get_weather(state="Maharashtra")
        assert res_mh["status"] == "success"
        assert len(res_mh["records"]) == 0
        print("PASS  Geographic filtering works")

    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")
        print("E. Timeout handling")
        res_timeout = service.get_warnings(state="Kerala")
        assert res_timeout["status"] == "unavailable"
        assert res_timeout["mode"] == "ERROR"
        assert len(res_timeout["records"]) == 0
        print("PASS  Timeouts gracefully degrade")

    print("\n============================================================")
    print("  ALL TESTS PASSED")
    print("============================================================")

if __name__ == "__main__":
    run_tests()
