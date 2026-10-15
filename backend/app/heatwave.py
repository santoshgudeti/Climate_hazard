from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta
from math import isfinite
from statistics import mean
from .config import MIN_BASELINE_OBSERVATIONS, MIN_EVENT_DAYS


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile, avoiding a heavy numeric dependency."""
    sorted_values = sorted(values)
    if not sorted_values:
        raise ValueError("Cannot calculate a percentile of no values")
    position = (len(sorted_values) - 1) * q
    lower, upper = int(position), min(int(position) + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def parse_daily(provider_data: dict) -> list[dict]:
    daily = provider_data["daily"]
    by_date: dict[date, float | None] = {}
    for raw_day, raw_temp in zip(daily.get("time", []), daily.get("temperature_2m_max", [])):
        current = date.fromisoformat(raw_day)
        temp = float(raw_temp) if raw_temp is not None else None
        by_date[current] = temp if temp is not None and isfinite(temp) and -90 < temp < 70 else None
    return [{"date": current, "tmax": by_date[current]} for current in sorted(by_date)]


def seasonal_key(day: date) -> tuple[int, int]:
    # Map leap day into the late-February seasonal neighbourhood.
    return (2, 28) if day.month == 2 and day.day == 29 else (day.month, day.day)


def build_thresholds(baseline_days: list[dict]) -> dict[tuple[int, int], float]:
    thresholds: dict[tuple[int, int], float] = {}
    for month in range(1, 13):
        for day_number in range(1, 32):
            try:
                anchor = date(2001, month, day_number)
            except ValueError:
                continue
            candidates = []
            for record in baseline_days:
                if record["tmax"] is None:
                    continue
                record_anchor = date(2001, record["date"].month, min(record["date"].day, 28) if record["date"].month == 2 and record["date"].day == 29 else record["date"].day)
                circular_distance = abs((record_anchor - anchor).days)
                circular_distance = min(circular_distance, 365 - circular_distance)
                if circular_distance <= 7:
                    candidates.append(record["tmax"])
            if len(candidates) >= MIN_BASELINE_OBSERVATIONS:
                thresholds[(month, day_number)] = percentile(candidates, 0.95)
    return thresholds


def detect_heatwaves(selected_days: list[dict], thresholds: dict[tuple[int, int], float]) -> tuple[list[dict], dict]:
    events, run = [], []
    expected = (selected_days[-1]["date"] - selected_days[0]["date"]).days + 1 if selected_days else 0
    present = sum(1 for item in selected_days if item["tmax"] is not None)

    def flush() -> None:
        nonlocal run
        if len(run) >= MIN_EVENT_DAYS:
            events.append({
                "start_date": run[0]["date"].isoformat(),
                "end_date": run[-1]["date"].isoformat(),
                "duration_days": len(run),
                "peak_temperature_c": round(max(item["tmax"] for item in run), 1),
                "max_exceedance_c": round(max(item["tmax"] - item["threshold"] for item in run), 1),
                "cumulative_exceedance_c": round(sum(item["tmax"] - item["threshold"] for item in run), 1),
            })
        run = []

    previous = None
    for item in selected_days:
        threshold = thresholds.get(seasonal_key(item["date"]))
        qualifies = item["tmax"] is not None and threshold is not None and item["tmax"] > threshold
        contiguous = previous is not None and item["date"] == previous + timedelta(days=1)
        if qualifies and (not run or contiguous):
            run.append({**item, "threshold": threshold})
        else:
            flush()
            if qualifies:
                run.append({**item, "threshold": threshold})
        previous = item["date"]
    flush()
    return events, {"expected_days": expected, "received_days": len(selected_days), "valid_temperature_days": present, "missing_days": expected - present}


def annual_metrics(events: list[dict], start_year: int, end_year: int) -> list[dict]:
    groups = defaultdict(list)
    for event in events:
        groups[int(event["start_date"][:4])].append(event)
    output = []
    for year in range(start_year, end_year + 1):
        year_events = groups[year]
        output.append({"year": year, "event_count": len(year_events), "heatwave_days": sum(e["duration_days"] for e in year_events)})
    for index, item in enumerate(output):
        window = output[max(0, index - 4):index + 1]
        item["rolling_average_events"] = round(mean(row["event_count"] for row in window), 2)
    return output


def summarize(events: list[dict], metrics: list[dict]) -> dict:
    first, last = metrics[:5], metrics[-5:]
    first_average, last_average = mean(item["event_count"] for item in first), mean(item["event_count"] for item in last)
    # Require two non-overlapping five-year windows before making a comparison claim.
    change = None if len(metrics) < 10 or first_average == 0 else round((last_average - first_average) / first_average * 100, 1)
    slope_per_year = None
    if len(metrics) >= 2:
        x_mean = mean(range(len(metrics)))
        y_mean = mean(item["event_count"] for item in metrics)
        denominator = sum((index - x_mean) ** 2 for index in range(len(metrics)))
        slope_per_year = sum((index - x_mean) * (item["event_count"] - y_mean) for index, item in enumerate(metrics)) / denominator
    return {
        "total_events": len(events),
        "total_heatwave_days": sum(event["duration_days"] for event in events),
        "mean_duration_days": round(mean([event["duration_days"] for event in events]), 1) if events else 0,
        "mean_peak_temperature_c": round(mean([event["peak_temperature_c"] for event in events]), 1) if events else None,
        "first_window_average": round(first_average, 2) if first else None,
        "last_window_average": round(last_average, 2) if last else None,
        "percent_change": change,
        "linear_trend_events_per_decade": round(slope_per_year * 10, 2) if slope_per_year is not None else None,
    }
