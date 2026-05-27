# businesslog-ai

Intelligent analysis of business event logs — pattern detection, anomaly scoring, KPI computation, and trend forecasting. Pure Python, no external dependencies.

## Installation

```bash
pip install businesslog-ai
```

## Quick Start

```python
from datetime import datetime, timedelta
from businesslog_ai import BusinessEvent, LogAnalyzer, MetricsEngine, TrendPredictor, BusinessReport

# Create events from your log sources
events = [
    BusinessEvent(
        timestamp=datetime.now() - timedelta(hours=1),
        source="payment-service",
        message="Invoice payment of $12,500 received from Acme Corp",
    ),
    BusinessEvent(
        timestamp=datetime.now() - timedelta(minutes=30),
        source="monitor",
        message="Critical outage detected in us-east-1 region",
    ),
    BusinessEvent(
        timestamp=datetime.now() - timedelta(minutes=5),
        source="crm",
        message="New deal closed worth $50k — enterprise tier",
    ),
]

# Events auto-categorize and score severity
for e in events:
    print(f"{e.category.value:12s} {e.severity.value:8s} {e.source}: {e.message}")
# finance       info     payment-service: Invoice payment of $12,500 received...
# operations    critical monitor: Critical outage detected in us-east-1 region
# sales         info     crm: New deal closed worth $50k — enterprise tier

# Analyze patterns and anomalies
analyzer = LogAnalyzer()
analyzer.add_events(events)
patterns = analyzer.detect_patterns()
anomalies = analyzer.detect_anomalies()

# Compute KPIs
engine = MetricsEngine()
engine.ingest(events)
kpis = engine.compute_kpis()
for kpi in kpis:
    print(f"  {kpi.name}: {kpi.value} ({kpi.unit})")

# Forecast trends
predictor = TrendPredictor()
predictor.fit(events)
trends = predictor.predict(horizon=7)

# Generate a full report
report = BusinessReport.from_events(events)
print(report.summary)
for insight in report.insights:
    print(f"  💡 {insight.title}: {insight.recommendation}")
```

## Modules

### `event` — BusinessEvent

Structured event with auto-categorization and severity detection.

```python
e = BusinessEvent(timestamp=..., source="crm", message="New deal closed worth $50k")
e.category      # EventCategory.SALES (auto-detected)
e.severity      # EventSeverity.INFO (auto-detected)

# Enrich and tag
enriched = e.enrich(region="us-east").tag("enterprise", "priority")
enriched.to_dict()  # serialize
BusinessEvent.from_dict(data)  # deserialize
```

**Categories:** `sales`, `finance`, `operations`, `marketing`, `customer`, `engineering`, `hr`, `compliance`, `unknown`

**Severities:** `critical`, `high`, `medium`, `low`, `info`

### `analyzer` — LogAnalyzer

Pattern detection and anomaly scoring.

```python
analyzer = LogAnalyzer()
analyzer.add_events(events)

patterns = analyzer.detect_patterns()
# Returns: dominant sources, category concentrations, severity spikes,
#          repeated message templates

anomalies = analyzer.detect_anomalies(threshold=0.6)
# Returns: rare sources, off-hours events, category outliers,
#          severity anomalies with 0.0–1.0 scores

analyzer.summary()  # dict of stats
```

### `metrics` — MetricsEngine

KPI computation from event streams.

```python
engine = MetricsEngine()
engine.ingest(events)

kpis = engine.compute_kpis()
# total_events, incident_rate (%), mean_time_between_events,
# per-category counts, unique_sources

rates = engine.event_rates(window="1h")
# Bucketed event counts over time windows

engine.severity_timeline()  # per-day severity distribution
engine.top_sources(limit=10)  # most active sources
```

### `predictor` — TrendPredictor

Simple forecasting using linear regression (no external deps).

```python
predictor = TrendPredictor()
predictor.fit(events)

trends = predictor.predict(horizon=7)
for t in trends:
    print(f"{t.name}: {t.direction} (slope={t.slope}, confidence={t.confidence})")
    print(f"  forecast: {t.forecast}")

# Filter by category
trends = predictor.predict(horizon=7, category=EventCategory.SALES)
```

### `report` — BusinessReport

One-call comprehensive report generation.

```python
report = BusinessReport.from_events(events, forecast_horizon=7)
report.summary       # executive summary text
report.kpis          # computed KPIs
report.patterns      # detected patterns
report.anomalies     # anomalous events
report.trends        # forecasted trends
report.insights      # actionable insights & recommendations

report.to_dict()     # full serialization
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -q
```

## License

MIT
