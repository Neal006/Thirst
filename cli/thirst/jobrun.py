"""`thirst run`: plan, wait, cap, run, meter, receipt (plan 04.6 and 04.7)."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from typing import Any

from . import config, outbox, powercap, receipt
from .context import ApiClient, Context
from .errors import EXIT_BAD_ARGS, EXIT_GPU, EXIT_INTERRUPTED, CliError, GpuError
from .gpus import child_environment
from .jobsetup import JobGpus, detect_gpus, load_client, web_url
from .meter import EnergyMeter, Meter
from .modelled import ModelledMeter, load_bundled_sweep, power_model
from .planning import build_plan_request, parse_deadline
from .powercap import PowerCap
from .runner import (
    CapController,
    PausableDecision,
    Runner,
    RunnerOptions,
    RunOutcome,
    pausable_decision,
)
from .schedule import Segment, compress, plan_line, segments_from_plan, transitions

logger = logging.getLogger(__name__)

_NO_COMMAND = (
    "Put your command after --, for example: "
    'thirst run --hours 6 --deadline "2026-10-10 09:00" -- python train.py'
)
_MARKER_PRESENT = (
    "A previous run may have left a GPU power cap in place. "
    "Run `thirst doctor --restore` first, then try again."
)
_ACTIONS = {
    "start": "start the command at {level}% power",
    "pause": "pause the command (SIGSTOP)",
    "resume": "resume the command at {level}% power",
    "cap": "change the power cap to {level}%",
    "end": "planned end",
}


@dataclass(frozen=True)
class _Instruments:
    meter: EnergyMeter
    cap: CapController | None
    gpus: JobGpus


def _plan_from_server(
    client: ApiClient, request: dict[str, Any]
) -> tuple[str, dict[str, Any], tuple[Segment, ...]]:
    plan = client.post_plan(request)
    chosen = plan.get("chosen")
    plan_id = plan.get("plan_id")
    if not isinstance(chosen, dict) or not isinstance(plan_id, str):
        raise CliError("The server sent a plan the CLI cannot read. Try again in a minute.")
    return plan_id, chosen, segments_from_plan(chosen.get("schedule") or [])


def _print_dry_run(ctx: Context, segments: tuple[Segment, ...]) -> None:
    ctx.out("Dry run: nothing is started. The CLI would make these changes:")
    for step in transitions(segments):
        text = _ACTIONS[step.action].format(level=round(step.level * 100))
        ctx.out(f"  {step.when:%d %b %H:%M}  {text}")


def _instruments(ctx: Context, args: argparse.Namespace, gpus: JobGpus, sleep: Any) -> _Instruments:
    if args.modelled:
        model = power_model(gpus.model, load_bundled_sweep())
        meter = ModelledMeter(
            model, gpus.count, gpu_label=gpus.model.label, wall=ctx.wall, mono=ctx.mono
        )
        return _Instruments(meter, None, gpus)
    if gpus.api is None:
        raise GpuError("No GPU is available to measure.")
    meter = Meter(gpus.api, gpus.indices, wall=ctx.wall, mono=ctx.mono)
    cap = None
    if not args.no_cap:
        cap = PowerCap(
            gpus.api,
            gpus.indices,
            smi=ctx.smi,
            sleep=sleep,
            fallback_clocks=args.fallback_clocks,
        )
    return _Instruments(meter, cap, gpus)


def _exit_code(outcome: RunOutcome) -> int:
    if outcome.interrupted:
        code = EXIT_INTERRUPTED
    elif outcome.exit_code is None:
        code = 1
    elif outcome.exit_code < 0:
        code = 128 + abs(outcome.exit_code)  # killed by a signal, as a shell reports it
    else:
        code = outcome.exit_code
    if outcome.restore_failures and code == 0:
        code = EXIT_GPU  # the job worked but a GPU is still capped: scripts must notice
    return code


def _report_restore_failures(ctx: Context, outcome: RunOutcome) -> None:
    if not outcome.restore_failures:
        return
    ctx.err("WARNING: could not put the GPU power limit back. Run by hand:")
    for command in outcome.restore_failures:
        ctx.err(f"  {command}")
    ctx.err("Or run `thirst doctor --restore` later.")


def _handle_receipt(
    ctx: Context,
    client: ApiClient,
    body: dict[str, Any],
    gpus: JobGpus,
    outcome: RunOutcome,
) -> None:
    for note in outcome.notes:
        ctx.out(f"Note: {note}")
    for warning in receipt.plausibility_warnings(body, gpus.model.p_max_w):
        ctx.out(f"Warning: {warning}")
    posted = outbox.post_or_queue(client, body)
    status = posted.status
    receipt.save_receipt(body, posted.response, status)
    if status == "posted" and posted.response:
        text = receipt.format_scored(body, posted.response, web_url(ctx.env))
    elif status == "queued":
        text = receipt.format_local(body, queued=True)
    else:
        text = receipt.format_local(body, queued=False, note=posted.message)
    ctx.out(text.rstrip("\n"))


def _finish(
    ctx: Context,
    args: argparse.Namespace,
    client: ApiClient,
    gpus: JobGpus,
    outcome: RunOutcome,
    meter: EnergyMeter,
    ids: tuple[str, str, str],
) -> int:
    _report_restore_failures(ctx, outcome)
    if not outcome.started:
        if outcome.error:
            ctx.err(f"thirst: {outcome.error}")
            return EXIT_BAD_ARGS if outcome.error.startswith("Could not start") else 1
        ctx.out("Nothing was started, so there is no receipt.")
        return EXIT_INTERRUPTED
    if outcome.error:
        ctx.err(f"thirst: {outcome.error}")
    site_id, plan_id, job_id = ids
    facts = receipt.JobFacts(
        site_id=site_id,
        plan_id=plan_id,
        job_id=job_id,
        start_ts=outcome.start_ts or ctx.wall(),
        end_ts=outcome.end_ts or ctx.wall(),
        exit_code=outcome.exit_code,
        interrupted=outcome.interrupted,
        overran=outcome.overran,
        cap_applied=outcome.cap_applied,
        cap_method=outcome.cap_method,
    )
    body = receipt.build_body(facts, meter.summary())
    if args.slot_seconds:
        ctx.out("This was a test run (--slot-seconds), so the receipt was not posted.")
        ctx.out(receipt.format_local(body, queued=False, note="Test run, not posted.").rstrip())
    else:
        _handle_receipt(ctx, client, body, gpus, outcome)
    return _exit_code(outcome)


def _execute(
    ctx: Context,
    args: argparse.Namespace,
    client: ApiClient,
    site_id: str,
    plan_id: str,
    segments: tuple[Segment, ...],
    gpus: JobGpus,
    decision: PausableDecision,
) -> int:
    flag = ctx.new_flag()
    sleep = ctx.make_sleep(flag)
    parts = _instruments(ctx, args, gpus, sleep)
    job_id = receipt.new_job_id()
    runner = Runner(
        segments,
        list(args.command),
        meter=parts.meter,
        cap=parts.cap,
        spawn=ctx.spawn,
        wall=ctx.wall,
        mono=ctx.mono,
        sleep=sleep,
        interrupt=flag,
        say=ctx.out,
        env=child_environment(ctx.env),
        log_path=config.logs_dir() / f"{job_id}.log",
        guard=ctx.make_guard(flag),
        options=RunnerOptions(pausable=decision.pausable, meter_background=ctx.meter_background),
    )
    try:
        outcome = runner.run()
        return _finish(ctx, args, client, gpus, outcome, parts.meter, (site_id, plan_id, job_id))
    finally:
        parts.meter.close()


def cmd_run(args: argparse.Namespace, ctx: Context) -> int:
    if not args.command:
        raise CliError(_NO_COMMAND)
    cfg, client = load_client(ctx)
    deadline = parse_deadline(args.deadline)
    uses_gpu_caps = not (args.modelled or args.no_cap or args.dry_run)
    if uses_gpu_caps and powercap.marker_present():
        raise GpuError(_MARKER_PRESENT)
    gpus = detect_gpus(
        ctx,
        gpu_model=args.gpu_model,
        gpus=args.gpus,
        need_hardware=not (args.modelled or args.dry_run),
        modelled=args.modelled,
    )
    try:
        decision = pausable_decision(args.pausable, args.command, ctx.env, ctx.os_name)
        if decision.reason:
            ctx.out(decision.reason)
        request = build_plan_request(
            site_id=cfg.site_id,
            gpu_model=gpus.model.id,
            gpu_count=gpus.count,
            work_hours=args.hours,
            deadline=deadline,
            pausable=decision.pausable,
            pausable_allowed=decision.allowed,
            alpha=args.alpha,
            force_now=args.now,
        )
        plan_id, chosen, segments = _plan_from_server(client, request)
        ctx.out(plan_line(chosen))
        if args.slot_seconds:
            segments = compress(segments, args.slot_seconds, ctx.wall())
        if args.dry_run:
            _print_dry_run(ctx, segments)
            return 0
        return _execute(ctx, args, client, cfg.site_id, plan_id, segments, gpus, decision)
    finally:
        if gpus.api is not None:
            gpus.api.shutdown()
