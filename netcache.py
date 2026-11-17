#!/usr/bin/env python3
"""
Record / replay every web request a build makes, so a build can be repeated exactly (for testing).

  FH_RECORD=snap.json.gz python build.py   -> runs normally and saves every response + the build time
  FH_REPLAY=snap.json.gz python build.py   -> no network at all: answers come from the file, the clock is frozen
                                              at the recorded build time, so the page comes out the same every time

Nothing here is used in a normal build. Login cookies are never saved (only the URL and the response).
"""
import gzip
import json
import os
import time as _time
from datetime import datetime as _dt

import requests

STATE = {"mode": None, "path": None, "store": {}, "now": None}
_real_get = requests.get


class _Resp:
    """Just enough of requests.Response for this project."""

    def __init__(self, status, text, url):
        self.status_code, self.text, self.url = status, text, url

    def json(self):
        return json.loads(self.text)

    @property
    def ok(self):
        return self.status_code < 400

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error for url: {self.url}", response=self)


def _key(url, params=None, headers=None):
    p = json.dumps(params, sort_keys=True, default=str) if params is not None else ""
    h = (headers or {}).get("x-fantasy-filter", "")
    return f"{url}|{p}|{h}"


def _get(url, params=None, headers=None, **kw):
    k = _key(url, params, headers)
    if STATE["mode"] == "replay":
        hits = STATE["store"].get(k)
        if not hits:
            raise requests.ConnectionError(f"not in snapshot: {url}")
        n = STATE.setdefault("_used", {}).get(k, 0)        # same URL asked twice: hand back the answers in order
        STATE["_used"][k] = n + 1
        h = hits[min(n, len(hits) - 1)]
        if h.get("error"):
            raise requests.ConnectionError(h["error"])
        return _Resp(h["status"], h["text"], url)
    try:
        r = _real_get(url, params=params, headers=headers, **kw)
    except Exception as e:
        STATE["store"].setdefault(k, []).append({"error": f"{type(e).__name__}: {e}"})
        raise
    STATE["store"].setdefault(k, []).append({"status": r.status_code, "text": r.text})
    return r


class _Frozen(_dt):
    @classmethod
    def now(cls, tz=None):
        return _dt.fromtimestamp(STATE["now"] / 1000, tz)


def _freeze_clock():
    import sys
    ms = STATE["now"]
    _time.time = lambda: ms / 1000.0
    _time.sleep = lambda s: None
    for mod in list(sys.modules.values()):
        if getattr(mod, "datetime", None) is _dt:
            try:
                mod.datetime = _Frozen
            except Exception:
                pass


def install():
    """Call at the very start of build.py. Does nothing unless FH_RECORD or FH_REPLAY is set."""
    rec, rep = os.environ.get("FH_RECORD"), os.environ.get("FH_REPLAY")
    if rep:
        with gzip.open(rep, "rt", encoding="utf-8") as f:
            snap = json.load(f)
        STATE.update(mode="replay", path=rep, store=snap["responses"], now=snap["now_ms"])
        requests.get = _get
        _freeze_clock()
        print(f"  (replaying {rep}: {len(snap['responses'])} saved requests, clock frozen at build time)")
    elif rec:
        STATE.update(mode="record", path=rec, now=int(_time.time() * 1000))
        requests.get = _get


def freeze_late():
    """Modules imported after install() also get the frozen clock."""
    if STATE["mode"] == "replay":
        _freeze_clock()


def now_ms():
    return STATE["now"] if STATE["now"] is not None else int(_time.time() * 1000)


def save():
    if STATE["mode"] != "record":
        return
    with gzip.open(STATE["path"], "wt", encoding="utf-8") as f:
        json.dump({"now_ms": STATE["now"], "responses": STATE["store"]}, f)
    print(f"  saved {len(STATE['store'])} requests to {STATE['path']}")
