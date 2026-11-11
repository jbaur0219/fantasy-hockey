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

    planner_on = streams_on = v3_ok = False
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
