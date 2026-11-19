#!/usr/bin/env python3
"""
GAME LOGS (READ-ONLY): each player's recent games, for the Game log tab on the player card and for Compare.

Source: ESPN's own per-game stats (the same numbers ESPN's game log shows), so the fantasy points per game are
exactly this league's scoring. One request per batch of players (view=kona_playercard). The opponent and date of
each game come from the NHL schedule ESPN already gave us.

Writes site/gamelog.json (loaded by the page only when a card or Compare needs it, so the main page stays small):
  {"v": built_ms, "nx": {team: [date_ms, opp, home]},       next game for every NHL team
   "p": {player id: [[date_ms, opp, home, pts, ...], ...]}}  newest game first
  skater row: [date, opp, home, pts, G, A, SOG, HIT, BLK, TOI seconds, PPP]
  goalie row: [date, opp, home, pts, W(1/0), GA, SV, SA, SO(1/0), TOI seconds]
If ESPN does not answer, the build carries on and the page says the game log is unavailable.
"""
import json

import requests

PERIODS = 30          # last 30 scoring days, which covers about 12-15 games
KEEP = 15             # games kept per player
BATCH = 50
# ESPN stat ids (per-game split, statSplitTypeId 5)
SK = {"g": "13", "a": "14", "sog": "29", "hit": "31", "blk": "32", "ppp": "38", "toi": "26", "gp": "30"}
GK = {"w": "1", "ga": "4", "sv": "6", "sa": "3", "so": "7", "toi": "8", "gp": "30"}


def _n(stats, k):
    try:
        return float(stats.get(k) or 0)
    except (TypeError, ValueError):
        return 0.0


def _r1(x):
    x = round(float(x), 2)
    return int(x) if x == int(x) else x


def fetch(cfg, ids):
    """Raw ESPN player records (with per-game stats) for these ESPN player ids. Never raises."""
    season, league = cfg["season"], cfg["league"]
    url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{season}/segments/0/leagues/{league}"
    out, fails = [], 0
    ids = list(dict.fromkeys(int(i) for i in ids if i is not None))
    for k in range(0, len(ids), BATCH):
        part = ids[k:k + BATCH]
        flt = {"players": {"filterIds": {"value": part}, "limit": len(part),
                           "filterStatsForTopScoringPeriodIds": {"value": PERIODS,
                                                                 "additionalValue": [f"00{season}", f"10{season}"]}}}
        try:
            r = requests.get(url, params=[("view", "kona_playercard")], cookies=cfg.get("cookies"),
                             headers={"x-fantasy-filter": json.dumps(flt)}, timeout=30)
            r.raise_for_status()
            js = r.json()
            for it in (js.get("players") if isinstance(js, dict) else js) or []:
                pl = it.get("player") if isinstance(it, dict) and "player" in it else it
                if isinstance(pl, dict):
                    out.append(pl)
        except Exception as e:
            fails += 1
            if fails == 1:
                print(f"  game logs: ESPN request failed ({type(e).__name__}: {str(e)[:80]})")
            if fails >= 2 and not out:              # ESPN is not answering this view: stop asking
                break
    return out


def game_index(schedules):
    """{game id: (date_ms, home team id, away team id)} and {team id: abbrev}."""
    gi, abbr, by_tp = {}, {}, {}
    for t in (schedules.get("settings") or {}).get("proTeams", []):
        abbr[t.get("id")] = t.get("abbrev", "?")
        for sp, lst in (t.get("proGamesByScoringPeriod") or {}).items():
            for g in lst or []:
                gi[str(g.get("id"))] = (g.get("date") or 0, g.get("homeProTeamId"), g.get("awayProTeamId"))
                by_tp[(t.get("id"), str(sp))] = str(g.get("id"))
    return gi, abbr, by_tp


def parse_player(pl, gi, abbr, by_tp):
    """Rows for one ESPN player record, newest first (only games he actually played)."""
    goalie = pl.get("defaultPositionId") == 5
    rows = {}
    for s in pl.get("stats") or []:
        if s.get("statSplitTypeId") != 5:
            continue
        st = s.get("stats") or {}
        if _n(st, "30") < 1:                      # no game played that day
            continue
        tid = s.get("proTeamId") or pl.get("proTeamId")
        gid = str(s.get("externalId") or "") or by_tp.get((tid, str(s.get("scoringPeriodId"))), "")
        g = gi.get(gid) or gi.get(by_tp.get((tid, str(s.get("scoringPeriodId"))), ""))
        if not g:
            continue
        date, home, away = g
        is_home = 1 if home == tid else 0
        opp = abbr.get(away if is_home else home, "?")
        pts = _r1(s.get("appliedTotal") or 0)
        if goalie:
            row = [date, opp, is_home, pts, 1 if _n(st, GK["w"]) >= 1 else 0, int(_n(st, GK["ga"])),
                   int(_n(st, GK["sv"])), int(_n(st, GK["sa"])), 1 if _n(st, GK["so"]) >= 1 else 0, int(_n(st, GK["toi"]))]
        else:
            row = [date, opp, is_home, pts] + [int(_n(st, SK[k])) for k in ("g", "a", "sog", "hit", "blk")] \
                  + [int(_n(st, SK["toi"])), int(_n(st, SK["ppp"]))]
        rows[gid or f"{date}"] = row
    return sorted(rows.values(), key=lambda r: -r[0])[:KEEP]


def next_games(schedules, now_ms):
    """{team abbrev: [date_ms, opp abbrev, home]} for each team's next game that has not started."""
    gi, abbr, _ = game_index(schedules)
    nx = {}
    for date, home, away in gi.values():
        if not date or date <= now_ms:
            continue
        for tid, oid, h in ((home, away, 1), (away, home, 0)):
            a = abbr.get(tid)
            if a and (a not in nx or date < nx[a][0]):
                nx[a] = [date, abbr.get(oid, "?"), h]
    return nx


def build(cfg, data, site_data, now_ms, players=None):
    """The gamelog.json content. players = raw ESPN records (fetched here when None)."""
    ids = [p["id"] for p in site_data.get("mine", []) + site_data.get("fas", [])]
    for t in site_data.get("teams", []):
        ids += [p["id"] for p in t.get("players", [])]
    if players is None:
        players = fetch(cfg, ids)
    gi, abbr, by_tp = game_index(data["schedules"])
    logs = {}
    for pl in players:
        try:
            rows = parse_player(pl, gi, abbr, by_tp)
        except Exception:
            continue
        if rows and pl.get("id") is not None:
            logs[str(pl["id"])] = rows
    print(f"  game logs: {len(logs)} of {len(set(ids))} players")
    return {"v": now_ms, "nx": next_games(data["schedules"], now_ms), "p": logs}
