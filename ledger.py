#!/usr/bin/env python3
"""
LIFETIME LEDGER (READ-ONLY): every move the tool has ever suggested, and what following it was worth.

record.py already logs each suggestion (history/moves.jsonl) and scores it once its games are played. This module turns
that into the numbers you can show other people:

  history/lifetime.json  lifetime totals, by rating, by week, newest moves
  history/moves.csv      every move ever suggested, one row each, opens in Excel
Back end only: nothing here is published to the site or shown in the app. The build workflow commits history/.

Definitions (shown on the page, so nobody has to guess)
  Suggested      every distinct move the plan has put in front of you since logging began.
  Scored         moves whose games have been played. Points = what the added player scored minus what the dropped
                 player scored, from the move's day to the end of that matchup week.
  Made / Skipped by what you actually did in ESPN. "Extra points" is the total for moves you made.
  Misses are included: the win rate counts every scored move, good or bad.
Never fails the build: any problem just leaves the stats files out.
"""
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


def _r(x):
    return round(x, 1)


def _group(rows):
    rs = [r for r in rows if r.get("actual") is not None]
    n = len(rs)
    pts = sum(r["actual"] for r in rs)
    wins = sum(1 for r in rs if r["actual"] > 0)
    return {"n": n, "pts": _r(pts), "wins": wins, "win_pct": round(100 * wins / n) if n else None,
            "avg": round(pts / n, 2) if n else None, "expected": _r(sum(r.get("expected") or 0 for r in rs))}


def _date(ms):
    try:
        return datetime.fromtimestamp(ms / 1000, tz=ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        return None


def summarize(rows, now_ms=None):
    """rows: every move, oldest first (record.STATE['rows'])."""
    made = [r for r in rows if r.get("result") == "done"]
    skipped = [r for r in rows if r.get("result") == "missed"]
    scored = [r for r in rows if r.get("actual") is not None]
    final = [r for r in scored if r.get("final")]
    weeks = {}
    for r in rows:
        weeks.setdefault(r.get("mp"), []).append(r)
    by_week = []
    for mp in sorted((k for k in weeks if k is not None)):
        w = weeks[mp]
        by_week.append({"week": mp, "suggested": len(w), "made": _group([r for r in w if r.get("result") == "done"]),
                        "all": _group(w)})
    logged = [r["logged"] for r in rows if r.get("logged")]
    return {
        "updated": now_ms, "since": _date(min(logged)) if logged else None,
        "suggested": len(rows), "scored": len(scored), "final": len(final),
        "pending": len(rows) - len(scored),
        "made": _group(made), "skipped": _group(skipped), "all": _group(rows),
        "by_rating": {c: _group([r for r in rows if r.get("conf") == c]) for c in ("strong", "lean", "optional")},
        "by_week": by_week,
        "recent": [{"week": r.get("mp"), "day": r.get("day"), "status": "made" if r.get("result") == "done" else "skipped",
                    "rating": r.get("conf"), "add": r["add"]["n"], "drop": r["drop"]["n"],
                    "expected": r.get("expected"), "actual": r.get("actual"), "final": bool(r.get("final"))}
                   for r in reversed(rows[-15:])],
    }


def csv_text(rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["matchup_week", "day", "logged_date", "status", "rating", "add", "drop", "expected_pts", "actual_pts",
                "final", "scored"])
    for r in rows:
        w.writerow([r.get("mp"), r.get("day"), _date(r["logged"]) if r.get("logged") else "",
                    "made" if r.get("result") == "done" else "skipped", r.get("conf") or "", r["add"]["n"], r["drop"]["n"],
                    "" if r.get("expected") is None else r["expected"], "" if r.get("actual") is None else r["actual"],
                    "yes" if r.get("final") else "no", "yes" if r.get("actual") is not None else "no"])
    return out.getvalue()


def write_files(rows, out="history", now_ms=None):
    s = summarize(rows, now_ms)
    d = Path(out)
    d.mkdir(exist_ok=True)
    (d / "lifetime.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
    (d / "moves.csv").write_text(csv_text(rows), encoding="utf-8")
    return s
