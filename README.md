# Climate Hazard Trend Analyzer

A full-stack MVP that analyzes historical daily maximum temperatures and identifies heatwaves for a chosen city and year range.

## What it does

- Searches cities using Open-Meteo geocoding.
- Fetches historical daily maximum temperature from Open-Meteo.
- Detects heatwaves: **3 or more consecutive days above a local seasonal 95th-percentile threshold** calculated from the 1991–2020 baseline.
- Displays annual events, heatwave days, a rolling trend, individual events, coverage, and methodology.
- Caches raw weather responses and derived analyses. Configure MongoDB for persistent NoSQL caching; a bounded in-memory cache keeps local development usable without it.

## Run locally

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

Set `MONGODB_URI` in `.env` to use MongoDB Atlas. Without it, caching is in memory only.

### Frontend

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

The Vite development server proxies `/api` to `http://localhost:8000`.

## Tests

```powershell
pytest
```

## Assumptions and limitations

- Results describe the selected coordinate/city, not an entire state or bounding box.
- The app describes observed historical indicators; it does not forecast or establish climate-change causation.
- A fixed 1991–2020 baseline improves comparison across selected ranges. Locations without adequate baseline data return a clear error.
- Daily maximum temperature does not represent humidity, nighttime heat, health risk, or local station observations.

## Data source

Open-Meteo Geocoding API and Historical Weather API, requested in Celsius and UTC. The API/source details and coverage are returned with each analysis.

## Architecture

The React frontend searches for a city or lets the user click a map coordinate, then requests `POST /api/analyses/heatwave` from the FastAPI backend. FastAPI validates the request, checks the derived-analysis cache, fetches/caches raw Open-Meteo daily temperatures when required, and runs the pure heatwave-analysis module. MongoDB Atlas is the intended persistent NoSQL cache; local development uses an in-memory fallback only when `MONGODB_URI` is not configured. The response contains JSON summary values, yearly values (including a trailing 5-year average), events, coverage, methodology, and a linear trend slope. The frontend renders an interactive Chart.js trend chart and can export event details as CSV.

## Security and performance

- Coordinates, labels, and date ranges are validated server-side; a request is limited to 40 years.
- Weather requests have timeouts and bounded retries.
- Raw weather payloads and derived analysis responses are cached separately with expiry.
- CORS is restricted through the `CORS_ORIGINS` environment variable.
- The expensive analysis route has an in-process limit of 10 requests per IP per minute. Use Redis or another shared limiter in a multi-instance deployment.

## Improvements with more time

- Configure and monitor production MongoDB Atlas, then replace the in-process rate limiter with Redis.
- Add integration/API tests and accessibility tests in addition to hazard unit tests.
- Add PDF export, stronger spatial aggregation for full states/bounding boxes, and alternative hazards such as drought and heavy rainfall.
- Add Mann–Kendall trend testing and uncertainty/significance explanations.

## AI disclosure

AI assistance was used for planning, documentation, boilerplate generation, and review. The implementation, assumptions, test cases, and output must be reviewed, run, and understood by the submitter before submission.
