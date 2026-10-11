# Fix list

Running list of problems found while building and testing. Record each item as `- [ ] <area> | <problem> | <owner>`. Mark it `[x]` when fixed, or add `(accepted: <reason>)`.
The prioritised plan for these items lives in [`TODO.md`](TODO.md).

## Open

- [ ] web | The water/carbon slider can't change anything while the placeholder power-cap sweep makes all 11 Pareto points identical. On `feat/web-ui-accessibility` the planner hides it and says why (accepted until the sweep is measured, TODO 2.1) | —

## Fixed on 2026-10-11

- [x] ci | PR #19 (Bedrock error notes + a one-sentence job box) was merged with an unresolved conflict in `web/src/pages/PlanPage.tsx` (`<<<<<<< HEAD … >>>>>>> upstream/main`): web lint failed, `main` CI went red and Deploy was skipped from 18:09. Nothing reached AWS (stack and Lambdas last updated 12:32 IST). PR #20 reverted the merge; `main` CI, Deploy and the live e2e job are green again. The feature can come back as a fixed PR from the `pr-18` branch.

On `feat/web-ui-accessibility` (each with tests):

- [x] cli | `thirst doctor` on a laptop GPU said "The NVIDIA driver reported an error while reading the GPU" and failed. It now prints `[warn]`, explains that laptops block power-limit changes, and points to `--no-cap` (TODO 4.1.a).
- [x] cli | `thirst plan` printed `Assumptions: /assumptions`. It now prints the full site URL (4.1.b).
- [x] cli | `thirst run --dry-run` showed hour slots (12:00–18:00) under a plan line saying 12:47–17:14. It now uses the plan's times (4.1.c).
- [x] cli | `--modelled` needed `--gpu-model` and `--gpus` even with a GPU detected. It now uses the detected GPU (4.1.d).
- [x] cli | A 2-minute job printed `0.00 kWh` and `0.0 L`. Below 0.1 kWh it now shows Wh, mL and g (4.1.e).
- [x] cli | A `--private` site's receipt printed a link that returns 404. It now says the receipts are kept off the website (4.1.f).
- [x] cli | A `--modelled` receipt said "uncapped" next to the 70% plan level's saving. It now says "modelled at 70% (plan level)" (4.1.g).
- [x] cli | Review leftovers (TODO 4.2): the site key no longer reaches the user's command, the `/plan` reply is checked before use, `nvidia-smi` and `sudo` run by full path, the sweep sets `CUDA_DEVICE_ORDER`, the output tee survives a failing log, and the CLI tests run on Python 3.10.
- [x] cli | A second `thirst sweep` run replaced the first. It is now combined (median per level, plan 4.5.d, TODO 2.2).
- [x] web | The phone e2e "jump links scroll to their group" test was flaky. It now waits for the tables to render (5.4).
- [x] web | axe on the UX branch found low-contrast tag chips, a faded "Sample" stamp and a timetable scroll area the keyboard couldn't reach. All fixed before the branch was offered for merge.
- [x] web | Four header links broke words on a 360 px phone. They no longer wrap (new e2e check).
- [x] ci | Deploy logs warned that Node 20 actions are deprecated. The workflows use Node 24 versions now, and Deploy runs the e2e suite against the live site after each deploy (TODO 3.5, 5.5).

Earlier:

- [x] deploy | The Deploy workflow failed with "Not authorized to perform sts:AssumeRoleWithWebIdentity": the repo uses GitHub's immutable OIDC subject. The role now trusts both forms (D38).
- [x] web | axe found 14 failing audits: low contrast (`--text-faint`, `--leaf`, `--alarm`, `--tag-measured`, gold badge), a `<p>` inside a `<dl>`, and tag chips smaller than 24 px. Fixed in PR #9.
- [x] web | The home page "get started" box showed the GitHub install line; it now shows `pip install thirst` (PR #11).
- [x] web | The main JS chunk was 810 kB, and the production build shipped an unused mock chunk. It is now 249 kB, with no mocks (PR #6).
- [x] cli | Receipts were saved only after the network attempt. Now they are on disk first, and Ctrl-C while sending keeps them for `thirst sync` (PR #7).
- [x] cli | An error while a job was paused skipped SIGCONT before SIGTERM; a crashed cap restore exited 0; SIGHUP killed the CLI with the cap still applied (PR #7).
- [x] cli | PyPI had 0.3.0, without the fixes above or the 31 new GPUs, so an RTX 3050 Laptop wasn't recognised. 0.3.1 was published via Trusted Publishing (PR #12); 0.3.2 (PR #15) adds the walkthrough fixes.

## Metrics evidence (PRD §8.1)

- [x] `POST /plan` p95 < 2000 ms: **383 ms** over 50 live calls, 0 failures. Evidence: `docs/bench_plan.txt`, 2026-10-11.
- [x] Cost < $5: Cost Explorer shows **$0.00** unblended for 1–11 Oct 2026. The console screenshot is still to be saved.
- [~] Clean-machine setup: a fresh venv → `pip install thirst` → `register` → `plan` → `run` → receipt took about 5 minutes on 2026-10-11 (Windows laptop, Python 3.12). A second rehearsal on a different machine (Linux, Python 3.13, fresh venv, `pip install ./cli` → `doctor` → `register` → a 60 s `run --modelled --now` → receipt, against `scripts/local_api.py`) took **70 s**. The formal timed run with the live API and a phone (plan 7.6) is still open (TODO 1.14).
- [x] Full-history secret scan: gitleaks 8.28.0 over all 54 commits and the working tree, **no leaks found** (`docs/gitleaks_full_history.txt`).
- [ ] `powercap_sweep.json` measured for our GPU: needs a desktop NVIDIA GPU
- [ ] At least one receipt with method `nvml_*` on the board: needs a GPU run
- [x] Video < 3:00: **2:54** (174 s), `docs/video/thirst-demo.mp4` with captions `docs/video/thirst-demo.srt` (Neal). YouTube upload still open.
