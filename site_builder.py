#!/usr/bin/env python3
"""
SITE DATA + PAGE (READ-ONLY): turns the players and teams into the compact data the page reads, and drops that data
into the page files in web/ (page.html, app.css, app.js). build.py runs it; it never changes anything in ESPN.
"""
import json
import os
from pathlib import Path

import analyze as A
import dashboard as D


def r3(x):
    return None if x is None else round(float(x), 3)


def slim(p, standings):
    """Keep only what the web page needs (short keys keep the page small)."""
    d = {"id": p["id"], "n": p["name"], "pos": p["pos"], "grp": p["group"], "tm": p.get("team", "?"),
         "slot": "FA" if p.get("slot") is None else A.slot_name(p["slot"]),
         "gp": int(p["gp"]), "ppg": r3(p["ppg"]), "exp": r3(p["exp_ppg"]), "proj": r3(p["proj_ppg"]),
         "out": r3(p["outlook"]), "rec": r3(p.get("recent_ppg")), "g7": p.get("g7", 0),
         "own": r3(p.get("own")), "inj": p["injury"], "fl": p["flags"], "st": p.get("status")}
    if p["group"] == "G":
        d.update({"svp": r3(p.get("svp")), "w": int(p.get("wins", 0)), "ga": int(p.get("ga", 0)),
                  "sp": r3(D.start_prob(p, standings))})
    else:
        d.update({"g": int(p.get("g", 0)), "a": int(p.get("a", 0)), "sog": int(p.get("sog", 0)),
                  "hit": int(p.get("hit", 0)), "blk": int(p.get("blk", 0)), "ppp": int(p.get("ppp", 0)),
                  "shp": r3(p.get("sh_pct"))})
    return d


def build_site_data(cfg, data, league, standings, now_ms):
    ctx = D.build_context(cfg, data, league, standings, now_ms)
    sp = data["roster"].get("scoringPeriodId", 1)
    abbr, g7map = A.team_info(data["schedules"], sp, A.DAYS_AHEAD)
    meta = {t.get("id"): t for t in league.get("teams", [])}

    teams = []
    for t in data["roster"].get("teams", []):
        tid = t.get("id")
        players = D.roster_players(t, cfg["season"], abbr)
        for p in players:
            p["g7"] = g7map.get(p["team_id"], 0)
        m = meta.get(tid, {})
        w, l, ti, pf = D.record_of(m)
        tb = (t.get("tradeBlock") or m.get("tradeBlock") or {}).get("players") or {}
        block = [int(k) for k, v in tb.items() if v == "ON_THE_BLOCK"]      # NORMAL = not actually offered
        logo = m.get("logo") or t.get("logo") or ""
        logo = logo if isinstance(logo, str) and logo.startswith("https://") else ""   # ESPN's team picture; blank -> initials
        teams.append({"id": tid, "name": D.team_label(m) if m else f"Team {tid}", "logo": logo, "rec": f"{w}-{l}-{ti}",
                      "w": w, "pf": r3(pf), "me": tid == cfg["team"], "block": block,
                      "players": [slim(p, standings) for p in players]})

    return {
        "league": ctx["league_name"], "me": ctx["my_name"], "rec": ctx["my_rec"], "updated": ctx["updated"],
        "matchup": ctx["matchup"],
        "goalies": [{"p": slim(g["p"], standings), "rows": g["rows"]} for g in ctx["goalies"]],
        "moves": [{"add": slim(m["add"], standings), "drop": slim(m["drop"], standings),
                   "gain": r3(m["gain"]), "wk": r3(m["week_gain"])} for m in ctx["moves"]],
        "alerts": [{"k": k, "t": t} for k, t in ctx["alerts"]],
        "mine": [slim(p, standings) for p in ctx["mine"]],
        "fas": [slim(p, standings) for p in ctx["fas"]],
        "teams": teams,
    }


WEB = Path(os.environ.get("FH_WEB_DIR") or Path(__file__).with_name("web"))


def _web():
    return tuple((WEB / f).read_text(encoding="utf-8") for f in ("page.html", "app.css", "app.js"))


def render_site(site_data):
    """One self-contained page (styles, script and data inline). Used by the test tools (replay, compare, smoke)."""
    page, css, js = _web()
    blob = json.dumps(site_data, separators=(",", ":"), ensure_ascii=True).replace("</", "<\\/")
    return page.replace("__CSS__", css).replace("__JS__", js).replace("__DATA__", blob)


# The published app is split in two so it opens instantly and updates itself:
#   - the app (index.html + app.<code>.js/.css): changes only when the code changes. The phone keeps it, so it opens
#     straight away. The file names carry a fingerprint of the code, so a new version is never mixed with an old one.
#   - the data (data.json): changes with every build.
#   - version.json says which code and which data are live. The open app checks it every 15 s and when it comes back to
#     the screen, and reloads itself (keeping your tab and scroll) when either changed. Just before that reload it puts the
#     data the new page needs in sessionStorage ('fh_pre'); the loader below uses it, so the reload needs no network.
LOADER = r"""<script>window.FH_CODE='__CODE__';(function(){
var el=document.getElementById('data');
function boot(txt){el.textContent=txt;var s=document.createElement('script');s.src='app.__CODE__.js';document.body.appendChild(s);}
function fail(){var w=document.querySelector('.wrap');if(w)w.insertAdjacentHTML('afterbegin','<div class="card" style="margin:12px 0">Could not load the latest data. Check your signal, then <a href="" onclick="location.reload();return false">try again</a>.</div>');}
var pre=null;try{pre=sessionStorage.getItem('fh_pre');sessionStorage.removeItem('fh_pre');}catch(e){}
if(pre){boot(pre);return;}
var tries=0;(function go(){fetch('data.json?t='+Date.now(),{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error(r.status);return r.text();}).then(boot).catch(function(){if(++tries<3)setTimeout(go,800*tries);else fail();});})();
})();</script>"""


def code_version():
    """A short fingerprint of the app code: changes whenever page.html, app.css or app.js changes."""
    import hashlib
    page, css, js = _web()
    return hashlib.sha1((page + "\0" + css + "\0" + js + "\0" + LOADER).encode("utf-8")).hexdigest()[:10]


def write_shell(out="site"):
    """index.html + app.<code>.js/.css (no data). Returns the code version."""
    page, css, js = _web()
    code = code_version()
    out = Path(out)
    out.mkdir(exist_ok=True)
    for old in list(out.glob("app.*.js")) + list(out.glob("app.*.css")):
        old.unlink()
    (out / f"app.{code}.css").write_text(css, encoding="utf-8")
    (out / f"app.{code}.js").write_text(js, encoding="utf-8")
    shell = (page.replace("<style>__CSS__</style>", f'<link rel="stylesheet" href="app.{code}.css">')
                 .replace("__DATA__", "")
                 .replace("<script>__JS__</script>", LOADER.replace("__CODE__", code)))
    for k in ("__CSS__", "__JS__", "__DATA__"):
        if k in shell:
            raise RuntimeError(f"page.html no longer has the expected {k} slot")
    (out / "index.html").write_text(shell, encoding="utf-8")
    return code


def write_version(out="site", data_v=None):
    """version.json: the live code and data versions. data_v=None keeps the data version already in the folder."""
    out = Path(out)
    vf = out / "version.json"
    if data_v is None:
        try:
            data_v = json.loads(vf.read_text(encoding="utf-8")).get("data")
        except Exception:
            data_v = None
    v = {"code": code_version(), "data": data_v}
    vf.write_text(json.dumps(v), encoding="utf-8")
    return v


def write_site(site_data, out="site"):
    """The published app: the shell, data.json and version.json."""
    write_shell(out)
    blob = json.dumps(site_data, separators=(",", ":"), ensure_ascii=True)
    (Path(out) / "data.json").write_text(blob, encoding="utf-8")
    return write_version(out, site_data.get("v"))


if __name__ == "__main__":
    # python site_builder.py shell [site]  ->  republish just the app code next to the live data (code-only update)
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "shell":
        d = sys.argv[2] if len(sys.argv) > 2 else "site"
        write_shell(d)
        print("version:", write_version(d))
