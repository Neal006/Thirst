# Thirst: a water and carbon planner, receipt and rating for GPU work in India

Version 0.3 (refined) · 9 Oct 2026 · Environmental Hacks (WeMakeDevs x AWS) · Track 02: Heat and Water

> **One line for judges:** Thirst tells you when and how fast to run a GPU job so it takes less water from a stressed city and puts less CO₂ in the air. It proves the result with a measured "water receipt", and it turns receipts into a fair rating where a 4-GPU college lab can beat a big company's lab.

New words are explained in the **Glossary (section 14)**. Every number has a source in **section 15**, or a label that says it is our own assumption.

---

## 1. The problem, in plain words

AI runs on GPUs. GPUs run on electricity. Every unit of electricity (1 kWh) that a GPU uses also uses water, in two places:

1. **At the building (direct water).** Big data centres often cool themselves with cooling towers, which evaporate water. They evaporate more water in hot and humid hours.
2. **At the power plant (indirect water).** Most Indian electricity comes from coal plants, and coal plants also cool themselves with water. Indian rules let an older coal plant with a cooling tower consume up to 3.5 m³ of water per MWh, which is 3.5 litres per kWh. Units built after 2017 are allowed up to 3.0. Plants that use sea water are not covered by this limit, and many plants self-report that they do not meet it.

**How big is it?**

- Data centres used about 415 TWh of electricity worldwide in 2024, and the IEA expects about 945 TWh by 2030.
- Researchers estimate that AI worldwide may withdraw 4.2 to 6.6 billion m³ of water in 2027.
- In India, data centre capacity was about 1.5 GW in 2025 and one industry report expects about 6.5 GW by 2030. The same report estimates water use rising from about 150 billion litres a year to about 359 billion litres, with more than half of the facilities in water-stressed regions. These are industry estimates, not government numbers.
- Mumbai and Chennai are the two biggest data centre hubs, and both are water-stressed cities.

**Who feels it:** people in Chennai, Bengaluru, Hyderabad and Mumbai, whose taps, tankers and groundwater compete with cooling towers and power plants. The Indian planning norm for city water supply is 135 litres per person per day (CPHEEO). We use this number to turn litres into something people understand: **"person-days of city water"**.

**Why it keeps happening:** a student or engineer who starts a 6-hour training job sees the loss curve, not the water or the CO₂. Nothing tells them the cost, and nothing rewards them when they do better. So nobody changes anything.

---

## 2. What we can honestly change, and what we cannot

Your aim is to fight the damage that AI compute causes to natural resources. Software cannot undo water that is already gone, so we do not claim to "reverse" anything. Software can do three real things:

| Lever | What Thirst does | Is it a real cut or a shift? |
|---|---|---|
| **1. Slow the GPU a little (power cap)** | Lower the GPU's power limit (for example to 85%). The same job uses less energy and finishes a little later | **Real cut.** Less energy means less water and less CO₂ |
| **2. Pick better hours (timing and pauses)** | Start or pause the job so it runs in hours with less water and CO₂ per kWh, and still meet the deadline | **Mostly a shift.** It changes *when*, not *how much*. It becomes a real cut when the job uses midday solar power that would otherwise be wasted |
| **3. Make it visible and reward it (receipt and rating)** | A measured receipt after every job, and a public rating that rewards good choices | **Behaviour change** over months, which is where the large effect comes from |

**Money is on our side in India.** India's time-of-day electricity rules say that for commercial and industrial users, power in the 8 "solar hours" must cost 10 to 20 percent less than normal, and peak hours must cost more. Rollout is state by state, and a draft amendment proposes moving the deadline for commercial users to April 2027, so the team must check each state. Where it applies, the greener midday hours are also the cheaper hours, so labs and companies save money while they save water and CO₂.

---

## 3. How we reached this idea

| Step | Idea | Why we moved on |
|---|---|---|
| 1 | Capture waste heat from GPUs (hardware) | Cannot be shown in a 3-minute video, needs hardware, and the person who benefits is unclear |
| 2 | A scheduler that picks the best hour for water and carbon | Good, but judges will see it as "a carbon scheduler plus water". Tools like CATS and WattTime already move jobs in time |
| 3 | Add three things: a **speed knob** (GPU power cap), **water weighted by local stress**, and a **measured receipt** from the real GPU | This makes it new and measurable. Most tools only move jobs in time and only count carbon |
| 4 | Model what labs really have: **room AC**, not cooling towers | Labs have almost no direct water, but their AC uses more power on hot afternoons. This keeps the model honest |
| 5 | Turn receipts into a **rating of the operator** (the lab or site), not the AI model | Existing ratings score models. Nobody scores how a lab actually runs its jobs. This gives people a reason to keep using Thirst |
| 6 | **This version (v0.3):** fix fairness in the score, use Indian factors (CEA, MoEFCC), add "person-days of water", say plainly what is a cut and what is a shift, and cut scope to fit 2.5 days | Makes the idea defensible in front of judges and buildable by Sunday |

---

## 4. What already exists, and our gap

| Tool or project | What it does | What it does not do |
|---|---|---|
| **AI Energy Score** (Salesforce, Hugging Face, Cohere, CMU) | 1 to 5 star energy label and public leaderboard for **AI models** | Does not rate how a lab runs jobs. No water |
| **ML.ENERGY Leaderboard** | Measures energy of **models** | Same as above |
| **Carbon Aware SDK, WattTime, Electricity Maps** | Carbon signals for picking cleaner hours | No water, no deadlines, no GPU speed control. Hourly India data from Electricity Maps needs the paid API |
| **CATS** (Climate-Aware Task Scheduler) | Open-source command line tool that picks the lowest-carbon start time | Carbon only. No water, no GPU power cap, no receipt |
| **CarbonScaler** | Scales batch jobs up in low-carbon hours and slows them in high-carbon hours | Carbon only, Kubernetes clusters, research tool |
| **WaterWise** (research, open source) | Scheduler that optimises carbon and water across data centres in different regions | For big geo-distributed clouds, not a lab tool, no India data, no rating |
| **CodeCarbon** | Measures CO₂ after the code runs | No plan before the job, no water |
| **CarbonPilot** (a July 2026 hackathon project) | Agent that estimates energy, carbon and water of an AI job and suggests a greener GPU or region | Estimates only. Does not run the job, set the power cap, or give a measured receipt |

**Our gap, in one sentence (put this in the writeup):**

> Existing tools score the **model** or only move jobs in **time** for **carbon**. Thirst plans **time and GPU speed** together, counts **water weighted by local water stress**, uses **Indian grid and weather data**, proves the result with a **measured receipt**, and rates the **operator**, so a small lab can earn recognition.

---

## 5. The product

### 5.1 The loop

```
 Plan  ──►  Run  ──►  Receipt  ──►  Rating
  │                                   │
  └────────── better next time ◄──────┘
```

1. **Plan.** You describe the job: GPU type and count, hours of work, deadline, can it pause, city, cooling type. Thirst picks the **start time, pauses and GPU power cap** that cost the least stress-weighted water and CO₂, and still finish before the deadline.
2. **Run.** `thirst run -- python train.py` waits for the planned start, sets the power cap, runs your command, pauses and resumes it as planned, and measures real GPU energy from the GPU itself (NVML).
3. **Receipt.** At the end you get litres of water, kg of CO₂ and kWh, compared with "if you had started right away at full power". Energy is **measured**. Water and CO₂ are **modelled from the measured energy**, and the receipt says so.
4. **Rating.** Receipts add up to a 0 to 100 **Thirst Score** per site, ranked inside size groups, so a 4-GPU lab competes with other small labs, not with a giant.

### 5.2 What a student sees

> "Start at 01:00 with the GPU at 85% power. Done by 08:10, before your 09:00 deadline. Saves about 15 to 30% stress-weighted water and 10 to 20% CO₂ compared with starting now. The GPU part is measured; the water part is modelled."

(These numbers show the layout only. Real numbers come from the engine and from Step 0.)

### 5.3 The three layers and what we build this weekend

| Layer | What it is | Weekend scope |
|---|---|---|
| **Planner** (web + API) | Best start, pauses and power cap, with a water-vs-carbon slider and ranges | Build fully |
| **Runner and receipt** (CLI) | Runs the job with the plan, measures energy, sends a signed receipt | Build fully, record one real overnight job |
| **Rating and board** | Thirst Score per site, size groups, badges | Build the core: score, one board, site page |

The AI agent (Strands Agents SDK on Amazon Bedrock) only **reads** a plain-English request and **explains** the plan. The math solver makes every decision, so the demo works even without the AI.

---

## 6. The science inside, in simple words

### 6.1 Two kinds of water, and why we count "consumption"

- **Withdrawal** is water taken out of a river, lake or ground. Some of it goes back.
- **Consumption** is water that does not go back, mostly because it evaporates.
- For cooling towers with good water, roughly 80% of the water taken in is evaporated. We count **consumption**, because evaporated water is lost to the local basin. This matches Li et al.

### 6.2 Why a litre in Chennai counts more than a litre in Shillong

A litre taken from a place with little water hurts more people than a litre taken from a place with plenty. We multiply litres by a **stress weight** from WRI Aqueduct (Low = 1.0 up to Extremely high = 2.5). These weights are **our design choice**, written in the spec so anyone can change them. We call the result **stress-weighted litres**.

### 6.3 Heat physics: every GPU watt becomes heat

All the electricity a GPU uses turns into heat in the room. The AC must pump that heat outside. An AC with a COP of 3 needs about 0.33 kWh of extra electricity to remove 1 kWh of heat. On a hot afternoon the AC works harder (lower COP), so the **same job uses more electricity** in the afternoon than at night. Most tools ignore this. Thirst models it.

### 6.4 Why a slightly slower GPU saves energy

A GPU's power rises faster than its speed, because higher speed needs higher voltage, and power grows with voltage squared. Also, training often waits for memory, so the GPU is not always busy. Research from the Zeus and Perseus teams shows that lowering GPU power can save a large share of energy for a small slowdown. We **measure** this on our own GPU (power-cap sweep) instead of trusting a paper's number.

### 6.5 Carbon and water of the Indian grid by hour

- At midday, solar power pushes some coal off the grid, so **both** CO₂ and power-plant water per kWh go down.
- At night, coal is high, but the air is cooler, so cooling towers and ACs use less.
- We use the **average** mix of the grid in each hour, like CEA and the CSEP tracker do. The **marginal** plant (the one that turns on when you add load) in India is often coal at all hours, so real savings from timing alone can be smaller. We say this on screen.
- IPCC world-average numbers are too low for Indian coal plants, so we **calibrate** our coal factor so that the yearly average matches the official CEA grid factor (0.727 kg CO₂ per kWh for 2023-24).

### 6.6 The open question (we test it first)

In India, midday solar may lower carbon **and** power-plant water so much that it beats the "cool night" advantage. If so, the headline is "Midday wins in India, and here is by how much". If the hours conflict, the headline is "Solar hours vs cool nights: here is the best balance". Either result is a real finding, and we show the chart in the video.

---

## 7. The Thirst Score (spec v0.2)

### 7.1 Rules we copy from ENERGY STAR

1. **Fair:** do not punish what you cannot control (your city's climate, your state's coal grid).
2. **Peer groups:** compare like with like.
3. **One simple number and a badge.**
4. **Measured beats modelled:** every number has a data-quality tag.

### 7.2 Score the choice, not the location

For every job we compute three versions of the same footprint:

- **Base:** start the moment the job was submitted, at full power. The server records the submit time, so nobody can fake it.
- **Best:** the best plan that meets the deadline.
- **Actual:** what really happened, using the measured energy.

```
J = 0.45 × W/W_base + 0.35 × C/C_base + 0.20 × E/E_base        (so J_base = 1)

Capture = (1 − J_actual) / (1 − J_best),   kept between 0 and 1
```

**Capture** = "what share of the possible saving did you actually take?" A lab next to a coal plant and a lab next to a dam each start from their own Base, so both can reach Capture 0.95.

**Fairness fix in v0.2:** Base, Best and Actual are all scored with the **same forecast that existed at submit time**. So a wrong weather forecast never lowers your score. The **absolute** litres and kg on the receipt use the observed weather and grid data.

If a job has almost no room to save (`1 − J_best` under 3%), it is marked "no room to shift" and left out of Capture, so urgent jobs are never punished.

### 7.3 Site score (0 to 100, last 30 days)

| Part | Points | What it rewards |
|---|---|---|
| A. Behaviour | 50 | Energy-weighted average Capture × 50 |
| B. Facility efficiency | 30 | PUE and WUE better than similar sites. Needs metered building data, so it shows "Not rated" for now |
| C. Measurement and openness | 20 | 10 points for share of energy measured by NVML, 5 for coverage of 80% or more of GPU energy, 5 for public receipts |

When B is "Not rated", the score is A + C out of 70, scaled to 100, and tagged **Provisional**.

**Badges:** Platinum 90+, Gold 75+, Silver 60+, Bronze 45+. Gold and above need at least 30% of energy from flexible jobs.

**Size groups (like weight classes in boxing):** D1 Lab up to 16 GPUs, D2 Cluster 17 to 256, D3 Facility 257 to 4,096, D4 Hyperscale above 4,096. We rank **sites**, not companies, so a big company's 8-GPU lab competes in D1.

**Every row shows the absolute monthly footprint** next to the score, so a large user can never hide behind a good score.

### 7.4 Anti-cheating (short)

| Trick | Why it fails |
|---|---|
| Pretend the job would have run at the worst hour | Base uses the server's submit time |
| Declare a fake long deadline | Capture is a ratio, a bigger chance is also harder to take |
| Mark every job "not flexible" | Under 30% flexible energy blocks Gold |
| Send only good jobs | Coverage check and public coverage % |
| Split one job into many | Capture is energy-weighted, so splitting changes nothing |
| Send fake energy | Receipts are signed per site; energy above GPU limits (count × max power × hours) is rejected |

---

## 8. Impact in people words (illustrative)

All numbers below are **our assumptions for illustration**. The app shows real ranges.

Assumptions: CPU, memory and fans add 20% to GPU energy; room-AC lab, AC efficiency gives about 1.35 kWh at the wall per 1 kWh of IT load; grid water 2.2 to 2.7 L per kWh (coal share of 70 to 75% at 3.0 to 3.5 L per kWh, to be checked with Ember data); grid carbon 0.727 kg per kWh (CEA 2023-24); saving of 10 to 25% from power cap plus timing (to be checked by our sweep and Step 0).

| Case | Facility energy | Grid water | CO₂ | Saving with Thirst |
|---|---|---|---|---|
| One job: 2 GPUs × 400 W × 6 h | about 7.8 kWh | 17 to 21 L | about 5.7 kg | about 2 to 5 L and 0.6 to 1.4 kg |
| One lab for a year: 8 GPUs at 400 W, busy half the time | about 22,700 kWh | 50,000 to 61,000 L | about 16.5 t | 5,000 to 15,000 L (**37 to 113 person-days of city water**) and 1.6 to 4.1 t CO₂ |

**National what-if (not a claim):** if Indian data centres cut their water use by 10% through better timing, power caps and cooling choices, that is about 15 billion litres a year, which equals the city water norm for about 3 lakh (300,000) people for a full year. The per-job number is small. The habit across thousands of labs and data halls is what matters, and that is why the rating exists.

---

## 9. Who uses it and why they would care

| User | What they get | Why they care |
|---|---|---|
| Student or researcher in a college GPU lab | One command, one clear instruction, a receipt | Their lab climbs the board. Easy win |
| Lab head or professor | Site page, monthly totals, badge | Power bill, grant and accreditation reports, pride |
| Startup on rented GPUs (colocation or cloud) | Receipts per job, a Gold badge | Enterprise buyers ask for footprint data |
| Data centre or colocation operator in Chennai, Mumbai, Hyderabad | Direct water planning with wet-bulb, receipts for customers | Water risk, cheaper solar-hour power, customer reporting |
| Sustainability team at a listed company | Per-job numbers that add up | SEBI's BRSR Core asks top listed companies to disclose water and energy intensity |

**The people who benefit but do not use the app:** residents in water-stressed basins. The "person-days of water" number keeps them in the story.

---

## 10. Business and adoption (short)

- **Open core:** the CLI, spec, public board and lab dashboard are free. Later paid parts: company dashboard with BRSR export, "Thirst Verified" audit, Slurm and Kubernetes plugins, and an API for cloud and colocation providers to issue receipts to their customers.
- **Adoption order:** college labs, then startups, then regional labs of larger companies, then cloud and colocation providers, then standards bodies.
- **Neutral ownership later:** donate the spec to a neutral body, the way the Green Software Foundation took its SCI spec to an ISO standard.
- **No market-size numbers** in the pitch. We have no sourced figure.

---

## 11. Risks we say out loud

1. **Water numbers are modelled.** Only energy is measured. We show ranges and label every number.
2. **The India trade-off may be weak.** Step 0 decides the headline.
3. **Hourly Indian grid data is limited.** We use national 5-minute generation data from the CSEP tracker if we can export it, or else a documented solar-radiation proxy. Both are labelled.
4. **Average vs marginal carbon.** We use average and say so.
5. **Shifting is not cutting.** Only the power cap cuts energy. We say both.
6. **Rebound.** Greener-looking compute can lead to more compute. We always show the absolute footprint.
7. **Most labs use room AC.** Their direct water is near zero. The cooling-type toggle keeps the model honest.
8. **Power cap needs admin rights.** If refused, the job runs uncapped and the receipt says so.
9. **We leave out the water and carbon used to make the GPU** (embodied footprint). We say so in the assumptions.

---

## 12. What we will not do

- Rank any company that did not opt in. Simulated demo sites are clearly tagged "Simulated".
- Claim exact litre savings. Ranges only.
- Build heat recovery hardware.
- Use GPU instances on AWS.
- Let the AI agent make decisions.

---

## 13. What changed from the team's v0.2 draft

| Change | Why |
|---|---|
| Score all three footprints with the submit-time forecast; absolute numbers use observed data | Forecast errors must not punish users |
| Base energy for capped jobs comes from the measured sweep: `E_base = E_work / ε` (ε = energy per unit of work at that power level) | Base must be the same work at full power |
| Coal carbon factor calibrated to the CEA grid factor, not the IPCC world median | Indian coal plants emit more than the world median |
| Coal water uses the MoEFCC limits (3.0 to 3.5 L/kWh) as a range, with a note that seawater plants are exempt and many plants miss the limit | Uses the Indian rule, honest about compliance |
| Added "person-days of city water" (CPHEEO 135 L) | Makes impact human |
| Added the time-of-day tariff | Money and the environment point the same way |
| Added CATS, CarbonScaler, WaterWise and CarbonPilot to the competition table | Judges may know them; we show we do too |
| Paused GPUs still draw idle power, and the planner now counts it | Honest receipts, and the planner avoids long idle gaps |
| Scope cut for 2.5 days left | One working loop beats five half-working features |

---

## 14. Glossary

| Word | Simple meaning |
|---|---|
| **kWh** | A unit of electricity. A 1,000-watt heater running for 1 hour uses 1 kWh |
| **TWh / GW** | Very large units. 1 TWh = 1 billion kWh. 1 GW = 1 million kW of power |
| **GPU** | The chip that trains and runs AI models |
| **TDP / power limit** | The most power a GPU is allowed to draw. We can lower it with `nvidia-smi -pl` |
| **Power cap** | Setting a lower power limit so the GPU uses less energy |
| **NVML** | NVIDIA's library that reads how much energy the GPU has used |
| **PUE** | Power Usage Effectiveness. Total building power ÷ computer power. 1.5 means 0.5 kWh extra for cooling and losses per 1 kWh of compute |
| **WUE** | Water Usage Effectiveness. Litres of water the building uses per kWh of compute |
| **COP** | Coefficient of Performance. How much heat an AC removes per unit of electricity. Higher is better |
| **Wet-bulb temperature** | A temperature that combines heat and humidity. Cooling towers use more water when it is high |
| **Withdrawal / consumption** | Water taken out vs water that does not come back (mostly evaporated) |
| **Water stress** | How much of a place's available water is already being used. High stress means little is left |
| **Stress-weighted litres** | Litres multiplied by the stress weight of the place they come from |
| **Grid carbon intensity** | kg of CO₂ released per kWh of electricity from the grid |
| **Average vs marginal** | Average: the mix of all plants running. Marginal: the plant that turns on when you add more load |
| **Direct / indirect water** | Water used at the building vs water used at the power plant |
| **Capture** | Share of the possible saving that you actually took (0 to 1) |
| **Pareto chart** | A chart of all good plans, where you cannot improve water without making carbon worse |
| **Time-of-day (ToD) tariff** | Electricity price that changes by hour. Solar hours are cheaper |
| **BRSR Core** | SEBI's sustainability report format for top listed Indian companies |
| **Embodied footprint** | Water and carbon used to make the hardware itself |
| **Rebound effect** | When something becomes cheaper or cleaner, people use more of it |

---

## 15. Sources

- IEA, *Energy and AI*, executive summary (data centre electricity 415 TWh in 2024, about 945 TWh in 2030): https://www.iea.org/reports/energy-and-ai/executive-summary
- Li, Yang, Islam, Ren, *Making AI Less "Thirsty"* (4.2 to 6.6 billion m³ withdrawal in 2027; withdrawal vs consumption): https://arxiv.org/abs/2304.03271 and CACM version https://cacm.acm.org/?p=768187
- MoEFCC notification of 7 Dec 2015 and amendment of 28 Jun 2018 on thermal plant water use, as quoted by the Ministry of Power in Lok Sabha: https://powermin.gov.in/sites/default/files/uploads/LS_13122018_Eng.pdf and https://eparlib.nic.in/bitstream/123456789/779379/1/AU3728.pdf
- Manthan Adhyayan Kendra, compliance of thermal plants with water norms: https://www.manthan-india.org/wp-content/uploads/pdf/Water-Use-Norms-Violations-Summary.pdf
- CEA CO₂ Baseline Database 2023-24 (weighted average 0.727 t CO₂/MWh), summary: https://solarquarter.com/2025/01/06/co2-baseline-database-highlights-indias-progress-in-renewable-energy-and-emission-reduction-cea/ and CEA user guide: https://cea.nic.in/wp-content/uploads/baseline/2026/09/User_Guide__Version_22.0.pdf
- Rubix Data Sciences report on Indian data centres (1.5 GW to 6.5 GW, 150 to 359 billion litres): https://cxotoday.com/hardware/data-centre-boom-indias-capacity-to-quadruple-to-6-5-gw-by-2030-finds-rubix-data-sciences/
- Climate Fact Checks, water cost of India's data centres: https://climatefactchecks.org/the-hidden-water-cost-of-indias-race-to-become-an-ai-superpower/
- Business Standard, Macquarie on Mumbai and Chennai shares: https://www.business-standard.com/industry/news/india-s-data-centre-capacity-to-double-by-2027-rise-5x-by-2030-macquarie-125102801409_1.html
- Ministry of Power, time-of-day tariff (Lok Sabha answer, 20 Jul 2023): https://eparlib.nic.in/bitstream/123456789/2504104/1/AU41.pdf ; news: https://www.energetica-india.net/news/government-amends-electricity-rules-and-introduces-tod-tariff ; draft deadline change: https://thedailybrief.zerodha.com/p/the-new-rules-of-paying-for-electricity
- CPHEEO 135 litres per person per day (Lok Sabha answer): https://eparlib.nic.in/bitstream/123456789/978296/1/AU739.pdf
- CSEP Electricity and Carbon Tracker (national 5-minute generation by source): https://carbontracker.in/
- Electricity Maps data access (hourly data via paid API): https://developers.thegreenwebfoundation.org/co2js/data/electricity-maps/
- AI Energy Score: https://www.esgtoday.com/salesforce-partners-launch-energy-ratings-for-ai-models/
- CATS: https://github.com/GreenScheduler/cats ; CarbonScaler: https://github.com/umassos/CarbonScaler ; WaterWise: https://arxiv.org/html/2501.17944v2 ; CarbonPilot: https://lablab.ai/submissions/es61wc6hs8lkp0nlnna56guw
- Water stress weighting: *Not All Water Consumption Is Equal*, https://arxiv.org/html/2506.22773v2 ; WRI Aqueduct: https://www.wri.org/aqueduct
- Zeus (PyTorch blog): https://pytorch.org/blog/zeus/ ; Perseus: https://arxiv.org/abs/2312.06902
- Stull (2011), wet-bulb from temperature and humidity; Open-Meteo: https://open-meteo.com
- From the team's earlier research, re-check before quoting in the video: SEBI BRSR Core circular (12 Jul 2023), EU Energy Efficiency Directive 2023/1791 Article 12, ENERGY STAR score technical reference.
