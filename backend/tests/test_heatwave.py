from datetime import date, timedelta
from app.heatwave import detect_heatwaves, percentile, summarize


def rows(temperatures):
    start = date(2020, 6, 1)
    return [{"date": start + timedelta(days=index), "tmax": value} for index, value in enumerate(temperatures)]


def thresholds_for(records, value=30):
    return {(record["date"].month, record["date"].day): value for record in records}


def test_percentile_uses_linear_interpolation():
    assert percentile([0, 10], 0.95) == 9.5


def test_three_consecutive_hot_days_is_an_event():
    records = rows([31, 32, 33])
    events, _ = detect_heatwaves(records, thresholds_for(records))
    assert len(events) == 1
    assert events[0]["duration_days"] == 3


def test_two_hot_days_are_not_an_event():
    records = rows([31, 32])
    events, _ = detect_heatwaves(records, thresholds_for(records))
    assert events == []


def test_threshold_equality_does_not_qualify():
    records = rows([30, 30, 30])
    events, _ = detect_heatwaves(records, thresholds_for(records))
    assert events == []


def test_missing_value_breaks_run():
    records = rows([31, 32, None, 33, 34, 35])
    events, _ = detect_heatwaves(records, thresholds_for(records))
    assert len(events) == 1
    assert events[0]["start_date"] == "2020-06-04"


def test_short_range_does_not_claim_percent_change():
    metrics = [{"year": 2020 + index, "event_count": 2, "heatwave_days": 6} for index in range(3)]
    assert summarize([], metrics)["percent_change"] is None


def test_annual_metrics_include_trailing_rolling_average():
    from app.heatwave import annual_metrics
    events = [{"start_date": "2020-06-01", "duration_days": 3}, {"start_date": "2021-06-01", "duration_days": 3}]
    metrics = annual_metrics(events, 2020, 2021)
    assert metrics[0]["rolling_average_events"] == 1
    assert metrics[1]["rolling_average_events"] == 1
