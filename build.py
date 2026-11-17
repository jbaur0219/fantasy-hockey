#!/usr/bin/env python3
"""
Builds the interactive site WITH deeper stats (NHL.com + MoneyPuck). READ-ONLY.

Run:  python3 build.py     ->  writes site/index.html

Same as site_builder.py, plus: expected goals, ice time, power-play time, goalie save-% regression,
real goalie start rates, and extra columns/flags on the page. If the extra data can't be loaded,
it falls back to the basic version automatically.
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import analyze as A
import dashboard as D
import pwa
import ui as UI
import enrich as E
import planner as PL
import roles as R
import streams2 as S2
import streams3 as S3
import streams4 as S4
import gameplan as GP
import weekplan as WK
import optimizer as OPT
import edge as EDG
import playercard as PC
import streams as STR
import site_builder as SB
import starters as S
import netcache as NC
import goalies as GL
import core as C

_base_slim = SB.slim
EXTRA = ("toi", "pp", "ixg", "gx", "xgf", "gs", "qs", "gsax", "h60", "b60", "own_chg")


def slim_plus(p, standings):
    d = _base_slim(p, standings)
    for k in EXTRA:
        if p.get(k) is not None:
            d[k] = SB.r3(p[k])
    return d


def patch_text(text, pairs, label):
    """Apply exact-match replacements. If the page code ever changes and one no longer matches, skip it."""
    for old, new in pairs:
        if text.count(old) != 1:
            print(f"  (page patch skipped in {label}: '{old[:40]}...' not found once)")
            continue
        text = text.replace(old, new)
    return text


JS_PATCHES = [
    ("var cFlags={",
     "var cTOI={h:'TOI',v:function(p){return p.toi;},num:1,fmt:function(x){return f(x,1);}};"
     "var cPP={h:'PP min',v:function(p){return p.pp;},num:1,fmt:function(x){return f(x,1);}};"
     "var cXG={h:'G vs xG',v:function(p){return p.gx;},num:1,r:function(p){return p.gx==null?'-':"
     "'<span class=\"'+(p.gx>=2?'warn':(p.gx<=-2?'good':''))+'\">'+sgn(p.gx,1)+'</span>';}};"
     "var cFlags={"),
    ("cProj,cOut,cG7,cFlags];", "cProj,cOut,cG7,cTOI,cPP,cXG,cFlags];"),
    ("cGP,cG7,{h:'Owned'", "cGP,cG7,cTOI,cPP,cXG,{h:'Owned'"),
    ("cell('Games played',p.gp)+",
     "cell('Games played',p.gp)+(p.toi!=null?cell('Ice time/gm',f(p.toi,1)+' min'):'')"
     "+(p.pp!=null?cell('PP time/gm',f(p.pp,1)+' min'):'')+(p.ixg!=null?cell('Expected goals',f(p.ixg,1)):'')"
     "+(p.gx!=null?cell('Goals vs xG',sgn(p.gx,1)):'')+(p.gsax!=null?cell('Goals saved vs exp.',sgn(p.gsax,1)):'')"
     "+(p.qs!=null?cell('Quality starts',f(p.qs*100,0)+'%'):'')+"),
]
PAGE_PATCHES = [
    ('</div><div id="modal"></div>',
     '<div class="muted" style="margin-top:22px">Data: ESPN, NHL.com, MoneyPuck.com (expected goals) and DailyFaceoff.com (starting goalies). '
     'G vs xG = goals minus expected goals: positive means finishing above expectation (may cool), negative means due to rise.</div>'
     '</div><div id="modal"></div>'),
]


LOCK_JS = r"""/* ---------- daily lock: once the first game of a day starts, nobody can be added for that day ---------- */
var LK=(function(){
  var C=D.clock||null;
  function etDate(ms){
    try{return new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(ms));}
    catch(e){return new Date(ms).toISOString().slice(0,10);}
  }
  function closed(i,now){
    if(!C)return false;
    now=now||Date.now();
    var l=C.lock[i];
    if(l)return now>=l;
    return !!C.dates[i]&&C.dates[i]<etDate(now);
  }
  function count(){var c=0;if(C)for(var i=0;i<C.dates.length;i++)if(closed(i))c++;return c;}
  function first(){if(!C)return 0;var n=C.dates.length;for(var i=0;i<n;i++)if(!closed(i))return i;return n;}
  function age(){
    if(!C||!C.built)return '';
    var m=Math.max(0,Math.round((Date.now()-C.built)/60000));
    return m<2?' (just now)':(m<90?' ('+m+' min ago)':' ('+Math.round(m/60)+' h ago)');
  }
  function bar(){
    var el=document.getElementById('lockbar');
    if(!el||!C)return;
    var n=C.dates.length,k=count(),fi=first();
    if(!k){el.innerHTML='';return;}
    var staleSince=0;
    for(var i=0;i<n;i++){if(closed(i)&&C.lock[i]&&C.lock[i]>C.built)staleSince=1;}
    var ti=C.dates.indexOf(etDate(Date.now())),started=ti>=0&&closed(ti);
    var msg=(started?'<b>Today\'s games have started, so adds are locked.</b> ':'<b>Earlier days in this matchup week are already over.</b> ')+(fi<n?'Everything below is for '+esc(C.labels[fi])+' onward.':'Every game day left in this matchup week has started.');
    if(staleSince)msg+=' <span class="muted">This page was built before puck drop. A fresh build starts automatically within about 15 minutes of the first game, and the tabs already skip the closed day.</span>';
    el.innerHTML='<div class="card" style="margin:8px 0;border-left:4px solid var(--amber)">&#128274; '+msg+'</div>';
  }
  function start(){
    bar();
    var last=count();
    setInterval(function(){
      var c=count();
      if(c===last)return;
      last=c;bar();
      try{if(typeof gameplanRender==='function')gameplanRender();}catch(e){}
      try{if(typeof streamsRender==='function')streamsRender();}catch(e){}
      try{if(typeof plannerRender==='function')plannerRender();}catch(e){}
    },30000);
  }
  return {closed:closed,count:count,first:first,age:age,bar:bar,start:start};
})();
function lkPlan(pl){
  if(!pl||!LK.count())return pl;
  var keep=function(m){return !LK.closed(m.t);};
  var c={};for(var k in pl)c[k]=pl[k];
  c.moves=(pl.moves||[]).filter(keep);
  c.hidden=(pl.moves||[]).length-c.moves.length;
  if(pl.marginal)c.marginal=pl.marginal.filter(keep);
  if(c.hidden){
    c.gain=c.moves.reduce(function(s,m){return s+m.gain;},0);
    if(pl.matchup){var mm={};for(var q in pl.matchup)mm[q]=pl.matchup[q];mm.p_win_after=null;c.matchup=mm;}
  }
  return c;
}
function lkNote(pl){
  return (pl&&pl.hidden)?'<div class="why warn" style="margin-bottom:8px">'+pl.hidden+' suggested move'+(pl.hidden===1?'':'s')+' for a day that has already started '+(pl.hidden===1?'was':'were')+' hidden. A fresh plan builds automatically shortly after puck drop.</div>':'';
}

/* ---------- tabs + startup ---------- */"""

LOCK_PATCHES = [
    ("/* ---------- tabs + startup ---------- */", LOCK_JS),
    ("showTab((location.hash||'').slice(1));", "LK.start();\nshowTab((location.hash||'').slice(1));"),
    ("+' \\u00b7 updated '+D.updated+'", "+' \\u00b7 updated '+D.updated+LK.age()+'"),
]
LOCK_PAGE = [("<noscript>", '<div id="lockbar" role="status" aria-live="polite"></div><noscript>'),
             ("<!doctype html><html>", '<!doctype html><html lang="en">'),
             ('<meta name="robots" content="noindex">', '<meta name="robots" content="noindex"><meta name="theme-color" content="#2563eb">')]
LOCK_CSS = [(".me td{font-weight:700}", ".me td{font-weight:700}td,th{font-variant-numeric:tabular-nums}"
             "button:focus-visible,a:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}")]


REFRESH_BAR = r"""<div id="rfbar" style="margin:6px 0 10px;display:flex;flex-wrap:wrap;gap:10px;align-items:center">
<button id="rfbtn" type="button" style="padding:6px 14px;border-radius:8px;border:1px solid currentColor;background:transparent;color:inherit;font:inherit;font-weight:600;cursor:pointer">&#8635; Refresh data</button>
<span id="rfmsg" class="muted" style="font-size:13px"></span>
<a id="rfforget" href="#" style="display:none;font-size:12px;opacity:.7">forget token</a></div>"""

REFRESH_JS = r"""(function(){
var OWNER='jbaur0219',REPO='fantasy-hockey',WF='daily.yml',KEY='fh_gh_token';
var btn=document.getElementById('rfbtn'),msg=document.getElementById('rfmsg'),fg=document.getElementById('rfforget');
if(!btn)return;
function tok(){try{return localStorage.getItem(KEY)||'';}catch(e){return '';}}
function setTok(v){try{if(v)localStorage.setItem(KEY,v);else localStorage.removeItem(KEY);}catch(e){}fg.style.display=tok()?'inline':'none';}
function say(t,bad){msg.textContent=t;msg.style.color=bad?'#d33':'';}
function api(path,opt){opt=opt||{};opt.headers={'Authorization':'Bearer '+tok(),'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'};return fetch('https://api.github.com/repos/'+OWNER+'/'+REPO+path,opt);}
function sleep(ms){return new Promise(function(r){setTimeout(r,ms);});}
setTok(tok());
fg.addEventListener('click',function(e){e.preventDefault();setTok('');say('Token removed from this browser.');});
var busy=false;
btn.addEventListener('click',async function(){
  if(busy)return;
  if(!tok()){
    var v=window.prompt('One-time setup: paste a GitHub token for this repo (Actions: read and write). It is saved only in this browser.\n\nCreate one at https://github.com/settings/personal-access-tokens/new');
    if(!v){say('A token is needed to start a refresh.',true);return;}
    setTok(v.trim());
  }
  busy=true;btn.disabled=true;var t0=Date.now();
  try{
    say('Starting refresh...');
    var r=await api('/actions/workflows/'+WF+'/dispatches',{method:'POST',body:JSON.stringify({ref:'main',inputs:{reason:'manual-button'}})});
    if(r.status===401||r.status===403||r.status===404){setTok('');say('GitHub rejected the token (expired or missing permission). Click again to paste a new one.',true);return;}
    if(r.status!==204){say('Could not start the refresh (HTTP '+r.status+').',true);return;}
    var run=null;
    for(var i=0;i<60;i++){
      await sleep(6000);
      var q=await api('/actions/workflows/'+WF+'/runs?event=workflow_dispatch&per_page=10');
      if(!q.ok)continue;
      var j=await q.json();
      var runs=(j.workflow_runs||[]).filter(function(x){return (x.display_title||'').indexOf('manual-button')>=0&&Date.parse(x.created_at)>=t0-60000;});
      run=runs[0]||null;
      var secs=Math.round((Date.now()-t0)/1000);
      say((run&&run.status==='in_progress'?'Building... ':'Queued... ')+secs+'s');
      if(run&&run.status==='completed')break;
    }
    if(run&&run.status==='completed'&&run.conclusion==='success'){say('Done. Reloading...');location.href=location.pathname+'?r='+Date.now()+location.hash;return;}
    if(run&&run.status==='completed'){say('The build failed. Check the Actions tab on GitHub.',true);return;}
    say('Still running after 6 minutes. Reload in a bit.',true);
  }catch(e){say('Something went wrong: '+e.message,true);}
  finally{busy=false;btn.disabled=false;}
});
})();"""


def add_refresh_button(html_text):
    """Adds a 'Refresh data' button under the page title. It asks GitHub to rebuild the site, then reloads the page."""
    marker = '<div class="sub" id="sub"></div>'
    end = html_text.rfind("</body>")
    if html_text.count(marker) != 1 or end < 0:
        print("  (refresh button skipped: page layout changed)")
        return html_text
    html_text = html_text.replace(marker, marker + REFRESH_BAR)
    end = html_text.rfind("</body>")
    return html_text[:end] + "<script>" + REFRESH_JS + "</script>" + html_text[end:]


REQUIRED = ("function gameplanRender", "function streamsRender", "function plannerRender", "function uiStart",
            "LK.start();", "function pcTag", "function wiResult", "function suggestFor", "uiToday")


def health_report(site_data, nhl_counts):
    """What data this build had, in plain English, for the badge at the top of the page and the alerts."""
    items, level = [], "ok"
    lines = R.health()
    if lines["state"] == "missing":
        level = "bad"
        items.append(lines["note"])
    elif lines["state"] != "live":
        level = "warn" if (R.STATE["cache_age_h"] or 0) > 24 or lines["state"] == "partial" else level
        items.append(lines["note"])
    if S.HEALTH["state"] in ("missing", "cached") and S.HEALTH["note"]:
        level = "warn" if level == "ok" and S.HEALTH["state"] == "missing" else level
        items.append(S.HEALTH["note"])
    sk, xg = nhl_counts
    if not sk:
        level = "bad"
        items.append("NHL.com stats could not be loaded, so projections are rougher than usual.")
    elif not xg:
        level = "warn" if level == "ok" else level
        items.append("MoneyPuck expected goals could not be loaded.")
    if not site_data.get("matchup"):
        items.append("This week's matchup was not found.")
    return {"level": level, "items": items,
            "lines": lines["state"], "starters": S.HEALTH["state"],
            "healthy_plan": lines["state"] == "live" or (lines["state"] == "cached" and (R.STATE["cache_age_h"] or 0) <= 24)}


def _no_streams_plan(*a, **k):
    return {"base": 0, "total": 0, "gain": 0, "moves": [], "marginal": []}


def _goalies(mine, sp, games, abbr, standings, now_ms):
    return GL.build(mine, sp, games, abbr, standings, now_ms, D.CUR_DAYS)


def write_notify_payload(site_data, now_ms):
    """The text of the morning push notification, for notify.py."""
    clock = site_data.get("clock")
    gp = site_data.get("gameplan") or {}
    moves = gp.get("moves") or []
    first_open = 0
    if clock:
        first_open = next((i for i in range(len(clock["lock"])) if not D.day_locked(clock, i, now_ms)), None)
    label = clock["labels"][first_open] if clock and first_open is not None else datetime.fromtimestamp(now_ms / 1000, D.et_zone()).strftime("%a %b %d")

    def line(m):
        return f"add {m['add']['n']} ({m['add']['tm']}), drop {m['drop']['n']} (+{m['gain']:.1f})"

    today = [m for m in moves if m.get("t") == first_open]
    if today:
        parts = [("Move today: " if len(today) == 1 else "Moves today: ") + "; ".join(line(m) for m in today[:2]) + "."]
    elif moves:
        nxt = moves[0]
        parts = [f"No move needed today. Next: {nxt['day']}, {line(nxt)}."]
    else:
        parts = ["No add is worth a move today."]
    m = site_data.get("matchup")
    if m:
        parts.append(f"Win chance {m['p_win'] * 100:.0f}%.")
    if gp.get("moves_left") is not None:
        parts.append(f"{gp['moves_left']} moves left.")
    h = site_data.get("health") or {}
    if h.get("level") == "bad":
        parts.append("Warning: " + " ".join(h.get("items", [])[:1]))
    payload = {"title": f"Fantasy Hockey \u00b7 {label}", "body": " ".join(parts), "url": "./", "tag": "fh-daily"}
    Path("notify_payload.json").write_text(json.dumps(payload), encoding="utf-8")
    print(f"  alert text: {payload['title']} | {payload['body']}")


def main():
    NC.install()
    try:
        _main()
    finally:
        NC.save()


def _main():
    cfg = A.get_config()
    print("Reading your ESPN league...")
    data = A.fetch_all(cfg)
    base = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{cfg['season']}"
    league = A.espn_get(f"{base}/segments/0/leagues/{cfg['league']}", cfg["cookies"],
                        params=[("view", "mSettings"), ("view", "mTeam"),
                                ("view", "mMatchup"), ("view", "mMatchupScore")])
    standings = D.load_nhl_standings()
    abbr, _ = D.schedule_maps(data["schedules"])

    planner_on = streams_on = v3_ok = gp_on = False
    nhl_counts = (0, 0)
    print("Loading deeper stats...")
    try:
        nhl = E.load(cfg["season"])
        nhl_counts = (len(nhl["sk"]), sum(1 for d in nhl["sk"].values() if "ixg" in d))
        if nhl["sk"] or nhl["gk"]:
            E.install(nhl, abbr)
            SB.slim = slim_plus
            SB.JS = patch_text(SB.JS, JS_PATCHES, "page script")
            SB.PAGE = patch_text(SB.PAGE, PAGE_PATCHES, "page layout")
            try:
                S.install(S.load())
            except Exception as e:
                print(f"  starting goalies skipped ({type(e).__name__}: {e})")
            SB.JS, SB.PAGE, SB.CSS, planner_on = PL.patch_all(SB.JS, SB.PAGE, SB.CSS)
            SB.JS, SB.PAGE, SB.CSS, streams_on = STR.patch_all(SB.JS, SB.PAGE, SB.CSS)
            try:
                R.install(R.load(set(abbr.values())), abbr)
                print(" ", R.summary())
            except Exception as e:
                print(f"  line roles skipped ({type(e).__name__}: {e})")
            if streams_on:
                S2.install()
                SB.JS, SB.CSS, _ok = S2.patch_all(SB.JS, SB.CSS)
                S3.install()
                SB.JS, v3_ok = S3.patch_all(SB.JS)
                S4.install()
                SB.JS, v4_ok = S4.patch_all(SB.JS)
                STR.plan_moves = _no_streams_plan          # one plan for the whole site: core.py (Game plan)
                if v3_ok:
                    SB.JS, SB.PAGE, gp_on = GP.patch_all(SB.JS, SB.PAGE)
        else:
            print("  no deeper stats available, building the basic version")
    except Exception as e:
        print(f"  deeper stats failed ({type(e).__name__}: {e}); building the basic version")

    SB.JS = patch_text(SB.JS, LOCK_PATCHES, "daily lock")
    SB.PAGE = patch_text(SB.PAGE, LOCK_PAGE, "daily lock layout")
    SB.CSS = patch_text(SB.CSS, LOCK_CSS, "polish styles")
    _pp, _pj = pwa.page_patches()
    SB.PAGE = patch_text(SB.PAGE, _pp, "phone app layout")
    SB.JS = patch_text(SB.JS, _pj, "phone app script")
    SB.JS, SB.PAGE, SB.CSS, _ui_ok = UI.apply(SB.JS, SB.PAGE, SB.CSS)      # grouped tabs, photos, contrast (cosmetic only)
    SB.JS, SB.CSS, _pc_ok = PC.apply(SB.JS, SB.CSS)                         # cleaner player card popup (cosmetic only)
    D.goalie_decisions = _goalies                                           # start/bench calls for the whole matchup

    now_ms = NC.now_ms()
    site_data = SB.build_site_data(cfg, data, league, standings, now_ms)
    _ab, _gm = D.schedule_maps(data["schedules"])
    site_data["g28"] = C.team_games(_gm, _ab, data["roster"].get("scoringPeriodId", 1), 28)   # trade values: next 4 weeks
    if site_data.get("matchup"):
        PL.MOVE_LIMIT = site_data["matchup"].get("move_limit", PL.MOVE_LIMIT)
    try:
        _m = site_data.get("matchup")
        _nd = max(1, min(int(_m["days_left"]) if _m else 7, D.MAX_DAYS))
        site_data["clock"] = D.day_clock(data["schedules"], data["roster"].get("scoringPeriodId", 1), _nd, now_ms)
        lk = [i for i in range(_nd) if D.day_locked(site_data["clock"], i, now_ms)]
        first = site_data["clock"]["lock"][0]
        print(f"  day lock: {site_data['clock']['labels'][0]} first puck "
              f"{datetime.fromtimestamp(first / 1000, D.et_zone()).strftime('%I:%M %p') if first else 'no games'}; "
              f"{len(lk)} day(s) already locked")
    except Exception as e:                                  # the page copes without it; never fail the build over this
        print(f"  day lock clock skipped ({type(e).__name__}: {e})")
    try:
        PC.annotate(site_data, data, now_ms)                # games left in this matchup, for the player card
    except Exception as e:
        print(f"  games-left skipped ({type(e).__name__}: {e})")
    if planner_on:
        try:
            site_data["planner"] = PL.build(cfg, data, league, standings, now_ms, site_data)
        except Exception as e:
            print(f"  planner data failed ({type(e).__name__}: {e})")
    if streams_on:
        try:
            site_data["streams"] = STR.build(cfg, data, league, standings, now_ms, site_data)
            pl = site_data["streams"]["plan"]
            print(f"  move plan: {len(pl['moves'])} moves, +{pl['gain']} pts")
            for mv in pl["moves"]:
                print(f"     {mv['day']}: add {mv['add']['n']} drop {mv['drop']['n']} (+{mv['gain']})")
        except Exception as e:
            print(f"  streams data failed ({type(e).__name__}: {e})")
    if gp_on:
        try:
            mp = (league.get("status") or {}).get("currentMatchupPeriod")
            site_data["gameplan"] = GP.build(cfg, data, league, standings, now_ms, site_data, prev=WK.previous(mp))
            gp = site_data["gameplan"]
            print(f"  game plan: {len(gp['moves'])} of {gp['moves_left']} moves, +{gp['gain']} pts")
            for mv in gp["moves"]:
                print(f"     {mv['day']} [{mv['tier']}]: add {mv['add']['n']} drop {mv['drop']['n']} (+{mv['gain']}, cost {mv['cost']}, net {mv['net']}){' kept' if mv.get('kept') else ''}")
        except Exception as e:
            print(f"  game plan data failed ({type(e).__name__}: {e})")
    site_data["health"] = health_report(site_data, nhl_counts)
    if gp_on:
        try:
            site_data["weekplan"] = WK.build(cfg, data, league, standings, now_ms, site_data,
                                             healthy=site_data["health"]["healthy_plan"])
        except Exception as e:                              # the locked plan is an extra: never fail the build over it
            print(f"  weekly plan skipped ({type(e).__name__}: {e})")
    try:
        site_data["edge"] = EDG.build(cfg, data, league, standings, now_ms, site_data)
    except Exception as e:                                  # the schedule matrix is an extra: never fail the build over it
        print(f"  schedule edge skipped ({type(e).__name__}: {e})")
    if v3_ok:
        site_data["moves"] = []                  # the Streams tab now owns the move suggestions
    if not site_data["mine"]:
        sys.exit("Couldn't find your team. Check LEAGUE_ID and TEAM_ID.")
    print(E.summary())
    miss = [p["n"] for p in site_data["mine"] if "toi" not in p and p["grp"] != "G"]
    if miss:
        print("  roster skaters without NHL stats:", ", ".join(miss))
    Path("site").mkdir(exist_ok=True)
    html_text = SB.render_site(site_data)
    html_text = add_refresh_button(html_text)
    missing = [k for k in REQUIRED if k not in html_text]
    if missing:                                            # never publish a page with a section silently missing
        sys.exit("Page is incomplete, not publishing it. Missing: " + ", ".join(missing))
    Path("site/index.html").write_text(html_text, encoding="utf-8")
    try:
        pwa.write_files("site")
        write_notify_payload(site_data, now_ms)
    except Exception as e:                                  # the app files and alert text are extras: never fail the build
        print(f"  phone app files skipped ({type(e).__name__}: {e})")
    m = site_data["matchup"]
    if m:
        print(f"Matchup vs {m['opp_name']}: {m['me_now']:.1f}-{m['opp_now']:.1f}, win chance {m['p_win']*100:.0f}%")
    for gd in site_data["goalies"]:
        p = gd["p"]
        print(f"  {p['n']}: outlook {p['out']:.2f}, start chance {int((p.get('sp') or 0)*100)}%, "
              f"vs xG {p.get('gsax')}")
        for r in gd["rows"]:
            print(f"     {r['day']} {'vs' if r['home'] else '@'} {r['opp']}: win {r['p']*100:.0f}% exp {r['e']:+.1f} -> {r['verdict']}")
    for mv in site_data["moves"]:
        print(f"  MOVE add {mv['add']['n']} ({mv['add']['out']:.2f}) drop {mv['drop']['n']} ({mv['drop']['out']:.2f})")
    for a in site_data["alerts"]:
        print("  ALERT:", a["t"])
    print(f"Saved site/index.html ({len(html_text)//1024} KB)")


if __name__ == "__main__":
    main()
