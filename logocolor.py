#!/usr/bin/env python3
"""
Team color from the team's logo: the hue (0-359) of the most colorful thing in the picture.

Grays, blacks and whites are ignored, so a red-and-black logo gives red and a gray circle with a blue surfboard gives blue.
The app tints every matchup card (Today, the matchup sheet, League > Matchups) with this one number per team, so the same
team is the same color everywhere. Returns None when the picture can't be read (no Pillow, no network, a gray logo);
the app then falls back to a steady color of its own.
"""
import colorsys
import io
import json
import os
from pathlib import Path

import requests

try:
    from PIL import Image
except Exception:  # Pillow missing: every team just gets the app's fallback color
    Image = None


def hue_of_image(img):
    """Dominant hue of a PIL image, ignoring transparent, gray, near-black and near-white pixels."""
    img = img.convert("RGBA")
    img.thumbnail((64, 64))
    w, h = img.size
    px = img.load()
    bins = [0.0] * 36                                   # 10-degree bins, weight = how vivid and bright the pixel is
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 128:
                continue
            hh, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if s < 0.30 or v < 0.25:
                continue
            bins[int(hh * 36) % 36] += s * v
    if max(bins) <= 0:
        return None
    # smooth over neighbours (wrapping) so one hue split across two bins still wins
    sm = [bins[(i - 1) % 36] * 0.5 + bins[i] + bins[(i + 1) % 36] * 0.5 for i in range(36)]
    peak = max(range(36), key=lambda i: sm[i])
    # circular mean of the pixels' bins within 2 bins of the peak
    sx = sy = 0.0
    import math
    for d in range(-2, 3):
        i = (peak + d) % 36
        ang = math.radians(i * 10 + 5)
        sx += bins[i] * math.cos(ang)
        sy += bins[i] * math.sin(ang)
    return int(round(math.degrees(math.atan2(sy, sx)))) % 360


_cache = {}


def _file():
    base = Path(os.environ.get("DATA_DIR") or Path(__file__).with_name("data"))
    return base / "logo_hues.json"


def _load():
    if not _cache:
        try:
            _cache.update(json.loads(_file().read_text(encoding="utf-8")))
        except Exception:
            pass
    return _cache


def _save():
    try:
        f = _file()
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(_cache), encoding="utf-8")
        os.replace(tmp, f)
    except Exception:
        pass


def hue_for_logo(url):
    """Hue for a logo URL, remembered on the volume so each picture is downloaded once (a failed download is retried next build)."""
    if not url or Image is None:
        return None
    c = _load()
    if url in c:
        return c[url]
    try:
        r = requests.get(url, timeout=6)
        if r.status_code >= 400:
            return None
        hue = hue_of_image(Image.open(io.BytesIO(r.content)))
    except Exception:
        return None
    c[url] = hue            # None is remembered too: a gray logo stays gray
    _save()
    return hue
