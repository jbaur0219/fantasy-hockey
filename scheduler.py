#!/usr/bin/env python3
"""
Decides whether the site should be rebuilt right now, and starts the build if so.

Runs every 15 minutes from .github/workflows/refresh.yml. Four triggers, each at most once per day:

  morning   : from 8:50 AM Eastern -> rebuild, so the site is fresh by 9 AM every day (also sends the morning alert)
  post-game : every NHL game on that day's slate is over -> rebuild (the build waits ~10 min so stats can settle)
  pre-game  : we are inside the 4 hours before that day's first puck drop -> rebuild (injuries, goalie news, lines)
  lock      : the day's first puck has dropped -> rebuild, so the site drops that day (nobody can be added once the
              first game starts) and leads with tomorrow

A started build is titled "morning YYYY-MM-DD", "post-game YYYY-MM-DD", "pre-game YYYY-MM-DD" or "lock YYYY-MM-DD". A trigger is skipped if a run with that
title already exists and did not fail, so a failed or cancelled build is retried on the next check.

Set DRY_RUN=true to only print what it would do.
"""
import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
PRE_GAME_HOURS = 4
MORNING_START = (8, 50)                       # ET; the build takes a few minutes, so it is fresh by 9 AM
MORNING_END_HOUR = 12                         # a missed morning build is skipped after noon
PENDING = {"FUT", "PRE", "LIVE", "CRIT"}      # anything else (FINAL, OFF, postponed...) counts as over
WORKFLOW = "daily.yml"
DRY_RUN = os.environ.get("DRY_RUN", "").lower() == "true"


def fetch_games(day):
    """Games on one date from the NHL, as [{'start': datetime, 'state': 'FINAL'}]; None if it could not be read."""
    url = f"https://api-web.nhle.com/v1/score/{day.isoformat()}"
    last = None
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "fantasy-hockey-refresh"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.load(r)
            games = []
            for g in data.get("games", []):
                start = datetime.fromisoformat(g["startTimeUTC"].replace("Z", "+00:00"))
                games.append({"start": start, "state": str(g.get("gameState", "")).upper()})
            return games
        except Exception as e:  # network hiccup, odd response...
            last = e
            time.sleep(3)
    print(f"::warning::Could not read NHL games for {day}: {last}")
    return None


def build_titles():
    """Titles of recent builds that are running, queued or finished fine."""
    out = subprocess.run(
        ["gh", "run", "list", "--workflow", WORKFLOW, "--limit", "80", "--json", "displayTitle,conclusion"],
        capture_output=True, text=True, check=True,
    ).stdout
    bad = {"failure", "cancelled", "timed_out", "startup_failure"}
    return [r["displayTitle"] for r in json.loads(out) if r.get("conclusion") not in bad]


def start(reason):
    print(f"-> starting a build: {reason}" + ("  (dry run, not started)" if DRY_RUN else ""))
    if not DRY_RUN:
        subprocess.run(["gh", "workflow", "run", WORKFLOW, "-f", f"reason={reason}"], check=True)


def main():
    now = datetime.now(timezone.utc)
    today = now.astimezone(ET).date()
    yesterday = today - timedelta(days=1)
    print(f"Now: {now:%Y-%m-%d %H:%M} UTC / {now.astimezone(ET):%a %b %d %I:%M %p} ET")
    titles = build_titles()

    def done(reason):
        return any(f"({reason})" in t for t in titles)

    slates = {}
    for day in (yesterday, today):
        games = fetch_games(day)
        slates[day] = games
        if games is None:
            continue
        states = {}
        for g in games:
            states[g["state"]] = states.get(g["state"], 0) + 1
        print(f"{day}: {len(games)} games {states}")

    started = False

    # 1) post-game: the whole slate is over (yesterday's covers games that ran past midnight)
    for day in (yesterday, today):
        games = slates[day]
        reason = f"post-game {day}"
        if games and all(g["state"] not in PENDING for g in games):
            if done(reason):
                print(f"{reason}: already refreshed")
            else:
                start(reason)
                started = True

    # 2) pre-game: inside the window before today's first puck drop
    games = slates[today]
    if games:
        first = min(g["start"] for g in games)
        opens = first - timedelta(hours=PRE_GAME_HOURS)
        reason = f"pre-game {today}"
        print(f"First puck drop {first.astimezone(ET):%I:%M %p} ET, pre-game window opens {opens.astimezone(ET):%I:%M %p} ET")
        if opens <= now < first:
            if done(reason):
                print(f"{reason}: already refreshed")
            else:
                start(reason)
                started = True

    # 3) lock: today's first puck has dropped, so today is closed for adds; rebuild to lead with tomorrow
    if games and not started and any(g["state"] in PENDING for g in games):   # not when the slate is over: post-game covers that
        reason = f"lock {today}"
        if now >= min(g["start"] for g in games):
            if done(reason):
                print(f"{reason}: already refreshed")
            else:
                start(reason)
                started = True

    # 4) morning: fresh by 9 AM Eastern every day (and the morning alert goes out with this build)
    et_now = now.astimezone(ET)
    reason = f"morning {today}"
    if not started and (et_now.hour, et_now.minute) >= MORNING_START and et_now.hour < MORNING_END_HOUR:
        if done(reason):
            print(f"{reason}: already refreshed")
        else:
            start(reason)
            started = True

    if not started:
        print("Nothing to do this time.")


if __name__ == "__main__":
    main()
