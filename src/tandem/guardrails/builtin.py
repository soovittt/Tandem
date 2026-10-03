"""
Built-in guardrails: a small, real starter set.

These are deliberately simple and dependency-free so the pipeline works today.
For production, wrap NeMo Guardrails as additional rails implementing the same
protocols (topic control, jailbreak detection, richer PII models, etc.).
"""

from __future__ import annotations

import re

from tandem.domain.message import ToolCall
from tandem.guardrails.base import GuardrailVerdict
from tandem.tools.base import Tool

# Patterns for common sensitive data. Intentionally conservative.
_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("[redacted-email]", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("[redacted-phone]", re.compile(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b")),
    ("[redacted-key]", re.compile(r"\b(?:sk|pk|api|key)[-_][A-Za-z0-9]{16,}\b")),
]


class PIIRedactionGuardrail:
    """Redact obvious PII / secrets from text (usable as input OR output rail)."""

    def check(self, text: str) -> GuardrailVerdict:
        redacted = text
        for replacement, pattern in _PII_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return GuardrailVerdict(allowed=True, text=redacted)


class BlockedTopicGuardrail:
    """Refuse inputs mentioning configured off-limits terms (input rail)."""

    def __init__(self, blocked_terms: list[str]) -> None:
        self._terms = [t.lower() for t in blocked_terms]

    def check(self, text: str) -> GuardrailVerdict:
        lowered = text.lower()
        for term in self._terms:
            if term in lowered:
                return GuardrailVerdict(
                    allowed=False, reason=f"Request touches a blocked topic: {term!r}."
                )
        return GuardrailVerdict(allowed=True)


class DomainAllowlistGuardrail:
    """Restrict web_search to an approved set of domains (tool rail)."""

    def __init__(self, allowed_domains: list[str]) -> None:
        self._allowed = [d.lower() for d in allowed_domains]

    def check(self, call: ToolCall, tool: Tool) -> GuardrailVerdict:
        if call.name != "web_search":
            return GuardrailVerdict(allowed=True)
        query = str(call.arguments.get("query", "")).lower()
        # If the query pins a site: filter, it must be an allowed domain.
        for token in query.split():
            if token.startswith("site:"):
                domain = token[len("site:"):]
                if not any(domain.endswith(a) for a in self._allowed):
                    return GuardrailVerdict(
                        allowed=False, reason=f"Domain {domain!r} is not allow-listed."
                    )
        return GuardrailVerdict(allowed=True)
