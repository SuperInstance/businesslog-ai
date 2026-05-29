# businesslog-ai

**Intelligent analysis of business event logs** — pattern detection, anomaly scoring, KPI computation, and trend forecasting. Pure Python, zero dependencies.

## What This Gives You

- **Auto-categorization** — events classify as finance, operations, sales, HR, or custom categories
- **Anomaly detection** — statistical scoring flags unusual events
- **KPI engine** — compute revenue, MRR, burn rate, and custom metrics from raw logs
- **Trend forecasting** — linear extrapolation with confidence intervals
- **Report generation** — executive summaries with metrics, patterns, and anomalies

## Installation

```bash
pip install businesslog-ai
```

## Quick Start

```python
from datetime import datetime, timedelta
from businesslog_ai import BusinessEvent, LogAnalyzer, MetricsEngine, TrendPredictor, BusinessReport

events = [
    BusinessEvent(timestamp=datetime.now(), source="payment", message="Invoice $12,500 from Acme Corp"),
    BusinessEvent(timestamp=datetime.now(), source="monitor", message="Critical outage in us-east-1"),
]

analyzer = LogAnalyzer()
analyzer.add_events(events)
patterns = analyzer.detect_patterns()
anomalies = analyzer.detect_anomalies()

engine = MetricsEngine()
kpis = engine.compute_kpis(analyzer)

report = BusinessReport(kpis=kpis, patterns=patterns, anomalies=anomalies)
print(report.to_text())
```

## Testing

```bash
pip install -e .
pytest
```

## How It Fits

Analysis engine in the business logging pipeline: `businesslog-app` logs → `businesslog-backend` stores → `businesslog-ai` analyzes → `businesslog-agent` publishes to PLATO.

## License

MIT
