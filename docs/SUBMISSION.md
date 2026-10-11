# Submission checklist (plan 7.10, TRD §17)

Submit Sun 11 Oct, 14:00 to 16:00 IST. Status as of 2026-10-11 ~13:00 IST.
✅ done · ⬜ a person must do it · ⚠️ partly done.

| # | Item | Status | Evidence / how |
|---|---|---|---|
| 7.10.a | Every team member registered and on the team | ⬜ | Check on the hackathon site **before** submitting |
| 7.10.b | Secret scan of the whole history | ⚠️ | gitleaks runs in CI on every push and PR. A full-history scan has not been run: `gitleaks detect --source . --log-opts="--all"`. Also delete the PyPI token that was pasted in chat. |
| 7.10.c | Repo public, MIT licence, commits from 8 Oct onwards | ⬜ | `LICENSE` is present. Flip it: `gh repo edit Neal006/Thirst --visibility public --accept-visibility-change-consequences` |
| 7.10.d | README lists the AI coding tools, credits and licences | ✅ | README "AI tools used" and "Credits" sections |
| 7.10.e | Live URL works signed-out and on a phone | ✅ | Playwright suite (desktop + 360 px phone) against the live API: 77 passed, 2 skipped by design. Re-run with `npm --prefix web run e2e`. |
| 7.10.f | Video under 3:00, unlisted, plays signed-out, AWS on screen and named out loud | ⬜ | Storyboard in `docs/implementation-plan/07-integration-qa-release.md` §7.8 |
| 7.10.g | Writeup has all sections; blog published and linked | ⚠️ | Writeup: [`docs/WRITEUP.md`](WRITEUP.md). Blog (900 to 1,200 words) still to publish; then add its link to the writeup and the README. |
| 7.10.h | Billing checked, screenshot saved | ⚠️ | Cost Explorer, 1 to 11 Oct: $0.00 unblended. Take the screenshot in the console. Budget `thirst-monthly` ($50) alerts are on. |
| 7.10.i | Submit, then re-open the page to confirm it saved | ⬜ | |
| 7.10.j | After submitting: leave the stack running, don't wipe data, keep budget alerts | ⬜ | Don't run `seed.py --wipe-simulated` or delete the stack until judging ends |

## PRD §8.1 metrics

| Metric | Target | Status |
|---|---|---|
| `POST /plan` p95 | < 2000 ms | ✅ 463 ms over 50 live calls, 0 failures (`docs/bench_plan.txt`) |
| `powercap_sweep.json` measured for our GPU | measured | ⬜ needs `thirst sweep` on a desktop NVIDIA GPU (laptops usually block power limits) |
| ≥ 1 receipt with method `nvml_*` on the board | ≥ 1 | ⬜ needs one real `thirst run` on a GPU machine |
| Setup timer (7.6) | < 15 min | ⬜ not recorded in `docs/FIXLIST.md` |
| Cost on Sat | < $5 | ✅ $0.00 for the month so far |
| Video length | < 3:00 | ⬜ |

## Links for the form

- Live site: https://main.dzxkrtlc7xqfx.amplifyapp.com
- Repo: https://github.com/Neal006/Thirst
- CLI: https://pypi.org/project/thirst/
- Writeup: https://github.com/Neal006/Thirst/blob/main/docs/WRITEUP.md
- Video: _add_
- Blog: _add_

## Known gaps (also in issue #5)

- Bedrock access is blocked at the account level ("Operation not allowed" for every model). `/explain` returns the template until an AWS Support case clears it. Then set `BedrockModelId` in `samconfig.toml` and push to `main`.
- Placeholder power-cap data: every plan picks 70% and the trade-off slider has no visible effect until the sweep is measured.
- PyPI `thirst` 0.3.0 was published before the CLI review fixes (PR #7). Publishing 0.3.1 needs a new PyPI token or Trusted Publishing.
