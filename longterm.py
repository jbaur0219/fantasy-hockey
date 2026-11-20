#!/usr/bin/env python3
"""
LONG-TERM IMPACT of a stream (READ-ONLY): what an add/drop costs you after this matchup week.

A stream is a this-week move, but the player you drop is gone. This module answers "is there a long-term downside?"
the same way for the plan (core.py), the move cards and the Try a swap tester:

  per game  = each player's projected points per game with hot and cold streaks taken out (the luck-adjusted outlook,
              not the recent-form number the this-week values use). Goalies: per team game, start chance included.
  games     = each team's real games over the HORIZON_DAYS after this matchup ends.
  gap       = dropped player's points over that stretch minus the added player's (the added player never counts below
              a typical free agent, since you could always swap him for one).
  get-back  = how likely the dropped player is gone if you want him back, from how widely he is rostered on ESPN
              (and whether that is rising). Even when he is likely still there, getting him back costs a move.
  cost      = max(0, gap) x (FIX_SHARE + (1 - FIX_SHARE) x chance he is gone)

The verdict is None / Small / Real by that cost. Every move's net gain on the site already has it taken off.
"""
import analyze as A

HORIZON_DAYS = 21          # the three weeks after this matchup
FIX_SHARE = 0.35           # share of the gap you lose even if he is still a free agent (a move to fix, and the risk)
SMALL, REAL = 0.5, 2.0     # verdict cut-offs, in points over the horizon
REPLACEMENT = {"F": 1.45, "D": 1.5, "G": 1.0}   # what a typical free agent gives per game (same as streams.py)
LUCK_GOALS = 2.5           # goals above / below expected worth calling out


def true_pg(p):
    """Projected points per game going forward, streaks taken out."""
    out = p.get("out") or 0.0
    if p.get("grp") == "G":
        return out * (p.get("sp") or 0.5)
    return out


def gone_chance(p):
    """Chance the dropped player is claimed before you would want him back (ESPN rostered %, 0-100)."""
    own = p.get("own")
    if own is None:
        return 0.5
    g = (own - 20.0) / 60.0
    if (p.get("own_chg") or 0) >= 2:
        g += 0.1
    return max(0.05, min(0.95, g))


def cost(y, x, fut):
    """Points you give up after this week by dropping roster player y and keeping free agent x."""
    if y.get("inj") in A.BAD_INJURY:
        return 0.0
    gy, gx = fut.get(y["tm"], 0), fut.get(x["tm"], 0)
    floor = REPLACEMENT.get(y["grp"], 1.45) * (0.5 if y["grp"] == "G" else 1.0)
    gap = true_pg(y) * gy - max(true_pg(x), floor) * gx
    return round(max(0.0, gap) * (FIX_SHARE + (1 - FIX_SHARE) * gone_chance(y)), 3)


def verdict(c):
    return "none" if c < SMALL else ("small" if c < REAL else "real")


def _last(n):
    return n.split()[-1] if n else n


def _role(p):
    rl = p.get("rl")
    if not rl or p.get("grp") == "G":
        return None
    parts = [s.strip() for s in rl.split("-")]
    names = {"F1": "top line", "F2": "second line", "F3": "third line", "F4": "fourth line",
             "D1": "top pair", "D2": "second pair", "D3": "third pair", "PP1": "first power play",
             "PP2": "second power play"}
    words = [names.get(s, s) for s in parts if s]
    return " and ".join(words) if words else None


def assess(y, x, fut, c=None):
    """Plain-English long-term check for dropping y (yours) to add x. Returns {v, pts, lines}."""
    if c is None:
        c = cost(y, x, fut)
    d, a = _last(y["n"]), _last(x["n"])
    lines = []
    if y.get("inj") in A.BAD_INJURY:
        lines.append(f"{d} is {y['inj'].replace('_', ' ').lower()}, so he isn't scoring for you now.")
        return {"v": "none", "pts": 0.0, "lines": lines, "gy": 0, "gx": fut.get(x["tm"], 0)}
    py, px = true_pg(y), true_pg(x)
    gy, gx = fut.get(y["tm"], 0), fut.get(x["tm"], 0)
    if abs(py - px) < 0.05:
        lines.append(f"Per game from here on, they're about even ({d} {py:.2f}, {a} {px:.2f}), with hot and cold "
                     f"streaks taken out.")
    elif py > px:
        lines.append(f"{d} is the better player per game from here on ({py:.2f} vs {px:.2f}), with hot and cold "
                     f"streaks taken out.")
    else:
        lines.append(f"{a} is the better player per game from here on ({px:.2f} vs {py:.2f}), with hot and cold "
                     f"streaks taken out.")
    for p, who in ((x, a), (y, d)):
        gxs = p.get("gx")
        if gxs is not None and (p.get("gp") or 0) >= 8:
            if gxs >= LUCK_GOALS:
                lines.append(f"{who} has scored about {gxs:.0f} more goals than his chances usually give, so expect "
                             f"fewer going forward.")
            elif gxs <= -LUCK_GOALS:
                lines.append(f"{who} has scored about {-gxs:.0f} fewer goals than his chances usually give, so he's "
                             f"due to bounce back.")
    for p, who in ((y, d), (x, a)):
        r = _role(p)
        tr = p.get("tr")
        if r:
            s = f"{who}: {r}"
            if tr is not None and abs(tr) >= 1.0:
                s += f", ice time {'up' if tr > 0 else 'down'} {abs(tr):.1f} min lately"
            lines.append(s + ".")
    days = HORIZON_DAYS // 7
    if y["tm"] == x["tm"]:
        lines.append(f"Next {days} weeks: both play {gy} games ({y['tm']}).")
    else:
        lines.append(f"Next {days} weeks: {y['tm']} plays {gy} games, {x['tm']} plays {gx}.")
    own = y.get("own")
    if own is not None:
        g = gone_chance(y)
        if g >= 0.6:
            lines.append(f"{d} is rostered in {own:.0f}% of ESPN leagues, so someone will likely claim him. "
                         f"Don't count on getting him back.")
        elif g >= 0.3:
            lines.append(f"{d} is rostered in {own:.0f}% of ESPN leagues, so he may get claimed before you want him back.")
        else:
            lines.append(f"{d} is rostered in only {own:.0f}% of ESPN leagues, so he'll likely still be there if you "
                         f"want him back (it costs a move).")
    v = verdict(c)
    if v == "none":
        lines.append("Bottom line: no real long-term downside.")
    elif v == "small":
        lines.append(f"Bottom line: a small long-term cost, about {c:.1f} pts over the next {days} weeks. "
                     f"It's already taken off this move's gain.")
    else:
        lines.append(f"Bottom line: a real long-term cost, about {c:.1f} pts over the next {days} weeks. "
                     f"It's already taken off this move's gain, so only make it if this week matters a lot.")
    return {"v": v, "pts": round(c, 1), "lines": lines, "gy": gy, "gx": gx}
