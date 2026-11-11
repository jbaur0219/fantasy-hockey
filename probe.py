#!/usr/bin/env python3
"""Inspect how the Daily Faceoff starting-goalies page is built. Read-only; prints a short structure report."""
import json
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (personal fantasy hockey tool)"}
SKIP = ("Logo", "Color", "Headshot", "FaceUrl", "Slug", "Legacy", "Fantasydata", "Puckpedia")

r = requests.get("https://www.dailyfaceoff.com/starting-goalies", headers=UA, timeout=30)
page = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S).group(1))["props"]["pageProps"]
games = page["data"]
print("date", page.get("date"), "| specificDate", page.get("specificDate"), "| games", len(games))
for n in (0, 1):
    print("--- game", n)
    for k, v in games[n].items():
        if not any(s in k for s in SKIP):
            print(f"{k} = {str(v)[:70]}")
