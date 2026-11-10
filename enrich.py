#!/usr/bin/env python3
"""
Deeper stats for the fantasy tool (READ-ONLY, public data only).

Sources
  - NHL.com official stats API: ice time, power-play time, hits/blocks per 60, goalie starts, quality starts
  - MoneyPuck.com (free, credit required): expected goals for skaters, expected goals against for goalies

What it changes
  - Skaters: "expected" points now use expected goals (xG) instead of just regressing shooting %.
  - Goalies: save % is regressed toward the league average (small samples fool everyone).
  - Players with no ESPN projection are pulled toward a replacement-level prior, so a 4-game hot streak
    no longer looks like a star.
  - Goalie start chance uses real games started.
  - Extra stats and flags are attached to each player for the website.

It plugs into analyze.py / dashboard.py by wrapping a few of their functions, so nothing else has to change.
If any data source fails, the tool carries on with what it has.
"""
import csv
import io
import re
import unicodedata

import requests

import analyze as A
import dashboard as D

UA = {"User-Agent": "Mozilla/5.0 (personal fantasy hockey tool)"}
XG_WEIGHT = 0.6            # how much of a skater's expected goals comes from xG (rest from his shrunk real goals)
SV_PRIOR_SHOTS = 600       # shots of "average goalie" mixed in when judging a goalie's save %
LEAGUE_SV = 0.903
PRIORS = {"F": 1.45, "D": 1.5, "G": 1.0}        # replacement-level points per game (per start for goalies)
PRIOR_GAMES = {"F": 12, "D": 12, "G": 6}        # how strongly that prior counts when there is no ESPN projection
SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}

STATE = {"idx": {"sk": {}, "gk": {}}, "abbr": {}, "matched": 0, "missed": [], "errors": 0}
_orig_parse = A.parse_player
_orig_start_prob = D.start_prob


# ---------------------------------------------------------------------------
# Loading data
# ---------------------------------------------------------------------------
def norm(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    return " ".join(w for w in s.split() if w not in SUFFIXES)


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _get(url, params=None):
    try:
        r = requests.get(url, params=params, headers=UA, timeout=40)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  (could not load {url.split('//')[1][:55]}: {e})")
        return None


def nhl_report(report, season_id):
    r = _get(f"https://api.nhle.com/stats/rest/en/{report}",
             {"limit": -1, "cayenneExp": f"seasonId={season_id} and gameTypeId=2"})
    return r.json().get("data", []) if r else []


def moneypuck(kind, year):
    r = _get(f"https://moneypuck.com/moneypuck/playerData/seasonSummary/{year}/regular/{kind}.csv")
    if not r:
        return []
    return [row for row in csv.DictReader(io.StringIO(r.text)) if row.get("situation") == "all"]


def _merge(store, rows, name_key, fields):
    for row in rows:
        pid = row.get("playerId")
        if pid is None:
            continue
        d = store.setdefault(int(pid), {"name": row.get(name_key), "teams": row.get("teamAbbrevs") or ""})
        for src, dst in fields.items():
            if row.get(src) is not None:
                d[dst] = row[src]


def load(season):
    """Returns {'sk': {...}, 'gk': {...}} keyed by NHL player id."""
    sid = f"{season - 1}{season}"
    sk, gk = {}, {}
    _merge(sk, nhl_report("skater/summary", sid), "skaterFullName", {"gamesPlayed": "gp", "timeOnIcePerGame": "toi"})
    _merge(sk, nhl_report("skater/timeonice", sid), "skaterFullName", {"ppTimeOnIcePerGame": "pp"})
    _merge(sk, nhl_report("skater/realtime", sid), "skaterFullName", {"hitsPer60": "h60", "blockedShotsPer60": "b60"})
    _merge(gk, nhl_report("goalie/summary", sid), "goalieFullName", {"gamesStarted": "gs", "gamesPlayed": "gp"})
    _merge(gk, nhl_report("goalie/advanced", sid), "goalieFullName", {"qualityStartsPct": "qs"})
    for row in moneypuck("skaters", season - 1):
        d = sk.get(int(float(row["playerId"])))
        if d is not None:
            d["ixg"] = fnum(row.get("I_F_xGoals"))
            d["xgf"] = fnum(row.get("onIce_xGoalsPercentage"))
    for row in moneypuck("goalies", season - 1):
        d = gk.get(int(float(row["playerId"])))
        xg, g = fnum(row.get("xGoals")), fnum(row.get("goals"))
        if d is not None and xg is not None and g is not None:
            d["gsax"] = xg - g                       # goals saved above expected
    print(f"  NHL/MoneyPuck data: {len(sk)} skaters ({sum(1 for d in sk.values() if 'ixg' in d)} with xG), "
          f"{len(gk)} goalies ({sum(1 for d in gk.values() if 'gsax' in d)} with xG)")
    return {"sk": sk, "gk": gk}


def _index(store):
    idx = {}
    for d in store.values():
        idx.setdefault(norm(d.get("name")), []).append(d)
    return idx


def _find(group, name, team_id):
    cands = STATE["idx"]["gk" if group == "G" else "sk"].get(norm(name), [])
    if len(cands) <= 1:
        return cands[0] if cands else None
    espn = STATE["abbr"].get(team_id)
    nhl = D.NHL_ABBR.get(espn, espn)
    same = [c for c in cands if nhl and nhl in (c.get("teams") or "").split(",")]
    pool = same or cands
    return max(pool, key=lambda c: c.get("gp") or 0)


# ---------------------------------------------------------------------------
# The upgraded model
# ---------------------------------------------------------------------------
def _enrich_skater(p, c):
    toi, pp = fnum(c.get("toi")), fnum(c.get("pp"))
    p["toi"] = toi / 60.0 if toi else None
    p["pp"] = pp / 60.0 if pp is not None else None
    p["h60"], p["b60"] = fnum(c.get("h60")), fnum(c.get("b60"))
    p["xgf"] = c.get("xgf")
    ixg = c.get("ixg")
    gp, g, sog = p["gp"], p.get("g", 0), p.get("sog", 0)
    if ixg is not None and gp > 0:
        shrunk = (g + A.SHOT_PRIOR * A.LEAGUE_SHOOTING_PCT) / (sog + A.SHOT_PRIOR) * sog if (sog or g) else 0
        exp_g = XG_WEIGHT * ixg + (1 - XG_WEIGHT) * shrunk
        p["exp_ppg"] = (p["applied"] - 2 * (g - exp_g)) / gp
        p["ixg"] = ixg
        p["gx"] = g - ixg


def _enrich_goalie(p, c, pl, season):
    stats = {s.get("id"): s for s in pl.get("stats", [])}.get(f"00{season}", {}).get("stats", {})
    sa, sv = A.num(stats, A.S_SA), A.num(stats, A.S_SV)
    p["gs"] = fnum(c.get("gs"))
    qs = fnum(c.get("qs"))
    p["qs"] = qs
    p["gsax"] = c.get("gsax")
    if sa > 0 and p["gp"] > 0 and p["ppg"] is not None:
        sv_reg = (sv + SV_PRIOR_SHOTS * LEAGUE_SV) / (sa + SV_PRIOR_SHOTS)
        extra_saves = (sv_reg - sv / sa) * (sa / p["gp"])        # per start
        p["exp_ppg"] = p["ppg"] + 2.2 * extra_saves              # each extra save = +0.2 and one fewer goal against (+2)


def _finish(p):
    """Recompute outlook (with the replacement-level prior when ESPN has no projection) and flags."""
    g, gp, base, proj = p["group"], p["gp"], p["exp_ppg"], p["proj_ppg"]
    if proj is not None:
        w = A.GAMES_PRIOR_GOALIE if g == "G" else A.GAMES_PRIOR_SKATER
        p["outlook"] = (gp * base + w * proj) / (gp + w) if base is not None else proj
    else:
        w = PRIOR_GAMES[g]
        p["outlook"] = (gp * base + w * PRIORS[g]) / (gp + w) if base is not None else PRIORS[g]
    flags = A.make_flags(p)
    if g == "G":
        gsax = p.get("gsax")
        if gsax is not None and p["gp"] >= 5 and abs(gsax) >= 3:
            flags.append(f"Saving {gsax:+.1f} goals vs expected")
    else:
        if p.get("pp") is not None and p["pp"] >= 2.5:
            flags.append(f"Top power-play role ({p['pp']:.1f} PP min/game)")
        gx = p.get("gx")
        if gx is not None and gp >= 8:
            if gx >= 2.5:
                flags.append(f"Scoring {gx:+.1f} goals above expected - likely to cool")
            elif gx <= -2.5:
                flags.append(f"Scoring {gx:+.1f} goals below expected - due to rise")
    p["flags"] = flags


def _wrapped_parse(pl, season, slot=None, status=None):
    p = _orig_parse(pl, season, slot=slot, status=status)
    try:
        c = _find(p["group"], pl.get("fullName"), pl.get("proTeamId"))
        if c is not None:
            STATE["matched"] += 1
            if p["group"] == "G":
                _enrich_goalie(p, c, pl, season)
            else:
                _enrich_skater(p, c)
        else:
            STATE["missed"].append(pl.get("fullName"))
        _finish(p)
    except Exception:                       # never let a data hiccup break the site
        STATE["errors"] += 1
    return p


def _start_prob(p, standings):
    gs = p.get("gs")
    if gs is not None:
        return D.clamp(gs / D.team_games_played(p["team"], standings), 0.15, 0.9)
    return _orig_start_prob(p, standings)


def install(nhl, abbr):
    """Turn the upgraded model on. abbr = {ESPN pro team id: abbreviation}."""
    STATE["idx"] = {"sk": _index(nhl["sk"]), "gk": _index(nhl["gk"])}
    STATE["abbr"] = abbr
    A.parse_player = _wrapped_parse
    D.start_prob = _start_prob


def summary():
    miss = sorted(set(m for m in STATE["missed"] if m))
    return (f"enrichment: {STATE['matched']} players matched, {len(miss)} not matched, "
            f"{STATE['errors']} errors" + (f" (e.g. {', '.join(miss[:8])})" if miss else ""))
