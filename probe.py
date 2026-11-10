#!/usr/bin/env python3
"""Probe which public hockey data sources work from this machine. Read-only; prints a short report."""
import csv
import io
import json

import requests

UA = {"User-Agent": "Mozilla/5.0 (personal fantasy hockey tool)"}


def get(url, params=None):
    print("\n==", url, params or "")
    try:
        r = requests.get(url, params=params, headers=UA, timeout=25)
    except Exception as e:
        print("   ERROR", type(e).__name__, str(e)[:140])
        return None
    print("   status", r.status_code, "|", r.headers.get("content-type", "")[:35], "|", len(r.content), "bytes")
    if r.status_code != 200:
        print("   body:", r.text[:140].replace("\n", " "))
        return None
    return r


def nhl_stats():
    base = "https://api.nhle.com/stats/rest/en"
    exp = "seasonId=20262027 and gameTypeId=2"
    for rep in ("skater/summary", "skater/timeonice", "skater/powerplay", "skater/realtime",
                "goalie/summary", "goalie/advanced", "goalie/startedVsRelieved"):
        r = get(f"{base}/{rep}", {"limit": 2, "cayenneExp": exp})
        if r:
            d = r.json()
            rows = d.get("data", [])
            print("   total:", d.get("total"), "| fields:", sorted(rows[0].keys())[:40] if rows else "none")


def nhl_web():
    r = get("https://api-web.nhle.com/v1/schedule/now")
    if not r:
        return
    days = r.json().get("gameWeek", [])
    games = [g for d in days[:1] for g in d.get("games", [])]
    print("   first day:", days[0].get("date") if days else None, "| games:", len(games))
    if games:
        gid = games[0]["id"]
        r2 = get(f"https://api-web.nhle.com/v1/gamecenter/{gid}/landing")
        if r2:
            j = r2.json()
            print("   landing keys:", sorted(j.keys()))
            m = j.get("matchup") or {}
            print("   matchup keys:", sorted(m.keys()))
            gc = m.get("goalieComparison") or {}
            print("   goalieComparison keys:", sorted(gc.keys()))
            for side in ("homeTeam", "awayTeam"):
                t = gc.get(side) or {}
                print("   ", side, "goalie leaders:", json.dumps(t)[:300])


def moneypuck():
    for season in (2026, 2025):
        for kind in ("skaters", "goalies"):
            r = get(f"https://moneypuck.com/moneypuck/playerData/seasonSummary/{season}/regular/{kind}.csv")
            if r:
                rows = list(csv.DictReader(io.StringIO(r.text)))
                print("   rows:", len(rows), "| columns:", len(rows[0]) if rows else 0)
                if rows:
                    print("   sample columns:", list(rows[0].keys())[:30])


def faceoff():
    r = get("https://www.dailyfaceoff.com/robots.txt")
    if r:
        print("   robots.txt:", r.text[:400].replace("\n", " | "))
    get("https://www.dailyfaceoff.com/starting-goalies")


if __name__ == "__main__":
    nhl_stats()
    nhl_web()
    moneypuck()
    faceoff()
    print("\nDONE")
