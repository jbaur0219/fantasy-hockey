#!/usr/bin/env python3
"""
Weekly PLANNER tab (READ-ONLY).

Adds a "Planner" tab to the website:
  - Your week at a glance: for each of the next 7 days, how many of your skaters/goalies play and how many
    lineup slots would sit empty (those are the best days for streaming pickups)
  - Games per team: a heat map of who plays when, with totals and back-to-backs
  - Streaming goalies: the best free-agent goalies for each day (win chance + expected points)
  - Moves and waivers: adds used this matchup and waiver timing

Everything is computed from ESPN's schedule, the NHL standings and the player data already loaded.
"""
from datetime import datetime, timedelta

import analyze as A
import dashboard as D
import starters as S

STREAM_MIN_START = 0.3      # only free-agent goalies who start at least this often
STREAM_POOL = 25            # look at the best 25 free-agent goalies
MOVE_LIMIT = 7              # replaced by the league's own limit on every build (budget())


def _grid(schedules, sp, abbr, games, now_ms, ndays):
    teams = []
    for tid, ab in abbr.items():
        if not ab or ab in ("FA", "?"):
            continue
        row = []
        for i in range(ndays):
            gl = games.get(tid, {}).get(str(sp + i), [])
            if gl:
                g = gl[0]
                home = g.get("homeProTeamId") == tid
                opp = abbr.get(g.get("awayProTeamId") if home else g.get("homeProTeamId"), "?")
                row.append([opp, 1 if home else 0])
            else:
                row.append(None)
        teams.append({"tm": ab, "g": row})
    return teams


def _stream(site_data, sp, abbr, games, standings, now_ms, ndays):
    tid_of = {ab: tid for tid, ab in abbr.items()}
    clock = D.day_clock_games(games, sp, ndays, now_ms)
    pool = [p for p in site_data["fas"] if p["grp"] == "G" and p["inj"] not in A.BAD_INJURY]
    pool = sorted(pool, key=lambda p: -(p["out"] or 0))[:STREAM_POOL]
    out = []
    for p in pool:
        if (p.get("sp") or 0) < STREAM_MIN_START:
            continue
        tid = tid_of.get(p["tm"])
        s_me = D.team_strength(p["tm"], standings)
        for i in range(ndays):
            if D.day_locked(clock, i, now_ms):
                continue                                        # the day has started: nobody can be added for it
            for g in games.get(tid, {}).get(str(sp + i), [])[:1]:
                home = g.get("homeProTeamId") == tid
                opp = abbr.get(g.get("awayProTeamId") if home else g.get("homeProTeamId"), "?")
                pw = D.log5(s_me, D.team_strength(opp, standings)) + (D.HOME_ICE if home else -D.HOME_ICE)
                if p.get("svp") and p["gp"] >= 5:
                    pw += D.clamp((p["svp"] - 0.905) * 2.0, -0.05, 0.05)
                pw = D.clamp(pw, 0.15, 0.85)
                e = (p["out"] or 0) + 4 * (pw - s_me)
                st = None
                if i == 0 and S.STATE["by_team"].get(p["tm"]):
                    starter = S.STATE["by_team"][p["tm"]]
                    if S.E.norm(starter["name"]) != S.E.norm(p["n"]):
                        continue                                # someone else is in net today
                    st = starter["status"]
                out.append({"i": i, "id": p["id"], "n": p["n"], "o": opp, "h": 1 if home else 0,
                            "p": round(pw, 3), "e": round(e, 2), "st": st})
    return out


def _moves_used(league, my_id):
    return D.move_budget(league, my_id)["used"]


DAYS_LEFT = {"n": None}      # days left in the matchup, set by build.py once the matchup is known (per-day limits)


def budget(league, my_id):
    """This league's own add limit and what is left this matchup (dashboard.move_budget). Also keeps MOVE_LIMIT,
    which a few older callers read, in step with the league's rule."""
    global MOVE_LIMIT
    b = D.move_budget(league, my_id, days_left=DAYS_LEFT["n"])
    MOVE_LIMIT = b["limit"]
    return b


def build(cfg, data, league, standings, now_ms, site_data):
    sp = data["roster"].get("scoringPeriodId", 1)
    abbr, games = D.schedule_maps(data["schedules"])
    m = site_data.get("matchup")
    ndays = max(1, min(int(m["days_left"]) if m else 7, D.MAX_DAYS))       # only the rest of THIS matchup week (through Sunday)
    days = D.day_clock_games(games, sp, ndays, now_ms)["labels"]
    bg = budget(league, cfg["team"])
    return {"days": days, "teams": _grid(data["schedules"], sp, abbr, games, now_ms, ndays),
            "stream": _stream(site_data, sp, abbr, games, standings, now_ms, ndays),
            "moves_used": bg["used"], "limit": bg["limit"], "unlimited": bg["unlimited"], "limit_known": bg["known"]}
