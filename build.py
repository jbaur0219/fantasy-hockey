#!/usr/bin/env python3
"""
Builds the interactive site WITH deeper stats (NHL.com + MoneyPuck). READ-ONLY.

Run:  python3 build.py     ->  writes site/index.html

Same as site_builder.py, plus: expected goals, ice time, power-play time, goalie save-% regression,
real goalie start rates, and extra columns/flags on the page. If the extra data can't be loaded,
it falls back to the basic version automatically.
"""
import sys
import time
from pathlib import Path

import analyze as A
import dashboard as D
import enrich as E
import planner as PL
import roles as R
import streams2 as S2
import streams3 as S3
import streams4 as S4
import gameplan as GP
import streams as STR
import site_builder as SB
import starters as S

_base_slim = SB.slim
EXTRA = ("toi", "pp", "ixg", "gx", "xgf", "gs", "qs", "gsax", "h60", "b60")


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


def main():
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
    print("Loading deeper stats...")
    try:
        nhl = E.load(cfg["season"])
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
                if v3_ok:
                    SB.JS, SB.PAGE, gp_on = GP.patch_all(SB.JS, SB.PAGE)
        else:
            print("  no deeper stats available, building the basic version")
    except Exception as e:
        print(f"  deeper stats failed ({type(e).__name__}: {e}); building the basic version")

    now_ms = int(time.time() * 1000)
    site_data = SB.build_site_data(cfg, data, league, standings, now_ms)
    if planner_on:
        try:
            site_data["planner"] = PL.build(cfg, data, league, standings, now_ms, site_data)
        except Exception as e:
            print(f"  planner data failed ({type(e).__name__: {e})")
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
            site_data["gameplan"] = GP.build(cfg, data, league, standings, now_ms, site_data)
            gp = site_data["gameplan"]
            print(f"  game plan: {len(gp['moves'])} of {gp['moves_left']} moves, +{gp['gain']} pts")
            for mv in gp["moves"]:
                print(f"     {mv['day']} [{mv['tier']}]: add {mv['add']['n']} drop {mv['drop']['n']} (+{mv['gain']}, net {mv['net']})")
        except Exception as e:
            print(f"  game plan data failed ({type(e).__name__: {e})")
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
    Path("site/index.html").write_text(html_text, encoding="utf-8")
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
