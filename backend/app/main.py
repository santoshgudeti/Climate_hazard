from __future__ import annotations
from datetime import date
from hashlib import sha256
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from .config import BASELINE_START_YEAR, BASELINE_END_YEAR, CORS_ORIGINS
from .schemas import HeatwaveRequest
from .repository import CacheRepository
from .weather_client import search_locations, fetch_daily_max_temperature, WeatherProviderError
from .heatwave import parse_daily, build_thresholds, detect_heatwaves, annual_metrics, summarize

app = FastAPI(title="Climate Hazard Trend Analyzer", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
repository = CacheRepository()
request_windows: dict[str, list[float]] = {}


def key_for(value: object) -> str:
    return sha256(repr(value).encode()).hexdigest()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.middleware("http")
async def limit_analysis_requests(request: Request, call_next):
    """Small in-process safety limit; use a shared store such as Redis when horizontally scaling."""
    if request.url.path == "/api/analyses/heatwave":
        import time
        now = time.monotonic()
        client = request.client.host if request.client else "unknown"
        active = [stamp for stamp in request_windows.get(client, []) if now - stamp < 60]
        if len(active) >= 10:
            return JSONResponse(status_code=429, content={"detail": "Too many analysis requests. Please wait a minute."})
        active.append(now)
        request_windows[client] = active
    return await call_next(request)


@app.get("/api/locations")
async def locations(name: str = Query(min_length=2, max_length=80)):
    try:
        results = await search_locations(name)
    except WeatherProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return [{"id": row.get("id"), "name": row["name"], "country": row.get("country"), "admin1": row.get("admin1"), "latitude": row["latitude"], "longitude": row["longitude"]} for row in results]


@app.post("/api/analyses/heatwave")
async def analyze_heatwave(request: HeatwaveRequest):
    normalized = (round(request.latitude, 3), round(request.longitude, 3))
    analysis_key = key_for((normalized, request.start_year, request.end_year, "heatwave-v1", "seasonal-p95-1991-2020"))
    cached = repository.get("analysis_cache", analysis_key)
    if cached:
        cached["cache_status"] = {"raw_weather": "hit", "analysis": "hit"}
        return cached
    fetch_start = date(min(request.start_year, BASELINE_START_YEAR), 1, 1)
    fetch_end = date(max(request.end_year, BASELINE_END_YEAR), 12, 31)
    weather_key = key_for((normalized, fetch_start.isoformat(), fetch_end.isoformat(), "temperature_2m_max_celsius_utc"))
    raw = repository.get("weather_cache", weather_key)
    raw_status = "hit" if raw else "miss"
    try:
        if raw is None:
            raw = await fetch_daily_max_temperature(request.latitude, request.longitude, fetch_start, fetch_end)
            repository.set("weather_cache", weather_key, raw)
        days = parse_daily(raw)
        baseline = [row for row in days if BASELINE_START_YEAR <= row["date"].year <= BASELINE_END_YEAR]
        thresholds = build_thresholds(baseline)
        if len(thresholds) < 350:
            raise HTTPException(status_code=422, detail="Insufficient valid 1991–2020 baseline data for this location")
        selected = [row for row in days if request.start_year <= row["date"].year <= request.end_year]
        if not selected:
            raise HTTPException(status_code=422, detail="No daily temperature data for the selected range")
        events, coverage = detect_heatwaves(selected, thresholds)
        metrics = annual_metrics(events, request.start_year, request.end_year)
        result = {
            "location": {"label": request.label, "latitude": request.latitude, "longitude": request.longitude},
            "range": {"start_year": request.start_year, "end_year": request.end_year},
            "summary": summarize(events, metrics),
            "annual_metrics": metrics,
            "events": events,
            "coverage": coverage,
            "methodology": {"hazard": "Heatwave", "definition": "Three or more consecutive days with daily maximum temperature strictly above a local seasonal 95th-percentile threshold.", "baseline": "1991–2020; percentile uses a ±7-day seasonal window.", "source": "Open-Meteo Historical Weather API; daily temperature_2m_max in Celsius, UTC.", "algorithm_version": "heatwave-v1"},
            "cache_status": {"raw_weather": raw_status, "analysis": "miss"},
        }
        repository.set("analysis_cache", analysis_key, result)
        return result
    except WeatherProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


# Serve compiled frontend in production when frontend/dist is present
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

