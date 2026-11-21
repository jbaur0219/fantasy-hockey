#!/usr/bin/env python3
"""
LEAGUE SCOREBOARD (READ-ONLY): every matchup in the league this week, for the Matchups tab.

For each matchup: both teams' points so far, their points on each day, the projected final and the win chance
(same model as your own matchup on Today), and how many player-games each side has left. Also tonight's NHL game for
every team, so the page can show who plays tonight on each roster. If ESPN sends per-player points for today or this
week (rosterForCurrentScoringPeriod / rosterForMatchupPeriod), those are passed on too; the page works without them.

  {"mp": 7, "dates": ["2026-11-16", ...], "labels": ["Mon Nov 16", ...], "today": 4,
   "games": [{"a": team id, "b": team id, "as": pts, "bs": pts, "ap": proj, "bp": proj, "pa": win chance of a,
              "ad": [pts per day], "bd": [...], "al": games left a, "bl": games left b}],
   "tn": {"EDM": [puck drop ms, "CAR", 0 = away / 1 = home]},
   "pt": {player id: points today}, "pw": {player id: points this week},
   "dp": {day index: {team id: [[player id, slot, points, name, "POS", "TM"], ...]}}}    each past day's real lineup
slot is F / D / G / UTIL (counted) or BN / IR (did not count). A player is listed when he scored or was in the lineup.
"""
import math

import analyze as A
import dashboard as D


def _r1(x):
    return round(float(x or 0), 1)


def _player_pts(side, key):
    out = {}
    for e in ((side.get(key) or {}).get("entries") or []):
        pid = e.get("playerId")
        pe = e.get("playerPoolEntry") or {}
        v = pe.get("appliedStatTotal")
        if pid is not None and v is not None:
            out[str(pid)] = _r1(v)
    return out


def _entry_row(e, season, abbr):
    """[player id, slot, points, name, position, team] for one roster entry of one past day, or None."""
    pe = e.get("playerPoolEntry") or {}
    pl = pe.get("player") or {}
    pid = e.get("playerId", pl.get("id"))
    if pid is None:
        return None
    slot = A.slot_name(e.get("lineupSlotId"))
    v = pe.get("appliedStatTotal")
    pts = _r1(v)
    if not pts and slot in ("BN", "IR"):
        return None                                  # sat on the bench and scored nothing: not worth listing
    q = A.parse_player(pl, season, slot=slot) if pl else {"name": "?", "pos": "?", "team_id": None}
    return [pid, slot, pts, q.get("name", "?"), q.get("pos", "?"), abbr.get(q.get("team_id"), "?")]


def past_lineups(cfg, league, mp, start, today, abbr, fetch=None):
    """Each finished day of this matchup week: every team's real lineup that day (who was in a counting slot, who was
    on the bench) and what each player scored. One ESPN request per day. A day that cannot be read is left out and the
    page falls back to game logs for it."""
    fetch = fetch or A.espn_get
    base = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{cfg['season']}/segments/0/leagues/{cfg['league']}"
    out = {}
    for i in range(0, today):
        try:
            js = fetch(base, cfg["cookies"], params=[("view", "mMatchup"), ("view", "mMatchupScore"), ("scoringPeriodId", start + i)])
        except (Exception, SystemExit) as e:         # an extra: one bad day never breaks the build
            print(f"  lineup for day {i + 1} skipped ({type(e).__name__}: {e})")
            continue
        day = {}
        for m in (js.get("schedule") or []):
            if m.get("matchupPeriodId") != mp:
                continue
            for side in (m.get("home") or {}, m.get("away") or {}):
                ents = (side.get("rosterForCurrentScoringPeriod") or {}).get("entries") or []
                rows = [r for r in (_entry_row(e, cfg["season"], abbr) for e in ents) if r]
                if side.get("teamId") is not None and ents:
                    day[str(side["teamId"])] = rows
        if day:
            out[str(i)] = day
    return out


def tonight(data, sp):
    abbr, games = D.schedule_maps(data["schedules"])
    tn = {}
    for tid, gl in games.items():
        for g in gl.get(str(sp), []):
            if not g.get("date"):
                continue
            home = g.get("homeProTeamId") == tid
            opp = g.get("awayProTeamId") if home else g.get("homeProTeamId")
            tn[abbr.get(tid, "?")] = [g["date"], abbr.get(opp, "?"), 1 if home else 0]
            break
    return tn


def build(cfg, data, league, standings, now_ms):
    season = cfg["season"]
    abbr, games = D.schedule_maps(data["schedules"])
    sp = data["roster"].get("scoringPeriodId", 1)
    mp = (league.get("status") or {}).get("currentMatchupPeriod")
    rosters = {t.get("id"): D.roster_players(t, season, abbr) for t in data["roster"].get("teams", [])}
    cur = [m for m in league.get("schedule", []) if m.get("matchupPeriodId") == mp and m.get("home") and m.get("away")]
    if not cur:
        return None
    length = D.matchup_length(league, mp)
    start, end = D.matchup_periods(cur[0], mp, length)
    clock = D.day_clock_games(games, start, length, now_ms)
    left_periods = list(range(max(sp, start), end + 1))

    def games_left(tid):
        n = 0
        for p in rosters.get(tid, []):
            if D.A.slot_name(p["slot"]) == "IR" or p["injury"] in D.A.BAD_INJURY:
                continue
            n += sum(len(D.games_on(games, p["team_id"], s, now_ms)) for s in left_periods)
        return n

    out, pt, pw = [], {}, {}
    for m in cur:
        a, b = m["home"], m["away"]
        ta, tb = a.get("teamId"), b.get("teamId")
        mu_a, var_a = D.expected_remaining(rosters.get(ta, []), left_periods, games, now_ms, standings)
        mu_b, var_b = D.expected_remaining(rosters.get(tb, []), left_periods, games, now_ms, standings)
        sa, sb = D.side_points(a), D.side_points(b)
        sd = math.sqrt(var_a + var_b) or 1.0
        pa = D.clamp(D.norm_cdf((sa + mu_a - sb - mu_b) / sd), 0.01, 0.99) if left_periods else (1.0 if sa > sb else 0.0 if sb > sa else 0.5)

        def daily(side):
            by = side.get("pointsByScoringPeriod") or {}
            return [_r1(by.get(str(s))) if str(s) in by else None for s in range(start, end + 1)]

        out.append({"a": ta, "b": tb, "as": _r1(sa), "bs": _r1(sb), "ap": _r1(sa + mu_a), "bp": _r1(sb + mu_b),
                    "pa": round(pa, 3), "ad": daily(a), "bd": daily(b), "al": games_left(ta), "bl": games_left(tb)})
        for side in (a, b):
            pt.update(_player_pts(side, "rosterForCurrentScoringPeriod"))
            pw.update(_player_pts(side, "rosterForMatchupPeriod"))

    me = cfg["team"]
    out.sort(key=lambda g: (0 if me in (g["a"], g["b"]) else 1, abs(g["pa"] - 0.5)))    # yours first, then closest
    today = max(0, min(sp - start, length - 1))
    try:
        dp = past_lineups(cfg, league, mp, start, today, abbr)
    except Exception as e:
        print(f"  past lineups skipped ({type(e).__name__}: {e})")
        dp = {}
    return {"mp": mp, "dates": clock["dates"], "labels": clock["labels"], "today": today,
            "games": out, "tn": tonight(data, sp), "pt": pt, "pw": pw, "done": not left_periods, "dp": dp}
