#!/usr/bin/env python3
"""
Weekly PLANNER tab (READ-ONLY).

Adds a "Planner" tab to the website:
  - Your week at a glance: for each of the next 7 days, how many of your skaters/goalies play and how many
    lineup slots would sit empty (those are the best days for streaming pickups)
  - Games per team: a heat map of who plays when, with totals and back-to-backs
  - Streaming goalies: the best free-agent goalies for each day (win chance + expected points)
  - Moves and waivers: adds used this matchup and waiver timing

Everything is computed from ESPN's schedule, the NHL standings and the player data already loaded.
"""
from datetime import datetime, timedelta

import analyze as A
import dashboard as D
import starters as S

STREAM_MIN_START = 0.3      # only free-agent goalies who start at least this often
STREAM_POOL = 25            # look at the best 25 free-agent goalies
MOVE_LIMIT = 7


def _grid(schedules, sp, abbr, games, now_ms, ndays):
    teams = []
    for tid, ab in abbr.items():
        if not ab or ab in ("FA", "?"):
            continue
        row = []
        for i in range(ndays):
            gl = games.get(tid, {}).get(str(sp + i), [])
            if gl:
                g = gl[0]
                home = g.get("homeProTeamId") == tid
                opp = abbr.get(g.get("awayProTeamId") if home else g.get("homeProTeamId"), "?")
                row.append([opp, 1 if home else 0])
            else:
                row.append(None)
        teams.append({"tm": ab, "g": row})
    return teams


def _stream(site_data, sp, abbr, games, standings, now_ms, ndays):
    tid_of = {ab: tid for tid, ab in abbr.items()}
    pool = [p for p in site_data["fas"] if p["grp"] == "G" and p["inj"] not in A.BAD_INJURY]
    pool = sorted(pool, key=lambda p: -(p["out"] or 0))[:STREAM_POOL]
    out = []
    for p in pool:
        if (p.get("sp") or 0) < STREAM_MIN_START:
            continue
        tid = tid_of.get(p["tm"])
        s_me = D.team_strength(p["tm"], standings)
        for i in range(ndays):
            for g in games.get(tid, {}).get(str(sp + i), [])[:1]:
                if i == 0 and g.get("date", 0) <= now_ms:
                    continue                                    # today's game already started
                home = g.get("homeProTeamId") == tid
                opp = abbr.get(g.get("awayProTeamId") if home else g.get("homeProTeamId"), "?")
                pw = D.log5(s_me, D.team_strength(opp, standings)) + (D.HOME_ICE if home else -D.HOME_ICE)
                if p.get("svp") and p["gp"] >= 5:
                    pw += D.clamp((p["svp"] - 0.905) * 2.0, -0.05, 0.05)
                pw = D.clamp(pw, 0.15, 0.85)
                e = (p["out"] or 0) + 4 * (pw - s_me)
                st = None
                if i == 0 and S.STATE["by_team"].get(p["tm"]):
                    starter = S.STATE["by_team"][p["tm"]]
                    if S.E.norm(starter["name"]) != S.E.norm(p["n"]):
                        continue                                # someone else is in net today
                    st = starter["status"]
                out.append({"i": i, "id": p["id"], "n": p["n"], "o": opp, "h": 1 if home else 0,
                            "p": round(pw, 3), "e": round(e, 2), "st": st})
    return out


def _moves_used(league, my_id):
    try:
        mp = str((league.get("status") or {}).get("currentMatchupPeriod"))
        for t in league.get("teams", []):
            if t.get("id") == my_id:
                tot = (t.get("transactionCounter") or {}).get("matchupAcquisitionTotals") or {}
                v = tot.get(mp)
                return int(v) if v is not None else None
    except Exception:
        pass
    return None


def build(cfg, data, league, standings, now_ms, site_data):
    sp = data["roster"].get("scoringPeriodId", 1)
    abbr, games = D.schedule_maps(data["schedules"])
    today = datetime.fromtimestamp(now_ms / 1000, D.et_zone()).date()
    m = site_data.get("matchup")
    ndays = max(1, min(int(m["days_left"]) if m else 7, 7))       # only the rest of THIS matchup week (through Sunday)
    days = [(today + timedelta(days=i)).strftime("%a %b %d").replace(" 0", " ") for i in range(ndays)]
    return {"days": days, "teams": _grid(data["schedules"], sp, abbr, games, now_ms, ndays),
            "stream": _stream(site_data, sp, abbr, games, standings, now_ms, ndays),
            "moves_used": _moves_used(league, cfg["team"]), "limit": MOVE_LIMIT}


# ---------------------------------------------------------------------------
# Website patches (exact-match; skipped with a message if the page code ever changes)
# ---------------------------------------------------------------------------
PLANNER_JS = r"""
function plannerRender(){
  var P=D.planner,h='';
  if(!P){$('#t-planner').innerHTML='<div class="card">Planner data is not available right now.</div>';return;}
  var act=D.mine.filter(function(p){return p.slot!=='IR'&&!isInj(p);});
  var gm={};P.teams.forEach(function(t){gm[t.tm]=t.g;});
  function plays(p,i){var g=gm[p.tm];return !!(g&&g[i]);}
  var rows=P.days.map(function(d,i){
    var Fa=act.filter(function(p){return p.grp==='F'&&plays(p,i);}).length;
    var Da=act.filter(function(p){return p.grp==='D'&&plays(p,i);}).length;
    var Ga=act.filter(function(p){return p.grp==='G'&&plays(p,i);}).length;
    var fF=Math.min(9,Fa),fD=Math.min(5,Da),left=(Fa-fF)+(Da-fD),util=left>0?1:0;
    return {d:d,i:i,F:Fa,D:Da,G:Ga,empty:(9-fF)+(5-fD)+(1-util)};
  });
  h+='<div class="card"><h2>Your week at a glance</h2>'+mkTable([
    {h:'Day',v:function(r){return r.i;},r:function(r){return esc(r.d);}},
    {h:'Forwards playing (9 slots)',v:function(r){return r.F;},num:1},
    {h:'Defense playing (5 slots)',v:function(r){return r.D;},num:1},
    {h:'Goalies playing',v:function(r){return r.G;},num:1},
    {h:'Empty slots',v:function(r){return r.empty;},num:1,r:function(r){return '<span class="'+(r.empty>=4?'bad':(r.empty>=2?'warn':'good'))+'">'+r.empty+'</span>';}}],rows)
    +'<div class="muted">Empty slots are days when you cannot fill every lineup spot with a healthy player who has a game. Those are the best days for a streaming pickup.</div></div>';
  h+='<div class="card"><h2>Moves and waivers</h2>';
  if(P.moves_used==null)h+='<div>Your league allows '+P.limit+' adds per matchup. ESPN shows how many you have used on your roster page.</div>';
  else h+='<div><span class="big">'+P.moves_used+' / '+P.limit+'</span> <span class="muted">adds used this matchup</span></div>';
  h+='<div class="muted" style="margin-top:6px">Waivers clear after 1 day, so a claim placed today is usually yours tomorrow. Plan a pickup a day before you need it. Players marked FREEAGENT can be added immediately.</div></div>';
  h+='<div class="card"><h2>Streaming goalies by day</h2><div class="chips">';
  P.days.forEach(function(d,i){
    var list=P.stream.filter(function(s){return s.i===i;}).sort(function(a,b){return b.e-a.e;}).slice(0,3);
    h+='<div class="chip"><div class="d">'+esc(d)+'</div>';
    if(!list.length)h+='<div class="m muted">No good options</div>';
    list.forEach(function(s){h+='<div class="m"><a class="pl" data-id="'+s.id+'">'+esc(s.n)+'</a> '+(s.h?'vs':'@')+' '+esc(s.o)+' &middot; win '+Math.round(s.p*100)+'% &middot; '+sgn(s.e,1)+(s.st?' &middot; '+esc(s.st):'')+'</div>';});
    h+='</div>';});
  h+='</div><div class="muted" style="margin-top:8px">Free-agent goalies who start at least 30% of their team games. Expected points use team strength, home ice and save %. Starters are only confirmed for today, so check tomorrow morning before adding.</div></div>';
  var mineBy={};act.forEach(function(p){mineBy[p.tm]=(mineBy[p.tm]||0)+1;});
  var trows=P.teams.map(function(t){
    var tot=t.g.filter(Boolean).length,b2b=0;
    for(var i=1;i<t.g.length;i++){if(t.g[i]&&t.g[i-1])b2b++;}
    return {tm:t.tm,g:t.g,total:tot,b2b:b2b,mine:mineBy[t.tm]||0,me:!!mineBy[t.tm]};});
  trows.sort(function(a,b){return (b.total-a.total)||a.tm.localeCompare(b.tm);});
  var cols=[{h:'Team',v:function(r){return r.tm;}}];
  P.days.forEach(function(d,i){cols.push({h:d,v:function(r){return r.g[i]?1:0;},num:1,r:function(r){var c=r.g[i];return c?'<span class="gcell">'+(c[1]?'vs':'@')+' '+esc(c[0])+'</span>':'<span class="muted">-</span>';}});});
  cols.push({h:'Games',v:function(r){return r.total;},num:1},{h:'Back-to-backs',v:function(r){return r.b2b;},num:1},{h:'My players',v:function(r){return r.mine;},num:1});
  h+='<div class="card"><h2>Games per team, rest of this matchup</h2>'+mkTable(cols,trows)
    +'<div class="muted">Bold rows are teams you own players on. More games means more points, and back-to-backs often mean a backup goalie in the second game.</div></div>';
  $('#t-planner').innerHTML=h;
  $$('#t-planner table').forEach(function(t){wireSort(t.parentNode);});
}

/* ---------- tabs + startup ---------- */"""

JS_PATCHES = [
    ("var TABS=['overview','roster','free','trade','league'];", "var TABS=['overview','roster','free','trade','planner','league'];"),
    ("/* ---------- tabs + startup ---------- */", PLANNER_JS.lstrip("\n")),
    ("tradeInit();leagueRender();", "tradeInit();leagueRender();plannerRender();"),
]
PAGE_PATCHES = [
    ('<button id="nav-league">League</button>',
     '<button id="nav-planner">Planner</button><button id="nav-league">League</button>'),
    ('<section id="t-league" style="display:none">',
     '<section id="t-planner" style="display:none"></section>\n<section id="t-league" style="display:none">'),
]
CSS_PATCHES = [
    (".me td{font-weight:700}", ".me td{font-weight:700}.gcell{background:var(--soft);border-radius:6px;padding:1px 6px;font-size:12px;white-space:nowrap}"),
]


def patch_text(text, pairs, label):
    for old, new in pairs:
        if text.count(old) != 1:
            print(f"  (planner patch skipped in {label}: '{old[:40]}...' not found once)")
            return text            # all-or-nothing, so the page never ends up half-patched
    for old, new in pairs:
        text = text.replace(old, new)
    return text


def patch_all(js, page, css):
    """Apply the page, script and style patches together, or none of them."""
    nj = patch_text(js, JS_PATCHES, "page script")
    npg = patch_text(page, PAGE_PATCHES, "page layout")
    nc = patch_text(css, CSS_PATCHES, "styles")
    if nj != js and npg != page and nc != css:
        return nj, npg, nc, True
    print("  planner tab skipped (page code changed)")
    return js, page, css, False
