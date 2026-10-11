class RunoffService:
    DEFAULT_URBAN_COEFFICIENT = 0.85

    def calculate_runoff(self, rainfall_mm_hr, coefficient=0.85):
        return rainfall_mm_hr * coefficient

    def calculate_volume_m3(self, runoff_mm_hr, area_m2, duration_hr):
        return (runoff_mm_hr * area_m2 / 1000.0) * duration_hr

    def get_coefficient_info(self):
        return {
            "DEFAULT_URBAN_COEFFICIENT": self.DEFAULT_URBAN_COEFFICIENT,
            "description": "0.85 coefficient used for high-density urban areas with significant impervious surfaces."
        }

runoff_service = RunoffService()
