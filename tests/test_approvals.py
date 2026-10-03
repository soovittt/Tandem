"""
Tests for the approval broker — especially the safety-critical id correlation:
a stale/mismatched approval must NOT authorize the current action.

Run:  uv run python tests/test_approvals.py
"""

from __future__ import annotations

import threading
import time

from tandem.agent.approval import ApprovalBroker, PendingApproval


def test_id_correlation_and_grant() -> None:
    broker = ApprovalBroker()
    result: dict[str, bool] = {}

    def worker() -> None:
        result["decision"] = broker.request(
            "s1", PendingApproval(tool="x", arguments={}, description="d"), timeout=5
        )

    t = threading.Thread(target=worker)
    t.start()
    time.sleep(0.2)

    pending = broker.pending("s1")
    assert pending is not None, "action should be pending"

    # A mismatched id must be ignored (the real action keeps waiting).
    assert broker.resolve("s1", "wrong-id", True) is False
    assert broker.pending("s1") is not None, "still pending after stale approve"

    # The correct id approves it.
    assert broker.resolve("s1", pending.id, True) is True
    t.join(timeout=2)
    assert result.get("decision") is True


def test_timeout_denies() -> None:
    broker = ApprovalBroker()
    decision = broker.request(
        "s2", PendingApproval(tool="x", arguments={}, description="d"), timeout=0.3
    )
    assert decision is False  # no resolve → deny on timeout


if __name__ == "__main__":
    test_id_correlation_and_grant()
    test_timeout_denies()
    print("OK — approval id-correlation + timeout-denies verified.")
