#!/usr/bin/env python3
"""
LIFETIME LEDGER (READ-ONLY): every move the tool has ever suggested, and what following it was worth.

record.py already logs each suggestion (history/moves.jsonl) and scores it once its games are played. This module turns
that into the numbers you can show other people:

  history/lifetime.json  lifetime totals, by rating, by week, newest moves
  history/moves.csv      every move ever suggested, one row each, opens in Excel
  history/move_ledger.xlsx  the same as an Excel file: Summary tab + All moves tab
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


def write_xlsx(s, rows, path):
    """history/move_ledger.xlsx: a Summary tab and an All moves tab, rebuilt from the log on every build."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    for k, v in [("Tracking since", s["since"]), ("Moves suggested", s["suggested"]), ("Scored so far", s["scored"]),
                 ("Waiting on games", s["pending"]), ("Moves you made (scored)", s["made"]["n"]),
                 ("Extra points from moves you made", s["made"]["pts"]), ("Moves you skipped (scored)", s["skipped"]["n"]),
                 ("Points from skipped moves", s["skipped"]["pts"]), ("Win rate, all scored (%)", s["all"]["win_pct"]),
                 ("Points per scored move", s["all"]["avg"])]:
        ws.append([k, v])
    ws.append([])
    ws.append(["By rating", "Scored", "Ahead", "Points"])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    for c, g in s["by_rating"].items():
        ws.append([c.title(), g["n"], g["wins"], g["pts"]])
    ws.append([])
    ws.append(["By week", "Suggested", "Made pts", "All pts"])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    for w in s["by_week"]:
        ws.append([f"Week {w['week']}", w["suggested"], w["made"]["pts"], w["all"]["pts"]])
    for c in ws["A"]:
        c.font = Font(bold=True)
    ws.column_dimensions["A"].width = 36
    m = wb.create_sheet("All moves")
    for r in csv.reader(io.StringIO(csv_text(rows))):
        m.append(r)
    for c in m[1]:
        c.font = Font(bold=True)
    for col, w in zip("ABCDEFGHIJK", [13, 13, 12, 9, 9, 20, 20, 13, 11, 7, 8]):
        m.column_dimensions[col].width = w
    m.freeze_panes = "A2"
    wb.save(path)


def write_files(rows, out="history", now_ms=None):
    s = summarize(rows, now_ms)
    d = Path(out)
    d.mkdir(exist_ok=True)
    (d / "lifetime.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
    (d / "moves.csv").write_text(csv_text(rows), encoding="utf-8")
    try:
        write_xlsx(s, rows, d / "move_ledger.xlsx")
    except Exception as e:                       # the Excel copy is an extra (needs openpyxl); the CSV is still written
        print(f"  Excel ledger skipped ({type(e).__name__}: {e})")
    return s
