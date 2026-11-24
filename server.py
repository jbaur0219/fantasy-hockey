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
  - Sends the morning alert after the new page is live, a reminder with the pre-game build when today's planned moves
    are still not made, and a "site is not updating" alert (when SEND_ALERTS=1).

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
  STALE_MIN=25           rebuild on open when the data is older than this many minutes (the background keeps it
                         under ~21 minutes from 7 AM to 1 AM ET, so this mostly matters overnight)
  FRESH_MIN=20           background rebuild when the data is older than this (checked every minute)
  RESEED_STATE=1         one-time: replace the saved state with the copy that came with this deploy
  FH_BUILD_CMD           test hook: run this instead of build.py
  OWNER_USER, OWNER_PASSWORD   the owner account, made (or its password updated) on boot; see auth.py
  AUTH=1                 require sign-in for the app, its data and every API. Off (the default) the app works as
                         before; only the owner pages (/admin/backtest, /admin/lifetime) need sign-in.
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

import auth as AUTHM

CODE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR") or CODE / "data").resolve()
PORT = int(os.environ.get("PORT", "8080"))
STALE_MIN = float(os.environ.get("STALE_MIN", "25"))
CHECK_EVERY = int(os.environ.get("CHECK_EVERY", "600"))      # seconds between scheduler checks
TICK = int(os.environ.get("TICK", "60"))                     # seconds between keep-fresh / alert checks
SETTLE_S = int(os.environ.get("SETTLE_S", "600"))            # post-game builds wait for final stats to settle
BUILD_TIMEOUT = int(os.environ.get("BUILD_TIMEOUT", "1200"))
STALE_ALERT_H = 14
SEND_ALERTS = os.environ.get("SEND_ALERTS", "") == "1"
AUTH_ON = os.environ.get("AUTH", "") == "1"
AU = AUTHM.Auth(DATA)
BUILD_CMD = shlex.split(os.environ.get("FH_BUILD_CMD", "")) or [sys.executable, str(CODE / "build.py")]
PERSIST = ("plan_state.json", "keep.json", "cache", "history")
LIVE = DATA / "live"
RUNS = DATA / "runs.json"

LOCK = threading.Lock()
PUB = threading.RLock()                     # one publish at a time (full builds and quick app-code updates)
ST = {"building": None, "queued": None, "pending": {}, "last_start": 0.0, "last_error": None, "alerted_day": None,
      "login": False, "login_alert_day": None, "held_alert_at": 0.0, "morning_at": 0.0, "reminded_day": None}
GZ = {}
ET = None


def et_now():
    global ET
    if ET is None:
        from zoneinfo import ZoneInfo
        ET = ZoneInfo("America/New_York")
    return datetime.now(ET)


def log(msg):
    print(f"[server {et_now():%m-%d %H:%M:%S} ET] {msg}", flush=True)


def write_atomic(path, text):
    """Write a whole file or nothing: a crash halfway never leaves a broken file behind (phones, alert key, runs)."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


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
    write_atomic(RUNS, json.dumps(runs[-200:]))


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
    write_atomic(f, json.dumps(v))
    log("made a new alert key (phones re-link by themselves the next time the app opens)")
    return v


def load_subs():
    try:
        return json.loads((DATA / "subs.json").read_text(encoding="utf-8"))
    except Exception:
        return []


def add_sub(sub, user=None):
    if not isinstance(sub, dict) or not str(sub.get("endpoint", "")).startswith("https://") \
            or not isinstance(sub.get("keys"), dict) or len(sub["endpoint"]) > 1000:
        return False
    with LOCK:
        old = {s.get("endpoint"): s for s in load_subs()}
        welcomed = bool(old.get(sub["endpoint"], {}).get("welcomed"))
        subs = [s for s in old.values() if s.get("endpoint") != sub["endpoint"]]
        row = {"endpoint": sub["endpoint"], "keys": {k: str(v)[:200] for k, v in sub["keys"].items()
                                                     if k in ("p256dh", "auth")}, "welcomed": welcomed}
        if user:
            row["user"] = user                   # whose phone (alerts are still the owner's league for everyone)
        subs.append(row)
        write_atomic(DATA / "subs.json", json.dumps(subs[-20:]))
    log(f"phone linked for alerts ({len(subs[-20:])} total)")
    if not welcomed:
        threading.Thread(target=welcome, args=(sub["endpoint"],), daemon=True).start()
    return True


def welcome(endpoint):
    """One confirmation push per phone, so you know alerts really work."""
    try:
        f = DATA / f"welcome-{abs(hash(endpoint)) % 10**8}.json"
        write_atomic(f, json.dumps({"title": "Alerts are on", "body": "Your daily Fantasy Hockey alerts will show up here.",
                                 "url": "./", "tag": "fh-welcome"}), encoding="utf-8")
        env = push_env()
        cfg = json.loads(env["PUSH_CONFIG"])
        cfg["subscriptions"] = [x for x in cfg["subscriptions"] if x.get("endpoint") == endpoint]
        env["PUSH_CONFIG"] = json.dumps(cfg)
        r = subprocess.run([sys.executable, str(CODE / "notify.py"), str(f)], cwd=CODE, timeout=60, env=env,
                           capture_output=True, text=True)
        log("welcome push: " + (r.stdout.strip().splitlines() or ["no output"])[-1][:160])
        f.unlink(missing_ok=True)
        with LOCK:
            subs = load_subs()
            for x in subs:
                if x.get("endpoint") == endpoint:
                    x["welcomed"] = True
            write_atomic(DATA / "subs.json", json.dumps(subs))
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
    write_atomic(f, json.dumps({"title": title, "body": body, "url": "./", "tag": tag}))
    notify(f)


LOGIN_SIGNS = ("rejected your login cookies", "Missing login cookies")


def login_failed(tail):
    """ESPN turned the cookies down: builds cannot work until ESPN_S2 / SWID are replaced in Railway."""
    if not any(x in tail for x in LOGIN_SIGNS):
        return
    ST["login"] = True
    ST["last_error"] = "ESPN sign-in expired: update ESPN_S2 and SWID in Railway Variables"
    day = et_now().date()
    if ST["login_alert_day"] != day:
        ST["login_alert_day"] = day
        alert("Fantasy Hockey: ESPN sign-in expired",
              "Updates are paused. Copy fresh ESPN_S2 and SWID cookies into Railway (Variables). "
              "The app keeps showing the last update until then.")


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
    with PUB:
        _publish(site)


def _publish(site):
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
    if HOT["web"]:
        env["FH_WEB_DIR"] = str(HOT["web"])
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
        login_failed(tail)
        return False
    ST["login"] = False
    ok, why, held = gate(site)
    if not ok:
        ST["last_error"] = f"{reason}: held back ({why})"
        log(f"HELD BACK: {why}")
        if held and time.time() - ST["held_alert_at"] > 6 * 3600:     # say it once, not at every retry
            ST["held_alert_at"] = time.time()
            f2 = DATA / "held_alert.json"
            write_atomic(f2, json.dumps(held))
            notify(f2)
        return True
    payload = work / "notify_payload.json"
    keep_payload = DATA / "notify_payload.json"
    if payload.exists():
        shutil.copyfile(payload, keep_payload)
    reminder = work / "reminder_payload.json"
    keep_reminder = DATA / "reminder_payload.json"
    if reminder.exists():
        shutil.copyfile(reminder, keep_reminder)
    elif keep_reminder.exists():
        keep_reminder.unlink()                    # nothing left to do today
    if (work / "snapshot.json.gz").exists():
        shutil.copyfile(work / "snapshot.json.gz", DATA / "last_snapshot.json.gz")
    publish(site)
    ST["last_error"] = None
    log(f"build published in {time.time() - t0:.0f}s: {reason} ({why})")
    try:                                          # the app code changed while this build ran: put the newest code on top
        shell_update("caught up after a build")
    except Exception as e:
        log(f"shell update after build failed: {e}")
    if reason.startswith("morning") and keep_payload.exists():
        notify(keep_payload)
        ST["morning_at"] = time.time()
    elif reason.startswith("pre-game") and keep_reminder.exists():
        day = et_now().date()
        # once a day, a few hours before puck drop, only for moves still not made (made moves drop off the plan);
        # skipped when the morning alert went out in the last 90 minutes (early games: it would say the same thing)
        if ST["reminded_day"] != day and time.time() - ST["morning_at"] > 90 * 60:
            ST["reminded_day"] = day
            notify(keep_reminder)
            log("move reminder sent")
    return True


def _build_thread(reason, keep):
    ok = False
    try:
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
        request_build(nxt[0], nxt[1], settle=False)          # a queued post-game build has already waited


SCHEDULED = ("morning", "pre-game", "post-game", "lock")


def _merge(old, new):
    """One waiting slot, but nothing important is lost: the newest Keep list always survives, and a scheduled build's
    name (which decides the morning alert and tells the scheduler it ran) beats an on-open or background one."""
    if not old:
        return new
    reason = old[0] if old[0].startswith(SCHEDULED) and not new[0].startswith(SCHEDULED) else new[0]
    return (reason, new[1] or old[1])


def request_build(reason, keep="", settle=True):
    """Start a build, or queue it if one is running. Returns 'started', 'queued' or 'waiting'.
    Post-game builds wait SETTLE_S for final stats without holding the build slot, so Keep taps and refreshes in the
    meantime still run right away."""
    if settle and SETTLE_S and reason.startswith("post-game"):
        with LOCK:
            if reason in ST["pending"]:
                return "waiting"
            ST["pending"][reason] = time.time()
        threading.Timer(SETTLE_S, _settled, args=(reason,)).start()
        return "waiting"
    with LOCK:
        if ST["building"]:
            ST["queued"] = _merge(ST["queued"], (reason, keep or ""))
            return "queued"
        ST["building"] = reason
        ST["last_start"] = time.time()
    threading.Thread(target=_build_thread, args=(reason, keep or ""), daemon=True).start()
    return "started"


def _settled(reason):
    with LOCK:
        ST["pending"].pop(reason, None)
    log(f"stats settled: {reason} -> {request_build(reason, settle=False)}")


def request_refresh(reason, keep, force):
    """The app asked for fresh data (on open, the Refresh button, the Keep button)."""
    age = data_age_min()
    label = f"{reason or 'on-open'} {datetime.now():%Y-%m-%d %H:%M}"
    if keep is not None:                                        # a Keep tap must never be dropped: queue it if needed
        return {"state": request_build(label, keep, settle=False), "age_min": age}
    with LOCK:
        if ST["building"]:
            return {"state": "building", "age_min": age}
        since = (time.time() - ST["last_start"]) / 60
    wanted = force or age is None or age >= STALE_MIN
    if not wanted:
        return {"state": "fresh", "age_min": age}
    if since < (1.0 if force else STALE_MIN / 3) or (ST["login"] and not force and since < 60):
        return {"state": "recent", "age_min": age}              # one was just tried: do not hammer ESPN
    request_build(label)
    return {"state": "started", "age_min": age}


def status():
    with LOCK:
        b = ST["building"]
    age = data_age_min()
    return {"ok": True, "building": bool(b), "age_min": None if age is None else round(age, 1),
            "has_site": live_dir() is not None, "last_error": ST["last_error"], "login_expired": ST["login"]}


# ---------------------------------------------------------------- scheduler.py, run locally
def sched_titles():
    with LOCK:
        t = [f"Daily ({r['reason']})" for r in load_runs() if r.get("ok")]
        if ST["building"]:
            t.append(f"Daily ({ST['building']})")
        if ST["queued"]:
            t.append(f"Daily ({ST['queued'][0]})")
        t += [f"Daily ({r})" for r in ST["pending"]]
    return t


def sched_start(reason):
    log(f"scheduler: {reason} -> {request_build(reason)}")


def stale_alert():
    age = data_age_min()
    now = et_now()                                # Eastern time: the server's own clock is UTC
    if age is None or age < STALE_ALERT_H * 60 or not (9 <= now.hour <= 21) or ST["alerted_day"] == now.date():
        return
    ST["alerted_day"] = now.date()
    if ST["login"]:
        return                                    # the sign-in alert already said why
    alert("Fantasy Hockey: app is not updating",
          f"The app has not updated in {age / 60:.0f} hours. The latest error: {ST['last_error'] or 'none recorded'}. "
          "Check the Railway logs.")


FRESH_MIN = float(os.environ.get("FRESH_MIN") or 20)


def keep_fresh():
    """Waking hours: rebuild in the background when the data is older than FRESH_MIN, so opening the app is instant."""
    hr = et_now().hour
    if hr < 7 and hr >= 1:                        # sleep 1am-7am ET
        return
    age = data_age_min()
    with LOCK:
        if ST["building"] or ST["queued"]:
            return
        since = (time.time() - ST["last_start"]) / 60
    if ST["login"] and since < 60:                # ESPN said no: try once an hour, not every few minutes
        return
    if (age is None or age >= FRESH_MIN) and since >= FRESH_MIN / 2:
        log(f"keep-fresh: data is {age if age is None else round(age)} min old -> {request_build('auto-fresh')}")


APP_ONLY = {"server.py", "site_builder.py", "pwa.py", "notify.py", "scheduler.py", "watch.py"}


def model_changed():
    """True when the deployed model/data code differs from what made the live data (needs a full ESPN build).
    App-look changes (web/, site_builder.py, pwa.py) only need the quick shell update."""
    import hashlib
    h = hashlib.sha1()
    for p in sorted([p for p in CODE.glob("*.py") if p.name not in APP_ONLY] + list((CODE / "tools").glob("*.py"))
                    + list((CODE / "platforms").glob("*.py"))):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    stamp, f = h.hexdigest(), DATA / "model_stamp.txt"
    try:
        same = f.read_text().strip() == stamp
    except Exception:
        same = False
    write_atomic(f, stamp)
    return not same


HOT = {"web": None, "sha": None}          # web/ files pulled straight from GitHub, ahead of Railway's redeploy


def web_dir():
    return HOT["web"] or CODE / "web"


def shell_update(why):
    """Put new app code live next to the current data: no ESPN build, a second or two. The open app reloads itself."""
    import site_builder
    import pwa
    with PUB:                                     # a full build cannot go live halfway through this
        for _ in range(2):
            src = live_dir()
            if not src:
                return False
            site_builder.WEB = web_dir()
            work = DATA / "shellwork"
            shutil.rmtree(work, ignore_errors=True)
            shutil.copytree(src, work)
            before = (read_json(work / "version.json", {}) or {}).get("code")
            site_builder.write_shell(work)
            pwa.write_files(str(work))
            after = site_builder.write_version(work)["code"]
            if after == before:
                shutil.rmtree(work, ignore_errors=True)
                return False
            if live_dir() != src:                  # cannot happen while PUB is held; kept as a guard
                continue
            _publish(work)
            log(f"app code {before} -> {after} live in seconds ({why})")
            return True
    return False


REPO = os.environ.get("GH_REPO", "jbaur0219/fantasy-hockey")
HOT_EVERY = int(os.environ.get("HOT_EVERY") or 15)


def _get(url):
    from urllib.request import Request, urlopen
    return urlopen(Request(url, headers={"User-Agent": "fantasy-hockey-server"}), timeout=20).read()


def hot_loop():
    """Every few seconds: has main moved on GitHub? If its web/ files differ, put them live right away."""
    import re
    last = None
    time.sleep(20)
    while True:
        try:
            refs = _get(f"https://github.com/{REPO}.git/info/refs?service=git-upload-pack")
            m = re.search(rb"([0-9a-f]{40}) refs/heads/main", refs)
            sha = m.group(1).decode() if m else None
            if sha and sha != last:
                files = {f: _get(f"https://raw.githubusercontent.com/{REPO}/{sha}/web/{f}")
                         for f in ("page.html", "app.css", "app.js")}
                cur = web_dir()
                if any((cur / f).read_bytes() != b for f, b in files.items()):
                    d = DATA / "hotweb" / sha[:12]
                    d.mkdir(parents=True, exist_ok=True)
                    for f, b in files.items():
                        (d / f).write_bytes(b)
                    # keep the two before it: a build that started a moment ago may still be reading one of them
                    olds = sorted((p for p in (DATA / "hotweb").iterdir() if p != d), key=lambda p: p.stat().st_mtime)
                    for old in olds[:-2]:
                        shutil.rmtree(old, ignore_errors=True)
                    HOT["web"], HOT["sha"] = d, sha
                    shell_update(f"GitHub {sha[:7]}")
                last = sha
        except Exception as e:
            log(f"hot update check failed: {type(e).__name__}: {e}")
        time.sleep(HOT_EVERY)


def loop():
    import scheduler
    scheduler.build_titles, scheduler.start = sched_titles, sched_start
    time.sleep(15)
    if not live_dir():
        request_build("boot")
    elif model_changed():                         # the model changed: new data needed
        request_build("new version")
    last_sched = 0.0
    while True:
        if time.time() - last_sched >= CHECK_EVERY:
            last_sched = time.time()
            try:
                scheduler.main()
            except Exception as e:                # a bad check never stops the loop
                log(f"scheduler check failed: {type(e).__name__}: {e}")
        try:
            keep_fresh()
        except Exception as e:
            log(f"keep-fresh check failed: {e}")
        try:
            stale_alert()
        except Exception as e:
            log(f"stale check failed: {e}")
        time.sleep(TICK)


# ---------------------------------------------------------------- web
TEXT = {".html", ".js", ".css", ".json", ".webmanifest", ".svg"}
WAIT = (b"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        b"<meta http-equiv=refresh content=10><body style='font-family:-apple-system,sans-serif;padding:40px;"
        b"background:#0b1d3a;color:#fff'><h2>Getting your team ready&hellip;</h2><p>This takes about a minute. The page opens by itself when it is done.</p>")


def owner_page(name):
    """The owner's private pages (never published, never in the app): the backtest report and the track record."""
    hist = DATA / "history"
    if name == "backtest":
        p = hist / "backtest.md"
        return p.read_text(encoding="utf-8") if p.exists() else "No backtest yet: it is written by the next build."
    if name == "lifetime":
        p = hist / "lifetime.json"
        return p.read_text(encoding="utf-8") if p.exists() else "{}"
    return None


INVITE_PAGE = (b"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
               b"<meta name=color-scheme content='light dark'><body style='font:17px -apple-system,system-ui,sans-serif;"
               b"max-width:430px;margin:0 auto;padding:56px 20px'><h1 style='font-size:28px'>Invite a friend</h1>"
               b"<p>Make a one-time code (good for 7 days). They open the app, tap \"Have an invite code?\" and pick a "
               b"name and password. Everyone sees your league for now.</p><button id=b style='font:inherit;padding:12px 18px;"
               b"border:0;border-radius:12px;background:#007aff;color:#fff'>Make a code</button><p id=c "
               b"style='font:600 28px ui-monospace,monospace;margin-top:24px'></p><script>b.onclick=function(){"
               b"fetch('/api/invite',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})"
               b".then(function(r){return r.json()}).then(function(j){c.textContent=j.code||j.error})}</script>")


# Reachable without signing in even when AUTH=1: the sign-in page and its API, plus what iOS needs to put the app on the
# home screen (manifest, icons, service worker). None of these carry league data.
OPEN_PATHS = {"/login", "/api/login", "/api/signup", "/api/logout", "/api/me", "/manifest.webmanifest", "/sw.js",
              "/icon.svg"}


def is_open(path):
    return path in OPEN_PATHS or (path.endswith(".png") and "/" not in path.lstrip("/"))


class Handler(BaseHTTPRequestHandler):
    server_version = "FantasyHockey"
    protocol_version = "HTTP/1.1"                 # keep the connection open between requests (1.0 closed it every time)

    def log_message(self, *a):
        pass

    def https(self):
        return (self.headers.get("X-Forwarded-Proto") or "").lower() == "https"

    def send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.security_headers()
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
        if self.https():
            self.send_header("Strict-Transport-Security", "max-age=31536000")

    def json(self, obj, code=200, extra=None):
        self.send(code, json.dumps(obj).encode(), "application/json", dict({"Cache-Control": "no-store"}, **(extra or {})))

    # ------------------------------------------------------------ who is asking
    def client_ip(self):
        xff = self.headers.get("X-Forwarded-For")
        return xff.split(",")[-1].strip() if xff else self.client_address[0]   # last hop = added by Railway's proxy

    def token(self):
        return AUTHM.token_from(self.headers.get("Cookie"))

    def user(self):
        try:
            return AU.session(self.token())
        except Exception:
            return None

    def same_origin(self):
        """A POST must come from this app's own pages (blocks other sites posting with your cookie)."""
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            return False
        origin = self.headers.get("Origin")
        if not origin or origin == "null":
            return origin is None                 # no Origin header: not a browser cross-site request
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or ""
        return urlparse(origin).netloc == host

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        route = urlparse(self.path).path
        if route not in ("/api/refresh", "/api/subscribe", "/api/login", "/api/signup", "/api/logout", "/api/invite"):
            return self.json({"error": "not found"}, 404)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 65536:
                self.close_connection = True
                return self.json({"error": "too large"}, 413)
            body = json.loads(self.rfile.read(n) or b"{}")   # read all of it: leftovers would break the next request
            if not isinstance(body, dict):
                body = {}
        except Exception:
            body = {}
        # Checked whenever a cookie could matter: the sign-in routes, and everything once sign-in is required.
        # (With AUTH off /api/refresh and /api/subscribe stay exactly as before: open to the app, no cookie involved.)
        if (AUTH_ON or route not in ("/api/refresh", "/api/subscribe")) and not self.same_origin():
            return self.json({"error": "forbidden"}, 403)
        if route == "/api/login":
            tok, why = AU.login(str(body.get("name") or "")[:64], str(body.get("password") or "")[:200],
                                self.client_ip())
            if not tok:
                msg = "Too many tries. Wait a few minutes." if why == "slow down" else "Wrong name or password."
                return self.json({"error": msg}, 429 if why == "slow down" else 401)
            return self.json({"ok": True}, extra={"Set-Cookie": AUTHM.cookie_header(tok, self.https())})
        if route == "/api/signup":
            tok, msg = AU.signup(body.get("code"), str(body.get("name") or "")[:64],
                                 str(body.get("password") or "")[:200], self.client_ip())
            if not tok:
                return self.json({"error": msg}, 400)
            log(f"new account: {AUTHM.norm_name(body.get('name'))}")
            return self.json({"ok": True}, extra={"Set-Cookie": AUTHM.cookie_header(tok, self.https())})
        if route == "/api/logout":
            AU.logout(self.token())
            return self.json({"ok": True}, extra={"Set-Cookie": AUTHM.cookie_header("", self.https(), clear=True)})
        me = self.user()
        if route == "/api/invite":
            if not me or me["role"] != "owner":
                return self.json({"error": "owner only"}, 403)
            return self.json({"code": AU.invite(me["name"])})
        if AUTH_ON and not me:
            return self.json({"error": "sign in"}, 401)
        if route == "/api/subscribe":
            return self.json({"ok": add_sub(body, me and me["name"])})
        keep = body.get("keep")
        keep = None if keep in (None, "") else str(keep)[:300]
        self.json(request_refresh(str(body.get("reason") or "")[:40], keep, bool(body.get("force"))))

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/login":
            return self.send(200, AUTHM.LOGIN_PAGE.encode(), "text/html; charset=utf-8", {"Cache-Control": "no-store"})
        if path == "/api/me":
            me = self.user()
            return self.json({"user": me and {"name": me["name"], "role": me["role"]}, "auth": AUTH_ON})
        if path.startswith("/admin/"):
            me = self.user()
            if not me or me["role"] != "owner":
                return self.send(404, b"Not found", "text/plain")
            if path == "/admin/invite":
                return self.send(200, INVITE_PAGE, "text/html; charset=utf-8", {"Cache-Control": "no-store"})
            text = owner_page(path[len("/admin/"):])
            if text is None:
                return self.send(404, b"Not found", "text/plain")
            return self.send(200, text.encode(), "text/plain; charset=utf-8", {"Cache-Control": "no-store"})
        if AUTH_ON and not is_open(path) and not self.user():
            if path.startswith("/api/") or not (path.endswith("/") or path.endswith(".html")):
                return self.json({"error": "sign in"}, 401)
            return self.send(303, b"", "text/plain", {"Location": "/login", "Cache-Control": "no-store"})
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
        st = f.stat()
        gz_ok = ext in TEXT and "gzip" in (self.headers.get("Accept-Encoding") or "") and st.st_size > 1024
        etag = f'"{st.st_mtime_ns:x}-{st.st_size:x}{"-gz" if gz_ok else ""}"'
        h["ETag"] = etag
        if gz_ok:
            h["Vary"] = "Accept-Encoding"
        if etag in (self.headers.get("If-None-Match") or ""):    # unchanged since last time: no body to send
            self.send_response(304)
            self.security_headers()
            for k, v in h.items():
                self.send_header(k, v)
            self.end_headers()
            return
        body = f.read_bytes()
        if gz_ok:
            key = (str(f), st.st_mtime_ns, len(body))
            if key not in GZ:
                GZ[key] = gzip.compress(body, 6)
            body, h["Content-Encoding"] = GZ[key], "gzip"
        self.send(200, body, ctype, h)


def main():
    seed_state()
    try:
        owner = AU.ensure_owner(os.environ.get("OWNER_USER", ""), os.environ.get("OWNER_PASSWORD", ""))
        if owner:
            log(f"owner account ready: {owner}")
    except Exception as e:
        log(f"owner account NOT set up: {e}")
    if AUTH_ON and not AU.has_owner():
        log("AUTH=1 but there is no owner account yet: set OWNER_USER and OWNER_PASSWORD (nobody can sign in)")
    log(f"sign-in {'REQUIRED (AUTH=1)' if AUTH_ON else 'optional (owner pages only)'}")
    shutil.rmtree(DATA / "hotweb", ignore_errors=True)   # this deploy's own web/ is the starting point
    try:
        shell_update("new deploy")                # new app code live before the first visitor, no ESPN build
    except Exception as e:
        log(f"shell update failed: {e}")
    threading.Thread(target=hot_loop, daemon=True).start()
    threading.Thread(target=loop, daemon=True).start()
    log(f"serving on port {PORT}; data in {DATA}; alerts {'on' if SEND_ALERTS else 'OFF'}")
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
