# Technical Walkthrough & Interview Guide

Use this document to understand and explain the project in your own words. Do not memorise a script; be able to point to the relevant file, run a request, and explain the trade-offs.

## 1. A 60-second explanation

“I built a historical heatwave trend analyzer. The React frontend accepts a city and year range; it calls a FastAPI backend. The backend resolves/fetches daily maximum temperatures from Open-Meteo, validates and caches the source data, then applies a region- and season-specific heatwave definition: at least three consecutive days whose maximum temperature exceeds that calendar day’s 95th-percentile threshold from a 1991–2020 baseline. It aggregates events by year and returns cards, chart series, event records, method information, and coverage. I cache derived analyses in MongoDB as well as raw weather responses so repeat requests are quick and the external API is not unnecessarily called. I deliberately finished a transparent heatwave vertical slice instead of making incomplete drought and rainfall features.”

## 2. Architecture, component by component

```text
Browser (React + TypeScript)
  Location/year form → API client → dashboard/chart/table/method panel
                                      │ HTTPS JSON
                                      ▼
FastAPI application
  route → request validation → cache lookup → weather client → analysis service
                                                        │
                              MongoDB ← raw cache + derived analysis cache
                                                        │ cache miss only
                                                        ▼
                                     Open-Meteo historical daily API
```

### Frontend responsibilities

The frontend collects input, prevents obvious invalid ranges, shows loading/error/empty states, and renders server-returned metrics. It does **not** calculate climate events. Keeping domain logic on the server makes the result consistent for all clients and easier to unit-test.

Good component boundaries:

- `LocationSearch`: debounced, bounded request to the geocoding endpoint.
- `AnalysisForm`: coordinates/year state and submission validation.
- `SummaryCards`, `AnnualTrendChart`, `EventTable`, `MethodologyPanel`: presentation-only components.
- `api.ts`: typed API calls and response/error conversion.

### Backend responsibilities

- Pydantic request models validate latitude (−90 to 90), longitude (−180 to 180), range ordering, and maximum span.
- `weather_client.py` owns provider URL construction, timeouts, response parsing, unit request, and bounded retries.
- `hazards/heatwave.py` is a pure function module. It takes date/value records and returns thresholds, events, annual metrics, and coverage—no HTTP or database calls.
- `repository.py` owns Mongo keys, indexes, and serialization.
- The API route coordinates these components and maps known failures to safe error responses.

This separation is intentional: I can test the heatwave rule with a tiny synthetic dataset without the network or database, and I can replace the provider without rewriting the hazard algorithm.

## 3. The heatwave algorithm, step by step

1. Ask the weather source for daily `temperature_2m_max` in Celsius over the selected years and the 1991–2020 baseline.
2. Sort records by date; remove duplicate dates; parse temperatures as finite numbers.
3. Keep a coverage report. A null value or absent calendar date is a gap.
4. For each day-of-year, gather baseline observations within a ±7-day seasonal window, then compute its 95th percentile.
5. Match each selected date to its seasonal threshold. A date qualifies only when `tmax > threshold`; equality does not qualify, matching “above the 95th percentile.”
6. Walk in calendar order. Consecutive qualifying days are one run. Any non-qualifying or missing day closes it.
7. Keep runs of three or more days. For each, calculate duration, peak temperature, maximum threshold exceedance, and cumulative exceedance.
8. Group retained events by their start year and calculate annual counts/days. Compute rolling averages and a guarded beginning-versus-end comparison.

### Pseudocode

```python
run = []
for day in ordered_selected_days:
    qualifies = day.is_present and day.tmax > threshold_for(day.date)
    contiguous = run and day.date == run[-1].date + one_day
    if qualifies and (not run or contiguous):
        run.append(day)
    else:
        save_if_at_least_three_days(run)
        run = [day] if qualifies else []
save_if_at_least_three_days(run)
```

The actual implementation should separately require chronological adjacency; merely iterating an array is not enough because an omitted date must not turn 1 June and 3 June into a false two-day sequence.

## 4. Why these choices were made

| Choice | Reason | Trade-off |
| --- | --- | --- |
| Heatwave only | Fits limited time while proving the complete stack. | Fewer features; other hazards remain planned work. |
| Daily maximum temperature | Directly supports a basic heatwave definition and keeps provider calls/light UI manageable. | Does not capture humid heat or nighttime minimum temperature. |
| Seasonal 95th percentile | Adapts to both geography and season. | More computation and a baseline-data requirement. |
| 1991–2020 fixed baseline | Keeps analyses comparable across user-selected ranges. | The baseline choice is itself an assumption and must be disclosed. |
| 3 consecutive days | Matches the case-study example and prevents one-day spikes from becoming events. | Other organizations use different operational definitions. |
| MongoDB cache | Satisfies NoSQL requirement and makes repeated analysis quicker. | Requires hosted configuration and cache invalidation/versioning. |
| Open-Meteo | Simple historical daily API, practical for an MVP. | A gridded/reanalysis point is not a local station observation. |

## 5. Cache design you should be able to explain

There are two caches because they solve different costs.

`weather_cache` saves the provider response for normalized coordinates, date range, requested variable, units, and source version. It avoids repeated external requests and preserves the evidence used for analysis.

`analysis_cache` saves the calculated response for normalized coordinates, selected range, hazard name, baseline, source, and `algorithm_version`. It avoids re-running percentile and event logic for identical queries.

When I change heatwave logic, I bump `algorithm_version`; the old derived record no longer matches the key. This is safer than serving a silently stale result. Both collections use a TTL expiry, but records also carry fetched/created timestamps that the UI can disclose.

## 6. Important edge cases

- Exactly three qualifying adjacent dates = one event.
- Two qualifying dates = not an event.
- A day exactly equal to the percentile threshold = not qualifying.
- Missing 2 June between hot 1 June and 3 June breaks the run.
- An event crossing New Year stays one event; annual allocation must be documented (MVP attributes it to start year).
- A range with no events is a successful response with zero metrics.
- A range too short for the 5-year comparison or a zero early average should say comparison is unavailable, rather than divide by zero or make an infinite percentage claim.
- Insufficient 1991–2020 baseline data returns a clear analysis-unavailable message.

## 7. Questions a reviewer may ask, with honest answers

### “Why not use a fixed 40°C threshold?”

Because heat risk and unusual heat are local. A fixed threshold would undercount unusual heat in cooler climates and can misrepresent seasonal conditions. The percentile rule is the case-study direction and adapts to local historical temperatures.

### “Is this proof that climate change caused the observed increase?”

No. The application reports a descriptive historical indicator. Causal attribution needs a much broader scientific design and evidence base. The UI calls it an observed trend and exposes data coverage and method.

### “Why do you need the baseline if a user selects 2015–2020?”

The selected period tells us which events to report. The fixed historical baseline tells us what is unusual. Separating them prevents the threshold from changing simply because the user changes the viewing window.

### “Why cache both data and analyses?”

Raw cache protects the provider and supports reproducibility; derived cache avoids CPU work and improves response latency. They have different keys and invalidation needs.

### “How would you support a state or bounding box?”

I would use gridded data, sample or aggregate all included grid cells, calculate a clearly defined spatial statistic, and disclose resolution/coverage. I would not pass a box centre point off as a regional analysis.

### “How would you add drought or rainfall?”

I would make hazard modules with their own input variables and definitions—for example precipitation deficit over a rolling window, or heavy-rain days above a local percentile. They should not reuse the heatwave rule just because the interface is shared.

### “What would you do with more time?”

First, add map selection and CSV export after the core is reliable. Next, add a Mann–Kendall trend test with a clear explanation of significance and limitations, then multiple hazards and true spatial aggregation.

## 8. Live-change readiness

Before an interview, run the project locally and know these paths: the request model, provider client, threshold function, event grouping loop, aggregation function, cache-key builder, route handler, API client, and chart component. Be prepared to make a small change such as:

- change the minimum event duration from 3 to 4 days;
- add a `min_duration_days` configuration value;
- alter a chart label or empty-state message;
- add a unit test for a missing date;
- return coverage in the response.

After any change, explain the effect, run the relevant unit test, then make one API/UI check. Do not claim an external result is scientifically validated beyond the documented method.

## 9. README and disclosure checklist

The case study explicitly asks for AI-tool disclosure. In the README, accurately state the tools used and the kind of help received (for example, planning, boilerplate, review, or debugging), then verify and be able to explain every committed line yourself. Include setup, environment variables, architecture, source URL/name, algorithm, baseline, caching, assumptions, limitations, tests, deployed URL, and future work.

The best interview posture is straightforward: explain what you personally checked, which trade-offs were deliberate, and which parts are MVP assumptions. A precise limitation is stronger than an unsupported claim.
