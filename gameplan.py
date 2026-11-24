#!/usr/bin/env python3
"""
GAME PLAN data (READ-ONLY): the one move plan (from core.py) plus what the Game plan page shows around it:
the day-by-day lineup table before and after the plan, the best stream targets, and the matchup it leads to.
"""
import analyze as A
import dashboard as D
import planner as PL
import starters as S
import streams as STR

INF = STR.INF
SLOTS = {"F": 9, "D": 5, "G": 2}
TARGETS_F, TARGETS_D, TARGETS_G = 6, 6, 4


def _counts(active):
    """Lineup slots that have a player with a game today. UTIL is filled by the best leftover skater."""
    out = {}
    for g, k in SLOTS.items():
        out[g] = min(k, sum(1 for gg, v in active if gg == g and v > 0))
    extra = sum(1 for gg, v in active if gg == "F" and v > 0) - SLOTS["F"]
    extra += sum(1 for gg, v in active if gg == "D" and v > 0) - SLOTS["D"]
    out["U"] = 1 if extra > 0 else 0
    return out


def _day_rows(entries, ndays, days, game_fn):
    rows = []
    for d in range(ndays):
        act = STR._active(entries, d)
        c = _counts(act)
        open_slots = sum(SLOTS[g] - c[g] for g in SLOTS) + (1 - c["U"])
        rows.append({"day": days[d], "pts": round(STR.day_value(act), 1), "f": c["F"], "d": c["D"], "g": c["G"],
                     "u": c["U"], "open": open_slots})
    return rows


def build(cfg, data, league, standings, now_ms, site_data, prev=None):
    """The one plan (core.py), plus the before/after day table, stream targets and the matchup it leads to."""
    import core as C
    sp = data["roster"].get("scoringPeriodId", 1)
    abbr, games = D.schedule_maps(data["schedules"])
    m = site_data.get("matchup")
    ndays = max(1, min(int(m["days_left"]) if m else 7, D.MAX_DAYS))
    game = STR.make_game_fn(abbr, games, sp, now_ms)
    starters = S.STATE["by_team"]
    days = D.day_clock_games(games, sp, ndays, now_ms)["labels"]
    bg = PL.budget(league, cfg["team"])                    # this league's own weekly add limit, not a fixed 7
    used, moves_left = bg["used"], bg["left"]
    nxt = C.team_games(games, abbr, sp + ndays, 7)
    import longterm as LT
    fut = C.team_games(games, abbr, sp + ndays, LT.HORIZON_DAYS)     # for the long-term cost of each drop

    import keep as KP
    import roles as R
    lh = R.health()["state"]
    cautious = lh == "missing"                           # no line data at all: don't invent new moves without roles
    healthy = lh == "live" or (lh == "cached" and (R.STATE["cache_age_h"] or 0) <= 24)
    mp = (league.get("status") or {}).get("currentMatchupPeriod")
    kept = KP.load(mp)
    res = C.plan(site_data["mine"], site_data["fas"], game, ndays, days, standings, starters, moves_left, fut, prev=prev,
                 only_prev=cautious, keep_ids=kept, healthy=healthy, ir_free=D.ir_free(league, site_data["mine"]))
    entries, _, pool = C.build_inputs(site_data["mine"], site_data["fas"], game, ndays, standings, starters)
    before_rows = _day_rows(entries, ndays, days, game)
    after_rows = _day_rows(res["ents"], ndays, days, game)
    taken = {mv["add"]["id"] for mv in res["moves"]}

    def target(x):
        p = x["p"]
        first = next((i for i in range(ndays) if x["v"][i] > 0), None)
        return {"id": p["id"], "n": p["n"], "pos": p["pos"], "tm": p["tm"], "grp": x["g"],
                "role": STR._role_text(p), "total": round(sum(x["v"]), 1),
                "games": sum(1 for i in range(ndays) if x["v"][i] > 0),
                "first": days[first] if first is not None else "", "waiver": x["waiver"], "taken": p["id"] in taken}

    ranked = sorted(pool, key=lambda x: -sum(x["v"]))
    plan = {"base": res["base"], "total": res["total"], "gain": res["gain"], "moves": res["moves"],
            "before": before_rows, "after": after_rows,
            "targets": {g: [target(x) for x in ranked if x["g"] == g][:k]
                        for g, k in (("F", TARGETS_F), ("D", TARGETS_D), ("G", TARGETS_G))},
            "small": res.get("small", []),
            "moves_left": moves_left, "limit": bg["limit"], "used_known": bg["used_known"], "moves_used": used,
            "unlimited": bg["unlimited"], "limit_known": bg["known"], "season_left": bg["season_left"],
            "next_games": nxt, "fut": fut, "fut_days": LT.HORIZON_DAYS, "cautious": cautious, "mp": mp, "kept": sorted(kept), "healthy": healthy}
    plan["unused"] = max(0, moves_left - len(plan["moves"]))
    plan["ir_free"] = D.ir_free(league, site_data["mine"])
    if m:
        # one projection model for the whole site: same daily-lineup values as the plan, for both teams
        opp = next((t for t in site_data.get("teams", []) if t["id"] == m.get("opp_id")), None)
        try:
            pr = C.matchup_projection(site_data["mine"], opp["players"] if opp else [], game, ndays, standings, starters,
                                      m["me_now"], m["opp_now"])
            m.update({"proj_me": pr["proj_me"], "proj_opp": pr["proj_opp"], "p_win": pr["p_win"], "sd": pr["sd"]})
        except Exception as e:
            print(f"  matchup projection kept the old model ({type(e).__name__}: {e})")
        plan["matchup"] = {"opp": m.get("opp_name"), "me_now": round(m["me_now"], 1), "opp_now": round(m["opp_now"], 1),
                           "proj_me": round(m["proj_me"], 1), "proj_opp": round(m["proj_opp"], 1),
                           "p_win": round(m["p_win"], 3), "p_win_after": C.win_after(m, plan["gain"]),
                           "days_left": m["days_left"]}
    return plan
