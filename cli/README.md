# thirst

**Run your GPU job at the right hour and the right speed, so it takes less water and CO₂. Get a signed receipt that proves it.**

Thirst is a command-line tool for people who train AI models on NVIDIA GPUs in India. It does four things:
- plans when to start a job and how far to lower the GPU power limit
- runs your command on that plan
- measures the real GPU energy
- sends a signed receipt to your lab's page on the [Thirst leaderboard](https://main.dzxkrtlc7xqfx.amplifyapp.com/leaderboard)

```bash
pip install thirst                      # Python 3.10+

thirst doctor                           # check GPU, power-cap permission, clock and API
thirst register --name "CSE GPU Lab" --city Chennai --cooling room_ac --gpus 4
thirst plan --hours 6 --deadline "2026-10-12 09:00" --pausable
thirst run  --hours 6 --deadline "2026-10-12 09:00" --pausable -- python train.py
```

A receipt looks like this (your numbers come from your GPU and the planner):

```text
Thirst receipt j_tksft2nswiku
  Ran      11 Oct 02:00 to 08:40 IST on 2 x NVIDIA GeForce RTX 4090, cap 70%
  Energy   3.89 kWh GPU (measured)
  Water    16.5 L (modelled); if you had started right away: 21.0 L
  Carbon   4.81 kg CO2 (modelled); if you had started right away: 6.12 kg
  Capture  You took 86% of the possible saving
  Score    Site score 82 (Provisional)
```

## Commands

| Command | What it does |
|---|---|
| `thirst register` | Creates your lab's site once and saves its key to `~/.thirst/config.toml` (never printed). `--cooling room_ac\|air_chiller\|evaporative`. Add `--private` to stay off the leaderboard. |
| `thirst plan` | Shows the best start time and power cap, with savings as ranges. `--alpha 0` means least CO₂, `1` means least water. `--json` prints the raw answer. |
| `thirst run -- <cmd>` | Waits for the planned hour, caps the GPU, runs your command, pauses and resumes it if planned, **always restores the power limit** (also on Ctrl-C, a dropped SSH session or a crash), then posts a receipt |
| `thirst run --dry-run` | Shows what would happen, starts nothing |
| `thirst run --now` | Starts right away (still measured, still a receipt) |
| `thirst run --no-cap` | Never touches the power limit (laptops usually don't allow it); energy is still measured |
| `thirst run --modelled` | Estimates energy instead of reading the GPU and labels it "modelled". It uses the detected GPU. With no NVIDIA GPU add `--gpu-model <id> --gpus <n>` (ids are on the [Assumptions page](https://main.dzxkrtlc7xqfx.amplifyapp.com/assumptions)). |
| `thirst doctor` / `thirst doctor --restore` | Checks the setup / puts back a power limit left behind by a crash |
| `thirst sync` | Sends receipts that were saved while offline |
| `thirst receipt show <job_id>` | Prints a saved receipt again |
| `thirst sweep` | Measures your GPU's speed and energy at each power level (`pip install "thirst[sweep]"`, needs PyTorch) |

Energy is **measured** from the GPU (NVML). Water and CO₂ are **modelled** from it using Indian grid and weather data, and every receipt says which is which. The receipt is saved on disk before it is sent, so nothing is lost if the network drops: run `thirst sync` later.

## Environment variables

- `THIRST_HOME`: config, receipts and logs folder (default `~/.thirst`)
- `THIRST_API_URL`: another API, which must be `https://` except on localhost
- `THIRST_WEB_URL`: base URL for receipt links

## Good to know

- **Windows** and multi-GPU distributed launchers (`torchrun`, DeepSpeed, MPI) run without pauses. The CLI says so when it happens.
- **Laptop GPUs** usually block power-limit changes. `thirst doctor` reports it, and `--no-cap` runs the job measured but uncapped.
- **Exit codes:**

  | Code | Meaning |
  |---|---|
  | your command's code | normal run |
  | 2 | bad arguments or command not found |
  | 3 | config problem (e.g. not registered) |
  | 4 | API problem |
  | 5 | GPU problem, including a power limit that could not be restored |
  | 130 | Ctrl-C |

Step-by-step test of the CLI and website: [USER_TEST_GUIDE.md](https://github.com/Neal006/Thirst/blob/main/docs/USER_TEST_GUIDE.md).
Project, website and the science: https://github.com/Neal006/Thirst · MIT licence.
