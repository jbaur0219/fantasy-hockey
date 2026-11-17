#!/usr/bin/env python3
"""
ROLES (READ-ONLY): who plays on which line / power-play unit right now, and whether that is changing.

Source: Daily Faceoff team line-combination pages (public, allowed by robots.txt; one polite request per team
per run, about 32 in total). Credit: DailyFaceoff.com.

What it adds to every skater
  - Role label such as "F1 - PP1" (first line, first power-play unit) or "D3 - PP2" (third pair, second PP unit)
  - Usage trend: ice time over the last 5 games versus the season average
  - A role-aware outlook: his production-based outlook blended with what players in the SAME role typically score
    (computed from the league itself), nudged for rising / falling ice time
  - A tag: core (real role, keep), depth, streamer (replaceable bottom-of-lineup role) or watch (role has slipped)

If a team's page can't be read, those players keep their normal outlook and no tag.
"""
import json
import re
import time
from pathlib import Path

import requests

import analyze as A
import dashboard as D
import enrich as E

SLUGS = {
    "ANA": "anaheim-ducks", "BOS": "boston-bruins", "BUF": "buffalo-sabres", "CGY": "calgary-flames",
    "CAR": "carolina-hurricanes", "CHI": "chicago-blackhawks", "COL": "colorado-avalanche",
    "CBJ": "columbus-blue-jackets", "DAL": "dallas-stars", "DET": "detroit-red-wings", "EDM": "edmonton-oilers",
    "FLA": "florida-panthers", "LA": "los-angeles-kings", "MIN": "minnesota-wild", "MTL": "montreal-canadiens",
    "NSH": "nashville-predators", "NJ": "new-jersey-devils", "NYI": "new-york-islanders",
    "NYR": "new-york-rangers", "OTT": "ottawa-senators", "PHI": "philadelphia-flyers",
    "PIT": "pittsburgh-penguins", "SJ": "san-jose-sharks", "SEA": "seattle-kraken", "STL": "st-louis-blues",
    "TB": "tampa-bay-lightning", "TOR": "toronto-maple-leafs", "UTA": "utah-mammoth", "UTAH": "utah-mammoth",
    "VAN": "vancouver-canucks", "VGK": "vegas-golden-knights", "WSH": "washington-capitals",
    "WPG": "winnipeg-jets",
}
EV = ("f1", "f2", "f3", "f4", "d1", "d2", "d3")
TIER = {"F1": "top line", "F2": "second line", "F3": "third line", "F4": "fourth line",
        "D1": "top pair", "D2": "second pair", "D3": "third pair"}
HIT_ADJ = {"F": 0.17, "D": 0.20}      # hits/GWG are not on the lines pages; this nudges role averages into our scoring
W_BASE, W_SMALL = 0.35, 0.30          # weight on the role average: 35%, rising to 65% for tiny samples
TREND_PER_MIN, TREND_CAP = 0.025, 0.10
KEEP_PPG, KEEP_REC = 1.9, 2.2         # a player producing like this for you is never tagged a streamer

STATE = {"teams": {}, "prior": {"cell": {}, "tier": {}}, "abbr": {}, "ok": [], "failed": [], "errors": 0,
         "cached": [], "cache_age_h": None}
CACHE_FILE = Path(__file__).with_name("cache") / "df_lines.json"
CACHE_MAX_H = 72              # line combinations older than this are not used
STAT_KEYS = ("gamesPlayed", "goals", "assists", "powerplayPoints", "blocks", "shots", "toiMinutes", "toiSeconds")
PREV = {}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _toi(stats):
    gp = stats.get("gamesPlayed") or 0
    return (((stats.get("toiMinutes") or 0) + (stats.get("toiSeconds") or 0) / 60.0) / gp) if gp else None


def _df_ppg(s):
    gp = s.get("gamesPlayed") or 0
    if not gp:
        return None
    return (2 * (s.get("goals") or 0) + (s.get("assists") or 0) + 0.5 * (s.get("powerplayPoints") or 0)
            + 0.5 * (s.get("blocks") or 0) + 0.1 * (s.get("shots") or 0)) / gp


def parse_team(comb):
    """{normalized name: role info} for one team's line-combinations page data."""
    out = {}
    for pl in comb.get("players", []):
        name = pl.get("name")
        if not name:
            continue
        d = out.setdefault(E.norm(name), {"name": name, "ev": None, "pp": 0, "g": None, "toi": None,
                                          "toi5": None, "stats": None, "inj": None})
        gid = pl.get("groupIdentifier") or ""
        if gid in EV:
            d["ev"] = gid.upper()
            if d["stats"] is None:
                d["stats"] = pl.get("season") or {}
        elif gid == "pp1":
            d["pp"] = 1
        elif gid == "pp2" and d["pp"] == 0:
            d["pp"] = 2
        elif gid == "g":
            d["g"] = (pl.get("positionIdentifier") or "").upper()
        if pl.get("injuryStatus"):
            d["inj"] = pl.get("injuryStatus")
        if d["toi"] is None:
            d["toi"] = _toi(pl.get("season") or {})
        if d["toi5"] is None:
            d["toi5"] = _toi(pl.get("last5") or {})
    for d in out.values():                                   # keep only what the model uses (small cache file)
        if d["stats"]:
            d["stats"] = {k: d["stats"].get(k) for k in STAT_KEYS}
    return out


def build_priors(teams):
    """Average points per game for each (line, power-play unit) combination across the whole league."""
    cells, tiers = {}, {}
    for team in teams.values():
        for e in team.values():
            s, ev = e.get("stats"), e.get("ev")
            if not ev or not s or (s.get("gamesPlayed") or 0) < 5:
                continue
            v = _df_ppg(s)
            cells.setdefault((ev, e["pp"]), []).append(v)
            tiers.setdefault(ev, []).append(v)
    mean = lambda xs: sum(xs) / len(xs)
    return {"cell": {k: mean(v) for k, v in cells.items() if len(v) >= 4},
            "tier": {k: mean(v) for k, v in tiers.items()}}


def _now_ms():
    try:
        import netcache
        return netcache.now_ms()
    except Exception:
        return int(time.time() * 1000)


def _read_cache():
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_cache(cache):
    try:
        import netcache
        if netcache.STATE["mode"] == "replay":
            return                                           # test replays never touch the saved cache
    except Exception:
        pass
    CACHE_FILE.parent.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, separators=(",", ":"), sort_keys=True), encoding="utf-8")


def _fetch(slug):
    url = f"https://www.dailyfaceoff.com/teams/{slug}/line-combinations"
    last = None
    for attempt in range(2):
        try:
            r = requests.get(url, headers=E.UA, timeout=30)
            r.raise_for_status()
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
            return parse_team(json.loads(m.group(1))["props"]["pageProps"]["combinations"]), None
        except Exception as e:
            last = e
            code = getattr(getattr(e, "response", None), "status_code", None)
            if attempt == 0 and code in (403, 429, 500, 502, 503, 504):
                time.sleep(6)
                continue
            break
    return None, last


def load(abbrs):
    """Reads each team's page. Returns {ESPN abbreviation: {name: role info}}.

    If Daily Faceoff blocks the request (it sometimes refuses GitHub's servers), each team falls back to its last good
    copy from cache/df_lines.json when that copy is under CACHE_MAX_H hours old. After two teams in a row are refused,
    the rest are not requested (they would be refused too) and come from the cache.
    """
    teams, cache, now = {}, _read_cache(), _now_ms()
    blocked = 0
    for ab in sorted(set(abbrs)):
        slug = SLUGS.get(ab)
        if not slug:
            continue
        got, err = (None, "skipped after repeated refusals") if blocked >= 2 else _fetch(slug)
        if got:
            teams[ab] = got
            cache[ab] = {"at": now, "players": got}
            STATE["ok"].append(ab)
            blocked = 0
        else:
            code = getattr(getattr(err, "response", None), "status_code", None) if not isinstance(err, str) else None
            blocked = blocked + 1 if (code in (403, 429) or isinstance(err, str)) else blocked
            c = cache.get(ab)
            if c and (now - c.get("at", 0)) <= CACHE_MAX_H * 3600 * 1000:
                teams[ab] = c["players"]
                STATE["cached"].append(ab)
                age = (now - c["at"]) / 3600000
                STATE["cache_age_h"] = max(STATE["cache_age_h"] or 0, age)
            else:
                STATE["failed"].append(f"{ab} ({type(err).__name__ if not isinstance(err, str) else 'blocked'})")
        time.sleep(0.35)
    if STATE["ok"]:
        _write_cache(cache)
    print(f"  Daily Faceoff lines: {len(STATE['ok'])} teams read"
          + (f", {len(STATE['cached'])} from the saved copy (up to {STATE['cache_age_h']:.0f} h old)" if STATE["cached"] else "")
          + (f", missing: {', '.join(STATE['failed'])}" if STATE["failed"] else ""))
    return teams


def health():
    """'live', 'cached' or 'missing', plus a short plain-English note for the page."""
    n_ok, n_c, n_f = len(STATE["ok"]), len(STATE["cached"]), len(STATE["failed"])
    if n_ok + n_c == 0:
        return {"state": "missing", "note": "Line and power-play data could not be loaded, so moves ignore roles."}
    if n_c or n_f:
        age = STATE["cache_age_h"] or 0
        note = f"Line data: {n_ok} teams fresh, {n_c} from a saved copy up to {age:.0f} h old"
        if n_f:
            note += f", {n_f} missing"
        return {"state": "cached" if not n_f else "partial", "note": note + "."}
    return {"state": "live", "note": "Line data fresh."}


# ---------------------------------------------------------------------------
# Role helpers
# ---------------------------------------------------------------------------
def label(ev, pp):
    parts = [ev] if ev else []
    if pp:
        parts.append(f"PP{pp}")
    return " - ".join(parts) if parts else "no role"


def phrase(ev, pp):
    parts = [TIER[ev]] if ev in TIER else []
    if pp == 1:
        parts.append("first power-play unit")
    elif pp == 2:
        parts.append("second power-play unit")
    return " and ".join(parts) if parts else "no line role"


def is_top(grp, ev, pp):
    return pp == 1 or (grp == "F" and ev in ("F1", "F2")) or (grp == "D" and ev in ("D1", "D2"))


def classify(p):
    """core / depth / streamer / watch for a skater with a known role."""
    ev, pp, tr = p.get("ev"), p.get("ppu") or 0, p.get("tr")
    grp = p["group"]
    if p.get("rl") == "Off lines":
        return "watch"
    top = is_top(grp, ev, pp)
    fading = tr is not None and tr <= -3.0            # a 2-minute dip is noise; 3+ minutes is a real change
    producing = (p.get("ppg") or 0) >= KEEP_PPG or (p.get("recent_ppg") or 0) >= KEEP_REC
    if top and fading:
        return "watch"
    if top:
        return "core"
    low = (grp == "F" and ev in ("F3", "F4")) or (grp == "D" and ev == "D3")
    if low and not producing:
        return "streamer"
    return "depth"


# ---------------------------------------------------------------------------
# The role-aware outlook (wraps the player parser)
# ---------------------------------------------------------------------------
def _find(team, name):
    """Exact match first; then same last name + same first initial (Gabe vs Gabriel), only if unambiguous."""
    n = E.norm(name)
    if n in team:
        return team[n]
    parts = n.split()
    if len(parts) < 2:
        return None
    hits = [e for k, e in team.items() if k.split()[-1:] == [parts[-1]] and k[:1] == n[:1]]
    return hits[0] if len(hits) == 1 else None


def _apply(p, pl):
    team = STATE["teams"].get(STATE["abbr"].get(pl.get("proTeamId")))
    if team is None:
        return                                           # that team's page wasn't read: leave the player alone
    e = _find(team, pl.get("fullName"))
    if p["group"] == "G":
        if e and e.get("g"):
            p["rl"] = e["g"]
        return
    if e is None:
        p["rl"] = "Not listed"                           # not on the page under any matching name: unknown, so no tag
        return
    if e["ev"] is None and not e["pp"]:
        p["rl"], p["ev"], p["ppu"] = "Off lines", None, 0
        p["cls"] = classify(p)
        return
    ev, pp = e["ev"], e["pp"]
    p["rl"], p["ev"], p["ppu"] = label(ev, pp), ev, pp
    toi, toi5 = e.get("toi"), e.get("toi5")
    p["toi5"] = toi5
    p["tr"] = (toi5 - toi) if (toi is not None and toi5 is not None) else None
    pri = STATE["prior"]["cell"].get((ev, pp)) or STATE["prior"]["tier"].get(ev)
    if pri is not None:
        prior = pri + HIT_ADJ[p["group"]]
        w = W_BASE + W_SMALL * max(0, (10 - p["gp"]) / 10.0)
        mult = 1.0 if p["tr"] is None else max(1 - TREND_CAP, min(1 + TREND_CAP, 1 + TREND_PER_MIN * p["tr"]))
        p["outlook_before_role"] = p["outlook"]
        p["role_prior"] = prior
        p["outlook"] = ((1 - w) * p["outlook"] + w * prior) * mult
    p["cls"] = classify(p)
    if p["cls"] == "streamer":
        p["flags"].append(f"Replaceable role ({label(ev, pp)})")
    if p["tr"] is not None and abs(p["tr"]) >= 2.0:
        p["flags"].append(f"Ice time {'down' if p['tr'] < 0 else 'up'} {abs(p['tr']):.1f} min over last 5 games")


def _wrapped(pl, season, slot=None, status=None):
    p = PREV["parse"](pl, season, slot=slot, status=status)
    try:
        _apply(p, pl)
    except Exception:
        STATE["errors"] += 1
    return p


def install(teams, abbr):
    """Turn on role-aware values. abbr = {ESPN pro team id: abbreviation}."""
    PREV["parse"] = A.parse_player                       # keep the stats layer that is already installed
    STATE["teams"], STATE["abbr"] = teams, abbr
    STATE["prior"] = build_priors(teams)
    A.parse_player = _wrapped


def summary():
    return (f"roles: {len(STATE['ok'])} teams, {len(STATE['prior']['cell'])} role groups, {STATE['errors']} errors")
