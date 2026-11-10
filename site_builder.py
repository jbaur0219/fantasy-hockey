#!/usr/bin/env python3
"""
Fantasy Hockey INTERACTIVE SITE  (READ-ONLY)

Run:  python3 site_builder.py     ->  writes site/index.html

Builds one self-contained web page with tabs:
  Overview   - matchup win probability, goalie START/BENCH calls, suggested moves, lineup alerts
  Roster     - sortable/filterable table, click any player for a stat card
  Free agents- sortable/filterable, shows the upgrade over your weakest player at each position
  Trade lab  - pick players on both sides and see the effect on both lineups
  League     - standings plus power rankings for all 12 teams

It never adds, drops, trades, or changes your lineup. It only reads.
Uses analyze.py and dashboard.py (same folder).
"""
import json
import sys
import time
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
        teams.append({"id": tid, "name": D.team_label(m) if m else f"Team {tid}", "rec": f"{w}-{l}-{ti}",
                      "w": w, "pf": r3(pf), "me": tid == cfg["team"],
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


CSS = r"""
:root{--bg:#f5f6f8;--card:#fff;--text:#1d2330;--muted:#6a7385;--line:#e4e7ee;--accent:#2563eb;
--green:#16a34a;--amber:#d97706;--red:#dc2626;--gray:#6b7280;--soft:#eef2ff}
@media (prefers-color-scheme:dark){:root{--bg:#0f1420;--card:#171e2e;--text:#e8ecf5;--muted:#9aa5bd;
--line:#263049;--accent:#60a5fa;--green:#4ade80;--amber:#fbbf24;--red:#f87171;--gray:#9ca3af;--soft:#1e2a4a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:16px 14px 60px}
h1{font-size:22px;margin:0}.sub{color:var(--muted);font-size:13px;margin:2px 0 12px}
.tabs{position:sticky;top:0;z-index:5;background:var(--bg);padding:8px 0;display:flex;gap:6px;flex-wrap:wrap;
border-bottom:1px solid var(--line);margin-bottom:6px}
.tabs button{border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:999px;
padding:7px 14px;font-size:14px;cursor:pointer}.tabs button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0}
.card h2{font-size:14px;margin:0 0 10px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.card h3{font-size:14px;margin:0 0 6px}
.vs{display:flex;justify-content:space-between;gap:10px;align-items:flex-end;flex-wrap:wrap}
.team{flex:1;min-width:140px}.team .n{font-weight:600}.team .s{font-size:28px;font-weight:700}
.team .r{color:var(--muted);font-size:13px}.right{text-align:right}
.bar{height:14px;border-radius:8px;background:var(--line);overflow:hidden;margin:12px 0 6px;display:flex}
.bar i{display:block;height:100%}.bar .a{background:var(--accent)}.bar .b{background:var(--gray)}
.big{font-size:30px;font-weight:700}.muted{color:var(--muted);font-size:13px}
.g{border-top:1px solid var(--line);padding:10px 0}.g:first-of-type{border-top:0}
.gh{display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px}.gh b{font-size:16px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
.chip{border:1px solid var(--line);border-radius:10px;padding:8px 10px;min-width:150px;flex:1}
.chip .d{font-size:12px;color:var(--muted)}.chip .o{font-weight:600}.chip .m{font-size:13px}
.pill{display:inline-block;border-radius:999px;padding:2px 10px;font-size:12px;font-weight:700;color:#fff}
.start{background:var(--green)}.risky{background:var(--amber)}.bench{background:var(--red)}.done{background:var(--gray)}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600;cursor:pointer;white-space:nowrap;user-select:none}
th.asc:after{content:' \25B2'}th.desc:after{content:' \25BC'}.scroll{overflow-x:auto}
.good{color:var(--green);font-weight:600}.warn{color:var(--amber)}.bad{color:var(--red);font-weight:600}
ul{margin:0;padding-left:18px}li{margin:4px 0}
a.pl{color:var(--accent);cursor:pointer;font-weight:600}a.pl:hover{text-decoration:underline}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px}
.chip-btn{border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:999px;padding:4px 12px;cursor:pointer}
.chip-btn.on{background:var(--soft);border-color:var(--accent);color:var(--accent);font-weight:600}
input[type=text],select{background:var(--card);color:var(--text);border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:14px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media (max-width:640px){.two{grid-template-columns:1fr}}
.opt{display:block;padding:3px 0;font-size:14px}.listbox{max-height:340px;overflow:auto;border:1px solid var(--line);border-radius:8px;padding:6px 10px}
.res{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:10px 0}
.res .box{border:1px solid var(--line);border-radius:10px;padding:10px}.res .t{font-size:12px;color:var(--muted)}
.res .v{font-size:20px;font-weight:700}
.verdict{padding:10px 12px;border-radius:10px;background:var(--soft);margin-top:8px;font-weight:600}
#modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:20;align-items:center;justify-content:center;padding:14px}
#modal.open{display:flex}#modal .box{background:var(--card);border-radius:14px;max-width:560px;width:100%;max-height:90vh;overflow:auto;padding:16px}
.mhead{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;margin-bottom:10px}.mhead b{font-size:18px}
.x{margin-left:auto;border:0;background:none;color:var(--muted);font-size:24px;cursor:pointer}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px}
.cell{border:1px solid var(--line);border-radius:8px;padding:8px}.cell .k{font-size:11px;color:var(--muted)}.cell .v{font-weight:700;font-size:16px}
.me td{font-weight:700}
"""

JS = r"""
(function(){
var D=JSON.parse(document.getElementById('data').textContent);
var BAD=['OUT','INJURY_RESERVE','SUSPENSION'];
function $(s,r){return (r||document).querySelector(s);}
function $$(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s));}
function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function f(x,d){if(x==null||isNaN(x))return '-';return Number(x).toFixed(d==null?2:d);}
function sgn(x,d){return (x>=0?'+':'')+f(x,d);}
var ALL={};
D.mine.concat(D.fas).forEach(function(p){ALL[p.id]=p;});
D.teams.forEach(function(t){t.players.forEach(function(p){if(!ALL[p.id])ALL[p.id]=p;});});
function plink(p){return '<a class="pl" data-id="'+p.id+'">'+esc(p.n)+'</a> <span class="muted">('+esc(p.pos)+', '+esc(p.tm)+')</span>';}
function isInj(p){return BAD.indexOf(p.inj)>=0;}
function val(p){return p.grp==='G'?(p.out||0)*p.g7*(p.sp||0.5):(p.out||0)*p.g7;}
function lineup(players){
  var a=players.filter(function(p){return p.slot!=='IR'&&!isInj(p);});
  function by(g){return a.filter(function(p){return p.grp===g;}).sort(function(x,y){return val(y)-val(x);});}
  var F=by('F'),Dd=by('D'),G=by('G');
  var used=F.slice(0,9).concat(Dd.slice(0,5));
  var rest=F.slice(9).concat(Dd.slice(5)).sort(function(x,y){return val(y)-val(x);});
  if(rest.length)used.push(rest[0]);
  used=used.concat(G.slice(0,2));
  return used.reduce(function(s,p){return s+val(p);},0);
}
function flagsHtml(p){return (p.fl&&p.fl.length)?esc(p.fl.join('; ')):'';}

/* ---------- generic sortable table ---------- */
function mkTable(cols,rows){
  var h='<div class="scroll"><table><thead><tr>';
  cols.forEach(function(c,i){h+='<th data-i="'+i+'" data-num="'+(c.num?1:0)+'">'+esc(c.h)+'</th>';});
  h+='</tr></thead><tbody>';
  rows.forEach(function(r){
    h+='<tr'+(r.me?' class="me"':'')+'>';
    cols.forEach(function(c){
      var v=c.v(r);
      h+='<td data-v="'+esc(v==null?'':v)+'"'+(c.cls?' class="'+c.cls(r)+'"':'')+'>'+(c.r?c.r(r):esc(v==null?'-':(c.fmt?c.fmt(v):v)))+'</td>';
    });
    h+='</tr>';
  });
  return h+'</tbody></table></div>';
}
function wireSort(c){
  $$('th',c).forEach(function(th){th.addEventListener('click',function(){
    var i=+th.getAttribute('data-i');
    var asc=th.classList.contains('asc')?false:(th.classList.contains('desc')?true:th.getAttribute('data-num')!=='1');
    var tb=$('tbody',c);var rows=$$('tr',tb);
    rows.sort(function(a,b){
      var x=a.children[i].getAttribute('data-v'),y=b.children[i].getAttribute('data-v');
      var nx=parseFloat(x),ny=parseFloat(y);
      var r=(!isNaN(nx)&&!isNaN(ny))?nx-ny:String(x).localeCompare(String(y));
      return asc?r:-r;});
    rows.forEach(function(r){tb.appendChild(r);});
    $$('th',c).forEach(function(t){t.classList.remove('asc');t.classList.remove('desc');});
    th.classList.add(asc?'asc':'desc');
  });});
}
function chips(id,opts,cur,cb){
  var h='';opts.forEach(function(o){h+='<button class="chip-btn'+(o===cur?' on':'')+'" data-v="'+o+'">'+o+'</button>';});
  var c=$(id);c.innerHTML=h;
  $$('button',c).forEach(function(b){b.addEventListener('click',function(){cb(b.getAttribute('data-v'));});});
}

/* ---------- columns ---------- */
var worst={};
['F','D','G'].forEach(function(g){
  var a=D.mine.filter(function(p){return p.grp===g&&p.slot!=='IR';});
  worst[g]=a.length?Math.min.apply(null,a.map(function(p){return p.out;})):0;});
function up(p){return p.out-worst[p.grp];}
var cName={h:'Player',v:function(p){return p.n;},r:plink};
var cPPG={h:'PPG',v:function(p){return p.ppg;},num:1,fmt:f};
var cProj={h:'Proj',v:function(p){return p.proj;},num:1,fmt:f};
var cOut={h:'Outlook',v:function(p){return p.out;},num:1,fmt:f};
var cGP={h:'GP',v:function(p){return p.gp;},num:1};
var cG7={h:'G7',v:function(p){return p.g7;},num:1};
var cFlags={h:'Flags',v:function(p){return (p.fl||[]).join('; ');},r:flagsHtml};
var rosterCols=[cName,{h:'Slot',v:function(p){return p.slot;}},cGP,cPPG,{h:'Exp',v:function(p){return p.exp;},num:1,fmt:f},cProj,cOut,cG7,cFlags];
var faCols=[cName,cOut,{h:'vs weakest',v:function(p){return up(p);},num:1,r:function(p){var u=up(p);return '<span class="'+(u>=0.2?'good':(u<0?'bad':''))+'">'+sgn(u)+'</span>';}},
  cPPG,cProj,cGP,cG7,{h:'Owned',v:function(p){return p.own;},num:1,r:function(p){return p.own==null?'-':f(p.own,0)+'%';}},
  {h:'Status',v:function(p){return p.st||'';}},cFlags];

/* ---------- overview ---------- */
function overview(){
  var h='',m=D.matchup;
  if(m){var pw=Math.round(m.p_win*100);
    h+='<div class="card"><h2>This week matchup</h2><div class="vs"><div class="team"><div class="n">'+esc(D.me)+'</div><div class="s">'+f(m.me_now,1)+'</div><div class="r">projected final '+Math.round(m.proj_me)+'</div></div>'
    +'<div class="team right"><div class="n">'+esc(m.opp_name)+'</div><div class="s">'+f(m.opp_now,1)+'</div><div class="r">'+esc(m.opp_rec)+' &middot; projected final '+Math.round(m.proj_opp)+'</div></div></div>'
    +'<div class="bar"><i class="a" style="width:'+pw+'%"></i><i class="b" style="width:'+(100-pw)+'%"></i></div>'
    +'<div><span class="big">'+pw+'%</span> <span class="muted">chance you win this week ('+m.days_left+' scoring days left, best lineup each day)</span></div></div>';}
  h+='<div class="card"><h2>Goalie decisions</h2>';
  if(!D.goalies.length)h+='<div class="muted">No goalies on your roster.</div>';
  D.goalies.forEach(function(g){
    var p=g.p;
    h+='<div class="g"><div class="gh"><b>'+plink(p)+'</b><span class="muted">'+f(p.out)+' pts/start outlook'+(p.svp?' &middot; save % '+f(p.svp,3):'')+'</span></div>';
    if(!g.rows.length)h+='<div class="muted">No games in the next few days.</div>';
    else{h+='<div class="chips">';
      g.rows.forEach(function(r){
        h+='<div class="chip"><div class="d">'+esc(r.day)+' &middot; '+esc(r.time)+'</div><div class="o">'+(r.home?'vs':'@')+' '+esc(r.opp)+'</div>'
        +'<div class="m">Win chance '+Math.round(r.p*100)+'% &middot; exp. '+sgn(r.e,1)+' pts</div>'
        +'<div style="margin-top:6px"><span class="pill '+r.cls+'">'+esc(r.verdict)+'</span></div></div>';});
      h+='</div>';}
    h+='</div>';});
  h+='<div class="muted" style="margin-top:8px">BENCH = expected points below zero. START (RISKY) = slightly positive but a big swing either way. NHL single games are close to coin flips, so treat win chances as leans. Confirmed starters are not included yet.</div></div>';
  h+='<div class="card"><h2>Suggested moves</h2>';
  if(D.moves.length){
    h+=mkTable([{h:'Add',v:function(m){return m.add.n;},r:function(m){return plink(m.add);}},
      {h:'Outlook',v:function(m){return m.add.out;},num:1,fmt:f},{h:'Games (7d)',v:function(m){return m.add.g7;},num:1},
      {h:'Drop',v:function(m){return m.drop.n;},r:function(m){return plink(m.drop);}},
      {h:'Outlook',v:function(m){return m.drop.out;},num:1,fmt:f},
      {h:'Gain/game',v:function(m){return m.gain;},num:1,r:function(m){return '<span class="good">'+sgn(m.gain)+'</span>';}},
      {h:'Gain (7d)',v:function(m){return m.wk;},num:1,r:function(m){return '<span class="good">'+sgn(m.wk,1)+'</span>';}}],D.moves);
    h+='<div class="muted">Players with very few games and no ESPN projection can look better than they are. Check small samples before acting.</div>';
  }else h+='<div class="muted">Nothing available clearly beats your weakest players.</div>';
  h+='</div><div class="card"><h2>Lineup alerts (today)</h2>';
  if(D.alerts.length)h+='<ul>'+D.alerts.map(function(a){return '<li class="'+a.k+'">'+esc(a.t)+'</li>';}).join('')+'</ul>';
  else h+='<div class="good">No lineup problems found.</div>';
  h+='</div>';
  $('#t-overview').innerHTML=h;
  $$('#t-overview table').forEach(function(t){wireSort(t.parentNode);});
}

/* ---------- roster ---------- */
var R={pos:'All',q:''};
function rosterRender(){
  chips('#rosterPos',['All','F','D','G'],R.pos,function(v){R.pos=v;rosterRender();});
  var rows=D.mine.filter(function(p){return (R.pos==='All'||p.grp===R.pos)&&(!R.q||p.n.toLowerCase().indexOf(R.q)>=0);});
  $('#rosterTbl').innerHTML=mkTable(rosterCols,rows);wireSort($('#rosterTbl'));
}

/* ---------- free agents ---------- */
var FA={pos:'All',q:'',hide:true,games:false,n:50};
function faRender(){
  chips('#faPos',['All','F','D','G'],FA.pos,function(v){FA.pos=v;faRender();});
  var rows=D.fas.filter(function(p){return (FA.pos==='All'||p.grp===FA.pos)&&(!FA.q||p.n.toLowerCase().indexOf(FA.q)>=0)&&(!FA.hide||!isInj(p))&&(!FA.games||p.g7>0);});
  rows.sort(function(a,b){return b.out-a.out;});
  var total=rows.length;rows=rows.slice(0,FA.n);
  $('#faTbl').innerHTML=mkTable(faCols,rows)+'<div class="muted">Showing '+rows.length+' of '+total+'. vs weakest = outlook minus your weakest active player at that position.</div>';
  wireSort($('#faTbl'));
}

/* ---------- trade lab ---------- */
function listHtml(ps){
  return ps.slice().sort(function(a,b){return b.out-a.out;}).map(function(p){
    return '<label class="opt"><input type="checkbox" value="'+p.id+'"> '+esc(p.n)+' <span class="muted">'+esc(p.pos)+' &middot; '+f(p.out)+(p.slot==='IR'?' &middot; IR':'')+'</span></label>';}).join('');
}
function theTeam(){var id=$('#tradeTeam').value;return D.teams.filter(function(t){return String(t.id)===id;})[0];}
function checked(sel){return $$(sel+' input:checked').map(function(c){return +c.value;});}
function tradeTeam(){var t=theTeam();$('#getList').innerHTML=t?listHtml(t.players):'';runTrade();}
function box(t,v){return '<div class="box"><div class="t">'+t+'</div><div class="v">'+v+'</div></div>';}
function delta(d){return '<span class="'+(d>0.5?'good':(d<-0.5?'bad':''))+'">'+sgn(d,1)+'</span>';}
function runTrade(){
  var t=theTeam(),out=$('#tradeOut');
  var give=checked('#giveList'),get=checked('#getList');
  if(!t||(!give.length&&!get.length)){out.innerHTML='<div class="muted">Pick players on each side to see how a trade changes both lineups.</div>';return;}
  var mine=D.mine,theirs=t.players;
  var myAfter=mine.filter(function(p){return give.indexOf(p.id)<0;}).concat(theirs.filter(function(p){return get.indexOf(p.id)>=0;}));
  var thAfter=theirs.filter(function(p){return get.indexOf(p.id)<0;}).concat(mine.filter(function(p){return give.indexOf(p.id)>=0;}));
  var b1=lineup(mine),a1=lineup(myAfter),b2=lineup(theirs),a2=lineup(thAfter);
  var d1=a1-b1,d2=a2-b2,v;
  if(d1>0.5&&d2>0.5)v='Win-win: it helps both lineups, so they might accept.';
  else if(d1>0.5&&d2<=0.5)v='Helps you but costs them about '+f(-d2,1)+' pts/week, so they may decline.';
  else if(d1<=0.5&&d2>0.5)v='Helps them more than you. You would lose about '+f(Math.max(0,-d1),1)+' pts/week.';
  else v='Little change for either side.';
  var size=myAfter.length,note='';
  if(size>22)note='<div class="warn">You would have '+size+' players and need to drop '+(size-22)+'.</div>';
  else if(size<22)note='<div class="muted">You would have '+(22-size)+' open roster spot(s).</div>';
  out.innerHTML='<div class="res">'+box('You: weekly points',f(b1,1)+' to '+f(a1,1)+' '+delta(d1))+box(esc(t.name)+': weekly points',f(b2,1)+' to '+f(a2,1)+' '+delta(d2))+'</div><div class="verdict">'+esc(v)+'</div>'+note
  +'<div class="muted" style="margin-top:8px">Approximate: best lineup using each player outlook times games in the next 7 days. Does not account for positional scarcity or what they actually need.</div>';
}
function tradeInit(){
  var sel=$('#tradeTeam');
  sel.innerHTML=D.teams.filter(function(t){return !t.me;}).map(function(t){return '<option value="'+t.id+'">'+esc(t.name)+'</option>';}).join('');
  $('#giveList').innerHTML=listHtml(D.mine);
  sel.addEventListener('change',tradeTeam);
  $('#giveList').addEventListener('change',runTrade);$('#getList').addEventListener('change',runTrade);
  tradeTeam();
}

/* ---------- league ---------- */
function leagueRender(){
  var rows=D.teams.map(function(t){return {id:t.id,name:t.name,rec:t.rec,w:t.w,pf:t.pf,me:t.me,power:lineup(t.players)};});
  rows.sort(function(a,b){return b.power-a.power;});rows.forEach(function(r,i){r.pr=i+1;});
  rows.sort(function(a,b){return (b.w-a.w)||(b.pf-a.pf);});
  $('#leagueTbl').innerHTML=mkTable([{h:'Team',v:function(r){return r.name;}},{h:'W-L-T',v:function(r){return r.w;},num:1,r:function(r){return esc(r.rec);}},
    {h:'Points for',v:function(r){return r.pf;},num:1,fmt:function(x){return f(x,1);}},
    {h:'Power (weekly pts)',v:function(r){return r.power;},num:1,fmt:function(x){return f(x,0);}},
    {h:'Power rank',v:function(r){return r.pr;},num:1}],rows);
  wireSort($('#leagueTbl'));
}

/* ---------- player card ---------- */
function closeModal(){$('#modal').classList.remove('open');}
function modal(p){
  function cell(k,v){return '<div class="cell"><div class="k">'+k+'</div><div class="v">'+v+'</div></div>';}
  var h='<div class="mhead"><b>'+esc(p.n)+'</b><span class="muted">'+esc(p.pos)+' &middot; '+esc(p.tm)+' &middot; '+esc(p.slot==='FA'?(p.st||'Free agent'):p.slot)+'</span><button class="x" id="mx">&times;</button></div><div class="grid">';
  h+=cell('Outlook (pts/gm)',f(p.out))+cell('Actual PPG',f(p.ppg))+cell('Luck-adjusted',f(p.exp))+cell('ESPN projection',f(p.proj))+cell('Last 15 days',f(p.rec))+cell('Games (7d)',p.g7)+cell('Games played',p.gp)+cell('Rostered',p.own==null?'-':f(p.own,0)+'%');
  if(p.grp==='G')h+=cell('Wins',p.w)+cell('Goals against',p.ga)+cell('Save %',p.svp==null?'-':f(p.svp,3))+cell('Start chance',p.sp==null?'-':Math.round(p.sp*100)+'%');
  else h+=cell('Goals',p.g)+cell('Assists',p.a)+cell('PP points',p.ppp)+cell('Shots',p.sog)+cell('Shooting %',p.shp==null?'-':f(p.shp*100,0)+'%')+cell('Hits',p.hit)+cell('Blocks',p.blk);
  h+='</div>';
  if(p.slot==='FA')h+='<div style="margin-top:10px">Versus your weakest '+p.grp+': <b class="'+(up(p)>=0.2?'good':(up(p)<0?'bad':''))+'">'+sgn(up(p))+'</b> pts/game</div>';
  if(p.fl&&p.fl.length)h+='<ul style="margin-top:10px">'+p.fl.map(function(x){return '<li>'+esc(x)+'</li>';}).join('')+'</ul>';
  if(p.inj&&p.inj!=='ACTIVE')h+='<div class="warn" style="margin-top:8px">Status: '+esc(p.inj)+'</div>';
  var m=$('#modal');m.innerHTML='<div class="box">'+h+'</div>';m.classList.add('open');
  $('#mx').addEventListener('click',closeModal);
}

/* ---------- tabs + startup ---------- */
var TABS=['overview','roster','free','trade','league'];
function showTab(n){
  if(TABS.indexOf(n)<0)n='overview';
  TABS.forEach(function(t){$('#t-'+t).style.display=(t===n)?'block':'none';$('#nav-'+t).classList.toggle('on',t===n);});
  try{history.replaceState(null,'','#'+n);}catch(e){}
}
document.addEventListener('click',function(e){
  var a=e.target.closest?e.target.closest('a.pl'):null;
  if(a){var p=ALL[a.getAttribute('data-id')];if(p)modal(p);return;}
  if(e.target.id==='modal')closeModal();
});
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeModal();});
TABS.forEach(function(t){$('#nav-'+t).addEventListener('click',function(){showTab(t);});});
$('#rosterQ').addEventListener('input',function(){R.q=this.value.toLowerCase();rosterRender();});
$('#faQ').addEventListener('input',function(){FA.q=this.value.toLowerCase();faRender();});
$('#faHide').addEventListener('change',function(){FA.hide=this.checked;faRender();});
$('#faGames').addEventListener('change',function(){FA.games=this.checked;faRender();});
$('#faN').addEventListener('change',function(){FA.n=+this.value;faRender();});
$('#title').textContent=D.me;
$('#sub').textContent=D.league+' \u00b7 record '+D.rec+' \u00b7 updated '+D.updated+' \u00b7 read-only, nothing is changed in ESPN';
overview();rosterRender();faRender();tradeInit();leagueRender();
showTab((location.hash||'').slice(1));
})();
"""

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="robots" content="noindex">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Fantasy Hockey Manager</title>
<style>__CSS__</style></head><body><div class="wrap">
<h1 id="title">Fantasy Hockey Manager</h1><div class="sub" id="sub"></div>
<div class="tabs">
<button id="nav-overview">Overview</button><button id="nav-roster">My roster</button>
<button id="nav-free">Free agents</button><button id="nav-trade">Trade lab</button><button id="nav-league">League</button></div>
<noscript><div class="card">This page needs JavaScript turned on.</div></noscript>
<section id="t-overview"></section>
<section id="t-roster" style="display:none"><div class="card"><h2>My roster</h2>
<div class="controls"><span id="rosterPos"></span><input type="text" id="rosterQ" placeholder="Search players"></div>
<div id="rosterTbl"></div>
<div class="muted">PPG = actual points per game. Exp = luck-adjusted. Proj = ESPN projection. Outlook = blend used for ranking. G7 = games in the next 7 days. Click a column to sort, a name for a stat card.</div></div></section>
<section id="t-free" style="display:none"><div class="card"><h2>Free agents and waivers</h2>
<div class="controls"><span id="faPos"></span><input type="text" id="faQ" placeholder="Search players">
<label><input type="checkbox" id="faHide" checked> hide injured</label>
<label><input type="checkbox" id="faGames"> only with games this week</label>
<select id="faN"><option value="25">Top 25</option><option value="50" selected>Top 50</option><option value="100">Top 100</option><option value="300">All</option></select></div>
<div id="faTbl"></div></div></section>
<section id="t-trade" style="display:none"><div class="card"><h2>Trade lab</h2>
<div class="controls"><label>Trade partner: <select id="tradeTeam"></select></label></div>
<div class="two"><div><h3>You give</h3><div class="listbox" id="giveList"></div></div><div><h3>You get</h3><div class="listbox" id="getList"></div></div></div>
<div id="tradeOut" style="margin-top:12px"></div></div></section>
<section id="t-league" style="display:none"><div class="card"><h2>Standings and power rankings</h2>
<div id="leagueTbl"></div>
<div class="muted">Power = approximate points each team's best lineup should score in the next 7 days, from outlook and schedule.</div></div></section>
</div><div id="modal"></div>
<script type="application/json" id="data">__DATA__</script><script>__JS__</script></body></html>"""


def render_site(site_data):
    blob = json.dumps(site_data, separators=(",", ":"), ensure_ascii=True).replace("</", "<\\/")
    return PAGE.replace("__CSS__", CSS).replace("__JS__", JS).replace("__DATA__", blob)


def main():
    cfg = A.get_config()
    print("Reading your ESPN league...")
    data = A.fetch_all(cfg)
    base = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{cfg['season']}"
    league = A.espn_get(f"{base}/segments/0/leagues/{cfg['league']}", cfg["cookies"],
                        params=[("view", "mSettings"), ("view", "mTeam"),
                                ("view", "mMatchup"), ("view", "mMatchupScore")])
    standings = D.load_nhl_standings()
    site_data = build_site_data(cfg, data, league, standings, int(time.time() * 1000))
    if not site_data["mine"]:
        sys.exit("Couldn't find your team. Check LEAGUE_ID and TEAM_ID.")
    Path("site").mkdir(exist_ok=True)
    html_text = render_site(site_data)
    Path("site/index.html").write_text(html_text, encoding="utf-8")
    m = site_data["matchup"]
    if m:
        print(f"Matchup vs {m['opp_name']}: {m['me_now']:.1f}-{m['opp_now']:.1f}, win chance {m['p_win']*100:.0f}%")
    print(f"Saved site/index.html ({len(html_text)//1024} KB, {sum(len(t['players']) for t in site_data['teams'])} rostered players, "
          f"{len(site_data['fas'])} free agents)")


if __name__ == "__main__":
    main()
