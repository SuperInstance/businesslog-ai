"""MetricsEngine — compute KPIs and metrics from event streams."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .event import BusinessEvent, EventCategory, EventSeverity


@dataclass
class KPI:
    """A computed key performance indicator.

    Attributes:
        name: Metric name.
        value: Numeric value.
        unit: Unit of measurement (e.g., 'count', 'rate', 'seconds').
        category: Related business category, if any.
        period: Time period the metric covers.
    """

    name: str
    value: float
    unit: str = "count"
    category: EventCategory | None = None
    period: str = ""


class MetricsEngine:
    """Computes KPIs and business metrics from event streams.

    Usage::

        engine = MetricsEngine()
        engine.ingest(events)
        kpis = engine.compute_kpis()
        rates = engine.event_rates(window="1h")
    """

    def __init__(self) -> None:
        self._events: list[BusinessEvent] = []

    def ingest(self, events: list[BusinessEvent]) -> None:
        """Load events for metric computation."""
        self._events.extend(events)

    def clear(self) -> None:
        """Reset all stored events."""
        self._events.clear()

    @property
    def event_count(self) -> int:
        return len(self._events)

    # ── Core KPIs ───────────────────────────────────────────────────────

    def compute_kpis(self) -> list[KPI]:
        """Compute a standard set of business KPIs from loaded events.

        Returns KPIs for:
        - Total event volume
        - Incident rate (CRITICAL + HIGH as % of total)
        - Mean time between events
        - Category breakdown
        - Per-source event counts
        """
        kpis: list[KPI] = []
        if not self._events:
            return kpis

        total = len(self._events)

        # Total volume
        kpis.append(KPI(name="total_events", value=total, unit="count"))

        # Incident rate
        critical_high = sum(
            1 for e in self._events
            if e.severity in (EventSeverity.CRITICAL, EventSeverity.HIGH)
        )
        kpis.append(KPI(
            name="incident_rate",
            value=round(critical_high / total * 100, 2),
            unit="percent",
        ))

        # Mean time between events
        if total > 1:
            sorted_events = sorted(self._events, key=lambda e: e.timestamp)
            deltas = [
                (sorted_events[i + 1].timestamp - sorted_events[i].timestamp).total_seconds()
                for i in range(len(sorted_events) - 1)
            ]
            mtbe = sum(deltas) / len(deltas)
            kpis.append(KPI(name="mean_time_between_events", value=round(mtbe, 2), unit="seconds"))

        # Category distribution
        cat_counts: dict[EventCategory, int] = defaultdict(int)
        for e in self._events:
            cat_counts[e.category] += 1
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
            kpis.append(KPI(
                name=f"events_{cat.value}",
                value=count,
                unit="count",
                category=cat,
            ))

        # Unique sources
        kpis.append(KPI(
            name="unique_sources",
            value=len(set(e.source for e in self._events)),
            unit="count",
        ))

        return kpis

    # ── Event Rates ─────────────────────────────────────────────────────

    def event_rates(self, window: str = "1h") -> list[dict[str, Any]]:
        """Compute event rates over time windows.

        Args:
            window: Window size — '1h', '6h', '1d', '15m', '30m'.

        Returns:
            List of dicts with 'window_start', 'window_end', 'count', 'categories'.
        """
        if not self._events:
            return []

        window_seconds = self._parse_window(window)
        sorted_events = sorted(self._events, key=lambda e: e.timestamp)
        start = sorted_events[0].timestamp
        end = sorted_events[-1].timestamp

        results: list[dict[str, Any]] = []
        current = start
        while current <= end:
            next_window = current + timedelta(seconds=window_seconds)
            window_events = [
                e for e in self._events
                if current <= e.timestamp < next_window
            ]
            cat_counts: dict[str, int] = defaultdict(int)
            for e in window_events:
                cat_counts[e.category.value] += 1

            results.append({
                "window_start": current.isoformat(),
                "window_end": next_window.isoformat(),
                "count": len(window_events),
                "categories": dict(cat_counts),
            })
            current = next_window

        return results

    # ── Severity Distribution ───────────────────────────────────────────

    def severity_timeline(self) -> list[dict[str, Any]]:
        """Return per-day severity counts for timeline visualization."""
        if not self._events:
            return []

        day_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for e in self._events:
            day = e.timestamp.date().isoformat()
            day_counts[day][e.severity.value] += 1

        return [
            {"date": day, "severities": dict(sevs)}
            for day, sevs in sorted(day_counts.items())
        ]

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _parse_window(window: str) -> int:
        """Parse a window string like '1h', '30m', '1d' into seconds."""
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        unit = window[-1].lower()
        value = int(window[:-1])
        return value * units.get(unit, 3600)

    def top_sources(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return the most active event sources."""
        from collections import Counter
        counts = Counter(e.source for e in self._events)
        return [
            {"source": source, "count": count}
            for source, count in counts.most_common(limit)
        ]
