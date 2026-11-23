#!/usr/bin/env python3
"""
ALWAYS-ON SERVER: serves the app and keeps it fresh, in place of GitHub Pages + the GitHub Actions watcher.

What it does
  - Serves the published app (index.html, app.<code>.js/.css, data.json, version.json, icons, service worker).
  - Rebuilds with the same build.py, at the same moments as scheduler.py: morning (fresh by 9 AM ET), 4 hours before
    the first puck drop, at puck drop (the add-lock), and after the last game. The decisions are scheduler.py's own;
    only "start a build" and "was it already done" are swapped for local ones.
  - Rebuilds when you open the app and the data is more than STALE_MIN minutes old (POST /api/refresh). The open app
    already polls version.json, so it reloads itself when the new data lands.
  - The Refresh button and the Keep button call the same endpoint, so no GitHub token is needed.
  - Never lets a broken build replace a good page (the same publish check as the workflow: tools/publish_gate.py).
  - Sends the morning alert after the new page is live, and a "site is not updating" alert (when SEND_ALERTS=1).

Where things live (DATA_DIR, a persistent volume in production)
  live -> sites/<time>   the page being served (swapped in one step, so a visitor never sees a half-written build)
  plan_state.json, keep.json, cache/, history/   the build's memory; the code folder's copies are links to these
  runs.json              which builds ran (scheduler.py asks this instead of GitHub's run list)

Settings (environment variables)
  ESPN_S2, SWID          ESPN login cookies (ESPN_2 also accepted, the name the GitHub secret used)
  LEAGUE_ID, TEAM_ID, SEASON   read by analyze.py (defaults are in that file)
  PUSH_CONFIG            phone push keys, same JSON as the GitHub secret
  SEND_ALERTS=1          turn on push alerts (leave off while GitHub is still sending them)
  DATA_DIR               where state lives (default ./data; use the volume path in production)
  STALE_MIN=15           rebuild on open when the data is older than this many minutes
  RESEED_STATE=1         one-time: replace the saved state with the copy that came with this deploy
  FH_BUILD_CMD           test hook: run this instead of build.py
"""
import gzip
import json
import mimetypes
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

CODE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR") or CODE / "data").resolve()
PORT = int(os.environ.get("PORT", "8080"))
STALE_MIN = float(os.environ.get("STALE_MIN", "15"))
CHECK_EVERY = int(os.environ.get("CHECK_EVERY", "600"))      # seconds between scheduler checks
SETTLE_S = int(os.environ.get("SETTLE_S", "600"))            # post-game builds wait for final stats to settle
BUILD_TIMEOUT = int(os.environ.get("BUILD_TIMEOUT", "1200"))
STALE_ALERT_H = 14
SEND_ALERTS = os.environ.get("SEND_ALERTS", "") == "1"
BUILD_CMD = shlex.split(os.environ.get("FH_BUILD_CMD", "")) or [sys.executable, str(CODE / "build.py")]
PERSIST = ("plan_state.json", "keep.json", "cache", "history")
LIVE = DATA / "live"
RUNS = DATA / "runs.json"

LOCK = threading.Lock()
ST = {"building": None, "queued": None, "last_start": 0.0, "last_error": None, "alerted_day": None}
GZ = {}


def log(msg):
    print(f"[server {datetime.now():%m-%d %H:%M:%S}] {msg}", flush=True)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


# ---------------------------------------------------------------- state on the volume
def seed_state():
    """The build keeps its memory in files next to the code. Move them onto the volume and leave links behind."""
    DATA.mkdir(parents=True, exist_ok=True)
    reseed = os.environ.get("RESEED_STATE") == "1"
    for name in PERSIST:
        src, dst = CODE / name, DATA / name
        if src.is_symlink():
            continue
        if src.exists() and (reseed or not dst.exists()):
            if dst.is_dir():
                shutil.rmtree(dst)
            elif dst.exists():
                dst.unlink()
            shutil.copytree(src, dst) if src.is_dir() else shutil.copy2(src, dst)
            log(f"state: {name} {'replaced from this deploy' if reseed else 'seeded from this deploy'}")
        if name in ("cache", "history"):
            dst.mkdir(exist_ok=True)
        if src.is_dir():
            shutil.rmtree(src)
        elif src.exists():
            src.unlink()
        src.symlink_to(dst)


def load_runs():
    return read_json(RUNS, []) or []


def save_runs(runs):
    tmp = RUNS.with_suffix(".tmp")
    tmp.write_text(json.dumps(runs[-200:]), encoding="utf-8")
    os.replace(tmp, RUNS)


def live_dir():
    try:
        return LIVE.resolve() if LIVE.exists() else None
    except OSError:
        return None


def data_age_min():
    d = live_dir()
    if not d:
        return None
    at = (read_json(d / "health.json", {}) or {}).get("at")
    if not at:
        v = (read_json(d / "version.json", {}) or {}).get("data")
        at = v
    if not at:
        at = (d / "index.html").stat().st_mtime * 1000
    return max(0.0, (time.time() * 1000 - at) / 60000)


# ---------------------------------------------------------------- phone alerts (server-managed)
def _b64u(b):
    import base64
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def vapid():
    """Alert keys live on the volume. Made once, so phones never need a pasted code."""
    f = DATA / "vapid.json"
    try:
        v = json.loads(f.read_text(encoding="utf-8"))
        if v.get("private") and v.get("public"):
            return v
    except Exception:
        pass
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    k = ec.generate_private_key(ec.SECP256R1())
    raw = k.private_numbers().private_value.to_bytes(32, "big")
    pub = k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    v = {"private": _b64u(raw), "public": _b64u(pub)}
    f.write_text(json.dumps(v), encoding="utf-8")
    return v


def load_subs():
    try:
        return json.loads((DATA / "subs.json").read_text(encoding="utf-8"))
    except Exception:
        return []


def add_sub(sub):
    if not isinstance(sub, dict) or not str(sub.get("endpoint", "")).startswith("https://") \
            or not isinstance(sub.get("keys"), dict):
        return False
    with LOCK:
        old = {s.get("endpoint"): s for s in load_subs()}
        welcomed = bool(old.get(sub["endpoint"], {}).get("welcomed"))
        subs = [s for s in old.values() if s.get("endpoint") != sub["endpoint"]]
        subs.append({"endpoint": sub["endpoint"], "keys": sub["keys"], "welcomed": welcomed})
        (DATA / "subs.json").write_text(json.dumps(subs[-20:]), encoding="utf-8")
    log(f"phone linked for alerts ({len(subs[-20:])} total)")
    if not welcomed:
        threading.Thread(target=welcome, args=(sub["endpoint"],), daemon=True).start()
    return True


def welcome(endpoint):
    """One confirmation push per phone, so you know alerts really work."""
    try:
        f = DATA / "welcome.json"
        f.write_text(json.dumps({"title": "Alerts are on", "body": "Your daily Fantasy Hockey alerts will show up here.",
                                 "url": "./", "tag": "fh-welcome"}), encoding="utf-8")
        env = push_env()
        cfg = json.loads(env["PUSH_CONFIG"])
        cfg["subscriptions"] = [x for x in cfg["subscriptions"] if x.get("endpoint") == endpoint]
        env["PUSH_CONFIG"] = json.dumps(cfg)
        r = subprocess.run([sys.executable, str(CODE / "notify.py"), str(f)], cwd=CODE, timeout=60, env=env,
                           capture_output=True, text=True)
        log("welcome push: " + (r.stdout.strip().splitlines() or ["no output"])[-1][:160])
        with LOCK:
            subs = load_subs()
            for x in subs:
                if x.get("endpoint") == endpoint:
                    x["welcomed"] = True
            (DATA / "subs.json").write_text(json.dumps(subs), encoding="utf-8")
    except Exception as e:
        log(f"welcome push failed: {e}")


def push_env():
    env = dict(os.environ)
    subs = load_subs()
    if subs:
        env["PUSH_CONFIG"] = json.dumps({"vapid_private": vapid()["private"], "subscriptions": subs})
    return env


# ---------------------------------------------------------------- building
def notify(payload_file):
    if not SEND_ALERTS:
        log("alert skipped (SEND_ALERTS is off)")
        return
    try:
        subprocess.run([sys.executable, str(CODE / "notify.py"), str(payload_file)], cwd=CODE, timeout=120, env=push_env())
    except Exception as e:
        log(f"alert failed: {e}")


def alert(title, body, tag="fh-health"):
    f = DATA / "alert.json"
    f.write_text(json.dumps({"title": title, "body": body, "url": "./", "tag": tag}), encoding="utf-8")
    notify(f)


def gate(site):
    """(publish?, reason) using the same rule as the workflow's publish check."""
    sys.path.insert(0, str(CODE / "tools"))
    import publish_gate as G
    new = read_json(site / "health.json")
    if new is None:
        return True, "no health file from the build", None
    ld = live_dir()
    live = read_json(ld / "health.json") if ld else None
    publish, why = G.decide(new, live if G.degraded(new) else None, int(time.time() * 1000))
    if not publish:
        held = {"title": "Fantasy Hockey: kept the last good update",
                "body": f"The latest update was missing {G.what_failed(new)}, so the app is still showing the earlier "
                        "one. It will try again at the next scheduled update.", "url": "./", "tag": "fh-health"}
        return False, why, held
    return True, why, None


def publish(site):
    sites = DATA / "sites"
    sites.mkdir(exist_ok=True)
    dest = sites / str(int(time.time() * 1000))
    shutil.move(str(site), str(dest))
    tmp = DATA / ".live_tmp"
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    tmp.symlink_to(dest)
    os.replace(tmp, LIVE)                      # one atomic step: visitors get the old page or the new one, never a mix
    GZ.clear()
    for old in sorted(sites.iterdir(), key=lambda p: p.name)[:-3]:
        shutil.rmtree(old, ignore_errors=True)


def do_build(reason, keep):
    work = DATA / "work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    env = dict(os.environ)
    if not env.get("ESPN_S2") and env.get("ESPN_2"):
        env["ESPN_S2"] = env["ESPN_2"]
    env["FH_KEEP"] = keep or ""
    env["FH_RECORD"] = str(work / "snapshot.json.gz")
    t0 = time.time()
    log(f"build start: {reason}")
    with open(work / "build.log", "w", encoding="utf-8") as f:
        try:
            r = subprocess.run(BUILD_CMD, cwd=work, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=BUILD_TIMEOUT)
            code = r.returncode
        except subprocess.TimeoutExpired:
            code = -9
    tail = (work / "build.log").read_text(encoding="utf-8", errors="replace")[-1500:]
    shutil.copyfile(work / "build.log", DATA / "last_build.log")
    site = work / "site"
    if code != 0 or not (site / "index.html").exists():
        ST["last_error"] = f"{reason}: build failed (exit {code})"
        log(f"build FAILED ({code}) after {time.time() - t0:.0f}s\n{tail}")
        return False
    ok, why, held = gate(site)
    if not ok:
        ST["last_error"] = f"{reason}: held back ({why})"
        log(f"HELD BACK: {why}")
        if held:
            f2 = DATA / "held_alert.json"
            f2.write_text(json.dumps(held), encoding="utf-8")
            notify(f2)
        return True
    payload = work / "notify_payload.json"
    keep_payload = DATA / "notify_payload.json"
    if payload.exists():
        shutil.copyfile(payload, keep_payload)
    if (work / "snapshot.json.gz").exists():
        shutil.copyfile(work / "snapshot.json.gz", DATA / "last_snapshot.json.gz")
    publish(site)
    ST["last_error"] = None
    log(f"build published in {time.time() - t0:.0f}s: {reason} ({why})")
    if reason.startswith("morning") and keep_payload.exists():
        notify(keep_payload)
    return True


def _build_thread(reason, keep):
    ok = False
    try:
        if reason.startswith("post-game") and SETTLE_S:
            time.sleep(SETTLE_S)
        ok = do_build(reason, keep)
    except Exception as e:
        ST["last_error"] = f"{reason}: {type(e).__name__}: {e}"
        log(f"build crashed: {type(e).__name__}: {e}")
    with LOCK:
        runs = load_runs()
        runs.append({"reason": reason, "ok": ok, "at": int(time.time())})
        save_runs(runs)
        ST["building"] = None
        nxt, ST["queued"] = ST["queued"], None
    if nxt:
        request_build(*nxt)


def request_build(reason, keep=""):
    """Start a build, or queue it (one slot) if one is running. Returns 'started' or 'queued'."""
    with LOCK:
        if ST["building"]:
            ST["queued"] = (reason, keep or "")
            return "queued"
        ST["building"] = reason
        ST["last_start"] = time.time()
    threading.Thread(target=_build_thread, args=(reason, keep or ""), daemon=True).start()
    return "started"


def request_refresh(reason, keep, force):
    """The app asked for fresh data (on open, the Refresh button, the Keep button)."""
    age = data_age_min()
    label = f"{reason or 'on-open'} {datetime.now():%Y-%m-%d %H:%M}"
    if keep is not None:                                        # a Keep tap must never be dropped: queue it if needed
        return {"state": request_build(label, keep), "age_min": age}
    with LOCK:
        if ST["building"]:
            return {"state": "building", "age_min": age}
        since = (time.time() - ST["last_start"]) / 60
    wanted = force or age is None or age >= STALE_MIN
    if not wanted:
        return {"state": "fresh", "age_min": age}
    if since < (1.0 if force else STALE_MIN / 3):
        return {"state": "recent", "age_min": age}              # one was just tried: do not hammer ESPN
    request_build(label)
    return {"state": "started", "age_min": age}


def status():
    with LOCK:
        b = ST["building"]
    age = data_age_min()
    return {"ok": True, "building": bool(b), "age_min": None if age is None else round(age, 1),
            "has_site": live_dir() is not None, "last_error": ST["last_error"]}


# ---------------------------------------------------------------- scheduler.py, run locally
def sched_titles():
    with LOCK:
        t = [f"Daily ({r['reason']})" for r in load_runs() if r.get("ok")]
        if ST["building"]:
            t.append(f"Daily ({ST['building']})")
        if ST["queued"]:
            t.append(f"Daily ({ST['queued'][0]})")
    return t


def sched_start(reason):
    log(f"scheduler: {reason} -> {request_build(reason)}")


def stale_alert():
    age = data_age_min()
    now = datetime.now()
    if age is None or age < STALE_ALERT_H * 60 or not (9 <= now.hour <= 21) or ST["alerted_day"] == now.date():
        return
    ST["alerted_day"] = now.date()
    alert("Fantasy Hockey: site is not updating",
          f"The site has not updated in {age / 60:.0f} hours. ESPN login cookies may have expired; "
          "check the server logs.")


FRESH_MIN = float(os.environ.get("FRESH_MIN") or 20)


def keep_fresh():
    """Waking hours: rebuild in the background when the data is older than FRESH_MIN, so opening the app is instant."""
    from zoneinfo import ZoneInfo
    hr = datetime.now(ZoneInfo("America/New_York")).hour
    if hr < 7 and hr >= 1:                        # sleep 1am-7am ET
        return
    age = data_age_min()
    with LOCK:
        if ST["building"] or ST["queued"]:
            return
        since = (time.time() - ST["last_start"]) / 60
    if (age is None or age >= FRESH_MIN) and since >= FRESH_MIN / 2:
        log(f"keep-fresh: data is {age if age is None else round(age)} min old -> {request_build('auto-fresh')}")


def code_changed():
    """True when the deployed code differs from the code that made the live site (stamp kept on the volume)."""
    import hashlib
    h = hashlib.sha1()
    for p in sorted(list(CODE.glob("*.py")) + list((CODE / "web").glob("*")) + list((CODE / "tools").glob("*.py"))):
        if p.is_file():
            h.update(p.name.encode())
            h.update(p.read_bytes())
    stamp, f = h.hexdigest(), DATA / "code_stamp.txt"
    try:
        same = f.read_text().strip() == stamp
    except Exception:
        same = False
    f.write_text(stamp)
    return not same


def loop():
    import scheduler
    scheduler.build_titles, scheduler.start = sched_titles, sched_start
    time.sleep(15)
    if not live_dir():
        request_build("boot")
    elif code_changed():                          # a new version was deployed: rebuild so the new app code goes live
        request_build("new version")
    while True:
        try:
            scheduler.main()
        except Exception as e:                    # a bad check never stops the loop
            log(f"scheduler check failed: {type(e).__name__}: {e}")
        try:
            keep_fresh()
        except Exception as e:
            log(f"keep-fresh check failed: {e}")
        try:
            stale_alert()
        except Exception as e:
            log(f"stale check failed: {e}")
        time.sleep(CHECK_EVERY)


# ---------------------------------------------------------------- web
TEXT = {".html", ".js", ".css", ".json", ".webmanifest", ".svg"}
WAIT = (b"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        b"<meta http-equiv=refresh content=10><body style='font-family:-apple-system,sans-serif;padding:40px;"
        b"background:#0b1d3a;color:#fff'><h2>Building the first update...</h2><p>This takes about a minute.</p>")


class Handler(BaseHTTPRequestHandler):
    server_version = "FantasyHockey"

    def log_message(self, *a):
        pass

    def send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, obj, code=200):
        self.send(code, json.dumps(obj).encode(), "application/json", {"Cache-Control": "no-store"})

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        route = urlparse(self.path).path
        if route not in ("/api/refresh", "/api/subscribe"):
            return self.json({"error": "not found"}, 404)
        try:
            n = min(int(self.headers.get("Content-Length") or 0), 4096)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            body = {}
        if route == "/api/subscribe":
            return self.json({"ok": add_sub(body)})
        keep = body.get("keep")
        keep = None if keep in (None, "") else str(keep)[:300]
        self.json(request_refresh(str(body.get("reason") or "")[:40], keep, bool(body.get("force"))))

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/status":
            return self.json(status())
        if path == "/api/push":
            return self.json({"key": vapid()["public"]})
        if path.startswith("/api/"):
            return self.json({"error": "not found"}, 404)
        root = live_dir()
        if not root:
            return self.send(503, WAIT, "text/html; charset=utf-8", {"Cache-Control": "no-store", "Retry-After": "10"})
        rel = path.lstrip("/") or "index.html"
        if rel.endswith("/"):
            rel += "index.html"
        f = (root / rel).resolve()
        if root not in f.parents or not f.is_file():
            return self.send(404, b"Not found", "text/plain")
        ext = f.suffix.lower()
        ctype = {".webmanifest": "application/manifest+json", ".js": "text/javascript"}.get(ext) \
            or mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        if ext in (".html", ".css", ".json"):
            ctype += "; charset=utf-8"
        immutable = f.name.startswith("app.") or ext == ".png"
        h = {"Cache-Control": "public, max-age=31536000, immutable" if immutable else "no-cache"}
        body = f.read_bytes()
        if ext in TEXT and "gzip" in (self.headers.get("Accept-Encoding") or "") and len(body) > 1024:
            key = (str(f), len(body))
            if key not in GZ:
                GZ[key] = gzip.compress(body, 6)
            body, h["Content-Encoding"], h["Vary"] = GZ[key], "gzip", "Accept-Encoding"
        self.send(200, body, ctype, h)


def main():
    seed_state()
    threading.Thread(target=loop, daemon=True).start()
    log(f"serving on port {PORT}; data in {DATA}; alerts {'on' if SEND_ALERTS else 'OFF'}")
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
