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
import time
from datetime import datetime
from pathlib import Path

import requests

import analyze as A
import dashboard as D
import enrich as E

URL = "https://www.dailyfaceoff.com/starting-goalies"
REV = {v: k for k, v in D.NHL_ABBR.items()}          # NHL-style abbreviation -> ESPN-style
STATE = {"by_team": {}}
_orig_alerts = D.lineup_alerts
PREV = {}
CACHE_FILE = Path(__file__).with_name("cache") / "df_starters.json"
HEALTH = {"state": "missing", "note": ""}


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


def _fetch():
    last = None
    for attempt in range(2):
        try:
            r = requests.get(URL, headers=E.UA, timeout=30)
            r.raise_for_status()
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
            return json.loads(m.group(1))["props"]["pageProps"], None
        except Exception as e:
            last = e
            if attempt == 0:
                time.sleep(6)
    return None, last


def load():
    """Today's starters. If Daily Faceoff refuses the request, uses the last copy saved today (cache/df_starters.json)."""
    today = datetime.now(D.et_zone()).strftime("%Y-%m-%d")
    page, err = _fetch()
    out = parse_page(page, today) if page else {}
    if page and out:
        conf = sum(1 for v in out.values() if v["status"] == "Confirmed")
        print(f"  Daily Faceoff: starters listed for {len(out)} teams ({conf} confirmed)")
        HEALTH.update(state="live", note="")
        try:
            import netcache
            if netcache.STATE["mode"] != "replay":
                CACHE_FILE.parent.mkdir(exist_ok=True)
                CACHE_FILE.write_text(json.dumps({"date": today, "by_team": out}, sort_keys=True), encoding="utf-8")
        except Exception:
            pass
        return out
    if page is not None:
        print(f"  (Daily Faceoff page is for {page.get('date')}, not {today}; ignoring)")
        HEALTH.update(state="none", note="")
        return {}
    else:
        print(f"  (Daily Faceoff starters unavailable: {type(err).__name__}: {err})")
    try:
        c = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        if c.get("date") == today and c.get("by_team"):
            print(f"  Daily Faceoff starters: using today's saved copy ({len(c['by_team'])} teams)")
            HEALTH.update(state="cached", note="Starting goalies are from an earlier check today.")
            return c["by_team"]
    except Exception:
        pass
    HEALTH.update(state="missing", note="Starting goalies could not be checked; calls use each goalie's usual share of starts.")
    return {}


def _is_starter(p):
    s = STATE["by_team"].get(p.get("team"))
    return None if not s else E.norm(s["name"]) == E.norm(p["name"])


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
    D.start_prob = _start_prob
    D.lineup_alerts = _alerts
