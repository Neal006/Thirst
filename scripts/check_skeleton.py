"""Assert that the repository skeleton from plan step 1.2 exists.

Run: ``python scripts/check_skeleton.py`` (exit 0 = skeleton complete).
``template.yaml`` and ``samconfig.toml`` are created by plan step 05.1, so they are
listed separately in ``DEFERRED``.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ENGINE_MODULES = (
    "errors",
    "units",
    "factors",
    "wetbulb",
    "cooling",
    "grid",
    "footprint",
    "planner",
    "score",
)
HANDLER_MODULES = ("api", "refresh", "explain", "store", "security", "validation", "errors")
CLI_MODULES = ("config", "client", "meter", "powercap", "runner", "sweep", "receipt")

REQUIRED_FILES: tuple[str, ...] = (
    "README.md",
    "SPEC.md",
    "ASSUMPTIONS.md",
    "AGENTS.md",
    "LICENSE",
    "Idea.md",
    "prd.md",
    "trd.md",
    "Makefile",
    "pyproject.toml",
    "docs/FIXLIST.md",
    "src/requirements.txt",
    "layers/strands/requirements.txt",
    "cli/pyproject.toml",
    "cli/thirst/__init__.py",
    "cli/thirst/__main__.py",
    "scripts/check_skeleton.py",
    "scripts/seed.py",
    "scripts/bench_plan.py",
    "scripts/gen_assumptions.py",
    "scripts/gen_fixtures.py",
    "scripts/smoke.sh",
    "src/engine/__init__.py",
    "src/handlers/__init__.py",
    ".github/workflows/ci.yml",
    "web/package.json",
    "web/package-lock.json",
    "web/.env.example",
    "web/src/App.tsx",
    *(f"src/engine/{m}.py" for m in ENGINE_MODULES),
    *(f"src/handlers/{m}.py" for m in HANDLER_MODULES),
    *(f"cli/thirst/{m}.py" for m in CLI_MODULES),
)

REQUIRED_DIRS: tuple[str, ...] = (
    "src/engine/data",
    "cli/thirst/data",
    "data/raw",
    "data/notebook",
    "notebooks",
    "tests/engine",
    "tests/handlers",
    "tests/cli",
    "tests/fixtures",
    "tests/vectors",
)

# Created later by their own plan step: template.yaml and samconfig.toml (05.1).
DEFERRED: tuple[str, ...] = ("template.yaml", "samconfig.toml")


def missing(root: Path = ROOT) -> list[str]:
    """Return every required path that does not exist under ``root``."""
    absent = [p for p in REQUIRED_FILES if not (root / p).is_file()]
    absent += [p + "/" for p in REQUIRED_DIRS if not (root / p).is_dir()]
    return absent


def main() -> int:
    absent = missing()
    if absent:
        sys.stderr.write("Skeleton incomplete. Missing:\n")
        for path in absent:
            sys.stderr.write(f"  - {path}\n")
        return 1
    sys.stdout.write(f"Skeleton OK ({len(REQUIRED_FILES)} files, {len(REQUIRED_DIRS)} dirs).\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
