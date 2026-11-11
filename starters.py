#!/usr/bin/env python3
"""
Confirmed / expected starting goalies for TODAY (READ-ONLY, one polite request per run).

Source: the public Daily Faceoff starting-goalies page (its robots.txt allows it). Credit: DailyFaceoff.com.

What it adds
  - Goalie cards say START - CONFIRMED / LIKELY / UNCONFIRMED, or NOT STARTING when the backup is in net.
  - A goalie listed as today's starter gets a higher start chance in the weekly projections
    (fixes goalies who missed time and look like part-timers on season totals).
  - Lineup alerts when a goalie in your lineup is not starting and a bench goalie is.

Plugs into dashboard.py by wrapping a few functions. If the page can't be read, nothing changes.
"""
import json
import re
from datetime import datetime

import requests

import analyze as A
import dashboard as D
import enrich as E

URL = "https://www.dailyfaceoff.com/starting-goalies"
REV = {v: k for k, v in D.NHL_ABBR.items()}          # NHL-style abbreviation -> ESPN-style
STATE = {"by_team": {}}
_orig_goalie_decisions = D.goalie_decisions
_orig_alerts = D.lineup_alerts
PREV = {}


def parse_page(page, today):
    """Turns the page data into {ESPN team abbreviation: {'name', 'status'}}; {} if it isn't today's page."""
    if str(page.get("date", ""))[:10] != today:
        return {}
    out = {}
    for g in page.get("data", []):
        for side in ("home", "away"):
            name, ab = g.get(f"{side}GoalieName"), g.get(f"{side}TeamAbbreviation")
            if name and ab:
                out[REV.get(ab, ab)] = {"name": name, "status": g.get(f"{side}NewsStrengthName") or "Unconfirmed"}
    return out


def load():
    try:
        r = requests.get(URL, headers=E.UA, timeout=30)
        r.raise_for_status()
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
        page = json.loads(m.group(1))["props"]["pageProps"]
    except Exception as e:
        print(f"  (Daily Faceoff starters unavailable: {type(e).__name__}: {e})")
        return {}
    today = datetime.now(D.et_zone()).strftime("%Y-%m-%d")
    out = parse_page(page, today)
    if not out:
        print(f"  (Daily Faceoff page is for {page.get('date')}, not {today}; ignoring)")
    else:
        conf = sum(1 for v in out.values() if v["status"] == "Confirmed")
        print(f"  Daily Faceoff: starters listed for {len(out)} teams ({conf} confirmed)")
    return out


def _is_starter(p):
    s = STATE["by_team"].get(p.get("team"))
    return None if not s else E.norm(s["name"]) == E.norm(p["name"])


def _goalie_decisions(mine, sp, games, abbr, standings, now_ms):
    out = _orig_goalie_decisions(mine, sp, games, abbr, standings, now_ms)
    today = D.fmt_game(now_ms)[0]
    for gd in out:
        p = gd["p"]
        s = STATE["by_team"].get(p["team"])
        if not s:
            continue
        for r in gd["rows"]:
            if r["day"] != today or r["cls"] == "done":
                continue
            if _is_starter(p):
                r["verdict"] = f"{r['verdict']} - {s['status'].upper()}"
            else:
                r["verdict"], r["cls"], r["e"] = f"NOT STARTING ({s['name'].split()[-1]} in net)", "done", 0.0
    return out


def _start_prob(p, standings):
    base = PREV["sp"](p, standings)
    return max(base, 0.6) if _is_starter(p) else base


def _alerts(mine, sp, games, now_ms):
    alerts = _orig_alerts(mine, sp, games, now_ms)
    goalies = [p for p in mine if p["group"] == "G"]
    bench = [p for p in goalies if A.slot_name(p["slot"]) == "BN" and _is_starter(p) and p["outlook"] >= 0.5
             and D.games_on(games, p["team_id"], sp, now_ms)]
    for g in goalies:
        if A.slot_name(g["slot"]) == "G" and _is_starter(g) is False and D.games_on(games, g["team_id"], sp, now_ms):
            if bench:
                b = bench.pop(0)
                alerts.append(("warn", f"{g['name']} is not starting today ({STATE['by_team'][g['team']]['name']} is in net). "
                                       f"Swap in {b['name']}, who is listed to start."))
            else:
                alerts.append(("warn", f"{g['name']} is not starting today ({STATE['by_team'][g['team']]['name']} is in net)."))
    return alerts


def install(by_team):
    STATE["by_team"] = by_team
    if not by_team:
        return
    PREV["sp"] = D.start_prob                          # keep the NHL games-started version if it is installed
    D.goalie_decisions = _goalie_decisions
    D.start_prob = _start_prob
    D.lineup_alerts = _alerts
