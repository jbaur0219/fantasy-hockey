#!/usr/bin/env python3
"""
BACKTEST (READ-ONLY, BACK END ONLY): score every logged suggestion against what actually happened, and say where the
plan's bars should move.

Inputs
  history/moves.jsonl   every move the plan ever logged: made ("done"), skipped ("missed") and the small moves it left
                        off your list ("hidden"). Since 2026-11-25 each line also carries how the plan saw the move
                        (day index, days in the matchup, the bar it had to clear, games that count, long-term cost...).
  actual results        record.py scores each move (added player's points minus dropped player's points from the move's
                        day to the end of that matchup week). In a build they come from record.STATE["rows"]; offline
                        (tools/backtest.py) from history/results.json or, failing that, the actual_pts column of
                        history/moves.csv.

What it reports (history/backtest.json and history/backtest.md; never published, never in the app)
  calibration  expected vs actual, overall and by kind of move (skater / goalie, early / late week, shown / hidden).
               "expected" here is the move's THIS-WEEK lineup gain (before long-term cost), because the actual score is
               this week's points only; net (after cost) is reported next to it.
  bands        moves grouped by their expected net (0.5-1.0, 1.0-1.5, ...): how many, average actual, how often ahead,
               and a 90% bootstrap range for the average.
  bars         for each bar the plan uses (SHOW_NET, LATE_NET, the goalie bar) a verdict: hold, lower, raise, or
               "not enough data yet" with the way the data leans. A bar only moves when the moves right next to it
               (MIN_N or more of them, scored) say so clearly: the 90% range of their average actual is entirely above
               zero (moves under the bar would have helped: lower it) or entirely below (moves just over it lose points:
               raise it). Hockey is noisy; one week never moves a bar.

Known limits, stated in the report too
  - The actual score compares the two players, not your lineup slots: a player who would have sat on your bench still
    counts. Moves whose reason was "his games would be benched" are scored too generously or too harshly. Moves logged
    since 2026-11-25 carry the counted games (ca/cd), so this can be corrected later from game logs.
  - Opportunity cost: a move under the bar might have used a move the weekly limit needed later. With no reserve of
    moves (product rule) this mostly matters in the last days, which have their own bar.
"""
import csv
import json
import math
import random
from datetime import datetime
from pathlib import Path

MIN_N = 15                # scored moves needed next to a bar before the report recommends moving it
BAND = 0.5                # width of the expected-net bands
STEP = 0.25               # how far a bar moves when the data says so
BOOT = 2000
LATE_DAYS = 3             # mirrors core.LATE_DAYS (imported when available, so the two never disagree)
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _bars():
    """The bars the plan uses today (from core.py when it can be imported, else the documented values)."""
    try:
        import core as C
        return {"show": C.SHOW_NET, "late": C.LATE_NET, "late_days": C.LATE_DAYS, "slack": C.HOLD_SLACK,
                "goalie": getattr(C, "GOALIE_NET", None) or C.SHOW_NET}
    except Exception:
        return {"show": 1.0, "late": 0.5, "late_days": LATE_DAYS, "slack": 0.5, "goalie": 1.0}


def _key(e):
    return f"{e.get('mp')}|{(e.get('add') or {}).get('id')}|{(e.get('drop') or {}).get('id')}"


def _name_key(mp, day, add, drop):
    return f"{mp}|{day}|{add}|{drop}"


def read_log(path):
    out = []
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except FileNotFoundError:
        pass
    return out


def actuals_offline(hist):
    """{key: actual} from results.json (final weeks) and moves.csv (the last build's scores, by names)."""
    hist = Path(hist)
    by_key, by_name = {}, {}
    try:
        for k, v in json.loads((hist / "results.json").read_text(encoding="utf-8")).items():
            if isinstance(v, dict) and v.get("actual") is not None:
                by_key[k] = float(v["actual"])
    except Exception:
        pass
    try:
        with (hist / "moves.csv").open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("actual_pts") not in (None, ""):
                    by_name[_name_key(r["matchup_week"], r["day"], r["add"], r["drop"])] = float(r["actual_pts"])
    except Exception:
        pass
    return by_key, by_name


def _late(e, bars):
    """In the last LATE_DAYS days of the matchup when the move was made. Logged since 2026-11-25; older moves are read
    from the day name (matchups run Monday to Sunday)."""
    if e.get("late") is not None:
        return bool(e["late"])
    if e.get("t") is not None and e.get("nd") is not None:
        return e["nd"] - e["t"] <= bars["late_days"]
    d = str(e.get("day") or "")[:3]
    return d in DAYS and 7 - DAYS.index(d) <= bars["late_days"]


def _goalie(e):
    if e.get("g"):
        return e["g"] == "G"
    return (e.get("add") or {}).get("pos") == "G" or (e.get("drop") or {}).get("pos") == "G"


def rows(log, scored=None, offline=None):
    """One row per distinct move (same de-duplication as record.py: matchup + add + drop), with its actual score."""
    scored = scored or {}
    by_key, by_name = offline or ({}, {})
    bars = _bars()
    out, seen, pairs = [], set(), set()
    for e in log:
        if not e.get("add") or not e.get("drop"):
            continue
        k = _key(e)
        kd = f"{k}|{e.get('day')}"          # the same pair suggested again on another day is its own move
        if kd in seen:
            continue
        seen.add(kd)
        act = None
        if k not in pairs:                  # record.py scores a pair once per week: that score is its first log's
            act = scored.get(k)
            if act is None:
                act = by_key.get(k)
        if act is None:
            act = by_name.get(_name_key(e.get("mp"), e.get("day"), e["add"].get("n"), e["drop"].get("n")))
        pairs.add(k)
        net = e.get("net") if e.get("net") is not None else e.get("expected_gain")
        gain = e.get("expected_gain") if e.get("expected_gain") is not None else net
        out.append({"key": kd, "mp": e.get("mp"), "day": e.get("day"), "result": e.get("result"),
                    "add": e["add"].get("n"), "drop": e["drop"].get("n"),
                    "net": None if net is None else float(net), "gain": None if gain is None else float(gain),
                    "actual": act, "goalie": _goalie(e), "late": _late(e, bars), "kept": e.get("kept"),
                    "ir": bool(e.get("ir")), "need": e.get("need"), "conf": e.get("conf"),
                    "counted": None if e.get("ca") is None else [e.get("ca"), e.get("cd")]})
    return out


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def _boot(xs, seed=0):
    """90% bootstrap range for the mean (None with fewer than 3 values)."""
    if len(xs) < 3:
        return None
    rnd = random.Random(seed)
    n = len(xs)
    means = sorted(sum(rnd.choice(xs) for _ in range(n)) / n for _ in range(BOOT))
    return [round(means[int(0.05 * BOOT)], 2), round(means[int(0.95 * BOOT) - 1], 2)]


def group(rs):
    rs = [r for r in rs if r["actual"] is not None]
    n = len(rs)
    if not n:
        return {"n": 0}
    act = [r["actual"] for r in rs]
    gain = sum(r["gain"] or 0 for r in rs)
    out = {"n": n, "actual": round(sum(act), 1), "expected": round(gain, 1),
           "net": round(sum(r["net"] or 0 for r in rs), 1), "avg": round(sum(act) / n, 2),
           "ahead": sum(1 for a in act if a > 0), "range90": _boot(act),
           "mean_err": round(sum(r["actual"] - (r["gain"] or 0) for r in rs) / n, 2),
           "abs_err": round(sum(abs(r["actual"] - (r["gain"] or 0)) for r in rs) / n, 2)}
    out["ratio"] = round(sum(act) / gain, 2) if gain > 0 else None
    return out


def bands(rs):
    out = []
    xs = [r for r in rs if r["net"] is not None]
    if not xs:
        return out
    lo = math.floor(min(r["net"] for r in xs) / BAND) * BAND
    hi = max(r["net"] for r in xs)
    while lo <= hi:
        b = [r for r in xs if lo <= r["net"] < lo + BAND]
        if b:
            out.append({"from": round(lo, 2), "to": round(lo + BAND, 2), **group(b),
                        "logged": len(b)})
        lo += BAND
    return out


def verdict(name, bar, below, above):
    """Should `bar` move? below / above: scored moves just under / just over it."""
    gb, ga = group(below), group(above)
    v = {"bar": name, "now": bar, "below": gb, "above": ga, "move": 0.0}
    rb, ra = gb.get("range90"), ga.get("range90")
    if gb["n"] >= MIN_N and rb and rb[0] > 0:
        v.update(call="lower", move=-STEP, to=round(bar - STEP, 2),
                 why=f"{gb['n']} moves just under the {bar:g} bar averaged {gb['avg']:+.2f} pts (90% range "
                     f"{rb[0]:+.2f} to {rb[1]:+.2f}): they would have helped, so lower it to {bar - STEP:g}.")
    elif ga["n"] >= MIN_N and ra and ra[1] < 0:
        v.update(call="raise", move=STEP, to=round(bar + STEP, 2),
                 why=f"{ga['n']} moves just over the {bar:g} bar averaged {ga['avg']:+.2f} pts (90% range "
                     f"{ra[0]:+.2f} to {ra[1]:+.2f}): they lost points, so raise it to {bar + STEP:g}.")
    else:
        need = max(0, MIN_N - gb["n"]) + max(0, MIN_N - ga["n"])
        lean = []
        if gb["n"]:
            lean.append(f"{gb['n']} under it averaged {gb['avg']:+.2f}")
        if ga["n"]:
            lean.append(f"{ga['n']} just over it averaged {ga['avg']:+.2f}")
        enough = gb["n"] >= MIN_N or ga["n"] >= MIN_N
        v.update(call="hold" if enough else "wait", to=bar,
                 why=(("Hold: the data on both sides is consistent with this bar. " if enough else
                       f"Not enough scored moves yet (about {need} more needed next to this bar). ")
                      + ("So far: " + "; ".join(lean) + "." if lean else "Nothing scored next to it yet.")))
    return v


def analyze(rs, now_ms=None):
    bars = _bars()
    scored = [r for r in rs if r["actual"] is not None]
    shown = [r for r in rs if r["result"] in ("done", "missed")]
    hidden = [r for r in rs if r["result"] == "hidden"]
    sk = [r for r in rs if not r["goalie"]]
    early_sk = [r for r in sk if not r["late"] and r["net"] is not None]
    late_sk = [r for r in sk if r["late"] and r["net"] is not None]
    gk = [r for r in rs if r["goalie"] and r["net"] is not None]

    def near(xs, bar, side):
        if side < 0:
            return [r for r in xs if bar - BAND <= r["net"] < bar]
        return [r for r in xs if bar <= r["net"] < bar + BAND]

    verdicts = [
        verdict("SHOW_NET (skaters, early week)", bars["show"], near(early_sk, bars["show"], -1), near(early_sk, bars["show"], 1)),
        verdict("LATE_NET (skaters, last %d days)" % bars["late_days"], bars["late"],
                near(late_sk, bars["late"], -1), near(late_sk, bars["late"], 1)),
        verdict("Goalie moves", bars["goalie"], near(gk, bars["goalie"], -1), [r for r in gk if r["net"] >= bars["goalie"]]),
    ]
    gs = group([r for r in shown if r["goalie"]])
    if gs["n"] >= 3 and gs["avg"] < 0 and verdicts[2]["call"] in ("wait", "hold"):
        verdicts[2]["why"] += (f" Watch: the {gs['n']} goalie moves shown so far lost {gs['actual']:+.1f} pts in total; "
                               "the rules say goalie moves get a higher bar if they keep missing.")
    cal = group(scored)
    notes = []
    if cal["n"] >= MIN_N and cal.get("range90") and cal.get("ratio") is not None and cal["ratio"] < 0.7:
        notes.append(f"The plan's gains came in at {cal['ratio']:.0%} of what it expected over {cal['n']} moves. That is a "
                     "calibration problem (projections too high), not a bar problem: shrink the projections first.")
    pend = len(rs) - len(scored)
    return {
        "updated": now_ms, "moves": len(rs), "scored": len(scored), "pending": pend,
        "min_n": MIN_N, "bars_now": bars,
        "calibration": {"all": cal, "shown": group(shown), "hidden": group(hidden),
                        "made": group([r for r in rs if r["result"] == "done"]),
                        "skipped": group([r for r in rs if r["result"] == "missed"]),
                        "skaters": group(sk), "goalies": group([r for r in rs if r["goalie"]]),
                        "early": group([r for r in rs if not r["late"]]), "late": group([r for r in rs if r["late"]]),
                        "ir": group([r for r in rs if r["ir"]]), "kept_by_slack": group([r for r in rs if r["kept"]])},
        "bands": bands(scored),
        "verdicts": verdicts,
        "notes": notes,
        "worst": sorted(({k: r[k] for k in ("mp", "day", "result", "add", "drop", "net", "gain", "actual")}
                         for r in scored), key=lambda r: r["actual"])[:5],
        "best": sorted(({k: r[k] for k in ("mp", "day", "result", "add", "drop", "net", "gain", "actual")}
                        for r in scored), key=lambda r: -r["actual"])[:5],
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def _g(g):
    if not g.get("n"):
        return "none scored"
    r = g.get("range90")
    rng = f", 90% range {r[0]:+.2f} to {r[1]:+.2f}" if r else ""
    ratio = f", {g['ratio']:.0%} of expected" if g.get("ratio") is not None else ""
    return (f"{g['n']} scored, {g['actual']:+.1f} pts actual vs {g['expected']:+.1f} expected{ratio}; "
            f"avg {g['avg']:+.2f}{rng}; {g['ahead']} of {g['n']} ahead")


def markdown(a):
    when = datetime.fromtimestamp(a["updated"] / 1000).strftime("%Y-%m-%d %H:%M") if a.get("updated") else "offline run"
    out = [f"# Backtest of logged suggestions ({when})", "",
           f"{a['moves']} distinct moves logged, {a['scored']} scored, {a['pending']} waiting on games. "
           f"A bar only moves with {a['min_n']}+ scored moves next to it and a clear signal.", "",
           "## Where the bars should move", ""]
    for v in a["verdicts"]:
        arrow = {"lower": f"lower to {v.get('to')}", "raise": f"raise to {v.get('to')}", "hold": "hold",
                 "wait": "hold (not enough data)"}[v["call"]]
        out.append(f"- **{v['bar']}**, now {v['now']:g}: **{arrow}**. {v['why']}")
    for n in a["notes"]:
        out.append(f"- {n}")
    out += ["", "## Calibration (actual this-week points vs the plan's this-week gain)", ""]
    for k, label in (("all", "All scored"), ("shown", "Shown to you"), ("hidden", "Left off the list"),
                     ("made", "Made"), ("skipped", "Skipped"), ("skaters", "Skater moves"), ("goalies", "Goalie moves"),
                     ("early", "Early week"), ("late", "Last days"), ("ir", "IR moves"), ("kept_by_slack", "Kept by slack")):
        out.append(f"- {label}: {_g(a['calibration'][k])}")
    out += ["", "## By expected net", "", "| net | scored | avg actual | ahead | 90% range |", "|---|---|---|---|---|"]
    for b in a["bands"]:
        r = b.get("range90")
        out.append(f"| {b['from']:+.1f} to {b['to']:+.1f} | {b['n']} | {b['avg']:+.2f} | {b['ahead']} | "
                   + (f"{r[0]:+.2f} to {r[1]:+.2f}" if r else "-") + " |")
    out += ["", "## Biggest misses", ""]
    out += [f"- wk {r['mp']} {r['day']}: {r['add']} for {r['drop']} ({r['result']}): expected {r['gain']:+.1f}, "
            f"actual {r['actual']:+.1f}" for r in a["worst"]]
    out += ["", "## Biggest hits", ""]
    out += [f"- wk {r['mp']} {r['day']}: {r['add']} for {r['drop']} ({r['result']}): expected {r['gain']:+.1f}, "
            f"actual {r['actual']:+.1f}" for r in a["best"]]
    out += ["", "## Limits", "",
            "- Actual = added player's points minus dropped player's points over the same days, bench games included.",
            "- Moves logged before 2026-11-25 lack the plan's own view of the move; early/late is read from the day name.",
            "- Small samples: a 90% range that crosses zero means the data cannot tell yet."]
    return "\n".join(out) + "\n"


def write_files(log_rows, out="history", now_ms=None):
    """Called by the build with record.STATE['rows'] (already scored). Writes backtest.json and backtest.md."""
    d = Path(out)
    log = read_log(d / "moves.jsonl")
    scored = {f"{r.get('mp')}|{r['add']['id']}|{r['drop']['id']}": r.get("actual") for r in (log_rows or [])
              if r.get("actual") is not None}
    a = analyze(rows(log, scored, actuals_offline(d)), now_ms)
    d.mkdir(exist_ok=True)
    (d / "backtest.json").write_text(json.dumps(a, indent=1), encoding="utf-8")
    (d / "backtest.md").write_text(markdown(a), encoding="utf-8")
    return a
