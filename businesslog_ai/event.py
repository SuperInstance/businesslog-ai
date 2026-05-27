"""BusinessEvent — structured representation of a business log event."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventCategory(Enum):
    """High-level business event categories."""

    SALES = "sales"
    FINANCE = "finance"
    OPERATIONS = "operations"
    MARKETING = "marketing"
    CUSTOMER = "customer"
    ENGINEERING = "engineering"
    HR = "hr"
    COMPLIANCE = "compliance"
    UNKNOWN = "unknown"


class EventSeverity(Enum):
    """Event severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# Keyword → category mapping for auto-categorization
_KEYWORD_MAP: dict[EventCategory, list[str]] = {
    EventCategory.SALES: [
        "revenue", "deal", "contract", "pipeline", "quota", "closing", "won", "lost",
        "opportunity", "lead", "prospect", "upsell", "cross-sell",
    ],
    EventCategory.FINANCE: [
        "invoice", "payment", "billing", "expense", "budget", "forecast", "tax",
        "payroll", "cashflow", "p&l", "margin", "cost",
    ],
    EventCategory.OPERATIONS: [
        "deployment", "incident", "outage", "supply", "inventory", "logistics",
        "shipping", "warehouse", "fulfillment", "downtime",
    ],
    EventCategory.MARKETING: [
        "campaign", "impression", "click", "conversion", "ctr", "roi", "brand",
        "seo", "adwords", "social media", "funnel", "awareness",
    ],
    EventCategory.CUSTOMER: [
        "support", "ticket", "churn", "retention", "nps", "csat", "complaint",
        "refund", "onboarding", "feedback", "escalation",
    ],
    EventCategory.ENGINEERING: [
        "release", "bug", "feature", "sprint", "backlog", "technical debt",
        "architecture", "performance", "latency", "error rate", "merge",
    ],
    EventCategory.HR: [
        "hire", "onboard", "offboard", "review", "promotion", "salary",
        "benefit", "training", "policy", "complaint", "diversity",
    ],
    EventCategory.COMPLIANCE: [
        "audit", "regulation", "gdpr", "privacy", "security", "breach",
        "policy violation", "sox", "hipaa", "pci", "compliance",
    ],
}

_SEVERITY_KEYWORDS: dict[EventSeverity, list[str]] = {
    EventSeverity.CRITICAL: ["outage", "breach", "data loss", "security incident", "sev1"],
    EventSeverity.HIGH: ["incident", "failure", "escalation", "urgent", "sev2"],
    EventSeverity.MEDIUM: ["warning", "degraded", "delay", "risk", "issue"],
    EventSeverity.LOW: ["minor", "informational", "note", " FYI"],
    EventSeverity.INFO: ["completed", "success", "info", "update", "scheduled"],
}


@dataclass
class BusinessEvent:
    """A structured business event from a log entry.

    Attributes:
        timestamp: When the event occurred.
        source: Origin system or service name.
        message: Raw event message text.
        category: Auto-detected or manually set business category.
        severity: Auto-detected or manually set severity level.
        metadata: Arbitrary key-value pairs for additional context.
        tags: Free-form tags for filtering and grouping.
    """

    timestamp: datetime
    source: str
    message: str
    category: EventCategory = EventCategory.UNKNOWN
    severity: EventSeverity = EventSeverity.INFO
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Auto-categorize and score severity if not explicitly set."""
        if self.category is EventCategory.UNKNOWN:
            self.category = self._detect_category()
        if self.severity is EventSeverity.INFO:
            detected = self._detect_severity()
            if detected is not None:
                self.severity = detected

    def _detect_category(self) -> EventCategory:
        """Detect the event category from message and source text."""
        text = f"{self.source} {self.message}".lower()
        scores: dict[EventCategory, int] = {}
        for category, keywords in _KEYWORD_MAP.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[category] = score
        if not scores:
            return EventCategory.UNKNOWN
        return max(scores, key=lambda c: scores[c])

    def _detect_severity(self) -> EventSeverity | None:
        """Detect severity from message text. Returns None if indeterminate."""
        text = self.message.lower()
        for severity, keywords in _SEVERITY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return severity
        return None

    def enrich(self, **extra: Any) -> BusinessEvent:
        """Return a new event with additional metadata merged in."""
        new_meta = {**self.metadata, **extra}
        return BusinessEvent(
            timestamp=self.timestamp,
            source=self.source,
            message=self.message,
            category=self.category,
            severity=self.severity,
            metadata=new_meta,
            tags=self.tags.copy(),
        )

    def tag(self, *new_tags: str) -> BusinessEvent:
        """Return a new event with additional tags."""
        merged = list(dict.fromkeys(self.tags + list(new_tags)))
        return BusinessEvent(
            timestamp=self.timestamp,
            source=self.source,
            message=self.message,
            category=self.category,
            severity=self.severity,
            metadata=self.metadata.copy(),
            tags=merged,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BusinessEvent:
        """Create a BusinessEvent from a plain dictionary."""
        ts = data["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        return cls(
            timestamp=ts,
            source=data["source"],
            message=data["message"],
            category=EventCategory(data.get("category", "unknown")),
            severity=EventSeverity(data.get("severity", "info")),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "metadata": self.metadata,
            "tags": self.tags,
        }

    def matches(self, pattern: str) -> bool:
        """Check if message matches a regex pattern."""
        return bool(re.search(pattern, self.message, re.IGNORECASE))
