from __future__ import annotations

import os
from urllib.parse import urlparse


class SecretResolutionError(RuntimeError):
    pass


async def resolve_secret_ref(secret_ref: str) -> str:
    """Resolve a `scheme://name` credential reference to its live secret value.

    Only the `env://` scheme is implemented today - it reads a named environment
    variable, matching the convention already documented on
    ``ConnectorMetadata.secret_provider_schemes`` in connector-hub. The other
    advertised schemes (aws-sm, azure-kv, gcp-sm, vault) are intentionally left
    unresolved here rather than faked, so a misconfigured connector fails
    closed instead of silently reporting a fabricated success.
    """
    value = str(secret_ref or "").strip()
    if not value or "://" not in value:
        raise SecretResolutionError("secret_ref must use an explicit provider scheme, e.g. env://JIRA_API_TOKEN")
    scheme = value.split("://", 1)[0].lower()
    if scheme != "env":
        raise SecretResolutionError(
            f"secret provider '{scheme}' is not configured in this deployment; use env:// or wire a real provider"
        )
    parsed = urlparse(value)
    name = (parsed.netloc + parsed.path).strip("/")
    if not name:
        raise SecretResolutionError("environment secret reference has no variable name")
    resolved = os.getenv(name)
    if resolved is None:
        raise SecretResolutionError(f"environment secret {name} is unavailable")
    return resolved
