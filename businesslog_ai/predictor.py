"""TrendPredictor — simple forecasting for business event trends."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .event import BusinessEvent, EventCategory


@dataclass
class Trend:
    """A detected or predicted trend.

    Attributes:
        name: Trend identifier.
        direction: 'up', 'down', or 'stable'.
        slope: Rate of change per period.
        confidence: 0.0–1.0 prediction confidence.
        forecast: Predicted values for future periods.
    """

    name: str
    direction: str
    slope: float
    confidence: float
    forecast: list[float]


class TrendPredictor:
    """Simple trend detection and forecasting for event streams.

    Uses moving averages and linear regression (no external deps).

    Usage::

        predictor = TrendPredictor()
        predictor.fit(events)
        trends = predictor.predict(horizon=7)
    """

    def __init__(self) -> None:
        self._events: list[BusinessEvent] = []
        self._daily_counts: dict[str, int] = {}

    def fit(self, events: list[BusinessEvent]) -> None:
        """Fit the predictor on historical events."""
        self._events = sorted(events, key=lambda e: e.timestamp)
        self._daily_counts = self._compute_daily_counts()

    def predict(self, horizon: int = 7, category: EventCategory | None = None) -> list[Trend]:
        """Predict future event trends.

        Args:
            horizon: Number of days to forecast.
            category: Optionally filter to a single category.

        Returns:
            List of Trend objects with forecasts.
        """
        if not self._events:
            return []

        trends: list[Trend] = []

        if category is not None:
            daily = self._compute_daily_counts(category)
            trends.append(self._forecast(f"events_{category.value}", daily, horizon))
        else:
            # Overall trend
            trends.append(self._forecast("total_events", self._daily_counts, horizon))

            # Per-category trends
            from collections import defaultdict
            cat_daily: dict[EventCategory, dict[str, int]] = defaultdict(lambda: defaultdict(int))
            for event in self._events:
                day = event.timestamp.date().isoformat()
                cat_daily[event.category][day] += 1

            for cat, counts in cat_daily.items():
                trends.append(self._forecast(f"events_{cat.value}", dict(counts), horizon))

        return trends

    def _forecast(self, name: str, daily_counts: dict[str, int], horizon: int) -> Trend:
        """Generate a forecast using linear regression on daily counts."""
        if not daily_counts:
            return Trend(name=name, direction="stable", slope=0.0, confidence=0.0, forecast=[])

        sorted_days = sorted(daily_counts.keys())
        n = len(sorted_days)

        # Simple linear regression: y = a + b*x
        x_vals = list(range(n))
        y_vals = [daily_counts[d] for d in sorted_days]

        x_mean = sum(x_vals) / n
        y_mean = sum(y_vals) / n

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals))
        denominator = sum((x - x_mean) ** 2 for x in x_vals)

        slope = numerator / denominator if denominator != 0 else 0.0
        intercept = y_mean - slope * x_mean

        # Generate forecast
        forecast: list[float] = []
        for i in range(1, horizon + 1):
            predicted = intercept + slope * (n - 1 + i)
            forecast.append(round(max(predicted, 0.0), 2))

        # Direction
        if abs(slope) < 0.1:
            direction = "stable"
        elif slope > 0:
            direction = "up"
        else:
            direction = "down"

        # Confidence based on R²
        ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(x_vals, y_vals))
        ss_tot = sum((y - y_mean) ** 2 for y in y_vals)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
        confidence = round(max(0.0, min(1.0, r_squared)), 3)

        return Trend(
            name=name,
            direction=direction,
            slope=round(slope, 3),
            confidence=confidence,
            forecast=forecast,
        )

    def _compute_daily_counts(self, category: EventCategory | None = None) -> dict[str, int]:
        """Compute daily event counts, optionally filtered by category."""
        from collections import defaultdict
        counts: dict[str, int] = defaultdict(int)
        for event in self._events:
            if category is not None and event.category != category:
                continue
            day = event.timestamp.date().isoformat()
            counts[day] += 1
        return dict(counts)
