# Submission checklist (plan 7.10, TRD §17)

Submit Sun 11 Oct, 14:00 to 16:00 IST. Status as of 2026-10-11 ~15:30 IST.
✅ done · ⬜ a person must do it · ⚠️ partly done.

| # | Item | Status | Evidence / how |
|---|---|---|---|
| 7.10.a | Every team member registered and on the team | ⬜ | Check on the hackathon site **before** submitting |
| 7.10.b | Secret scan of the whole history | ⚠️ | ✅ Full-history scan done: gitleaks 8.28.0 over all 54 commits on every branch and the working tree, **no leaks found** ([`gitleaks_full_history.txt`](gitleaks_full_history.txt)). gitleaks also runs in CI on every push and PR. ⬜ Still to do: delete the PyPI token that was pasted in chat (it never reached git, so no scan can find it). |
| 7.10.c | Repo public, MIT licence, commits from 8 Oct onwards | ⬜ | `LICENSE` is present. Flip it: `gh repo edit Neal006/Thirst --visibility public --accept-visibility-change-consequences` |
| 7.10.d | README lists the AI coding tools, credits and licences | ✅ | README "AI tools used" and "Credits" sections |
| 7.10.e | Live URL works signed-out and on a phone | ✅ | Playwright (desktop + 360 px phone) against the live site after the last deploy: 74 passed, 4 skipped (data-dependent), 1 flaky that passed 12/12 on re-run. The owner also ran [`USER_TEST_GUIDE.md`](USER_TEST_GUIDE.md) end to end. Re-run with `npm --prefix web run e2e`. After `feat/web-ui-accessibility` merges, Deploy runs this suite on every deploy. On that branch, against a production build with the local API: 82 passed, 9 skipped, 0 failed. |
| 7.10.f | Video under 3:00, unlisted, plays signed-out, AWS on screen and named out loud | ⬜ | Brief with the must-show feature checklist: [`VIDEO_BRIEF.md`](VIDEO_BRIEF.md); shot-by-shot script with voice lines, captions and checks: [`VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md) |
| 7.10.g | Writeup has all sections; blog published and linked | ⚠️ | Writeup: [`docs/WRITEUP.md`](WRITEUP.md). Blog (900 to 1,200 words) still to publish; then add its link to the writeup and the README. |
| 7.10.h | Billing checked, screenshot saved | ⚠️ | Cost Explorer, 1 to 11 Oct: $0.00 unblended. Take the screenshot in the console. Budget `thirst-monthly` ($50) alerts are on. |
| 7.10.i | Submit, then re-open the page to confirm it saved | ⬜ | |
| 7.10.j | After submitting: leave the stack running, don't wipe data, keep budget alerts | ⬜ | Don't run `seed.py --wipe-simulated` or delete the stack until judging ends |

## PRD §8.1 metrics

| Metric | Target | Status |
|---|---|---|
| `POST /plan` p95 | < 2000 ms | ✅ 383 ms over 50 live calls, 0 failures (`docs/bench_plan.txt`) |
| `powercap_sweep.json` measured for our GPU | measured | ⬜ needs `thirst sweep` on a desktop NVIDIA GPU (laptops usually block power limits) |
| ≥ 1 receipt with method `nvml_*` on the board | ≥ 1 | ⬜ needs one real `thirst run` on a GPU machine |
| Setup timer (7.6) | < 15 min | ⚠️ about 5 min from a fresh venv to the first receipt (Windows laptop, 2026-10-11), and 70 s on a second machine against the local API (`FIXLIST.md`). The formal timer with the live API and a phone is still open |
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
- Placeholder power-cap data: every plan picks 70%, and all 11 trade-off points are the same. After `feat/web-ui-accessibility` merges, the planner hides the slider and says why, until the sweep is measured.
- The seven small CLI wording/UX issues from the live walkthroughs are fixed and published in `thirst` 0.3.2 (PR #15, [`FIXLIST.md`](FIXLIST.md)).
- PyPI `thirst` 0.3.2 is published (PR #7 fixes, the 31 new GPUs, the walkthrough fixes) through Trusted Publishing: future releases are `git tag cli-vX.Y.Z && git push origin cli-vX.Y.Z`, no token.
