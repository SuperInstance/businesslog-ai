"""Tests for businesslog-ai."""

from datetime import datetime, timedelta

from businesslog_ai.event import BusinessEvent, EventCategory, EventSeverity
from businesslog_ai.analyzer import LogAnalyzer
from businesslog_ai.metrics import MetricsEngine
from businesslog_ai.predictor import TrendPredictor
from businesslog_ai.report import BusinessReport


def _make_event(
    message: str = "something happened",
    source: str = "test-service",
    category: EventCategory = EventCategory.UNKNOWN,
    severity: EventSeverity = EventSeverity.INFO,
    minutes_ago: int = 0,
    **metadata,
) -> BusinessEvent:
    return BusinessEvent(
        timestamp=datetime.now() - timedelta(minutes=minutes_ago),
        source=source,
        message=message,
        category=category,
        severity=severity,
        metadata=metadata,
    )


# ── BusinessEvent Tests ─────────────────────────────────────────────────

class TestBusinessEvent:
    def test_auto_categorize_sales(self):
        e = BusinessEvent(
            timestamp=datetime.now(), source="crm", message="New deal closed worth $5000"
        )
        assert e.category == EventCategory.SALES

    def test_auto_categorize_finance(self):
        e = BusinessEvent(
            timestamp=datetime.now(), source="billing", message="Invoice payment received"
        )
        assert e.category == EventCategory.FINANCE

    def test_auto_categorize_operations(self):
        e = BusinessEvent(
            timestamp=datetime.now(), source="infra", message="Service outage detected in production"
        )
        assert e.category == EventCategory.OPERATIONS

    def test_auto_categorize_customer(self):
        e = BusinessEvent(
            timestamp=datetime.now(), source="helpdesk", message="Support ticket escalated by customer"
        )
        assert e.category == EventCategory.CUSTOMER

    def test_auto_severity_critical(self):
        e = BusinessEvent(
            timestamp=datetime.now(), source="monitor", message="Complete outage in production region"
        )
        assert e.severity == EventSeverity.CRITICAL

    def test_auto_severity_high(self):
        e = BusinessEvent(
            timestamp=datetime.now(), source="alert", message="Incident reported: API failure"
        )
        assert e.severity == EventSeverity.HIGH

    def test_explicit_category_not_overridden(self):
        e = BusinessEvent(
            timestamp=datetime.now(), source="crm", message="payment invoice",
            category=EventCategory.FINANCE,
        )
        assert e.category == EventCategory.FINANCE

    def test_enrich(self):
        e = _make_event("test")
        enriched = e.enrich(region="us-east", priority=1)
        assert enriched.metadata["region"] == "us-east"
        assert enriched.metadata["priority"] == 1
        assert e.metadata == {}  # original unchanged

    def test_tag(self):
        e = _make_event("test")
        tagged = e.tag("urgent", "review")
        assert "urgent" in tagged.tags
        assert "review" in tagged.tags
        assert e.tags == []

    def test_tag_dedup(self):
        e = _make_event("test", tags=["urgent"])
        tagged = e.tag("urgent", "review")
        assert tagged.tags.count("urgent") == 1

    def test_to_dict_roundtrip(self):
        original = _make_event("test", source="svc", metadata={"key": "val"}, tags=["t1"])
        d = original.to_dict()
        restored = BusinessEvent.from_dict(d)
        assert restored.message == original.message
        assert restored.source == original.source
        assert restored.metadata == original.metadata
        assert restored.tags == original.tags

    def test_matches_regex(self):
        e = _make_event("Error code 503: Service unavailable")
        assert e.matches(r"error code \d+")
        assert not e.matches(r"success")

    def test_unknown_category(self):
        e = BusinessEvent(
            timestamp=datetime.now(), source="misc", message="Something random happened"
        )
        assert e.category == EventCategory.UNKNOWN


# ── LogAnalyzer Tests ────────────────────────────────────────────────────

class TestLogAnalyzer:
    def test_empty_analyzer(self):
        a = LogAnalyzer()
        assert a.detect_patterns() == []
        assert a.detect_anomalies() == []
        assert a.summary()["total_events"] == 0

    def test_add_events(self):
        a = LogAnalyzer()
        a.add_events([_make_event("a"), _make_event("b")])
        assert len(a.events) == 2

    def test_clear(self):
        a = LogAnalyzer()
        a.add_event(_make_event("test"))
        a.clear()
        assert len(a.events) == 0

    def test_source_pattern(self):
        a = LogAnalyzer()
        events = [_make_event("event", source="dominant-svc") for _ in range(8)]
        events += [_make_event("event", source="other") for _ in range(2)]
        a.add_events(events)
        patterns = a.detect_patterns()
        dominant = [p for p in patterns if "Dominant" in p.name]
        assert len(dominant) >= 1

    def test_severity_pattern(self):
        a = LogAnalyzer()
        events = [_make_event("critical outage!", severity=EventSeverity.CRITICAL) for _ in range(5)]
        a.add_events(events)
        patterns = a.detect_patterns()
        high_sev = [p for p in patterns if "High Severity" in p.name]
        assert len(high_sev) >= 1

    def test_template_pattern(self):
        a = LogAnalyzer()
        for i in range(5):
            a.add_event(BusinessEvent(
                timestamp=datetime.now(), source="api",
                message=f"Request processed in {i * 100}ms",
            ))
        patterns = a.detect_patterns()
        templates = [p for p in patterns if "Template" in p.name]
        assert len(templates) >= 1

    def test_anomaly_rare_source(self):
        a = LogAnalyzer()
        # Many normal events
        for _ in range(10):
            a.add_event(_make_event("normal ops", source="main-svc"))
        # One rare source
        a.add_event(_make_event("mystery event", source="never-seen-before"))
        anomalies = a.detect_anomalies(threshold=0.3)
        assert len(anomalies) >= 1
        assert any("never-seen-before" in a.event.source for a in anomalies)

    def test_anomaly_off_hours(self):
        a = LogAnalyzer()
        e = BusinessEvent(
            timestamp=datetime.now().replace(hour=3, minute=0),
            source="night-owl", message="automated task ran",
        )
        a.add_event(e)
        # Add enough normal events to make the source rare
        for _ in range(6):
            a.add_event(_make_event("normal", source="daytime-svc", minutes_ago=60))
        anomalies = a.detect_anomalies(threshold=0.3)
        assert len(anomalies) >= 1

    def test_summary(self):
        a = LogAnalyzer()
        a.add_events([_make_event("test") for _ in range(5)])
        s = a.summary()
        assert s["total_events"] == 5
        assert "severity_distribution" in s
        assert "categories" in s


# ── MetricsEngine Tests ──────────────────────────────────────────────────

class TestMetricsEngine:
    def test_empty(self):
        m = MetricsEngine()
        assert m.compute_kpis() == []
        assert m.event_rates() == []

    def test_kpis(self):
        m = MetricsEngine()
        events = [
            _make_event("ok", severity=EventSeverity.INFO),
            _make_event("bad", severity=EventSeverity.CRITICAL),
            _make_event("meh", severity=EventSeverity.MEDIUM),
        ]
        m.ingest(events)
        kpis = m.compute_kpis()
        names = [k.name for k in kpis]
        assert "total_events" in names
        assert "incident_rate" in names
        assert "unique_sources" in names

    def test_incident_rate(self):
        m = MetricsEngine()
        events = [
            _make_event("a", severity=EventSeverity.CRITICAL),
            _make_event("b", severity=EventSeverity.HIGH),
            _make_event("c", severity=EventSeverity.INFO),
            _make_event("d", severity=EventSeverity.INFO),
        ]
        m.ingest(events)
        kpis = {k.name: k for k in m.compute_kpis()}
        assert kpis["incident_rate"].value == 50.0

    def test_event_rates(self):
        m = MetricsEngine()
        now = datetime.now()
        events = [
            BusinessEvent(timestamp=now - timedelta(hours=2), source="a", message="old"),
            BusinessEvent(timestamp=now - timedelta(hours=1), source="b", message="mid"),
            BusinessEvent(timestamp=now, source="c", message="new"),
        ]
        m.ingest(events)
        rates = m.event_rates(window="1h")
        assert len(rates) >= 3
        assert sum(r["count"] for r in rates) == 3

    def test_severity_timeline(self):
        m = MetricsEngine()
        m.ingest([_make_event("test") for _ in range(3)])
        timeline = m.severity_timeline()
        assert len(timeline) >= 1

    def test_top_sources(self):
        m = MetricsEngine()
        for _ in range(5):
            m.ingest([_make_event("a", source="alpha")])
        for _ in range(3):
            m.ingest([_make_event("b", source="beta")])
        top = m.top_sources(limit=2)
        assert top[0]["source"] == "alpha"
        assert top[0]["count"] == 5

    def test_mtbe(self):
        m = MetricsEngine()
        base = datetime.now()
        events = [
            BusinessEvent(timestamp=base, source="s", message="a"),
            BusinessEvent(timestamp=base + timedelta(seconds=100), source="s", message="b"),
            BusinessEvent(timestamp=base + timedelta(seconds=200), source="s", message="c"),
        ]
        m.ingest(events)
        kpis = {k.name: k for k in m.compute_kpis()}
        assert "mean_time_between_events" in kpis
        assert kpis["mean_time_between_events"].value == 100.0


# ── TrendPredictor Tests ────────────────────────────────────────────────

class TestTrendPredictor:
    def test_empty(self):
        p = TrendPredictor()
        assert p.predict() == []

    def test_increasing_trend(self):
        p = TrendPredictor()
        base = datetime.now() - timedelta(days=10)
        events = []
        for i in range(10):
            # Create increasingly many events per day
            for _ in range(i + 1):
                events.append(BusinessEvent(
                    timestamp=base + timedelta(days=i, hours=12),
                    source="svc", message=f"event day {i}",
                ))
        p.fit(events)
        trends = p.predict(horizon=5)
        overall = next(t for t in trends if t.name == "total_events")
        assert overall.direction == "up"
        assert len(overall.forecast) == 5
        assert overall.forecast[-1] > overall.forecast[0]

    def test_stable_trend(self):
        p = TrendPredictor()
        base = datetime.now() - timedelta(days=5)
        events = []
        for i in range(5):
            for _ in range(3):
                events.append(BusinessEvent(
                    timestamp=base + timedelta(days=i, hours=12),
                    source="svc", message=f"event day {i}",
                ))
        p.fit(events)
        trends = p.predict(horizon=3)
        overall = next(t for t in trends if t.name == "total_events")
        assert overall.direction == "stable"

    def test_category_trend(self):
        p = TrendPredictor()
        base = datetime.now() - timedelta(days=5)
        events = []
        for i in range(5):
            events.append(BusinessEvent(
                timestamp=base + timedelta(days=i),
                source="crm", message=f"New deal closed day {i}",
                category=EventCategory.SALES,
            ))
        p.fit(events)
        trends = p.predict(horizon=3, category=EventCategory.SALES)
        assert len(trends) == 1
        assert trends[0].name == "events_sales"


# ── BusinessReport Tests ────────────────────────────────────────────────

class TestBusinessReport:
    def test_empty_report(self):
        report = BusinessReport.from_events([])
        assert "No events" in report.summary
        assert report.kpis == []

    def test_full_report(self):
        events = [
            _make_event("New deal worth $50k", source="crm", minutes_ago=10),
            _make_event("Invoice payment received", source="billing", minutes_ago=30),
            _make_event("Support ticket escalated", source="helpdesk", minutes_ago=60),
            _make_event("Critical outage in us-east-1", source="monitor", severity=EventSeverity.CRITICAL, minutes_ago=90),
            _make_event("Critical failure in eu-west-1", source="monitor", severity=EventSeverity.CRITICAL, minutes_ago=95),
            _make_event("High severity incident reported", source="alert", severity=EventSeverity.HIGH, minutes_ago=100),
            _make_event("Marketing campaign launched", source="ads", minutes_ago=120),
        ]
        report = BusinessReport.from_events(events)
        assert report.summary
        assert len(report.kpis) > 0
        assert len(report.patterns) > 0
        assert len(report.insights) > 0

    def test_report_to_dict(self):
        events = [_make_event("test") for _ in range(3)]
        report = BusinessReport.from_events(events)
        d = report.to_dict()
        assert "generated_at" in d
        assert "kpis" in d
        assert "insights" in d

    def test_high_incident_rate_insight(self):
        events = [
            _make_event("critical outage!", severity=EventSeverity.CRITICAL),
            _make_event("high severity incident", severity=EventSeverity.HIGH),
            _make_event("normal event", severity=EventSeverity.INFO),
        ]
        report = BusinessReport.from_events(events)
        incident_insight = next(
            (i for i in report.insights if "Incident Rate" in i.title), None
        )
        assert incident_insight is not None

    def test_trends_in_report(self):
        base = datetime.now() - timedelta(days=7)
        events = []
        for i in range(7):
            for _ in range(i + 1):
                events.append(BusinessEvent(
                    timestamp=base + timedelta(days=i, hours=12),
                    source="svc", message=f"event day {i}",
                ))
        report = BusinessReport.from_events(events)
        assert len(report.trends) > 0
