#!/usr/bin/env python3
"""Inspect how the Daily Faceoff starting-goalies page is built. Read-only; prints a short structure report."""
import json
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (personal fantasy hockey tool)"}
LINES = [0]


def say(*a):
    if LINES[0] < 90:
        print(*a)
        LINES[0] += 1


def describe(o, path, depth):
    if depth > 6 or LINES[0] >= 90:
        return
    if isinstance(o, dict):
        say(f"{path} dict keys: {list(o.keys())[:25]}")
        for k, v in list(o.items())[:25]:
            if isinstance(v, (dict, list)) and v:
                describe(v, f"{path}.{k}", depth + 1)
    elif isinstance(o, list):
        say(f"{path} list len {len(o)}")
        if o and isinstance(o[0], (dict, list)):
            describe(o[0], f"{path}[0]", depth + 1)
        elif o:
            say(f"{path}[0] = {str(o[0])[:100]}")


r = requests.get("https://www.dailyfaceoff.com/starting-goalies", headers=UA, timeout=30)
say("status", r.status_code, "len", len(r.text))
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
say("has __NEXT_DATA__:", bool(m))
if m:
    data = json.loads(m.group(1))
    describe(data.get("props", {}).get("pageProps", {}), "pageProps", 0)
else:
    for kw in ("Confirmed", "Unconfirmed", "Likely"):
        i = r.text.find(kw)
        say(kw, "found at", i, "|", r.text[max(0, i - 150):i + 150].replace("\n", " ") if i >= 0 else "")
