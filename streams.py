#!/usr/bin/env python3
"""
STREAMS + PLAYER VALUES (READ-ONLY). Everything about what a player is worth this week, who may be dropped, and the
Streams / Swap lab cards. (This file replaces the old streams.py, streams2.py, streams3.py and streams4.py, which
patched each other in layers; the behaviour is the same, written once.)

How a player is valued on a given day
  - He only scores on days his team plays, and only while that day is still open (once the first game of the day
    starts, nobody can be added for it).
  - Points per game = his outlook blended with recent form (season + last 15 days), nudged up against weak opponents
    and down against strong ones (at most +/- 15%), plus a small home-ice bump. Watch-listed players count at 85%.
  - Day-to-day players count at 75%, players ruled out at 0.
  - Goalies: expected points for the start x his chance to start (confirmed starters count 100% / 0% today).

Who can be dropped (drop_rule)
  - Never: stars (projected 2.5+), anyone producing for you (1.9+ pts/game this season or 2.2+ over 15 days).
  - Fair drops for a normal gain (1+ point): injured, watch-listed, underperforming for his role, losing his role,
    or a light schedule this week. Other healthy top-role players need a bigger gain (2+), depth players 1.5.
  - Adds must be on a top-six line, top-four pair or first power-play unit (add_ok).

The move plan itself is in core.py.
"""
from pathlib import Path

import analyze as A
import dashboard as D
import enrich as E
import league as L
import planner as PL
import roles as R
import site_builder as SB
import starters as S

INF = 99
REPLACEMENT = {"F": 1.45, "D": 1.5, "G": 1.0}   # what a typical free agent gives you per game
DTD = 0.75              # day-to-day players count at 75%
ROWS_F, ROWS_D = 8, 6   # rows kept per day in the stream lists
PROTECT_GOALIE = 2.0    # goalies this good are never suggested as drops
MIN_GAIN = 1.0          # a normal move must add this many points, net of what you give up
CORE_GAIN = 2.0         # dropping a healthy top-role player that is not clearly underperforming needs this much
DEPTH_GAIN = 1.5        # dropping a depth player (3rd line, 3rd pair, etc.)
STAR_OUT = 2.5          # outlook at or above this is never dropped (unless watch-listed or injured)
FORM_WEIGHT = 0.40      # how much recent form (season + last 15 days) is blended into this week's value
MIN_GP = 6              # games needed before anyone is called an underperformer
UNDER_RATIO = 0.88      # underperforming = scoring under 88% of what his role usually gives
LIGHT_GAP = 2           # light week = this many games fewer than the busiest team
WATCH_HAIRCUT = 0.85    # watch-listed players are valued at 85% (less ice time / PP time expected)
OPTIONS_PER_PLAYER = 3
WEEK_ADDS_F, WEEK_ADDS_D = 6, 4

WATCHLIST_FILE = Path(__file__).with_name("watchlist.txt")
STATE = {"watch": {}, "ref": 0}


# ---------------------------------------------------------------------------
# Schedule, opponents and per-day values
# ---------------------------------------------------------------------------
def _mult(me, opp, home, standings):
    s_me, s_opp = D.team_strength(me, standings), D.team_strength(opp, standings)
    m = 1 + 0.6 * (0.5 - s_opp) + 0.4 * (s_me - 0.5) + (0.02 if home else -0.02)
    tag = "weak" if s_opp <= 0.46 else ("strong" if s_opp >= 0.54 else "avg")
    return D.clamp(m, 0.85, 1.15), tag


def make_game_fn(abbr, games, sp, now_ms):
    tid_of = {ab: tid for tid, ab in abbr.items()}
    locked = {}

    def day_locked(i):
        """No adds once the first game of the day (any NHL game) has started, so the whole day is off the table."""
        if i not in locked:
            starts = [g.get("date") for gl in games.values() for g in gl.get(str(sp + i), []) if g.get("date")]
            locked[i] = bool(starts) and now_ms >= min(starts)
        return locked[i]

    def game(tm, i):
        if day_locked(i):
            return None                                  # the day has started: nobody can be added for it
        tid = tid_of.get(tm)
        gl = games.get(tid, {}).get(str(sp + i), [])
        if not gl:
            return None
        g = gl[0]
        home = g.get("homeProTeamId") == tid
        opp = abbr.get(g.get("awayProTeamId") if home else g.get("homeProTeamId"), "?")
        return opp, home
    game.today = D.today_index(games, sp, now_ms)          # the day today's starting goalies are for
    return game


def _base_values(p, game, ndays, standings, starters, lineup_goalie=False):
    """Expected fantasy points for player p on each of the next ndays days (before the form blend)."""
    v = [0.0] * ndays
    if p["inj"] in A.BAD_INJURY:
        return v
    fac = 1.0 if p["inj"] in ("ACTIVE", None) else DTD
    for i in range(ndays):
        g = game(p["tm"], i)
        if not g:
            continue
        opp, home = g
        if p["grp"] == "G":
            s_me = D.team_strength(p["tm"], standings)
            pw = D.log5(s_me, D.team_strength(opp, standings)) + (D.HOME_ICE if home else -D.HOME_ICE)
            if p.get("svp") and p["gp"] >= 5:
                pw += D.clamp((p["svp"] - 0.905) * 2.0, -0.05, 0.05)
            pw = D.clamp(pw, 0.15, 0.85)
            e = (p["out"] or 0) + _win_pts() * (pw - s_me)
            st = p.get("sp") or 0.5
            # (review B1, 2026-11-25: your own goalies' start chance is no longer floored at 50%; a goalie only
            # scores when he starts, whoever rosters him)
            s = starters.get(p["tm"]) if i == getattr(game, "today", 0) else None
            if s:
                st = 1.0 if E.norm(s["name"]) == E.norm(p["n"]) else 0.0
            v[i] = max(0.0, e * st * fac)
        else:
            m, _ = _mult(p["tm"], opp, home, standings)
            v[i] = (p["out"] or 0) * m * fac
    return v


def values(p, game, ndays, standings, starters, lineup_goalie=False):
    """Per-day expected points, with recent form blended in. Also notes his games left (used by the drop rules)."""
    v = _base_values(_with_eff(p), game, ndays, standings, starters, lineup_goalie=lineup_goalie)
    if p.get("grp") != "G":
        n = sum(1 for x in v if x > 0)
        p["_gl"] = n                                       # games left this week (used by the drop rules)
        if n > STATE["ref"]:
            STATE["ref"] = n                               # the busiest team's games left so far
    return v


def day_value(active):
    """Best lineup score for one day. active = [(group, value)]; this league's slots (9 F, 5 D, 1 UTIL, 2 G here)."""
    S_ = L.SLOTS
    fwd = sorted((v for g, v in active if g == "F"), reverse=True)
    dfn = sorted((v for g, v in active if g == "D"), reverse=True)
    gk = sorted((v for g, v in active if g == "G"), reverse=True)
    rest = sorted(fwd[S_["F"]:] + dfn[S_["D"]:], reverse=True)
    return sum(fwd[:S_["F"]]) + sum(dfn[:S_["D"]]) + sum(rest[:S_["UTIL"]]) + sum(gk[:S_["G"]])


def _active(entries, d, skip=None):
    return [(e["grp"], e["v"][d]) for e in entries if e["join"] <= d < e["leave"] and e is not skip]


def _brief(p):
    return {"id": p["id"], "n": p["n"], "pos": p["pos"], "tm": p["tm"]}


# ---------------------------------------------------------------------------
# Watch list, form, and the drop / add rules
# ---------------------------------------------------------------------------
def _norm(name):
    try:
        return E.norm(name)
    except Exception:
        return " ".join(str(name or "").lower().split())


def load_watchlist():
    """watchlist.txt: one player per line, 'Name | note'. Lines starting with # are ignored."""
    out = {}
    try:
        for line in WATCHLIST_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, _, note = line.partition("|")
            if name.strip():
                out[_norm(name)] = note.strip() or "On your watch list."
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"  watchlist.txt could not be read ({type(e).__name__}: {e})")
    return out


def _watch(p):
    return STATE["watch"].get(_norm(p.get("n")))


def _form(p):
    """Recent scoring per game: average of season and last-15-days when both exist."""
    s, r = p.get("ppg"), p.get("rec")
    if s is not None and r is not None:
        return 0.5 * s + 0.5 * r
    return s if s is not None else r


def eff_out(p):
    """This week's outlook: the normal outlook nudged toward recent form, trimmed for watch-listed players."""
    out = p.get("out") or 0.0
    if p.get("grp") == "G":
        return out
    form = _form(p)
    if form is not None and (p.get("gp") or 0) >= MIN_GP:
        out = (1 - FORM_WEIGHT) * out + FORM_WEIGHT * form
    if _watch(p):
        out *= WATCH_HAIRCUT
    return out


def _with_eff(p):
    if p.get("grp") == "G":
        return p
    q = dict(p)
    q["out"] = eff_out(p)
    return q


def producing(p):
    return (p.get("ppg") or 0) >= R.KEEP_PPG or (p.get("rec") or 0) >= R.KEEP_REC


def underperforming(p):
    """Scoring well under what his role normally gives (or at free-agent level while holding a top role)."""
    if p.get("grp") == "G" or (p.get("gp") or 0) < MIN_GP:
        return False
    form = _form(p)
    if form is None:
        return False
    exp = p.get("rp")
    if exp and form <= UNDER_RATIO * exp:
        return True
    return p.get("cls") == "core" and form <= REPLACEMENT[p["grp"]] + 0.10


def role_risk(p):
    return (p.get("cls") == "watch" or p.get("rl") == "Off lines"
            or (p.get("tr") is not None and p["tr"] <= -2.0))


def light_week(gl, ref):
    return gl <= ref - LIGHT_GAP


def drop_rule(p, gl, ref):
    """(can he be dropped?, net points a move must clear)."""
    if p["inj"] in A.BAD_INJURY:
        return True, MIN_GAIN
    if p["grp"] == "G":
        return (p["slot"] == "BN" and (p["out"] or 0) < PROTECT_GOALIE), MIN_GAIN
    if _watch(p):
        return True, MIN_GAIN
    if (p.get("out") or 0) >= STAR_OUT:
        return False, 0.0
    under = underperforming(p)
    if producing(p) and not under:
        return False, 0.0
    if under or role_risk(p) or light_week(gl, ref):
        return True, MIN_GAIN
    cls = p.get("cls")
    if cls == "streamer":
        return True, MIN_GAIN
    if cls == "core":
        return True, CORE_GAIN
    return True, DEPTH_GAIN


def add_ok(p):
    if p["inj"] in A.BAD_INJURY:
        return False
    if p["grp"] == "G":
        return (p.get("sp") or 0) >= 0.3
    if not R.STATE["teams"]:
        return True                                        # no line data at all (not even a saved copy): don't block everything
    if p.get("rl") in (None, "Off lines", "Not listed"):
        return False
    return R.is_top(p["grp"], p.get("ev"), p.get("ppu") or 0)


# ---------------------------------------------------------------------------
# Reasons (plain English)
# ---------------------------------------------------------------------------
def _role_text(p):
    if p["grp"] == "G":
        return {"G1": "starting goalie", "G2": "backup goalie"}.get(p.get("rl"), "goalie")
    if p.get("rl") == "Off lines":
        return "not on his team's current lines"
    return R.phrase(p.get("ev"), p.get("ppu") or 0)


def _opps(p, t, ndays, days, game, standings):
    parts = []
    for i in range(t, ndays):
        g = game(p["tm"], i)
        if g:
            opp, home = g
            _, tag = _mult(p["tm"], opp, home, standings)
            parts.append(f"{days[i].split()[0]} {'vs' if home else '@'} {opp} ({tag})")
    return ", ".join(parts)


def _fill(entries, x, y, t, ndays):
    S_ = L.SLOTS
    play = fill = 0
    for d in range(t, ndays):
        if x["v"][d] <= 0:
            continue
        play += 1
        cnt = {g: sum(1 for e in entries if e["join"] <= d < e["leave"] and e["grp"] == g and e["v"][d] > 0)
               for g in ("F", "D", "G")}
        if y["v"][d] > 0:
            cnt[y["grp"]] -= 1                              # y is leaving
        util_open = max(0, cnt["F"] - S_["F"]) + max(0, cnt["D"] - S_["D"]) < S_["UTIL"]
        if cnt[x["grp"]] < S_[x["grp"]] or (x["grp"] != "G" and util_open):
            fill += 1
    return play, fill


def _why_add(x, entries, y, t, ndays, days, game, standings):
    p = x["p"]
    games = sum(1 for i in range(t, ndays) if x["v"][i] > 0)
    if p["grp"] == "G":
        out = [f"{p['n']} ({p['tm']}) starts about {int(round((p.get('sp') or 0) * 100))}% of his team's games."]
    else:
        out = [f"{p['n']} is on the {_role_text(p)} for {p['tm']} ({p.get('rl') or 'role unknown'})."]
        if y["p"]["inj"] not in A.BAD_INJURY and y["p"].get("rl"):
            out.append(f"Role change: {y['p']['rl']} out, {p.get('rl') or 'role unknown'} in.")
    out.append(f"{games} game{'s' if games != 1 else ''} left this week: {_opps(p, t, ndays, days, game, standings)}.")
    if p.get("tr") is not None and p.get("toi5") is not None:
        out.append(f"Ice time is {p['toi5']:.1f} min over his last 5 games ({p['tr']:+.1f} vs his season average).")
    play, fill = _fill(entries, x, y, t, ndays)
    if fill:
        out.append(f"Fills an empty {x['grp']} lineup slot on {fill} of the {play} days he plays.")
    else:
        out.append(f"Upgrades a {x['grp']} lineup spot you already fill (no empty slot).")
    return out


def _drop_reasons(p, gl, ref):
    out = []
    note = _watch(p)
    if note:
        out.append(f"On your watch list: {note}")
    if underperforming(p):
        form, exp = _form(p), p.get("rp")
        txt = f"Producing {form:.2f} pts/game recently"
        if exp:
            txt += f" against about {exp:.2f} for a typical {p.get('rl') or 'player in his role'}"
        out.append(txt + ", so the role is not turning into points.")
    if p["inj"] not in A.BAD_INJURY and light_week(gl, ref):
        out.append(f"Light week: {gl} game{'s' if gl != 1 else ''} left while the busiest teams have {ref}.")
    return out


# ---------------------------------------------------------------------------
# Streams tab data: daily streams, roster audit, best weekly adds, swap tester
# ---------------------------------------------------------------------------
def stream_rows(fas, game, ndays, standings, games_left):
    """Best free-agent forwards and defensemen for each day."""
    fas = [_with_eff(p) for p in fas]
    rows = []
    pool = sorted((p for p in fas if p["grp"] != "G" and add_ok(p)), key=lambda p: -(p["out"] or 0))[:80]
    for i in range(ndays):
        day = []
        for p in pool:
            g = game(p["tm"], i)
            if not g:
                continue
            opp, home = g
            m, tag = _mult(p["tm"], opp, home, standings)
            fac = 1.0 if p["inj"] in ("ACTIVE", None) else DTD
            day.append({"i": i, "id": p["id"], "n": p["n"], "pos": p["pos"], "grp": p["grp"], "tm": p["tm"],
                        "o": opp, "h": 1 if home else 0, "tag": tag, "e": round((p["out"] or 0) * m * fac, 2),
                        "gl": games_left(p["tm"], i), "w": 1 if p.get("st") == "WAIVERS" else 0, "rl": p.get("rl")})
        for grp, k in (("F", ROWS_F), ("D", ROWS_D)):
            rows += sorted((r for r in day if r["grp"] == grp), key=lambda r: -r["e"])[:k]
    return rows


def _week_total(p, game, ndays, standings, starters):
    v = values(p, game, ndays, standings, starters)
    return sum(v), sum(1 for x in v if x > 0)


def audit(site_data, game, ndays, days, standings, starters):
    mine = [p for p in site_data["mine"] if p["grp"] != "G" and p["slot"] != "IR" and p["inj"] not in A.BAD_INJURY]
    fas = [p for p in site_data["fas"] if p["grp"] != "G" and add_ok(p)]
    tot = {}
    for p in mine + fas:
        tot[p["id"]] = _week_total(p, game, ndays, standings, starters)
    ref = max([g for _, g in tot.values()] or [0])
    options = {g: sorted((p for p in fas if p["grp"] == g), key=lambda p: -tot[p["id"]][0]) for g in ("F", "D")}

    out = []
    for p in mine:
        e, gl = tot[p["id"]]
        tags, why, sev = [], [], 0
        note = _watch(p)
        under = underperforming(p)
        stars = (p.get("out") or 0) >= STAR_OUT
        if note:
            tags.append({"k": "role", "t": "Watch list"})
            why.append(note)
            sev += 3
        if under and not stars:
            tags.append({"k": "under", "t": "Underperforming"})
            form, exp = _form(p), p.get("rp")
            txt = f"Scoring {form:.2f} pts/game"
            if p.get("ppg") is not None and p.get("rec") is not None:
                txt += f" (season {p['ppg']:.2f}, last 15 days {p['rec']:.2f})"
            if exp:
                txt += f" against about {exp:.2f} for a typical {p.get('rl') or 'player in his role'}"
            why.append(txt + ".")
            sev += 3
        if role_risk(p) and not note:
            tags.append({"k": "role", "t": "Role at risk"})
            if p.get("rl") == "Off lines":
                why.append("Not on his team's current line combinations (scratched, injured or demoted).")
            elif p.get("tr") is not None and p.get("toi5") is not None:
                why.append(f"Ice time {p['toi5']:.1f} min over his last 5 games ({p['tr']:+.1f} vs his season average).")
            sev += 2
        if light_week(gl, ref) and not stars and not (producing(p) and not under):
            tags.append({"k": "light", "t": f"{gl} game{'s' if gl != 1 else ''} left"})
            opps = _opps(p, 0, ndays, days, game, standings)
            why.append(f"Light week: {gl} game{'s' if gl != 1 else ''} left{(' (' + opps + ')') if opps else ''}; the busiest teams have {ref}.")
            sev += 2
        if p.get("cls") == "streamer" and not tags:
            tags.append({"k": "streamer", "t": "Replaceable role"})
            why.append(f"{p.get('rl')}: {_role_text(p)}.")
            sev += 1
        if not tags:
            continue
        if p.get("rl") and not any(p.get("rl") in w for w in why):
            why.insert(0, f"{p.get('rl')}: {_role_text(p)}.")
        repl = []
        for q in options[p["grp"]]:
            if len(repl) >= OPTIONS_PER_PLAYER:
                break
            qe, qg = tot[q["id"]]
            if qe > e + 0.5 and q["tm"] != p["tm"]:
                repl.append({"id": q["id"], "n": q["n"], "rl": q.get("rl"), "tm": q["tm"], "gl": qg, "e": round(qe, 1)})
        out.append({"id": p["id"], "n": p["n"], "pos": p["pos"], "tm": p["tm"], "slot": p["slot"], "rl": p.get("rl"),
                    "tags": tags, "why": why, "repl": repl, "sev": sev, "e": round(e, 1), "gl": gl})
    out.sort(key=lambda a: (-a["sev"], a["e"]))
    return out[:10]


def week_adds(site_data, game, ndays, days, standings, starters):
    fas = [p for p in site_data["fas"] if p["grp"] != "G" and add_ok(p)]
    rows = []
    for g, k in (("F", WEEK_ADDS_F), ("D", WEEK_ADDS_D)):
        scored = []
        for p in fas:
            if p["grp"] != g:
                continue
            e, gl = _week_total(p, game, ndays, standings, starters)
            if gl:
                scored.append((e, gl, p))
        for e, gl, p in sorted(scored, key=lambda s: -s[0])[:k]:
            rows.append({"id": p["id"], "n": p["n"], "pos": p["pos"], "grp": g, "tm": p["tm"], "rl": p.get("rl"),
                         "e": round(e, 1), "gl": gl, "w": 1 if p.get("st") == "WAIVERS" else 0,
                         "opps": _opps(p, 0, ndays, days, game, standings)})
    return rows


def whatif_data(site_data, game, ndays, days, standings, starters):
    """Everything the page needs to try 'add this free agent, drop that player' and re-score your daily lineups."""
    def rec(p, mine):
        v = values(p, game, ndays, standings, starters, lineup_goalie=(mine and p["grp"] == "G" and p["slot"] == "G"))
        d = {"id": p["id"], "n": p["n"], "pos": p["pos"], "tm": p["tm"], "grp": p["grp"], "slot": p["slot"],
             "rl": p.get("rl"), "cls": p.get("cls"), "out": round(eff_out(p), 2), "ppg": p.get("ppg"), "rec": p.get("rec"),
             "rp": p.get("rp"), "tr": p.get("tr"), "gp": p.get("gp"), "st": p.get("st"),
             "gl": sum(1 for x in v if x > 0), "e": round(sum(v), 1), "v": [round(x, 2) for x in v],
             "inj": p.get("inj")}
        d["o"] = _opps(p, 0, ndays, days, game, standings)
        return d
    mine = [rec(p, True) for p in site_data["mine"] if p["slot"] != "IR"]
    fa_sk = sorted((p for p in site_data["fas"] if p["grp"] != "G" and p["inj"] not in A.BAD_INJURY),
                   key=lambda p: -(p.get("out") or 0))[:250]
    fa_g = sorted((p for p in site_data["fas"] if p["grp"] == "G" and p["inj"] not in A.BAD_INJURY),
                  key=lambda p: -(p.get("sp") or 0))[:20]
    return {"days": [x.split()[0] for x in days], "mine": mine, "fas": [rec(p, False) for p in fa_sk + fa_g]}


def build(cfg, data, league, standings, now_ms, site_data):
    sp = data["roster"].get("scoringPeriodId", 1)
    abbr, games = D.schedule_maps(data["schedules"])
    m = site_data.get("matchup")
    ndays = max(1, min(int(m["days_left"]) if m else 7, D.MAX_DAYS))
    game = make_game_fn(abbr, games, sp, now_ms)
    starters = S.STATE["by_team"]
    days = D.day_clock(data["schedules"], sp, ndays, now_ms)["labels"]
    bg = PL.budget(league, cfg["team"])
    used, moves_left = bg["used"], bg["left"]

    def games_left(tm, i):
        return sum(1 for j in range(i, ndays) if game(tm, j))

    # the move plan lives in core.py (Game plan); this empty one keeps the page's older Streams card quiet
    plan = {"base": 0, "total": 0, "gain": 0, "moves": [], "marginal": [], "moves_left": moves_left,
            "used_known": used is not None}
    d = {"days": days, "rows": stream_rows(site_data["fas"], game, ndays, standings, games_left), "plan": plan}
    try:
        cdays = D.day_clock_games(games, sp, ndays, now_ms)["labels"]
        d["audit"] = audit(site_data, game, ndays, cdays, standings, starters)
        d["week"] = week_adds(site_data, game, ndays, cdays, standings, starters)
        d["whatif"] = whatif_data(site_data, game, ndays, cdays, standings, starters)
    except Exception as e:
        print(f"  streams cards failed ({type(e).__name__}: {e})")
    return d


def slim_roles(d, p):
    """Adds role fields to a player's page data (line / PP role, class, ice-time trend, typical points for his role)."""
    for k in ("rl", "cls", "ev"):
        if p.get(k) is not None:
            d[k] = p[k]
    for k in ("ppu", "tr", "toi5"):
        if p.get(k) is not None:
            d[k] = SB.r3(p[k])
    if p.get("role_prior") is not None:
        d["rp"] = SB.r3(p["role_prior"])
    return d


def install():
    STATE["watch"] = load_watchlist()
    print(f"  streams: this-week-first drops on, {len(STATE['watch'])} on the watch list")


def _win_pts():
    """This league's points for a goalie win (league.py; 4 when the settings can't be read)."""
    import league as L
    return L.settings().win_points()
