# Demo video script (target 2:55, hard limit < 3:00)

This is the shot-by-shot script for the version after PR #15, which brought the Monsoon design, plan views, the "Run this plan" card, the Cities page and CLI 0.3.2.
- **The why** (goals, rules, the feature checklist): [`VIDEO_BRIEF.md`](VIDEO_BRIEF.md).
- **This file:** the exact screen, action and spoken line for every second.

**Rules from the hackathon and plan 7.8:**
- Under 3:00 by the exported file's length.
- Uploaded to YouTube as **unlisted**, and it plays signed out.
- AWS **on screen and named out loud**.
- Captions on, because judges may watch muted.
- Never show tokens, `config.toml`, the AWS account id, or billing pages with personal details.

**How the timing works.** The voice-over is about 420 words, which is about 2:48 at a calm 150 words a minute. If a take runs long, cut the *italic* phrases first.

**Honesty rules for the voice:**
- Say "about", "ranges", "modelled" and "simulated" exactly where the script does.
- Never say a single litre figure.
- Never say "measured" over a modelled receipt.
- Don't show the water/carbon slider. Today every option gives the same plan, and the page says so.

---

## 1. Before recording (30 min)

### Browser (Chrome, a clean profile, no extensions or bookmarks bar)
1. Set the window to 1920 × 1080, page zoom 110%, and light mode.
2. Open these tabs, in this order. Load each once so nothing is still loading on camera.
   1. https://main.dzxkrtlc7xqfx.amplifyapp.com/ (home), with **Chennai** selected
   2. https://main.dzxkrtlc7xqfx.amplifyapp.com/plan?city=Chennai (planner, empty form)
   3. https://main.dzxkrtlc7xqfx.amplifyapp.com/cities
   4. https://main.dzxkrtlc7xqfx.amplifyapp.com/leaderboard
   5. https://main.dzxkrtlc7xqfx.amplifyapp.com/sites/s_simaaaaaaa (Demo Lab, Chennai, Gold)
   6. https://main.dzxkrtlc7xqfx.amplifyapp.com/assumptions
   7. GitHub README "Built on AWS" diagram: https://github.com/Neal006/Thirst#built-on-aws
   8. AWS console, region **Asia Pacific (Mumbai) ap-south-1**: CloudFormation → stack `thirst-dev` → **Resources**
   9. AWS console → Lambda → Functions (filter `thirst-dev`)
   10. AWS console → DynamoDB → Tables (filter `thirst-dev`)
   11. AWS console → EventBridge → Schedules (`RefreshFnHourly`, `rate(1 hour)`)
   12. AWS console → Amplify → app `dzxkrtlc7xqfx`
   13. GitHub → `src/handlers/explain.py`, scrolled to `def _invents_numbers` (about line 232)
   14. GitHub → Actions → the latest green **Deploy** run (it has two green jobs: `deploy` and `e2e`)
3. Do one practice run on the planner tab: press **Overnight fine-tune**, then **Plan**, so the API is warm. Then reload the tab so the form is empty again.
4. Clear the planner's **Recent** list if it holds old test jobs (DevTools → Application → Local Storage → delete the Thirst key), or leave one entry to show.
5. Don't open the AWS account menu (top right). Blur the account name and any ARN containing the account id in the edit.

### Terminal (Windows Terminal or any terminal with a big font)
1. Use font size 18+, high contrast, about 100 × 30 characters, and a short prompt such as `$ `.
2. Install the CLI: `pip install -U thirst`, then check `thirst --version` says **0.3.2**.
3. Point Thirst at a throwaway folder so your real config never appears on screen:
   - PowerShell: `$env:THIRST_HOME="$env:TEMP\thirst-demo"`
   - bash: `export THIRST_HOME=/tmp/thirst-demo`
4. Off camera, register once. Use a public lab, so the receipt has a link you can open:
   ```
   thirst register --name "Demo Recording Lab" --city Chennai --cooling room_ac --gpus 1
   ```
   After the shoot, send the `s_...` id to a maintainer so the lab is deleted (`scripts/seed.py --delete-site <id>`).
5. **Pre-record the run (shot 7B).** Record it separately and speed it up in the edit.
   - **Check the plan first:** `thirst plan --hours 0.05 --deadline "<tomorrow> 09:00"`.
     - If it says `start` within the hour (usually late morning to mid-afternoon), run the job now.
     - If it starts tomorrow (usually evenings), `thirst run` will wait for hours. Either film the real countdown line ("Waiting for the planned start: starts in 9 h 20 min") as its own shot and record the receipt at a time the plan starts at once, or record the whole run at midday.
   - **Best:** a Linux desktop with an NVIDIA GPU and a 1-hour job. It gives a `measured` receipt with a real cap.
   - **Fallback (any laptop), a modelled receipt.** Tested 11 Oct with 0.3.2:
     ```
     thirst run --modelled --hours 0.05 --deadline "<tomorrow> 09:00" -- python -c "import time; print('training...', flush=True); time.sleep(150); print('done', flush=True)"
     ```
     - **Expected output:** `Plan: start …, cap 70%`, then `training...`, `done`, then the receipt.
     - **Receipt lines to show:** "modelled at 70% (plan level)", energy in Wh, "Saved 20% water and 20% CO2", "You took 100% of the possible saving", "Site score 78.5 gold (Provisional)".
     - **Voice-over:** say **"modelled"** (shot 7B gives the line).
6. Run `clear` before each terminal shot.

### Audio
- Record the voice separately: phone voice memo in a quiet room, or OBS mic only.
- Read the script twice before recording.

---

## 2. Shot list

| # | Time | Screen | Action on screen | Voice-over (read exactly) | Caption |
|---|---|---|---|---|---|
| 1 | **0:00–0:12** | Tab 1, home page, top | Hold on the headline **"Every GPU hour drinks water twice."** At 0:07 move the mouse slowly over the two meters ("Water, best vs worst hour", "CO₂, best vs worst hour"). | "Every hour a GPU trains a model, it drinks water twice: at the building that cools it, and at the power plant that feeds it. In Chennai, that water is already scarce." | Every GPU hour drinks water twice |
| 2 | **0:12–0:30** | Tab 1, water clock, then beakers | 0:12 hover the amber **RUN** arc and the **Best start** label. 0:17 switch the city Chennai → Delhi → back to Chennai. 0:23 scroll to the beakers and click **Data centre · cooling tower**. | "Thirst makes it visible. This dial is Chennai's next twenty-four hours from today's live forecast. Longer wedges are thirstier hours; the amber arc is the best window. Same job, two start times, *and with a cooling tower the water is taken twice.*" | Live forecast · best window · water taken twice |
| 3 | **0:30–0:42** | Tab 1, power-cap switch | Click **100% → 85% → 70%**. Hover the energy bar as it shrinks. | "The second lever is speed. At seventy percent power the same job takes a little longer but uses noticeably less energy. That's a real cut, not just a shift." | 70% power = a real energy cut |
| 4 | **0:42–1:10** | Tab 2, planner | 0:42 click the **Overnight fine-tune** quick pick (2 × RTX 4090 · 6 h · by 9 AM). 0:45 click **Plan**. 0:47 the result card appears: hover the plan sentence, the **why** line under it, then a range and its `modelled` chip. 0:58 click the view tabs **Timetable → Hourly → Calendar → Chart** (about 3 s each). | "A student plans tonight's job: two RTX 4090s, six hours of work, done by nine. In about a second Thirst says when to start, how fast to run and when it finishes, with one line on why that time, and savings as ranges, each labelled. Read the next forty-eight hours as a timetable, hour by hour, on a calendar, or as a chart." | Plan in ~1 s · why this time · 4 ways to read it |
| 5 | **1:10–1:24** | Tab 2, **Run this plan** card | Hover the command box and click **Copy**. Click **Add to calendar** (the `.ics` file downloads; show the download chip for 1 s). Click **Copy share link**. End by hovering the **Recent** list. | "Then act on it: copy the exact command, add the run to your calendar with a reminder, or send a link that reopens the same job for your labmate." | Copy the command · add to calendar · share |
| 6 | **1:24–1:36** | Tab 3, **Compare cities** | Slow scroll through the six city cards: best start, the 48-hour strip, water for the job, saving vs now. Hover **Plan here** on one card. | "Or compare cities: the same job in six Indian cities, with each one's best start, the next two days, and the water it would take." | Same job, six cities |
| 7A | **1:36–1:42** | Terminal, live | Type `pip install thirst` (already installed, so it returns fast). Then type `thirst doctor` and show its `[ok]` lines. | "On the GPU machine, it's one package." | `pip install thirst` |
| 7B | **1:42–2:02** | Terminal, pre-recorded run, sped up 10–30× | Show `thirst run … -- python train.py`. The plan line appears, then the job output, then the **receipt** block. Hold 3 s on the receipt. Zoom into the **Energy**, **Saved** and **Capture** lines. | "thirst run waits for the right hour, lowers the GPU power limit, runs your script, and always puts the limit back, even on Ctrl-C or a dropped SSH session. Then a signed receipt: energy measured from the GPU, water and CO2 modelled from it." With the laptop fallback, say instead: "…Then a signed receipt. On this laptop the energy is modelled; on a lab GPU it's measured." | Always restores the GPU limit · signed receipt |
| 8 | **2:02–2:20** | Tab 4 leaderboard → Tab 5 site page | 2:02 hover **Pick your weight class** and the **D1** tab, then the top medal rows and their **(simulated)** labels. 2:11 click **Demo Lab, Chennai** and hover the score ring and the badge ladder. | "Receipts add up to a score: of the saving that was possible, how much did you take? We score the choice, not the climate, and labs compete in weight classes, so a four-GPU college lab never faces a data centre. Demo labs are marked simulated." | Fair score · weight classes · demo labs simulated |
| 9 | **2:20–2:44** | Tab 7 diagram (4 s), then quick cuts of tabs 8→12 (~3 s each), Tab 13 (2 s), Tab 14 (2 s) | Cut on each service name in the voice-over. Show the CloudFormation resources, the Lambda functions, the DynamoDB tables, the hourly schedule, the Amplify app, then `explain.py` `_invents_numbers`, then the green **Deploy + e2e** run. | "It all runs serverless on AWS. Amplify hosts the site. API Gateway and AWS Lambda run the planner and scoring. Amazon DynamoDB keeps the weather, plans and receipts. EventBridge Scheduler refreshes the forecast every hour. An explainer on Amazon Bedrock with the Strands Agents SDK is wired in, waiting on model access. AWS SAM deploys it all from GitHub, with no stored keys." | Amplify · API Gateway · Lambda · DynamoDB · EventBridge · Bedrock + Strands · SAM |
| 10 | **2:44–2:54** | Tab 6, Assumptions | Hover the **How sure we are** bar, click a `placeholder` chip, then scroll to **Words we use**. | "And every number wears a label: measured, modelled, sourced, or placeholder. Today our power-cap curve is still a placeholder, and we say so." | Every number wears a label |
| 11 | **2:54–2:58** | End card (a still image or a slide) | Static: **Thirst**, the site URL, `pip install thirst`, `github.com/Neal006/Thirst`, "team hello_world · WeMakeDevs × AWS". | "Thirst. Run at the right hour, and the right speed, and prove it." | — |

Total: **2:58**. If the export is 2:59 or more, trim the cities scroll (shot 6) or the view-tab clicks (shot 4), never the AWS names.

---

## 3. Shot-by-shot detail

### Shot 1 · Hook (0:00–0:12)
- Start recording on tab 1, already scrolled to the top and fully loaded, with the mouse parked off-screen.
- The meters must have finished animating before 0:07.
- *Optional opener:* 2–3 s of credited, openly licensed footage of a water tanker queue. If you use it, take those seconds from shot 2.

### Shot 2 · Water clock (0:12–0:30)
- The city picker sits in the hero. Wait until the dial redraws (about 1 s) before the next switch.
- The **Room AC / Data centre · cooling tower** toggle sits above the beakers. With the cooling tower, a building-water layer appears in both beakers.

### Shot 3 · Speed knob (0:30–0:42)
- The switch is under "A slower GPU drinks less". Pause about 1 s on each level, so the bars visibly move.

### Shot 4 · Planner (0:42–1:10)
- **The quick pick** fills the form. Keep **More options** closed: the point is that planning takes one click.
- **The result card** shows one sentence, e.g. *"Start at 04:00, GPU at 70%, done by 10:40"*, with the **why** line under it. Read the times you see. Don't say "start now" unless the card says so.
- **Under the card** you'll see "For this job every option gives the same plan…" in place of the slider. That's honest and expected: don't linger on it.
- **The view tabs** also work with the arrow keys. The last tab used is remembered, so reset to **Timetable** before recording.

### Shot 5 · Run this plan (1:10–1:24)
- **Copy** puts the exact `thirst run …` command for this job on the clipboard.
- **Add to calendar** downloads `thirst-plan.ics`, with a 10-minute reminder.
- **Copy share link** gives a `/plan?city=…&gpu=…` link that fills the form and plans at once. Optionally paste it into a new tab for 1 s to show it.

### Shot 6 · Cities (1:24–1:36)
- The page header reads "The same job in every city: 2 × RTX 4090 for 6 hours, done by 9 AM tomorrow."
- Each card shows **Best start**, the 48-hour strip, **Water for the job**, **Saving vs now** and **Plan here**.

### Shot 7 · Terminal (1:36–2:02)
- 7A is live typing; it's fine to paste. `thirst doctor` on a laptop shows a `[warn]` about the power limit. That's fine, or crop to the `[ok]` lines.
- 7B is pre-recorded. In the edit:
  - keep the plan line readable for 1 s and the receipt readable for 3 s
  - add a small "×20" badge while it is sped up
  - crop out any file path with your username, and anything from `config.toml`

### Shot 8 · Leaderboard (2:02–2:20)
- Keep the **(simulated)** labels in frame. They are part of the honesty story.
- On the site page, the badge ladder shows the points to the next badge.

### Shot 9 · AWS (2:20–2:44)
- Cut on each spoken service name; each view needs only 2–3 s.
- CloudFormation **Resources** lists the functions, tables, HTTP API and schedule together. Use it as the establishing shot.
- **Blur:** the account name/id and any ARN with the account number.
- Bedrock: show the code (`_invents_numbers`, which rejects any AI answer that invents a number), not the console. Model access is still pending on the account.

### Shot 10 · Assumptions (2:44–2:54)
- The status bar shows 30 design choices, 18 placeholders, 8 sourced, 1 calibrated.
- **Words we use** is the plain-language glossary.

### Shot 11 · End card (2:54–2:58)
- Make it at 1920 × 1080 in the site's Monsoon colours: teal `#126e6b`, amber `#f0b43c`, ink `#1d2321`, paper `#f7f8f6`. Use the Archivo font.

---

## 4. Editing and export (Clipchamp or DaVinci Resolve)

1. Lay the voice track first. Then cut the screen clips to fit the voice, never the other way round.
2. Add captions: paste the SRT below, or use auto-captions and fix "Thirst", "CO2", "Strands" and "Amplify".
3. Keep the music bed at −24 dB or lower, or use no music.
4. Export at 1080p, 30 fps, H.264. **Check the duration in the file's properties: it must be under 3:00.**
5. Upload to YouTube as **Unlisted**, titled "Thirst: water and carbon receipts for GPU jobs in India (WeMakeDevs × AWS)". Put the site URL, the repo and `pip install thirst` in the description.
6. Open the link in a private window, signed out, and watch it to the end.

---

## 5. Captions (SRT)

```srt
1
00:00:00,000 --> 00:00:06,000
Every hour a GPU trains a model, it drinks water twice:

2
00:00:06,000 --> 00:00:12,000
at the building that cools it, and at the power plant that feeds it. In Chennai, that water is already scarce.

3
00:00:12,000 --> 00:00:21,000
Thirst makes it visible. This dial is Chennai's next 24 hours from today's live forecast.

4
00:00:21,000 --> 00:00:30,000
Longer wedges are thirstier hours; the amber arc is the best window. Same job, two start times.

5
00:00:30,000 --> 00:00:42,000
The second lever is speed. At 70% power the same job takes a little longer but uses noticeably less energy. A real cut, not just a shift.

6
00:00:42,000 --> 00:00:50,000
A student plans tonight's job: two RTX 4090s, six hours of work, done by nine.

7
00:00:50,000 --> 00:01:00,000
In about a second Thirst says when to start, how fast to run and when it finishes, with one line on why that time, and savings as labelled ranges.

8
00:01:00,000 --> 00:01:10,000
Read the next 48 hours as a timetable, hour by hour, on a calendar, or as a chart.

9
00:01:10,000 --> 00:01:24,000
Then act on it: copy the exact command, add the run to your calendar with a reminder, or send a link that reopens the same job.

10
00:01:24,000 --> 00:01:36,000
Or compare cities: the same job in six Indian cities, with each one's best start, the next two days, and the water it would take.

11
00:01:36,000 --> 00:01:42,000
On the GPU machine, it's one package.

12
00:01:42,000 --> 00:01:52,000
thirst run waits for the right hour, lowers the GPU power limit, runs your script, and always puts the limit back.

13
00:01:52,000 --> 00:02:02,000
Then a signed receipt: energy measured from the GPU, water and CO2 modelled from it.

14
00:02:02,000 --> 00:02:11,000
Receipts add up to a score: of the saving that was possible, how much did you take?

15
00:02:11,000 --> 00:02:20,000
We score the choice, not the climate. Labs compete in weight classes. Demo labs are marked simulated.

16
00:02:20,000 --> 00:02:32,000
It all runs serverless on AWS. Amplify hosts the site. API Gateway and AWS Lambda run the planner and scoring.

17
00:02:32,000 --> 00:02:44,000
DynamoDB keeps weather, plans and receipts; EventBridge Scheduler refreshes hourly; Bedrock + Strands is wired in; AWS SAM deploys it, no stored keys.

18
00:02:44,000 --> 00:02:54,000
Every number wears a label: measured, modelled, sourced, or placeholder. Today our power-cap curve is still a placeholder.

19
00:02:54,000 --> 00:02:58,000
Thirst. Run at the right hour, and the right speed, and prove it.
```

If you used the laptop fallback in shot 7B, change caption 13 to: *"Then a signed receipt. On this laptop the energy is modelled; on a lab GPU it's measured."*

---

## 6. Final check before uploading

- [ ] Length < 3:00 in the file properties
- [ ] Every AWS service is said out loud: Amplify, API Gateway, Lambda, DynamoDB, EventBridge Scheduler, Bedrock, Strands Agents, SAM
- [ ] AWS console visible on screen
- [ ] Every feature in [`VIDEO_BRIEF.md`](VIDEO_BRIEF.md) §3 appears
- [ ] No account id, token, `config.toml` or personal billing data visible
- [ ] "ranges", "modelled", "simulated" and "placeholder" are said where the script says them
- [ ] Captions present and correct
- [ ] Unlisted, plays signed out
- [ ] Link added to `docs/WRITEUP.md`, the README and the submission form
- [ ] The recording lab's `s_...` id sent for deletion
