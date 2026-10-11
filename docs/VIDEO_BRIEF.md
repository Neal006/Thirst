# Thirst demo video: the brief (A to Z)

> **Who this is for.** Whoever records and edits the 3-minute submission video (Neal), or any AI assistant helping with it.
> - It explains **what** the video must achieve, **what must be shown**, **what must be said**, and the rules.
> - The exact second-by-second script, with every spoken line, every click and the captions, is in [`VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md).
> - Read this first, then record from the script.
>
> **If you paste this into an AI tool**, add: *"Use this brief and VIDEO_SCRIPT.md. Don't invent features or numbers that aren't listed here. Keep the video under 3:00."*

---

## 1. What we are making

| | |
|---|---|
| Length | **2:50 to 2:58. Never 3:00 or more** (check the exported file's duration). |
| Format | 1920 × 1080, 30 fps, H.264, with burned-in or uploaded captions |
| Where | YouTube, **unlisted**, and it must play in a signed-out private window |
| Audience | Hackathon judges (WeMakeDevs × AWS Environmental Hacks, Track 02 Heat & Water). They watch many videos, often muted. |
| One-line story | *Every GPU hour drinks water twice. Thirst picks **when** and **how fast** to run your job, then proves the saving with a receipt.* |
| Tone | Calm, concrete, honest. Show the product working; no hype words ("revolutionary", "AI-powered magic"). |

## 2. Hard rules (from the hackathon and our own honesty rules)

1. **AWS on screen and named out loud.** Show the AWS console, and say each service: Amplify, API Gateway, Lambda, DynamoDB, EventBridge Scheduler, Bedrock, Strands Agents SDK, SAM.
2. **Under 3:00.**
3. **Captions on**, because judges may watch muted.
4. **Never show** tokens, `config.toml`, the AWS account id or account name, or billing pages with personal data. Blur them if they appear.
5. **Numbers are ranges, never single litre figures.** Say "about 18 to 20 percent", not "saves 4 litres".
6. **Say the labels.** Water and CO₂ are *modelled*. GPU energy is *measured* (or *modelled* on a laptop). Demo labs are *simulated*. The power-cap curve is a *placeholder*.
7. **Don't show the water/carbon slider.** With today's placeholder data every option gives the same plan, and the page says so honestly; it's just not a good shot.
8. **Bedrock:** the explainer is wired in, but model access on our AWS account is still pending. Say "wired in, waiting on model access". Show the code, not a fake answer.

## 3. Features the video must show (checklist)

Every row must appear on screen. The "Shot" column points to [`VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md).

| # | Feature | What the viewer must see | What the speaker must get across | Shot |
|---|---|---|---|---|
| 1 | **The problem** | Home page headline "Every GPU hour drinks water twice." | Water is used at the building and at the power plant; Indian cities are water-stressed | 1 |
| 2 | **Live water clock** | 24-hour dial, amber RUN arc, the city switch redrawing it | It's today's live forecast; some hours are thirstier; Thirst finds the best window | 2 |
| 3 | **Start now vs plan** | Two beakers; the cooling-tower toggle adding building water | Same job, two start times; a cooling tower "drinks twice" | 2 |
| 4 | **Speed knob (power cap)** | 100% / 85% / 70% switch; time up, energy down | Slowing the GPU a little is a *real cut*, not just a shift | 3 |
| 5 | **One-click plan** | Quick pick → Plan → result card in about a second | When to start, how fast, when it ends | 4 |
| 6 | **Why this time** | The one-line reason under the plan | The plan explains itself | 4 |
| 7 | **Honest numbers** | Savings shown as ranges with `modelled` chips | Ranges and labels, never a single figure | 4 |
| 8 | **Four plan views** | Timetable, Hourly, Calendar, Chart tabs | Read the next 48 hours the way you like | 4 |
| 9 | **Run this plan** | Copy the command, Add to calendar (.ics), Copy share link, Recent plans | Act on the plan in one click, or hand it to a labmate | 5 |
| 10 | **Compare cities** | /cities: six city cards with best start, 48 h strip, water, Plan here | The same job in six Indian cities | 6 |
| 11 | **CLI** | `pip install thirst`, `thirst doctor`, `thirst run …`, then the receipt | One package; it waits for the right hour, caps the GPU and **always restores the limit** | 7 |
| 12 | **Signed receipt** | The receipt block: energy, saved %, capture %, site score | Energy measured (or modelled), water and CO₂ modelled; signed | 7 |
| 13 | **Fair leaderboard** | Weight-class tabs, medal rows, "(simulated)" labels | Score the *choice*, not the climate; small labs compete with small labs | 8 |
| 14 | **Lab page** | Score ring, badge ladder | A 0–100 score, a badge, the points to the next one | 8 |
| 15 | **AWS architecture** | Diagram + console: CloudFormation stack, Lambda, DynamoDB, EventBridge schedule, Amplify; `explain.py`; the green Deploy + e2e run | Serverless on AWS; every service named; deploys from GitHub with no stored keys | 9 |
| 16 | **Transparency** | Assumptions page: "How sure we are" bar, a `placeholder` chip, "Words we use" glossary | Every number wears a label; we say what's still a placeholder | 10 |
| 17 | **Close** | End card: name, site URL, `pip install thirst`, repo | Run at the right hour and the right speed, and prove it | 11 |

Optional, only if there's time:
- the phone layout (resize the window)
- forecast freshness ("Forecast updated N hours ago")
- the share link reopening a plan in a new tab

## 4. The story, A to Z (what's said, what's seen)

Use this as the outline. The exact words are in the script.

| Part | Time | Seen on screen | Said (the gist) |
|---|---|---|---|
| **A. Hook** | 0:00–0:12 | Home page headline and meters | Every GPU hour drinks water twice, and in Chennai that water is scarce |
| **B. See it** | 0:12–0:30 | Water clock, city switch, beakers, cooling-tower toggle | Thirst makes it visible: live forecast, thirsty hours, the best window |
| **C. The second lever** | 0:30–0:42 | Power-cap switch | Running a bit slower is a real energy cut |
| **D. Plan it** | 0:42–1:10 | Quick pick → plan card → why line → ranges → 4 view tabs | One click gives when, how fast and when it ends, with the reason and honest ranges |
| **E. Act on it** | 1:10–1:24 | Run this plan: copy, calendar, share, recent | Copy the command, add it to your calendar, share it |
| **F. Compare** | 1:24–1:36 | Cities page | The same job across six cities |
| **G. Run it** | 1:36–2:02 | Terminal: install, doctor, run, receipt | One package; it waits, caps, always restores, and gives a signed receipt |
| **H. Get rated** | 2:02–2:20 | Leaderboard → lab page | A fair score in weight classes; demo labs are simulated |
| **I. Built on AWS** | 2:20–2:44 | Diagram + console + code + green deploy | Each service named; serverless; no stored keys |
| **J. Honesty** | 2:44–2:54 | Assumptions page | Every number labelled; placeholders admitted |
| **K. Close** | 2:54–2:58 | End card | Run at the right hour and the right speed, and prove it |

## 5. Facts you may say (all checked on 11 Oct 2026)

- **Website:** https://main.dzxkrtlc7xqfx.amplifyapp.com
- **CLI:** `pip install thirst` (version 0.3.2). Python 3.10+, and 42 GPU models are recognised, including laptop GPUs.
- **Planner speed:** a plan comes back in about a second. Measured: p95 383 ms over 50 live calls.
- **Today's plans:** 70% GPU power, with about 18–20% less water and CO₂ and 20–21% less energy than starting right away. These are **modelled** ranges, and most of the saving comes from the power cap, whose curve is a **placeholder**.
- **Scoring:** a lab with one plan-following receipt scores about 78.5, **Gold (Provisional)**.
- **Weight classes:**
  - D1: up to 16 GPUs
  - D2: 17–256
  - D3: 257–4,096
  - D4: above that
- **Factors:** 57 in total, made up of 30 design choices, 18 placeholders, 8 sourced and 1 calibrated.
- **AWS:** Amplify, API Gateway (HTTP API), Lambda (arm64, Python 3.12), DynamoDB (4 tables), EventBridge Scheduler (hourly), Bedrock + Strands Agents SDK (wired in, access pending), SAM, CloudWatch alarms, and GitHub Actions with OIDC (no stored keys).
- **Cost so far:** $0.00 for the month.

**Never say** any of these:
- a single litre figure
- "measured" for water or CO₂
- that the AI makes the decisions (the solver decides; AI only explains)
- that it "reverses" water use
- that the demo labs are real

## 6. Before you record (summary; details in the script §1)

1. Chrome at 1920 × 1080 and 110% zoom, clean profile, with the 14 tabs from the script open and warmed up.
2. Terminal at font 18+, with `pip install -U thirst` done (0.3.2), `THIRST_HOME` set to a temp folder, and a public demo lab registered off camera.
3. Pre-record the `thirst run` receipt. Check `thirst plan` first: in the evening the plan may start tomorrow and the run will wait for hours.
4. Record the voice separately in a quiet room.
5. After the shoot, send the demo lab's `s_...` id to a maintainer for deletion.

## 7. Deliverables

1. The exported MP4 (< 3:00).
2. The YouTube **unlisted** link, tested signed out.
3. The link added to `docs/WRITEUP.md` (top table), the README, and the submission form.
4. The captions file (`.srt`). It's in the script §5, adjusted if any line changed.

## 8. Final check

Go through the checklist at the end of [`VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md) §6. Every row of §3 above must be ticked.
