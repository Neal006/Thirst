# Phase 01 — Foundations

Owner: **all** (lead per step below) · Window: **Fri 9 Oct 09:00 to 10:30 IST** · Gate: **G0 Ready**
Goal: everyone can write code, run tests, deploy to AWS, and reach every external data source by 10:30.
Nothing in later phases should wait on accounts, installs or permissions.

[← Index](README.md)

### Implementation status (9 Oct 2026)

| Step | Status |
|---|---|
| 1.1 repo hygiene | **Done locally** (1.1.a was done on GitHub as `Neal006/Thirst`; 1.1.h branch protection still open) |
| 1.2 skeleton | **Done locally**; `python scripts/check_skeleton.py` exits 0 (stubs only; `template.yaml` and `samconfig.toml` wait for 05.1) |
| 1.3 Python tooling | **Done locally** (ruff, mypy, pytest, coverage pass; `make` was not available on the first dev box, so the Makefile has not been run yet) |
| 1.4 Node tooling | **Done locally** on Node 22; `npm run lint`, `npm test -- --run` and `npm run build` pass |
| 1.5 CI | **Written, not yet run on GitHub** |
| 1.6 AWS and guardrails | **Open, needs a person** (account, SAM CLI, Docker, budgets, Bedrock, SSM secret) |
| 1.7 data checks | 1.7.a **done** (`sample_forecast.json`); 1.7.b to 1.7.f **open** |
| 1.8 GPU box | **Open, needs the GPU machine** |
| 1.9 team and admin | **Open, needs a person** |
| 1.10 AGENTS.md | **Done** (kept current in each change) |

---

## 1.1 Repository hygiene (lead: A, 15 min, P0)

**Sub-steps**

- **1.1.a** Rename the repo to match the product (decision D2):
  `gh repo rename thirst --repo Neal006/thrist --yes`, then `git remote set-url origin https://github.com/Neal006/thirst.git` in every clone.
- **1.1.b** Rename the idea doc so cross-references resolve (D1): `git mv Idea_1.md Idea.md`.
- **1.1.c** Add `LICENSE` (MIT, holder "team hello_world", year 2026). It's required at submission (TRD §17).
- **1.1.d** Add `.gitignore`: Python (`__pycache__/`, `.venv/`, `.pytest_cache/`, `.coverage`, `htmlcov/`, `*.egg-info/`, `dist/`), Node (`node_modules/`, `web/dist/`), SAM (`.aws-sam/`), notebooks (`.ipynb_checkpoints/`), OS (`.DS_Store`, `Thumbs.db`), local config (`.env`, `.env.*`, `!.env.example`, `samconfig.local.toml`).
- **1.1.e** Add `.editorconfig` (UTF-8, LF, 4 spaces for Python, 2 for TS/JSON/YAML, final newline).
- **1.1.f** Add `.gitattributes` with `* text=auto eol=lf`. This stops the CRLF warnings already seen on Windows.
- **1.1.g** Check the history rule (TRD §3, "commits only from 8 Oct 2026"): `git log --reverse --format='%ad %s' --date=iso | head -1`. The first commit must be on or after 2026-10-08.
- **1.1.h** Protect `main`: require CI to pass and forbid force-push
  (`gh api -X PUT repos/Neal006/thirst/branches/main/protection ...`, or the web UI). On a private free
  repo where protection is unavailable, agree to the rule verbally and record it in `AGENTS.md`.

**Done when:** `gh repo view --json name,visibility` shows `thirst`, `PRIVATE`; `LICENSE`, `.gitignore`, `.editorconfig` and `.gitattributes` are on `main`.

---

## 1.2 Directory skeleton (lead: A, 10 min, P0)

Create the TRD §3 layout plus the plan-level additions (D5, D6, D14, D19). Each empty directory gets a one-line `README.md` or `__init__.py` so git keeps it.

```
thirst/
├─ README.md  SPEC.md  ASSUMPTIONS.md  AGENTS.md  LICENSE
├─ Idea.md  prd.md  trd.md
├─ docs/implementation-plan/…  docs/FIXLIST.md  docs/india_finding.png (later)
├─ template.yaml  samconfig.toml
├─ Makefile                      # task runner (see 1.3.e)
├─ pyproject.toml                # engine + handlers + dev tools (ruff, pytest, hypothesis, mypy)
├─ src/
│  ├─ engine/  __init__.py units.py factors.py wetbulb.py cooling.py grid.py footprint.py planner.py score.py
│  │           data/ factors.json gpus.json cities.json grid_shares.json powercap_sweep.json sample_forecast.json
│  ├─ handlers/ __init__.py api.py refresh.py explain.py store.py security.py validation.py errors.py
│  └─ requirements.txt           # aws-lambda-powertools only (boto3 is in the runtime)
├─ layers/strands/requirements.txt   # strands-agents (D14)
├─ cli/ pyproject.toml  thirst/ __init__.py __main__.py config.py client.py meter.py powercap.py runner.py sweep.py receipt.py data/gpus.json
├─ web/                          # Vite + React + TS (Phase 06)
├─ data/raw/  data/notebook/     # downloads and notebook outputs only (D6)
├─ notebooks/india_tradeoff_check.ipynb
├─ scripts/ seed.py bench_plan.py gen_assumptions.py gen_fixtures.py smoke.sh
└─ tests/ engine/ handlers/ cli/ fixtures/ vectors/
```

**Done when:** `python scripts/check_skeleton.py` exits 0 (it asserts every path above exists), and `python -c "import sys; sys.path.insert(0,'src'); import engine, handlers"` succeeds.

---

## 1.3 Python tooling (lead: B, 20 min, P0)

- **1.3.a** Every machine: Python **3.12** (matches Lambda). The CLI supports 3.10 or newer for lab machines (see 04.1.b).
- **1.3.b** Use `uv` (fast) or `python -m venv .venv`. Commands in this plan use `uv run …`; the plain-pip equivalent is `.venv/bin/python -m …`.
- **1.3.c** Root `pyproject.toml`:
  - `[project] name = "thirst-engine"`, `requires-python = ">=3.12"`, no runtime dependencies (D16).
  - `[project.optional-dependencies] dev = ["pytest>=8", "pytest-cov", "hypothesis", "ruff", "mypy", "boto3", "moto[dynamodb,ssm]>=5", "aws-lambda-powertools", "freezegun"]`.
  - `[tool.pytest.ini_options] pythonpath = ["src", "cli"]`, `testpaths = ["tests"]`, `addopts = "-q --strict-markers"`, markers `gpu` (needs NVIDIA) and `aws` (needs real AWS).
  - `[tool.ruff] line-length = 100`, rules `E,F,I,B,UP,SIM,S` (S = bandit-style security).
  - `[tool.coverage.report] fail_under = 80`. Engine-only gate is 90 (enforced in CI by a second `--cov=src/engine --cov-fail-under=90` run).
- **1.3.d** Pre-commit (optional but recommended): `ruff`, `ruff-format`, `end-of-file-fixer`, `gitleaks`.
- **1.3.e** `Makefile` targets (each one is one line, and works the same in CI):
  `make test` · `make cov` · `make lint` · `make type` · `make check` (= lint + type + cov) · `make fixtures` · `make assumptions` · `make build` (`sam build`) · `make deploy` · `make web` · `make web-test` · `make smoke`.
  On Windows without `make`, run the same commands as listed in the Makefile, or use Git Bash.

**Done when:** `make check` runs on a clean clone and passes on the empty skeleton (one trivial test, `tests/test_smoke.py::test_imports`).

---

## 1.4 Node tooling (lead: C, 15 min, P0)

- **1.4.a** Node **22.12 or newer** (the lockfile's vitest 5, jest-dom 7 and jsdom 29 need it; the CI web job uses 22), npm 10+. `web/package.json` has `"engines": {"node": ">=22.12"}`.
- **1.4.b** `npm create vite@latest web -- --template react-ts` (D17), then `cd web && npm i recharts react-router-dom` and `npm i -D vitest @testing-library/react @testing-library/jest-dom jsdom @playwright/test msw eslint prettier`.
- **1.4.c** `web/.env.example`: `VITE_API_URL=http://127.0.0.1:3000` and `VITE_USE_MOCKS=false`.
- **1.4.d** `npm run build` and `npm test -- --run` pass on the scaffold.

**Done when:** `cd web && npm ci && npm run build && npm test -- --run` passes.

---

## 1.5 Continuous integration (lead: A, 15 min, P0)

`.github/workflows/ci.yml`, triggered on `push` and `pull_request`:

| Job | Steps |
|---|---|
| `python` | checkout → setup-python 3.12 → `pip install -e .[dev]` → `ruff check` → `mypy src` → `pytest --cov=src --cov=cli -m "not gpu and not aws"` → engine coverage ≥ 90 |
| `web` | checkout → setup-node 20 → `npm ci` → `npm run lint` → `npm test -- --run` → `npm run build` |
| `sam` | `pip install aws-sam-cli` → `sam validate --lint` (no AWS credentials needed) |
| `secrets` | `gitleaks/gitleaks-action@v2` |

- **1.5.a** Pin action versions to tags (`actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4`).
- **1.5.b** Concurrency group per branch so old runs cancel.
- **1.5.c** Badge in `README.md`.

**Done when:** the first PR shows four green checks.

---

## 1.6 AWS account and guardrails (lead: A, 30 min, P0)

- **1.6.a** Sign in with the hackathon account. Set the region to **`ap-south-1`** in the console and in the CLI profile:
  `aws configure sso` (or access keys for an IAM user `thirst-deployer`) → profile `thirst`; check with `aws sts get-caller-identity --profile thirst`.
- **1.6.b** Install the **SAM CLI** (check `sam --version` ≥ 1.120) and **Docker Desktop**. Docker is needed for `sam build --use-container` and `sam local`.
- **1.6.c** **AWS Budgets** (TRD §12): one monthly cost budget with alerts at **$10, $25, $50** (actual) to two team emails, plus a **$5 forecast alert** for the PRD Saturday target (D4).
- **1.6.d** Turn on **Cost Explorer** now (data takes up to 24 h to appear).
- **1.6.e** **Bedrock model access, start now because approval can take time:** Console → Bedrock (`ap-south-1`) → Model access → request one small model, for example Claude Haiku or Amazon Nova Micro or Lite, whichever is offered. If none is offered in `ap-south-1`, request it in `us-east-1` and note that a cross-region inference profile is needed (TRD §2). Record the exact `BEDROCK_MODEL_ID` in `AGENTS.md` Gotchas.
- **1.6.f** Create the server secret (TRD §2 "Secrets"). It is never committed and never printed again:
  ```bash
  aws ssm put-parameter --profile thirst --region ap-south-1 \
    --name /thirst/server_secret --type SecureString \
    --value "$(python -c 'import secrets; print(secrets.token_hex(32))')"
  ```
- **1.6.h** **By Fri 12:00** (PRD §11 open decision): post the chosen `BEDROCK_MODEL_ID` and region (or "not approved yet → template only") in the chat and in `AGENTS.md`.
- **1.6.g** Write down the **never create** list from TRD §12 at the top of `AGENTS.md` Gotchas: EC2 GPU, SageMaker endpoints, OpenSearch, NAT Gateway, RDS/Aurora, provisioned concurrency.

**Done when:** `aws ssm get-parameter --name /thirst/server_secret --with-decryption --profile thirst --query Parameter.Name` returns the name; budgets are visible; the Bedrock request is submitted (screenshot in the team chat).

---

## 1.7 External data checks (lead: C, 30 min, P0)

Each check either passes, or triggers its fallback **now** instead of at 12:00.

- **1.7.a Open-Meteo forecast**, all 6 seed cities in **one** request (multi-location call):
  ```bash
  curl "https://api.open-meteo.com/v1/forecast?latitude=13.0827,12.9716,17.3850,19.0760,28.6139,18.5204&longitude=80.2707,77.5946,78.4867,72.8777,77.2090,73.8567&hourly=temperature_2m,relative_humidity_2m,shortwave_radiation&timezone=Asia%2FKolkata&forecast_days=3&past_days=1"
  ```
  Expect a JSON **array** of 6 objects, each with 96 hourly values. Save one response as `src/engine/data/sample_forecast.json` (the offline fallback, TRD §9).
- **1.7.b Open-Meteo archive** for Step 0: `https://archive-api.open-meteo.com/v1/archive?...&start_date=2026-09-25&end_date=2026-10-08`. Archive data can lag by a few days; if the latest days are missing, take 14 days ending at the last available date.
- **1.7.c CSEP tracker export** (grid Option A): try carbontracker.in for the national 5-minute generation by source over the last 14 days. Look for a CSV or download button first, then the page's JSON network calls. **Time box 20 minutes.** If nothing exports cleanly, go to Option B. Don't scrape against the site's terms.
- **1.7.d Ember** (grid Option B and calibration): download India annual generation by source for 2023-24 (and the latest year) from Ember's data explorer to `data/raw/ember_india.csv`. Record the licence (usually CC-BY 4.0) in `ASSUMPTIONS.md`.
- **1.7.e WRI Aqueduct**: look up the baseline water stress category for the 6 cities. Record the category, the lookup date and the URL per city in `src/engine/data/cities.json` (schema in 08 §2.3).
- **1.7.f** Record every source URL, the access date and the licence in `ASSUMPTIONS.md` as you go. Don't leave it to Saturday.

**Done when:** `sample_forecast.json` is committed; the Option A/B grid decision is posted (formal deadline Fri 12:00, PRD §11); `cities.json` has 6 entries with stress categories.

---

## 1.8 GPU machine readiness (lead: B, 30 min, P0)

- **1.8.a** `nvidia-smi`: record the GPU model, driver version and CUDA version in `AGENTS.md` Gotchas.
- **1.8.b** Check power-limit control:
  `nvidia-smi -q -d POWER` shows the min, max and default limits. Try `sudo nvidia-smi -i 0 -pl <default-50>`, then restore with `sudo nvidia-smi -i 0 -pl <default>`.
  If it's refused (laptop or permissions), test the fallback `sudo nvidia-smi -i 0 -lgc 300,1500` then `-rgc` (TRD §6.2).
- **1.8.c** Persistence mode: `sudo nvidia-smi -pm 1` (keeps limits across short idle periods; they still reset on reboot).
- **1.8.d** Check that the energy counter is supported:
  `python -c "import pynvml as n; n.nvmlInit(); h=n.nvmlDeviceGetHandleByIndex(0); print(n.nvmlDeviceGetTotalEnergyConsumption(h))"`.
  If it raises `NVMLError_NotSupported`, the meter uses power integration (04.3).
- **1.8.e** Decide **how the CLI gets root** for the cap. Use **one** of these:
  1. run `sudo -E thirst run …`, or
  2. a sudoers entry that allows only `/usr/bin/nvidia-smi` without a password for the lab user (safer: the training script itself never runs as root).

  Option 2 is preferred; record the choice in `AGENTS.md`.
- **1.8.f** Python 3.10+ with `torch` that sees the GPU (`python -c "import torch; print(torch.cuda.is_available())"`), needed for the sweep (04.5).
- **1.8.g** Make sure the box won't sleep overnight (`systemctl mask sleep.target suspend.target` or the desktop power settings) and that `tmux` is installed.

- **1.8.h** Choose the **overnight workload** now (a LoRA fine-tune or a long ResNet run), get it running, and time 10 minutes of it to estimate `--hours` honestly. Moved here from 4.9.a so B isn't doing it at 22:00.

**Done when:** a cap change and a restore both work (or the fallback works), `pynvml` reads energy or power, and `torch.cuda.is_available()` is `True`.

---

## 1.9 Team and admin (lead: leader, 10 min, P0)

- **1.9.a** Every member is registered on the hackathon platform and **joined to the team** (PRD §11). Third member: before submission, no exceptions.
- **1.9.b** Check the schedule page for the **exact deadline time** now, again Sat morning and Sun 08:00 (PRD §11, TRD §15). Put it at the top of `AGENTS.md`.
- **1.9.c** Shared chat channel with three pinned items: the live URL (once it exists), the gates table, and `docs/FIXLIST.md`.
**Done when:** all members show on the team page (screenshot in the chat), and the deadline time is written at the top of `AGENTS.md`.

- **1.9.d** Agree on roles A/B/C (TRD §15). With two people, apply the merge rule from the [index](README.md#1-how-to-read-this-plan).

---

## 1.10 AGENTS.md bootstrap (lead: A, 10 min, P0)

Create `AGENTS.md` at the root with the standard sections (Identity, Stack & Commands, Current State, Architecture, File Map, Conventions, Gotchas, Decisions Log, Changelog). Copy decisions D1 to D26 into the Decisions Log. **Every PR adds one Changelog line.** This is the team's shared memory for humans and AI coding tools.

**G0 check (10:30):** run `make check`, check the CI badge is green, check `sam --version`, check `aws sts get-caller-identity`, check `nvidia-smi`, and check `sample_forecast.json` is committed. Any red item gets its fallback straight away (see the [gates table](README.md#3-milestones-and-gates)).
