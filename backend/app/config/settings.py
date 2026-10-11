import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory Resolution
# settings.py -> config -> app -> backend -> root (ResilienceRoute)
CONFIG_DIR = Path(__file__).resolve().parent
APP_DIR = CONFIG_DIR.parent
BACKEND_DIR = APP_DIR.parent
ROOT_DIR = BACKEND_DIR.parent

# Load .env if present in backend directory
env_path = BACKEND_DIR / ".env"
if env_path.exists():
    load_dotenv(env_path)


class Settings:
    """Lightweight application configuration."""

    def __init__(self):
        self.PORT: int = int(os.getenv("PORT", "8000"))
        self.ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
        self.DEMO_MODE: bool = os.getenv("DEMO_MODE", "true").lower() == "true"

        # DEM Path Configuration (Fallback to portable root data path)
        default_dem_path = (
            ROOT_DIR / "data" / "terrain" / "cdnd43d_v3r1" / "cdnd43d.tif"
        )
        env_dem_path = os.getenv("DEM_PATH")
        self.DEM_PATH: str = (
            env_dem_path if env_dem_path else str(default_dem_path)
        )

        # OSM Graph Path Configuration
        default_osm_path = (
            ROOT_DIR / "data" / "osm" / "hubballi_dharwad_drive.graphml"
        )
        env_osm_path = os.getenv("OSM_GRAPH_PATH")
        self.OSM_GRAPH_PATH: str = (
            env_osm_path if env_osm_path else str(default_osm_path)
        )

        # Database Path Configuration (Fallback to data/aegis.db)
        default_db_path = ROOT_DIR / "data" / "aegis.db"
        env_db_path = os.getenv("DATABASE_PATH")
        self.DATABASE_PATH: str = env_db_path if env_db_path else str(default_db_path)
        self.DATABASE_URL: str = f"sqlite:///{self.DATABASE_PATH}"

        # Geographic coverage (ADR-008). Inputs farther than this from the loaded road
        # network are rejected. Provisional prototype default, not a validated threshold.
        self.MAX_SNAP_DISTANCE_M: float = float(os.getenv("MAX_SNAP_DISTANCE_M", "250"))

        # Weather observations older than this are STALE and treated as unknown.
        # Provisional: Open-Meteo "current" values are 15-minute model intervals.
        self.WEATHER_MAX_AGE_MINUTES: float = float(os.getenv("WEATHER_MAX_AGE_MINUTES", "90"))


settings = Settings()
