"""
EVERY PLAYER (READ-ONLY): the rest of ESPN's player pool, for the search in the app.

The page already carries every rostered player in the league and the top free agents the model looks at. This adds
everyone else ESPN lists (deep free agents, waivers, injured players nobody holds), in the same compact shape, as
site/pool.json. The app loads it only when you search, so the page itself stays small. Nothing here feeds the moves.

  {"v": build time, "n": count, "p": [player, ...]}     player = the same short keys as data.json (site_builder.slim)
"""
import json

import analyze as A
import playercard as PC
import site_builder as SB

POOL_LIMIT = 2500      # ESPN lists roughly 1,500 NHL players; this is the ceiling, not a target


def fetch(cfg, get=None):
    """Every free agent and waiver player ESPN lists, most rostered first."""
    get = get or A.espn_get
    url = (f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{cfg['season']}"
           f"/segments/0/leagues/{cfg['league']}")
    ffilter = {"players": {
        "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
        "filterSlotIds": {"value": list(range(0, 26))},
        "limit": POOL_LIMIT,
        "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
    }}
    return get(url, cfg["cookies"], params=[("view", "kona_player_info")],
               headers={"x-fantasy-filter": json.dumps(ffilter)})


def known_ids(site_data):
    ids = set()
    for p in site_data.get("mine", []) + site_data.get("fas", []):
        ids.add(p["id"])
    for t in site_data.get("teams", []):
        for p in t.get("players", []):
            ids.add(p["id"])
    return ids


def build(cfg, data, site_data, standings, now_ms, raw=None, get=None):
    """Players not already in the page data. raw = an ESPN answer (tests); otherwise it is fetched."""
    raw = raw if raw is not None else fetch(cfg, get)
    have = known_ids(site_data)
    sp = data["roster"].get("scoringPeriodId", 1)
    abbr, games = A.team_info(data["schedules"], sp, A.DAYS_AHEAD)
    out, seen = [], set()
    for e in raw.get("players", []) or []:
        pl = e.get("player") or {}
        pid = pl.get("id")
        if pid is None or pid in have or pid in seen:
            continue
        seen.add(pid)
        p = A.parse_player(pl, cfg["season"], status=e.get("status"))     # the module attribute: keeps NHL / role extras
        p["team"] = abbr.get(p["team_id"], "?")
        if p["team"] == "?" and not p["gp"]:
            continue                                                       # no NHL team and no games: not a real option
        p["g7"] = games.get(p["team_id"], 0)
        p["week_pts"] = p["outlook"] * p["g7"]
        out.append(SB.slim(p, standings))
    PC.annotate({"matchup": site_data.get("matchup"), "fas": out}, data, now_ms)   # games left / tonight, for the card
    return {"v": now_ms, "n": len(out), "p": out}
