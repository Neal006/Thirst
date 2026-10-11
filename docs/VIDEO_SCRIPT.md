# Demo video script (target 2:50, hard limit < 3:00)

**Rules from the hackathon and plan 7.8:**
- Under 3:00 by the exported file's length.
- Uploaded to YouTube as **unlisted**, and it plays signed out.
- AWS **on screen and named out loud**.
- Captions on, because judges may watch muted.
- Never show tokens, `config.toml`, the AWS account id, or billing pages with personal details.

**How the timing works.** The voice-over is about 400 words, which is about 2:40 at a calm 150 words a minute. That leaves about 10 s of slack. If a take runs long, cut the *italic* phrases first.

**Honesty rules for the voice:**
- Say "about", "modelled" and "ranges" exactly where the script does.
- Never say a single litre figure.
- Don't say "measured" over a modelled receipt.
- Demo labs are "simulated".

---

## 1. Before recording (30 min)

### Browser (Chrome, a clean profile, no extensions or bookmarks bar)
1. Set the window to 1920 × 1080, page zoom 110%, and light mode.
2. Open these tabs, in this order:
   1. https://main.dzxkrtlc7xqfx.amplifyapp.com/ (home), with **Chennai** selected
   2. https://main.dzxkrtlc7xqfx.amplifyapp.com/plan?city=Chennai
   3. https://main.dzxkrtlc7xqfx.amplifyapp.com/leaderboard
   4. https://main.dzxkrtlc7xqfx.amplifyapp.com/sites/s_simaaaaaaa (Demo Lab, Chennai, Gold)
   5. https://main.dzxkrtlc7xqfx.amplifyapp.com/assumptions
   6. GitHub README "Built on AWS" diagram: https://github.com/Neal006/Thirst#built-on-aws
   7. AWS console, region **Asia Pacific (Mumbai) ap-south-1**: CloudFormation → stack `thirst-dev` → **Resources** tab
   8. AWS console → Lambda → Functions, filtered by `thirst-dev`
   9. AWS console → DynamoDB → Tables, filtered by `thirst-dev`
   10. AWS console → EventBridge → Schedules
   11. AWS console → Amplify → app `dzxkrtlc7xqfx`
   12. GitHub → Actions → the latest green **Deploy** run
   13. GitHub → `src/handlers/explain.py`, scrolled to `def _invents_numbers` (about line 232)
3. Load each tab once so nothing is still loading on camera.
4. In the AWS console, don't open the account menu (top right). The account name is visible there: blur it in the edit.

### Terminal (Windows Terminal or any terminal with a big font)
1. Use font size 18+, a light or dark theme with high contrast, about 100 × 30 characters, and a short prompt such as `$ `.
2. Point Thirst at a throwaway folder so your real config never appears on screen:
   - PowerShell: `$env:THIRST_HOME="$env:TEMP\thirst-demo"`
   - bash: `export THIRST_HOME=/tmp/thirst-demo`
3. Before recording, register once:
   ```
   thirst register --name "Demo Recording Lab" --city Chennai --cooling room_ac --gpus 1 --private
   ```
   Don't show this on camera: the output prints the config path. After the shoot, a maintainer deletes the site with `scripts/seed.py --delete-site <id>`.
4. **Pre-record the run (shot 4B)** because it takes minutes. Record it separately and speed it up in the edit.
   - **Best:** a Linux desktop with an NVIDIA GPU and a 1-hour job. It gives a `measured` receipt with a real cap.
   - **Fallback (any laptop), a modelled receipt.** Tested on 2026-10-11 with `thirst` 0.3.1. Don't use `--now`: following the plan is what earns the saving.
     ```
     thirst run --modelled --gpu-model RTX-3050-Laptop --gpus 1 --hours 0.05 --deadline "<tomorrow> 09:00" -- python -c "import time; print('training...', flush=True); time.sleep(150); print('done', flush=True)"
     ```
     - **Duration:** about 2.5 minutes in real time.
     - **Receipt:** "Saved 20% water and 20% CO2", "You took 100% of the possible saving", "Site score 78.5 gold (Provisional)".
     - **Short job:** energy prints as `0.00 kWh`. For bigger numbers on screen, use `--gpu-model RTX-4090 --gpus 2 --hours 1` with a 1-hour sleep, then speed it up.
     - **Voice-over:** say **"modelled"**.
     - **Private lab:** with `--private` (as registered above) the receipt link returns "not found". Don't open it on camera. If you want to show the receipt page, register the recording lab without `--private`.
5. Run `clear` before each terminal shot.

### Audio
- Record the voice separately: phone voice memo in a quiet room, or OBS mic only.
- Read the script below twice before recording.

---

## 2. Shot list

| # | Time | Screen | Action on screen | Voice-over (read exactly) | Caption |
|---|---|---|---|---|---|
| 1 | **0:00–0:14** | Tab 1, home page, top | Hold still on the headline **"Every GPU hour drinks water twice."** At 0:08, slowly move the mouse over the two meters. | "Every hour a GPU trains a model, it uses water twice: at the building that cools it, and at the power plant that feeds it. In Chennai, that water is already scarce." | Every GPU hour drinks water twice |
| 2 | **0:14–0:34** | Tab 1, water clock, then beakers | 0:14 hover the yellow **RUN** arc. 0:20 switch the city Chennai → Delhi → back to Chennai. 0:26 scroll to **"Where the water goes"** and click **Data centre · cooling tower**. | "Thirst makes it visible. This dial is Chennai's next twenty-four hours from today's live forecast. Long blue wedges are thirsty hours; the yellow arc is the best window. Same job, two start times. *And with a cooling tower, the water is taken twice.*" | Live forecast · best window · water taken twice |
| 3 | **0:34–1:08** | Tab 2, planner | 0:34 click the **Overnight fine-tune** preset. 0:38 click **Plan**. 0:40 the plan card appears: hover the sentence, then the **18 to 19%** range, then a `modelled` chip. 0:52 scroll to the speed knob on the home page, or move the slider on the plan page. 1:00 click **100% → 85% → 70%** on the home page power-cap switch. | "A student plans a job: two RTX 4090s, six hours of work, done by nine in the morning. In about a second: start now, run the GPU at seventy percent, finish well before the deadline, with about eighteen to nineteen percent less water and CO2. Those are ranges, and they are modelled. Most of that saving is the speed knob: a slightly slower GPU uses less energy for the same work. That's a real cut, not just a shift." | Plan in ~1 s · ranges, not single numbers · 70% power = real energy cut |
| 4A | **1:08–1:18** | Terminal, live | Type `pip install thirst` (already installed, it returns fast). Then type `thirst plan --hours 6 --deadline "<tomorrow> 09:00"` and wait for the plan output. | "On the GPU machine, it's one package and one command." | `pip install thirst` |
| 4B | **1:18–1:40** | Terminal, pre-recorded run, sped up 10–30× | Show `thirst run … -- python train.py`. The plan line appears, then the job output, then the **receipt** block. Hold 3 s on the receipt. Zoom into the **Energy** and **Water** lines. | "thirst run waits for the right hour, lowers the GPU power limit, runs your script, and always puts the limit back, even on Ctrl-C or a dropped SSH session. Then you get a signed receipt: energy *measured* from the GPU, water and CO2 modelled from it." (If you use the modelled fallback, say: "energy here is modelled, because this laptop can't be capped; on a lab GPU it's measured.") | Always restores the GPU limit · signed receipt |
| 5 | **1:40–2:04** | Tab 3 leaderboard → Tab 4 site page | 1:40 hover the **D1** tab, then the top three medal rows and their **(simulated)** labels. 1:52 click **Demo Lab, Chennai** and hover the score ring and the badge ladder ("points to Platinum"). | "Receipts add up to a score: of the saving that was possible, how much did you take? We score the choice, not the climate, and labs compete in weight classes, so a four-GPU college lab never faces a data centre. These demo labs are simulated." | Fair score · weight classes · demo labs simulated |
| 6 | **2:04–2:40** | Tab 6 diagram (4 s), then quick cuts of tabs 7→11 (~3 s each), Tab 13 (3 s), Tab 12 (3 s) | Diagram: point at each box as you name it. Console: cut on each service name in the voice-over. CloudFormation resources list, then the Lambda functions, the DynamoDB tables, the EventBridge hourly schedule, the Amplify app, `explain.py` `_invents_numbers`, and the GitHub Deploy run (green). | "It all runs serverless on AWS. Amplify hosts the site. API Gateway and AWS Lambda run the planner and the scoring. Amazon DynamoDB keeps the weather, plans and receipts. EventBridge Scheduler refreshes the forecast every hour. An optional explainer on Amazon Bedrock, built with the Strands Agents SDK, puts a plan into plain words, and its answer is thrown away if it invents a number. AWS SAM deploys it all from GitHub, with no stored keys." | Amplify · API Gateway · Lambda · DynamoDB · EventBridge · Bedrock + Strands · SAM |
| 7 | **2:40–2:52** | Tab 5, Assumptions | Hover the **How sure we are** bar, then click a `placeholder` chip. | "And every number wears a label: measured, modelled, sourced, or placeholder. Today our power-cap curve is still a placeholder, and we say so." | Every number wears a label |
| 8 | **2:52–2:57** | End card (a still image or a slide) | Static: **Thirst**, the site URL, `pip install thirst`, `github.com/Neal006/Thirst`, "team hello_world · WeMakeDevs × AWS". | "Thirst. Run at the right hour, and the right speed, and prove it." | — |

Total: **2:57**. If the export is 2:58 or more, trim shot 6, not the AWS names.

---

## 3. Shot-by-shot detail

### Shot 1 · Hook (0:00–0:14)
- Start recording on tab 1, already scrolled to the top and fully loaded, with the mouse parked off-screen.
- The meters (**Water / kWh, best vs worst hours**, **CO₂ / kWh …**) must have finished animating before 0:08.
- *Optional opener:* 3 s of credited, openly licensed footage of a water tanker queue before the home page. If you use it, take those 3 s from shot 2's pause.

### Shot 2 · Water clock (0:14–0:34)
- City switch: use the city picker in the hero. Wait until the dial redraws (about 1 s) before switching again.
- After the switch back to Chennai, scroll smoothly to the beakers.
- The **Room AC / Data centre · cooling tower** toggle sits above the beakers. When clicked, the building-water layer appears in both beakers.

### Shot 3 · Planner (0:34–1:08)
- The plan card text will read something like *"Start 13:05, GPU at 70%, done by 19:45"*. Read the times you see as "start now" only if the card says it starts within the hour. Otherwise say "start at <time>".
- **Don't** linger on the water/carbon slider: today it doesn't change the plan (placeholder data). Use the home page power-cap switch for the "speed knob" moment.
- If the plan takes more than 2 s, cut the wait in the edit.

### Shot 4 · Terminal (1:08–1:40)
- 4A is live typing. It's fine to paste the command.
- 4B is the pre-recorded run. In the edit:
  - speed up the waiting and the job output
  - keep the plan line readable for 1 s and the receipt readable for 3 s
  - add a small "×20" badge while it is sped up
- Crop out anything showing a file path with your username, and anything from `config.toml`.

### Shot 5 · Leaderboard (1:40–2:04)
- Make sure the **(simulated)** labels are in frame. They are part of the honesty story.
- On the site page, the badge ladder shows the points needed for the next badge.

### Shot 6 · AWS (2:04–2:40)
- Cut on each spoken service name. Each console view only needs 2–3 s.
- In CloudFormation, the **Resources** tab shows the Lambda functions, tables, HTTP API and schedule in one list. Use it as the "establishing" shot.
- In EventBridge Schedules, the hourly schedule shows `rate(1 hour)`.
- **Blur:** the account name/id (top right), and any ARN that contains `857229543886`.
- Bedrock: we show code, not the console, because model access is still pending on the account. The words "optional explainer" are accurate.

### Shot 7 · Assumptions (2:40–2:52)
- The status bar shows the mix: 30 design choices, 18 placeholders, 8 sourced, 1 calibrated.
- Clicking a `placeholder` chip scrolls to that factor and highlights it.

### Shot 8 · End card (2:52–2:57)
- Make it in Canva or Slides at 1920 × 1080, using the site's colours (cobalt `#0a5cff`, yellow `#ffcc00`, ink `#0b1620`) and the Archivo font.

---

## 4. Editing and export (Clipchamp or DaVinci Resolve)

1. Lay the voice track first. Then cut the screen clips to fit the voice, never the other way round.
2. Add captions: paste the SRT below, or use auto-captions and fix the words "Thirst", "CO2" and "Strands".
3. Keep the music bed at −24 dB or lower, or use no music.
4. Export at 1080p, 30 fps, H.264. **Check the duration in the file's properties: it must be under 3:00.**
5. Upload to YouTube as **Unlisted**, titled "Thirst: water and carbon receipts for GPU jobs in India (WeMakeDevs × AWS)". Put the site URL, the repo and `pip install thirst` in the description.
6. Open the link in a private window, signed out, and watch it to the end.

---

## 5. Captions (SRT)

```srt
1
00:00:00,000 --> 00:00:07,000
Every hour a GPU trains a model, it uses water twice:

2
00:00:07,000 --> 00:00:14,000
at the building that cools it, and at the power plant that feeds it. In Chennai, that water is already scarce.

3
00:00:14,000 --> 00:00:24,000
Thirst makes it visible. This dial is Chennai's next 24 hours from today's live forecast.

4
00:00:24,000 --> 00:00:34,000
Long blue wedges are thirsty hours; the yellow arc is the best window. Same job, two start times.

5
00:00:34,000 --> 00:00:44,000
A student plans a job: two RTX 4090s, six hours of work, done by 9 in the morning.

6
00:00:44,000 --> 00:00:56,000
In about a second: run the GPU at 70%, finish before the deadline, with about 18–19% less water and CO2. Ranges, and modelled.

7
00:00:56,000 --> 00:01:08,000
Most of that saving is the speed knob: a slightly slower GPU uses less energy for the same work. A real cut, not just a shift.

8
00:01:08,000 --> 00:01:18,000
On the GPU machine, it's one package and one command.

9
00:01:18,000 --> 00:01:30,000
thirst run waits for the right hour, lowers the GPU power limit, runs your script, and always puts the limit back.

10
00:01:30,000 --> 00:01:40,000
Then a signed receipt: energy measured from the GPU, water and CO2 modelled from it.

11
00:01:40,000 --> 00:01:52,000
Receipts add up to a score: of the saving that was possible, how much did you take?

12
00:01:52,000 --> 00:02:04,000
We score the choice, not the climate. Labs compete in weight classes. These demo labs are simulated.

13
00:02:04,000 --> 00:02:16,000
It all runs serverless on AWS. Amplify hosts the site. API Gateway and AWS Lambda run the planner and scoring.

14
00:02:16,000 --> 00:02:28,000
Amazon DynamoDB keeps weather, plans and receipts. EventBridge Scheduler refreshes the forecast every hour.

15
00:02:28,000 --> 00:02:40,000
An optional explainer on Amazon Bedrock with the Strands Agents SDK; AWS SAM deploys it all from GitHub, no stored keys.

16
00:02:40,000 --> 00:02:52,000
Every number wears a label: measured, modelled, sourced, or placeholder. Today our power-cap curve is still a placeholder.

17
00:02:52,000 --> 00:02:57,000
Thirst. Run at the right hour, and the right speed, and prove it.
```

If you used the modelled fallback in shot 4B, change caption 10 to: *"Then a signed receipt. Energy here is modelled; on a lab GPU it's measured."*

---

## 6. Final check before uploading

- [ ] Length < 3:00 in the file properties
- [ ] Every AWS service is said out loud: Amplify, API Gateway, Lambda, DynamoDB, EventBridge Scheduler, Bedrock, Strands Agents, SAM
- [ ] AWS console visible on screen
- [ ] No account id, token, `config.toml` or personal billing data visible
- [ ] "simulated", "modelled" and "placeholder" are said where the script says them
- [ ] Captions present and correct
- [ ] Unlisted, plays signed out
- [ ] Link added to `docs/WRITEUP.md`, the README and the submission form
