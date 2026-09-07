from __future__ import annotations

from typing import Any


class ReadOnlyConnectorMixin:
    """Shared no-write behaviour for ITSM/monitoring connectors.

    These connector categories are registered as read-only in the capability
    registry (ticketing and monitoring data sources feed discovery and
    evidence, they do not execute remediation), so plan execution against
    them fails closed with a clear message instead of silently no-op'ing.
    """

    async def execute_action(self, *, action: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        raise NotImplementedError(f"{self.connector_id} is a read-only connector and does not execute actions")  # type: ignore[attr-defined]

    async def rollback_action(self, *, action: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        raise NotImplementedError(f"{self.connector_id} is a read-only connector and does not support rollback")  # type: ignore[attr-defined]

    async def validate_action(self, *, action: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(f"{self.connector_id} is a read-only connector and does not validate actions")  # type: ignore[attr-defined]
