#!/usr/bin/env python3
"""Compare two built pages: the page code and the data, ignoring the build timestamp.

python tools/compare.py old.html new.html   -> prints differences (exit 1 if any)
"""
import json
import re
import sys


def split(path):
    t = open(path, encoding="utf-8").read()
    m = re.search(r'<script type="application/json" id="data">(.*?)</script>', t, re.S)
    data = json.loads(m.group(1).replace("<\\/", "</"))
    for k in ("updated",):
        data.pop(k, None)
    (data.get("clock") or {}).pop("built", None)
    return t[:m.start()] + t[m.end():], data


def walk(a, b, path, out):
    if type(a) != type(b):
        out.append(f"{path}: {str(a)[:80]} -> {str(b)[:80]}")
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append(f"{path}.{k}: {'added' if k in b else 'removed'}")
            else:
                walk(a[k], b[k], f"{path}.{k}", out)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{path}: list {len(a)} -> {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{path}[{i}]", out)
    elif a != b:
        out.append(f"{path}: {str(a)[:80]} -> {str(b)[:80]}")


if __name__ == "__main__":
    pa, da = split(sys.argv[1])
    pb, db = split(sys.argv[2])
    out = []
    if pa != pb:
        out.append(f"page code differs ({len(pa)} vs {len(pb)} chars)")
    walk(da, db, "data", out)
    print("\n".join(out[:60]) if out else "IDENTICAL (page code and data)")
    sys.exit(1 if out else 0)
