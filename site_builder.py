#!/usr/bin/env python3
"""
SITE DATA + PAGE (READ-ONLY): turns the players and teams into the compact data the page reads, and drops that data
into the page files in web/ (page.html, app.css, app.js). build.py runs it; it never changes anything in ESPN.
"""
import json
from pathlib import Path

import analyze as A
import dashboard as D


def r3(x):
    return None if x is None else round(float(x), 3)


def slim(p, standings):
    """Keep only what the web page needs (short keys keep the page small)."""
    d = {"id": p["id"], "n": p["name"], "pos": p["pos"], "grp": p["group"], "tm": p.get("team", "?"),
         "slot": "FA" if p.get("slot") is None else A.slot_name(p["slot"]),
         "gp": int(p["gp"]), "ppg": r3(p["ppg"]), "exp": r3(p["exp_ppg"]), "proj": r3(p["proj_ppg"]),
         "out": r3(p["outlook"]), "rec": r3(p.get("recent_ppg")), "g7": p.get("g7", 0),
         "own": r3(p.get("own")), "inj": p["injury"], "fl": p["flags"], "st": p.get("status")}
    if p["group"] == "G":
        d.update({"svp": r3(p.get("svp")), "w": int(p.get("wins", 0)), "ga": int(p.get("ga", 0)),
                  "sp": r3(D.start_prob(p, standings))})
    else:
        d.update({"g": int(p.get("g", 0)), "a": int(p.get("a", 0)), "sog": int(p.get("sog", 0)),
                  "hit": int(p.get("hit", 0)), "blk": int(p.get("blk", 0)), "ppp": int(p.get("ppp", 0)),
                  "shp": r3(p.get("sh_pct"))})
    return d


def build_site_data(cfg, data, league, standings, now_ms):
    ctx = D.build_context(cfg, data, league, standings, now_ms)
    sp = data["roster"].get("scoringPeriodId", 1)
    abbr, g7map = A.team_info(data["schedules"], sp, A.DAYS_AHEAD)
    meta = {t.get("id"): t for t in league.get("teams", [])}

    teams = []
    for t in data["roster"].get("teams", []):
        tid = t.get("id")
        players = D.roster_players(t, cfg["season"], abbr)
        for p in players:
            p["g7"] = g7map.get(p["team_id"], 0)
        m = meta.get(tid, {})
        w, l, ti, pf = D.record_of(m)
        tb = (t.get("tradeBlock") or m.get("tradeBlock") or {}).get("players") or {}
        block = [int(k) for k, v in tb.items() if v == "ON_THE_BLOCK"]      # NORMAL = not actually offered
        teams.append({"id": tid, "name": D.team_label(m) if m else f"Team {tid}", "rec": f"{w}-{l}-{ti}",
                      "w": w, "pf": r3(pf), "me": tid == cfg["team"], "block": block,
                      "players": [slim(p, standings) for p in players]})

    return {
        "league": ctx["league_name"], "me": ctx["my_name"], "rec": ctx["my_rec"], "updated": ctx["updated"],
        "matchup": ctx["matchup"],
        "goalies": [{"p": slim(g["p"], standings), "rows": g["rows"]} for g in ctx["goalies"]],
        "moves": [{"add": slim(m["add"], standings), "drop": slim(m["drop"], standings),
                   "gain": r3(m["gain"]), "wk": r3(m["week_gain"])} for m in ctx["moves"]],
        "alerts": [{"k": k, "t": t} for k, t in ctx["alerts"]],
        "mine": [slim(p, standings) for p in ctx["mine"]],
        "fas": [slim(p, standings) for p in ctx["fas"]],
        "teams": teams,
    }


WEB = Path(__file__).with_name("web")


def render_site(site_data):
    """web/page.html with the styles, the script and this build's data dropped in."""
    page = (WEB / "page.html").read_text(encoding="utf-8")
    css = (WEB / "app.css").read_text(encoding="utf-8")
    js = (WEB / "app.js").read_text(encoding="utf-8")
    blob = json.dumps(site_data, separators=(",", ":"), ensure_ascii=True).replace("</", "<\\/")
    return page.replace("__CSS__", css).replace("__JS__", js).replace("__DATA__", blob)
