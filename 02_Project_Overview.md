# What This Project Is About

## The short version

Climate Hazard Trend Analyzer is a web application that turns historical daily weather data into an understandable answer to a climate question: **are unusually hot spells becoming more or less common at this location over time?**

The first version concentrates on heatwaves. A visitor chooses a city and a period such as 1990–2025. The application gets real daily maximum-temperature history, identifies heatwave events with a clear rule, and displays annual patterns, individual events, and a carefully worded trend summary.

## What the application does

The user is not simply shown a high-temperature chart. The system compares each day with what is unusually hot for that location and season. It calls a heatwave an event only when the daily maximum temperature remains above a local 95th-percentile threshold for at least three consecutive days.

For example, if three consecutive Delhi days each exceed the unusual-heat threshold calculated for their dates, they form one heatwave event. A two-day spike does not. If data for a day are missing, the sequence stops; the software does not invent continuity.

The result page shows:

- how many events happened each year;
- how many heatwave days and average event days there were;
- when each detected event began and ended, including its peak temperature;
- an annual chart and 5-year rolling average; and
- an explanation of the source, definition, coverage, and limitations.

## Why the threshold is seasonal and local

“Above 35°C” is not a fair universal heatwave rule. A 35°C day means something different in Delhi, London, and a high-altitude town. Even in one city, normal temperatures differ dramatically between winter and summer.

The application therefore derives a local threshold from a fixed historical reference period (1991–2020). For every calendar date, it examines temperatures around that date across the reference years and calculates the 95th percentile. A day is unusual only relative to that location and time of year. This makes the comparison more meaningful than a single global temperature cutoff.

## What the trend statement means

The app compares average yearly event counts from the first five and last five years of the user’s selected range and shows a 5-year rolling average. If the earlier average is 1.2 events/year and the later average is 1.7 events/year, the app can say that the measured indicator rose by about 42% over those two windows.

This is a description of the data, not a forecast and not proof that one particular cause produced the change. The interface should say exactly which years were compared and avoid percentage claims when the range is too short, coverage is poor, or the starting value is zero.

## Data flow in plain language

```text
Choose city and years
        ↓
City is converted to latitude/longitude
        ↓
Python API requests/caches historical daily maximum temperatures
        ↓
API validates and cleans the dates and values
        ↓
Heatwave algorithm groups qualifying 3+ day runs
        ↓
API stores derived results and returns JSON
        ↓
React dashboard shows cards, chart, event table, and method notes
```

## What we are building—not pretending to build

This is an analysis tool for historical data at or near a selected coordinate. It is not an emergency warning service, a medical heat-risk assessment, a weather forecast, or a definitive analysis for an entire state. A custom latitude-longitude box would require a gridded dataset and a stated spatial aggregation rule; it is sensible future work but should not be faked with a single point.

Similarly, drought and heavy rainfall are intentionally deferred. They need different variables, thresholds, and scientific assumptions. Completing one transparent heatwave implementation first is the right engineering choice for this take-home scope.

## Success looks like this

A reviewer can choose a real location, receive a fast and reproducible result, inspect the detected events, understand the exact definition used, and see that the project behaves honestly when data are missing or no heatwaves are found. The code will be structured so the data client, hazard logic, API, and visual interface are independently understandable and testable.
