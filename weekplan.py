#!/usr/bin/env python3
"""
LOCKED WEEKLY PLAN (READ-ONLY): one plan per matchup week that stays put and is tracked day by day.

  - The first build of a new matchup week saves that week's game plan to plan_state.json (the workflow commits the
    file back to the repo, so every later build can read it). Later builds do NOT re-plan it. They only check it:
        done        the player to add is on your roster
        due today   the move's day is today (or the first open day) and it has not been made
        missed      the day has passed (or its first puck dropped) without the move
        unavailable the player to add is injured or no longer a free agent
        waiting     a later day
    and whether today's fresh model still picks the same add ("still agrees") or not.
  - On the last day of a week it also builds a draft plan for NEXT week (all 7 days, 7 moves) from today's roster and
    the real schedule, so the setup is ready before Monday. It is rebuilt each time and never saved; the real plan
    locks on the first build of the new week, with fresher news.

Needs the plan from gameplan.py (site_data["gameplan"]). Never fails the build: any problem just skips the cards.
"""
import json
from pathlib import Path

import analyze as A
import dashboard as D
import gameplan as GP
import planner as PL
import streams as STR
import streams4 as S4

STATE_FILE = Path(__file__).with_name("plan_state.json")
KEEP = ("t", "day", "add", "drop", "gain", "net", "games", "waiver", "tier")


def _load():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save(state):
    STATE_FILE.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")


def _compact(plan, mp, now_ms, label):
    moves = []
    for m in plan["moves"]:
        c = {k: m.get(k) for k in KEEP}
        c["why"] = ((m.get("why_add") or [])[:1])
        moves.append(c)
    return {"mp": mp, "locked_at": now_ms, "week_label": label, "base": plan["base"], "total": plan["total"],
            "gain": plan["gain"], "moves": moves}


def _status(m, mine_ids, fa_by_id, clock, now_ms, first_open, fresh_adds):
    labels = clock["labels"]
    add = m["add"]
    st = {"state": "waiting", "agree": None}
    if add["id"] in mine_ids:
        st["state"] = "done"
        return st
    idx = labels.index(m["day"]) if m["day"] in labels else None
    past = idx is None or D.day_locked(clock, idx, now_ms)
    if past:
        st["state"] = "missed"
        return st
    fa = fa_by_id.get(add["id"])
    if fa is None or fa.get("inj") in A.BAD_INJURY:
        st["state"] = "unavailable"
        return st
    st["state"] = "due" if idx == first_open else "waiting"
    st["agree"] = add["id"] in fresh_adds
    return st


def next_week(cfg, data, league, standings, now_ms, site_data):
    """Draft plan for the matchup that starts after this one (all 7 days, 7 moves)."""
    m = site_data.get("matchup")
    if not m:
        return None
    sp = data["roster"].get("scoringPeriodId", 1) + int(m["days_left"])
    abbr, games = D.schedule_maps(data["schedules"])
    if not any(gl.get(str(sp)) for gl in games.values()):
        return None
    ndays = 7
    game = STR.make_game_fn(abbr, games, sp, now_ms)
    days = D.day_clock_games(games, sp, ndays, now_ms)["labels"]
    S4.STATE["ref"] = 0
    plan = GP.plan_full(site_data["mine"], site_data["fas"], game, ndays, days, standings, {}, PL.MOVE_LIMIT)
    out = {"base": plan["base"], "total": plan["total"], "gain": plan["gain"],
           "moves": [{**{k: mv.get(k) for k in KEEP}, "why": (mv.get("why_add") or [])[:1]} for mv in plan["moves"]],
           "first_day": days[0] if days else ""}
    return out


def build(cfg, data, league, standings, now_ms, site_data):
    fresh = site_data.get("gameplan")
    clock = site_data.get("clock")
    if not fresh or not clock:
        return None
    mp = (league.get("status") or {}).get("currentMatchupPeriod")
    state = _load()
    if not state or state.get("mp") != mp:
        state = _compact(fresh, mp, now_ms, clock["labels"][0] if clock["labels"] else "")
        _save(state)
        print(f"  weekly plan locked for matchup {mp}: {len(state['moves'])} moves")
    else:
        print(f"  weekly plan (matchup {mp}) kept from {state.get('week_label')}: {len(state['moves'])} moves")
    mine_ids = {p["id"] for p in site_data["mine"]}
    fa_by_id = {p["id"]: p for p in site_data["fas"]}
    first_open = next((i for i in range(len(clock["lock"])) if not D.day_locked(clock, i, now_ms)), None)
    fresh_adds = {mv["add"]["id"] for mv in fresh["moves"]}
    moves = []
    for m in state["moves"]:
        moves.append({**m, **_status(m, mine_ids, fa_by_id, clock, now_ms, first_open, fresh_adds)})
    out = {"mp": mp, "week_label": state.get("week_label"), "base": state["base"], "total": state["total"],
           "gain": state["gain"], "moves": moves, "preview": None}
    mt = site_data.get("matchup")
    if mt and int(mt.get("days_left", 7)) <= 1:
        try:
            out["preview"] = next_week(cfg, data, league, standings, now_ms, site_data)
        except Exception as e:
            print(f"  next-week preview skipped ({type(e).__name__}: {e})")
    return out
