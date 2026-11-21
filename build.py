#!/usr/bin/env python3
"""
Builds the site. READ-ONLY: it only reads ESPN and public stats; it never adds, drops, trades or changes anything.

Run:  python3 build.py     ->  writes site/index.html (+ the phone-app files and the morning alert text)

How it fits together
  1. Data: ESPN (your league, rosters, free agents, schedule), NHL.com (standings, ice time), MoneyPuck (expected goals)
     and DailyFaceoff (lines, power plays, starting goalies). enrich / starters / roles add those to every player.
  2. Model: streams (player values, drop rules, streams cards), core (the one move plan), goalies (start/bench),
     planner (week at a glance), weekplan (keeps the plan steady and tracks what you did), edge (schedule table).
  3. Page: web/page.html + web/app.css + web/app.js, with the data dropped in as JSON. The page is plain files now
     (no more text patching), so what you see in those files is exactly what ships.

Testing: FH_RECORD=snap.json.gz saves every web response; FH_REPLAY=snap.json.gz rebuilds offline from it
(see tools/replay.sh, tools/compare.py, tools/smoke.py and tests/).
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import analyze as A
import core as C
import dashboard as D
import edge as EDG
import enrich as E
import gamelog as GL
import gameplan as GP
import keep as KP
import netcache as NC
import planner as PL
import playercard as PC
import pool as POOL
import pwa
import record as RC
import roles as R
import scoreboard as SBD
import site_builder as SB
import starters as S
import streams as STR
import weekplan as WK

_base_slim = SB.slim
EXTRA = ("toi", "pp", "ixg", "gx", "xgf", "gs", "qs", "gsax", "h60", "b60", "own_chg")


NHL_OK = {"on": False}


def slim_full(p, standings):
    """The page data for one player: the basics, NHL.com / MoneyPuck extras when loaded, and line roles."""
    d = _base_slim(p, standings)
    if NHL_OK["on"]:
        for k in EXTRA:
            if p.get(k) is not None:
                d[k] = SB.r3(p[k])
    return STR.slim_roles(d, p)


REQUIRED = ("function gameplanRender", "function streamsRender", "function plannerRender", "function uiStart",
            "LK.start();", "function pcTag", "function wiResult", "function suggestFor", "uiToday")


def health_report(site_data, nhl_counts):
    """What data this build had, in plain English, for the badge at the top of the page and the alerts."""
    items, level = [], "ok"
    lines = R.health()
    if lines["state"] == "missing":
        level = "bad"
        items.append(lines["note"])
    elif lines["state"] != "live":
        level = "warn" if (R.STATE["cache_age_h"] or 0) > 24 or lines["state"] == "partial" else level
        items.append(lines["note"])
    if S.HEALTH["state"] in ("missing", "cached") and S.HEALTH["note"]:
        level = "warn" if level == "ok" and S.HEALTH["state"] == "missing" else level
        items.append(S.HEALTH["note"])
    sk, xg = nhl_counts
    if not sk:
        level = "bad"
        items.append("NHL.com stats could not be loaded, so projections are rougher than usual.")
    elif not xg:
        level = "warn" if level == "ok" else level
        items.append("MoneyPuck expected goals could not be loaded.")
    if not site_data.get("matchup"):
        items.append("This week's matchup was not found.")
    return {"level": level, "items": items,
            "lines": lines["state"], "starters": S.HEALTH["state"],
            "healthy_plan": lines["state"] == "live" or (lines["state"] == "cached" and (R.STATE["cache_age_h"] or 0) <= 24)}


def scoring_weights(league):
    """This league's points per stat, as {ESPN stat id: points}, read from the league settings."""
    try:
        items = ((league.get("settings") or {}).get("scoringSettings") or {}).get("scoringItems") or []
        return {str(i["statId"]): i.get("points", 0) for i in items if i.get("points")}
    except Exception:
        return {}


CORE_SECTIONS = ("streams", "gameplan", "planner")   # the move advice; a build missing any of these is degraded


def write_health_file(site_data, now_ms):
    """site/health.json: a small summary the publish check (tools/publish_gate.py) compares with the live site."""
    h = site_data.get("health") or {}
    missing = [k for k in CORE_SECTIONS if not site_data.get(k)]
    out = {"level": h.get("level", "ok"), "items": h.get("items", []), "missing": missing,
           "core_ok": not missing, "at": now_ms}
    Path("site/health.json").write_text(json.dumps(out), encoding="utf-8")
    if missing:
        print("  DEGRADED: these sections failed: " + ", ".join(missing))


def write_notify_payload(site_data, now_ms):
    """The text of the morning push notification, for notify.py."""
    clock = site_data.get("clock")
    gp = site_data.get("gameplan") or {}
    moves = gp.get("moves") or []
    first_open = 0
    if clock:
        first_open = next((i for i in range(len(clock["lock"])) if not D.day_locked(clock, i, now_ms)), None)
    label = clock["labels"][first_open] if clock and first_open is not None else datetime.fromtimestamp(now_ms / 1000, D.et_zone()).strftime("%a %b %d")

    def line(m):
        return f"add {m['add']['n']} ({m['add']['tm']}), drop {m['drop']['n']} (+{m['gain']:.1f})"

    # only Strong moves are worth a ping; smaller ones wait in the app
    strong = [m for m in moves if m.get("conf") == "strong"]
    today = [m for m in strong if m.get("t") == first_open]
    claims = [m for m in strong if m.get("waiver") and first_open is not None and m.get("t") == first_open + 1]
    small = [m for m in moves if m.get("t") == first_open and m.get("conf") != "strong"]
    if today:
        parts = [("Do today: ") + "; ".join(line(m) for m in today[:2]) + "."]
    else:
        parts = ["Nothing you need to do today."]
        nxt = next((m for m in strong if first_open is None or m.get("t", 0) > first_open), None)
        if nxt:
            parts.append(f"Next: {nxt['day'].split()[0]}, {line(nxt)}.")
    for m in claims[:1]:
        parts.append(f"Put in a waiver claim for {m['add']['n']} today.")
    if small and not today:
        parts.append(f"{len(small)} smaller optional move{'s' if len(small) != 1 else ''} in the app.")
    m = site_data.get("matchup")
    if m:
        parts.append(f"Win chance {m['p_win'] * 100:.0f}%.")
    if gp.get("moves_left") is not None:
        parts.append(f"{gp['moves_left']} moves left.")
    h = site_data.get("health") or {}
    if h.get("level") == "bad":
        parts.append("Warning: " + " ".join(h.get("items", [])[:1]))
    payload = {"title": f"Fantasy Hockey \u00b7 {label}", "body": " ".join(parts), "url": "./", "tag": "fh-daily"}
    Path("notify_payload.json").write_text(json.dumps(payload), encoding="utf-8")
    print(f"  alert text: {payload['title']} | {payload['body']}")


def main():
    NC.install()
    try:
        _main()
    finally:
        NC.save()


def _main():
    cfg = A.get_config()
    print("Reading your ESPN league...")
    data = A.fetch_all(cfg)
    base = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{cfg['season']}"
    league = A.espn_get(f"{base}/segments/0/leagues/{cfg['league']}", cfg["cookies"],
                        params=[("view", "mSettings"), ("view", "mTeam"),
                                ("view", "mMatchup"), ("view", "mMatchupScore")])
    standings = D.load_nhl_standings()
    abbr, _ = D.schedule_maps(data["schedules"])
    mp_now = (league.get("status") or {}).get("currentMatchupPeriod")
    KP.apply_env(mp_now)                                # "Keep him" list sent from the page with this refresh
    try:
        RC.install(data, cfg["season"])                 # season points for the track record
    except Exception as e:
        print(f"  track-record totals skipped ({type(e).__name__}: {e})")

    nhl_counts = (0, 0)
    print("Loading deeper stats...")
    try:
        nhl = E.load(cfg["season"])
        nhl_counts = (len(nhl["sk"]), sum(1 for d in nhl["sk"].values() if "ixg" in d))
        if nhl["sk"] or nhl["gk"]:
            E.install(nhl, abbr)
            NHL_OK["on"] = True
        else:
            print("  no deeper stats available")
    except Exception as e:
        print(f"  deeper stats failed ({type(e).__name__}: {e})")
    try:
        S.install(S.load())
    except Exception as e:
        print(f"  starting goalies skipped ({type(e).__name__}: {e})")
    try:
        R.install(R.load(set(abbr.values())), abbr)
        print(" ", R.summary())
    except Exception as e:
        print(f"  line roles skipped ({type(e).__name__}: {e})")
    STR.install()
    SB.slim = slim_full

    now_ms = NC.now_ms()
    site_data = SB.build_site_data(cfg, data, league, standings, now_ms)
    site_data["v"] = now_ms                                 # data version: the open app reloads when this changes
    site_data["scoring"] = scoring_weights(league)          # ESPN stat id -> points, for live points during games
    _ab, _gm = D.schedule_maps(data["schedules"])
    site_data["g28"] = C.team_games(_gm, _ab, data["roster"].get("scoringPeriodId", 1), 28)   # trade values: next 4 weeks
    if site_data.get("matchup"):
        PL.MOVE_LIMIT = site_data["matchup"].get("move_limit", PL.MOVE_LIMIT)
    try:
        _m = site_data.get("matchup")
        _nd = max(1, min(int(_m["days_left"]) if _m else 7, D.MAX_DAYS))
        site_data["clock"] = D.day_clock(data["schedules"], data["roster"].get("scoringPeriodId", 1), _nd, now_ms)
        lk = [i for i in range(_nd) if D.day_locked(site_data["clock"], i, now_ms)]
        first = site_data["clock"]["lock"][0]
        print(f"  day lock: {site_data['clock']['labels'][0]} first puck "
              f"{datetime.fromtimestamp(first / 1000, D.et_zone()).strftime('%I:%M %p') if first else 'no games'}; "
              f"{len(lk)} day(s) already locked")
    except Exception as e:                                  # the page copes without it; never fail the build over this
        print(f"  day lock clock skipped ({type(e).__name__}: {e})")
    try:
        PC.annotate(site_data, data, now_ms)                # games left in this matchup, for the player card
    except Exception as e:
        print(f"  games-left skipped ({type(e).__name__}: {e})")
    try:
        site_data["planner"] = PL.build(cfg, data, league, standings, now_ms, site_data)
    except Exception as e:
        print(f"  planner data failed ({type(e).__name__}: {e})")
    try:
        site_data["streams"] = STR.build(cfg, data, league, standings, now_ms, site_data)
        pl = site_data["streams"]["plan"]
        print(f"  move plan: {len(pl['moves'])} moves, +{pl['gain']} pts")
        for mv in pl["moves"]:
            print(f"     {mv['day']}: add {mv['add']['n']} drop {mv['drop']['n']} (+{mv['gain']})")
    except Exception as e:
        print(f"  streams data failed ({type(e).__name__}: {e})")
    try:
        mp = (league.get("status") or {}).get("currentMatchupPeriod")
        site_data["gameplan"] = GP.build(cfg, data, league, standings, now_ms, site_data, prev=WK.previous(mp))
        gp = site_data["gameplan"]
        print(f"  game plan: {len(gp['moves'])} of {gp['moves_left']} moves, +{gp['gain']} pts")
        for mv in gp["moves"]:
            print(f"     {mv['day']} [{mv['tier']}]: add {mv['add']['n']} drop {mv['drop']['n']} (+{mv['gain']}, cost {mv['cost']}, net {mv['net']}){' kept' if mv.get('kept') else ''}")
    except Exception as e:
        print(f"  game plan data failed ({type(e).__name__}: {e})")
    site_data["health"] = health_report(site_data, nhl_counts)
    try:
        site_data["weekplan"] = WK.build(cfg, data, league, standings, now_ms, site_data,
                                         healthy=site_data["health"]["healthy_plan"])
    except Exception as e:                              # the locked plan is an extra: never fail the build over it
        print(f"  weekly plan skipped ({type(e).__name__}: {e})")
    try:
        site_data["record"] = RC.build(mp_now, write=NC.STATE["mode"] != "replay")
        r = site_data["record"]
        if r:
            print(f"  track record: made {r['made']['n']} ({r['made']['pts']:+.1f} pts), "
                  f"skipped {r['skipped']['n']} ({r['skipped']['pts']:+.1f} pts), {r['untracked']} logged before tracking")
    except Exception as e:                                  # the track record is an extra: never fail the build over it
        print(f"  track record skipped ({type(e).__name__}: {e})")
    try:
        site_data["edge"] = EDG.build(cfg, data, league, standings, now_ms, site_data)
    except Exception as e:                                  # the schedule matrix is an extra: never fail the build over it
        print(f"  schedule edge skipped ({type(e).__name__}: {e})")
    try:
        site_data["sb"] = SBD.build(cfg, data, league, standings, now_ms)   # every matchup in the league, Matchups tab
    except Exception as e:                                  # an extra: never fail the build over it
        print(f"  league scoreboard skipped ({type(e).__name__}: {e})")
    gamelog = None
    try:
        gamelog = GL.build(cfg, data, site_data, now_ms)  # recent games, for the Game log tab and Compare
        site_data["gl"] = {"n": len(gamelog["p"]), "v": now_ms}
    except Exception as e:                                  # the game log is an extra: never fail the build over it
        print(f"  game logs skipped ({type(e).__name__}: {e})")
    pool = None
    try:
        pool = POOL.build(cfg, data, site_data, standings, now_ms)   # everyone else ESPN lists, for search in the app
        site_data["pool"] = {"n": pool["n"], "v": now_ms}
        print(f"  player search: {pool['n']} more players")
    except Exception as e:                                  # search falls back to the players already in the page
        print(f"  player search list skipped ({type(e).__name__}: {e})")
    site_data["moves"] = []                      # the Game plan owns the move suggestions
    if not site_data["mine"]:
        sys.exit("Couldn't find your team. Check LEAGUE_ID and TEAM_ID.")
    print(E.summary())
    miss = [p["n"] for p in site_data["mine"] if "toi" not in p and p["grp"] != "G"]
    if miss:
        print("  roster skaters without NHL stats:", ", ".join(miss))
    Path("site").mkdir(exist_ok=True)
    html_text = SB.render_site(site_data)
    missing = [k for k in REQUIRED if k not in html_text]
    if missing:                                            # never publish a page with a section silently missing
        sys.exit("Page is incomplete, not publishing it. Missing: " + ", ".join(missing))
    Path("full.html").write_text(html_text, encoding="utf-8")        # one-file copy for the test tools
    ver = SB.write_site(site_data, "site")                            # the published app: shell + data.json + version.json
    print(f"  app code {ver['code']}, data {ver['data']}")
    if gamelog is not None:
        Path("site/gamelog.json").write_text(json.dumps(gamelog, separators=(",", ":")), encoding="utf-8")
    if pool is not None:
        Path("site/pool.json").write_text(json.dumps(pool, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")
    write_health_file(site_data, now_ms)
    try:
        pwa.write_files("site")
        write_notify_payload(site_data, now_ms)
    except Exception as e:                                  # the app files and alert text are extras: never fail the build
        print(f"  phone app files skipped ({type(e).__name__}: {e})")
    m = site_data["matchup"]
    if m:
        print(f"Matchup vs {m['opp_name']}: {m['me_now']:.1f}-{m['opp_now']:.1f}, win chance {m['p_win']*100:.0f}%")
    for gd in site_data["goalies"]:
        p = gd["p"]
        print(f"  {p['n']}: outlook {p['out']:.2f}, start chance {int((p.get('sp') or 0)*100)}%, "
              f"vs xG {p.get('gsax')}")
        for r in gd["rows"]:
            print(f"     {r['day']} {'vs' if r['home'] else '@'} {r['opp']}: win {r['p']*100:.0f}% exp {r['e']:+.1f} -> {r['verdict']}")
    for mv in site_data["moves"]:
        print(f"  MOVE add {mv['add']['n']} ({mv['add']['out']:.2f}) drop {mv['drop']['n']} ({mv['drop']['out']:.2f})")
    for a in site_data["alerts"]:
        print("  ALERT:", a["t"])
    print(f"Saved the app to site/ ({len(html_text)//1024} KB as one page)")


if __name__ == "__main__":
    main()
