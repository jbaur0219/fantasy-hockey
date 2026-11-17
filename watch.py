#!/usr/bin/env python3
"""
WATCHER: keeps the site on schedule even though GitHub's own timer is unreliable.

GitHub only ran the old 15-minute timer a few times a day, so builds and the morning alert were hours late or missing.
This runs as one long job (about 5 hours 40 minutes). Every 10 minutes it runs scheduler.py (which starts a build at
the right moments: morning, 4 hours before the first game, at the first puck drop, and after the last game). Before it
ends it starts the next watcher, so there is always one running. A few spread-out timer entries in watch.yml restart
the chain if it ever breaks.

It also checks that the site itself is fresh: if no live build has succeeded in 14 hours it sends a phone alert.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import scheduler

RUN_FOR = 5 * 3600 + 40 * 60
EVERY = 10 * 60
STALE_HOURS = 14


def last_live_build_age_h():
    out = subprocess.run(["gh", "run", "list", "--workflow", "daily.yml", "--status", "success", "--limit", "20",
                          "--json", "displayTitle,updatedAt"], capture_output=True, text=True, check=True).stdout
    for r in json.loads(out):
        if "preview" in r["displayTitle"]:
            continue
        t = datetime.fromisoformat(r["updatedAt"].replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - t).total_seconds() / 3600
    return 999


def alert(title, body):
    if not os.environ.get("PUSH_CONFIG"):
        print("::warning::" + body)
        return
    Path("watch_alert.json").write_text(json.dumps({"title": title, "body": body, "url": "./", "tag": "fh-health"}))
    subprocess.run([sys.executable, "notify.py", "watch_alert.json"], check=False)


def main():
    t0, alerted = time.time(), False
    while True:
        try:
            scheduler.main()
        except Exception as e:                                # a bad check never stops the watcher
            print(f"::warning::check failed: {type(e).__name__}: {e}")
        try:
            age = last_live_build_age_h()
            et_hour = datetime.now(scheduler.ET).hour
            print(f"last successful live build: {age:.1f} h ago")
            if age > STALE_HOURS and not alerted and 9 <= et_hour <= 21:
                alert("Fantasy Hockey: site is not updating",
                      f"The site has not updated in {age:.0f} hours. ESPN login cookies may have expired; "
                      "check the Actions tab on GitHub.")
                alerted = True
        except Exception as e:
            print(f"::warning::freshness check failed: {type(e).__name__}: {e}")
        if time.time() - t0 + EVERY > RUN_FOR:
            break
        time.sleep(EVERY)
    if not scheduler.DRY_RUN:
        subprocess.run(["gh", "workflow", "run", "watch.yml"], check=False)   # hand over to the next watcher
        print("started the next watcher")


if __name__ == "__main__":
    main()
