#!/usr/bin/env python3
"""
PUBLISH CHECK: never let a broken build replace a good live page.

Runs in the workflow after build.py and before the page is published. It compares the new build's site/health.json
with the live site's health.json:

  - The new build is "degraded" when part of the move advice failed (streams, game plan or planner) or the health
    badge is red (line data or NHL stats missing).
  - A degraded build is held back when the live page is healthy and less than HOLD_HOURS old. The live page stays
    up, and a phone alert says why.
  - Otherwise it publishes (a healthy build always publishes, and a degraded build beats a page that is old or also
    degraded, because its badge tells you what is missing).

Writes publish=true|false to $GITHUB_OUTPUT. Any problem in this check itself means publish: it never blocks a
release on its own error.
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

HOLD_HOURS = 18
NEW = Path("site/health.json")


def degraded(h):
    return (not h.get("core_ok", True)) or h.get("level") == "bad"


def live_url():
    if os.environ.get("LIVE_HEALTH_URL"):
        return os.environ["LIVE_HEALTH_URL"]
    owner, _, repo = os.environ.get("GITHUB_REPOSITORY", "jbaur0219/fantasy-hockey").partition("/")
    return f"https://{owner}.github.io/{repo}/health.json"


def fetch_live(url):
    req = urllib.request.Request(url + f"?t={int(time.time())}", headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def decide(new, live, now_ms):
    """(publish?, reason)."""
    if not degraded(new):
        return True, "new build is healthy"
    if live is None:
        return True, "new build is degraded, but the live page's health is unknown"
    if degraded(live):
        return True, "new build is degraded, but so is the live page"
    age_h = (now_ms - (live.get("at") or 0)) / 3.6e6
    if age_h >= HOLD_HOURS:
        return True, f"new build is degraded, but the live page is {age_h:.0f} hours old"
    return False, f"new build is degraded and the live page is healthy ({age_h:.1f} hours old)"


def what_failed(new):
    names = {"streams": "streams", "gameplan": "the move plan", "planner": "the planner"}
    parts = [names.get(k, k) for k in new.get("missing") or []]
    parts += (new.get("items") or [])[:1] if new.get("level") == "bad" else []
    return "; ".join(parts) or "some data"


def main():
    publish, reason = True, "no health file from the build"
    try:
        if NEW.exists():
            new = json.loads(NEW.read_text(encoding="utf-8"))
            live = None
            if degraded(new):
                try:
                    live = fetch_live(live_url())
                except Exception as e:
                    print(f"could not read the live page's health ({type(e).__name__}: {e})")
            publish, reason = decide(new, live, int(time.time() * 1000))
            if not publish:
                Path("held_alert.json").write_text(json.dumps({
                    "title": "Fantasy Hockey: kept the last good update",
                    "body": f"The latest update was missing {what_failed(new)}, so the app is still showing the "
                            "earlier one. It will try again at the next scheduled update.",
                    "url": "./", "tag": "fh-health"}), encoding="utf-8")
    except Exception as e:
        publish, reason = True, f"check failed ({type(e).__name__}: {e})"
    print(("PUBLISH: " if publish else "::warning::HELD BACK: ") + reason)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"publish={'true' if publish else 'false'}\n")


if __name__ == "__main__":
    main()
    sys.exit(0)
