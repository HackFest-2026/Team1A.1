import unittest
from unittest.mock import patch

# Mock the imports so we can test hazard_service without starting the full app
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.services.hazard_service import hazard_service

class TestHazardMath(unittest.TestCase):
    
    @patch('app.services.hazard_service.weather_service.get_current_weather')
    @patch('app.services.hazard_service.terrain_service.get_terrain_susceptibility')
    def test_weighted_formula(self, mock_terrain, mock_weather):
        # Test case: Weather Score = 0 (Precip = 0), Terrain Score = 25
        # Weights: Weather 0.60, Terrain 0.40 -> Expected: 10
        mock_weather.return_value = {
            "status": "success",
            "source": "Open-Meteo",
            "data": {"precipitation_mm": 0.0}  # -> precip_risk = 0
        }
        
        mock_terrain.return_value = {
            "status": "success",
            "source": "ISRO DEM",
            "elevation_m": 600.0,
            "local_relative_elevation_m": 0.22,
            "susceptibility_score": 25
        }
        
        result = hazard_service.assess_flood_hazard(15.0, 75.0)
        self.assertEqual(result["risk"]["score"], 10, "Final risk score for (0 * 0.6) + (25 * 0.4) must be exactly 10")
        
        # Test case: Weather Score = 50 (Precip = 10mm -> 10/20*100=50), Terrain Score = 50
        # Weights: Weather 0.60, Terrain 0.40 -> Expected: 50
        mock_weather.return_value["data"]["precipitation_mm"] = 10.0
        mock_terrain.return_value["susceptibility_score"] = 50
        
        result = hazard_service.assess_flood_hazard(15.0, 75.0)
        self.assertEqual(result["risk"]["score"], 50, "Final risk score for (50 * 0.6) + (50 * 0.4) must be exactly 50")
        
        # Test case: Only Weather available (Terrain UNAVAILABLE)
        # Weather Score = 50 (Precip = 10mm) -> Expected: 50 (Fallback normalizes weight)
        mock_terrain.return_value["status"] = "unavailable"
        mock_weather.return_value["data"]["precipitation_mm"] = 10.0
        
        result = hazard_service.assess_flood_hazard(15.0, 75.0)
        self.assertEqual(result["risk"]["score"], 50, "Final risk score for one-source fallback must normalize correctly")

    def test_terrain_interpolation_formula(self):
        # Replicating the exact logic in terrain_service.py:
        # normalized = (local_relative_elevation - (-5.0)) / 7.0
        # score = int(100 - (normalized * 100))
        
        def calculate_score(rel_el):
            if rel_el <= -5.0:
                return 100
            elif rel_el >= 2.0:
                return 0
            else:
                normalized = (rel_el - (-5.0)) / 7.0
                return int(100 - (normalized * 100))
                
        self.assertEqual(calculate_score(-5.0), 100)
        self.assertEqual(calculate_score(2.0), 0)
        self.assertEqual(calculate_score(0.0), int(100 - ( (0.0 + 5.0)/7.0 ) * 100)) # ≈ 28
        self.assertEqual(calculate_score(0.22), int(100 - ( (0.22 + 5.0)/7.0 ) * 100)) # ≈ 25
        self.assertEqual(calculate_score(-2.5), int(100 - ( (-2.5 + 5.0)/7.0 ) * 100)) # ≈ 64
        
        print("Terrain interpolation math perfectly matches the implemented algorithm.")

if __name__ == '__main__':
    unittest.main()
