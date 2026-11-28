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
import pending as PN
import keep as KP
import league as L
import ledger as LG
import netcache as NC
import planner as PL
import playercard as PC
import pool as POOL
import pwa
import record as RC
import roles as R
import scoreboard as SBD
import nextroster as NR
import scout as SCT
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
    ns = S.not_starting(p)
    if ns:
        d["ns"] = ns                                       # another goalie is in net today: the page shows no projection
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
    if not L.STATE["known"]:
        level = "warn" if level == "ok" else level
        items.append("Your league's settings couldn't be read, so the lineup (9 F, 5 D, 1 UTIL, 2 G) is assumed.")
    elif L.settings().approx:
        items.append("Approximated for your league: " + L.settings().approx + ".")
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


def _deadline(clock, i):
    """'7:00 PM' (Eastern): the day's first puck drop, after which nobody can be added for that day."""
    try:
        ms = clock["lock"][i]
        if not ms:
            return None
        return datetime.fromtimestamp(ms / 1000, D.et_zone()).strftime("%I:%M %p").lstrip("0")
    except Exception:
        return None


def notify_texts(site_data, now_ms):
    """(morning alert, pre-game reminder or None). Every move on the plan is one to make, so the alert names them all."""
    clock = site_data.get("clock")
    gp = site_data.get("gameplan") or {}
    moves = gp.get("moves") or []
    first_open = 0
    if clock:
        first_open = next((i for i in range(len(clock["lock"])) if not D.day_locked(clock, i, now_ms)), None)
    label = clock["labels"][first_open] if clock and first_open is not None else datetime.fromtimestamp(now_ms / 1000, D.et_zone()).strftime("%a %b %d")
    is_today = bool(clock) and first_open is not None and \
        clock.get("dates", [None] * (first_open + 1))[first_open] == datetime.fromtimestamp(now_ms / 1000, D.et_zone()).strftime("%Y-%m-%d")
    dl = _deadline(clock, first_open) if clock and first_open is not None else None

    def line(m):
        out = f"move {m['drop']['n']} to IR" if m.get("ir") else f"drop {m['drop']['n']}"
        return f"add {m['add']['n']} ({m['add']['tm']}), {out} (+{m['gain']:.1f} pts)"

    today = [m for m in moves if first_open is not None and m.get("t") == first_open]
    claims = [m for m in moves if m.get("waiver") and first_open is not None and m.get("t") == first_open + 1]
    when = ("today" if is_today else label.split()[0]) + (f" before {dl}" if dl else "")
    parts = []
    if today:
        parts.append(f"Make {'this move' if len(today) == 1 else f'these {len(today)} moves'} {when}: "
                     + "; ".join(line(m) for m in today[:3]) + ".")
    else:
        parts.append("No move to make today.")
        nxt = next((m for m in moves if first_open is None or m.get("t", 0) > first_open), None)
        if nxt:
            parts.append(f"Next: {nxt['day'].split()[0]}, {line(nxt)}.")
    for m in claims[:1]:
        parts.append(f"Put in a waiver claim for {m['add']['n']} today.")
    m = site_data.get("matchup")
    if m:
        parts.append(f"Win chance {m['p_win'] * 100:.0f}%.")
    if gp.get("moves_left") is not None and not gp.get("unlimited"):
        parts.append(f"{gp['moves_left']} move{'s' if gp['moves_left'] != 1 else ''} left this week.")
    h = site_data.get("health") or {}
    if h.get("level") == "bad":
        parts.append("Warning: " + " ".join(h.get("items", [])[:1]))
    morning = {"title": f"Fantasy Hockey \u00b7 {label}", "body": " ".join(parts), "url": "./", "tag": "fh-daily"}
    reminder = None
    if today and is_today:
        reminder = {"title": "Fantasy Hockey \u00b7 moves lock " + (dl or "soon"),
                    "body": f"Still to do{' before ' + dl if dl else ''}: " + "; ".join(line(x) for x in today[:3]) + ".",
                    "url": "./", "tag": "fh-reminder"}
    return morning, reminder


INJURY_WORD = {"OUT": "is out", "INJURY_RESERVE": "is on injured reserve", "SUSPENSION": "is suspended"}


def injury_alerts(site_data, now_ms):
    """{player id: push} for every player on your roster who is OUT / on IR / suspended and not already sitting in an IR
    spot. The server sends a push the first time a player shows up here (a new injury), with the plan's answer: the pickup
    that replaces him, or the plain statement that no pickup beats keeping him."""
    clock = site_data.get("clock")
    moves = (site_data.get("gameplan") or {}).get("moves") or []
    out = {}
    for p in site_data.get("mine") or []:
        if p.get("inj") not in INJURY_WORD or p.get("slot") == "IR" or p.get("irn"):   # irn: in IR from tomorrow
            continue
        mv = next((m for m in moves if (m.get("drop") or {}).get("id") == p["id"]), None) or (moves[0] if moves else None)
        head = f"{p['n']} {INJURY_WORD[p['inj']]}."
        if mv:
            dl = _deadline(clock, mv["t"]) if clock and mv.get("t") is not None else None
            when = mv["day"].split()[0] + (f" before {dl}" if dl else "")
            if (mv.get("drop") or {}).get("id") == p["id"]:     # the plan already replaces him
                act = f"{'Move' if mv.get('ir') else 'Drop'} {p['n']}{' to IR' if mv.get('ir') else ''} and add {mv['add']['n']}"
            else:
                act = f"Next move: add {mv['add']['n']}, drop {mv['drop']['n']}"
            body = f"{head} {act} ({mv['add']['tm']}) {when} (+{mv['gain']:.1f} pts)."
        else:
            body = f"{head} No pickup beats keeping him this week, so no move is needed."
        out[str(p["id"])] = {"title": f"Fantasy Hockey \u00b7 {p['n']} {INJURY_WORD[p['inj']].replace('is ', '')}",
                             "body": body, "url": "./", "tag": f"fh-injury-{p['id']}"}
    return out


SWING_DAYS = 2            # the matchup swing alert only runs in the last two days of the matchup


def extra_alerts(site_data, now_ms):
    """What the server needs for the three 'stay up to date' alerts, as plain data (alerts_state.json):
      lineup    : today's lineup problems (a starter with no game while a bench player has one), only before the day's
                  first puck drop, when you can still fix them. Injured starters are left to the injury alert.
      swing     : the matchup numbers in the last two days, so the server can tell when your win chance moves a lot
      lookahead : next week's plan, written once per matchup for the server to send on the last evening."""
    out = {"lineup": None, "swing": None, "lookahead": None}
    clock = site_data.get("clock")
    today = datetime.fromtimestamp(now_ms / 1000, D.et_zone()).strftime("%Y-%m-%d")
    if clock and clock.get("dates") and clock["dates"][0] == today and not D.day_locked(clock, 0, now_ms):
        items = [{"key": a["t"], "text": a["t"]} for a in site_data.get("alerts") or [] if a.get("k") == "warn"]
        if items:
            out["lineup"] = {"date": today, "items": items, "deadline": _deadline(clock, 0)}
    m = site_data.get("matchup")
    if m and int(m.get("days_left", 99)) <= SWING_DAYS:
        out["swing"] = {"p": round(float(m["p_win"]), 4), "me": round(float(m["me_now"]), 1),
                        "opp": round(float(m["opp_now"]), 1), "opp_name": m.get("opp_name") or "your opponent",
                        "days_left": int(m["days_left"])}
    wp = site_data.get("weekplan") or {}
    pv = wp.get("preview")
    if pv and wp.get("mp") is not None:
        mv = pv.get("moves") or []
        if mv:
            parts = [f"{x['day'].split()[0]}: add {x['add']['n']} ({x['add']['tm']}), drop {x['drop']['n']} "
                     f"(+{x['gain']:.1f})" for x in mv[:3]]
            more = f" and {len(mv) - 3} more" if len(mv) > 3 else ""
            body = (f"Next week starts tomorrow. Your plan has {len(mv)} move{'s' if len(mv) != 1 else ''}"
                    f" (+{pv['gain']:.1f} pts): " + "; ".join(parts) + more + ".")
        else:
            body = "Next week starts tomorrow. No move is worth making yet; check again Monday morning."
        out["lookahead"] = {"mp": wp["mp"], "title": "Fantasy Hockey \u00b7 Next week's plan", "body": body}
    return out


def reconcile_alerts(site_data):
    """Today's lineup alerts are built from the roster as it is now, before the game plan exists. When a move planned for
    today drops the goalie an alert says to swap in (seen 2026-11-27: "drop Adin Hill" next to "Swap in Adin Hill, who
    is listed to start"), rewrite that alert so the app and the push agree with the plan. The plan itself already counts
    the dropped player as gone from the move's day on, so nothing in the plan changes."""
    gp = site_data.get("gameplan") or {}
    today = {m["drop"]["n"]: m for m in gp.get("moves") or [] if m.get("t") == 0 and m.get("drop")}
    if not today:
        return
    out = []
    for a in site_data.get("alerts") or []:
        t = a.get("t") or ""
        for name, m in today.items():
            tail = f"Swap in {name}, who is listed to start."
            if tail not in t:
                continue
            add = m["add"]["n"]
            if m.get("g") == "G" and 0 in (m.get("cda") or []):
                new = f"Today's move drops {name}: add {add} and start him there instead."
            else:
                new = f"Today's move drops {name}, so he can't fill in."
            t = t.replace(tail, new)
        out.append(dict(a, t=t))
    site_data["alerts"] = out


def write_notify_payload(site_data, now_ms):
    """The morning push notification (notify_payload.json) and, when today has moves, the pre-game reminder
    (reminder_payload.json). The server sends the reminder with the pre-game build; the plan only lists moves you
    have not made yet, so a move you already made is never in it."""
    morning, reminder = notify_texts(site_data, now_ms)
    Path("notify_payload.json").write_text(json.dumps(morning), encoding="utf-8")
    print(f"  alert text: {morning['title']} | {morning['body']}")
    rp = Path("reminder_payload.json")
    if reminder:
        rp.write_text(json.dumps(reminder), encoding="utf-8")
        print(f"  reminder text: {reminder['title']} | {reminder['body']}")
    elif rp.exists():
        rp.unlink()
    try:                                                    # who is hurt right now, with the plan's answer for each
        Path("injury_state.json").write_text(json.dumps(injury_alerts(site_data, now_ms)), encoding="utf-8")
    except Exception as e:
        print(f"  injury alerts skipped ({type(e).__name__}: {e})")
    try:
        Path("alerts_state.json").write_text(json.dumps(extra_alerts(site_data, now_ms)), encoding="utf-8")
    except Exception as e:
        print(f"  lineup / swing / lookahead alerts skipped ({type(e).__name__}: {e})")


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
    data["pending"] = PN.fetch(cfg)                      # waiver claims you put in that have not processed yet (None: unreadable)
    base = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{cfg['season']}"
    league = A.espn_get(f"{base}/segments/0/leagues/{cfg['league']}", cfg["cookies"],
                        params=[("view", "mSettings"), ("view", "mTeam"),
                                ("view", "mMatchup"), ("view", "mMatchupScore")])
    try:                                                # this league's own rules: lineup slots, move limits, scoring
        import platforms
        L.install(platforms.get(cfg).settings(league))
    except Exception as e:                              # keep the defaults; the health badge says so
        L.install(L.DEFAULT, known=False, note=f"{type(e).__name__}: {e}")
    print(" ", L.summary())
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
        import odds as ODDS
        ODDS.install(ODDS.load())
    except Exception as e:
        print(f"  betting lines skipped ({type(e).__name__}: {e})")
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
    site_data["rules"] = L.page_data()                      # the league settings the model used
    _ab, _gm = D.schedule_maps(data["schedules"])
    site_data["g28"] = C.team_games(_gm, _ab, data["roster"].get("scoringPeriodId", 1), 28)   # trade values: next 4 weeks
    try:                                                # claims already in with ESPN count as made from the day they process
        _m0 = site_data.get("matchup")
        _n0 = max(1, min(int(_m0["days_left"]) if _m0 else 7, D.MAX_DAYS))
        site_data["pending"] = PN.resolve(data.get("pending"), cfg["team"], site_data, _n0)
        PL.PENDING["n"] = PN.count_this_week(site_data["pending"])
        for _c in site_data["pending"]:
            print(f"  pending claim: add {_c['add_n'] or _c['add']} drop {_c['drop_n'] or _c['drop']}"
                  f"{'' if _c['this_week'] else ' (lands next week)'}")
    except Exception as e:
        site_data["pending"] = []
        PL.PENDING["n"] = 0
        print(f"  pending claims skipped ({type(e).__name__}: {e})")
    PL.budget(league, cfg["team"])                      # this league's own weekly add limit, for every planner below
    try:
        _m = site_data.get("matchup")
        _nd = max(1, min(int(_m["days_left"]) if _m else 7, D.MAX_DAYS))
        site_data["clock"] = D.day_clock(data["schedules"], data["roster"].get("scoringPeriodId", 1), _nd, now_ms)
        lk = [i for i in range(_nd) if D.day_locked(site_data["clock"], i, now_ms)]
        PL.DAYS_LEFT["n"] = _nd - len(lk)                   # open days left, for leagues with a per-day add limit
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
    real_mine, plan_mine = site_data["mine"], None
    try:                                                # today locked: plan from tomorrow's ESPN roster (nextroster.py)
        if NR.locked_today(data, now_ms):
            plan_mine, why = NR.plan_roster(cfg, data, site_data, standings, SB.slim)
            print(f"  tomorrow's roster: {why}")
            if plan_mine is not None:
                PC.annotate(dict(site_data, mine=plan_mine + [p for p in real_mine if p.get("nx")], fas=[], teams=[]),
                            data, now_ms)
                site_data["mine"] = plan_mine
    except Exception as e:
        print(f"  tomorrow's roster skipped ({type(e).__name__}: {e})")
        site_data["mine"] = real_mine
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
            print(f"     {mv['day']} [{mv['conf']}]: add {mv['add']['n']} drop {mv['drop']['n']} (+{mv['gain']}, cost {mv['cost']}, net {mv['net']}){' kept' if mv.get('kept') else ''}")
    except Exception as e:
        print(f"  game plan data failed ({type(e).__name__}: {e})")
    site_data["mine"] = real_mine                       # the page keeps today's slots (live views read them)
    try:
        reconcile_alerts(site_data)
    except Exception as e:                              # never fail the build over alert wording
        print(f"  alert reconcile skipped ({type(e).__name__}: {e})")
    site_data["health"] = health_report(site_data, nhl_counts)
    try:
        site_data["weekplan"] = WK.build(cfg, data, league, standings, now_ms, site_data,
                                         healthy=site_data["health"]["healthy_plan"])
    except Exception as e:                              # the locked plan is an extra: never fail the build over it
        print(f"  weekly plan skipped ({type(e).__name__}: {e})")
    if site_data.get("gameplan"):                       # small moves left off the list: back-end log only, never published
        hid = site_data["gameplan"].pop("small", None) or []
        if hid:
            print(f"  {len(hid)} small move(s) left off the list (logged privately): "
                  + "; ".join(f"{m['day']} add {m['add']['n']} drop {m['drop']['n']} ({m['net']:+.1f})" for m in hid))
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
    try:                                                    # opponent scouting for the matchup sheet (display only)
        _sab, _sgm = D.schedule_maps(data["schedules"])
        _sc = SCT.build(league, site_data, site_data.get("sb"), _sgm, _sab, data["roster"].get("scoringPeriodId", 1),
                        now_ms, cfg["team"], raw_tx=data.get("pending"), days_left=PL.DAYS_LEFT["n"])
        SCT.apply(site_data.get("sb"), _sc)
        if _sc:
            print(f"  scouting: {len(_sc)} teams; " + "; ".join(
                f"{t}: {v['n']} games, {v['mv']['left']} adds left, +{v.get('up', 0)} if they stream" for t, v in _sc.items()
                if t != str(cfg["team"]))[:400])
    except Exception as e:                                  # an extra: never fail the build over it
        print(f"  scouting skipped ({type(e).__name__}: {e})")
    site_data["df"] = dict(S.STATE.get("by_team") or {})   # today's starting goalies (Daily Faceoff), for the game page
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
        st = LG.write_files(RC.STATE["rows"], "history", now_ms)   # back-end lifetime stats (not published)
        print(f"  lifetime stats: {st['suggested']} suggested, {st['scored']} scored, "
              f"made moves {st['made']['pts']:+.1f} pts")
    except Exception as e:                                  # the stats page is an extra: never fail the build over it
        print(f"  lifetime stats skipped ({type(e).__name__}: {e})")
    try:
        import backtest as BT                               # private: where the plan's bars should move (not published)
        bt = BT.write_files(RC.STATE["rows"], "history", now_ms)
        print(f"  backtest: {bt['scored']} of {bt['moves']} moves scored; "
              + "; ".join(f"{v['bar']} {v['call']}" for v in bt["verdicts"]))
    except Exception as e:                                  # an extra: never fail the build over it
        print(f"  backtest skipped ({type(e).__name__}: {e})")
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
