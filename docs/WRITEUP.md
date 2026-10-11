# Thirst: water and carbon receipts for GPU jobs in India

**Environmental Hacks (WeMakeDevs × AWS) · Track 02 Heat & Water · team hello_world**

| | |
|---|---|
| Live site | https://main.dzxkrtlc7xqfx.amplifyapp.com |
| API | https://l6y3i40hh4.execute-api.ap-south-1.amazonaws.com |
| CLI | `pip install thirst` ([PyPI](https://pypi.org/project/thirst/), 0.3.2) |
| Score rules · every factor | [`SPEC.md`](../SPEC.md) · [`ASSUMPTIONS.md`](../ASSUMPTIONS.md) |
| Try it yourself | [`docs/USER_TEST_GUIDE.md`](USER_TEST_GUIDE.md) |
| Code | https://github.com/Neal006/Thirst (MIT) |
| Video | _add the unlisted YouTube link_ |
| Blog | _add the Builder Center link_ |

Every number below is a range or carries its label (measured, modelled, sourced, calibrated, placeholder), the same way the app shows it.

---

## 1. The problem

A GPU job uses electricity, and in India that electricity uses water twice:

- **At the building.** Cooling towers evaporate water, and room ACs work harder in hot hours.
- **At the power plant.** Most Indian power is coal, and Indian rules let an older coal unit with a cooling tower consume up to 3.5 litres per kWh (MoEFCC, _sourced_).

Mumbai and Chennai are India's two biggest data-centre hubs, and both are water-stressed cities. Yet a student who starts a 6-hour training run sees the loss curve, not the water or the CO₂. Nothing tells them the cost, and nothing rewards them for doing better.

## 2. What we built

A loop of **plan → run → receipt → rating**:

1. **Plan** (web or `thirst plan`). You give the GPU model, the GPU count, the hours of work, a deadline, the city and the cooling type. A deterministic solver picks the start hour, any pauses, and the GPU power cap that cut stress-weighted water and CO₂ while still meeting the deadline. It returns the plan plus an 11-point water-vs-carbon trade-off (Pareto front) behind a slider.
2. **Run** (`thirst run -- python train.py`). The CLI waits for the planned hour, lowers the GPU power limit through NVML, and runs the command. It pauses and resumes the command (SIGSTOP/SIGCONT) when the plan says so.
   - The power limit always comes back: at the end, on Ctrl-C, on a dropped SSH session, and after a crash. A restore marker file covers reboots.
3. **Receipt.** GPU energy is **measured** from NVML each hour. Water and CO₂ are **modelled** from that energy and that hour's weather and grid mix, and set against "if you had started right away". The receipt is HMAC-signed and saved on disk before it is sent. If the network is down it waits for `thirst sync`.
4. **Rating.** A 0–100 site score asks: *of the saving that was possible for this job, how much did you take?* It scores the choice, not the climate. Labs compete in weight classes (D1 ≤ 16 GPUs, up to D4 hyperscale), so a 4-GPU college lab never faces a data centre.

On the website:
- **Home page:** a 24-hour "water clock" for your city, start-now vs plan beakers split into building and power-plant water, and a power-cap switch.
- **Planner page:** the plan card with a "why this time" line, the next 48 hours as a timetable, hourly list, calendar or chart, and a "Run this plan" box that copies the exact `thirst run` command, adds the run to a calendar or shares a link to the same job. The Pareto slider appears when the 11 options differ.
- **Cities page:** the same job in six cities, so a lab can see where and when is cleanest.
- **Leaderboard and lab score pages:** the weight classes and each lab's score and badge.
- **Assumptions page:** a short glossary, then every one of the 57 factors with its value, range, status and source.

## 3. Where AWS fits

| Service | What it does in Thirst | Why this service |
|---|---|---|
| **AWS Lambda** (arm64, Python 3.12) | Three functions: `api` (planner, receipts, scores), `refresh` (hourly weather), `explain` (plain-words explanation) | The planner is pure Python and finishes in about 50 ms. Pay per request, nothing idles over a weekend. |
| **Amazon API Gateway** (HTTP API) | Public API with CORS and throttling (200 req/s, burst 400) | Cheapest front door for Lambda. Throttling protects the account during judging. |
| **Amazon DynamoDB** (4 tables, on-demand) | Weather snapshots, sites, plans (with TTL), receipts | Key-value access only. TTL clears anonymous plans after 2 h. Conditional writes stop duplicate receipts. |
| **Amazon EventBridge Scheduler** | Calls `refresh` every hour | A managed cron with retries. A failed refresh raises an alarm. |
| **AWS Amplify Hosting** | Serves the React site | Static hosting with HTTPS and a CDN. Deployed as a zip from CI. |
| **Amazon Bedrock + Strands Agents SDK** | Optional `explain` agent that turns a plan into three plain sentences, with tool access to the planner | The solver decides and the AI only explains. Any answer with a number not found in the plan facts is rejected and replaced by a template (decision D33). |
| **AWS SAM** | Infrastructure as code for the whole stack (`template.yaml`) | One `sam deploy`. The template is cross-checked against the code's table specs in tests. |
| **CloudWatch + SNS** | Alarms on Lambda errors, API 5xx and refresh failures, sent by email | We find out before the judges do. |
| **SSM Parameter Store** | The server secret for signing site tokens | No secret in code or in GitHub. |
| **IAM OIDC for GitHub Actions** | CI deploys with a role only `main` can assume | No AWS keys stored in GitHub. |
| **AWS Budgets** | $50 monthly budget, alerts at 10/20/50/100% and on the forecast | The cost guard, since we chose not to rate-limit judges. Spend this month so far: $0.00. |

There are no servers, no GPUs on AWS, no NAT gateway and no provisioned concurrency. The GPU work runs on the lab's own machine.

**Performance.** 50 live `POST /plan` calls: p50 219 ms, p95 383 ms, 0 failures (`docs/bench_plan.txt`, measured 2026-10-11).

## 4. Measured, modelled, and the limits we say out loud

| Part | Status |
|---|---|
| GPU energy on a receipt | **Measured** with NVML on the user's machine, or **modelled** with `--modelled`, and the receipt says which |
| Hourly weather (temperature, humidity, radiation) | **Live** from Open-Meteo, refreshed hourly |
| Building water and AC energy by hour | **Modelled** from wet-bulb temperature, PUE/WUE and AC COP |
| Grid CO₂ | **Calibrated** so the yearly average matches CEA's 0.727 kg CO₂/kWh (±15%) |
| Coal water limits, city norms, water-stress categories | **Sourced** (MoEFCC, CPHEEO, WRI Aqueduct) |
| Power-cap trade-off (speed and energy at 70/85/100%) | **Placeholder** until our own GPU sweep is measured |

Status mix on the live Assumptions page: 30 design choices, 18 placeholders, 8 sourced, 1 calibrated. The same table is generated into [`ASSUMPTIONS.md`](../ASSUMPTIONS.md).

**What this means for the numbers today.** A live plan on 2026-10-11 for 2 × RTX 4090, 6 hours of work, in Chennai, Delhi or Bengaluru picked the 70% power cap. Against starting right away, it showed:

| | Range | Label |
|---|---|---|
| Water | 18 to 19% less | modelled |
| CO₂ | 18 to 19% less | modelled |
| GPU energy | 20 to 21% less | modelled |

Almost all of that comes from the power cap, and the cap's speed/energy curve is a placeholder. Until our sweep replaces it:
- Every plan picks 70%.
- All 11 trade-off points are the same, so the planner hides the water-vs-carbon slider and says why.

We show this on screen (`tau: placeholder` tags) instead of hiding it.

**Other limits:**
- Time-shifting is mostly a *shift*, not a cut. The marginal plant in India is often coal at any hour. We use the average grid mix per hour, like CEA and the CSEP tracker, and say so.
- A pausable plan uses only each hour's cheapest power level. A tight deadline can force a fallback to a non-pausable plan, and the plan notes it.
- Multi-GPU distributed jobs (`torchrun`, DeepSpeed, MPI) and Windows run without pauses, and the CLI says so.
- The leaderboard holds 8 **simulated** demo labs, labelled "(simulated)". A real overnight receipt from our own GPU is still to come.
- Bedrock model access is not yet enabled on our account, so `/explain` serves the template explanation today (`source: template`). The agent code is deployed and switches on with one setting.
- We never claim to "reverse" water use. Savings are always ranges, never a single number of litres.

## 5. Quality

All of these run in CI on every PR (`.github/workflows/ci.yml`):

| Area | Coverage |
|---|---|
| Engine | ~317 tests, 99% coverage; property tests for deadlines |
| Handlers | ~520 tests, end to end on moto |
| CLI | ~440 tests, POSIX signal tests run on Linux |
| Web | ~510 Vitest tests, including a DOM scan that fails any bare number without a label |
| Static checks | `ruff`, strict `mypy`, `oxlint` |
| Template | `sam validate --lint` |
| Secrets | gitleaks scan |

Separately, the Playwright suite runs against the live site:
- **Coverage:** desktop and a 360 px phone, with axe accessibility checks.
- **Safety:** a read-only guard blocks every request except GET and `POST /plan`.
- **First run:** found contrast, list-markup and tap-target bugs, now fixed.
- **After the last deploy, against the live site:** 74 passed, 4 skipped (data-dependent), and 1 flaky test that passed 12/12 on re-run.

We also ran the whole user journey by hand from a fresh `pip install thirst`: register, plan, run, receipt, then the site and leaderboard pages ([`USER_TEST_GUIDE.md`](USER_TEST_GUIDE.md)). The CLI is released to PyPI by GitHub Actions with PyPI Trusted Publishing, so no PyPI token is stored anywhere.

## 6. AI tools used

- **Claude Code** (Anthropic; Claude Opus and Claude Sonnet models) was our coding assistant throughout:
  - It turned the PRD/TRD into a phased implementation plan.
  - It wrote code and tests test-first.
  - It reviewed its own diffs (security, Python and React reviews).
  - It set up AWS (SAM deploy, OIDC role, budgets) and CI.
  - Commits it helped write carry a `Co-Authored-By: Claude …` trailer.
- **Amazon Bedrock via the Strands Agents SDK** is the in-product AI (explanations only, guarded against invented numbers, see §3).

The team made the product decisions: the idea, the science choices, the score design, the honesty rules and the trade-offs in §4. Every AI-written change went through tests and CI before merging.

## 7. Credits

Weather by Open-Meteo (CC BY 4.0) · grid CO₂ factor from CEA · coal water limits from MoEFCC · water stress from WRI Aqueduct · city water norm from CPHEEO · national generation mix from the CSEP Electricity and Carbon Tracker · Recharts, nvidia-ml-py, AWS Lambda Powertools, Strands Agents.
