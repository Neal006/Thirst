# Phase 05 — Backend and AWS

Owner: **A** · Window: **Fri 09:30 to Sat 12:00** · Gates: **M2** (`/plan` live by 18:00), **M3** (receipts accepted by 22:00), **M4**
Source: TRD §2 (architecture), §7 (API), §8 (data model), §9 (refresh), §10 (agent), §12 (infra and cost).
Region **`ap-south-1`**. Profile `thirst`. Stack name `thirst-dev`.

[← Index](README.md) · Contracts: [08 §3 API](08-reference-contracts.md#3-api-contract), [08 §5 DynamoDB items](08-reference-contracts.md#5-dynamodb-item-shapes), [08 §4 errors](08-reference-contracts.md#4-error-codes)

---

## 5.0 Handler module map

| File | Responsibility |
|---|---|
| `handlers/api.py` | Powertools `APIGatewayHttpResolver` app; routes `/plan`, `/sites`, `/sites/{id}`, `/receipts`, `/leaderboard`, `/assumptions`; `handler = app.resolve` wrapper with a correlation id |
| `handlers/validation.py` | Pure validators per request body (type, range, length, enum). Return a frozen request object or raise `ApiError(400, code, msg)` |
| `handlers/security.py` | `site_token(secret, site_id)`, `verify_signature(token, ts, raw, sig, now)`, `load_secret()` (SSM, cached at cold start) |
| `handlers/store.py` | Repository classes: `WeatherRepo`, `SiteRepo`, `PlanRepo`, `ReceiptRepo`. Float↔Decimal conversion, gzip snapshot, transactions |
| `handlers/errors.py` | `ApiError`, mapping of `EngineError` codes to HTTP statuses, the `{error, message}` envelope (TRD §7) |
| `handlers/refresh.py` | Hourly Open-Meteo pull → weather rows |
| `handlers/explain.py` | Strands agent with template fallback, quota, guardrails |

Rule: handlers stay thin. Business logic lives in `engine`, I/O lives in `store`, and checks live in `validation` and `security`.

---

## 5.1 SAM skeleton and first deploy (60 min, P0, by Fri 11:00)

**Sub-steps**

- **5.1.a** `template.yaml` (TRD §12 outline, filled in):
  - `Parameters`: `Stage` (default `dev`), `AllowedOrigins` (CommaDelimitedList, default `http://localhost:5173`), `BedrockModelId` (String, default empty), `BedrockRegion` (default `ap-south-1`), `ServerSecretParam` (default `/thirst/server_secret`).
  - `Globals.Function`: `Runtime: python3.12`, `Architectures: [arm64]`, `MemorySize: 512`, `Timeout: 10`, `Tracing: Active` (X-Ray free tier), env vars `TABLE_WEATHER`, `TABLE_SITES`, `TABLE_PLANS`, `TABLE_RECEIPTS`, `SERVER_SECRET_PARAM`, `POWERTOOLS_SERVICE_NAME=thirst`, `LOG_LEVEL=INFO`.
  - `HttpApi` (`AWS::Serverless::HttpApi`):
    `CorsConfiguration: { AllowOrigins: !Ref AllowedOrigins, AllowMethods: [GET, POST, OPTIONS], AllowHeaders: [content-type, x-thirst-timestamp, x-thirst-signature, x-thirst-site], MaxAge: 600 }`,
    `DefaultRouteSettings: { ThrottlingRateLimit: 10, ThrottlingBurstLimit: 20 }` (TRD 7.1).
  - `ApiFn`: `CodeUri: src/`, `Handler: handlers.api.handler`, `Events` for each route (`Type: HttpApi`, `ApiId: !Ref HttpApi`). Policies: `DynamoDBCrudPolicy` for the 4 tables (each by name), `SSMParameterReadPolicy: { ParameterName: thirst/server_secret }`, plus `kms:Decrypt` on the AWS-managed SSM key (`alias/aws/ssm`).
  - `RefreshFn`: `CodeUri: src/`, `Handler: handlers.refresh.handler`, `Events: Hourly: { Type: ScheduleV2, Properties: { ScheduleExpression: "rate(1 hour)", RetryPolicy: { MaximumRetryAttempts: 1 } } }`. Policy: `DynamoDBCrudPolicy` on `WeatherTbl` only.
  - `ExplainFn`: `CodeUri: src/`, `Handler: handlers.explain.handler`, `Timeout: 29` (TRD §2), `Layers: [!Ref StrandsLayer]` (D14), route `POST /explain`. Policy: `bedrock:InvokeModel` + `bedrock:InvokeModelWithResponseStream` on the chosen model ARN. With a cross-region inference profile, this means the **profile ARN and the foundation-model ARN in every destination region** of that profile. DynamoDB CRUD on `PlansTbl` (quota counter, D13, plus plan lookup), `DynamoDBReadPolicy` on **`WeatherTbl`** and **`SitesTbl`** (the `make_plan` tool needs weather rows and site defaults), and SSM read is not needed.
  - `StrandsLayer`: `AWS::Serverless::LayerVersion`, `ContentUri: layers/strands/`, `CompatibleRuntimes: [python3.12]`, `CompatibleArchitectures: [arm64]`, `Metadata: { BuildMethod: python3.12, BuildArchitecture: arm64 }`.
  - Tables (5.2) and `LogGroup`s: `AWS::Logs::LogGroup` named `/aws/lambda/${Fn}`, `RetentionInDays: 7`, one per function (TRD §12).
  - `Outputs`: `ApiUrl`, the table names, `StackRegion`.
- **5.1.b** `src/requirements.txt`: `aws-lambda-powertools>=3` only. boto3 comes from the runtime (pin it later only if a feature needs it).
- **5.1.c′** **By Fri 10:45**: hand-write `tests/fixtures/plan_response.json` from the 08 §3.1 example (48 `series` rows, 11 `pareto` entries, plausible numbers, `"tags": {"…": "placeholder"}`). C builds against it until 02.7.k overwrites it with real engine output.
- **5.1.c** A stub `/plan` that returns `tests/fixtures/plan_response.json` (copied into `src/handlers/_stub/`), so the live URL exists before the engine lands.
- **5.1.d** First deploy: `sam build --use-container` (needed so arm64 wheels are right on Windows dev machines; note it in Gotchas), then `sam deploy --guided --profile thirst --region ap-south-1 --stack-name thirst-dev --capabilities CAPABILITY_IAM`. Commit `samconfig.toml` (no secrets in it).
- **5.1.e** Smoke check: `curl -s -X POST "$API/plan" -d '{}' | head -c 200` returns the stub JSON; `curl -I -X OPTIONS "$API/plan" -H "Origin: http://localhost:5173" -H "Access-Control-Request-Method: POST"` shows `access-control-allow-origin`.

**Done when:** the stack is `CREATE_COMPLETE`, `ApiUrl` is posted in the team chat, and the smoke check passes.

---

## 5.2 DynamoDB tables (20 min, P0)

Exactly TRD §8, all `BillingMode: PAY_PER_REQUEST`, `PointInTimeRecoverySpecification` off (cost), `SSESpecification` default (AWS-owned key).

| Logical id | Name | Keys | TTL attribute |
|---|---|---|---|
| `WeatherTbl` | `thirst-${Stage}-weather` | PK `city` (S), SK `hour` (S, ISO IST) | `ttl` (hour + 10 days) |
| `SitesTbl` | `thirst-${Stage}-sites` | PK `site_id` (S) | none |
| `PlansTbl` | `thirst-${Stage}-plans` | PK `plan_id` (S) | `ttl` (submit + 14 days; quota items + 2 days, D13) |
| `ReceiptsTbl` | `thirst-${Stage}-receipts` | PK `site_id` (S), SK `sk` (S) = `end_ts#job_id` or `job#<job_id>` guard (D12) | none |

- **5.2.a** Add `DeletionPolicy: Retain` + `UpdateReplacePolicy: Retain` on `SitesTbl` and `ReceiptsTbl` (real receipts must survive a stack mistake).
- **5.2.b** Receipts are queried by `site_id` with `sk BETWEEN "<from_iso>" AND "<to_iso>~"`. The `job#` guard items sort **after** the ISO timestamps (`j` > `2`), so they never appear in time-range queries. Add a test for this ordering.

**Done when:** `aws dynamodb list-tables --profile thirst` shows the four tables.

---

## 5.3 `store.py` — repository layer (60 min, P0)

**Tests first** (`tests/handlers/test_store.py`, with `moto` `mock_aws`)

1. Round trip for each repo: put → get gives an equal object. Floats survive (stored as `Decimal(str(x))`, read back as `float`).
2. `PlanRepo.put` gzip-compresses `forecast_snapshot` + `pareto` to a `B` (binary) attribute. The item stays < **100 KB** for the default example (the hard DynamoDB limit is 400 KB).
3. `ReceiptRepo.put_with_guard` uses `TransactWriteItems`: the guard item `job#<job_id>` has `ConditionExpression: attribute_not_exists(sk)`. A second put with the same job_id raises `DuplicateJob` → API 409.
4. `ReceiptRepo.last_30_days(site_id, now)` returns only items whose `end_ts` is within the window, never guard items.
5. `WeatherRepo.window(city, from_hour, n=48)` returns rows sorted by hour. `WeatherRepo.observed(city, hours)` returns only rows with `obs_*` fields.
6. `SiteRepo.scan_all()` paginates (`LastEvaluatedKey`) even though the table is small.

**Implement**

- **5.3.a** One `boto3.resource("dynamodb")` per cold start (module level), and table names from env vars.
- **5.3.b** `to_ddb(obj)` / `from_ddb(item)`: recursive Decimal conversion. Reject NaN and Inf (they can't be stored and mean an engine bug) with a 500 error and a clear log line.
- **5.3.d** **Reserved words:** `ttl`, `hour`, `name`, `public` and many others are DynamoDB reserved words. Every `UpdateExpression`, `ConditionExpression` and `KeyConditionExpression` uses `ExpressionAttributeNames` (`#ttl`, `#hour`, `#name`, …). Prefer the boto3 `Key()`/`Attr()` helpers, which do this automatically.
- **5.3.c** Keep repos immutable: methods take and return plain frozen dataclasses or dicts, never shared mutable state.

---

## 5.4 `refresh.py` — hourly weather (45 min, P0)

**Tests first** (`tests/handlers/test_refresh.py`; HTTP mocked with `responses` or a fake `urllib` opener)

1. One multi-location request returns a list of 6 → **future** rows written with `batch_writer` puts. **Past** (observed) rows use one `UpdateItem` per row, because `batch_writer` can't do updates. That's about 6 × 24 calls per hour, fine for a 10 s timeout.
2. Future hours are written as `fc_*` + `fc_issued`; past hours (≤ now) as `obs_*`. Updating an existing row keeps its `fc_*` fields (use `UpdateItem` with `SET obs_temp=…`, not a full put, for observed fields). This is important for the fairness rule: the original forecast must survive.
3. Derived `tw`, `ci`, `ewif` and `pue_inputs` are computed with the engine for each row.
4. Open-Meteo returns 500 or times out → no rows are written, a `WARNING refresh_failed` log line is emitted with the city list, and the function still returns success (the schedule shouldn't hammer the API with retries).
5. `ttl = epoch(hour) + 10 days`.

**Implement**

- **5.4.a** Use stdlib `urllib.request` with a 6 s timeout (no extra dependency).
- **5.4.b** The city list and coordinates come from `engine.factors.load_cities()`.
- **5.4.c** Add a Powertools metric `RefreshRowsWritten` and log `fc_issued`.
- **5.4.d** Run it once manually after deploy: `aws lambda invoke --function-name <RefreshFn> /dev/stdout --profile thirst`, then check the rows in the console.

---

## 5.5 `POST /plan` (60 min, P0, critical path, by 18:00)

**Tests first** (`tests/handlers/test_api_plan.py`, with moto and the engine)

1. A valid body (08 §3.1) → 200 with `plan_id` (`p_` + 10 base32 chars), `submit_ts` set by the **server** (D20), and the full engine output minus `forecast_snapshot` (stored, not returned; it is too big and not needed by the UI).
2. Validation errors (08 §3.1 rules): unknown city → 400 `unknown_city`; `gpu_count` 0 or > 4096 → 400; `work_hours` ≤ 0 or > 48 → 400; deadline in the past → 400 `deadline_in_past`; alpha outside [0, 1] → 400; extra unknown fields are ignored; body > 8 KB → 413.
3. Engine `deadline_too_soon` → 422 with the earliest feasible finish in `message`.
4. Fewer than 48 forecast rows → the engine fills them from the sample and the response has `tags.forecast == "cached"` and a `notes` entry: "Weather data is N hours old; using the last forecast" (TRD §11).
5. `force_now: true` → `chosen == base` (for `thirst run --now`).
6. `pausable_allowed: false` → the response is never pausable, and `notes` says why (D15).
7. (D23) With `site_id`, `city` and `cooling` may be left out; they default from the site, and the plan is linked to the site. Without `site_id`, both are required (400 otherwise). Only plans with a `site_id` can be used for receipts.
8. Latency (PRD §8.1): `scripts/bench_plan.py` sends **1 warm-up + 50 sequential requests to the deployed ApiUrl**, prints p50, p95 and max, and saves them to `docs/bench_plan.txt`. Pass = p95 < 2000 ms.

**Implement**

- **5.5.a** `validation.plan_request(body) -> PlanRequest`.
- **5.5.b** Load the forecast rows `WeatherRepo.window(city, floor_hour(now), 48)` → `engine.planner.plan(req, rows)`.
- **5.5.c** Persist `PlanRepo.put({plan_id, site_id?, submit_ts, inputs, base, best(=chosen), pareto, forecast_snapshot, ttl})`.
- **5.5.d** Response: round numbers at the boundary (kWh to 3 decimals, litres to 1, kg to 2, percentages to integers), and add `assumptions_url`.
- **5.5.e** Error mapping in `errors.py`; never return stack traces.

---

## 5.6 `POST /sites` and `GET /sites/{id}` (45 min, P0)

**Tests first**

1. `POST /sites` with a valid body → 201 `{site_id, token, division}`. The token equals `HMAC_SHA256(secret, site_id)` hex (TRD 7.1). **The token is never stored** (assert the table item has no `token` field).
2. Validation: `name` 3 to 60 characters after trimming, with control characters stripped; `org` ≤ 80; `city` in the seed list; `cooling` enum; `gpu_count` 1 to 100000; `coverage_declared` in [0, 1]; `public` boolean, default true.
3. `GET /sites/{id}` → 200 with the 08 §3.3 shape: score parts, badge, Provisional tag, last 10 receipts, monthly absolute footprint, division (no exact GPU count in the public response).
4. Unknown id → 404 `site_not_found`. A malformed id (not matching `^s_[a-z2-7]{10}$`) → 400.
5. A site with zero receipts → `score: null, reason: "needs_flexible_receipt"` (D10).

**Implement**

- **5.6.a** `site_id = "s_" + base32(secrets.token_bytes(7))[:10].lower()`.
- **5.6.b** `division` from `engine.score.division(gpu_count)` is stored, and recomputed on read if the thresholds change.
- **5.6.c** `GET` computes the score on read from the last 30 days of receipts (engine `site_score`), with a **20 s** in-memory cache keyed by site_id, and the response header `Cache-Control: no-store`. Several warm Lambda instances each keep their own cache, so a 60 s TTL plus browser caching could break "on the board within 1 minute" (PRD §6.2.7).

---

## 5.7 `POST /receipts` (90 min, P0, security-critical, by 22:00)

**Tests first** (`tests/handlers/test_api_receipts.py`)

1. **Signature (TRD §14):** a valid signature → 200; one changed byte in the body → 401 `bad_signature`; a timestamp 601 s old or 601 s in the future → 401 `stale_timestamp`; a missing header → 401; the shared vectors from `tests/vectors/hmac.json` pass.
2. **Base64 body (D21):** the same request with `isBase64Encoded: true` and a base64 body verifies the same way.
3. **Plausibility (TRD 7.1):** `Σ kWh > gpu_count × P_max_kW × hours × 1.1` → 422 `implausible_energy`. The hours come from `end_ts − start_ts`.
4. **Ownership:** a `plan_id` linked to another site → 403 `plan_site_mismatch`. A missing plan (TTL expired or unknown) → 404 `plan_not_found`.
5. **Duplicate:** the same `job_id` again → 409 `duplicate_job` (D12).
6. **Slots:** any slot hour outside `[floor_hour(start_ts), end_ts]`, or `start_ts < floor_hour(plan.submit_ts)` → 422 `slot_out_of_range`. Hours past the 48-slot snapshot are allowed and scored as `extrapolated` (02.8.b); more than 72 slots → 422; negative kWh → 400; `level` not in {1.0, 0.85, 0.7} → 400.
7. **Scoring:** the response contains `scoring`, `absolute`, `capture` (or `no_room: true`), `tags` (`energy: measured` if the method is NVML, else `modelled`), and the updated site score summary.
8. **Unverified** (D20): the receipt is stored but has `scored: false` and doesn't change the site score.
9. Leaderboard and site caches are invalidated for that site after a successful write.

**Implement**

- **5.7.a** Order of checks (cheapest first, and **verify before parsing JSON**): header presence → timestamp skew → read the raw body (decode base64 if needed) → look up the site (404 if unknown) → recompute the token → `hmac.compare_digest` the signature → parse JSON → validate → plan ownership → plausibility → score → transact write.
- **5.7.b** Scoring: `engine.score.receipt_footprints(receipt, plan_record, WeatherRepo.observed(city, hours))`.
- **5.7.c** Store the receipt item (08 §5.4) and the guard in one transaction. **Normalise `end_ts`** to the canonical `YYYY-MM-DDTHH:MM:SS+05:30` (converting `Z` and other offsets to IST) before building `sk`, so the `BETWEEN` range queries sort correctly. Add a test that posts a `Z` timestamp. The guard item also stores `sk_receipt` (the receipt's full sort key) so that 5.7.e can find the receipt with one read.
- **5.7.e** `GET /receipts/{site_id}/{job_id}` (D24): `GetItem` on the guard → `GetItem` on `sk_receipt` → return the 08 §3.4 response shape. 404 `receipt_not_found`; private sites (D26) → 404. Route it on `ApiFn`. `make fixtures` writes `tests/fixtures/receipt_response.json` for the Receipt page.
- **5.7.d** Log `site_id`, `job_id`, kWh total, capture and latency. **Never log the token or the signature.**

---

## 5.8 `GET /leaderboard` and `GET /assumptions` (45 min, P0)

**Tests first**

1. `division` defaults to `D1`; an invalid value → 400. `period` only `30d` in v0; `board` only `score` (P1 adds `improved`, `basin`).
2. Rows: rank, site name, `simulated` chip flag, badge, score (or "Not rated yet"), A and C parts, flexible share, monthly absolute footprint (kWh, litres, kg CO₂, person-days), receipts count. **No GPU count.**
3. Sites in other divisions are excluded; simulated sites are included and flagged; **private sites (`public: false`) are left off the board** (D26). `GET /sites/{id}` for a private site returns only name, division and score.
4. The in-Lambda cache is **20 s** per `(division, period, board)`; a test with a frozen clock shows the cache hit and the expiry. The response has `Cache-Control: no-store`.
5. `/assumptions` returns `engine.factors.table()` plus **`gpus: [{id, label, p_max_w, p_idle_w, sweep_status}]` from `gpus.json`** (the form's GPU list, 06.2.a), the stress weights, the city list and the data source list, with `Cache-Control: max-age=300`.

**Implement**

- **5.8.a** Leaderboard: scan `sites` (small), then query receipts for the last 30 days per site in that division, then `engine.score.leaderboard_rows`. The scans are fine at this size (TRD §8); note "materialised board" as a v1 task.
- **5.8.b** The leaderboard and site responses are `no-store` (5.6.c). The worst-case staleness is the 20 s Lambda cache.

---

## 5.9 `POST /explain` — Strands agent (P1, Sat 09:00 to 12:00)

Only after M4 passes. The **template stays the default** (TRD §10, PRD F12).

**Tests first** (`tests/handlers/test_explain.py`, with the Bedrock model mocked)

1. `{plan_id}` → returns `explain_template(plan)` with `source: "template"` when `BEDROCK_MODEL_ID` is empty.
2. `{text}` longer than 500 characters → 400 `text_too_long` (TRD §10 guardrail).
3. The quota (D13): the 301st call of the day → `source: "template"` with the note `daily_limit`.
4. Agent timeout (> 20 s, enforced with `concurrent.futures` around the agent call) or any exception → template fallback, logged.
5. **Prompt-injection hardening:** tool arguments from the model go through the **same** `validation.plan_request` as the API, so an invalid city or count is rejected, not passed to the engine. The model output is returned as **plain text** only (React escapes it). The system prompt says: only explain, never invent numbers, always say which numbers are modelled.
6. The form extraction for "LoRA on 2 × 4090, 6 hours, need it by 9 AM, can pause, Chennai lab with AC" gives `{gpu_model: RTX-4090, gpu_count: 2, work_hours: 6, deadline: next 09:00, pausable: true, city: Chennai, cooling: room_ac}` (a recorded-response test).

**Implement**

- **5.9.a** `layers/strands/requirements.txt`: `strands-agents` (pin the exact version that installs on Fri).
- **5.9.b** `explain.py` follows TRD §10, **except** that the TRD snippet's positional `planner.plan(city, …)` call doesn't match the engine API. The `make_plan` tool builds the request with `validation.plan_request(args)`, loads rows with `WeatherRepo.window(...)`, then calls `planner.plan(req, rows)`. Tools `make_plan`, `get_assumptions`; `BedrockModel(model_id=os.environ["BEDROCK_MODEL_ID"], region_name=os.environ["BEDROCK_REGION"], max_tokens=1000)`.
- **5.9.c** Quota: `UpdateItem` on `PlansTbl` `PK=quota#YYYY-MM-DD` with `ADD n :1`, `ConditionExpression: attribute_not_exists(n) OR n < :300`.
- **5.9.d** If the model is only available in `us-east-1`, set `BedrockRegion=us-east-1` or use a cross-region inference profile id; the function itself stays in `ap-south-1` (TRD §2).

---

## 5.10 Seed data (45 min, P0, Fri 18:00 to 22:00)

- **5.10.a** `scripts/seed.py --profile thirst --stage dev` writes directly to DynamoDB (admin credentials, not through the API):
  - the team's **real lab** site (non-simulated; the token is printed once for B's CLI config);
  - **8 simulated sites** named like `"Demo Lab, Chennai (simulated)"`, `"Demo Cluster, Hyderabad (simulated)"`, spread over D1 (5), D2 (2) and D3 (1), with `simulated = true` (TRD §8). **Never use real company names** (Idea §12).
- **5.10.b** For each simulated site, generate 10 to 40 receipts over the last 30 days with the **engine**, using the real weather from the `weather` table (or the sample) and a behaviour profile per site ("always starts now", "follows the plan", "follows 70%", "caps only"). That gives a believable spread of Capture values and scores. `method = "modelled"`.
- **5.10.c** Idempotent: fixed site ids (`s_sim000001`…). Re-running replaces their receipts (delete, then write).
- **5.10.d** `--wipe-simulated` removes only `simulated = true` sites and their receipts. **Never** touch non-simulated data. Re-seed afterwards, or the demo board is empty.
- **5.10.e** `--delete-site <site_id>` deletes one site and its receipts and guard items. It **refuses** ids starting with `s_sim` (the seeded demo sites). Use it for test sites from 7.1.d and 7.6, which are created through `POST /sites` and so can't be marked simulated.

**Done when:** `GET /leaderboard?division=D1` shows 5 or more rows with the Simulated chip and varied scores.

---

## 5.11 Security, cost and ops hardening (45 min, P0, Fri evening)

- **5.11.a** `ecc:security-reviewer` on `handlers/security.py`, `api.py` (receipts and sites), `explain.py`. Checklist: constant-time compare; skew window; replay (the timestamp window plus the job_id guard together stop replays); no secrets in logs or responses; strict input validation; CORS has no `*`; throttling is on; body size limits; IAM is least-privilege (no `*` resources except where AWS requires them).
- **5.11.b** Update the CORS origins once the Amplify domain exists (06.9): `sam deploy --parameter-overrides AllowedOrigins="https://main.<id>.amplifyapp.com,http://localhost:5173"`.
- **5.11.c** CloudWatch: one alarm on `ApiFn` `Errors ≥ 5 in 5 min` → the SNS topic emailing the team (free tier).
- **5.11.d** Cost check (TRD §12 "Daily check"): Billing → Cost Explorer every morning; spend over **$5 by Sat 21:00** means stop and find out what is costing money (D4).
- **5.11.e** Confirm that **nothing on the never-create list** exists: `aws ec2 describe-instances`, `aws sagemaker list-endpoints`, `aws rds describe-db-instances` all return empty.

---

## 5.12 Deploy routine (all of A's deploys)

```bash
make check                                   # tests green first
sam validate --lint
sam build --use-container
sam deploy --profile thirst                  # uses samconfig.toml
bash scripts/smoke.sh "$API"                 # /assumptions 200, /plan 200, /leaderboard 200, OPTIONS CORS ok
```

`scripts/smoke.sh` exits non-zero on any failure. Post the result in the chat after every deploy.
