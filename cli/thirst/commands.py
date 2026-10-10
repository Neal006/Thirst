"""The `thirst` subcommands except `run` (plan 04.8, 04.2, 04.5). `run` lives in jobrun.py."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import config, outbox, powercap, receipt, sweep
from .context import Context
from .errors import EXIT_API, EXIT_GPU, ApiError, CliError, ConfigError, GpuError
from .gpus import child_environment, resolve_model, select_gpu_indices
from .jobrun import cmd_run
from .jobsetup import detect_gpus, load_client, web_url
from .nvml import EnergyCounterUnsupported, LimitNotSupported, LimitPermissionDenied
from .planning import build_plan_request, parse_deadline
from .runner import pausable_decision
from .schedule import plan_line

__all__ = [
    "cmd_doctor",
    "cmd_plan",
    "cmd_receipt",
    "cmd_register",
    "cmd_run",
    "cmd_sweep",
    "cmd_sync",
]

CLOCK_SKEW_LIMIT_S = 60


# ------------------------------------------------------------ register


def cmd_register(args: argparse.Namespace, ctx: Context) -> int:
    api_url = args.api_url or ctx.env.get(config.URL_ENV) or config.DEFAULT_API_URL
    if not api_url:
        raise ConfigError(
            "Tell Thirst where the API is: pass --api-url, or set THIRST_API_URL "
            "(your team lead has the address)."
        )
    if config.config_path().exists() and not args.force:
        raise ConfigError(
            f"This computer is already registered ({config.config_path()}). "
            "Use --force to register a new site and replace it."
        )
    if not 0 <= args.coverage <= 1:
        raise CliError("--coverage must be between 0 and 1.")
    if args.gpus < 1:
        raise CliError("--gpus must be at least 1.")
    body: dict[str, Any] = {
        "name": args.name,
        "city": args.city,
        "cooling": args.cooling,
        "gpu_count": args.gpus,
        "coverage_declared": args.coverage,
        "public": not args.private,
    }
    if args.org:
        body["org"] = args.org
    created = ctx.make_client(api_url, "", "").post_site(body)
    saved = config.save(
        config.Config(api_url=api_url, site_id=created["site_id"], token=created["token"])
    )
    ctx.out(f"Registered site {created['site_id']} (division {created.get('division', '?')}).")
    ctx.out(f"Site page: {web_url(ctx.env).rstrip('/')}/sites/{created['site_id']}")
    ctx.out(f"The site key was saved to {saved} (private to your user). It is not shown again.")
    if body["public"]:
        ctx.out("Note: site names are public. Use --private to keep this site off the leaderboard.")
    return 0


# ------------------------------------------------------------ plan


def print_savings(ctx: Context, plan: dict[str, Any]) -> None:
    ranges = (plan.get("chosen") or {}).get("savings_ranges") or {}
    ctx.out("Expected savings compared with starting right away (ranges, modelled):")
    for key, label in (("water_pct", "Water"), ("co2_pct", "CO2"), ("energy_pct", "Energy")):
        if key in ranges:
            low, high = ranges[key]
            ctx.out(f"  {label:<7}{low} to {high}%")
    if plan.get("notes"):
        ctx.out("Notes: " + ", ".join(str(n) for n in plan["notes"]))
    ctx.out(f"Plan id: {plan.get('plan_id', '?')}. Assumptions: /assumptions")


def cmd_plan(args: argparse.Namespace, ctx: Context) -> int:
    cfg, client = load_client(ctx)
    deadline = parse_deadline(args.deadline)
    job = detect_gpus(ctx, gpu_model=args.gpu_model, gpus=args.gpus, need_hardware=False)
    decision = pausable_decision(args.pausable, (), ctx.env, ctx.os_name)
    request = build_plan_request(
        site_id=cfg.site_id,
        gpu_model=job.model.id,
        gpu_count=job.count,
        work_hours=args.hours,
        deadline=deadline,
        pausable=decision.pausable,
        pausable_allowed=decision.allowed,
        alpha=args.alpha,
        force_now=False,
    )
    plan = client.post_plan(request)
    if args.json:
        ctx.out(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    if decision.reason:
        ctx.out(decision.reason)
    ctx.out(plan_line(plan["chosen"]))
    print_savings(ctx, plan)
    return 0


# ------------------------------------------------------------ sync and receipts


def cmd_sync(args: argparse.Namespace, ctx: Context) -> int:
    _, client = load_client(ctx)
    queued = outbox.pending()
    if not queued:
        ctx.out("Nothing to send: the outbox is empty.")
        return 0
    result = outbox.sync(client)
    if result.sent:
        ctx.out(f"Posted {len(result.sent)} receipt(s).")
    if result.duplicates:
        ctx.out(f"{len(result.duplicates)} receipt(s) were already recorded by the server.")
    for job_id, message in result.rejected:
        ctx.out(f"Could not post {job_id}: {message} (moved to the outbox/rejected folder).")
    if result.error:
        ctx.err(f"thirst: {result.error}")
        ctx.err(f"{len(result.still_queued)} receipt(s) are still queued. Run `thirst sync` later.")
    return EXIT_API if (result.error or result.rejected) else 0


def cmd_receipt(args: argparse.Namespace, ctx: Context) -> int:
    ctx.out(receipt.render_saved(args.job_id).rstrip("\n"))
    return 0


# ------------------------------------------------------------ doctor


class _Report:
    """Collects the doctor's checks; prints [ok] or [FAIL] with a fix hint."""

    def __init__(self, ctx: Context) -> None:
        self._ctx = ctx
        self.failed = 0

    def ok(self, label: str, detail: str = "") -> None:
        self._ctx.out(f"[ok]   {label}" + (f": {detail}" if detail else ""))

    def fail(self, label: str, detail: str, hint: str = "") -> None:
        self.failed += 1
        suffix = f"  -> {hint}" if hint else ""
        self._ctx.out(f"[FAIL] {label}: {detail}{suffix}")


def _check_config_and_api(report: _Report, ctx: Context) -> None:
    try:
        cfg = config.load(ctx.env)
    except ConfigError as err:
        report.fail("Config", err.message, "run `thirst register`")
        return
    report.ok("Config", f"site {cfg.site_id}")
    try:
        server_time = ctx.make_client(cfg.api_url, cfg.token, cfg.site_id).get_server_time()
    except ApiError as err:
        report.fail("API reachable", err.message, "check your internet and THIRST_API_URL")
        return
    report.ok("API reachable")
    skew = abs((server_time - ctx.wall()).total_seconds())
    if skew > CLOCK_SKEW_LIMIT_S:
        report.fail(
            "Your clock vs the server",
            f"differs by {skew:.0f} s (limit {CLOCK_SKEW_LIMIT_S} s; "
            "receipts are rejected at 600 s)",
            "turn on automatic time sync",
        )
    else:
        report.ok("Your clock vs the server", f"{skew:.0f} s apart")


def _check_cap_permission(report: _Report, ctx: Context, api: Any) -> None:
    label = "GPU power cap permission"
    try:
        api.set_limit_mw(0, api.current_limit_mw(0))  # set the current limit to itself
    except LimitPermissionDenied:
        if ctx.smi(["sudo", "-n", "nvidia-smi", "-L"]) == 0:
            report.ok(label, "NVML needs root, but `sudo -n nvidia-smi` works")
        else:
            report.fail(
                label,
                "setting a power limit needs root",
                "run once as root: nvidia-smi -pm 1, then allow `sudo -n nvidia-smi` (sudoers)",
            )
    except LimitNotSupported:
        report.ok(label, "power limits are not supported; the clock-lock fallback will be used")
    except GpuError as err:
        report.fail(label, err.message, "run `nvidia-smi` to see the GPU state")
    else:
        report.ok(label)


def _check_gpus(report: _Report, ctx: Context) -> None:
    try:
        api = ctx.open_nvml()
    except GpuError as err:
        report.fail("NVIDIA GPU", err.message)
        return
    try:
        indices = select_gpu_indices(api, child_environment(ctx.env))
        names = [api.name(i) for i in indices]
        try:
            model = resolve_model(names, None)
        except CliError as err:
            report.fail("GPU model", err.message)
        else:
            report.ok("NVIDIA GPU", f"{len(indices)} x {names[0]} (model {model.id})")
        _check_counter(report, api, indices)
        _check_cap_permission(report, ctx, api)
    except GpuError as err:
        report.fail("NVIDIA GPU", err.message)
    finally:
        api.shutdown()


def _check_counter(report: _Report, api: Any, indices: tuple[int, ...]) -> None:
    missing = []
    for index in indices:
        try:
            api.total_energy_mj(index)
        except EnergyCounterUnsupported:
            missing.append(index)
    if missing:
        report.ok(
            "GPU energy counter",
            f"GPU {missing} has none; Thirst will use power integration (less exact)",
        )
    else:
        report.ok("GPU energy counter")


def cmd_doctor(args: argparse.Namespace, ctx: Context) -> int:
    if args.restore:
        return _restore(ctx)
    report = _Report(ctx)
    version = sys.version_info
    if version >= (3, 10):
        report.ok(f"Python {version.major}.{version.minor}.{version.micro}")
    else:
        report.fail("Python", f"{version.major}.{version.minor} is too old", "use Python 3.10+")
    _check_config_and_api(report, ctx)
    _check_gpus(report, ctx)
    if powercap.marker_present():
        report.fail(
            "Restore marker",
            "a previous run may have left a power cap in place",
            "run `thirst doctor --restore`",
        )
    else:
        report.ok("Restore marker", "none left over")
    return 1 if report.failed else 0


def _restore(ctx: Context) -> int:
    if not powercap.marker_present():
        ctx.out("Nothing to restore: no power cap was left behind.")
        return 0
    api = ctx.open_nvml()
    try:
        sleep = ctx.make_sleep(ctx.new_flag())
        result = powercap.recover_from_marker(api, ctx.smi, sleep=sleep)
    finally:
        api.shutdown()
    for uuid in result.restored:
        ctx.out(f"Restored the original power limit on {uuid}.")
    if result.note:
        ctx.err(f"thirst: {result.note}")
    if result.failed:
        ctx.err("Could not restore every GPU. Run by hand:")
        for command in result.manual_commands or tuple(
            f"(GPU {u} not found)" for u in result.failed
        ):
            ctx.err(f"  {command}")
        return EXIT_GPU
    return 0


# ------------------------------------------------------------ sweep


def _default_sweep_path() -> Path:
    engine_data = Path("src") / "engine" / "data"
    return (engine_data if engine_data.is_dir() else Path()) / "powercap_sweep.json"


def cmd_sweep(args: argparse.Namespace, ctx: Context) -> int:
    levels = sweep.parse_levels(args.levels)
    out = Path(args.out) if args.out else _default_sweep_path()
    api = ctx.open_nvml()
    try:
        indices = select_gpu_indices(api, child_environment(ctx.env))[:1]
        model = resolve_model(
            [api.name(indices[0])], None if args.gpu_model == "auto" else args.gpu_model
        )
        ctx.out(
            f"Sweeping {api.name(indices[0])} (GPU {indices[0]}): {args.steps} steps per level."
        )
        result = sweep.run_sweep(
            api,
            indices,
            model,
            ctx.make_workload(),
            levels=levels,
            steps=args.steps,
            warmup=args.warmup,
            idle_seconds=args.idle_seconds,
            smi=ctx.smi,
            mono=ctx.mono,
            sleep=ctx.make_sleep(ctx.new_flag()),
            now=ctx.wall,
        )
    finally:
        api.shutdown()
    return _finish_sweep(ctx, out, model.id, result)


def _finish_sweep(ctx: Context, out: Path, model_id: str, result: sweep.SweepResult) -> int:
    for level, values in result.entry["levels"].items():
        ctx.out(f"  {round(float(level) * 100)}%: tau {values['tau']:.3f}, eps {values['eps']:.3f}")
    ctx.out(f"  u {result.entry['u']:.3f}, idle power {result.entry['p_idle_w']:.1f} W")
    if result.gate_failures:
        rejected = out.with_suffix(".rejected.json")
        sweep.write_result(rejected, model_id, result.entry)
        ctx.err("The sweep failed its sanity checks, so the placeholders stay in place:")
        for message in result.gate_failures:
            ctx.err(f"  {message}")
        ctx.err(f"Run it once more. The raw result was saved to {rejected}.")
        return EXIT_GPU
    sweep.write_result(out, model_id, result.entry)
    ctx.out(f"Wrote {out}. Commit it so the engine uses the measured numbers.")
    return 0
