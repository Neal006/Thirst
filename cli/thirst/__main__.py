"""Thirst CLI entry point. Subcommands are implemented in plan steps 04.x."""

from __future__ import annotations

import sys
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI. Returns the process exit code."""
    _ = argv  # Subcommand parsing arrives in plan step 04.1.
    sys.stdout.write(
        "thirst: not implemented yet (see docs/implementation-plan/04-cli-hardware.md)\n"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
