"""
Credential broker.

The agent should never hold raw secrets. Instead, tools ask the broker to
authorize a request to a named endpoint; the broker attaches the secret ONLY if
that endpoint is allow-listed, and returns headers the caller can use without
ever seeing the key. This mirrors how OpenShell brokers credentials so an agent
can act on approved systems without being trusted with the keys themselves.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Credential:
    """A secret plus the single endpoint prefix it may be sent to."""

    endpoint_prefix: str  # e.g. "https://api.company-eln.com/"
    header_name: str      # e.g. "Authorization"
    header_value: str     # e.g. "Bearer <token>"


class CredentialBroker:
    """Injects credentials only for approved endpoints; never exposes raw secrets."""

    def __init__(self, credentials: list[Credential] | None = None) -> None:
        self._credentials = credentials or []

    def authorize(self, url: str) -> dict[str, str]:
        """Return headers to attach for `url`, or empty if nothing is authorized."""
        for cred in self._credentials:
            if url.startswith(cred.endpoint_prefix):
                return {cred.header_name: cred.header_value}
        return {}

    def is_allowed(self, url: str) -> bool:
        return any(url.startswith(c.endpoint_prefix) for c in self._credentials)
