# Goalie adds: betting lines and reading the matchup (2026-11-27)

The user's question, with screenshots of "Add Brossoit, drop Adin Hill (+1.0 pts)" and the game page's "LAK favored,
51% to win": "I don't really love how it's telling me to add a goalie that isn't favored to win... If I am up a lot and
have a good chance to win, I don't need to pick up a goalie and make a risky move like that."

## What the code did before

A goalie's points for a game = his outlook + win points x (win chance - his team's usual strength), times his start
chance. The win chance came only from the standings (points %, log5) plus 3 points of home ice and a small save %
nudge. The betting line was only shown on the game page; the plan never saw it.

## Check against the live line (ESPN scoreboard, 2026-11-27, 12 games with a line)

Home team's win chance, standings model vs the no-vig DraftKings line:

| Game | Line | Model | Model - line |
|---|---|---|---|
| DAL @ STL | 0.46 | 0.44 | -0.01 |
| OTT @ TB | 0.56 | 0.52 | -0.04 |
| VAN @ PHI | 0.68 | 0.63 | -0.05 |
| FLA @ WSH | 0.49 | 0.41 | -0.08 |
| DET @ CBJ | 0.54 | 0.50 | -0.04 |
| COL @ MIN | 0.53 | 0.65 | +0.11 |
| **LA @ ANA** | **0.49** | **0.60** | **+0.12** |
| VGK @ SJ | 0.34 | 0.31 | -0.03 |
| NYR @ CHI | 0.39 | 0.37 | -0.02 |
| WPG @ NYI | 0.53 | 0.56 | +0.02 |
| PIT @ BUF | 0.55 | 0.70 | +0.15 |
| SEA @ EDM | 0.66 | 0.71 | +0.05 |

Average miss 6 points of win chance, worst 15. The user's game was one of the worst: the model gave Brossoit's ANA 60%,
the line 49% (LA's poor record, 18 points in 22 games, hides a team the market rates). With 4 points a win that is
about 0.45 of the move's +1.0 coming from a win chance the market doesn't believe. One slate is a small sample, but
the direction is clear and the line is the better-informed number (it already prices tonight's goalies).

Also checked: ESPN lists Carter Hart, not Hill, as VGK's expected starter today, so dropping Hill today does not throw
away a Hill start (the open question from this morning).

## Change 1: use the betting line when there is one (`odds.py`)

Reads ESPN's public NHL scoreboard for today and tomorrow (`odds[0].moneyline.home/away.close.odds`, verified live),
removes the vig and uses that as the goalie's win chance. Games without a line (later days, games under way, ESPN
not reachable) keep the standings model, so nothing breaks. Used in the plan's values (`streams.py`) and the goalie
start/bench calls (`goalies.py`).

## Change 2: read the matchup before a goalie add (`core.ahead_hold`)

When you're already 85%+ to win (the plan's own projection, before any move), a goalie add only stays on the list if
it either raises your win chance by 1 point or more, or is a clear long-term upgrade (3+ more points than the goalie
you drop over the next three weeks). The win-chance change counts the move's points and the extra swing of every
goalie start it adds (a goalie night swings about 6 points; extra swing hurts when you're ahead). A move that stays
for the long term says so in its reason: "You're 9x% to win this week already, so this move is about the weeks after,
not this matchup." Held moves go to the private "small moves" log, so the backtest can check the rule later.

Only goalie adds are checked; skater moves are unchanged. Nothing changes when the week is close or you're behind
(taking more swings when far behind is a possible follow-up, not built).

What this means for the Brossoit move: with the line, its this-week value drops by about 0.45. If you're 85%+ to win,
it would only stay if the long-term edge holds (the card said 1.30 vs 0.98 a game, ANA 10 games vs VGK 8 over the
next three weeks: about 5 points), in which case it stays and says it's for the weeks after.

## Not changed

A higher bar for goalie moves: only one goalie move has been scored (Tolopilo for Hill, -6.6), and the backtest rule
needs 15+ before a bar moves.

## Tests

`tests/test_goalie_odds_and_lead.py` (9 tests, the scoreboard fixture is the live LA @ ANA shape). Full suite: 190
passed. A full replayed build (Nov 20 snapshot, no lines in it) gives the same plan as main.
