"""LogAnalyzer — pattern detection and anomaly scoring for event streams."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .event import BusinessEvent, EventCategory, EventSeverity


@dataclass
class Pattern:
    """A detected pattern in event data.

    Attributes:
        name: Human-readable pattern name.
        description: What this pattern represents.
        event_count: How many events match.
        category: Primary category of matching events.
        confidence: 0.0–1.0 confidence score.
    """

    name: str
    description: str
    event_count: int
    category: EventCategory
    confidence: float = 0.0


@dataclass
class Anomaly:
    """A detected anomaly in event data.

    Attributes:
        event: The anomalous event.
        score: 0.0–1.0 anomaly score (higher = more anomalous).
        reason: Human-readable explanation.
    """

    event: BusinessEvent
    score: float
    reason: str


class LogAnalyzer:
    """Analyzes streams of business events for patterns and anomalies.

    Usage::

        analyzer = LogAnalyzer()
        analyzer.add_events(events)
        patterns = analyzer.detect_patterns()
        anomalies = analyzer.detect_anomalies()
    """

    def __init__(self) -> None:
        self._events: list[BusinessEvent] = []

    def add_event(self, event: BusinessEvent) -> None:
        """Add a single event for analysis."""
        self._events.append(event)

    def add_events(self, events: list[BusinessEvent]) -> None:
        """Add multiple events for analysis."""
        self._events.extend(events)

    @property
    def events(self) -> list[BusinessEvent]:
        """Return a copy of all stored events."""
        return list(self._events)

    def clear(self) -> None:
        """Remove all stored events."""
        self._events.clear()

    # ── Pattern Detection ───────────────────────────────────────────────

    def detect_patterns(self) -> list[Pattern]:
        """Detect recurring patterns across the event stream.

        Returns patterns for:
        - High-frequency sources (burst detection)
        - Repeated message templates
        - Category concentrations
        - Severity distributions
        """
        patterns: list[Pattern] = []
        if not self._events:
            return patterns

        patterns.extend(self._source_patterns())
        patterns.extend(self._category_patterns())
        patterns.extend(self._severity_patterns())
        patterns.extend(self._message_template_patterns())

        return sorted(patterns, key=lambda p: p.confidence, reverse=True)

    def _source_patterns(self) -> list[Pattern]:
        """Detect source-based patterns (bursts, dominant sources)."""
        patterns: list[Pattern] = []
        source_counts = Counter(e.source for e in self._events)
        total = len(self._events)

        for source, count in source_counts.most_common(5):
            ratio = count / total
            if ratio > 0.3:
                patterns.append(Pattern(
                    name=f"Dominant Source: {source}",
                    description=f"{source} produces {ratio:.0%} of all events ({count}/{total})",
                    event_count=count,
                    category=EventCategory.UNKNOWN,
                    confidence=min(ratio, 0.95),
                ))
            elif count >= 3:
                patterns.append(Pattern(
                    name=f"Recurring Source: {source}",
                    description=f"{source} appears {count} times in the event stream",
                    event_count=count,
                    category=EventCategory.UNKNOWN,
                    confidence=0.4,
                ))

        return patterns

    def _category_patterns(self) -> list[Pattern]:
        """Detect category concentration patterns."""
        patterns: list[Pattern] = []
        cat_counts = Counter(e.category for e in self._events)
        total = len(self._events)

        for cat, count in cat_counts.most_common(5):
            ratio = count / total
            if ratio > 0.5:
                patterns.append(Pattern(
                    name=f"Category Concentration: {cat.value}",
                    description=f"{ratio:.0%} of events are {cat.value} ({count} events)",
                    event_count=count,
                    category=cat,
                    confidence=ratio * 0.9,
                ))

        return patterns

    def _severity_patterns(self) -> list[Pattern]:
        """Detect severity distribution anomalies."""
        patterns: list[Pattern] = []
        sev_counts = Counter(e.severity for e in self._events)
        total = len(self._events)

        critical_high = sev_counts.get(EventSeverity.CRITICAL, 0) + sev_counts.get(EventSeverity.HIGH, 0)
        if critical_high > 0:
            ratio = critical_high / total
            patterns.append(Pattern(
                name="High Severity Concentration",
                description=f"{ratio:.0%} of events are CRITICAL or HIGH severity ({critical_high}/{total})",
                event_count=critical_high,
                category=EventCategory.OPERATIONS,
                confidence=min(ratio * 1.5, 0.95),
            ))

        return patterns

    def _message_template_patterns(self) -> list[Pattern]:
        """Detect repeated message templates by normalizing messages."""
        patterns: list[Pattern] = []
        templates: dict[str, list[BusinessEvent]] = defaultdict(list)

        for event in self._events:
            # Normalize: replace numbers and UUIDs with placeholders
            template = re.sub(r"\d+", "{N}", event.message.lower())
            template = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}", "{UUID}", template)
            templates[template].append(event)

        for template, events in templates.items():
            if len(events) >= 3:
                patterns.append(Pattern(
                    name=f"Repeated Template: {template[:50]}",
                    description=f"Message template appears {len(events)} times",
                    event_count=len(events),
                    category=events[0].category,
                    confidence=min(len(events) / len(self._events) * 2, 0.9),
                ))

        return patterns

    # ── Anomaly Detection ───────────────────────────────────────────────

    def detect_anomalies(self, threshold: float = 0.6) -> list[Anomaly]:
        """Detect anomalous events based on multiple heuristics.

        Args:
            threshold: Minimum anomaly score (0.0–1.0) to include.

        Anomaly signals:
        - Severity spikes (CRITICAL/HIGH in normally quiet periods)
        - Unusual source appearances (single-occurrence sources)
        - Off-hours events
        - Category outliers
        """
        anomalies: list[Anomaly] = []
        if not self._events:
            return anomalies

        source_counts = Counter(e.source for e in self._events)
        cat_counts = Counter(e.category for e in self._events)
        total = len(self._events)

        for event in self._events:
            scores: list[float] = []
            reasons: list[str] = []

            # Single-occurrence source
            if source_counts[event.source] == 1 and total > 5:
                scores.append(0.4)
                reasons.append(f"Source '{event.source}' appears only once")

            # Rare category
            if cat_counts[event.category] / total < 0.1 and total > 5:
                scores.append(0.3)
                reasons.append(f"Category '{event.category.value}' is rare (<10%)")

            # Off-hours (before 6am or after 10pm)
            hour = event.timestamp.hour
            if hour < 6 or hour >= 22:
                scores.append(0.3)
                reasons.append(f"Off-hours event at {hour}:00")

            # High severity
            if event.severity in (EventSeverity.CRITICAL, EventSeverity.HIGH):
                scores.append(0.5)
                reasons.append(f"{event.severity.value.upper()} severity event")

            if scores:
                # Combined score: not simple average, weighted union
                combined = 1.0 - (1.0 - scores[0])
                for s in scores[1:]:
                    combined = 1.0 - (1.0 - combined) * (1.0 - s)

                if combined >= threshold:
                    anomalies.append(Anomaly(
                        event=event,
                        score=round(combined, 3),
                        reason="; ".join(reasons),
                    ))

        return sorted(anomalies, key=lambda a: a.score, reverse=True)

    # ── Summary Stats ───────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        """Return summary statistics of the current event set."""
        if not self._events:
            return {"total_events": 0}

        sev_counts = Counter(e.severity for e in self._events)
        cat_counts = Counter(e.category for e in self._events)
        timestamps = [e.timestamp for e in self._events]

        return {
            "total_events": len(self._events),
            "time_range": {
                "earliest": min(timestamps).isoformat(),
                "latest": max(timestamps).isoformat(),
            },
            "unique_sources": len(set(e.source for e in self._events)),
            "severity_distribution": {s.value: c for s, c in sev_counts.most_common()},
            "category_distribution": {c.value: c for c, count in cat_counts.most_common() for _ in [count]},
            "categories": {c.value: count for c, count in cat_counts.most_common()},
        }
