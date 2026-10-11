# Fix list

Running list of problems found while building and testing. Record each item as `- [ ] <area> | <problem> | <owner>`. Mark it `[x]` when fixed, or add `(accepted: <reason>)`.
The prioritised plan for these items lives in [`TODO.md`](TODO.md).

## Open

Found in the live walkthroughs on 2026-10-11 (laptop with an RTX 3050 Laptop GPU, `thirst` 0.3.0/0.3.1 against the live API):

- [ ] cli | `thirst doctor` on a laptop GPU says "The NVIDIA driver reported an error while reading the GPU" and fails. The real cause: the GPU doesn't allow power-limit changes (`nvidia-smi` shows `[N/A]`). It should be a warning that points to `--no-cap`. (TODO 4.1.a) | —
- [ ] cli | `thirst plan` prints `Assumptions: /assumptions`, a relative path; it should print the full site URL (TODO 4.1.b) | —
- [ ] cli | `thirst run --dry-run` shows hour slots (12:00–18:00) while the plan line shows 12:47–17:14 (TODO 4.1.c) | —
- [ ] cli | `--modelled` needs `--gpu-model` and `--gpus` even when a GPU is detected (TODO 4.1.d) | —
- [ ] cli | A 2-minute job prints `0.00 kWh` and `0.0 L`; show Wh and mL below 0.1 kWh (TODO 4.1.e) | —
- [ ] cli | For a `--private` site, the receipt prints a web link that returns 404 (TODO 4.1.f) | —
- [ ] cli | A `--modelled` receipt says "uncapped" but is credited with the 70% plan level's saving: the modelled meter assumes the plan's level was followed. Say "modelled at 70% (plan level)". (TODO 4.1.g) | —
- [ ] web | The phone e2e "jump links scroll to their group" test failed once against the live site, then passed 12/12 on re-run; make its wait more robust (TODO 5.4) | —
- [ ] web | The water/carbon slider has no visible effect, because the placeholder power-cap sweep makes all 11 Pareto points identical (accepted until the sweep is measured, TODO 2.1) | —

## Fixed on 2026-10-11

- [x] deploy | The Deploy workflow failed with "Not authorized to perform sts:AssumeRoleWithWebIdentity": the repo uses GitHub's immutable OIDC subject. The role now trusts both forms (D38).
- [x] web | axe found 14 failing audits: low contrast (`--text-faint`, `--leaf`, `--alarm`, `--tag-measured`, gold badge), a `<p>` inside a `<dl>`, and tag chips smaller than 24 px. Fixed in PR #9.
- [x] web | The home page "get started" box showed the GitHub install line; it now shows `pip install thirst` (PR #11).
- [x] web | The main JS chunk was 810 kB, and the production build shipped an unused mock chunk. It is now 249 kB, with no mocks (PR #6).
- [x] cli | Receipts were saved only after the network attempt. Now they are on disk first, and Ctrl-C while sending keeps them for `thirst sync` (PR #7).
- [x] cli | An error while a job was paused skipped SIGCONT before SIGTERM; a crashed cap restore exited 0; SIGHUP killed the CLI with the cap still applied (PR #7).
- [x] cli | PyPI had 0.3.0, without the fixes above or the 31 new GPUs, so an RTX 3050 Laptop wasn't recognised. 0.3.1 is now published via Trusted Publishing (PR #12).

## Metrics evidence (PRD §8.1)

- [x] `POST /plan` p95 < 2000 ms: **383 ms** over 50 live calls, 0 failures. Evidence: `docs/bench_plan.txt`, 2026-10-11.
- [x] Cost < $5: Cost Explorer shows **$0.00** unblended for 1–11 Oct 2026. The console screenshot is still to be saved.
- [~] Clean-machine setup: a fresh venv → `pip install thirst` → `register` → `plan` → `run` → receipt took about 5 minutes on 2026-10-11 (Windows laptop, Python 3.12). The formal timed run on a second machine (plan 7.6) is not done.
- [ ] `powercap_sweep.json` measured for our GPU: needs a desktop NVIDIA GPU
- [ ] At least one receipt with method `nvml_*` on the board: needs a GPU run
- [ ] Video < 3:00: not recorded yet
