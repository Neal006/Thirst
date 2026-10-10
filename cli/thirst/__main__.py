"""Thirst CLI entry point: argument parsing, dispatch and plain-words error handling (plan 04.0).

Exit codes: 0 ok, 2 bad arguments, 3 config, 4 API, 5 GPU, 130 Ctrl-C. An expected failure prints
one line ("thirst: ...") and never a stack trace; a surprise prints a generic line and, with
``--verbose``, the log (which never contains the site key or a signature).
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from . import __version__, commands
from .context import Context, default_context, stderr_writer, stdout_writer
from .errors import EXIT_BAD_ARGS, EXIT_INTERRUPTED, EXIT_OK, CliError
from .planning import MAX_WORK_HOURS

logger = logging.getLogger("thirst")
logger.addHandler(logging.NullHandler())

HANDLERS = {
    "register": "cmd_register",
    "plan": "cmd_plan",
    "run": "cmd_run",
    "sweep": "cmd_sweep",
    "doctor": "cmd_doctor",
    "sync": "cmd_sync",
    "receipt": "cmd_receipt",
}


def _job_options(sub: argparse.ArgumentParser) -> None:
    sub.add_argument(
        "--hours", type=float, required=True, help=f"work at full power (max {MAX_WORK_HOURS:g})"
    )
    sub.add_argument("--deadline", required=True, help='e.g. "2026-10-10 09:00" (India time)')
    sub.add_argument("--pausable", action="store_true", help="allow pauses (single-process jobs)")
    sub.add_argument("--alpha", type=float, default=0.5, help="0 = least CO2, 1 = least water")
    sub.add_argument("--gpu-model", default="auto", help="GPU model id; default: detect")
    sub.add_argument("--gpus", type=int, default=None, help="number of GPUs; default: detect")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thirst", description="Plan, run and measure GPU jobs.")
    parser.add_argument("--version", action="version", version=f"thirst {__version__}")
    parser.add_argument("--verbose", action="store_true", help="log requests (never secrets)")
    commands_ = parser.add_subparsers(dest="command_name")

    reg = commands_.add_parser("register", help="create this lab's site")
    reg.add_argument("--api-url", default=None, help="API address (or THIRST_API_URL)")
    reg.add_argument("--name", required=True)
    reg.add_argument("--city", required=True)
    reg.add_argument("--cooling", required=True, choices=["room_ac", "air_chiller", "evaporative"])
    reg.add_argument("--gpus", type=int, required=True, help="GPUs in the lab")
    reg.add_argument("--org", default=None)
    reg.add_argument("--coverage", type=float, default=0.0, help="share of work covered, 0 to 1")
    reg.add_argument("--private", action="store_true", help="keep the site off the leaderboard")
    reg.add_argument("--public", action="store_true", help="list the site (the default)")
    reg.add_argument("--force", action="store_true", help="replace an existing registration")

    plan = commands_.add_parser("plan", help="show the plan for a job without running it")
    _job_options(plan)
    plan.add_argument("--json", action="store_true", help="print the raw server response")

    run = commands_.add_parser("run", help="plan, then run your command: thirst run ... -- cmd")
    _job_options(run)
    run.add_argument("--now", action="store_true", help="start right away (no waiting)")
    run.add_argument("--modelled", action="store_true", help="no GPU: estimate the energy")
    run.add_argument("--no-cap", action="store_true", help="never change the power limit")
    run.add_argument("--dry-run", action="store_true", help="show the plan, start nothing")
    run.add_argument("--fallback-clocks", action="store_true", help="lock clocks instead of power")
    run.add_argument("--slot-seconds", type=float, default=None, help=argparse.SUPPRESS)

    swp = commands_.add_parser("sweep", help="measure the power-cap sweep (needs a GPU and torch)")
    swp.add_argument("--levels", default="100,85,70")
    swp.add_argument("--steps", type=int, default=300)
    swp.add_argument("--warmup", type=int, default=30)
    swp.add_argument("--idle-seconds", type=float, default=60.0)
    swp.add_argument("--gpu-model", default="auto")
    swp.add_argument("--out", default=None, help="powercap_sweep.json to update")

    doc = commands_.add_parser("doctor", help="check the setup")
    doc.add_argument("--restore", action="store_true", help="undo a power cap left behind")

    commands_.add_parser("sync", help="post receipts waiting in the outbox")

    rec = commands_.add_parser("receipt", help="saved receipts")
    rec_sub = rec.add_subparsers(dest="receipt_action", required=True)
    show = rec_sub.add_parser("show", help="print a saved receipt")
    show.add_argument("job_id")
    return parser


def _split_command(argv: list[str]) -> tuple[list[str], list[str] | None]:
    """Split ``thirst run ... -- cmd args`` at the first ``--`` (only for `run`)."""
    if "--" in argv and "run" in argv[: argv.index("--")]:
        cut = argv.index("--")
        return argv[:cut], argv[cut + 1 :]
    return argv, None


def _parse(argv: list[str], ctx: Context) -> argparse.Namespace | int:
    head, command = _split_command(argv)
    parser = build_parser()
    try:
        args = parser.parse_args(head)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_BAD_ARGS
    if args.command_name is None:
        for line in parser.format_help().rstrip("\n").split("\n"):
            ctx.out(line)
        return EXIT_OK
    args.command = command
    return args


def _setup_logging(verbose: bool) -> None:
    if verbose:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


def main(argv: Sequence[str] | None = None, *, context: Context | None = None) -> int:
    """Run the CLI and return the process exit code."""
    ctx = context or default_context(stdout_writer(), stderr_writer())
    parsed = _parse(list(sys.argv[1:] if argv is None else argv), ctx)
    if isinstance(parsed, int):
        return parsed
    _setup_logging(parsed.verbose)
    handler = getattr(commands, HANDLERS[parsed.command_name])
    try:
        return int(handler(parsed, ctx))
    except CliError as err:
        ctx.err(f"thirst: {err.message}")
        return err.exit_code
    except KeyboardInterrupt:
        ctx.err("thirst: cancelled.")
        return EXIT_INTERRUPTED
    except Exception:
        logger.exception("unexpected error")
        ctx.err(
            "thirst: something unexpected went wrong. "
            "Run again with --verbose and share the output with your team."
        )
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
