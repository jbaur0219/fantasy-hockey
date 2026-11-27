# Reading the matchup better: opponent streams and taking chances when behind (2026-11-27)

User, after the Scout tab was dropped: "I like the idea of having it on the back end helping it with the risk idea and
taking more chances when im behind. Like just using this features logic on the back end to make the risk feature more
accurate."

## What changes
1. **The plan's read of the matchup counts the opponent's streams.** `scout.opponent_upside` finds the best free agents
   for the opponent's open lineup spots (one add a day, their adds left by the league rule, 1.0+ pts each). Half of it
   (`core.OPP_STREAM_SHARE = 0.5`) is taken off your lead, and its games add swing. Only the plan's internal risk read
   uses this; the win chance you see on Today is unchanged, and notes quote that number.
2. **When you're well behind (under 30%), small moves that add games are shown.** A move under the show bar but worth
   0.3+ net points stays on the list if it raises your win chance by 1+ point (`core.behind_keep`). Its reason ends:
   "You're N% to win this week, so a move that adds games is worth it: you need the chances more than the safe points."
   Producers keep their own drop bar; IR moves and the "well ahead" goalie check are unchanged.

## Evidence
- Replayed Nov 20 snapshot (you 96%): opponent could stream +5.8; the plan's read 93%; same plan as main (Rinzel for
  Zegras Sat, Nazar for Andersson Sun, +4.7).
- Same snapshot with the opponent's projection pushed up 38 / 50 / 60 points (read 30% / 12% / 4%): same plan. The
  snapshot had no small moves left off the list, so there was nothing for the behind rule to add.
- How much a 0.6-pt, 2-game move helps when behind (sd 15): 15 down +1.5 points of win chance (kept), 25 down +0.8
  (not kept: the week is close to lost and half a point doesn't change it).
- Tests: `tests/test_behind_and_opponent.py` (6), `tests/test_scout.py` (18).

## Not known
- The 0.5 share is a guess. Check it once a few weeks of opponents' real adds can be compared with the upside.
- The 30% / 1-point / 0.3-pt numbers are judgment calls, not measured; the backtest needs 15+ scored behind-moves.
