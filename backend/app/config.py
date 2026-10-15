import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "climate_hazard_analyzer")
raw_origins = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS = [origin.strip() for origin in raw_origins.split(",") if origin.strip()] or ["*"]
WEATHER_CACHE_TTL_SECONDS = 60 * 60 * 24 * 30
ANALYSIS_CACHE_TTL_SECONDS = 60 * 60 * 24 * 7
BASELINE_START_YEAR = 1991
BASELINE_END_YEAR = 2020
MIN_BASELINE_OBSERVATIONS = 100
MIN_EVENT_DAYS = 3
