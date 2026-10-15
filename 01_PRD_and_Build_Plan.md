# Climate Hazard Trend Analyzer — Product Requirements & Build Plan

## 1. Purpose

Build a small, credible web application that lets a user select a location and date range, then understand how **heatwave events** have changed over time. The product turns daily historical temperature data into transparent climate indicators rather than presenting raw weather values without context.

The case study permits other hazards, but the first release intentionally focuses on Heatwave. A dependable single-hazard analysis is more valuable than several incomplete hazard types.

## 2. Problem and users

Historical weather data is difficult to interpret at a glance. A user should not have to download daily observations and manually decide whether a hot spell was unusual.

The primary user is a non-specialist analyst, planner, journalist, or climate-curious resident who wants to answer:

- How many heatwave events occurred each year in this place?
- How long and how intense were they?
- Is the observed indicator increasing, decreasing, or inconclusive in the selected period?
- What definition and data source produced the result?

## 3. MVP scope

### Inputs

- Location: choose a supported city or search for a city; the UI resolves it to latitude and longitude.
- Optional advanced location: custom latitude/longitude pair. A latitude-longitude *box* is deferred because a true box analysis requires gridded data aggregation rather than a single-point weather request.
- Hazard: Heatwave, selected and currently the only active option.
- Analysis range: start and end year, initially constrained to 1990 through the latest complete year supported by the source.

### Outputs

- Headline metric cards: total events, total heatwave days, mean event duration, and mean peak temperature.
- Annual chart: event count and heatwave-day count by year.
- Event table: start date, end date, duration, peak maximum temperature, and threshold used.
- Trend statement, such as: “The 5-year rolling average rose from 1.2 to 1.7 events/year (+42%) between the beginning and end of the selected period.”
- A methods panel naming the source, retrieved date, data coverage, heatwave definition, and caveats.

### Explicitly out of scope for the first submission

- Drought and heavy-rainfall logic.
- Forecasting future climate.
- Claims of causation or attribution to climate change.
- Authentication, collaboration, and polished reporting workflows.

## 4. Functional requirements

| ID | Requirement | Acceptance criterion |
| --- | --- | --- |
| FR-1 | A user can select/search a city and submit an analysis. | A valid city becomes coordinates and returns a result or a clear empty/error state. |
| FR-2 | A user can choose a valid year range. | Client and server reject inverted, unsupported, or excessively large ranges. |
| FR-3 | The backend retrieves daily historical maximum temperature from a public source. | Returned data includes dates and `temperature_2m_max` in Celsius. |
| FR-4 | The backend detects heatwave events. | An event has at least 3 consecutive valid days above the appropriate percentile threshold. |
| FR-5 | Results are persisted in NoSQL storage and reused. | Identical analysis requests are served from a non-expired cached analysis. |
| FR-6 | The UI visualizes annual results and event detail. | Charts are responsive, labelled, and have tooltips. |
| FR-7 | The app explains its result. | Every result view exposes definition, source, range, and limitations. |

## 5. Recommended technical design

### Stack

- Frontend: React + TypeScript + Vite; Chart.js with `react-chartjs-2`; Tailwind or compact CSS modules.
- Backend: Python 3.12, FastAPI, Pydantic, HTTPX, NumPy/Pandas.
- Database: MongoDB Atlas free tier via Motor/PyMongo. Collections: `weather_cache` and `analysis_cache`.
- Data: Open-Meteo Historical Weather API (daily `temperature_2m_max`, Celsius, UTC), plus its geocoding API for city search.
- Deployment: Vercel/Netlify for frontend and Render/Railway for API; MongoDB Atlas for persistence.

Open-Meteo is chosen for its simple, openly accessible historical daily endpoint. The provider and query parameters must be stored with cached records so an analysis is reproducible. NOAA or Copernicus would be sensible alternatives where station provenance or gridded spatial aggregation is needed.

### API shape

`GET /api/locations?name=Delhi`

Returns a short, bounded list of geocoded candidates.

`POST /api/analyses/heatwave`

Request:

```json
{
  "latitude": 28.6139,
  "longitude": 77.2090,
  "label": "Delhi, India",
  "start_year": 1990,
  "end_year": 2025
}
```

Response includes `summary`, `annual_metrics`, `events`, `methodology`, `coverage`, and `cache_status`.

`GET /health`

Health check without disclosing configuration.

### Data model

`weather_cache` key: rounded coordinates (e.g. 3 decimal places), source, requested start/end dates, unit, schema version. Document stores raw provider payload, fetched timestamp, coverage metadata, and a TTL expiry.

`analysis_cache` key: normalized coordinates, selected range, hazard version, baseline version, and source version. Document stores the response-ready derived metrics, event list, creation time, and a TTL expiry. Include `algorithm_version` so a change in logic never reuses incompatible analysis.

Mongo TTL indexes may expire old cached documents automatically. The application must still tolerate a cache miss or unavailable database and return a controlled 503 rather than an ambiguous result.

## 6. Climate-hazard method

### Heatwave definition

An event is **three or more consecutive calendar days** whose daily maximum temperature is strictly above a local, seasonal 95th-percentile threshold.

To avoid labelling every normal summer day as equally unusual, calculate a separate threshold for each calendar day:

1. Fetch the analysis range plus the baseline window necessary to compute thresholds.
2. Use a fixed 1991–2020 baseline where data are available.
3. For each calendar day, gather daily maximum temperatures in a ±7-day window across all baseline years.
4. Calculate its 95th percentile using a documented NumPy percentile method.
5. Mark selected-range days above their matched threshold; split runs on missing days or days at/below threshold.
6. Retain runs of length ≥3 as events.

For a location/range that does not contain sufficient baseline coverage, return an explicit “insufficient baseline data” response rather than silently changing the definition. Leap day can use the 28 February/1 March neighbourhood.

For each event calculate start/end dates, duration, peak daily maximum temperature, maximum exceedance above threshold, and cumulative exceedance. Aggregate count, days, mean duration, and mean/max intensity by year.

### Trend method

The default narrative compares the mean annual event count in the first and final five calendar years of the selected range. Display a 5-year rolling average chart. Also calculate an ordinary least-squares slope of annual event count per decade for context; describe it as an observed trend, not a prediction or causal finding.

If either comparison window has too few valid years, do not show a percentage change. Say that the period is too short for a robust comparison.

## 7. Data quality, safety, and performance

- Validate coordinate bounds, request body size, range length, and allowed hazard values server-side.
- Round coordinates only for cache keys; retain requested coordinates in the response.
- Deduplicate dates, sort chronologically, convert values to float, and treat missing/null/implausible values as gaps. Never bridge a gap when counting consecutive days.
- Record `expected_days`, `received_days`, `missing_days`, and provider metadata. Show a warning for material incompleteness.
- Use HTTP timeouts, retry only transient provider failures with bounded exponential backoff, and return useful 4xx/5xx JSON errors.
- Add IP-based rate limiting to expensive analysis routes; cap city search results and cache external responses.
- Keep secrets in environment variables, restrict CORS to deployed frontend origins, and avoid logging full user IPs or secrets.

## 8. UX flow

1. User opens dashboard, sees Heatwave selected and a simple method note.
2. User searches/selects a city, selects years, and chooses Analyze.
3. UI validates input, shows progress, then displays cards, annual chart, event table, and methodology together.
4. If there are no events, show a valid zero-events result—not an error.
5. If data are unavailable or incomplete, show the affected date coverage and a retry action.

Accessibility: use actual form labels, keyboard-operable controls, sufficient contrast, chart text alternatives/table data, and do not convey trend only through colour.

## 9. Implementation sequence (8–10 hours)

| Timebox | Deliverable |
| --- | --- |
| 0:00–0:30 | Repository, README skeleton, architecture decision, environment example. |
| 0:30–2:30 | FastAPI project, provider client, validation, raw-data cache. Test a real city manually. |
| 2:30–4:00 | Pure heatwave detection and annual aggregation functions with unit tests, including missing-date and 3-day boundary cases. |
| 4:00–5:00 | Mongo analysis cache, API response model, error handling/rate limit. |
| 5:00–7:00 | React form, loading/error/empty states, API integration. |
| 7:00–8:00 | Charts, event table, methodology/caveat panel. |
| 8:00–9:00 | Deploy, smoke-test deployed URLs, record data assumptions. |
| 9:00–10:00 | README, demo video, final QA and submission. |

## 10. Test and completion checklist

- Unit-test event detection: exactly 3 days, four days, interruption, missing date, threshold equality, and year boundary.
- Unit-test input validation and trend percentage edge cases (zero baseline and short ranges).
- Mock provider response for backend tests; do not make tests depend on live weather services.
- Manually check Delhi and a temperate city, an empty result, an invalid range, and a repeated request showing cache reuse.
- Verify deployed frontend can reach API over HTTPS and production CORS is restricted.
- README documents setup, architecture, real source, algorithm, assumptions, tests, deployment, AI usage, and next improvements.

## 11. Risks and decisions

| Risk | Decision/mitigation |
| --- | --- |
| A point API cannot represent a whole state or box. | MVP describes results as conditions at/near the selected coordinate; add gridded aggregation later. |
| Percentile threshold may vary by source/reprocessing. | Persist source, query, units, baseline, and algorithm version. |
| Historical APIs can be slow/unavailable. | Cache raw and derived results, timeout requests, surface provider failures. |
| A percentage claim can mislead. | State comparison windows and omit percentage where denominator/coverage is unsuitable. |
| Limited time. | Deliver Heatwave end-to-end before maps/export/Mann–Kendall bonus work. |

## 12. Future enhancements

Add map-based point selection (Leaflet), CSV export, drought/rainfall modules with their own definitions, multi-point/gridded region aggregation, Mann–Kendall significance testing, and tests against a curated reference dataset.
