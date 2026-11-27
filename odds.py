#!/usr/bin/env python3
"""
BETTING LINES (READ-ONLY): each game's win chance from the betting line, for goalie values.

Why: a goalie's points lean on wins, and the old win chance came only from the standings (points %) plus home ice.
Checked on 2026-11-27's slate (docs/goalie-odds-2026-11-27.md): the standings guess was off the line by 6 points of
win chance on average and by up to 15 (LA @ ANA: standings said ANA 60%, the line said 49%), which is the game the
user questioned ("add a goalie that isn't favored to win"). Lines exist for today and usually tomorrow; any game
without one keeps the standings guess, so nothing breaks when this can't be read.

Source: ESPN's public NHL scoreboard (the same one the app's Tonight tiles read), verified live 2026-11-27:
events[].competitions[0].odds[0].moneyline.{home,away}.close.odds (American, as text such as "-115"), with
.open.odds as the fallback, and competitors[].homeAway / team.abbreviation. Games already under way carry no odds.
"""
import json
from datetime import datetime, timedelta

import dashboard as D

URL = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={d}"
DAYS = 2                      # today and tomorrow: later days rarely have a line yet
STATE = {"by_game": {}}       # (ET date "YYYY-MM-DD", home abbr, away abbr) -> home team's win chance (no vig)
HEALTH = {"n": 0, "note": ""}
ALIAS = {"LAK": "LA", "NJD": "NJ", "SJS": "SJ", "TBL": "TB", "UTAH": "UTA", "WAS": "WSH", "MON": "MTL"}


def _ab(a):
    a = (a or "").upper()
    return ALIAS.get(a, a)


def _american(v):
    """Chance implied by an American price ("-115", "+180", -115). None if it can't be read."""
    try:
        v = float(str(v).replace("+", "").strip())
    except (TypeError, ValueError):
        return None
    if v == 0 or abs(v) < 100:
        return None
    return -v / (-v + 100) if v < 0 else 100 / (v + 100)


def _price(side):
    side = side or {}
    for k in ("close", "current", "open"):
        p = _american((side.get(k) or {}).get("odds"))
        if p is not None:
            return p
    return None


def parse(sb):
    """{(date, home, away): home win chance} from one ESPN scoreboard answer."""
    out = {}
    for e in (sb or {}).get("events") or []:
        try:
            c = (e.get("competitions") or [{}])[0]
            teams = {t.get("homeAway"): _ab((t.get("team") or {}).get("abbreviation")) for t in c.get("competitors") or []}
            o = (c.get("odds") or [{}])[0] or {}
            ml = o.get("moneyline") or {}
            ph, pa = _price(ml.get("home")), _price(ml.get("away"))
            if ph is None or pa is None:                     # older shape: homeTeamOdds.moneyLine
                ph = _american((o.get("homeTeamOdds") or {}).get("moneyLine"))
                pa = _american((o.get("awayTeamOdds") or {}).get("moneyLine"))
            if ph is None or pa is None or not teams.get("home") or not teams.get("away"):
                continue
            when = datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(D.et_zone())
            out[(when.strftime("%Y-%m-%d"), teams["home"], teams["away"])] = round(ph / (ph + pa), 4)
        except Exception:
            continue
    return out


def load(now=None):
    """Lines for today and tomorrow (Eastern). Never raises: no lines just means the standings guess is used."""
    import requests
    now = now or datetime.now(D.et_zone())
    out = {}
    for k in range(DAYS):
        d = (now + timedelta(days=k)).strftime("%Y%m%d")
        try:
            r = requests.get(URL.format(d=d), timeout=12)
            r.raise_for_status()
            out.update(parse(r.json()))
        except Exception as e:
            HEALTH["note"] = f"{type(e).__name__}: {e}"
    HEALTH["n"] = len(out)
    print(f"  betting lines: {len(out)} games" + (f" ({HEALTH['note']})" if not out and HEALTH["note"] else ""))
    return out


def install(by_game):
    STATE["by_game"] = dict(by_game or {})


def p_win(team, opp, home, date_ms):
    """Chance `team` beats `opp` in the game starting at date_ms (ESPN ms), from the betting line; None without one."""
    if not STATE["by_game"] or not date_ms:
        return None
    day = datetime.fromtimestamp(date_ms / 1000, D.et_zone()).strftime("%Y-%m-%d")
    t, o = _ab(team), _ab(opp)
    key = (day, t, o) if home else (day, o, t)
    ph = STATE["by_game"].get(key)
    if ph is None:
        return None
    return ph if home else 1 - ph


def dump():
    return json.dumps({"|".join(k): v for k, v in STATE["by_game"].items()}, sort_keys=True)
