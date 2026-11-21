#!/usr/bin/env python3
"""
CORE MOVE PLAN (READ-ONLY): the one plan the whole site uses.

Every tab, the Today screen and the morning alert show the same moves, and they come from here.
Each move also gets a confidence (Strong / Lean / Optional), a one-line reason, and other drops for the Keep button.

How a move is judged
  gain   = extra points your best daily lineup scores for the rest of this matchup with the move made
  cost   = what you give up after this week, by keeping the new player instead of the one you drop (longterm.py):
             both players' per-game value with streaks taken out, over their teams' real games in the three weeks
             after this matchup, weighted by how likely the dropped player is claimed before you could get him back
  net    = gain - cost. A move is "make this move" when net clears the bar for that drop (drop rules in streams4),
           and "optional" when it adds at least OPTIONAL_MIN.

How the plan is chosen
  1. A greedy plan (best move first, then the next best given the first, and so on).
  2. Local search: re-pick any move, or add one, while that raises the total (lineup points minus costs).
  3. It sticks with the plan from the previous build: a move in the previous plan is only replaced when the new
     choice is better by at least STICKY points, so the plan does not flip-flop between refreshes.
"""
import time

import analyze as A
import dashboard as D
import longterm as LT
import streams as STR

INF = STR.INF
OPTIONAL_MIN = 0.5        # smallest net gain worth an (optional) move
STICKY = 1.0              # points a new move must beat the previous plan's move by before the plan changes
# How sure the plan is about a move (shown as Strong / Lean / Optional; only Strong moves go in the morning alert)
STRONG_NET = 3.0          # net points that make a move Strong on its own
STRONG_SCHED_NET = 2.0    # ...or this much when the edge comes from extra games (a schedule edge is close to certain)
LEAN_NET = 1.5            # below this a move is Optional, whatever its tier
ALTS = 3                  # other drops kept for each move, for the "Keep him" button
POOL_SK, POOL_G = 45, 8
DROPS_PER = 7
MAX_PASSES = 4
TIME_BUDGET = 25.0
SLOTS = {"F": 9, "D": 5, "G": 2, "UTIL": 1}


# ---------------------------------------------------------------------------
# Values
# ---------------------------------------------------------------------------
def per_game(p):
    """Expected points per game going forward (goalies: per team game, so start chance is included)."""
    if p["grp"] == "G":
        return (p.get("out") or 0.0) * (p.get("sp") or 0.5)
    return STR.eff_out(p)


def cost(y, x, fut_games):
    """Points given up after this week by dropping roster player y and keeping free agent x instead (longterm.py)."""
    return LT.cost(y, x, fut_games)


def day_value(F, Dn, G):
    F = sorted(F, reverse=True)
    Dn = sorted(Dn, reverse=True)
    rest = sorted(F[SLOTS["F"]:] + Dn[SLOTS["D"]:], reverse=True)
    return (sum(F[:SLOTS["F"]]) + sum(Dn[:SLOTS["D"]]) + sum(rest[:SLOTS["UTIL"]])
            + sum(sorted(G, reverse=True)[:SLOTS["G"]]))


# ---------------------------------------------------------------------------
# Search (plain lists in, move triples out)
# ---------------------------------------------------------------------------
class Model:
    def __init__(self, base, pool, ndays, nxt_games):
        self.fut = nxt_games
        self.base, self.pool, self.ndays = base, pool, ndays
        self.cost = {}
        for xi, x in enumerate(pool):
            for yi, b in enumerate(base):
                if b["ok"]:
                    self.cost[(xi, yi)] = cost(b["p"], x["p"], nxt_games)

    def lineup_total(self, moves):
        leave, adds = {}, {}
        for xi, t, yi in moves:
            leave[yi] = t
            adds.setdefault(t, []).append(xi)
        total, days = 0.0, []
        for d in range(self.ndays):
            F, Dn, G = [], [], []
            for i, b in enumerate(self.base):
                if leave.get(i, INF) > d:
                    (F if b["g"] == "F" else Dn if b["g"] == "D" else G).append(b["v"][d])
            for t, xs in adds.items():
                if t <= d:
                    for xi in xs:
                        x = self.pool[xi]
                        (F if x["g"] == "F" else Dn if x["g"] == "D" else G).append(x["v"][d])
            v = day_value(F, Dn, G)
            days.append(v)
            total += v
        return total, days

    def score(self, moves):
        return self.lineup_total(moves)[0] - sum(self.cost[(xi, yi)] for xi, _, yi in moves)

    def drop_options(self, xi, t, used_y):
        x = self.pool[xi]
        out = []
        for i, b in enumerate(self.base):
            if not b["ok"] or i in used_y:
                continue
            if x["g"] == "G" and b["g"] not in ("G", "F"):
                continue
            if x["g"] != "G" and b["g"] not in ("F", "D"):
                continue
            out.append((sum(b["v"][t:]) + self.cost[(xi, i)], i))
        out.sort()
        return [i for _, i in out[:DROPS_PER]]

    def cands(self, used_x, used_y):
        for xi, x in enumerate(self.pool):
            if xi in used_x:
                continue
            for t in range(self.ndays):
                if x["v"][t] <= 0 or (x["waiver"] and t == 0):
                    continue
                for yi in self.drop_options(xi, t, used_y):
                    yield (xi, t, yi)

    def greedy(self, k):
        cur, best = [], self.score([])
        for _ in range(k):
            ux, uy = {m[0] for m in cur}, {m[2] for m in cur}
            top, topm = best, None
            for c in self.cands(ux, uy):
                s = self.score(cur + [c])
                if s > top + 0.05:
                    top, topm = s, c
            if topm is None:
                break
            cur.append(topm)
            best = top
        return cur

    def search(self, start, k, keep=(), deadline=None):
        """Hill-climb. Moves in `keep` (the previous plan) get a STICKY head start."""
        keep = set(keep)

        def adj(ms):
            return self.score(ms) + STICKY * sum(1 for m in ms if m in keep)

        cur = list(start)
        best = adj(cur)
        for _ in range(MAX_PASSES):
            improved = False
            for i in range(len(cur)):
                if deadline and time.time() > deadline:
                    return cur
                rest = cur[:i] + cur[i + 1:]
                ux, uy = {m[0] for m in rest}, {m[2] for m in rest}
                top, topm = best, None
                for c in self.cands(ux, uy):
                    s = adj(rest + [c])
                    if s > top + 0.05:
                        top, topm = s, c
                if topm is not None:
                    cur[i], best, improved = topm, top, True
            if len(cur) < k:
                ux, uy = {m[0] for m in cur}, {m[2] for m in cur}
                top, topm = best, None
                for c in self.cands(ux, uy):
                    s = adj(cur + [c])
                    if s > top + 0.05:
                        top, topm = s, c
                if topm is not None:
                    cur.append(topm)
                    best, improved = top, True
            if not improved:
                break
        return cur

    def tier(self, moves, bar):
        """Keep moves that pay off inside the final plan; label each 'make' or 'optional'."""
        moves = list(moves)
        while moves:
            full = self.score(moves)
            worst = None
            for m in moves:
                marg = full - self.score([q for q in moves if q is not m])
                if marg < OPTIONAL_MIN and (worst is None or marg < worst[0]):
                    worst = (marg, m)
            if not worst:
                break
            moves.remove(worst[1])
        full = self.score(moves)
        out = []
        for m in moves:
            marg = full - self.score([q for q in moves if q is not m])
            out.append((m, round(marg, 2), "make" if marg >= bar(self.base[m[2]]) else "optional"))
        return out


# ---------------------------------------------------------------------------
# Glue to the site data
# ---------------------------------------------------------------------------
def team_games(games, abbr, sp0, n):
    """{team: games in the n days starting at scoring period sp0}."""
    out = {}
    for tid, ab in abbr.items():
        out[ab] = sum(1 for i in range(n) if games.get(tid, {}).get(str(sp0 + i)))
    return out


def build_inputs(mine, fas, game, ndays, standings, starters):
    entries = [{"p": p, "v": STR.values(p, game, ndays, standings, starters,
                                        lineup_goalie=(p["grp"] == "G" and p["slot"] == "G")),
                "grp": p["grp"], "join": 0, "leave": INF} for p in mine if p["slot"] != "IR"]
    cand = [{"p": p, "v": STR.values(p, game, ndays, standings, starters), "grp": p["grp"],
             "waiver": p.get("st") == "WAIVERS"} for p in fas if STR.add_ok(p)]
    sk = sorted((x for x in cand if x["grp"] != "G"), key=lambda x: -sum(x["v"]))[:POOL_SK]
    gk = sorted((x for x in cand if x["grp"] == "G"), key=lambda x: -sum(x["v"]))[:POOL_G]
    pool = [x for x in sk + gk if sum(x["v"]) > 0]
    ref = max([STR.STATE["ref"]] + [sum(1 for v in e["v"] if v > 0) for e in entries + pool if e["grp"] != "G"])
    base = []
    for e in entries:
        gl = sum(1 for v in e["v"] if v > 0)
        ok, bar = STR.drop_rule(e["p"], gl, ref)
        base.append({"g": e["grp"], "v": e["v"], "ok": ok, "bar": bar or STR.MIN_GAIN, "p": e["p"], "e": e})
    return entries, base, [{"g": x["grp"], "v": x["v"], "waiver": x["waiver"], "p": x["p"], "x": x} for x in pool]


def plan(mine, fas, game, ndays, days, standings, starters, moves_left, nxt_games, prev=None, reasons=True, only_prev=False,
         keep_ids=(), healthy=True):
    """The plan. prev = [(add_id, day_label, drop_id), ...] from the previous build (kept unless clearly beaten).
    keep_ids: players you chose to keep this week (never suggested as drops). healthy: data was complete enough to call
    a move Strong. nxt_games: {team: games} over the long-term horizon after this matchup (longterm.HORIZON_DAYS)."""
    t0 = time.time()
    entries, base, pool = build_inputs(mine, fas, game, ndays, standings, starters)
    keep_ids = set(keep_ids or ())
    for b in base:
        if b["p"]["id"] in keep_ids:
            b["ok"] = False
    M = Model(base, pool, ndays, nxt_games)
    pi = {x["p"]["id"]: i for i, x in enumerate(pool)}
    bi = {b["p"]["id"]: i for i, b in enumerate(base)}
    keep = []
    for add_id, day, drop_id in (prev or []):
        if add_id in pi and drop_id in bi and day in days and base[bi[drop_id]]["ok"]:
            t = days.index(day)
            x = pool[pi[add_id]]
            if x["v"][t] > 0 and not (x["waiver"] and t == 0):
                keep.append((pi[add_id], t, bi[drop_id]))
    keep = keep[:moves_left]
    if only_prev:                     # data too incomplete to trust new suggestions: keep the last good plan only
        g, starts = keep, [keep]
    else:
        g = M.greedy(moves_left)
        starts = [g] + ([keep] if keep else [])
    best, best_s = None, None
    for st in starts:
        m = st if only_prev else M.search(st, moves_left, keep=keep, deadline=t0 + TIME_BUDGET)
        s = M.score(m) + STICKY * sum(1 for q in m if q in keep)
        if best is None or s > best_s:
            best, best_s = m, s
    tiers = M.tier(best, lambda b: b["bar"])
    base_total, before_days = M.lineup_total([])
    after_total, after_days = M.lineup_total([m for m, _, _ in tiers])

    # moves in day order, each with its own gain, cost and reasons
    order = sorted(tiers, key=lambda r: (r[0][1], -r[1]))
    ents = [dict(e) for e in entries]
    by_p = {e["p"]["id"]: e for e in ents}
    days_now = [STR.day_value(STR._active(ents, d)) for d in range(ndays)]
    out = []
    for (xi, t, yi), marg, tier in order:
        x = pool[xi]["x"]
        y = by_p[base[yi]["p"]["id"]]
        c = M.cost[(xi, yi)]
        gain = 0.0
        for d in range(t, ndays):
            act = STR._active(ents, d, skip=y)
            act.append((x["grp"], x["v"][d]))
            gain += STR.day_value(act) - days_now[d]
        mv = {"t": t, "day": days[t], "add": STR._brief(x["p"]), "drop": STR._brief(y["p"]),
              "gain": round(gain, 2), "cost": c, "net": round(gain - c, 2), "marg": marg, "need": base[yi]["bar"],
              "games": sum(1 for i in range(t, ndays) if x["v"][i] > 0), "waiver": x["waiver"], "tier": tier,
              "kept": (xi, t, yi) in keep}
        mv["ga"] = mv["games"]
        mv["gd"] = sum(1 for i in range(t, ndays) if y["v"][i] > 0) if y["p"]["inj"] not in A.BAD_INJURY else 0
        mv["conf"] = confidence(mv, y["p"], healthy, x["p"])
        mv["why1"] = headline(mv, x["p"], y["p"])
        if reasons:
            mv["why_add"] = STR._why_add(x, ents, y, t, ndays, days, game, standings)
            mv["why_drop"] = why_drop(y, t, ndays, c, nxt_games, x["p"])
        mv["lt"] = LT.assess(y["p"], x["p"], nxt_games, c)
        out.append(mv)
        y["leave"] = t
        ents.append({"p": x["p"], "v": x["v"], "grp": x["grp"], "join": t, "leave": INF})
        days_now = [STR.day_value(STR._active(ents, d)) for d in range(ndays)]
    final = [m for m, _, _ in tiers]
    for mv, (m, _, _) in zip(out, order):
        mv["alts"] = alternatives(M, final, m, days, ndays, healthy)
    return {"base": round(base_total, 1), "total": round(after_total, 1), "gain": round(after_total - base_total, 1),
            "moves": out, "before_days": before_days, "after_days": after_days, "ents": ents}


# ---------------------------------------------------------------------------
# Confidence, the one-line reason, and other drops for the same add
# ---------------------------------------------------------------------------
def day_to_day(p):
    """Listed as hurt but not ruled out (ESPN's DAY_TO_DAY): he may or may not play."""
    return bool(p) and p.get("inj") not in ("ACTIVE", None) and p.get("inj") not in A.BAD_INJURY


def confidence(mv, drop_p, healthy, add_p=None):
    """'strong', 'lean' or 'optional'. Strong = clearly worth a move; the morning alert only names Strong moves."""
    if mv["tier"] != "make":
        return "optional"
    sched = mv["ga"] > mv["gd"] or drop_p["inj"] in A.BAD_INJURY
    net = round(mv["net"], 1)                 # judged on the number the page shows
    if net >= STRONG_NET or (sched and net >= STRONG_SCHED_NET):
        c = "strong"
    elif net >= LEAN_NET:
        c = "lean"
    else:
        c = "optional"
    if c == "strong" and not healthy:
        c = "lean"                        # line or goalie data was missing: never call a move a sure thing
    if c == "strong" and day_to_day(add_p):
        c = "lean"                        # the player you'd add might not play: never a sure thing
    return c


def _last(n):
    return n.split()[-1] if n else n


def headline(mv, xp, yp):
    """One plain sentence with the reason and the payoff."""
    a, d = _last(xp["n"]), _last(yp["n"])
    ga, gd = mv["ga"], mv["gd"]
    if yp["inj"] in A.BAD_INJURY:
        why = f"{d} is {yp['inj'].replace('_', ' ').lower()}; {a} has {ga} game{'s' if ga != 1 else ''} left."
    elif ga > gd:
        why = f"{a} plays {ga} game{'s' if ga != 1 else ''} the rest of this week, {d} plays {gd}."
    elif xp["grp"] == "G":
        why = f"{a} is likely to start more ({int(round((xp.get('sp') or 0) * 100))}% of games)."
    else:
        pa, pd = per_game(xp), per_game(yp)
        why = (f"Both play {ga}; {a} projects {pa:.1f} pts a game to {d}'s {pd:.1f}." if ga == gd else
               f"{a} projects {pa:.1f} pts a game to {d}'s {pd:.1f}.")
    if xp["grp"] != "G":
        role = STR._role_text(xp)
        if role and role != "no line role":
            why += f" {a} is on {xp['tm']}'s {role}."
    if day_to_day(xp):
        why += f" {a} is day-to-day, so check he's playing before you add him."
    pay = f" About {mv['gain']:+.1f} pts this week"
    pay += f" ({mv['net']:+.1f} counting what you give up later)." if mv.get("cost", 0) >= 0.05 else "."
    return why + pay


def alternatives(M, final, m, days, ndays, healthy):
    """Other drops for this move's add and day, best first, for when you keep the player it drops."""
    xi, t, yi = m
    rest = [q for q in final if q is not m]
    used = {q[2] for q in rest}
    without = M.score(rest)
    out = []
    for j, b in enumerate(M.base):
        if j == yi or j in used or not b["ok"] or (xi, j) not in M.cost:
            continue
        xg, bg = M.pool[xi]["g"], b["g"]
        if (xg == "G" and bg not in ("G", "F")) or (xg != "G" and bg not in ("F", "D")):
            continue
        net = M.score(rest + [(xi, t, j)]) - without
        if net < OPTIONAL_MIN:
            continue
        c = M.cost[(xi, j)]
        xp, yp = M.pool[xi]["p"], b["p"]
        mv = {"t": t, "day": days[t], "add": STR._brief(xp), "drop": STR._brief(yp), "gain": round(net + c, 2),
              "cost": c, "net": round(net, 2), "games": sum(1 for i in range(t, ndays) if M.pool[xi]["v"][i] > 0),
              "waiver": M.pool[xi]["waiver"], "tier": "make" if net >= b["bar"] else "optional"}
        mv["ga"] = mv["games"]
        mv["gd"] = sum(1 for i in range(t, ndays) if b["v"][i] > 0) if yp["inj"] not in A.BAD_INJURY else 0
        mv["conf"] = confidence(mv, yp, healthy, xp)
        mv["why1"] = headline(mv, xp, yp)
        mv["lt"] = LT.assess(yp, xp, M.fut, c)
        out.append(mv)
    out.sort(key=lambda r: -r["net"])
    return out[:ALTS]


def why_drop(y, t, ndays, c, nxt_games, xp):
    p = y["p"]
    gl = sum(1 for i in range(t, ndays) if y["v"][i] > 0)
    out = []
    if p["inj"] in A.BAD_INJURY:
        out.append(f"{p['n']} is listed {p['inj'].replace('_', ' ').lower()}, so he is not scoring for you.")
    else:
        where = "on your bench" if p["slot"] == "BN" else f"in your {p['slot']} slot"
        role = STR._role_text(p)
        out.append(f"{p['n']} ({role}), currently {where}.")
        if p.get("ppg") is not None:
            out.append(f"Scoring {p['ppg']:.2f} pts/game this season"
                       + (f" ({p['rec']:.2f} over the last 15 days)" if p.get("rec") is not None else "") + ".")
        out.append("No games left this week from that day on." if gl == 0 else
                   (f"Only {gl} game{'s' if gl != 1 else ''} left this week." if gl <= 2 else f"{gl} games left this week."))
        out += [r for r in STR._drop_reasons(p, gl, STR.STATE["ref"]) if not r.startswith("Light week")][:2]
        if c >= 0.05:
            out.append(f"Long-term cost already counted: about {c:.1f} pts over the next three weeks "
                       f"(see Long term).")
        else:
            out.append("No long-term cost: see Long term.")
    return out


def matchup_projection(my_players, opp_players, game, ndays, standings, starters, me_now, opp_now):
    """Both teams' projected finals and your win chance, from the same daily-lineup model the plan uses."""
    import math

    def team(players, mine):
        ents = [{"p": p, "v": STR.values(p, game, ndays, standings, starters,
                                         lineup_goalie=(mine and p["grp"] == "G" and p["slot"] == "G")),
                 "grp": p["grp"], "join": 0, "leave": INF} for p in players if p["slot"] != "IR"]
        mu = var = 0.0
        for d in range(ndays):
            act = [(e["grp"], e["v"][d]) for e in ents if e["v"][d] > 0]
            mu += STR.day_value(act)
            sk = sorted([v for g, v in act if g == "F"], reverse=True)[:9] + sorted([v for g, v in act if g == "D"], reverse=True)[:5]
            var += (len(sk) + (1 if len(sk) >= 14 else 0)) * D.SKATER_SD ** 2
            var += min(2, sum(1 for g, v in act if g == "G")) * 0.6 * D.GOALIE_SD ** 2
        return mu, var

    mu_me, v_me = team(my_players, True)
    mu_op, v_op = team(opp_players, False)
    sd = math.sqrt(v_me + v_op) or 1.0
    p = D.norm_cdf((me_now + mu_me - opp_now - mu_op) / sd)
    return {"proj_me": me_now + mu_me, "proj_opp": opp_now + mu_op, "p_win": D.clamp(p, 0.01, 0.99), "sd": sd,
            "rest_me": mu_me, "rest_opp": mu_op}


def win_after(m, extra):
    if not m or not m.get("sd"):
        return None
    return round(D.clamp(D.norm_cdf((m["proj_me"] + extra - m["proj_opp"]) / m["sd"]), 0.01, 0.99), 3)
