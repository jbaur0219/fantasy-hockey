#!/usr/bin/env python3
"""Inspect how a Daily Faceoff team line-combinations page is built. Read-only; prints a short structure report."""
import json
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (personal fantasy hockey tool)"}
SKIP = ("Logo", "Color", "Headshot", "FaceUrl", "Image", "Url", "Legacy", "Fantasydata", "Puckpedia", "Slug")


def next_data(url):
    r = requests.get(url, headers=UA, timeout=30)
    print("GET", url, "->", r.status_code, len(r.text))
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
    return json.loads(m.group(1))["props"]["pageProps"] if m else None


goalies = next_data("https://www.dailyfaceoff.com/starting-goalies")
slugs = sorted({g.get("homeTeamSlug") for g in goalies["data"]} | {g.get("awayTeamSlug") for g in goalies["data"]})
print("team slugs:", slugs[:6], "... total", len(slugs))
slug = "tampa-bay-lightning" if "tampa-bay-lightning" in slugs else slugs[0]
page = next_data(f"https://www.dailyfaceoff.com/teams/{slug}/line-combinations")
if page:
    print("pageProps keys:", list(page.keys()))
    for k, v in page.items():
        if isinstance(v, dict):
            print(" ", k, "dict keys:", list(v.keys())[:20])
            for k2, v2 in v.items():
                if isinstance(v2, list) and v2 and isinstance(v2[0], dict):
                    print("   ", k2, "list len", len(v2), "| item keys:", [x for x in v2[0].keys() if not any(s in x for s in SKIP)])
                    for it in v2[:30]:
                        print("      ", {x: it[x] for x in it if not any(s in x for s in SKIP)})
                    break
