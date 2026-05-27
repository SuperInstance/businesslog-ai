"""BusinessReport — generate insights and recommendations from event analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .analyzer import LogAnalyzer, Pattern, Anomaly
from .event import BusinessEvent, EventCategory, EventSeverity
from .metrics import MetricsEngine, KPI
from .predictor import TrendPredictor, Trend


@dataclass
class Insight:
    """A single insight or recommendation.

    Attributes:
        title: Short title.
        description: Detailed explanation.
        severity: How important this insight is.
        category: Related business category.
        recommendation: Suggested action (if any).
    """

    title: str
    description: str
    severity: EventSeverity = EventSeverity.INFO
    category: EventCategory = EventCategory.UNKNOWN
    recommendation: str = ""


@dataclass
class BusinessReport:
    """Comprehensive business report generated from event analysis.

    Attributes:
        generated_at: When the report was generated.
        summary: High-level summary text.
        kpis: Computed KPIs.
        patterns: Detected patterns.
        anomalies: Detected anomalies.
        trends: Predicted trends.
        insights: Generated insights and recommendations.
    """

    generated_at: datetime = field(default_factory=datetime.now)
    summary: str = ""
    kpis: list[KPI] = field(default_factory=list)
    patterns: list[Pattern] = field(default_factory=list)
    anomalies: list[Anomaly] = field(default_factory=list)
    trends: list[Trend] = field(default_factory=list)
    insights: list[Insight] = field(default_factory=list)

    @classmethod
    def from_events(
        cls,
        events: list[BusinessEvent],
        forecast_horizon: int = 7,
    ) -> BusinessReport:
        """Generate a full report from a list of business events.

        Runs analysis, metrics, prediction, and insight generation.

        Args:
            events: The events to analyze.
            forecast_horizon: Days to forecast ahead.

        Returns:
            A complete BusinessReport.
        """
        # Analyze
        analyzer = LogAnalyzer()
        analyzer.add_events(events)
        patterns = analyzer.detect_patterns()
        anomalies = analyzer.detect_anomalies()

        # Metrics
        engine = MetricsEngine()
        engine.ingest(events)
        kpis = engine.compute_kpis()

        # Predict
        predictor = TrendPredictor()
        predictor.fit(events)
        trends = predictor.predict(horizon=forecast_horizon)

        # Generate insights
        insights = _generate_insights(kpis, patterns, anomalies, trends, events)

        # Summary
        summary = _generate_summary(events, kpis, anomalies, trends)

        return cls(
            generated_at=datetime.now(),
            summary=summary,
            kpis=kpis,
            patterns=patterns,
            anomalies=anomalies,
            trends=trends,
            insights=insights,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report to a dictionary."""
        return {
            "generated_at": self.generated_at.isoformat(),
            "summary": self.summary,
            "kpis": [{"name": k.name, "value": k.value, "unit": k.unit} for k in self.kpis],
            "patterns": [{"name": p.name, "confidence": p.confidence, "event_count": p.event_count} for p in self.patterns],
            "anomalies": [{"score": a.score, "reason": a.reason, "message": a.event.message} for a in self.anomalies],
            "trends": [{"name": t.name, "direction": t.direction, "slope": t.slope, "forecast": t.forecast} for t in self.trends],
            "insights": [{"title": i.title, "description": i.description, "recommendation": i.recommendation} for i in self.insights],
        }


def _generate_summary(
    events: list[BusinessEvent],
    kpis: list[KPI],
    anomalies: list[Anomaly],
    trends: list[Trend],
) -> str:
    """Generate a human-readable executive summary."""
    total = len(events)
    if total == 0:
        return "No events to analyze."

    parts: list[str] = [f"Analyzed {total} events."]

    # Incident rate
    incident_kpi = next((k for k in kpis if k.name == "incident_rate"), None)
    if incident_kpi:
        parts.append(f"Incident rate: {incident_kpi.value}%.")

    # Anomalies
    if anomalies:
        parts.append(f"Detected {len(anomalies)} anomalies.")

    # Top trend
    if trends:
        top = trends[0]
        direction_word = {"up": "increasing ↑", "down": "decreasing ↓", "stable": "stable →"}
        parts.append(f"Overall event volume is {direction_word.get(top.direction, top.direction)} (slope: {top.slope:.2f}/day).")

    return " ".join(parts)


def _generate_insights(
    kpis: list[KPI],
    patterns: list[Pattern],
    anomalies: list[Anomaly],
    trends: list[Trend],
    events: list[BusinessEvent],
) -> list[Insight]:
    """Generate actionable insights from analysis results."""
    insights: list[Insight] = []

    # High incident rate
    incident_kpi = next((k for k in kpis if k.name == "incident_rate"), None)
    if incident_kpi and incident_kpi.value > 20:
        insights.append(Insight(
            title="High Incident Rate",
            description=f"{incident_kpi.value}% of events are incidents (CRITICAL/HIGH severity).",
            severity=EventSeverity.HIGH,
            category=EventCategory.OPERATIONS,
            recommendation="Review incident response procedures and root cause analysis.",
        ))

    # Critical anomalies
    high_anomalies = [a for a in anomalies if a.score > 0.7]
    if high_anomalies:
        insights.append(Insight(
            title=f"{len(high_anomalies)} High-Score Anomalies",
            description="Several events show significant deviation from normal patterns.",
            severity=EventSeverity.HIGH,
            category=EventCategory.OPERATIONS,
            recommendation="Investigate anomalous events for potential systemic issues.",
        ))

    # Upward trends
    for trend in trends:
        if trend.direction == "up" and trend.slope > 1.0:
            insights.append(Insight(
                title=f"Rising Trend: {trend.name}",
                description=f"Events are increasing at {trend.slope:.1f}/day over the analysis period.",
                severity=EventSeverity.MEDIUM,
                recommendation="Monitor capacity and allocate resources proactively.",
            ))

    # Dominant source pattern
    for pattern in patterns:
        if "Dominant Source" in pattern.name and pattern.confidence > 0.5:
            insights.append(Insight(
                title=f"Source Concentration Risk: {pattern.name}",
                description=pattern.description,
                severity=EventSeverity.MEDIUM,
                category=pattern.category,
                recommendation="Ensure monitoring coverage is not biased toward a single source.",
            ))

    # Category imbalance
    cat_events = {}
    for k in kpis:
        if k.name.startswith("events_") and k.unit == "count":
            cat_events[k.name] = k.value
    if cat_events:
        max_cat = max(cat_events, key=cat_events.get)
        total_cat = sum(cat_events.values())
        if total_cat > 0 and cat_events[max_cat] / total_cat > 0.6:
            insights.append(Insight(
                title=f"Category Imbalance: {max_cat}",
                description=f"{max_cat} accounts for {cat_events[max_cat]}/{total_cat} categorized events.",
                severity=EventSeverity.LOW,
                recommendation="Check if logging is comprehensive across all business areas.",
            ))

    return insights
