#!/usr/bin/env python3
"""
PLAYERS YOU CHOSE TO KEEP (READ-ONLY toward ESPN): the "Keep him" button on the page.

Tapping "Keep" saves the player on the phone right away, and (when the page has a GitHub token) starts a refresh with
the full keep list as the `keep` input. build.py passes it here, it is saved in keep.json for this matchup week, and
the move plan never suggests dropping those players. The list clears itself when a new matchup week starts.

FH_KEEP: comma-separated ESPN player ids, or "none" to clear. Empty / unset = leave the saved list alone.
"""
import json
import os
from pathlib import Path

FILE = Path(__file__).with_name("keep.json")


def _read():
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def apply_env(mp):
    """Save the list sent with this build (if any) for matchup mp."""
    raw = (os.environ.get("FH_KEEP") or "").strip()
    if not raw:
        return
    ids = [] if raw.lower() == "none" else sorted({int(x) for x in raw.replace(" ", "").split(",") if x.lstrip("-").isdigit()})
    FILE.write_text(json.dumps({"mp": mp, "ids": ids}), encoding="utf-8")
    print(f"  keep list for matchup {mp}: {ids or 'cleared'}")


def load(mp):
    st = _read()
    return set(st.get("ids") or []) if st.get("mp") == mp else set()
