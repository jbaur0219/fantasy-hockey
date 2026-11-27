#!/usr/bin/env python3
"""
OPPONENT SCOUTING (READ-ONLY, back end): for every team in this week's matchups, what the rest of the week looks like
from their roster (roadmap #2, 2026-11-27). The user did not want a Scout tab ("other areas of the app already show
some of this"), so nothing here is drawn on its own: the games-that-count total feeds the scoreboard's "games left",
and opponent_upside() feeds the Game plan's read of the matchup (gameplan.py -> core.risk).

For each team, from today to the last day of the matchup:
  d    one row per day: [day index, skater games that fit the lineup, open skater spots, goalie games that fit,
       open goalie spots, 1 if the day is already locked for adds (first puck has dropped)]
       "Fit the lineup" = the best lineup the team could set from its own roster that day (9 F / 5 D / 1 UTIL / 2 G
       here, the league's own slots): a 10th forward with a game is a bench game and is not counted.
  n    games that count the rest of the week (sum of the day rows). The scoreboard's "games left" uses this number, so
       the Matchups tiles, the Week tab and the Scout tab always agree.
  pos  {"F": [spots with a game, spots], "D": [...], "G": [goalie games, goalie spots]} over the days left
  mv   {"left", "used", "known", "today"}: adds left this matchup by the league's own rule, adds used (ESPN's
       transactionCounter), and whether an add already went through today (a per-day league can't add again today).
       Your own team uses the Game plan's own number so the two screens agree.
  st   the best free-agent pickups for the team's open spots, greedy, one add per day where the league allows one:
       [{"i": day, "id", "n", "pos", "tm", "g": games that fill an open spot, "v": points those games are worth,
         "mine": 1 if the same player is an add in your Game plan}]. Not made for your own team (the Game plan is
       the only list of your moves). Only pickups worth 1.0+ points are listed, like the plan's own bar.
  up   what those pickups add together (about), so "if they stream" has one number.

Pending waiver claims of other teams are private in ESPN, so they are never read or shown here.
"""
import analyze as A
import dashboard as D
import league as L

SHOW = 1.0          # a pickup has to be worth this many points to be listed (core.SHOW_NET)
MAX_FA = 80         # free agents looked at, by projection (the pool is sorted; deeper players never win a spot)
CLAIM_TYPES = {"FREEAGENT", "WAIVER"}


def _tid_of(abbr):
    return {ab: tid for tid, ab in abbr.items()}


def _fill(nf, nd, ng, slots):
    """Best lineup from players with a game: (skaters counted, open skater spots, goalies counted, open goalie spots)."""
    F, Dn, U, G = slots.get("F", 9), slots.get("D", 5), slots.get("UTIL", 1), slots.get("G", 2)
    uf, ud = min(nf, F), min(nd, Dn)
    uu = min(U, (nf - uf) + (nd - ud))
    g = min(ng, G)
    return uf + ud + uu, (F - uf) + (Dn - ud) + (U - uu), g, G - g, (uf, ud, uu, F - uf, Dn - ud, U - uu)


def _plays(games, tid_of, tm, sp, now_ms):
    tid = tid_of.get(tm)
    return bool(tid is not None and D.games_on(games, tid, sp, now_ms))


def _locked(games, sp, now_ms):
    starts = [g.get("date") for gl in games.values() for g in gl.get(str(sp), []) if g.get("date")]
    return bool(starts) and now_ms >= min(starts)


def _can_play(p):
    return p.get("slot") != "IR" and p.get("inj") not in A.BAD_INJURY


def added_today(raw, team_id, sp):
    """True when ESPN shows an add for this team that went through today (FREEAGENT or a processed WAIVER).
    Uses the league transactions pending.fetch already reads (today and the two days before)."""
    for tx in ((raw or {}).get("transactions") or []):
        if not isinstance(tx, dict) or tx.get("teamId") != team_id or tx.get("scoringPeriodId") != sp:
            continue
        if str(tx.get("status") or "").upper() != "EXECUTED" or str(tx.get("type") or "").upper() not in CLAIM_TYPES:
            continue
        if any(isinstance(it, dict) and str(it.get("type") or "").upper() == "ADD" for it in tx.get("items") or []):
            return True
    return False


def _value(p):
    """Points a pickup's game is worth: the per-game projection; a goalie's times his chance to start."""
    v = float(p.get("out") or 0)
    if p.get("grp") == "G":
        v *= float(p.get("sp") or 0.5)
    return v


def _pickup_ok(p):
    if p.get("inj") in A.BAD_INJURY:
        return False
    try:
        import streams as STR
        return STR.add_ok(p)
    except Exception:                         # roles not loaded (tests, odd builds): keep anyone healthy
        return p.get("grp") != "G" or (p.get("sp") or 0) >= 0.3


def streams_for(open_by_day, plays, fas, days, locked, moves_left, per_day, taken=(), add_days=None):
    """Greedy best pickups for a team. open_by_day: {day: [open F, open D, open UTIL, open G]}. plays(p, day) -> bool.
    Each pick takes the free agent and day that fill the most open-spot points from that day to the end of the week,
    then those spots are filled. At most `per_day` adds a day (None: any number), only on days not locked.
    add_days: the days an add can be made on (default `days`); an off day with no NHL games still takes an add."""
    opn = {i: list(v) for i, v in open_by_day.items()}
    used_days, picks, gone = {}, [], set(taken)

    def gain(p, d, commit=False):
        tot, n = 0.0, 0
        for e in days:
            if e < d or not plays(p, e):
                continue
            o = opn[e]
            k = 3 if p["grp"] == "G" else (0 if p["grp"] == "F" else 1)
            if o[k] > 0:
                if commit:
                    o[k] -= 1
            elif k < 3 and o[2] > 0:
                if commit:
                    o[2] -= 1
            else:
                continue
            tot += _value(p)
            n += 1
        return tot, n

    for _ in range(max(0, int(moves_left or 0))):
        best = None
        for d in (add_days if add_days is not None else days):
            if locked.get(d) or (per_day is not None and used_days.get(d, 0) >= per_day):
                continue
            for p in fas:
                if p["id"] in gone:
                    continue
                v, n = gain(p, d)
                if n and (best is None or v > best[0] + 1e-9):
                    best = (v, n, p, d)
        if best is None or best[0] < SHOW:
            break
        v, n, p, d = best
        gain(p, d, commit=True)
        gone.add(p["id"])
        used_days[d] = used_days.get(d, 0) + 1
        picks.append({"i": d, "id": p["id"], "n": p.get("n"), "pos": p.get("pos"), "tm": p.get("tm"),
                      "g": n, "v": round(v, 1)})
    return picks


def build(league, site_data, sb, games, abbr, sp, now_ms, me, raw_tx=None, days_left=None):
    """{team id (str): scouting} for every team in this week's matchups (see the module doc). None when the week is over."""
    if not sb or sb.get("done"):
        return None
    slots = dict(L.SLOTS)
    today, length = int(sb.get("today") or 0), len(sb.get("dates") or [])
    start = sp - today
    # days with an NHL game still to start (today drops out once its last game has begun)
    days = [i for i in range(today, length)
            if any(g.get("date", 0) > now_ms for gl in games.values() for g in gl.get(str(start + i), []))]
    if not days:
        return None
    tid_of = _tid_of(abbr)
    add_days = [i for i in range(today, length) if not _locked(games, start + i, now_ms)]
    locked = {i: _locked(games, start + i, now_ms) for i in days}
    open_days = len(add_days)
    if days_left is None:
        days_left = open_days
    plays_cache = {}

    def plays(p, i):
        k = (p.get("tm"), i)
        if k not in plays_cache:
            plays_cache[k] = _plays(games, tid_of, p.get("tm"), start + i, now_ms)
        return plays_cache[k]

    fas = sorted((p for p in site_data.get("fas") or [] if _pickup_ok(p)), key=lambda p: -_value(p))[:MAX_FA]
    plan = (site_data.get("gameplan") or {})
    my_adds = {(m.get("add") or {}).get("id") for m in plan.get("moves") or []}
    teams = {t["id"]: t for t in site_data.get("teams") or []}
    in_week = {g[k] for g in sb.get("games") or [] for k in ("a", "b")}
    out = {}
    for tid in in_week:
        t = teams.get(tid)
        if not t:
            continue
        ps = [p for p in t.get("players") or [] if _can_play(p)]
        rows, opn, have = [], {}, {"F": 0, "D": 0, "G": 0}
        for i in days:
            on = [p for p in ps if plays(p, i)]
            nf = sum(1 for p in on if p.get("grp") == "F")
            nd = sum(1 for p in on if p.get("grp") == "D")
            ng = sum(1 for p in on if p.get("grp") == "G")
            sk, osk, g, og, parts = _fill(nf, nd, ng, slots)
            uf, ud, uu, of, od, ou = parts
            rows.append([i, sk, osk, g, og, 1 if locked[i] else 0])
            opn[i] = [of, od, ou, og]
            have["F"] += uf
            have["D"] += ud
            have["G"] += g
        n = len(days)
        # the UTIL spot counts in the day totals; the per-group spots leave it out so they read simply ("41 of 45")
        pos = {"F": [have["F"], slots.get("F", 9) * n], "D": [have["D"], slots.get("D", 5) * n],
               "G": [have["G"], slots.get("G", 2) * n]}
        bud = D.move_budget(league, tid, days_left=days_left)
        today_add = added_today(raw_tx, tid, sp) if raw_tx else False
        left = bud["left"]
        if tid == me and plan.get("moves_left") is not None:
            left = plan["moves_left"]                               # the Game plan's own number: the two screens agree
        elif today_add and bud.get("per_day") and today in add_days:
            left = max(0, left - bud["per_day"])                    # today's add is spent
        mv = {"left": None if bud.get("unlimited") else left, "used": bud.get("used"), "known": bool(bud.get("known")),
              "today": bool(today_add)}
        sc = {"d": rows, "n": sum(r[1] + r[3] for r in rows), "pos": pos, "mv": mv}
        if tid != me:
            cap = left if left is not None and not bud.get("unlimited") else len(days)
            st = streams_for(opn, plays, fas, days, locked, cap, bud.get("per_day"), add_days=add_days)
            for s in st:
                if s["id"] in my_adds:
                    s["mine"] = 1
            sc["st"] = st
            sc["up"] = round(sum(s["v"] for s in st), 1)
        out[str(tid)] = sc
    return out


def apply(sb, sc):
    """The scoreboard's games left = games that count (same number on the Matchups tiles, Week tab and Scout tab)."""
    if not sb or not sc:
        return sb
    for g in sb.get("games") or []:
        a, b = sc.get(str(g["a"])), sc.get(str(g["b"]))
        if a:
            g["al"] = a["n"]
        if b:
            g["bl"] = b["n"]
    return sb


def opponent_upside(opp_players, fas, game, ndays, moves_left, per_day=None):
    """Points your opponent could still add by streaming the rest of this week, for the Game plan's win-chance read.
    game(tm, i) is the plan's own game function (None when team tm has no game on day i, or the day is locked for adds).
    Same greedy as build(): the best free agents for their open lineup spots, one add a day. Returns (points, picks)."""
    slots = dict(L.SLOTS)
    days = list(range(ndays))
    ps = [p for p in opp_players or [] if _can_play(p)]
    opn = {}
    for i in days:
        on = [p for p in ps if game(p.get("tm"), i)]
        nf = sum(1 for p in on if p.get("grp") == "F")
        nd = sum(1 for p in on if p.get("grp") == "D")
        ng = sum(1 for p in on if p.get("grp") == "G")
        of, od, ou = (lambda x: (x[3], x[4], x[5]))(_fill(nf, nd, ng, slots)[4])
        opn[i] = [of, od, ou, _fill(nf, nd, ng, slots)[3]]
    pool = sorted((p for p in fas or [] if _pickup_ok(p)), key=lambda p: -_value(p))[:MAX_FA]
    plays = lambda p, i: bool(game(p.get("tm"), i))
    # a day where game() finds no game for anyone is locked for adds (or an off day): no add is planned on it
    teams = {p.get("tm") for p in pool + ps}
    locked = {i: not any(game(t, i) for t in teams) for i in days}
    picks = streams_for(opn, plays, pool, days, locked, moves_left if moves_left is not None else ndays, per_day)
    return round(sum(s["v"] for s in picks), 1), picks
