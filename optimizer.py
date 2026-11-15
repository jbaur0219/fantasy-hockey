#!/usr/bin/env python3
"""
WEEK OPTIMIZER (READ-ONLY): improves the game plan beyond one-move-at-a-time planning.

gameplan.py builds the plan greedily: it picks the best single move, assumes you made it, then picks the next best.
That can miss a better COMBINATION (for example, holding one pickup all week while streaming a different slot, or
swapping the same two players' timing). This module takes the greedy plan as a starting point and then keeps
improving it by local search until nothing better is found:

  - re-pick any one move (a different add, a different day, a different drop), or
  - add a move if you still have moves left,
  while keeping every rule the greedy plan uses (same add pool and role filter, same drop rules, a player added this
  week is never dropped, waiver players cannot be added the same day, adds only on days that are still open).

The score being maximised is the total points of your best daily lineup for the rest of the week, minus the
future value of every player you drop (the same penalty the greedy plan charges). Because it starts from the greedy
plan and only accepts improvements, it can never do worse than the greedy plan on that score.

After the search, every move is tiered by what it adds on its own inside the final plan:
  make   clears the normal bar for that drop  |  spare  clears the 0.5 point bar  |  anything lower is removed.
"""
import time

import analyze as A
import dashboard as D
import gameplan as GP
import streams as STR
import streams2 as S2
import streams4 as S4

INF = STR.INF
SLOTS_F, SLOTS_D, SLOTS_G = 9, 5, 2
MIN_STEP = 0.05          # an improvement must beat this to be accepted
MAX_PASSES = 4
TIME_BUDGET = 25.0       # seconds; the search just stops early (keeping its best plan) if it runs long
POOL_SK, POOL_G = 45, 8  # candidate adds searched (best by weekly value)
DROPS_PER = 6            # candidate drops tried per (add, day)


# ---------------------------------------------------------------------------
# Pure search (lists in, move triples out) so it can be tested on its own
# ---------------------------------------------------------------------------
def day_value(F, Dn, G):
    F = sorted(F, reverse=True)
    Dn = sorted(Dn, reverse=True)
    rest = sorted(F[SLOTS_F:] + Dn[SLOTS_D:], reverse=True)
    return sum(F[:SLOTS_F]) + sum(Dn[:SLOTS_D]) + (rest[0] if rest else 0.0) + sum(sorted(G, reverse=True)[:SLOTS_G])


def score(base, pool, moves, ndays):
    """moves = [(pool_index, day, base_index)]. Total lineup points minus the future-value penalty of the drops."""
    leave = {}
    adds = {}
    for xi, t, yi in moves:
        leave[yi] = t
        adds.setdefault(t, []).append(xi)
    total = 0.0
    for d in range(ndays):
        F, Dn, G = [], [], []
        for i, b in enumerate(base):
            if b["g"] == "I":
                continue
            if leave.get(i, INF) > d:
                (F if b["g"] == "F" else Dn if b["g"] == "D" else G).append(b["v"][d])
        for t, xs in adds.items():
            if t <= d:
                for xi in xs:
                    x = pool[xi]
                    (F if x["g"] == "F" else Dn if x["g"] == "D" else G).append(x["v"][d])
        total += day_value(F, Dn, G)
    return total - sum(base[yi]["pen"] for _, _, yi in moves)


def _drop_options(base, x, t, used_y):
    """The few best candidate drops for adding x on day t."""
    out = []
    for i, b in enumerate(base):
        if not b["ok"] or i in used_y:
            continue
        if x["g"] == "G":
            if b["g"] == "I":
                continue
            if b["g"] != "G" and b["g"] != "F":
                continue
        elif b["g"] not in ("F", "D"):
            continue
        out.append((sum(b["v"][t:]) + b["pen"], i))
    out.sort()
    return [i for _, i in out[:DROPS_PER]]


def _cands(base, pool, ndays, used_x, used_y):
    for xi, x in enumerate(pool):
        if xi in used_x:
            continue
        for t in range(ndays):
            if x["v"][t] <= 0 or (x["waiver"] and t == 0):
                continue
            for yi in _drop_options(base, x, t, used_y):
                yield (xi, t, yi)


def search(base, pool, ndays, k, start, deadline=None):
    """Hill-climb from `start`. Returns (moves, score)."""
    cur = list(start)
    best = score(base, pool, cur, ndays)
    for _ in range(MAX_PASSES):
        improved = False
        # re-pick each move in turn
        for i in range(len(cur)):
            if deadline and time.time() > deadline:
                return cur, best
            rest = cur[:i] + cur[i + 1:]
            ux, uy = {m[0] for m in rest}, {m[2] for m in rest}
            top, topm = best, None
            for c in _cands(base, pool, ndays, ux, uy):
                s = score(base, pool, rest + [c], ndays)
                if s > top + MIN_STEP:
                    top, topm = s, c
            if topm is not None:
                cur[i] = topm
                best = top
                improved = True
        # add a move if one is left
        if len(cur) < k:
            ux, uy = {m[0] for m in cur}, {m[2] for m in cur}
            top, topm = best, None
            for c in _cands(base, pool, ndays, ux, uy):
                s = score(base, pool, cur + [c], ndays)
                if s > top + MIN_STEP:
                    top, topm = s, c
            if topm is not None:
                cur.append(topm)
                best = top
                improved = True
        if not improved:
            break
    return cur, best


def prune(base, pool, moves, ndays, spare_min, need):
    """Tier each move by what it adds inside the final plan; drop the ones below the spare bar."""
    moves = list(moves)
    changed = True
    while changed and moves:
        changed = False
        full = score(base, pool, moves, ndays)
        worst = None
        for m in moves:
            marg = full - score(base, pool, [q for q in moves if q is not m], ndays)
            if marg < spare_min and (worst is None or marg < worst[0]):
                worst = (marg, m)
        if worst:
            moves.remove(worst[1])
            changed = True
    full = score(base, pool, moves, ndays)
    out = []
    for m in moves:
        marg = full - score(base, pool, [q for q in moves if q is not m], ndays)
        out.append((m, marg, "make" if marg >= need(base[m[2]]) else "spare"))
    return out


# ---------------------------------------------------------------------------
# Glue to the real plan
# ---------------------------------------------------------------------------
PREV = {}


def plan_full_opt(mine, fas, game, ndays, days, standings, starters, moves_left):
    greedy = PREV["plan_full"](mine, fas, game, ndays, days, standings, starters, moves_left)
    try:
        return _improve(greedy, mine, fas, game, ndays, days, standings, starters, moves_left)
    except Exception as e:
        print(f"  optimizer skipped ({type(e).__name__}: {e})")
        return greedy


def _improve(greedy, mine, fas, game, ndays, days, standings, starters, moves_left):
    t0 = time.time()
    entries = [{"p": p, "v": STR.values(p, game, ndays, standings, starters, lineup_goalie=(p["grp"] == "G" and p["slot"] == "G")),
                "grp": p["grp"], "join": 0, "leave": INF} for p in mine if p["slot"] != "IR"]
    cand = [{"p": p, "v": STR.values(p, game, ndays, standings, starters), "grp": p["grp"],
             "waiver": p.get("st") == "WAIVERS"} for p in fas if S2.add_ok(p)]
    sk = sorted((x for x in cand if x["grp"] != "G"), key=lambda x: -sum(x["v"]))[:POOL_SK]
    gk = sorted((x for x in cand if x["grp"] == "G"), key=lambda x: -sum(x["v"]))[:POOL_G]
    px = [x for x in sk + gk if sum(x["v"]) > 0]
    gids = {mv["add"]["id"] for mv in greedy["moves"]}
    for x in cand:                                       # make sure every greedy add can be found again
        if x["p"]["id"] in gids and all(q["p"]["id"] != x["p"]["id"] for q in px):
            px.append(x)
    base = [{"g": e["grp"], "v": e["v"], "ok": bool(S2.is_droppable(e["p"])), "pen": S4._pen(e["p"]), "p": e["p"]} for e in entries]
    pool = [{"g": x["grp"], "v": x["v"], "waiver": x["waiver"], "p": x["p"]} for x in px]
    bi = {b["p"]["id"]: i for i, b in enumerate(base)}
    pi = {x["p"]["id"]: i for i, x in enumerate(pool)}
    start = []
    for mv in greedy["moves"]:
        if mv["add"]["id"] in pi and mv["drop"]["id"] in bi:
            start.append((pi[mv["add"]["id"]], mv["t"], bi[mv["drop"]["id"]]))
    s_greedy = score(base, pool, start, ndays)
    moves, s_opt = search(base, pool, ndays, moves_left, start, deadline=t0 + TIME_BUDGET)
    tiers = prune(base, pool, moves, ndays, GP.SPARE_MIN, lambda b: S4.need4({"p": b["p"]}))
    if s_opt - s_greedy < 0.3 or not tiers:
        print(f"  optimizer: greedy plan kept (greedy {s_greedy:.1f}, searched {s_opt:.1f}, {time.time() - t0:.1f}s)")
        greedy["opt"] = {"delta": 0.0, "changed": False}
        return greedy
    # rebuild the plan: moves in day order, each with its own reasons, then the before/after tables
    order = sorted(tiers, key=lambda r: (r[0][1], r[0][0]))
    ents = [dict(e) for e in entries]
    by_p = {e["p"]["id"]: e for e in ents}
    before_rows = GP._day_rows([dict(e) for e in entries], ndays, days, game)
    base_days = [STR.day_value(STR._active(ents, d)) for d in range(ndays)]
    out_moves = []
    for (xi, t, yi), marg, tier in order:
        x = {"p": pool[xi]["p"], "v": pool[xi]["v"], "grp": pool[xi]["g"], "waiver": pool[xi]["waiver"]}
        y = by_p[base[yi]["p"]["id"]]
        pen = base[yi]["pen"]
        gain = 0.0
        for d in range(t, ndays):
            act = STR._active(ents, d, skip=y)
            act.append((x["grp"], x["v"][d]))
            gain += STR.day_value(act) - base_days[d]
        mv = GP.S3._move(ents, x, t, y, gain, pen, gain - pen, ndays, days, game, standings, GP.S3.need(y))
        mv["tier"] = tier
        out_moves.append(mv)
        y["leave"] = t
        ents.append({"p": x["p"], "v": x["v"], "grp": x["grp"], "join": t, "leave": INF})
        base_days = [STR.day_value(STR._active(ents, d)) for d in range(ndays)]
    after_rows = GP._day_rows(ents, ndays, days, game)
    total = sum(base_days)
    start_total = greedy["base"]
    taken = {m["add"]["id"] for m in out_moves}
    targets = {g: [dict(t, taken=(t["id"] in taken)) for t in lst] for g, lst in greedy["targets"].items()}
    print(f"  optimizer: improved the plan by {s_opt - s_greedy:+.1f} pts over the greedy plan "
          f"({len(greedy['moves'])} -> {len(out_moves)} moves, {time.time() - t0:.1f}s)")
    return {"base": greedy["base"], "total": round(total, 1), "gain": round(total - start_total, 1), "moves": out_moves,
            "before": before_rows, "after": after_rows, "targets": targets,
            "opt": {"delta": round(s_opt - s_greedy, 1), "changed": True}}


def install():
    PREV["plan_full"] = GP.plan_full
    GP.plan_full = plan_full_opt
