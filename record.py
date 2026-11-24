#!/usr/bin/env python3
"""
TRACK RECORD (READ-ONLY): did the advice work?

How a move is scored
  - While a planned move's day is still open, every build saves both players' season fantasy points ("base").
    The last save before that day's first puck drop is the starting line.
  - From then on: points the added player scored minus points the dropped player scored, over the same days,
    through the end of that matchup week. Made moves and skipped moves are scored the same way, so you can see
    what following the advice was worth either way.
  - A week's numbers are final once the next matchup week starts (saved in history/results.json).
  - Small moves the plan left off your list are logged as "hidden" and scored the same way. They stay out of the
    app's numbers (you never saw them); the private ledger (ledger.py) reports them separately.

It compares the two players, not your lineup slots: a player who sat on your bench still counts.
Never fails the build: any problem just leaves the card out.
"""
import json
from pathlib import Path

import analyze as A

LOG_FILE = Path(__file__).with_name("history") / "moves.jsonl"
RESULTS_FILE = Path(__file__).with_name("history") / "results.json"
STATE = {"tot": {}, "rows": []}


def install(data, season):
    """Season fantasy points and games for every player this build can see (all rosters + free agents)."""
    tot = {}

    def take(pl):
        by_id = {s.get("id"): s for s in pl.get("stats", [])}
        cur = by_id.get(f"00{season}", {})
        gp = A.num(cur.get("stats", {}), A.S_GP)
        if pl.get("id") is not None:
            tot[pl["id"]] = [round(float(cur.get("appliedTotal", 0) or 0), 2), int(gp)]

    for t in (data.get("roster") or {}).get("teams", []):
        for e in (t.get("roster") or {}).get("entries", []):
            take((e.get("playerPoolEntry") or {}).get("player") or {})
    for e in (data.get("free_agents") or {}).get("players", []):
        take(e.get("player") or {})
    STATE["tot"] = tot
    return tot


def snap(add_id, drop_id, now_ms):
    a, d = STATE["tot"].get(add_id), STATE["tot"].get(drop_id)
    if not a or not d:
        return None
    return {"a": a, "d": d, "at": now_ms}


def _key(e):
    return f"{e.get('mp')}|{e['add']['id']}|{e['drop']['id']}"


def _read_log():
    out = []
    try:
        for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    except FileNotFoundError:
        pass
    return out


def _score(e):
    b = e.get("base")
    if not b:
        return None
    a, d = STATE["tot"].get(e["add"]["id"]), STATE["tot"].get(e["drop"]["id"])
    if not a or not d:
        return None
    return {"actual": round((a[0] - b["a"][0]) - (d[0] - b["d"][0]), 1),
            "ga": a[1] - b["a"][1], "gd": d[1] - b["d"][1]}


def build(mp, write=True):
    """The track-record card: made vs skipped, each move's expected vs actual."""
    log = _read_log()
    if not log:
        return None
    try:
        results = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        results = {}
    changed = False
    rows = []
    seen = set()
    for e in log:
        k = _key(e)
        if k in seen:
            continue
        seen.add(k)
        final = results.get(k)
        sc = final
        if not final:
            sc = _score(e)
            if sc and mp is not None and e.get("mp") is not None and e["mp"] < mp:
                results[k] = sc               # the week is over: freeze it
                changed = True
                final = sc
        rows.append({"mp": e.get("mp"), "day": e.get("day"), "logged": e.get("logged"), "result": e.get("result"),
                     "add": e["add"], "drop": e["drop"],
                     "expected": e.get("net") if e.get("net") is not None else e.get("expected_gain"),
                     "conf": e.get("conf"), "why1": e.get("why1"),
                     "actual": sc["actual"] if sc else None, "ga": sc["ga"] if sc else None, "gd": sc["gd"] if sc else None,
                     "final": bool(final), "tracked": bool(e.get("base"))})
    if changed and write:
        RESULTS_FILE.parent.mkdir(exist_ok=True)
        RESULTS_FILE.write_text(json.dumps(results, indent=1, sort_keys=True), encoding="utf-8")

    def summary(kind):
        rs = [r for r in rows if r["result"] == kind and r["actual"] is not None]
        return {"n": len(rs), "pts": round(sum(r["actual"] for r in rs), 1),
                "wins": sum(1 for r in rs if r["actual"] > 0), "expected": round(sum(r["expected"] or 0 for r in rs), 1)}

    def by_conf(c):
        rs = [r for r in rows if r["conf"] == c and r["result"] != "hidden" and r["actual"] is not None]
        return {"n": len(rs), "pts": round(sum(r["actual"] for r in rs), 1), "wins": sum(1 for r in rs if r["actual"] > 0)}

    STATE["rows"] = list(rows)                        # every move, oldest first: the lifetime stats (ledger.py) read these
    rows.reverse()                                    # newest first
    shown = [r for r in rows if r["result"] != "hidden"]              # moves you were shown (the app's own numbers)
    return {"made": summary("done"), "skipped": summary("missed"),
            "strong": by_conf("strong"), "lean": by_conf("lean"), "optional": by_conf("optional"),
            "hidden": summary("hidden"),
            "untracked": sum(1 for r in shown if not r["tracked"]), "moves": shown[:30]}
