#!/usr/bin/env python3
"""A real page to test the look and feel on, offline.

  python tools/qa/page.py            -> /tmp/fhqa/page.html (replays the saved ESPN snapshot once, then reuses its data)
  python tools/qa/page.py --fresh    -> replay the snapshot again (after model/data code changes)

The snapshot is the Nov 20, 2026 preview build kept in git history (commit 4e9993a, preview/snapshot.json.gz); it is
not in the working tree on purpose. Newer requests (per-day lineups, player search) are not in it, so those parts
show their "couldn't read" states. Every run re-renders the page with the CURRENT web/ code.
"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get("FHQA_DIR", "/tmp/fhqa"))
OUT.mkdir(parents=True, exist_ok=True)
SNAP, DATA, PAGE = OUT / "snapshot.json.gz", OUT / "data.json", OUT / "page.html"

if not SNAP.exists():
    SNAP.write_bytes(subprocess.run(["git", "show", "4e9993a:preview/snapshot.json.gz"], cwd=ROOT,
                                    capture_output=True, check=True).stdout)
if "--fresh" in sys.argv or not DATA.exists():
    work = OUT / "work"
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git", "__pycache__", "site"))
    subprocess.run(["sh", "tools/replay.sh", str(SNAP), "", str(OUT / "full.html")], cwd=work, check=True,
                   stdout=subprocess.DEVNULL)
    h = (OUT / "full.html").read_text(encoding="utf-8")
    DATA.write_text(re.search(r'<script type="application/json" id="data">(.*?)</script>', h, re.S).group(1))
    shutil.rmtree(work, ignore_errors=True)
sys.path.insert(0, str(ROOT))
import site_builder  # noqa: E402
site_builder.WEB = ROOT / "web"
PAGE.write_text(site_builder.render_site(json.loads(DATA.read_text().replace("<\\/", "</"))), encoding="utf-8")
print(PAGE)
