#!/usr/bin/env python3
"""
WEEKLY PLAN MEMORY (READ-ONLY): keeps the plan steady through the week and tracks what you have done.

  - plan_state.json (committed back to the repo by the workflow) holds this matchup's latest plan.
  - Each build re-plans, but the planner (core.py) keeps every move from the previous plan unless a new choice is
    clearly better, so the plan does not flip-flop. Anything that did change is listed with the reason.
  - A move is DONE once the player it adds is on your roster, MISSED once its day starts without it.
  - The plan is only saved from a healthy build (line data fresh), so a bad data day never sets the week's plan.
  - On the last day of a matchup it also drafts NEXT week's plan from today's roster and the real schedule.

Never fails the build: any problem just skips the cards.
"""
import json
from pathlib import Path

import analyze as A
import dashboard as D
import planner as PL
import starters as S
import streams as STR
import streams4 as S4

STATE_FILE = Path(__file__).with_name("plan_state.json")
KEEP = ("t", "day", "add", "drop", "gain", "cost", "net", "games", "waiver", "tier")


def _load():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save(state):
    STATE_FILE.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")


def previous(mp):
    """[(add_id, day_label, drop_id)] from the last saved plan for this matchup, for core.plan(prev=...)."""
    st = _load()
    if not st or st.get("mp") != mp:
        return []
    return [(m["add"]["id"], m["day"], m["drop"]["id"]) for m in st.get("moves", [])]


def _why_changed(m, mine_ids, fa_by_id, fresh_add_ids, fresh_drop_ids):
    a, d = m["add"], m["drop"]
    if a["id"] in mine_ids:
        return None                                           # done, not a change
    fa = fa_by_id.get(a["id"])
    if fa is None:
        return f"{a['n']} is no longer a free agent."
    if fa.get("inj") in A.BAD_INJURY:
        return f"{a['n']} is now listed {fa['inj'].replace('_', ' ').lower()}."
    if d["id"] not in mine_ids:
        return f"{d['n']} is no longer on your roster."
    if a["id"] in fresh_add_ids:
        return f"{a['n']} is still in the plan, now paired with a different drop or day."
    return "Today's update found a better use of this move (fresh lines, goalie starts and next week's schedule)."


def build(cfg, data, league, standings, now_ms, site_data, healthy=True):
    fresh = site_data.get("gameplan")
    clock = site_data.get("clock")
    if not fresh or not clock:
        return None
    mp = (league.get("status") or {}).get("currentMatchupPeriod")
    state = _load()
    if not state or state.get("mp") != mp:
        state = {"mp": mp, "moves": [], "done": [], "missed": []}
    mine_ids = {p["id"] for p in site_data["mine"]}
    fa_by_id = {p["id"]: p for p in site_data["fas"]}
    fresh_keys = {(m["add"]["id"], m["day"], m["drop"]["id"]) for m in fresh["moves"]}
    fresh_adds = {m["add"]["id"] for m in fresh["moves"]}
    fresh_drops = {m["drop"]["id"] for m in fresh["moves"]}
    labels = clock["labels"]
    done = {(m["add"]["id"], m["drop"]["id"]): m for m in state.get("done", [])}
    missed = {(m["add"]["id"], m["drop"]["id"]): m for m in state.get("missed", [])}
    changes = []
    for m in state.get("moves", []):
        k = (m["add"]["id"], m["drop"]["id"])
        if m["add"]["id"] in mine_ids:
            done.setdefault(k, {kk: m.get(kk) for kk in KEEP})
            continue
        if (m["add"]["id"], m["day"], m["drop"]["id"]) in fresh_keys:
            continue
        idx = labels.index(m["day"]) if m["day"] in labels else None
        if idx is None or D.day_locked(clock, idx, now_ms):
            missed.setdefault(k, {kk: m.get(kk) for kk in KEEP})
            continue
        why = _why_changed(m, mine_ids, fa_by_id, fresh_adds, fresh_drops)
        if why:
            changes.append({"add": m["add"], "drop": m["drop"], "day": m["day"], "why": why})
    out = {"mp": mp, "done": list(done.values()), "missed": list(missed.values()), "changes": changes,
           "saved": healthy, "preview": None}
    if healthy:
        _save({"mp": mp, "updated": now_ms, "moves": [{k: m.get(k) for k in KEEP} for m in fresh["moves"]],
               "done": out["done"], "missed": out["missed"]})
        print(f"  weekly plan saved for matchup {mp}: {len(fresh['moves'])} moves, {len(done)} done, "
              f"{len(changes)} changed since the last build")
    else:
        print("  weekly plan NOT saved: data was incomplete this build")
    mt = site_data.get("matchup")
    if mt and int(mt.get("days_left", 7)) <= 1:
        try:
            out["preview"] = next_week(cfg, data, league, standings, now_ms, site_data)
        except Exception as e:
            print(f"  next-week preview skipped ({type(e).__name__}: {e})")
    return out


def next_week(cfg, data, league, standings, now_ms, site_data):
    """Draft plan for the matchup that starts after this one, from today's roster and the real schedule."""
    import core as C
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
    nxt = C.team_games(games, abbr, sp + ndays, 7)
    plan = C.plan(site_data["mine"], site_data["fas"], game, ndays, days, standings, {}, PL.MOVE_LIMIT, nxt)
    return {"base": plan["base"], "total": plan["total"], "gain": plan["gain"],
            "moves": [{**{k: mv.get(k) for k in KEEP}, "why": (mv.get("why_add") or [])[:1]} for mv in plan["moves"]],
            "first_day": days[0] if days else ""}
