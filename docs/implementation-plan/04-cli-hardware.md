# Phase 04 — CLI and hardware layer

Owner: **B** · Window: **Fri 13:00 to 22:00** · Gate: **M3 Scope lock** (overnight job started at 22:00)
Source: TRD §6 (hardware), §7.1 (signing), PRD US3/US4, F7/F8, PRD §6.2 (CLI flow).

[← Index](README.md) · Contracts: [08 §3 API](08-reference-contracts.md#3-api-contract), [08 §6 HMAC vectors](08-reference-contracts.md#6-hmac-test-vectors), [08 §2.6 config.toml](08-reference-contracts.md#26-thirstconfigtoml)

---

## 4.0 Shape of the CLI

```
thirst register --name "CSE GPU Lab" --city Chennai --cooling room_ac --gpus 4 [--org ...] [--coverage 0.8] [--public/--private]
thirst plan     --hours 6 --deadline "2026-10-10 09:00" [--pausable] [--alpha 0.5] [--gpu-model auto] [--gpus N] [--json]
thirst run      --hours 6 --deadline "..." [--pausable] [--alpha 0.5] [--now] [--modelled] [--no-cap] [--dry-run] -- <command...>
thirst sweep    [--levels 100,85,70] [--steps 300] [--warmup 30] [--idle-seconds 60] [--out PATH]
thirst doctor   # NVML? energy counter? cap permission? API reachable? config valid? clock skew vs server?
thirst sync     # re-post receipts queued in ~/.thirst/outbox/
thirst receipt show <job_id>   # re-print a saved receipt
```

| File | Responsibility |
|---|---|
| `__main__.py` | argparse, subcommands, exit codes (0 ok · 2 bad args · 3 config · 4 API · 5 GPU · 130 Ctrl-C) |
| `config.py` | read and write `~/.thirst/config.toml`, env overrides, file mode 0600 |
| `client.py` | HTTP client: timeouts, retries, HMAC signing, outbox queue |
| `meter.py` | NVML sampler thread, energy per GPU, per-slot run/idle buckets |
| `powercap.py` | read limits, set a clamped cap, clock-lock fallback, guaranteed restore |
| `runner.py` | state machine: wait, cap, start, pause/resume, finish, interrupt |
| `sweep.py` | ResNet-18 power-cap sweep, writes `powercap_sweep.json` |
| `receipt.py` | build the receipt body, print the terminal receipt, save to `~/.thirst/receipts/` |

Dependencies (`cli/pyproject.toml`): `requires-python = ">=3.10"`, `nvidia-ml-py>=12`, `httpx>=0.27`, `tomli>=2; python_version<'3.11'`, `tomli-w`. Optional extra `sweep = ["torch", "torchvision"]`. Entry point: `thirst = "thirst.__main__:main"`.

---

## 4.1 Package skeleton and config (30 min, P0)

**Tests first** (`tests/cli/test_config.py`)

1. `register` writes `~/.thirst/config.toml` (use `tmp_path` as HOME) with `api_url, site_id, token`. On POSIX the file mode is `0o600`.
2. The `THIRST_API_URL` and `THIRST_TOKEN` env vars override the file.
3. A missing config for `run` (without `--modelled --offline`) exits with code 3 and the message "Run `thirst register` first".
4. A corrupt TOML gives a clear error, not a traceback.

**Implement**

- **4.1.a** `cli/pyproject.toml` as above; `pip install -e ./cli` works.
- **4.1.b** Python 3.10 support: `tomllib` if available, else `tomli`.
- **4.1.c** `config.py`: a frozen `Config` dataclass; `load()`; `save()` (writes atomically: a temp file, then `os.replace`, then `chmod 600`).
- **4.1.d** `__main__.py` with subcommand stubs that print "not yet".

---

## 4.2 HTTP client and signing (40 min, P0)

**Tests first** (`tests/cli/test_client.py`, using the shared vectors in `tests/vectors/hmac.json`, 08 §6)

1. `sign(token, ts, raw_body)` equals the vector's expected hex for every vector.
2. The body is serialised **once** to bytes, and those exact bytes are both signed and sent. A test asserts that the sent body equals the signed body.
3. Timeouts: connect 5 s, read 15 s. Retries: 3 with backoff of 1, 2, 4 s on 5xx and network errors, **never on 4xx**.
4. If posting a receipt fails after all retries, it is written to `~/.thirst/outbox/<job_id>.json` (the body only; the old timestamp is **not** reused). `thirst sync` re-signs with a fresh timestamp and posts it again.
5. A 409 `duplicate_job` from the server during `sync` counts as success and removes the item from the outbox.

**Implement**

- **4.2.a** `Client(api_url, token)` with `post_plan`, `post_site`, `post_receipt`, `get_site`, `get_server_time` (read from the `Date` header of `GET /assumptions`, used by `doctor` for the skew check).
- **4.2.b** Headers: `X-Thirst-Timestamp` (unix seconds, string), `X-Thirst-Signature` (hex), `X-Thirst-Site` (site_id), `Content-Type: application/json`, `User-Agent: thirst-cli/<version>`.
- **4.2.c** Never log the token. `--verbose` logs the URL, status and latency only.

---

## 4.3 `meter.py` — NVML energy measurement (60 min, P0)

**Tests first** (`tests/cli/test_meter.py` with a **fake pynvml** module injected through `sys.modules`)

1. With an energy counter: samples of 0, 1000, 2500 mJ give a total of 2500 mJ.
2. A counter reset or wrap (a negative delta, for example after a driver reload) is ignored for that interval and logged as `counter_reset`. The interval's energy uses power × dt.
3. Without an energy counter (`NotSupported`), the meter falls back to `power_mW × dt`. The receipt's `method = nvml_power_integration`.
4. **Slot bucketing:** a sample interval that crosses the 02:00 boundary is split in proportion to time on each side.
5. **Run/idle split:** energy goes to `run_kwh` or `idle_kwh` depending on the runner state at the sample time. While waiting before start, nothing is recorded.
6. **GPU selection (D25):** CUDA's default order (fastest first) is not NVML's order (PCI bus). The runner sets `CUDA_DEVICE_ORDER=PCI_BUS_ID` in the child's environment (unless the user already set it), then maps `CUDA_VISIBLE_DEVICES` entries (indices or `GPU-…` UUIDs) to NVML handles **by UUID**. A test uses a fake NVML whose PCI order differs from the "fastest" order. Without the variable, all GPUs are measured.
7. The thread stops within 2 s of `stop()`, and `close()` calls `nvmlShutdown`.

**Implement**

- **4.3.a** `Meter(gpu_indices, state_fn)` runs a `threading.Thread(daemon=True)` that loops every **1 s** (TRD 6.1). It uses `time.monotonic()` for `dt` and the IST wall clock for slot assignment.
- **4.3.b** Probe per GPU at start: name, UUID, driver version, `has_energy_counter`, default / min / max power limits.
- **4.3.c** The bucket structure is `dict[slot_start_iso] -> {run_kwh, idle_kwh, level}`. It is guarded by a lock, and only the runner thread changes the state.
- **4.3.d** `summary()` gives the per-slot list for the receipt (08 §3.4), totals, method, and per-GPU metadata.
- **4.3.e** `--modelled` mode: `ModelledMeter` has the same interface and estimates `u × P_max × ε_l × τ_l` per GPU from the bundled `gpus.json`, `factors.json` and `powercap_sweep.json` in `cli/thirst/data/` (D19). `method = modelled` (TRD 6.5).

---

## 4.4 `powercap.py` — power cap with guaranteed restore (60 min, P0)

**Tests first** (`tests/cli/test_powercap.py` with fake NVML and a fake `subprocess.run` for `nvidia-smi`)

1. Target = `level × default_limit`, **clamped** to `[min, max]` (TRD 6.2).
2. Restore sets the **original** limit read at start, not the default. A test sets the original to a non-default value.
3. `NVML_ERROR_NO_PERMISSION` → try `sudo -n nvidia-smi -i <i> -pl <W>` (non-interactive, needs the sudoers entry from 1.8.e) → if that fails too, `cap_applied = false` and the job continues uncapped with a warning (TRD 6.2, Idea §11.8).
4. Clock-lock fallback (`--fallback-clocks`, or automatically when `-pl` is not supported): `nvidia-smi -lgc min,max`, then `-rgc` on restore. The receipt records `cap_method = "clock_lock"`.
5. **Restore on every exit path** (TRD 6.2, §14 "Power cap restore"): the context manager restores on normal exit, on an exception, on `SIGINT`, on `SIGTERM`, and through `atexit`. Restore is **idempotent** (calling it twice is safe).
6. A per-GPU failure during restore is retried 3 times. If it still fails, print a loud warning with the exact manual command to run.

**Implement**

- **4.4.a** `class PowerCap` (context manager) with `apply(level)`, `restore()` and `applied: bool`.
- **4.4.b** Read limits with `nvmlDeviceGetPowerManagementLimitConstraints`, `nvmlDeviceGetPowerManagementDefaultLimit` and `nvmlDeviceGetPowerManagementLimit` (current = original).
- **4.4.c** Set with `nvmlDeviceSetPowerManagementLimit(handle, mW)`, with the `nvidia-smi` fallback as above.
- **4.4.d** Write a **restore marker** file `~/.thirst/restore.json` (`{gpu_uuid: original_mW}`) before the first change, and delete it after restore. On the next CLI start, if the marker exists (for example after `kill -9` or a power loss), offer to restore: `thirst doctor --restore`.
- **4.4.e** Level changes in the middle of a run (pausable plans can change level per slot) call `apply(level)` again; restore still goes to the original.

---

## 4.5 `sweep.py` — measured power-cap sweep (45 min of work + about 45 min of machine time, P0, Fri afternoon)

**Tests first** (`tests/cli/test_sweep.py`, CPU-only with fakes)

1. `τ_l = time_100 / time_l` and `ε_l = (energy_l / steps) / (energy_100 / steps)` (TRD 6.4).
2. The output JSON validates against 08 §2.5 and includes the GPU name, driver, date and `steps`.
3. Re-running for the same GPU **replaces** that GPU's entry and keeps the other GPUs' entries.

**Implement**

- **4.5.a** Workload (TRD 6.4): torchvision `resnet18(num_classes=10)`, random tensors `(128, 3, 32, 32)` and random labels, SGD, **30 warm-up + 300 timed steps**, `torch.cuda.synchronize()` before each timer read. No dataset download, so the result is repeatable.
- **4.5.b** For each level in 100, 85, 70: apply the cap, wait 5 s to settle, run, record wall time, NVML energy and average power. Restore between levels and at the end (reuse `PowerCap`).
- **4.5.c** Idle: 60 s with the model loaded and no work → `p_idle_w`. Also `u = avg_power_100 / P_max`.
- **4.5.d** Run the sweep **once** (about 45 min of GPU time). Re-run only if a 4.5.f sanity gate fails. If a second run happens, keep the median per level and both runs in `raw`.
- **4.5.e** Write `src/engine/data/powercap_sweep.json` and copy the numbers into the commit message. The engine marks τ/ε/u/p_idle **measured** for that GPU (02.2.d).
- **4.5.f** **Sanity gates**, so the demo doesn't quote nonsense: `0.7 ≤ τ_85 ≤ 1.0`, `0.6 ≤ ε_85 ≤ 1.05`, `τ_70 ≤ τ_85`. If a gate fails, re-run once; if it fails again, keep the placeholders and record the raw result in `AGENTS.md`.
- **4.5.g** Run it on the GPU box by **Fri 17:00** (M2). The video line "85% power costs X% speed and saves Y% energy" comes from this file.

---

## 4.6 `runner.py` — wait, run, pause, resume, finish (90 min, P0, critical path)

### State machine

```
INIT → (plan fetched) → WAITING ──(slot start)──► RUNNING(level) ──(pause slot)──► PAUSED ──(run slot)──► RUNNING(level)
                           │                         │                                  │
                           └──────── Ctrl-C / SIGTERM at any state ──► INTERRUPTED ─────┘
RUNNING ──(child exits)──► FINISHED   (child exit code recorded; receipt still posted)
any ──(fatal error)──► FAILED (restore cap, SIGCONT if paused, save receipt locally)
```

### Tests first (`tests/cli/test_runner.py`; POSIX-only tests marked `skipif(os.name=="nt")`)

1. **Happy path with a fake clock:** the plan is wait 2 slots, run 1 at 85%, pause 1, run 1 at 100%. Check the state sequence, the `apply(level)` calls and the bucketed slots.
2. **Real child process:** `python -c "import time; [time.sleep(0.1) for _ in range(50)]"`, paused with SIGSTOP and resumed with SIGCONT. Check that the child's process group really stops (no progress while paused) and finishes.
3. **Ctrl-C while PAUSED:** the runner sends **SIGCONT before SIGTERM** (a stopped process can't handle SIGTERM), waits 10 s, then SIGKILL. The cap is restored, the receipt is saved with `interrupted: true` and posted. Exit code 130.
4. **Child fails** (exit 1) in the first slot: the receipt is posted with `exit_code = 1`, and the cap is restored.
5. **Job runs longer than the plan:** it keeps running after the last planned slot at the last level, and the receipt has `overran: true`. The CLI prints "Job ran past the plan; deadline may be missed". The planner's work estimate came from the user.
6. **Job finishes early:** the remaining schedule is ignored and nothing is idle-metered after exit.
7. **Distributed or Windows:** `cmd` contains `torchrun`, `accelerate launch`, `deepspeed`, `mpirun` or `srun`, **or** `WORLD_SIZE>1` is set, **or** the OS is Windows → `pausable` is forced to false before planning, and the plan request says so (D15).
8. **Clock jump or suspend:** if the wall clock jumps forward by more than 5 minutes between ticks, log `clock_jump` and resync to the current slot (don't replay missed transitions).
9. **`--now`:** skips waiting; the plan request has `force_now=true`, and the server returns the Base schedule as `chosen` (08 §3.1).
10. **`--dry-run`:** prints the plan and the transitions it would make, and doesn't start the command.

### Implement

- **4.6.a** Plan: `POST /plan` with the job **and always `site_id` from the config** (D23), so the server fills in city and cooling from the site and links the plan to it (the GPU model is auto-detected from NVML names through `nvml_name_patterns`; `--gpu-model` overrides; GPU count = number of visible GPUs). Print the one-line plan from PRD §6.2.4: "Plan: start 01:00, cap 85%, pause 04:00 to 05:00, done by 08:10".
- **4.6.b** Waiting: sleep until the next transition in chunks of at most 30 s, and print a countdown line every 10 minutes. Ctrl-C while waiting exits cleanly without posting a receipt (nothing ran).
- **4.6.c** Start: `subprocess.Popen(cmd, start_new_session=True)` (TRD 6.3); keep `pgid = os.getpgid(pid)`. stdout and stderr pass through to the terminal, and are also tee'd to `~/.thirst/logs/<job_id>.log`.
- **4.6.d** Transitions at slot boundaries: `killpg(pgid, SIGSTOP)` / `SIGCONT`; `powercap.apply(level)` before resuming; `meter.set_state("run" | "idle")`.
- **4.6.e** Signal handlers are installed **before** the first cap change. `SIGINT` and `SIGTERM` set a flag; the main loop does the shutdown sequence (restore, SIGCONT, terminate, receipt). Don't do heavy work inside the signal handler.
- **4.6.f** At the end: stop the meter, restore the cap, build the receipt (4.7), print it, post it (queue it in the outbox if posting fails), and save it to `~/.thirst/receipts/<job_id>.json`.
- **4.6.g** Exit code: the child's exit code if it finished, 130 if interrupted.
- **4.6.h Manual GPU-box check** (M3, before 22:00): a 3-slot plan with 1-minute slots (hidden flag `--slot-seconds 60`, for testing only) running `python -c` with a CUDA matmul loop. Watch `nvidia-smi` show the power limit change, the process stop (0% utilisation while paused, memory still allocated), resume, and the limit restore. Then press Ctrl-C mid-run and check the limit is restored (`nvidia-smi -q -d POWER`).

---

## 4.7 `receipt.py` — build, print, post (40 min, P0)

**Tests first**

1. The body matches 08 §3.4. All slot hours are within `[start_ts, end_ts]` (the server checks this too).
2. `Σ kWh ≤ gpu_count × P_max_kW × hours × 1.1` holds locally **before** posting. If it doesn't, the measurement is wrong: print a warning and post anyway, and the server will reject it with a clear code.
3. The terminal output (golden-file test) shows kWh **(measured)**, litres and kg CO₂ **(modelled, ranges)**, the Base comparison ("If you had started right away"), Capture ("You took 86% of the possible saving"), the site score with the Provisional tag, and the receipt URL.

**Implement**

- **4.7.a** Body: `site_id, plan_id, job_id (D22), start_ts, end_ts, slots[{hour, run_kwh, idle_kwh, level}], cap_applied, cap_method, method, gpu{name, driver, count}, exit_code, interrupted, overran, cli_version`.
- **4.7.b** Post → the server returns the scored receipt (08 §3.4 response). The CLI prints the **server's** numbers, not local estimates, so the CLI and the web always agree.
- **4.7.c** If posting failed (outbox), print the local kWh only, plus "Receipt queued, run `thirst sync`".

---

## 4.8 `doctor` and `register` and `plan` commands (30 min, P0)

- **4.8.a** `thirst register` → `POST /sites` → save the config, print the site id and the site URL. Warn: "Site names are public" (TRD 7.1).
- **4.8.b** `thirst plan` → `POST /plan` → print the one-line plan plus the savings ranges, and with `--json`, the raw response.
- **4.8.c** `thirst doctor` checks, each printed as ✓ or ✗ with a fix hint: Python version · `pynvml` import · GPUs found and their model mapping · energy counter supported · cap permission (dry run: read the limits, try setting the current limit to itself) · leftover restore marker · config present · API reachable · clock skew < 60 s (the signature window is 600 s) · `sudo -n nvidia-smi` works if configured.

---

## 4.9 Overnight real job (Fri 21:30 to 22:00 setup, P0, gate M3)

The single most important recording of the hackathon (G3, PRD §8.1).

- **4.9.a** Use the workload chosen and timed in **1.8.h** (about 5 to 6 h at 100%). The job must start **by 22:30 at the latest**. `/receipts` doesn't need to be live yet, because the receipt waits in the outbox until `thirst sync` (gate M3).
- **4.9.b** On the GPU box, inside `tmux new -s thirst`:
  ```bash
  thirst doctor
  thirst run --hours <H> --deadline "2026-10-10 09:00" --pausable -- python train.py ...
  ```
  Check the printed plan. Take a **screenshot** of it (for the video).
- **4.9.c** Detach. Before leaving, check: the box won't sleep (1.8.g), there is enough disk space for logs and checkpoints, persistence mode is on, and the restore marker path is writable.
- **4.9.d** Backup: if `thirst run` fails in the first 15 minutes, re-run with `--now` (non-pausable) so there is still a measured receipt by morning (gate M3 fallback).
- **4.9.e** **Sat 09:00 verification** (07.2): the receipt was posted (or is in the outbox → `thirst sync`), the site page shows it, Capture is shown, and the power limit was restored. Save the full terminal output to `docs/overnight_receipt.txt` and take screenshots for the video.

---

## 4.10a Deferred to Sat 09:00 to 12:00 (load balancing)

These P0 items move out of B's Friday so the overnight job starts on time: 4.4.d restore marker plus `doctor --restore` · 4.6 tests 8 (clock jump) and 10 (`--dry-run`) · 4.8.c `doctor` checks beyond NVML, cap and API · `thirst sync` (4.2 tests 4 and 5 stay; the outbox write must exist on Friday, and the sync command is Saturday).
The 4.6.h manual GPU check is the one Friday safety net for the cap restore.

## 4.11 `--offline` plans (P1)

`thirst plan/run --offline` plans locally with the engine (no server), and the receipt is posted with `method = "unverified"`: stored, never scored (D20). Only build it if all P0 is green at Sat 12:00. Until then, 4.1 test 3, 2.8 test 11 (unverified part) and 5.7 test 8 are P1.

## 4.10 CLI review (30 min, P0)

- **4.10.a** `ecc:python-reviewer` + `ecc:code-reviewer` on `cli/`.
- **4.10.b** `ecc:security-reviewer` on `client.py` (signing, token storage), `powercap.py` (sudo usage, no shell injection: **always pass a list of args to `subprocess`, never `shell=True`**), and `runner.py` (the user's command is run as given, never through a shell string).
- **4.10.c** Fix CRITICAL and HIGH findings before 22:00.
