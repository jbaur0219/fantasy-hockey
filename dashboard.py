#!/usr/bin/env python3
"""
LEAGUE CONTEXT (READ-ONLY): the matchup, schedule helpers, the daily add-lock clock, team strength, win chance
inputs, lineup alerts and standings. build.py uses it through site_builder.py. It never changes anything in ESPN.
"""
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import analyze as A

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
HOME_ICE = 0.03          # home-ice edge in win probability
SKATER_SD = 2.3          # typical game-to-game swing for a skater (fantasy points)
GOALIE_SD = 6.0          # typical swing for a goalie start
DEFAULT_TEAM_GP = 19     # used if NHL standings can't be loaded
GOALIE_DAYS = 3          # how many days ahead to show goalie calls (build_context uses the whole matchup)
CUR_DAYS = GOALIE_DAYS   # days left in the current matchup (set by build_context)
MAX_DAYS = 14            # longest matchup the planner handles (ESPN can merge two weeks, e.g. around a break)
NHL_ABBR = {"NJ": "NJD", "TB": "TBL", "SJ": "SJS", "LA": "LAK"}   # ESPN -> NHL names


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def norm_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def log5(a, b):
    """Chance team A beats team B given their strengths a and b (0-1)."""
    d = a * (1 - b) + b * (1 - a)
    return a * (1 - b) / d if d else 0.5


def et_zone():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")
    except Exception:
        return timezone.utc


def fmt_game(ms):
    d = datetime.fromtimestamp(ms / 1000, et_zone())
    return d.strftime("%a %b %d").replace(" 0", " "), d.strftime("%I:%M %p").lstrip("0")


def day_clock(schedules, sp, ndays, now_ms):
    """Same as day_clock_games, reading the games out of ESPN's schedule JSON."""
    return day_clock_games(schedule_maps(schedules)[1], sp, ndays, now_ms)


def day_clock_games(games, sp, ndays, now_ms):
    """The days the site plans for, and when each one locks.

    In this league nobody can add a player once the first game of the day has started, so a day is "locked"
    from the first puck drop of ANY NHL game that day. Returns {"built", "dates", "labels", "lock"} with one entry
    per day: the ET date (YYYY-MM-DD), its label ("Sat Nov 14") and the first puck drop in ms (None on an off day).
    Dates come from the real schedule for each scoring period, so they stay right even if ESPN has not rolled
    over to the new scoring period yet (late games, early morning).
    """
    tz = et_zone()
    firsts = []
    for i in range(ndays):
        starts = [g.get("date") for gl in games.values() for g in gl.get(str(sp + i), []) if g.get("date")]
        firsts.append(min(starts) if starts else None)
    # anchor: the first day with a known first game, else today
    anchor = None
    for i, ms in enumerate(firsts):
        if ms:
            anchor = datetime.fromtimestamp(ms / 1000, tz).date() - timedelta(days=i)
            break
    if anchor is None:
        anchor = datetime.fromtimestamp(now_ms / 1000, tz).date()
    dates = [anchor + timedelta(days=i) for i in range(ndays)]
    return {"built": int(now_ms),
            "dates": [d.isoformat() for d in dates],
            "labels": [d.strftime("%a %b %d").replace(" 0", " ") for d in dates],
            "lock": firsts}


def day_locked(clock, i, now_ms):
    """True once day i can no longer take adds (its first puck has dropped, or the day is over)."""
    ms = clock["lock"][i] if i < len(clock["lock"]) else None
    if ms:
        return now_ms >= ms
    return clock["dates"][i] < datetime.fromtimestamp(now_ms / 1000, et_zone()).date().isoformat()


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def load_nhl_standings():
    """{NHL abbrev: {'pct': points%, 'gp': games}}  -  {} if unavailable."""
    try:
        r = requests.get("https://api-web.nhle.com/v1/standings/now", timeout=20)
        r.raise_for_status()
        rows = r.json().get("standings", [])
    except Exception as e:  # never crash because of the NHL feed
        print(f"(NHL standings unavailable: {e}; using neutral team strength)")
        return {}
    out = {}
    for s in rows:
        ab = (s.get("teamAbbrev") or {}).get("default")
        gp = s.get("gamesPlayed") or 0
        pct = s.get("pointPctg")
        if pct is None and gp:
            pct = (s.get("points") or 0) / (2 * gp)
        if ab and gp and pct is not None:
            out[ab] = {"pct": float(pct), "gp": gp}
    return out


def team_strength(abbrev, standings):
    """0.5 = average team. Built from NHL points %, shifted so the league average is 0.5."""
    if not standings:
        return 0.5
    mean = sum(v["pct"] for v in standings.values()) / len(standings)
    row = standings.get(NHL_ABBR.get(abbrev, abbrev))
    return clamp(0.5 + (row["pct"] - mean), 0.3, 0.7) if row else 0.5


def team_games_played(abbrev, standings):
    row = standings.get(NHL_ABBR.get(abbrev, abbrev))
    return row["gp"] if row else DEFAULT_TEAM_GP


def schedule_maps(schedules):
    abbr, games = {}, {}
    for t in schedules.get("settings", {}).get("proTeams", []):
        abbr[t.get("id")] = t.get("abbrev", "?")
        games[t.get("id")] = t.get("proGamesByScoringPeriod") or {}
    return abbr, games


def games_on(games, team_id, sp, now_ms=None):
    """Games for a pro team on scoring period sp. If now_ms is given, only games not yet started."""
    lst = games.get(team_id, {}).get(str(sp), [])
    if now_ms is not None:
        lst = [g for g in lst if g.get("date", 0) > now_ms]
    return lst


def roster_players(team_json, season, abbr):
    out = []
    for e in team_json.get("roster", {}).get("entries", []):
        p = A.parse_player(e["playerPoolEntry"]["player"], season, slot=e.get("lineupSlotId"))
        p["team"] = abbr.get(p["team_id"], "?")
        out.append(p)
    return out


def team_label(t):
    return t.get("name") or f"{t.get('location', '')} {t.get('nickname', '')}".strip() or f"Team {t.get('id')}"


def record_of(t):
    o = (t.get("record") or {}).get("overall") or {}
    return o.get("wins", 0), o.get("losses", 0), o.get("ties", 0), o.get("pointsFor", 0)


# ---------------------------------------------------------------------------
# Matchup + win probability
# ---------------------------------------------------------------------------
def find_matchup(league, team_id):
    mp = (league.get("status") or {}).get("currentMatchupPeriod")
    for m in league.get("schedule", []):
        if m.get("matchupPeriodId") == mp and team_id in (m["home"].get("teamId"), m["away"].get("teamId")):
            mine, theirs = (m["home"], m["away"]) if m["home"].get("teamId") == team_id else (m["away"], m["home"])
            return mp, m, mine, theirs
    return mp, None, None, None


def matchup_length(league, mp):
    """Days in matchup mp: 7 per NHL week ESPN maps to it (usually one week, sometimes two around a break)."""
    try:
        weeks = ((league.get("settings") or {}).get("scheduleSettings") or {}).get("matchupPeriods", {}).get(str(mp))
        return 7 * max(1, len(weeks or [1]))
    except Exception:
        return 7


DEFAULT_MOVE_LIMIT = 7      # used only when the league's settings can't be read (the app then says so)
NO_LIMIT = 99               # stands in for "no weekly limit" in the planner


def move_limit_info(league, days):
    """This league's add limit for one matchup of `days` days, from its own ESPN settings.
    {"limit": adds allowed, "unlimited": no weekly cap, "known": read from the settings (not the fallback),
     "season_limit": adds allowed all season or None}"""
    acq = ((league or {}).get("settings") or {}).get("acquisitionSettings")
    if not isinstance(acq, dict) or acq.get("matchupAcquisitionLimit") is None:
        return {"limit": DEFAULT_MOVE_LIMIT, "unlimited": False, "known": False, "season_limit": None}
    try:
        lim = int(acq.get("matchupAcquisitionLimit"))
    except (TypeError, ValueError):
        return {"limit": DEFAULT_MOVE_LIMIT, "unlimited": False, "known": False, "season_limit": None}
    try:
        sl = int(acq.get("acquisitionLimit")) if acq.get("acquisitionLimit") is not None else -1
    except (TypeError, ValueError):
        sl = -1
    season = sl if sl >= 0 else None
    if lim < 0:
        return {"limit": NO_LIMIT, "unlimited": True, "known": True, "season_limit": season}
    if acq.get("matchupLimitPerScoringPeriod"):
        # the limit is per day: that many each day, and a day that has gone by can't be used any more
        return {"limit": lim * max(1, days), "unlimited": False, "known": True, "season_limit": season, "per_day": lim}
    return {"limit": lim, "unlimited": False, "known": True, "season_limit": season}


IR_OK = {"OUT", "INJURY_RESERVE"}   # injury statuses ESPN lets you put in an IR spot


def ir_free(league, mine):
    """Open IR spots on your roster: the league's IR slot count (ESPN slot ids 8-10 here) minus players already there."""
    counts = (((league or {}).get("settings") or {}).get("rosterSettings") or {}).get("lineupSlotCounts") or {}
    total = 0
    for k, v in counts.items():
        try:
            if int(k) in A.IR_SLOTS:
                total += int(v or 0)
        except (TypeError, ValueError):
            pass
    used = sum(1 for p in mine or [] if p.get("slot") == "IR")
    return max(0, total - used)


def move_limit(league, days):
    """Adds allowed this matchup, from the league's settings (NO_LIMIT when the league has no weekly cap)."""
    return move_limit_info(league, days)["limit"]


def move_budget(league, my_id, days=None, days_left=None):
    """How many adds you can still make this matchup, by this league's own rules.
    {"limit", "used", "left", "unlimited", "known", "used_known", "season_left"}. `left` also respects a season cap."""
    mp = ((league or {}).get("status") or {}).get("currentMatchupPeriod")
    if days is None:
        days = matchup_length(league or {}, mp)
    info = move_limit_info(league, days)
    team = next((t for t in (league or {}).get("teams", []) if t.get("id") == my_id), {}) or {}
    tc = team.get("transactionCounter") or {}
    used = None
    try:
        v = (tc.get("matchupAcquisitionTotals") or {}).get(str(mp))
        used = int(v) if v is not None else (0 if "matchupAcquisitionTotals" in tc else None)
    except (TypeError, ValueError):
        used = None
    left = max(0, info["limit"] - (used or 0))
    if info.get("per_day") and days_left is not None:
        left = info["per_day"] * max(0, int(days_left))     # unused days don't carry over (today's own adds unknown)
    season_left = None
    if info["season_limit"] is not None:
        try:
            season_left = max(0, info["season_limit"] - int(tc.get("acquisitions") or 0))
            left = min(left, season_left)
        except (TypeError, ValueError):
            season_left = None
    return {"limit": info["limit"], "used": used, "left": left, "unlimited": info["unlimited"],
            "known": info["known"], "used_known": used is not None, "season_left": season_left,
            "per_day": info.get("per_day")}


def matchup_periods(m, mp, length=7):
    keys = [int(k) for side in (m["home"], m["away"]) for k in (side.get("pointsByScoringPeriod") or {})]
    start = min(keys) if keys else 7 * (mp - 1)
    return start, start + length - 1


def side_points(side):
    return float(side.get("totalPointsLive", side.get("totalPoints", 0)) or 0)


def start_prob(p, standings):
    """Rough chance a goalie starts a given team game."""
    gp_team = team_games_played(p["team"], standings)
    w = (p["gp"] / gp_team) if p["gp"] else 0.2
    return clamp(w, 0.2, 0.9)


def _slots():
    import league as L
    return L.SLOTS


def expected_remaining(players, periods, games, now_ms, standings):
    """Expected points + variance for the rest of the week, using the best lineup each day."""
    mu = var = 0.0
    for sp in periods:
        avail = [p for p in players
                 if A.slot_name(p["slot"]) != "IR" and p["injury"] not in A.BAD_INJURY
                 and games_on(games, p["team_id"], sp, now_ms)]
        gks = sorted(((p["outlook"] * start_prob(p, standings), start_prob(p, standings))
                      for p in avail if p["group"] == "G"), reverse=True)[:_slots()["G"]]
        for ev, w in gks:
            mu += ev
            var += w * GOALIE_SD ** 2
        fwd = sorted([p for p in avail if p["group"] == "F"], key=lambda p: -p["outlook"])
        dfn = sorted([p for p in avail if p["group"] == "D"], key=lambda p: -p["outlook"])
        S_ = _slots()
        used = fwd[:S_["F"]] + dfn[:S_["D"]]
        rest = sorted(fwd[S_["F"]:] + dfn[S_["D"]:], key=lambda p: -p["outlook"])
        used += rest[:S_["UTIL"]]                                      # UTIL slot(s)
        for p in used:
            mu += p["outlook"]
            var += SKATER_SD ** 2
    return mu, var


# ---------------------------------------------------------------------------
# Goalie decisions
# ---------------------------------------------------------------------------
def goalie_decisions(mine, sp, games, abbr, standings, now_ms):
    """Start / bench calls for every day left in the matchup (see goalies.py)."""
    import goalies
    return goalies.build(mine, sp, games, abbr, standings, now_ms, CUR_DAYS, slots=_slots()["G"])


# ---------------------------------------------------------------------------
# Lineup alerts
# ---------------------------------------------------------------------------
def lineup_alerts(mine, sp, games, now_ms):
    alerts = []
    starters = [p for p in mine if A.slot_name(p["slot"]) in ("F", "D", "G", "UTIL")]
    bench = [p for p in mine if A.slot_name(p["slot"]) == "BN"]
    for p in starters:
        if p["injury"] in A.BAD_INJURY:
            alerts.append(("bad", f"{p['name']} is in your lineup but listed {p['injury'].replace('_', ' ').title()}."))
    idle = [p for p in starters if p["injury"] not in A.BAD_INJURY and not games_on(games, p["team_id"], sp)]
    ready = [p for p in bench if p["injury"] not in A.BAD_INJURY and games_on(games, p["team_id"], sp, now_ms)]
    used = set()
    for b in sorted(ready, key=lambda p: -p["outlook"]):
        for s in sorted(idle, key=lambda p: p["outlook"]):
            if id(s) in used:
                continue
            same = (s["group"] == b["group"]) or (A.slot_name(s["slot"]) == "UTIL" and b["group"] != "G")
            if same:
                used.add(id(s))
                alerts.append(("warn", f"Start {b['name']} (has a game today) in place of {s['name']} (no game)."))
                break
    return alerts


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def build_context(cfg, data, league, standings, now_ms):
    season, my_id = cfg["season"], cfg["team"]
    abbr, games = schedule_maps(data["schedules"])
    sp = data["roster"].get("scoringPeriodId", 1)
    mine, fas = A.build_players(data, cfg)
    moves = []                                   # move suggestions come from core.py (Game plan)

    teams = {t.get("id"): t for t in league.get("teams", [])}
    me_t = teams.get(my_id, {})
    w, l, t_, _ = record_of(me_t)

    matchup = None
    mp, m, my_side, opp_side = find_matchup(league, my_id)
    if m:
        opp_id = opp_side.get("teamId")
        opp_json = next((t for t in data["roster"].get("teams", []) if t.get("id") == opp_id), None)
        length = matchup_length(league, mp)
        global CUR_DAYS
        start, end = matchup_periods(m, mp, length)
        periods = list(range(max(sp, start), end + 1))
        CUR_DAYS = max(1, len(periods))
        mu_me, var_me = expected_remaining(mine, periods, games, now_ms, standings)
        opp_players = roster_players(opp_json, season, abbr) if opp_json else []
        mu_opp, var_opp = expected_remaining(opp_players, periods, games, now_ms, standings)
        me_now, opp_now = side_points(my_side), side_points(opp_side)
        sd = math.sqrt(var_me + var_opp) or 1.0
        z = (me_now + mu_me - opp_now - mu_opp) / sd
        ow, ol, ot, _ = record_of(teams.get(opp_id, {}))
        matchup = {"me_now": me_now, "opp_now": opp_now, "proj_me": me_now + mu_me, "proj_opp": opp_now + mu_opp,
                   "p_win": clamp(norm_cdf(z), 0.01, 0.99), "days_left": len(periods),
                   "days_total": length, "move_limit": move_limit(league, length),
                   "opp_name": team_label(teams.get(opp_id, {})), "opp_rec": f"{ow}-{ol}-{ot}", "opp_id": opp_id}

    standings_rows = []
    for tid, t in teams.items():
        tw, tl, tt, pf = record_of(t)
        standings_rows.append({"name": team_label(t), "rec": f"{tw}-{tl}-{tt}", "pf": pf, "w": tw, "me": tid == my_id})
    standings_rows.sort(key=lambda s: (-s["w"], -s["pf"]))

    return {
        "league_name": (league.get("settings") or {}).get("name", "Fantasy Hockey League"),
        "my_name": team_label(me_t) if me_t else "My Team",
        "my_rec": f"{w}-{l}-{t_}",
        "updated": datetime.now(et_zone()).strftime("%a %b %d, %I:%M %p ET").replace(" 0", " "),
        "matchup": matchup,
        "goalies": goalie_decisions(mine, sp, games, abbr, standings, now_ms),
        "moves": moves,
        "alerts": lineup_alerts(mine, sp, games, now_ms),
        "standings": standings_rows,
        "mine": mine,
        "fas": fas,
    }
