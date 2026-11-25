# Advice changes waiting for review (branch `advice-review-2026-11-25`)

Everything here changes what the plan suggests, so it stays off `main` until you approve it. UI and infrastructure
work from the same night is already live (see the end).

## What changes, in plain English

| Fix | What you would notice |
|---|---|
| A1 Goalie adds can replace a spare defenseman | When a goalie slot sits empty and a 6th defenseman never plays, the plan can now swap them. Before, a goalie add could only replace a forward or goalie. |
| A3 Drops ranked by lineup points lost | A player whose games all sit on your bench (position full those days) now counts as a cheap drop. This is the Andersson/Yamamoto pattern. The search also still tries the old "cheapest by his own points" list, so it never looks at fewer drops than before. |
| A4/A6 Reasons quote the numbers the plan used | No more "Brown 1.5 a game vs Smith 1.5 a game" for a +1.8 move: the line shows the per-game values after opponents, home ice and start chance. |
| C3 Dropping an injured star is no longer free | An OUT / IR / suspended player used to cost nothing to drop. With no open IR spot, the plan could drop an injured star for a one-week stream. His cost is now what a healthy him would cost times how much of it you likely get back (OUT 50%, IR 25%, suspended 75%). Stream-level injured players still cost nothing. IR moves are unchanged. |
| B1 No 50% start floor for your goalies | Your goalies' start chance was floored at 50% (Hill 45% -> 50%, a 30% backup -> 50%), so free-agent goalies looked worse and your win chance was a bit high. |
| B2 Today's starters apply to today | Between midnight and ESPN's overnight rollover, a confirmed benched goalie could keep a projection. |
| Scoring weights | Luck adjustment and goalie values use the league's own goal and win points (same numbers for your league). |

## Evidence

**Rule tests.** `tests/test_review_*.py` hold one test per bug that asserts the correct behaviour. On `main` they are
marked expected failures (9 of them); on this branch 7 pass. Full suite: 147 passed, 2 expected failures (A2, B6, both
still open, see below).

**Backtest of real logged moves** (`python tools/backtest.py`, repo copy of the history, 16 moves, 10 scored). It
cannot replay old weeks with the new code (the raw ESPN inputs for those builds were not saved in the repo, and this
sandbox cannot reach ESPN), so it measures the bars, not this branch:
- Skater moves: +17.5 actual vs +15.6 expected (8 of 9 ahead). Goalie moves: 1 scored, -6.6 (Tolopilo for Hill).
- Every bar: hold, not enough data (about 29 more scored moves needed next to each bar before the report will move one).

**Simulated weeks** (300 synthetic weeks, same inputs through `main` and this branch, `core.plan` only):
- Weeks with no injured player (131): the plan changed in 4, this-week points -0.01 on average (1 better, 2 worse). A1
  and A3 rarely matter in random rosters; they are aimed at specific patterns the tests reproduce.
- Weeks with an injured player (169): this branch gives up 0.17 this-week points a week on average, because it keeps
  injured good players instead of dropping them (C3). In the worst case (a 3.5-a-game star OUT all week, no IR spot)
  the plan made one fewer stream and scored 6.3 fewer points that week. The simulation only counts this week, so it
  cannot show what keeping the star is worth when he returns. This is the call to review: C3 trades some this-week
  points for not losing a star.
- Goalie adds that replaced a spare defenseman: 0 on `main`, 10 on this branch.

## Still open (not on this branch)
- A2: the plan can't stream the same spot twice in a week (add A Monday, drop A for B Wednesday). A bigger optimizer
  change; it would use more of the weekly moves.
- B6: matchup days when ESPN has no points yet (Monday before the first game). Unverified against ESPN; a wrong fix could
  shift the week, so left alone.
- B8-B10, C6, C7: small or design questions, listed in the review notes.

## Already live on `main` the same night
Backtest harness (private report each build), league settings from ESPN with a platform adapter, track-record scoring
fixes, and accounts / sign-in (off until AUTH=1).
