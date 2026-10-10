# thirst

**Run your GPU job at the right hour and the right speed, so it takes less water and CO₂. Get a signed receipt that proves it.**

Thirst is a command-line tool for people who train AI models on NVIDIA GPUs in India. It plans when to start a job and how much to lower the GPU power limit, runs your command on that plan, measures the real GPU energy, and sends a receipt to your lab's page on the Thirst leaderboard.

```bash
pip install thirst

thirst register --name "CSE GPU Lab" --city Chennai --cooling room_ac --gpus 4
thirst plan --hours 6 --deadline "2026-10-12 09:00" --pausable
thirst run  --hours 6 --deadline "2026-10-12 09:00" --pausable -- python train.py
```

| Command | What it does |
|---|---|
| `thirst register` | Creates your lab's site once and saves its key to `~/.thirst/config.toml` |
| `thirst plan` | Shows the best start time and power cap, with savings as ranges |
| `thirst run -- <cmd>` | Waits, caps the GPU, runs your command, pauses or resumes it, restores the power limit, posts a receipt |
| `thirst run --modelled` | No NVIDIA GPU: estimates energy instead and labels it "modelled" |
| `thirst doctor` | Checks GPU, power-cap permission, clock and API |
| `thirst sync` | Sends receipts that were saved while offline |

Energy is **measured** from the GPU (NVML). Water and CO₂ are **modelled** from it, using Indian grid and weather data, and every receipt says which is which.

Project, website and the science: https://github.com/Neal006/Thirst · MIT licence.
