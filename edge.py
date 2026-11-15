#!/usr/bin/env python3
"""
SCHEDULE EDGE (READ-ONLY): the weekly "who plays how much, against whom" matrix, per NHL team, with the best free
agent skaters on each team. Two windows: the rest of this matchup week, and next week (when the schedule is out).

Per team: games, home games, each opponent (with weak/avg/strong tag), and an edge score = sum over the games of the
same opponent/home multiplier the planner uses (so 3 easy games beat 3 average ones, and 4 games beat 3).
Never fails the build: any problem just skips the card.
"""
import analyze as A
import dashboard as D
import streams as STR
import streams2 as S2


def _window(data, standings, sp, ndays, fas, label, first_day):
    abbr, games = D.schedule_maps(data["schedules"])
    if not any(gl.get(str(sp + i)) for gl in games.values() for i in range(ndays)):
        return None
    clock = D.day_clock_games(games, sp, ndays, 0)
    best = {}
    for p in fas:
        if p["grp"] == "G" or not S2.add_ok(p):
            continue
        best.setdefault(p["tm"], []).append(p)
    rows = []
    for tid, ab in abbr.items():
        gl_total, home_n, edge, opps = 0, 0, 0.0, []
        for i in range(ndays):
            for g in games.get(tid, {}).get(str(sp + i), [])[:1]:
                home = g.get("homeProTeamId") == tid
                opp = abbr.get(g.get("awayProTeamId") if home else g.get("homeProTeamId"), "?")
                m, tag = STR._mult(ab, opp, home, standings)
                gl_total += 1
                home_n += 1 if home else 0
                edge += m
                opps.append({"d": clock["labels"][i].split()[0], "o": opp, "h": 1 if home else 0, "t": tag})
        if not gl_total:
            continue
        fa = sorted(best.get(ab, []), key=lambda p: -(p["out"] or 0))[:2]
        rows.append({"tm": ab, "g": gl_total, "home": home_n, "edge": round(edge, 2), "opps": opps,
                     "fa": [{"id": p["id"], "n": p["n"], "pos": p["pos"], "o": round(p["out"] or 0, 1),
                             "w": 1 if p.get("st") == "WAIVERS" else 0} for p in fa]})
    rows.sort(key=lambda r: (-r["edge"], r["tm"]))
    return {"label": label, "first": first_day, "days": [l.split()[0] for l in clock["labels"]], "rows": rows}


def build(cfg, data, league, standings, now_ms, site_data):
    m = site_data.get("matchup")
    if not m:
        return None
    sp = data["roster"].get("scoringPeriodId", 1)
    left = max(1, min(int(m["days_left"]), 7))
    out = []
    w1 = _window(data, standings, sp, left, site_data["fas"], "Rest of this week", "")
    if w1:
        out.append(w1)
    w2 = _window(data, standings, sp + left, 7, site_data["fas"], "Next week", "")
    if w2:
        out.append(w2)
    return out or None
