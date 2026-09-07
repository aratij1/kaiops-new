"""Validate an operator-managed recovery observer registry without network access."""

from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend/src/common"))

from common.recovery_observers import load_recovery_observer_registry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    parser.add_argument(
        "--query-references",
        action="store_true",
        help="Print expected query hashes for review; does not change the file.",
    )
    args = parser.parse_args()
    try:
        if args.query_references:
            payload = json.loads(args.registry.read_text(encoding="utf-8"))
            references = [
                {
                    "validator_id": check["spec"]["validator_id"],
                    "check_reference": "promql:sha256:" + sha256(check["query"].encode()).hexdigest(),
                }
                for profile in payload["profiles"]
                for check in profile["checks"]
            ]
            print(json.dumps(references, indent=2))
        else:
            registry = load_recovery_observer_registry(str(args.registry))
            print(
                json.dumps(
                    {
                        "valid": True,
                        "sources": len(registry.sources),
                        "profiles": len(registry.profiles),
                        "validators": sum(len(profile.checks) for profile in registry.profiles),
                    }
                )
            )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Registry validation failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
