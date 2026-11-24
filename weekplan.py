#!/usr/bin/env python3
"""
WEEKLY PLAN MEMORY (READ-ONLY): keeps the plan steady through the week and tracks what you have done.

  - plan_state.json (committed back to the repo by the workflow) holds this matchup's latest plan.
  - Each build re-plans, but the planner (core.py) keeps every move from the previous plan unless a new choice is
    clearly better, so the plan does not flip-flop. Anything that did change is listed with the reason.
  - A move is DONE once the player it adds is on your roster, MISSED once its day starts without it.
  - The plan is only saved from a healthy build (line data fresh), so a bad data day never sets the week's plan.
  - Small moves the plan left off your list (core.SHOW_NET) are saved too, and logged as "hidden" once their day starts,
    so the private track record shows whether leaving them off cost anything. They are never shown in the app.
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

STATE_FILE = Path(__file__).with_name("plan_state.json")
LOG_FILE = Path(__file__).with_name("history") / "moves.jsonl"     # every planned move that was made or missed
KEEP = ("t", "day", "add", "drop", "gain", "cost", "net", "games", "waiver", "tier", "conf", "why1", "base",
        "nd", "need", "kept", "ga", "gd", "ca", "cd", "g", "dg", "ir", "late", "bar")
LOG_EXTRA = ("t", "nd", "need", "kept", "ga", "gd", "ca", "cd", "g", "dg", "ir", "cost", "late", "bar")   # backtest.py


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


def _why_changed(m, mine_ids, fa_by_id, fresh_add_ids, fresh_drop_ids, small_keys=()):
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
    if (a["id"], d["id"]) in small_keys:
        return "The gain shrank (new lines, injuries or goalie news), so it is no longer worth one of your moves."
    return "Today's update found a better use of this move (fresh lines, goalie starts and next week's schedule)."


def build(cfg, data, league, standings, now_ms, site_data, healthy=True):
    fresh = site_data.get("gameplan")
    clock = site_data.get("clock")
    if not fresh or not clock:
        return None
    mp = (league.get("status") or {}).get("currentMatchupPeriod")
    state = _load()
    if not state or state.get("mp") != mp:
        state = {"mp": mp, "moves": [], "done": [], "missed": [], "small": [], "small_logged": []}
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
        why = _why_changed(m, mine_ids, fa_by_id, fresh_adds, fresh_drops,
                           {(x["add"]["id"], x["drop"]["id"]) for x in fresh.get("small") or []})
        if why:
            changes.append({"add": m["add"], "drop": m["drop"], "day": m["day"], "why": why})
    # small moves left off the list: log each once, when its day has started (scored like any other move)
    planned = set(done) | set(missed) | {(m["add"]["id"], m["drop"]["id"]) for m in fresh["moves"]}
    small_logged = {tuple(k) for k in state.get("small_logged", [])}
    new_hidden = []
    for m in state.get("small", []):
        k = (m["add"]["id"], m["drop"]["id"])
        if k in small_logged or k in planned:
            continue
        idx = labels.index(m["day"]) if m["day"] in labels else None
        if idx is None or D.day_locked(clock, idx, now_ms):
            small_logged.add(k)
            new_hidden.append(m)
    out = {"mp": mp, "done": list(done.values()), "missed": list(missed.values()), "changes": changes,
           "saved": healthy, "preview": None}
    if healthy:
        new = [("done", m) for k, m in done.items() if k not in {(x["add"]["id"], x["drop"]["id"]) for x in state.get("done", [])}]
        new += [("missed", m) for k, m in missed.items() if k not in {(x["add"]["id"], x["drop"]["id"]) for x in state.get("missed", [])}]
        new += [("hidden", m) for m in new_hidden]
        import netcache
        if new and netcache.STATE["mode"] != "replay":            # test replays never write the log
            LOG_FILE.parent.mkdir(exist_ok=True)
            with LOG_FILE.open("a", encoding="utf-8") as f:
                for kind, m in new:
                    f.write(json.dumps({"mp": mp, "logged": now_ms, "result": kind, "day": m.get("day"),
                                        "add": m["add"], "drop": m["drop"], "expected_gain": m.get("gain"),
                                        "net": m.get("net"), "conf": m.get("conf"), "why1": m.get("why1"),
                                        "base": m.get("base"),
                                        **{k: m.get(k) for k in LOG_EXTRA if m.get(k) is not None}}) + "\n")
        # starting line for the track record: both players' season points, refreshed until the move's day locks
        import record as RC
        old_base = {(m["add"]["id"], m["day"], m["drop"]["id"]): m.get("base") for m in state.get("moves", [])}
        saved = []
        for m in fresh["moves"]:
            sm = {k: m.get(k) for k in KEEP if k != "base"}
            key = (m["add"]["id"], m["day"], m["drop"]["id"])
            idx = labels.index(m["day"]) if m["day"] in labels else None
            open_day = idx is not None and not D.day_locked(clock, idx, now_ms)
            sm["base"] = (RC.snap(m["add"]["id"], m["drop"]["id"], now_ms) if open_day else None) or old_base.get(key)
            saved.append(sm)
        old_sbase = {(m["add"]["id"], m["day"], m["drop"]["id"]): m.get("base") for m in state.get("small", [])}
        small = []
        for m in fresh.get("small") or []:
            sm = {k: m.get(k) for k in KEEP if k != "base"}
            key = (m["add"]["id"], m["day"], m["drop"]["id"])
            idx = labels.index(m["day"]) if m["day"] in labels else None
            open_day = idx is not None and not D.day_locked(clock, idx, now_ms)
            if not open_day:
                continue
            sm["base"] = RC.snap(m["add"]["id"], m["drop"]["id"], now_ms) or old_sbase.get(key)
            small.append(sm)
        _save({"mp": mp, "updated": now_ms, "moves": saved, "done": out["done"], "missed": out["missed"],
               "small": small, "small_logged": sorted([list(k) for k in small_logged])})
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
    STR.STATE["ref"] = 0
    import longterm as LT
    fut = C.team_games(games, abbr, sp + ndays, LT.HORIZON_DAYS)
    plan = C.plan(site_data["mine"], site_data["fas"], game, ndays, days, standings, {}, PL.MOVE_LIMIT, fut)
    return {"base": plan["base"], "total": plan["total"], "gain": plan["gain"],
            "moves": [{**{k: mv.get(k) for k in KEEP}, "why": (mv.get("why_add") or [])[:1]} for mv in plan["moves"]],
            "first_day": days[0] if days else ""}
