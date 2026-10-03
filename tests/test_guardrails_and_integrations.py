"""
Tests for the guardrail pipeline and the filesystem integration.

Both are pure/local, so they run with no network or API key.

Run directly:  uv run python tests/test_guardrails_and_integrations.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from tandem.domain.message import ToolCall
from tandem.guardrails.base import Guardrails
from tandem.guardrails.builtin import (
    BlockedTopicGuardrail,
    DomainAllowlistGuardrail,
    PIIRedactionGuardrail,
)
from tandem.integrations.filesystem import FilesystemIntegration


def test_pii_redaction_rewrites_text() -> None:
    g = Guardrails(output=[PIIRedactionGuardrail()])
    verdict = g.run_output("reach me at jane@lab.io or +1 415 555 1234")
    assert "jane@lab.io" not in (verdict.text or "")
    assert "[redacted-email]" in (verdict.text or "")


def test_blocked_topic_blocks_input() -> None:
    g = Guardrails(input=[BlockedTopicGuardrail(["salary"])])
    verdict = g.run_input("what is the CEO salary")
    assert verdict.allowed is False


def test_domain_allowlist_blocks_offlist_site() -> None:
    rail = DomainAllowlistGuardrail(["company.com"])
    call = ToolCall(id="1", name="web_search", arguments={"query": "reactor site:evil.com"})

    class _Fake:  # minimal stand-in for a Tool
        name = "web_search"

    verdict = rail.check(call, _Fake())  # type: ignore[arg-type]
    assert verdict.allowed is False


def test_filesystem_integration_reads_and_refuses_traversal() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "run.txt").write_text("coating thickness = 12um")
        integration = FilesystemIntegration(root)
        tools = {t.name: t for t in integration.tools()}

        read = tools["read_file"].run(path="run.txt")
        assert "12um" in read.content
        assert read.sources  # a citation was attached

        # Path traversal outside the approved root must be refused.
        escaped = tools["read_file"].run(path="../../etc/passwd")
        assert "not found or not permitted" in escaped.content.lower()


if __name__ == "__main__":
    test_pii_redaction_rewrites_text()
    test_blocked_topic_blocks_input()
    test_domain_allowlist_blocks_offlist_site()
    test_filesystem_integration_reads_and_refuses_traversal()
    print("OK — guardrails + filesystem integration behave correctly.")
