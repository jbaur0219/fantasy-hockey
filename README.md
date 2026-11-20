# Fantasy Hockey Manager

A read-only advisor for an ESPN fantasy hockey league. It reads the league, public NHL stats, MoneyPuck expected goals
and DailyFaceoff lines and goalie starts. Then it builds one phone-friendly page with the day's moves, the week's plan,
goalie calls, streams and trade ideas. It never adds, drops, trades or changes anything in ESPN.

## How it runs

- **Watcher** (`.github/workflows/watch.yml`, `watch.py`): one long job that checks every 10 minutes whether to
  rebuild. It rebuilds in the morning (with the push alert), 4 hours before the first game, at the first puck drop,
  and after the last game. Before it ends it starts the next watcher. It alerts your phone if the site goes 14 hours
  without updating.
- **Build** (`.github/workflows/daily.yml`, `build.py`): reads everything, builds `site/`, publishes it to GitHub Pages,
  and saves `plan_state.json`, `cache/` (the last good DailyFaceoff data) and `history/` (moves made or missed).
- **Preview**: run the build with `mode=preview` on a branch. It builds without publishing and saves the page and a
  snapshot of every web response to `preview/` on that branch.

## Where things are

| File | What it does |
|---|---|
| `analyze.py` | Reads ESPN, scores players in this league's points system, base outlook per game |
| `enrich.py`, `starters.py`, `roles.py` | NHL.com / MoneyPuck stats, today's starting goalies, line and power-play roles |
| `dashboard.py` | Matchup, schedule helpers, the daily add-lock clock, lineup alerts, standings |
| `streams.py` | Player values per day, drop and add rules, Streams and Swap lab data |
| `core.py` | **The one move plan** (gain, long-term cost, search, sticky plan), each move's confidence (Strong / Lean / Optional), its one-line reason and other drops for the Keep button, and the win-chance model |
| `longterm.py` | Long-term impact of a stream: per game with streaks taken out, the next 3 weeks of games, and the chance the dropped player gets claimed. Feeds the plan's long-term cost and the Long term section on moves and Try a swap |
| `keep.py` | Players you chose to keep this week (the Keep button sends them as the `keep` input; saved in `keep.json`) |
| `record.py` | Track record: scores every suggested move after its games (made and skipped), finals in `history/results.json` |
| `goalies.py` | Start / bench for each goalie, every day of the matchup |
| `gamelog.py` | Each player's recent games from ESPN (this league's points per game), saved as `site/gamelog.json` for the Game log tab and Compare |
| `gameplan.py`, `weekplan.py`, `planner.py`, `edge.py`, `playercard.py` | Data for the Game plan, week memory, planner, schedule table, player card |
| `site_builder.py` + `web/` | The page: `web/page.html`, `web/app.css`, `web/app.js`, with the data dropped in |
| `scheduler.py`, `watch.py`, `notify.py`, `pwa.py` | When to rebuild, the watcher, push alerts, phone-app files |
| `netcache.py`, `tools/`, `tests/` | Record and replay builds, compare two builds, phone-size smoke test, rule tests |

## Testing a change

```
FH_RECORD=snap.json.gz python build.py                    # a real build that also saves every web response
sh tools/replay.sh snap.json.gz plan_state.json out.html  # rebuild offline from it, exactly
python tools/compare.py before.html after.html             # page code + data differences
python tools/smoke.py out.html shots/                      # every tab at iPhone size, script errors, screenshots
python -m unittest discover tests
```

Secrets: `ESPN_2` and `SWID` (ESPN login cookies), `PUSH_CONFIG` (push alerts). The league and team default to
`LEAGUE_ID=557638258`, `TEAM_ID=1`. Scoring, lineup slots and the 9 F / 5 D / 2 G / 1 UTIL layout currently match
this league and are not yet read from ESPN for other leagues.
