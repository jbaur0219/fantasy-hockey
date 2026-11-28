#!/usr/bin/env python3
"""
TOMORROW'S ROSTER (READ-ONLY): once today's first puck has dropped, plan from the roster ESPN has for tomorrow.

Why (user, 2026-11-27): the app said "Move Necas to IR and add Colton Sissons" on Friday; the user did both after the
day's first game had started. ESPN filed them for Saturday: Saturday's lineup had Necas in an IR spot and Sissons on
the roster, but the current-day roster (what the build reads) still had Necas in a forward spot and no Sissons. So the
next build saw an open IR spot and an injured forward again and suggested "Add Jake McCabe, move Necas to IR", a move
the user had already made. Checked against the live league that evening (mRoster with scoringPeriodId = tomorrow,
and the FREEAGENT add of Sissons at 7:40 PM in mTransactions2).

What it does: when today is locked, read tomorrow's roster for your team (one request, the same view ESPN's roster page
loads for another date) and give the planners that roster: tomorrow's IR spots (a player you put in IR is in IR;
other slots stay today's, since some drop rules read BN),
players added since the lock included, players dropped since the lock left out. The page's own list of your players
(`mine`) keeps today's slots (the live game views read today's), gains the players who join tomorrow, and each player
gets `irn` = 1 when tomorrow has him in IR. If tomorrow can't be read, nothing changes.
"""
import copy

import analyze as A
import dashboard as D


def locked_today(data, now_ms):
    """True once today's first NHL game has started (no adds today in this league): plans start tomorrow."""
    sp = data["roster"].get("scoringPeriodId", 1)
    clock = D.day_clock(data["schedules"], sp, 1, now_ms)
    return D.day_locked(clock, 0, now_ms)


def fetch(cfg, sp, fetch=None):
    """Your team's roster entries for scoring period sp (ESPN keeps one lineup per day). None if unreadable."""
    fetch = fetch or A.espn_get
    url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{cfg['season']}/segments/0/leagues/{cfg['league']}"
    js = fetch(url, cfg["cookies"], params=[("view", "mRoster"), ("forTeamId", cfg["team"]), ("scoringPeriodId", sp)])
    for t in (js or {}).get("teams") or []:
        if t.get("id") == cfg["team"]:
            ents = (t.get("roster") or {}).get("entries")
            return ents if ents else None
    return None


def merged_data(data, team, entries):
    """A copy of `data` whose roster for `team` is tomorrow's: tomorrow's players and slots. A player on both days keeps
    today's player record (so his stats are read exactly as before); a player new tomorrow uses tomorrow's record."""
    out = dict(data)
    out["roster"] = copy.copy(data["roster"])
    teams = []
    for t in data["roster"].get("teams", []):
        if t.get("id") != team:
            teams.append(t)
            continue
        now = {e.get("playerId"): e for e in ((t.get("roster") or {}).get("entries") or [])}
        ents = []
        for e in entries:
            e2 = dict(e)
            old = now.get(e.get("playerId"))
            if old and old.get("playerPoolEntry"):
                e2["playerPoolEntry"] = old["playerPoolEntry"]
            ents.append(e2)
        t2 = dict(t)
        t2["roster"] = dict(t.get("roster") or {}, entries=ents)
        teams.append(t2)
    out["roster"]["teams"] = teams
    return out


def plan_roster(cfg, data, site_data, standings, slim, fetch_fn=None):
    """(plan mine, summary) for tomorrow, or (None, reason). Also updates site_data["mine"] in place: new players added
    (slot = tomorrow's, `nx` = 1) and `irn` = 1 on anyone tomorrow has in IR."""
    sp = data["roster"].get("scoringPeriodId", 1)
    ents = fetch(cfg, sp + 1, fetch_fn)
    if not ents:
        return None, "tomorrow's roster could not be read"
    raw, _ = A.build_players(merged_data(data, cfg["team"], ents), cfg)
    tom = {p["id"]: slim(p, standings) for p in raw}
    cur = {p["id"]: p for p in site_data.get("mine") or []}
    plan = []
    for pid, tp in tom.items():
        if pid in cur:
            q = dict(cur[pid])
            if "IR" in (tp["slot"], q["slot"]):     # only IR moves carry over; other slots stay today's (bench/start
                q["slot"] = tp["slot"]              # choices are the lineup's job, and some drop rules read BN)
            plan.append(q)
        else:
            plan.append(tp)
    added = [p for pid, p in tom.items() if pid not in cur]
    gone = [p for pid, p in cur.items() if pid not in tom]
    to_ir = [cur[pid] for pid, p in tom.items() if pid in cur and p["slot"] == "IR" and cur[pid]["slot"] != "IR"]
    for p in site_data.get("mine") or []:
        if tom.get(p["id"], {}).get("slot") == "IR":
            p["irn"] = 1
    for p in added:
        q = dict(p)
        q["nx"] = 1
        site_data["mine"].append(q)
    bits = ([f"added {', '.join(p['n'] for p in added)}"] if added else []) + \
           ([f"gone {', '.join(p['n'] for p in gone)}"] if gone else []) + \
           ([f"to IR {', '.join(p['n'] for p in to_ir)}"] if to_ir else [])
    return plan, "; ".join(bits) or "same players and IR spots as today"
