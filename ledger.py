#!/usr/bin/env python3
"""
LIFETIME LEDGER (READ-ONLY): every move the tool has ever suggested, and what following it was worth.

record.py already logs each suggestion (history/moves.jsonl) and scores it once its games are played. This module turns
that into the numbers you can show other people:

  site/stats.html   a shareable page (no login): lifetime totals, by rating, by week, newest moves
  site/stats.json   the same numbers for anything else that wants them
  site/moves.csv    every move ever suggested, one row each, opens in Excel

Definitions (shown on the page, so nobody has to guess)
  Suggested      every distinct move the plan has put in front of you since logging began.
  Scored         moves whose games have been played. Points = what the added player scored minus what the dropped
                 player scored, from the move's day to the end of that matchup week.
  Made / Skipped by what you actually did in ESPN. "Extra points" is the total for moves you made.
  Misses are included: the win rate counts every scored move, good or bad.
Never fails the build: any problem just leaves the stats files out.
"""
import csv
import html
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


def _sg(x):
    return "n/a" if x is None else f"{x:+.1f}"


def page(s):
    e = html.escape
    m, a, sk = s["made"], s["all"], s["skipped"]

    def tile(v, k, sub=""):
        return f'<div class="t"><div class="v">{e(str(v))}</div><div class="k">{e(k)}</div><div class="s">{e(sub)}</div></div>'

    tiles = "".join([
        tile(s["suggested"], "Moves suggested", f"since {s['since']}" if s["since"] else ""),
        tile(_sg(m["pts"]), "Extra points", f"from {m['n']} moves followed"),
        tile(f"{a['win_pct']}%" if a["win_pct"] is not None else "n/a", "Moves that came out ahead",
             f"{a['wins']} of {a['n']} scored"),
        tile(_sg(a["avg"]) if a["avg"] is not None else "n/a", "Points per move", "all scored moves"),
    ])
    rat = "".join(
        f'<tr><td>{c.title()}</td><td>{g["n"]}</td><td>{g["wins"]}</td><td>{_sg(g["pts"])}</td></tr>'
        for c, g in s["by_rating"].items() if g["n"])
    wk = "".join(
        f'<tr><td>Week {w["week"]}</td><td>{w["suggested"]}</td><td>{_sg(w["made"]["pts"])}</td><td>{_sg(w["all"]["pts"])}</td></tr>'
        for w in reversed(s["by_week"]))
    rec = "".join(
        f'<tr><td>{e(str(r["day"] or ""))}</td><td>{e(r["add"])} for {e(r["drop"])}</td><td>{e(r["status"])}</td>'
        f'<td>{"pending" if r["actual"] is None else _sg(r["actual"])}</td></tr>' for r in s["recent"])
    upd = datetime.fromtimestamp((s["updated"] or 0) / 1000, tz=timezone.utc).strftime("%b %d, %Y") if s["updated"] else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Fantasy Hockey Manager: track record</title>
<style>
:root{{--bg:#fff;--fg:#1d1d1f;--mu:#6e6e73;--ln:#e5e5ea;--cd:#f5f5f7;--gd:#1a7f37}}
@media(prefers-color-scheme:dark){{:root{{--bg:#000;--fg:#f5f5f7;--mu:#98989d;--ln:#2c2c2e;--cd:#1c1c1e;--gd:#30d158}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 -apple-system,BlinkMacSystemFont,"SF Pro Text",system-ui,sans-serif}}
main{{max-width:720px;margin:0 auto;padding:28px 18px 60px}}h1{{font-size:28px;margin:0 0 4px}}h2{{font-size:18px;margin:30px 0 8px}}
.mu{{color:var(--mu);font-size:14px}}.g{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:18px}}
.t{{background:var(--cd);border-radius:16px;padding:16px}}.v{{font-size:32px;font-weight:700;color:var(--gd)}}.k{{font-weight:600}}.s{{color:var(--mu);font-size:13px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{text-align:left;padding:8px 6px;border-bottom:1px solid var(--ln)}}th{{color:var(--mu);font-weight:500}}
a{{color:inherit}}
</style></head><body><main>
<h1>Track record</h1>
<div class="mu">Every move the tool has suggested, scored on real results. Misses are included. Updated {e(upd)}.</div>
<div class="g">{tiles}</div>
<h2>Followed vs. skipped</h2>
<table><tr><th></th><th>Moves</th><th>Ahead</th><th>Points</th></tr>
<tr><td>Followed</td><td>{m['n']}</td><td>{m['wins']}</td><td>{_sg(m['pts'])}</td></tr>
<tr><td>Skipped</td><td>{sk['n']}</td><td>{sk['wins']}</td><td>{_sg(sk['pts'])}</td></tr></table>
{f'<h2>By rating</h2><table><tr><th></th><th>Moves</th><th>Ahead</th><th>Points</th></tr>{rat}</table>' if rat else ''}
{f'<h2>By week</h2><table><tr><th></th><th>Suggested</th><th>Followed</th><th>All</th></tr>{wk}</table>' if wk else ''}
<h2>Latest moves</h2><table><tr><th>Day</th><th>Move</th><th></th><th>Result</th></tr>{rec}</table>
<h2>How it is scored</h2>
<p class="mu">Each suggested move is scored by the points the added player scored minus the points the dropped player
scored, from the move's day to the end of that matchup week. {s['pending']} of {s['suggested']} moves are still waiting
on their games. Hockey is noisy, so judge it over many moves, not one. <a href="moves.csv">Download every move (CSV)</a></p>
</main></body></html>"""


def write_files(rows, out="site", now_ms=None):
    s = summarize(rows, now_ms)
    d = Path(out)
    d.mkdir(exist_ok=True)
    (d / "stats.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
    (d / "moves.csv").write_text(csv_text(rows), encoding="utf-8")
    (d / "stats.html").write_text(page(s), encoding="utf-8")
    return s
