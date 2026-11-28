
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
/* ESPN's status codes in plain words: injLabel = full ("Day-to-day"), injShort = for tight spots ("DTD") */
var INJ_TXT={DAY_TO_DAY:['Day-to-day','DTD'],OUT:['Out','OUT'],INJURY_RESERVE:['Injured reserve','IR'],SUSPENSION:['Suspended','SUSP']};
function injLabel(s){if(INJ_TXT[s])return INJ_TXT[s][0];var t=String(s||'').replace(/_/g,' ').toLowerCase();return t.charAt(0).toUpperCase()+t.slice(1);}
function injShort(s){return INJ_TXT[s]?INJ_TXT[s][1]:injLabel(s);}
/* weekly value over the next 4 weeks (per-game outlook x team games / 4), so one week's schedule never decides a trade */
function val(p){var g=(D.g28&&D.g28[p.tm]!=null)?D.g28[p.tm]/4:p.g7;return p.grp==='G'?(p.out||0)*g*(p.sp||0.5):(p.out||0)*g;}
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
var cOut={h:'Proj/gm',v:function(p){return p.out;},num:1,r:function(p){return f(p.out)+pcTag(p);}};
var cGP={h:'GP',v:function(p){return p.gp;},num:1};
var cG7={h:'Games left',v:function(p){return p.gl!=null?p.gl:p.g7;},num:1};
var cTOI={h:'TOI',v:function(p){return p.toi;},num:1,fmt:function(x){return f(x,1);}};var cPP={h:'PP min',v:function(p){return p.pp;},num:1,fmt:function(x){return f(x,1);}};var cXG={h:'G vs xG',v:function(p){return p.gx;},num:1,r:function(p){return p.gx==null?'-':'<span class="'+(p.gx>=2?'warn':(p.gx<=-2?'good':''))+'">'+sgn(p.gx,1)+'</span>';}};var cRole={h:'Role',v:function(p){return p.rl||'';},r:function(p){return p.rl?('<span class="'+(p.cls==='core'?'good':(p.cls==='watch'?'warn':(p.cls==='streamer'?'muted':'')))+'">'+esc(p.rl)+'</span>'+(p.cls?' <span class="muted">'+esc(p.cls)+'</span>':'')):'-';}};var cFlags={h:'Flags',v:function(p){return (p.fl||[]).join('; ');},r:flagsHtml};
var rosterCols=[cName,{h:'Slot',v:function(p){return p.slot;}},cGP,cPPG,{h:'Luck-adj',v:function(p){return p.exp;},num:1,fmt:f},cProj,cOut,cG7,cRole,cTOI,cPP,cXG,cFlags];
var faCols=[cName,cOut,{h:'vs your worst',v:function(p){return up(p);},num:1,r:function(p){var u=up(p);return '<span class="'+(u>=0.2?'good':(u<0?'bad':''))+'">'+sgn(u)+'</span>';}},
  cPPG,cProj,cGP,cG7,cRole,cTOI,cPP,cXG,{h:'Started',v:function(p){return p.pst;},num:1,r:function(p){return p.pst==null?'-':f(p.pst,0)+'%';}},{h:'Owned',v:function(p){return p.own;},num:1,r:function(p){return p.own==null?'-':f(p.own,0)+'%';}},{h:'Adds',v:function(p){return p.own_chg;},num:1,r:function(p){return pcTrend(p)||'<span class="muted">-</span>';}},
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
    h+='<div class="g"><div class="gh"><b>'+plink(p)+'</b><span class="muted">'+f(p.out)+' projected pts per start'+(p.svp?' &middot; save % '+f(p.svp,3):'')+'</span></div>';
    if(!g.rows.length)h+='<div class="muted">No games in the next few days.</div>';
    else{h+='<div class="chips">';
      g.rows.forEach(function(r){
        h+='<div class="chip"><div class="d">'+esc(r.day)+' &middot; '+esc(r.time)+'</div><div class="o">'+(r.home?'vs':'@')+' '+esc(r.opp)+'</div>'
        +'<div class="m">Win chance '+Math.round(r.p*100)+'% &middot; exp. '+sgn(r.e,1)+' pts</div>'
        +'<div style="margin-top:6px"><span class="pill '+r.cls+'">'+esc(r.verdict)+'</span></div></div>';});
      h+='</div>';}
    h+='</div>';});
  h+='<div class="muted" style="margin-top:8px">BENCH = expected points below zero. START (RISKY) = slightly positive but a big swing either way. NHL single games are close to coin flips, so treat win chances as leans. Confirmed starters come from DailyFaceoff.com for today only.</div></div>';
  h+='<div class="card"><h2>Suggested moves</h2>';
  if(D.moves.length){
    h+=mkTable([{h:'Add',v:function(m){return m.add.n;},r:function(m){return plink(m.add);}},
      {h:'Proj/gm',v:function(m){return m.add.out;},num:1,fmt:f},{h:'Games (7d)',v:function(m){return m.add.g7;},num:1},
      {h:'Drop',v:function(m){return m.drop.n;},r:function(m){return plink(m.drop);}},
      {h:'Proj/gm',v:function(m){return m.drop.out;},num:1,fmt:f},
      {h:'Gain/game',v:function(m){return m.gain;},num:1,r:function(m){return '<span class="good">'+sgn(m.gain)+'</span>';}},
      {h:'Gain (7d)',v:function(m){return m.wk;},num:1,r:function(m){return '<span class="good">'+sgn(m.wk,1)+'</span>';}}],D.moves);
    h+='<div class="muted">Players with very few games and no ESPN projection can look better than they are. Check small samples before acting.</div>';
  }else h+='<div class="muted">The role-aware plan is on the Streams tab. It accounts for lines, power plays, schedules and opponents.</div>';
  h+='</div><div class="card"><h2>Lineup alerts (today)</h2>';
  if(D.alerts.length)h+='<ul>'+D.alerts.map(function(a){return '<li class="'+a.k+'">'+esc(a.t)+'</li>';}).join('')+'</ul>';
  else h+='<div class="good">No lineup problems found.</div>';
  h+='</div>';
  $('#t-overview').innerHTML=h;
  $$('#t-overview table').forEach(function(t){wireSort(t.parentNode);});
}

/* ---------- roster ----------
   Two views, one segmented control:
   - Lineup (default): your lineup on one day of the matchup. A week strip on top (each day shows how full your lineup is),
     a short summary of that day, any lineup fix (a bench player has a game and a starter does not), then every player by
     lineup spot with his game that day: puck drop, live score, or final, and his projection or points (tap to see how they
     were made). Past days use ESPN's real lineup for that day (D.sb.dp); today uses live scores when they are in.
   - All stats: the full sortable table, as before.
   The week strip and the segmented control are built once and never rebuilt, so their selection pills slide (transform only). */
var R={pos:'All',q:'',view:'day',day:null};
try{R.view=localStorage.getItem('fh_rv')==='table'?'table':'day';}catch(e){}
var RD_SLOTS=[['F','Forwards'],['D','Defense'],['UTIL','Utility'],['G','Goalies'],['BN','Bench'],['IR','Injured reserve']];
function rdLineup(){var L=(D.rules&&D.rules.lineup)||{};return {F:L.F!=null?L.F:9,D:L.D!=null?L.D:5,UTIL:L.UTIL!=null?L.UTIL:1,G:L.G!=null?L.G:2};}
/* ESPN keeps a lineup for every day. S.fl[day] = your lineup that day (read from ESPN for today and later days);
   without it the current slots are used and the page says so. */
function rdKnown(i,S){return !!(S&&S.fl&&S.fl[String(i)])||i===rdT(S);}
/* a player's spot on day i: that day's ESPN lineup when it was read ('NA' = not on your roster that day, e.g. added or
   dropped after today's lock); otherwise his current spot. nx = joins your roster tomorrow (nextroster.py). */
function rdSl(p,i,S){var d=S&&S.fl&&S.fl[String(i)];if(d)return d[String(p.id)]||'NA';return p.nx&&i<=rdT(S)?'NA':p.slot;}
function rdAct(i,S){return function(p){return ['F','D','UTIL','G'].indexOf(rdSl(p,i,S))>=0;};}
/* the day to call "Today": the real date in New York once ESPN's day lags behind it after midnight */
function rdNow(S){var k=S&&S.dates?S.dates.indexOf(muEtd(Date.now())):-1;return k>=0?k:rdT(S);}
function rdT(S){return S?Math.min(S.today,S.dates.length-1):0;}
function rdGame(p,i,S){
  if(!S)return null;
  if(S.ws&&S.ws[p.tm])return S.ws[p.tm][i]||null;
  return (i===rdT(S)&&S.tn&&S.tn[p.tm])||null;
}
/* the live game (today's ESPN scoreboard) for a team, if it is the same game */
function rdLv(p,g){
  if(typeof LIVE==='undefined'||!LIVE||!LIVE.ev||!g)return null;
  var ab=lvAb(p.tm);
  for(var k=0;k<LIVE.ev.length;k++){var e=LIVE.ev[k];if((e.h.ab===ab||e.a.ab===ab)&&Math.abs(e.start-g[0])<6*3600e3)return e;}
  return null;
}
/* one player's day: game, state (none | up | live | final), whether he is not going to play, and points */
function rdState(p,i,S){
  var g=rdGame(p,i,S),t=rdT(S),o={g:g,st:'none',np:false,pts:null};
  if(!g)return o;
  o.np=BAD.indexOf(p.inj)>=0||(i===t&&p.grp==='G'&&!!p.ns);
  var now=Date.now();
  if(i>t){o.st='up';return o;}
  if(i<t){o.st='final';return o;}
  var e=rdLv(p,g);
  if(e&&e.st==='in')o.st='live';
  else if(e&&e.st==='post')o.st='final';
  else if(e&&e.st==='pre')o.st=now<g[0]+15*60e3?'up':'live';
  else o.st=now<g[0]?'up':(now<g[0]+3*3600e3?'live':'final');
  o.e=e;
  if(o.st!=='up'){
    var L=(typeof LIVE!=='undefined'&&LIVE&&LIVE.pts&&LIVE.pts[p.id])||null,sp=S.pt?S.pt[p.id]:null;
    o.pts=o.st==='final'&&sp!=null?sp:(L?Math.round(L.p*10)/10:(sp!=null?sp:null));
    if(L&&L.s&&o.st==='live')o.line=L.s;
  }
  return o;
}
function rdPlays(p,i,S){var s=rdState(p,i,S);return !!s.g&&!s.np;}
function rdGameTxt(p,s,i,S){
  var g=s.g,t=rdT(S);
  if(!g){
    if(i<t)return 'No game';
    var n=null;if(S&&S.ws&&S.ws[p.tm])for(var k=i+1;k<S.dates.length;k++)if(S.ws[p.tm][k]){n=k;break;}
    return n!=null?'No game &middot; next '+esc(dayShort(S.labels[n]).split(' ')[0]):'No more games this week';
  }
  var opp=(g[2]?'vs ':'@')+esc(g[1]);
  if(i>=t&&BAD.indexOf(p.inj)>=0)return opp+' &middot; <b class="rd-no">'+esc(injLabel(p.inj))+'</b>';
  if(i===t&&p.grp==='G'&&p.ns&&s.st==='up')return opp+' &middot; <b class="rd-no">Not starting</b>';
  var e=s.e;
  if(s.st==='live'){
    var sc='';if(e){var ab=lvAb(p.tm),me=e.h.ab===ab?e.h:e.a,ot=me===e.h?e.a:e.h;sc=' &middot; '+me.sc+'&ndash;'+ot.sc+(e.det?' &middot; '+esc(e.det):'');}
    return '<span class="sb-live"></span> '+opp+sc;
  }
  if(s.st==='final'){
    if(e&&e.st==='post'){var ab2=lvAb(p.tm),m2=e.h.ab===ab2?e.h:e.a,o2=m2===e.h?e.a:e.h;return opp+' &middot; '+(m2.sc>o2.sc?'W':'L')+' '+m2.sc+'&ndash;'+o2.sc;}
    return opp+' &middot; Final';
  }
  return opp+' &middot; '+(i===t?etTime(g[0]):esc(dayShort(S.labels[i]).split(' ')[0])+' '+etTime(g[0]));
}
function lastName(n){var w=String(n||'').trim().split(/\s+/);return w.length>1?w.slice(1).join(' '):n;}
/* recent form vs season (same test as the old roster list): only today and later, only with 6+ games */
function rdForm(p){
  if(p.rec==null||p.ppg==null||p.gp<6)return '';
  var d=p.rec-p.ppg;return d>=0.4?'<i class="rd-fm hot">Hot</i>':(d<=-0.4?'<i class="rd-fm cold">Cold</i>':'');
}
function rdInj(p){return (p.inj&&p.inj!=='ACTIVE')?'<i class="rd-inj">'+esc(injShort(p.inj))+'</i>':'';}
function rdRow(p,s,i,S,pts,bench){
  var off=!s.g||s.np||bench;
  var right;
  if(pts!=null)right=muNum(p.id,pts,i===rdT(S)?'t':'d'+i,pts<0?'mu-neg':'')+'<span class="rd-k'+(s.st==='live'?' lv':'')+'">'+(s.st==='live'?'live':(bench?'bench':'pts'))+'</span>';
  else if(s.g&&!s.np&&s.st==='up'&&p.out!=null)right='<b class="rd-pj">'+f(p.out,1)+'</b><span class="rd-k">proj</span>';
  else right='<b class="rd-dash">&ndash;</b>';
  return '<div class="row rd-r'+(off?' off':'')+'" data-rid="'+p.id+'">'+avHtml(p.id,p.tm)
    +'<div class="row-m"><div class="row-t rd-n"><a class="pl" data-noav="1" data-id="'+p.id+'">'+esc(p.n)+'</a>'+(i<rdT(S)&&p.slot!=='IR'?'':rdInj(p)+rdForm(p))+'</div>'
    +'<div class="row-s rd-s">'+esc(p.pos)+' '+esc(p.tm)+' &middot; '+rdGameTxt(p,s,i,S)+'</div></div>'
    +'<div class="rd-pt">'+right+'</div></div>';
}
function rdEmpty(lab){return '<div class="row rd-r rd-e"><span class="rd-ei">+</span><div class="row-m"><div class="row-t">Empty</div><div class="row-s">Open '+lab+' spot</div></div></div>';}
/* lineup fixes for a day that has not started: a healthy bench player has a game and someone in a spot he can fill does not */
function rdFixes(i,S){
  var t=rdT(S),mine=D.mine||[],L=rdLineup(),out=[],used={};
  if(i<t||!rdKnown(i,S))return out;
  var fits={F:['F','UTIL'],D:['D','UTIL'],G:['G']};
  var bench=mine.filter(function(p){var s=rdState(p,i,S);return p.grp!=='G'&&rdSl(p,i,S)==='BN'&&s.g&&!s.np&&s.st==='up';}).sort(function(a,b){return (b.out||0)-(a.out||0);});
  bench.forEach(function(b){
    var ok=fits[b.grp]||[],cand=null;
    ok.forEach(function(sl){
      if(cand)return;
      var have=mine.filter(function(p){return rdSl(p,i,S)===sl;});
      if(have.length<(L[sl]||0)){cand={empty:sl};return;}
      have.forEach(function(a){var s=rdState(a,i,S);if(!cand&&!used[a.id]&&(!s.g||s.np)&&(s.st==='up'||!s.g))cand={a:a,s:s};});
    });
    if(!cand)return;
    if(cand.a)used[cand.a.id]=1;
    out.push({b:b,a:cand.a,why:cand.a?(cand.s.np?(BAD.indexOf(cand.a.inj)>=0?injLabel(cand.a.inj).toLowerCase():'not starting'):'no game'):'',empty:cand.empty});
  });
  return out;
}
/* Lineup changes for a day (2026-11-27): the game-based fixes above, plus "both play, start the better one" on days with
   more of your skaters playing than spots. One list, used by Today's To do checklist and the Roster day view, so the two
   always agree. Each change: b = start him, a = bench him (or empty = the open spot), why = 'no game' | 'not starting' |
   an injury word | 'lower', gain = projected points the change adds that day. */
function tdVal(p,si,S,W){
  var C=D.clock,fi=C&&S?C.dates.indexOf(S.dates[si]):-1,w=W&&W[p.id];
  return (w&&w.v&&fi>=0&&w.v[fi]!=null)?w.v[fi]:(p.out||0);
}
/* Goalies (user, 2026-11-27: "I only have 2 starter goalie spots and it's suggesting I start all 3. It should tell me to
   start whichever 2 goalies have the best chance of winning. If only 1 has a good chance of winning or none, that's
   fine too"). Pick at most as many goalies as you have G spots, best first by projected points (start chance x win
   chance), and only goalies whose team is at least TD_GW to win (betting line, else the standings guess). Then: start a
   picked goalie who is on the bench, in an open G spot or in place of a G-spot goalie who wasn't picked. */
var TD_GW=0.5;
function tdWin(p,si,S,W){
  var C=D.clock,fi=C&&S?C.dates.indexOf(S.dates[si]):-1,w=W&&W[p.id];
  return (w&&w.w&&fi>=0&&w.w[fi]!=null)?w.w[fi]:null;
}
function tdGoalies(si,S,W,val){
  var nG=rdLineup().G,mine=D.mine||[];
  var gs=mine.filter(function(p){var sl=rdSl(p,si,S);return p.grp==='G'&&(sl==='G'||sl==='BN');});
  var up=function(p){var s=rdState(p,si,S);return !!s.g&&!s.np&&s.st==='up'&&BAD.indexOf(p.inj)<0;};
  var win=function(p){return tdWin(p,si,S,W);};
  var pick=gs.filter(function(p){var w=win(p);return up(p)&&val(p)>=0.1&&(w==null||w>=TD_GW);})
    .sort(function(a,b){return val(b)-val(a);}).slice(0,nG);
  var picked={};pick.forEach(function(p){picked[p.id]=1;});
  var inG=gs.filter(function(p){return rdSl(p,si,S)==='G';});
  var open=Math.max(0,nG-inG.length);
  /* G-spot goalies who weren't picked, the ones with no game first, then lowest value */
  var outs=inG.filter(function(p){return !picked[p.id];}).sort(function(a,b){return (up(a)?1:0)-(up(b)?1:0)||val(a)-val(b);});
  var res=[];
  pick.filter(function(p){return rdSl(p,si,S)==='BN';}).forEach(function(b){
    var x={b:b,g:1,wb:win(b)};
    if(open>0){open--;x.empty='G';x.gain=val(b);}
    else if(outs.length){
      var a=outs.shift(),s=rdState(a,si,S);x.a=a;x.wa=win(a);
      x.why=!s.g?'no game':(s.np?(BAD.indexOf(a.inj)>=0?injLabel(a.inj).toLowerCase():'not starting'):'lower');
      x.gain=val(b)-(up(a)?val(a):0);x.vb=val(b);x.va=val(a);
    }else return;
    if(x.why==='lower'&&x.gain<0.1)return;
    res.push(x);
  });
  return res;
}
function tdPct(w){return w==null?'':Math.round(w*100)+'% to win';}
function tdFixes(si,S){
  if(!S||si<0)return [];
  var W={};((D.streams&&D.streams.whatif&&D.streams.whatif.mine)||[]).forEach(function(p){W[p.id]=p;});
  var val=function(p){return tdVal(p,si,S,W);};
  var out=rdFixes(si,S).map(function(x){return {b:x.b,a:x.a,why:x.why,empty:x.empty,gain:val(x.b)};});
  if(si<rdT(S)||!rdKnown(si,S))return out;
  out=out.concat(tdGoalies(si,S,W,val));
  var used={};out.forEach(function(x){used[x.b.id]=1;if(x.a)used[x.a.id]=1;});
  var mine=(D.mine||[]).filter(function(p){return p.grp!=='G'&&!used[p.id];});
  var up=function(p){var s=rdState(p,si,S);return !!s.g&&!s.np&&s.st==='up';};
  var bench=mine.filter(function(p){return rdSl(p,si,S)==='BN'&&up(p);}).sort(function(a,b){return val(b)-val(a);});
  var fits={F:['F','UTIL'],D:['D','UTIL']};
  bench.forEach(function(b){
    var ok=fits[b.grp]||[],best=null;
    mine.forEach(function(a){if(used[a.id]||ok.indexOf(rdSl(a,si,S))<0||!up(a))return;if(!best||val(a)<val(best))best=a;});
    if(!best||val(b)-val(best)<0.1)return;
    used[b.id]=used[best.id]=1;
    out.push({b:b,a:best,why:'lower',gain:val(b)-val(best),vb:val(b),va:val(best)});
  });
  return out;
}
function tdKey(x,si,S){return 'lu'+x.b.id+'-'+(x.a?x.a.id:x.empty)+'@'+(S.dates[si]||si);}
/* one lineup change as a row, styled like a move row: who goes in (green arrow), who comes out (red arrow), why, points */
function tdRow(x,si,S,chk){
  var b=x.b,a=x.a,gb=rdGame(b,si,S),t=rdT(S),wb=lastName(b.n),wa=a?lastName(a.n):'',r;
  var when=gb?(gb[2]?'vs ':'@ ')+esc(gb[1])+(si===t?' at '+etTime(gb[0]):''):'';
  if(x.g&&x.why==='lower')r='Both play. '+esc(wb)+(x.wb!=null?'’s team is '+Math.round(x.wb*100)+'% to win'+(x.wa!=null?', '+esc(wa)+'’s '+Math.round(x.wa*100)+'%':'')+'.':' projects '+f(x.vb,1)+', '+esc(wa)+' '+f(x.va,1)+'.');
  else if(x.why==='lower')r='Both play. '+esc(wb)+' projects '+f(x.vb,1)+', '+esc(wa)+' '+f(x.va,1)+'.';
  else if(x.g&&!a)r=esc(wb)+' plays '+when+(x.wb!=null?', '+tdPct(x.wb):'')+'. Your G spot is open.';
  else if(!a)r=esc(wb)+' plays '+when+'. Your '+(x.empty==='UTIL'?'utility':x.empty)+' spot is empty.';
  else if(x.why==='no game')r=esc(wb)+' plays '+when+'. '+esc(wa)+' has no game.';
  else if(x.why==='not starting'){var al=(D.alerts||[]).filter(function(q){return q.t.indexOf(a.n)>=0;})[0],m=al&&/\(([^)]+)\)/.exec(al.t);
    r=esc(wa)+' isn’t starting'+(m?' ('+esc(m[1])+')':'')+'. '+esc(wb)+' plays '+when+'.';}
  else r=esc(wa)+' is '+esc(x.why)+'. '+esc(wb)+' plays '+when+'.';
  var k=chk?tdKey(x,si,S):'',on=chk&&TD.on(k);
  return '<div class="row mvr gpr td'+(chk?' chk':'')+(on?' done':'')+'"'+(chk?' data-tdk="'+k+'"':'')+'>'
    +(chk?tdBox(k,on):'')
    +'<span class="mvr-av">'+glAv(b,'add','up')+(a?glAv(a,'drop','dn'):'<span class="rav td-e"></span>')+'</span>'
    +'<div class="row-m"><div class="gpr-h"><div class="row-t">Start <a class="pl" data-noav="1" data-id="'+b.id+'">'+esc(wb)+'</a></div>'
    +(x.gain>=0.05?'<span class="gpr-p">+'+f(x.gain,1)+'<small>pts</small></span>':'')+'</div>'
    +'<div class="gpr-d">'+(a?'Bench <a class="pl" data-noav="1" data-id="'+a.id+'">'+esc(wa)+'</a>':'In your open '+(x.empty==='UTIL'?'utility':x.empty)+' spot')+'</div>'
    +'<div class="gpr-w">'+r+'</div></div></div>';
}
/* Today's checklist: tap the circle when it's done. Saved on this phone only; ESPN has the final word: if an update newer
   than the tap (90 s grace) still shows the item, the check clears so a change that didn't save in ESPN shows up again. */
var TD=(function(){
  var K='fh_todo';
  function all(){try{return JSON.parse(localStorage.getItem(K)||'{}')||{};}catch(e){return {};}}
  function on(k){var t=all()[k],b=(D.clock&&D.clock.built)||0;return !!t&&!(b>t+90000);}
  function set(k,v){var o=all(),now=Date.now();for(var q in o)if(now-o[q]>3*864e5)delete o[q];if(v)o[k]=now;else delete o[k];try{localStorage.setItem(K,JSON.stringify(o));}catch(e){}}
  return {on:on,set:set};
})();
function tdBox(k,on){
  return '<button type="button" class="tdc'+(on?' on':'')+'" data-chk="'+k+'" role="checkbox" aria-checked="'+(on?'true':'false')+'" aria-label="Done">'
    +'<svg viewBox="0 0 28 28"><circle class="o" cx="14" cy="14" r="11"/><circle class="f" cx="14" cy="14" r="12"/><path class="k" d="M9.2 14.3l3.3 3.2 6.4-6.8"/></svg></button>';
}
function tdToggle(btn){
  var k=btn.getAttribute('data-chk'),on=!btn.classList.contains('on');
  TD.set(k,on);
  $$('[data-chk="'+k+'"]').forEach(function(b){b.classList.toggle('on',on);b.setAttribute('aria-checked',on?'true':'false');var r=b.closest('.row');if(r)r.classList.toggle('done',on);});
  if(on&&navigator.vibrate)try{navigator.vibrate(8);}catch(e){}
}
function rdStrip(S){
  var n=S.dates.length,t=rdT(S),tn=rdNow(S),L=rdLineup(),tot=L.F+L.D+L.UTIL+L.G;
  var h='<div class="rd-days" id="rdDays" style="--n:'+n+'" role="tablist" aria-label="Matchup day"><span class="rd-sel" id="rdSel"></span>';
  S.dates.forEach(function(d,k){
    var act=(D.mine||[]).filter(rdAct(k,S)),lab=String(S.labels[k]||'').split(' '),c=act.filter(function(p){return rdPlays(p,k,S);}).length,fr=tot?Math.min(1,c/tot):0;
    h+='<button type="button" class="rd-d'+(k===tn&&!S.done?' t':'')+(k<tn?' past':'')+'" data-rday="'+k+'" role="tab" aria-label="'+esc(S.labels[k])+', '+c+' of '+tot+' lineup spots have a game">'
      +'<span class="rd-dn">'+esc(k===tn&&!S.done?'Today':lab[0])+'</span><span class="rd-dd">'+esc(lab[2]||'')+'</span><span class="rd-m"><i style="transform:scaleX('+fr.toFixed(3)+')"></i></span></button>';
  });
  return h+'</div>';
}
function rdSum(i,S){
  var t=rdT(S),act=(D.mine||[]).filter(rdAct(i,S)),L=rdLineup(),tot=L.F+L.D+L.UTIL+L.G;
  var st=act.map(function(p){return {p:p,s:rdState(p,i,S)};}),on=st.filter(function(x){return x.s.g&&!x.s.np;});
  function tile(v,k,cls){return '<div class="rd-tile"><b class="'+(cls||'')+'">'+v+'</b><span>'+k+'</span></div>';}
  var me=(D.teams.filter(function(x){return x.me;})[0]||{}).id,mg=null;
  (S.games||[]).forEach(function(g){if(!mg&&(g.a===me||g.b===me))mg=g;});
  var dayPts=mg?(mg.a===me?mg.ad[i]:mg.bd[i]):null;
  var first=on.map(function(x){return x.s.g[0];}).sort()[0];
  var h='<div class="rd-sum">';
  if(i<t){
    var dp=S.dp&&S.dp[String(i)]&&S.dp[String(i)][String(me)];
    var pl=dp?dp.filter(function(e){return e[1]!=='BN'&&e[1]!=='IR'&&S.ws&&S.ws[e[5]]&&S.ws[e[5]][i];}).length:on.length;
    h+=tile(dayPts==null?'&ndash;':f(dayPts,1),'points')+tile(pl,'played')+(function(){var op=mg?(mg.a===me?mg.bd[i]:mg.ad[i]):null;if(dayPts==null||op==null)return tile('&ndash;','vs opponent');var d=dayPts-op;return tile(sgn(d,1),'vs opponent',d>0?'ok':(d<0?'neg':''));})();
  }else{
    var proj=0,got=0,any=false;
    on.forEach(function(x){if(x.s.st==='up')proj+=(x.p.out||0);else{any=true;if(x.s.pts!=null)got+=x.s.pts;}});
    h+=tile(on.length+'<i>/'+tot+'</i>','playing',on.length<tot?'':'ok');
    if(i===t&&any)h+=tile(f(dayPts!=null&&dayPts>got?dayPts:got,1),'points so far')+tile(f(proj,1),'still to come');
    else h+=tile(f(proj,1),'projected')+tile(first?etTime(first).replace(':00',''):'&ndash;',first?'first game':'no games');
  }
  return h+'</div>';
}
function rdBody(i,S){
  var t=rdT(S),h=rdSum(i,S),L=rdLineup();
  var fx=tdFixes(i,S);
  if(fx.length)h+='<div class="grp rd-fix">'+fx.map(function(x){return tdRow(x,i,S,false);}).join('')+'</div>';
  var past=i<t,dp=past&&S.dp&&S.dp[String(i)],me=(D.teams.filter(function(x){return x.me;})[0]||{}).id,rows=dp&&dp[String(me)];
  if(past&&rows){
    var by={};rows.forEach(function(e){var sl=e[1]==='UTIL'?'UTIL':e[1];(by[sl]=by[sl]||[]).push(e);});
    RD_SLOTS.forEach(function(sc){
      var L2=(by[sc[0]]||[]).slice().sort(function(a,b){return b[2]-a[2];});if(!L2.length)return;
      var bn=sc[0]==='BN'||sc[0]==='IR';
      h+='<div class="rd-sec"><span>'+sc[1]+'</span><span class="rd-sr">'+(bn?'did not count':f(L2.reduce(function(s,e){return s+e[2];},0),1)+' pts')+'</span></div><div class="grp">';
      h+=L2.map(function(e){
        var k=ALL[e[0]],p=k||{id:e[0],n:e[3],pos:e[4],tm:e[5],grp:e[4]==='G'?'G':e[4]==='D'?'D':'F'};
        var s=rdState(p,i,S);return rdRow(p,s,i,S,(s.g&&e[1]!=='IR')||e[2]?e[2]:null,bn);
      }).join('')+'</div>';
    });
    return h+'<div class="rd-note">ESPN\'s lineup for '+esc(S.labels[i])+'. Bench points did not count. Tap a score to see how it was made.</div>';
  }
  var mine=D.mine||[];
  RD_SLOTS.forEach(function(sc){
    var ps=mine.filter(function(p){return rdSl(p,i,S)===sc[0];});
    var need=L[sc[0]]||0,empty=sc[0]!=='BN'&&sc[0]!=='IR'?Math.max(0,need-ps.length):0;
    if(!ps.length&&!empty)return;
    var st=ps.map(function(p){return {p:p,s:rdState(p,i,S)};});
    st.sort(function(a,b){var x=a.s.g&&!a.s.np?0:1,y=b.s.g&&!b.s.np?0:1;return (x-y)||((a.s.g?a.s.g[0]:0)-(b.s.g?b.s.g[0]:0))||((b.p.out||0)-(a.p.out||0));});
    var on=st.filter(function(x){return x.s.g&&!x.s.np;}).length,lineup=sc[0]!=='BN'&&sc[0]!=='IR';
    h+='<div class="rd-sec"><span>'+sc[1]+'</span><span class="rd-sr">'+(lineup?on+' of '+(ps.length+empty)+' playing':(sc[0]==='BN'&&on?on+' with a game':''))+'</span></div><div class="grp">';
    h+=st.map(function(x){return rdRow(x.p,x.s,i,S,x.s.pts,!lineup);}).join('');
    for(var k=0;k<empty;k++)h+=rdEmpty(sc[0]==='UTIL'?'utility':sc[0]);
    h+='</div>';
  });
  var note=past?'ESPN\'s lineup for this day is not available, so this is your roster now.':
    (!rdKnown(i,S)?'ESPN\'s lineup for '+esc(S.labels[i])+' could not be read, so this shows today\'s lineup. Gray numbers are projections.':
    (i===t?'Gray numbers are projections. Tap a score to see how it was made.':'Your lineup for '+esc(S.labels[i])+' as set in ESPN. Gray numbers are projections.'));
  return h+'<div class="rd-note">'+note+'</div>';
}
function rdPill(i,n,anim){
  var el=document.getElementById('rdSel');if(!el)return;
  if(!anim)el.classList.add('nt');
  el.style.transform='translateX('+(i*100)+'%)';
  if(!anim){void el.offsetWidth;el.classList.remove('nt');}
  $$('#rdDays .rd-d').forEach(function(b){var on=+b.getAttribute('data-rday')===i;b.classList.toggle('on',on);b.setAttribute('aria-selected',on?'true':'false');});
}
function rdPaint(dir){
  var S=D.sb,b=document.getElementById('rdBody');if(!S||!b)return;
  b.innerHTML=rdBody(R.day,S);
  if(dir&&!RM){b.classList.remove('in-r','in-l');void b.offsetWidth;b.classList.add(dir>0?'in-r':'in-l');}
}
function rdDay(i){
  var S=D.sb;if(!S||i===R.day||i<0||i>=S.dates.length)return;
  var dir=i>R.day?1:-1;R.day=i;rdPill(i,S.dates.length,true);rdPaint(dir);
}
/* Swipe the list sideways to move a day. The selection pill follows the finger (transform only, passive listeners,
   no layout reads while moving: the width is read once at touchstart); the list gives a little with the drag. */
var RSW=null;
document.addEventListener('touchstart',function(e){
  var b=e.target&&e.target.closest&&e.target.closest('#rdBody');RSW=null;
  if(!b||!D.sb||e.touches.length!==1||e.target.closest('.mu-bk'))return;
  var t=e.touches[0];RSW={x:t.clientX,y:t.clientY,dx:0,lock:0,w:b.offsetWidth||360,b:b,sel:document.getElementById('rdSel')};
},{passive:true});
document.addEventListener('touchmove',function(e){
  var g=RSW;if(!g)return;
  var t=e.touches[0],dx=t.clientX-g.x,dy=t.clientY-g.y;
  if(!g.lock){if(Math.abs(dx)<8&&Math.abs(dy)<8)return;g.lock=Math.abs(dx)>Math.abs(dy)*1.3?1:-1;
    if(g.lock>0){if(g.sel)g.sel.classList.add('nt');g.b.classList.remove('in-r','in-l');g.b.classList.add('rd-drag');}}
  if(g.lock<0)return;
  var n=D.sb.dates.length,i=R.day,edge=(dx>0&&i===0)||(dx<0&&i===n-1);
  g.dx=edge?dx*0.25:dx;
  if(g.sel)g.sel.style.transform='translateX('+((i-g.dx/g.w)*100)+'%)';
  g.b.style.transform='translate3d('+(g.dx*0.3)+'px,0,0)';
},{passive:true});
function rdSwEnd(){
  var g=RSW;RSW=null;if(!g||g.lock<1)return;
  if(g.sel){void g.sel.offsetWidth;g.sel.classList.remove('nt');}
  g.b.classList.remove('rd-drag');g.b.style.transform='';
  var n=D.sb.dates.length,j=R.day+(g.dx<-50?1:(g.dx>50?-1:0));
  if(j!==R.day&&j>=0&&j<n)rdDay(j);else rdPill(R.day,n,true);
}
document.addEventListener('touchend',rdSwEnd,{passive:true});
document.addEventListener('touchcancel',rdSwEnd,{passive:true});
/* fresh live scores: repaint today in place, unless a score breakdown is open */
function rdLive(){
  var S=D.sb;if(!S||R.view!=='day'||R.day!==rdT(S))return;
  var b=document.getElementById('rdBody');if(!b||b.querySelector('.mu-bk'))return;
  b.innerHTML=rdBody(R.day,S);
}
function rdSeg(){
  var sg=document.getElementById('rosterSeg');if(!sg)return;
  if(!sg.firstChild)sg.innerHTML='<div class="pcseg rd-seg"><span class="th"></span><button type="button" data-rv="day">Lineup</button><button type="button" data-rv="table">All stats</button></div>';
  var p=sg.firstChild;p.classList.toggle('two',R.view==='table');
  $$('button',p).forEach(function(x){x.classList.toggle('on',x.getAttribute('data-rv')===R.view);});
}
function rosterRender(){
  rdSeg();
  var ctl=document.getElementById('rosterCtl'),box=$('#rosterTbl'),S=D.sb;
  if(ctl)ctl.style.display=R.view==='table'?'':'none';
  if(R.view==='day'&&S&&S.dates&&S.dates.length){
    if(R.day==null)R.day=rdNow(S);
    box.innerHTML=rdStrip(S)+'<div id="rdBody" class="rd-body"></div>';
    rdPill(R.day,S.dates.length,false);rdPaint(0);
    return;
  }
  if(R.view==='day'){box.innerHTML='<div class="rd-note">Your day-by-day lineup shows up after the next data refresh.</div>';return;}
  chips('#rosterPos',['All','F','D','G'],R.pos,function(v){R.pos=v;rosterRender();});
  var rows=D.mine.filter(function(p){return (R.pos==='All'||p.grp===R.pos)&&(!R.q||p.n.toLowerCase().indexOf(R.q)>=0);});
  box.innerHTML='<div class="rd-tbl">'+mkTable(rosterCols,rows)+'</div><div class="rd-note">PPG = points per game so far. Luck-adj = what he would average if puck luck evened out. Proj = ESPN\'s projection. Proj/gm = our projection, used for every suggestion. Games left = games left in this matchup week.</div>';
  wireSort(box);
}
document.addEventListener('click',function(e){
  var t=e.target;if(!t||!t.closest)return;
  var b=t.closest('[data-rv]');
  if(b){var v=b.getAttribute('data-rv');if(v!==R.view){R.view=v;try{localStorage.setItem('fh_rv',v);}catch(x){}rosterRender();}return;}
  var d=t.closest('[data-rday]');if(d){rdDay(+d.getAttribute('data-rday'));return;}
  var r=t.closest('.rd-r[data-rid]');
  if(r&&!t.closest('.mu-nb,a.pl')){var p=ALL[r.getAttribute('data-rid')];if(p)modal(p);}
});

/* ---------- free agents ---------- */
var FA={pos:'Skaters',q:'',hide:true,games:false,n:50};
function faRender(){
  chips('#faPos',['Skaters','F','D','G'],FA.pos,function(v){FA.pos=v;faRender();});
  var rows=D.fas.filter(function(p){return (FA.pos==='Skaters'?p.grp!=='G':p.grp===FA.pos)&&(!FA.q||p.n.toLowerCase().indexOf(FA.q)>=0)&&(!FA.hide||!isInj(p))&&(!FA.games||(p.gl!=null?p.gl:p.g7)>0);});
  rows.sort(function(a,b){return b.out-a.out;});
  var total=rows.length;rows=rows.slice(0,FA.n);
  $('#faTbl').innerHTML=mkTable(faCols,rows)+'<div class="muted">Showing '+rows.length+' of '+total+'. Proj/gm = projected points per game (per start for goalies). vs your worst = that minus your weakest active player at the same position. Goalies are listed separately because a start is not comparable to a skater\'s game.</div>';
  wireSort($('#faTbl'));
}

/* ---------- trade lab ---------- */
function ownerTeam(id){return D.teams.filter(function(t){return t.players.some(function(x){return x.id===id;});})[0];}
function onBlock(p){var t=ownerTeam(p.id);return !!(t&&!t.me&&t.block&&t.block.indexOf(p.id)>=0);}
function listHtml(ps){
  return ps.slice().sort(function(a,b){return b.out-a.out;}).map(function(p){
    var sub=esc(p.pos)+' &middot; '+esc(p.tm)+(p.slot==='IR'?' &middot; IR':'')+(p.inj&&p.inj!=='ACTIVE'?' &middot; '+esc(injShort(p.inj)):'');
    return '<label class="opt tl-row"><input type="checkbox" value="'+p.id+'"><span class="tl-av">'+avHtml(p.id,p.tm)+'</span><span class="tl-nm"><b>'+esc(p.n)+'</b><span>'+sub+(onBlock(p)?' <i class="tag">on block</i>':'')+'</span></span><span class="tl-pt">'+f(p.out)+'<i>pts/gm</i></span></label>';}).join('');
}
function theTeam(){var id=$('#tradeTeam').value;return D.teams.filter(function(t){return String(t.id)===id;})[0];}
function checked(sel){return $$(sel+' input:checked').map(function(c){return +c.value;});}
function tradeTeam(){var t=theTeam();$('#getList').innerHTML=t?listHtml(t.players):'';runTrade();}
function box(t,v){return '<div class="box"><div class="t">'+t+'</div><div class="v">'+v+'</div></div>';}
function delta(d){return '<span class="'+(d>0.5?'good':(d<-0.5?'bad':''))+'">'+sgn(d,1)+'</span>';}
function tlCount(){
  var g=checked('#giveList').length,r=checked('#getList').length;
  var a=$('#tlGn'),b=$('#tlRn');if(a)a.textContent=g?g:'';if(b)b.textContent=r?r:'';
  var rs=$('#tlReset');if(rs)rs.hidden=!(g||r);
}
function tlTile(name,b,a,d){
  var cls=d>0.5?'good':(d<-0.5?'bad':'');
  return '<div class="tl-tile"><div class="tl-k">'+name+'</div><div class="tl-v">'+f(a,1)+'</div><div class="tl-d '+cls+'">'+sgn(d,1)+' pts/wk</div><div class="tl-s">now '+f(b,1)+'</div></div>';
}
function tlNames(ids,list){
  var n=ids.map(function(id){var p=list.filter(function(x){return x.id===id;})[0];return p?shortName(p.n):'';}).filter(Boolean);
  return n.length?esc(n.join(', ')):'<span class="muted">nobody yet</span>';
}
function runTrade(){
  var t=theTeam(),out=$('#tradeOut');
  var give=checked('#giveList'),get=checked('#getList');
  tlCount();
  if(!t||(!give.length&&!get.length)){out.innerHTML='<div class="tl-empty"><b>Build a trade</b><span>Pick players below on each side and the effect on both lineups shows up here.</span></div>';return;}
  var mine=D.mine,theirs=t.players;
  var myAfter=mine.filter(function(p){return give.indexOf(p.id)<0;}).concat(theirs.filter(function(p){return get.indexOf(p.id)>=0;}));
  var thAfter=theirs.filter(function(p){return get.indexOf(p.id)<0;}).concat(mine.filter(function(p){return give.indexOf(p.id)>=0;}));
  var b1=lineupWithFA(mine,1),a1=lineupWithFA(myAfter,1+Math.max(0,give.length-get.length)),b2=lineupWithFA(theirs,1),a2=lineupWithFA(thAfter,1+Math.max(0,get.length-give.length));
  var d1=a1-b1,d2=a2-b2,v,vc;
  if(d1>0.5&&d2>0.5){v='Win-win: it helps both lineups, so they might accept.';vc='ok';}
  else if(d1>0.5&&d2<=0.5){v='Helps you but costs them about '+f(-d2,1)+' pts/week, so they may decline.';vc='wn';}
  else if(d1<=0.5&&d2>0.5){v='Helps them more than you. You would lose about '+f(Math.max(0,-d1),1)+' pts/week.';vc='bd';}
  else{v='Little change for either side.';vc='gy';}
  var size=myAfter.length,note='';
  if(size>22)note='<div class="tl-note warn">You would have '+size+' players and need to drop '+(size-22)+'.</div>';
  else if(size<22)note='<div class="tl-note">You would have '+(22-size)+' open roster spot'+(22-size===1?'':'s')+'.</div>';
  out.innerHTML='<div class="tl-res">'+tlTile('You',b1,a1,d1)+tlTile(esc(t.name),b2,a2,d2)+'</div>'
    +'<div class="tl-verdict v-'+vc+'">'+esc(v)+'</div>'
    +'<div class="tl-sum"><div><span>You give</span>'+tlNames(give,mine)+'</div><div><span>You get</span>'+tlNames(get,theirs)+'</div></div>'+note
    +'<details class="tl-how"><summary>How this is calculated</summary><div class="muted">Points per week over the next 4 weeks: each player\'s projected points per game times his team\'s games, using each team\'s best lineup (9 F, 5 D, 1 UTIL, 2 G). It does not know what a manager actually needs, so treat it as a starting point.</div></details>';
}
/* ---------- trading block + trade finder ---------- */
var TF={id:null,q:''};
function pl2(p){return '<a class="pl" data-id="'+p.id+'">'+esc(p.n)+'</a> <span class="muted">'+esc(p.pos)+'</span>';}
function blockRender(){
  var h='',n=0;
  D.teams.forEach(function(t){
    if(t.me||!t.block||!t.block.length)return;
    var ps=t.players.filter(function(p){return t.block.indexOf(p.id)>=0;});
    if(!ps.length)return;
    n+=ps.length;
    h+='<div class="tfh">'+esc(t.name)+'</div>';
    ps.sort(function(a,b){return b.out-a.out;}).forEach(function(p){
      h+='<div class="tfr"><div class="sm">'+pl2(p)+' <span class="muted">'+esc(p.tm)+'</span><div class="muted">'+f(p.out)+' projected pts/game &middot; '+((D.g28&&D.g28[p.tm]!=null)?D.g28[p.tm]+' games next 4 weeks':p.g7+' games next 7 days')+'</div></div>'
        +'<div class="sr"><button type="button" class="chip-btn" data-tf="'+p.id+'">Find offers</button></div></div>';});
  });
  if(!n)h='<div class="muted">Nobody in your league has players on the trading block right now.</div>';
  else h+='<div class="muted" style="margin-top:8px">These are the players other managers have marked as available in ESPN. Tap Find offers to see trades that would help you without hurting them.</div>';
  $('#blockOut').innerHTML=h;
}
var BC={};
function lineupBase(key,players){if(BC[key]==null)BC[key]=lineupWithFA(players,1);return BC[key];}
function okP(p){return p.slot!=='IR'&&!isInj(p);}
function topFA(){
  if(BC.fa)return BC.fa;var o=[];
  ['F','D','G'].forEach(function(g){o=o.concat(D.fas.filter(function(p){return p.grp===g&&!isInj(p);}).sort(function(a,b){return val(b)-val(a);}).slice(0,4));});
  return BC.fa=o;
}
/* best lineup after picking up to k free agents (one for a normal add/drop, more when a trade frees roster spots).
   Both sides of every comparison get the same chance, so a trade never gets credit for a pickup you could make anyway. */
function lineupWithFA(ps,k){
  var cur=ps.slice(),best=lineup(cur),used={};
  for(var n=0;n<k;n++){
    var top=null,tv=best;
    topFA().forEach(function(f){if(used[f.id])return;var v=lineup(cur.concat([f]));if(v>tv+0.01){tv=v;top=f;}});
    if(!top)break;used[top.id]=1;cur.push(top);best=tv;
  }
  return best;
}
function swapEval(give,thTeam,get){
  var mine=D.mine,theirs=thTeam.players;
  var gi=give.map(function(p){return p.id;}),ge=get.map(function(p){return p.id;});
  var myAfter=mine.filter(function(p){return gi.indexOf(p.id)<0;}).concat(get);
  var thAfter=theirs.filter(function(p){return ge.indexOf(p.id)<0;}).concat(give);
  return {give:give,get:get,team:thTeam,
    d1:lineupWithFA(myAfter,1+Math.max(0,give.length-get.length))-lineupBase('me',mine),
    d2:lineupWithFA(thAfter,1+Math.max(0,get.length-give.length))-lineupBase('t'+thTeam.id,theirs)};
}
function topN(ps,n){return ps.filter(okP).sort(function(a,b){return val(b)-val(a);}).slice(0,n);}
function pairs(ps){var o=[];for(var i=0;i<ps.length;i++)for(var j=i+1;j<ps.length;j++)o.push([ps[i],ps[j]]);return o;}
function suggestFor(p){
  var ot=ownerTeam(p.id);if(!ot)return null;
  var rows=[],myOk=D.mine.filter(okP);
  if(ot.me){
    D.teams.forEach(function(t){
      if(t.me)return;
      var cand=topN(t.players,10);
      t.players.forEach(function(q){if(okP(q))rows.push(swapEval([p],t,[q]));});            /* 1-for-1 */
      cand.forEach(function(q){myOk.forEach(function(m){if(m.id!==p.id)rows.push(swapEval([p,m],t,[q]));});});   /* you give 2, get 1 */
      pairs(cand).forEach(function(c){rows.push(swapEval([p],t,c));});                       /* you give 1, get 2 */
    });
  }else{
    var cand=topN(ot.players,10).filter(function(q){return q.id!==p.id;}),mo=topN(D.mine,12);
    myOk.forEach(function(m){rows.push(swapEval([m],ot,[p]));});
    pairs(mo).forEach(function(c){rows.push(swapEval(c,ot,[p]));});
    mo.forEach(function(m){cand.forEach(function(q){rows.push(swapEval([m],ot,[p,q]));});});
  }
  rows.forEach(function(r){
    r.blk=r.give.concat(r.get).some(onBlock);r.sc=r.d1+(r.blk?1:0)-(r.give.length+r.get.length>2?0.3:0);
    r.kind=r.give.length+'-for-'+r.get.length;
  });
  function pick(list,n){   /* best few, at most 3 of the same kind so 1-for-1 and 2-for-1 both show up */
    var cnt={},o=[];list.sort(function(a,b){return b.sc-a.sc;}).forEach(function(r){
      if(o.length>=n||(cnt[r.kind]||0)>=3)return;cnt[r.kind]=(cnt[r.kind]||0)+1;o.push(r);});return o;}
  function need(r){return r.give.length+r.get.length>2?1.0:0.5;}   /* uneven deals must clearly help you */
  var wins=pick(rows.filter(function(r){return r.d1>=need(r)&&r.d2>=0.5;}),7);
  var tilt=pick(rows.filter(function(r){return r.d1>=need(r)&&r.d2<0.5&&r.d2>-1.5;}),5);
  return {mine:!!ot.me,owner:ot,wins:wins,tilt:tilt};
}
function plist(ps){return ps.map(pl2).join(' + ');}
function sugRow(r){
  var net=r.get.length-r.give.length,note=net>0?' &middot; <span class="muted">you would need to drop '+net+'</span>':(net<0?' &middot; <span class="muted">frees a roster spot (filled with the best free agent)</span>':'');
  return '<div class="tfr"><div class="sm"><span class="tag" style="background:var(--accent)">'+r.kind+'</span> <b>Give</b> '+plist(r.give)+' <b>for</b> '+plist(r.get)+'<div class="muted">'+esc(r.team.name)+(r.blk?' &middot; <span class="tag">on block</span>':'')+note+'</div></div>'
    +'<div class="sr"><span>You '+delta(r.d1)+' <span class="muted">/ them</span> '+delta(r.d2)+' <span class="muted">pts/wk</span></span>'
    +'<button type="button" class="chip-btn" data-open="'+r.give.map(function(p){return p.id;}).join('+')+','+r.get.map(function(p){return p.id;}).join('+')+','+r.team.id+'">Open in lab</button></div></div>';
}
function finderRender(){
  var res=$('#finderRes'),out=$('#finderOut'),q=TF.q.trim().toLowerCase(),h='';
  if(q.length>=2){
    var hits=[];
    D.teams.forEach(function(t){t.players.forEach(function(p){if(p.n.toLowerCase().indexOf(q)>=0)hits.push({p:p,t:t});});});
    hits=hits.slice(0,8);
    h=hits.length?hits.map(function(x){return '<button type="button" class="chip-btn" data-tf="'+x.p.id+'">'+esc(x.p.n)+' <span class="muted">'+esc(x.p.pos)+' &middot; '+(x.t.me?'your team':esc(x.t.name))+'</span></button>';}).join(''):'<span class="muted">No players found.</span>';
  }
  res.innerHTML=h;
  var p=TF.id?ALL[TF.id]:null;
  if(!p||!ownerTeam(p.id)){out.innerHTML='<div class="muted">Search for a player on your team (to see who could take him and what you could ask for) or on another team (to see what you could offer for him).</div>';return;}
  var S=suggestFor(p),t='';
  t+='<div class="verdict">'+(S.mine?'Where could you move ':'What could you offer for ')+esc(p.n)+'?'+(onBlock(p)?' <span class="tag">on '+esc(S.owner.name)+'\'s block</span>':'')+'</div>';
  if(S.wins.length){t+='<div class="tfh">Win-win swaps (help both lineups)</div>'+S.wins.map(sugRow).join('');}
  else t+='<div class="muted" style="margin-top:8px">No trade I tried helps both lineups right now.</div>';
  if(S.tilt.length)t+='<div class="tfh">Helps you more (they may want a sweetener)</div>'+S.tilt.map(sugRow).join('');
  t+='<div class="muted" style="margin-top:8px">Includes 1-for-1, 2-for-1 and 1-for-2 deals, using the same estimate as the Trade lab below: points per week over the next 4 weeks, not just this week (a freed roster spot is filled with the best free agent; a 2-for-1 must help you by at least 1 point a week). Players on a manager\'s block are ranked higher. Open in lab to tweak a deal.</div>';
  out.innerHTML=t;
}
function openInLab(give,get,tid){
  give=[].concat(give);get=[].concat(get);
  $('#tradeTeam').value=String(tid);tradeTeam();
  $$('#giveList input').forEach(function(c){c.checked=give.indexOf(+c.value)>=0;});
  $$('#getList input').forEach(function(c){c.checked=get.indexOf(+c.value)>=0;});
  runTrade();
  var el=$('#tradeOut');if(el&&el.scrollIntoView)el.scrollIntoView({behavior:'smooth',block:'center'});
}
function tradeInit(){
  var sel=$('#tradeTeam');
  sel.innerHTML=D.teams.filter(function(t){return !t.me;}).map(function(t){return '<option value="'+t.id+'">'+esc(t.name)+'</option>';}).join('');
  $('#giveList').innerHTML=listHtml(D.mine);
  sel.addEventListener('change',tradeTeam);
  $('#giveList').addEventListener('change',runTrade);$('#getList').addEventListener('change',runTrade);
  var rs=$('#tlReset');
  if(rs)rs.addEventListener('click',function(){
    $$('#giveList input:checked,#getList input:checked').forEach(function(c){c.checked=false;});
    runTrade();
  });
  var seg=$('#tlSeg');
  if(seg)seg.addEventListener('click',function(e){
    var b=e.target.closest?e.target.closest('[data-tls]'):null;if(!b)return;
    var k=b.getAttribute('data-tls');
    seg.classList.toggle('two',k==='get');
    $$('button',seg).forEach(function(x){x.classList.toggle('on',x===b);});
    $('#giveList').hidden=(k!=='give');$('#getList').hidden=(k!=='get');
  });
  tradeTeam();
  blockRender();finderRender();
  $('#finderQ').addEventListener('input',function(){TF.q=this.value;finderRender();});
  document.addEventListener('click',function(e){
    var b=e.target.closest?e.target.closest('[data-tf],[data-open]'):null;if(!b)return;
    if(b.hasAttribute('data-tf')){TF.id=+b.getAttribute('data-tf');TF.q='';$('#finderQ').value='';finderRender();
      var c=$('#finderOut');if(c&&c.scrollIntoView)c.scrollIntoView({behavior:'smooth',block:'start'});}
    else{var pr=b.getAttribute('data-open').split(',');openInLab(pr[0].split('+').map(Number),pr[1].split('+').map(Number),+pr[2]);}
  });
}

/* ---------- league ---------- */
function leagueRender(){
  var rows=D.teams.map(function(t){return {id:t.id,name:t.name,logo:t.logo,rec:t.rec,w:t.w,pf:t.pf,me:t.me,power:lineup(t.players)};});
  rows.sort(function(a,b){return b.power-a.power;});rows.forEach(function(r,i){r.pr=i+1;});
  rows.sort(function(a,b){return (b.w-a.w)||(b.pf-a.pf);});
  $('#leagueTbl').innerHTML=mkTable([{h:'Team',v:function(r){return r.name;},r:function(r){return '<span class="tm-c">'+muMono(r,'mono-s')+'<span>'+esc(r.name)+'</span></span>';}},{h:'W-L-T',v:function(r){return r.w;},num:1,r:function(r){return esc(r.rec);}},
    {h:'PF',v:function(r){return r.pf;},num:1,fmt:function(x){return f(x,1);}},
    {h:'Strength',v:function(r){return r.power;},num:1,fmt:function(x){return f(x,0);}},
    {h:'Rank',v:function(r){return r.pr;},num:1}],rows);
  wireSort($('#leagueTbl'));
}

/* ---------- player card ---------- */
function closeModal(){if(typeof sheetClose==='function')sheetClose();else $('#modal').classList.remove('open');}
function modal(p){
  function cell(k,v){return '<div class="cell"><div class="k">'+k+'</div><div class="v">'+v+'</div></div>';}
  var h='<div class="mhead">'+avHtml(p.id,p.tm)+'<b>'+esc(p.n)+'</b><span class="muted">'+esc(p.pos)+' &middot; '+esc(p.tm)+' &middot; '+esc(p.slot==='FA'?(p.st||'Free agent'):p.slot)+'</span><button class="x" id="mx">&times;</button></div><div class="grid">';
  h+=cell('Projected pts/game',f(p.out))+cell('Points per game',f(p.ppg))+cell('Luck-adjusted',f(p.exp))+cell('ESPN projection',f(p.proj))+cell('Last 15 days',f(p.rec))+cell('Games (7d)',p.g7)+cell('Games played',p.gp)+(p.rl?cell('Line / PP role',esc(p.rl)):'')+(p.tr!=null?cell('Ice time, last 5 vs season',sgn(p.tr,1)+' min'):'')+(p.toi!=null?cell('Ice time/gm',f(p.toi,1)+' min'):'')+(p.pp!=null?cell('PP time/gm',f(p.pp,1)+' min'):'')+(p.ixg!=null?cell('Expected goals',f(p.ixg,1)):'')+(p.gx!=null?cell('Goals vs xG',sgn(p.gx,1)):'')+(p.gsax!=null?cell('Goals saved vs exp.',sgn(p.gsax,1)):'')+(p.qs!=null?cell('Quality starts',f(p.qs*100,0)+'%'):'')+cell('Rostered',p.own==null?'-':f(p.own,0)+'%');
  if(p.grp==='G')h+=cell('Wins',p.w)+cell('Goals against',p.ga)+cell('Save %',p.svp==null?'-':f(p.svp,3))+cell('Start chance',p.sp==null?'-':Math.round(p.sp*100)+'%');
  else h+=cell('Goals',p.g)+cell('Assists',p.a)+cell('PP points',p.ppp)+cell('Shots',p.sog)+cell('Shooting %',p.shp==null?'-':f(p.shp*100,0)+'%')+cell('Hits',p.hit)+cell('Blocks',p.blk);
  h+='</div>';
  if(p.slot==='FA')h+='<div style="margin-top:10px">Versus your weakest '+p.grp+': <b class="'+(up(p)>=0.2?'good':(up(p)<0?'bad':''))+'">'+sgn(up(p))+'</b> pts/game</div>';
  if(p.fl&&p.fl.length)h+='<ul style="margin-top:10px">'+p.fl.map(function(x){return '<li>'+esc(x)+'</li>';}).join('')+'</ul>';
  if(p.inj&&p.inj!=='ACTIVE')h+='<div class="warn" style="margin-top:8px">Status: '+esc(injLabel(p.inj))+'</div>';
  var m=$('#modal');m.innerHTML='<div class="box">'+h+'</div>';m.classList.add('open');
  $('#mx').addEventListener('click',closeModal);
}

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
  }).filter(function(r){return !LK.closed(r.i);});
  h+='<div class="card"><h2>Your week at a glance</h2>'+mkTable([
    {h:'Day',v:function(r){return r.i;},r:function(r){return esc(r.d);}},
    {h:'Fwd',v:function(r){return r.F;},num:1},
    {h:'Def',v:function(r){return r.D;},num:1},
    {h:'Goalies',v:function(r){return r.G;},num:1},
    {h:'Empty',v:function(r){return r.empty;},num:1,r:function(r){return '<span class="'+(r.empty>=4?'bad':(r.empty>=2?'warn':'good'))+'">'+r.empty+'</span>';}}],rows)
    +'<div class="muted">Fwd, Def and Goalies are how many of your players have a game (you start 9 forwards, 5 defense). Empty slots are days when you cannot fill every lineup spot with a healthy player who has a game. Those are the best days for a streaming pickup.</div></div>';
  h+='<div class="card"><h2>Moves and waivers</h2>';
  if(P.moves_used==null)h+='<div>Your league allows '+P.limit+' adds per matchup. ESPN shows how many you have used on your roster page.</div>';
  else h+='<div><span class="big">'+P.moves_used+' / '+P.limit+'</span> <span class="muted">adds used this matchup</span></div>';
  h+='<div class="muted" style="margin-top:6px">Waivers clear after 1 day, so a claim placed today is usually yours tomorrow. Plan a pickup a day before you need it. Players marked FREEAGENT can be added immediately.</div></div>';
  h+='<div class="card"><h2>Streaming goalies by day</h2><div class="chips">';
  P.days.forEach(function(d,i){
    if(LK.closed(i))return;
    var list=P.stream.filter(function(s){return s.i===i;}).sort(function(a,b){return b.e-a.e;}).slice(0,3);
    h+='<div class="chip"><div class="d">'+esc(d)+'</div>';
    if(!list.length)h+='<div class="m muted">No good options</div>';
    list.forEach(function(s){h+='<div class="m"><a class="pl" data-id="'+s.id+'">'+esc(s.n)+'</a> '+(s.h?'vs':'@')+' '+esc(s.o)+' &middot; win '+Math.round(s.p*100)+'% &middot; '+sgn(s.e,1)+(s.st?' &middot; '+esc(s.st):'')+'</div>';});
    h+='</div>';});
  h+='</div><div class="muted" style="margin-top:8px">Free-agent goalies who start at least 30% of their team games. Expected points use team strength, home ice and save %. Starters are only confirmed for today, so check tomorrow morning before adding.</div></div>';
  $('#t-planner').innerHTML=h;
  $$('#t-planner table').forEach(function(t){wireSort(t.parentNode);});
}

function marginalHtml(pl){
  var M=pl.marginal||[];
  if(!M.length)return '';
  var h='<div style="margin-top:14px"><b>Marginal options</b> <span class="muted">(real but below the bar; use a spare move only if you want to)</span></div>';
  M.forEach(function(m,i){
    h+='<div class="step"><div class="num" style="background:var(--gray)">'+(i+1)+'</div><div><div><b>'+esc(m.day)+'</b>: add <a class="pl" data-id="'+m.add.id+'">'+esc(m.add.n)+'</a> <span class="muted">('+esc(m.add.pos)+', '+esc(m.add.tm)+', '+m.games+' game'+(m.games===1?'':'s')+' left)</span>'+(m.waiver?' <span class="warn">on waivers, claim the day before</span>':'')+'</div>'
    +'<div>drop <a class="pl" data-id="'+m.drop.id+'">'+esc(m.drop.n)+'</a> <span class="muted">('+esc(m.drop.pos)+', '+esc(m.drop.tm)+') &middot; '+sgn(m.gain,1)+' pts this week, '+sgn(m.net,1)+' after what you give up (needs '+f(m.need,1)+')</span></div>'+reasonsHtml(m)+'</div></div>';});
  return h;
}
function reasonsHtml(m){
  var h='';
  if(m.why_add&&m.why_add.length)h+='<div class="why"><b>Why add:</b><ul>'+m.why_add.map(function(x){return '<li>'+esc(x)+'</li>';}).join('')+'</ul></div>';
  if(m.why_drop&&m.why_drop.length)h+='<div class="why"><b>Why drop:</b><ul>'+m.why_drop.map(function(x){return '<li>'+esc(x)+'</li>';}).join('')+'</ul></div>';
  return h;
}
function auditHtml(){
  var A2=(D.streams&&D.streams.audit)||[];
  var core=D.mine.filter(function(p){return p.cls==='core';}).map(function(p){return p.n;});
  var h='<div class="card"><h2>Your roster: core players and streamers</h2>';
  if(core.length)h+='<div class="muted">Core, never suggested as drops: '+core.map(function(n){return esc(n);}).join(', ')+'</div>';
  if(!A2.length)return h+'<div class="good" style="margin-top:6px">No skater on your roster has a weak or slipping role right now.</div></div>';
  A2.forEach(function(a){
    h+='<div class="step"><div class="num" style="background:'+(a.cls==='watch'?'var(--amber)':'var(--gray)')+'">'+(a.cls==='watch'?'!':'S')+'</div><div>'
    +'<div><a class="pl" data-id="'+a.id+'">'+esc(a.n)+'</a> <span class="muted">('+esc(a.pos)+', '+esc(a.tm)+', '+esc(a.slot)+')</span> <b>'+esc(rlTxt(a.rl))+'</b> <span class="'+(a.cls==='watch'?'warn':'muted')+'">'+(a.cls==='watch'?'watch: role has slipped':'streamer: replaceable role')+'</span></div>'
    +'<ul class="why">'+a.why.map(function(x){return '<li>'+esc(x)+'</li>';}).join('')+'</ul>';
    if(a.repl&&a.repl.length)h+='<div class="why"><b>Better options:</b> '+a.repl.map(function(r){return '<a class="pl" data-id="'+r.id+'">'+esc(r.n)+'</a> ('+esc(r.rl||'')+', '+esc(r.tm)+', '+r.gl+' gm left, about '+f(r.e,1)+' pts this week)';}).join(' &middot; ')+'</div>';
    h+='</div></div>';});
  return h+'</div>';
}
var WI={add:'',drop:'',day:0,addQ:'',dropQ:''};
function wiDay(act){
  var F=[],Dn=[],G=[];
  act.forEach(function(a){(a.g==='F'?F:(a.g==='D'?Dn:G)).push(a.v);});
  var desc=function(a,b){return b-a;},sum=function(a){return a.reduce(function(x,y){return x+y;},0);};
  F.sort(desc);Dn.sort(desc);G.sort(desc);
  var rest=F.slice(9).concat(Dn.slice(5)).sort(desc);
  return sum(F.slice(0,9))+sum(Dn.slice(0,5))+(rest.length?rest[0]:0)+sum(G.slice(0,2));
}
function wiFind(L,id){return L.filter(function(x){return String(x.id)===String(id);})[0];}
function wiLine(p,label){
  var bits=[esc(p.tm)];if(p.rl)bits.push(esc(rlTxt(p.rl)));
  return '<div class="wi-row"><span class="wi-lbl">'+label+'</span>'+avHtml(p.id,p.tm)+'<div class="wi-nm"><a class="pl" data-noav="1" data-id="'+p.id+'">'+esc(p.n)+'</a>'
    +'<span class="muted">'+bits.join(' · ')+'</span></div><div class="wi-pt"><b>'+f(p.e,1)+'</b><span class="muted">'+p.gl+' gm</span></div></div>';
}
function wiResult(){
  var W=(D.streams&&D.streams.whatif)||null;
  if(!W)return '';
  var a=wiFind(W.fas,WI.add),d=wiFind(W.mine,WI.drop);
  if(!a||!d)return '<div class="muted" style="margin-top:8px">Pick a free agent to add and one of your players to drop.</div>';
  var n=W.days.length,st=Math.max(Math.min(WI.day,n-1),Math.min(LK.first(),n-1)),base=0,aft=0,rows='';
  for(var i=0;i<n;i++){
    var act=W.mine.map(function(p){return {g:p.grp,v:p.v[i],id:p.id};});
    var b=wiDay(act);
    var c=wiDay(i>=st?act.filter(function(x){return x.id!==d.id;}).concat([{g:a.grp,v:a.v[i],id:a.id}]):act);
    base+=b;aft+=c;
    if(!LK.closed(i))rows+='<tr><td>'+esc(W.days[i])+'</td><td>'+f(b,1)+'</td><td>'+(i>=st?f(c,1):'-')+'</td><td>'+(i>=st?sgn(c-b,1):'-')+'</td></tr>';
  }
  var diff=aft-base,lt=ltAssess(ALL[d.id]||d,ALL[a.id]||a);
  var h='<div class="wi-head"><span class="big">'+sgn(diff,1)+'</span><span class="muted">pts this week</span></div>';
  h+='<div class="wi-pair">'+wiLine(a,'Add')+wiLine(d,'Drop')+'</div>';
  if(a.st==='WAIVERS'&&st===0)h+='<div class="why warn">He is on waivers, so he cannot be added today. Pick a later start day.</div>';
  var wk=diff>=1?'Helps this week':(diff>-1?'About even this week':'Costs you this week');
  var ltw=!lt?'':(lt.v==='none'?'no real long-term downside':(lt.v==='small'?'a small long-term cost (about '+f(lt.pts,1)+' pts)':'a real long-term cost (about '+f(lt.pts,1)+' pts)'));
  var joiner=!lt?'.':((diff>=1)===(lt.v==='none')?', with '+ltw+'.':', but '+ltw+'.');
  h+='<div class="wi-verdict">'+wk+joiner+'</div>';
  if(d.rp&&d.ppg!=null&&d.ppg<0.9*d.rp){
    if(d.cls==='watch'||d.rl==='Off lines'||(d.tr!=null&&d.tr<=-2))h+='<div class="why muted">'+esc(d.n.split(' ').pop())+'\'s role or ice time is shrinking, so a bounce-back is less likely.</div>';
    else h+='<div class="why muted">'+esc(d.n.split(' ').pop())+'\'s role looks intact. If you\'d rather hold him, bench him this week instead.</div>';
  }
  if(ALL[a.id]&&ALL[d.id])h+='<div style="margin:10px 0 2px">'+cmpBtn(ALL[a.id],ALL[d.id],'Compare '+shortName(a.n)+' and '+shortName(d.n))+'</div>';
  if(lt){
    var why=lt.lines.slice(0,-1);
    h+='<details class="pc-det lt-det"><summary>Long term '+ltPill(lt)+'</summary><ul class="why">'+why.map(function(x){return '<li>'+esc(x)+'</li>';}).join('')+'</ul></details>';
  }
  h+='<details class="pc-det"><summary>Day by day</summary><div style="overflow-x:auto"><table style="margin-top:6px"><tr><th>Day</th><th>Before</th><th>After</th><th>Change</th></tr>'+rows+'</table></div></details>';
  return h;
}
/* ---------- searchable pickers for Try a swap ---------- */
function wiNorm(x){var t=String(x==null?'':x).toLowerCase();return t.normalize?t.normalize('NFD').replace(/[\u0300-\u036f]/g,''):t;}
function wiSuggest(){
  var W=(D.streams&&D.streams.whatif)||{mine:[],fas:[]},S=D.streams||{};
  var pairs={},addRank={},dropRank={},k=0;
  function note(m){
    k++;
    var a=m.add.id,d=m.drop.id;
    (pairs[d]=pairs[d]||[]).push(a);
    if(addRank[a]==null)addRank[a]=k;
    if(dropRank[d]==null)dropRank[d]=k;
  }
  var gp=(typeof lkPlan==='function'&&D.gameplan)?lkPlan(D.gameplan):D.gameplan;
  var sp=(typeof lkPlan==='function'&&S.plan)?lkPlan(S.plan):S.plan;
  if(gp)(gp.moves||[]).forEach(note);
  if(sp){(sp.moves||[]).forEach(note);(sp.marginal||[]).forEach(note);}
  (S.audit||[]).forEach(function(a){
    k++;if(dropRank[a.id]==null)dropRank[a.id]=k+50;
    (a.repl||[]).forEach(function(r){(pairs[a.id]=pairs[a.id]||[]).push(r.id);if(addRank[r.id]==null)addRank[r.id]=k+50;});
  });
  (S.week||[]).forEach(function(r){k++;if(addRank[r.id]==null)addRank[r.id]=k+100;});
  return {pairs:pairs,addRank:addRank,dropRank:dropRank};
}
function wiOptions(kind){
  var W=(D.streams&&D.streams.whatif)||{mine:[],fas:[]},sg=wiSuggest(),q=wiNorm(kind==='add'?WI.addQ:WI.dropQ).trim();
  var list=kind==='add'?W.fas:W.mine,groups=[];
  function match(p){
    if(!q)return true;
    var hay=wiNorm(p.n+' '+p.pos+' '+p.tm);
    return q.split(/\s+/).every(function(t){return hay.indexOf(t)>=0;});
  }
  var rows=list.filter(match);
  var sel=kind==='add'?WI.drop:WI.add;
  var pairIds=(kind==='add'&&sel&&sg.pairs[sel])?sg.pairs[sel]:[];
  var rank=kind==='add'?sg.addRank:sg.dropRank,taken={};
  function take(label,arr){arr=arr.filter(function(p){return !taken[p.id];});arr.forEach(function(p){taken[p.id]=1;});if(arr.length)groups.push({t:label,l:arr});}
  if(kind==='add'){
    if(pairIds.length){
      var dn=(wiFind(W.mine,sel)||{}).n||'this player';
      take('Suggested to replace '+dn,rows.filter(function(p){return pairIds.indexOf(p.id)>=0;}).sort(function(x,y){return (sg.addRank[x.id]||999)-(sg.addRank[y.id]||999);}));
    }
    take('Suggested adds',rows.filter(function(p){return rank[p.id]!=null;}).sort(function(x,y){return rank[x.id]-rank[y.id];}));
    take(q?'Matches':'All free agents, best this week first',rows.slice().sort(function(x,y){return y.e-x.e||y.out-x.out;}));
  }else{
    take('Suggested drops',rows.filter(function(p){return rank[p.id]!=null;}).sort(function(x,y){return rank[x.id]-rank[y.id];}));
    take(q?'Matches':'Your roster, weakest first',rows.slice().sort(function(x,y){return x.out-y.out;}));
  }
  return groups;
}
function wiOptHtml(p,kind){
  var av=(typeof avHtml==='function')?avHtml(p.id,p.tm):'';
  return '<div class="opt2" data-pick="'+kind+'" data-id="'+p.id+'">'+av+'<div class="nm"><b>'+esc(p.n)+'</b><span>'+esc(p.pos)+' &middot; '+esc(p.tm)+(p.rl?' &middot; '+esc(rlTxt(p.rl)):'')+' &middot; '+p.gl+' gm left</span></div><div class="pt">'+f(p.e,1)+' pts</div></div>';
}
function wiListHtml(kind){
  var gs=wiOptions(kind),h='';
  gs.forEach(function(g){h+='<div class="gh2">'+esc(g.t)+'</div>'+g.l.slice(0,kind==='add'?80:40).map(function(p){return wiOptHtml(p,kind);}).join('');});
  return h||'<div class="none">No players match that search.</div>';
}
function wiPicker(kind){
  var W=(D.streams&&D.streams.whatif)||{mine:[],fas:[]};
  var id=kind==='add'?WI.add:WI.drop,p=wiFind(kind==='add'?W.fas:W.mine,id);
  var label=kind==='add'?'Add (free agent)':'Drop (your player)';
  var ph=kind==='add'?'Search free agents or pick a suggestion':'Search your roster or pick a suggestion';
  return '<div class="cb" data-kind="'+kind+'"><label>'+label+'</label><div class="cbin"><input type="text" class="cbq" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" placeholder="'+ph+'" value="'+esc(p?p.n:'')+'">'+(id?'<button type="button" class="cbx" data-clear="'+kind+'" aria-label="Clear">&times;</button>':'')+'</div><div class="cbl" style="display:none"></div></div>';
}
function whatifHtml(){
  var W=(D.streams&&D.streams.whatif)||null;
  if(!W)return '';
  var h='<div class="card"><h2>Try a swap</h2><div class="muted">Search or pick a free agent and one of your players. It re-scores your best daily lineup for the rest of the week with and without the swap. Players your plan suggests are listed first. Injured free agents are not listed.</div>';
  h+=wiPicker('drop')+wiPicker('add');
  h+='<div style="margin-top:10px"><label class="muted">Starting <select id="wiDay">'
    +W.days.map(function(x,i){if(LK.closed(i))return '';return '<option value="'+i+'"'+(i===Math.max(WI.day,LK.first())?' selected':'')+'>'+esc(x)+'</option>';}).join('')
    +'</select></label></div>';
  return h+'<div id="wiOut">'+wiResult()+'</div></div>';
}
function wiOpen(box,keepQ){
  var kind=box.getAttribute('data-kind'),l=box.querySelector('.cbl');
  l.innerHTML=wiListHtml(kind);l.style.display='block';
  var first=l.querySelector('.opt2');if(first)first.classList.add('act');
  if(!keepQ&&box.scrollIntoView)setTimeout(function(){try{box.scrollIntoView({block:'start',behavior:'smooth'});}catch(e){}},60);
}
function wiClose(box){var l=box.querySelector('.cbl');if(l)l.style.display='none';}
function wiPick(kind,id){
  if(kind==='add'){WI.add=id;WI.addQ='';}else{WI.drop=id;WI.dropQ='';}
  var box=document.querySelector('.cb[data-kind="'+kind+'"]');
  var W=(D.streams&&D.streams.whatif)||{mine:[],fas:[]};
  var p=wiFind(kind==='add'?W.fas:W.mine,id);
  if(box){
    box.querySelector('.cbq').value=p?p.n:'';
    var inb=box.querySelector('.cbin'),x=inb.querySelector('.cbx');
    if(id&&!x)inb.insertAdjacentHTML('beforeend','<button type="button" class="cbx" data-clear="'+kind+'" aria-label="Clear">&times;</button>');
    if(!id&&x)inb.removeChild(x);
    wiClose(box);box.querySelector('.cbq').blur();
  }
  var o=document.getElementById('wiOut');if(o)o.innerHTML=wiResult();
}
document.addEventListener('focusin',function(e){
  var t=e.target;
  if(t&&t.classList&&t.classList.contains('cbq')){
    var box=t.closest('.cb');
    if(t.value&&!(box.getAttribute('data-kind')==='add'?WI.addQ:WI.dropQ))t.select();
    wiOpen(box);
  }
});
document.addEventListener('input',function(e){
  var t=e.target;
  if(t&&t.classList&&t.classList.contains('cbq')){
    var box=t.closest('.cb'),kind=box.getAttribute('data-kind');
    if(kind==='add')WI.addQ=t.value;else WI.dropQ=t.value;
    wiOpen(box,true);
  }
});
document.addEventListener('keydown',function(e){
  var t=e.target;
  if(!t||!t.classList||!t.classList.contains('cbq'))return;
  var box=t.closest('.cb'),l=box.querySelector('.cbl'),opts=[].slice.call(l.querySelectorAll('.opt2')),i=opts.findIndex(function(x){return x.classList.contains('act');});
  if(e.key==='ArrowDown'||e.key==='ArrowUp'){
    e.preventDefault();if(l.style.display==='none')wiOpen(box);
    if(i>=0)opts[i].classList.remove('act');
    i=e.key==='ArrowDown'?Math.min(opts.length-1,i+1):Math.max(0,i-1);
    if(opts[i]){opts[i].classList.add('act');opts[i].scrollIntoView({block:'nearest'});}
  }else if(e.key==='Enter'){
    e.preventDefault();var a=l.querySelector('.opt2.act');if(a)wiPick(box.getAttribute('data-kind'),a.getAttribute('data-id'));
  }else if(e.key==='Escape'){wiClose(box);t.blur();}
});
document.addEventListener('mousedown',function(e){
  var t=e.target;if(!t||!t.closest)return;
  var o=t.closest('.opt2[data-pick]');
  if(o){e.preventDefault();wiPick(o.getAttribute('data-pick'),o.getAttribute('data-id'));return;}
  var x=t.closest('[data-clear]');
  if(x){e.preventDefault();var k=x.getAttribute('data-clear');if(k==='add')WI.addQ='';else WI.dropQ='';wiPick(k,'');var b=document.querySelector('.cb[data-kind="'+k+'"] .cbq');if(b)b.focus();return;}
  if(!t.closest('.cb'))[].forEach.call(document.querySelectorAll('.cb'),wiClose);
});
document.addEventListener('touchstart',function(e){
  var t=e.target;if(!t||!t.closest)return;
  if(!t.closest('.cb'))[].forEach.call(document.querySelectorAll('.cb'),wiClose);
},{passive:true});
document.addEventListener('change',function(e){
  var t=e.target;
  if(!t||t.id!=='wiDay')return;
  WI.day=parseInt(t.value,10)||0;
  var o=document.getElementById('wiOut');
  if(o)o.innerHTML=wiResult();
});
function weekHtml(){
  var W=(D.streams&&D.streams.week)||[];
  if(!W.length)return '';
  var h='<div class="card"><h2>Best adds for the rest of this week</h2><div class="muted">Ranked by total expected points over the games left this week (schedule and opponents included). Only first-line, first-pair or first power-play players are listed.</div>';
  ['F','D'].forEach(function(g){
    var L=W.filter(function(r){return r.grp===g;});
    if(!L.length)return;
    h+='<div style="margin-top:10px"><b>'+(g==='F'?'Forwards':'Defensemen')+'</b></div>';
    L.forEach(function(r){
      h+='<div style="margin-top:6px"><a class="pl" data-id="'+r.id+'">'+esc(r.n)+'</a> <span class="muted">'+esc(r.pos)+' '+esc(r.tm)+(r.rl?' &middot; '+esc(rlTxt(r.rl)):'')+'</span> &middot; <b>'+f(r.e,1)+' pts</b> &middot; '+r.gl+' game'+(r.gl===1?'':'s')+(r.w?' <span class="warn">(waivers)</span>':'')+'<div class="why">'+esc(r.opps)+'</div></div>';
    });
  });
  return h+'</div>';
}
function auditHtml4(){
  var A2=(D.streams&&D.streams.audit)||[];
  var h='<div class="card"><h2>Your roster: who to look at this week</h2>';
  h+='<div class="muted">Skaters who are underperforming for their role, have a light schedule, or may be losing ice time. Not automatic drops: the move plan only suggests them when a replacement clearly pays off.</div>';
  if(!A2.length)h+='<div class="good" style="margin-top:6px">No skater on your roster is underperforming, on a light schedule, or losing role right now.</div>';
  A2.forEach(function(a,i){
    /* headshot sits beside the name as a block (inline headshots overlapped the wrapped line below); names inside sentences get none */
    var tg=(a.rl?['<b>'+esc(rlTxt(a.rl))+'</b>']:[]).concat(a.tags.map(function(t){return '<span class="'+(t.k==='under'||t.k==='role'?'warn':'muted')+'">'+esc(t.t)+'</span>';}));
    h+='<div class="step au"><div class="num" style="background:'+(a.sev>=3?'var(--amber)':'var(--gray)')+'">'+(i+1)+'</div><div class="au-b">'
    +'<div class="au-h">'+avHtml(a.id,a.tm)+'<div class="au-t"><div class="au-n"><a class="pl" data-noav="1" data-id="'+a.id+'">'+esc(a.n)+'</a> <span class="muted">'+esc(a.pos)+' &middot; '+esc(a.tm)+' &middot; '+esc(a.slot)+'</span></div>'
    +'<div class="au-s">'+tg.join(' &middot; ')+'</div></div></div>'
    +'<ul class="why">'+a.why.map(function(x){return '<li>'+esc(x)+'</li>';}).join('')+'</ul>';
    if(a.repl&&a.repl.length)h+='<div class="why au-o"><b>Better options this week:</b> '+a.repl.map(function(r){return '<a class="pl" data-noav="1" data-id="'+r.id+'">'+esc(r.n)+'</a> ('+esc(r.rl||'')+', '+esc(r.tm)+', '+r.gl+' gm, about '+f(r.e,1)+' pts vs '+f(a.e,1)+')';}).join(' &middot; ')+'</div>';
    h+='</div></div>';});
  h+='</div>';
  return h+whatifHtml()+weekHtml();
}
var ST={pos:'All'};
function streamsRender(){
  var S=D.streams,h='';
  if(!S){$('#t-streams').innerHTML='<div class="card">Streaming data is not available right now.</div>';return;}
  var pl=lkPlan(S.plan);
  h+='<div class="card"><h2>Best use of your moves this week</h2>'+lkNote(pl);
  if(!pl.moves.length)h+='<div class="muted">No add is worth a move right now ('+pl.moves_left+' moves left). Your lineup already beats everything available.</div>';
  else{
    h+='<div><span class="big">+'+f(pl.gain,1)+'</span> <span class="muted">projected points from '+pl.moves.length+' of your '+pl.moves_left+' remaining moves (about '+f(pl.base,0)+' to '+f(pl.total,0)+' for the rest of the matchup)</span></div>';
    pl.moves.forEach(function(m,i){
      h+='<div class="step"><div class="num">'+(i+1)+'</div><div><div><b>'+esc(m.day)+'</b>: add <a class="pl" data-id="'+m.add.id+'">'+esc(m.add.n)+'</a> <span class="muted">('+esc(m.add.pos)+', '+esc(m.add.tm)+', '+m.games+' game'+(m.games===1?'':'s')+' left)</span>'+(m.waiver?' <span class="warn">on waivers, claim the day before</span>':'')+'</div>'
      +'<div>drop <a class="pl" data-id="'+m.drop.id+'">'+esc(m.drop.n)+'</a> <span class="muted">('+esc(m.drop.pos)+', '+esc(m.drop.tm)+')</span> &middot; <span class="good">'+sgn(m.gain,1)+' pts</span></div>'+reasonsHtml(m)+'</div></div>';});
  }
  h+=marginalHtml(pl);
  h+='<div class="muted" style="margin-top:8px">The plan checks every free agent on every remaining day against every player you could drop, then picks moves one at a time that add the most points to your best daily lineup. It accounts for how many games each team plays and how tough the opponents are, and stops when a move is not worth it. Stars and anyone producing for you are never suggested as drops. Players who are underperforming for their role, have a light schedule this week, or are on your watch list can be dropped for a normal gain (1+ point after allowing for what you give up). Healthy top-role players can be dropped only for a bigger gain (2+ points). Every forward or defenseman added must be on a top-six line, top-four pair or first power-play unit. Options below the bar are listed separately as marginal. '+(pl.used_known?'':'ESPN did not report your adds used, so it assumes none. ')+'Later steps assume the earlier ones were made.</div></div>';
  h+=auditHtml4();
  h+='<div class="card"><h2>Best skater streams by day</h2><div class="controls"><span id="stPos"></span></div><div class="chips">';
  S.days.forEach(function(d,i){
    if(LK.closed(i))return;
    var list=S.rows.filter(function(r){return r.i===i&&(ST.pos==='All'||r.grp===ST.pos);}).sort(function(a,b){return b.e-a.e;}).slice(0,ST.pos==='All'?8:6);
    h+='<div class="chip" style="min-width:270px"><div class="d">'+esc(d)+'</div>';
    if(!list.length)h+='<div class="m muted">No games</div>';
    list.forEach(function(r){
      h+='<div class="m"><a class="pl" data-id="'+r.id+'">'+esc(r.n)+'</a> <span class="muted">'+esc(r.pos)+' '+esc(r.tm)+'</span>'+(r.rl?' <span class="muted">'+esc(rlTxt(r.rl))+'</span>':'')+' '+(r.h?'vs':'@')+' '+esc(r.o)+' <span class="'+(r.tag==='weak'?'good':(r.tag==='strong'?'warn':'muted'))+'">'+(r.tag==='weak'?'soft':(r.tag==='strong'?'tough':'avg'))+'</span> &middot; <b>'+f(r.e,1)+'</b> &middot; '+r.gl+' gm left'+(r.w?' <span class="warn">(waivers)</span>':'')+'</div>';});
    h+='</div>';});
  if(LK.first()>=S.days.length)h+='<div class="muted">Every game day left in this matchup week has started, so there is nothing left to add for. Next week\'s streams appear after the next refresh.</div>';
  h+='</div><div class="muted" style="margin-top:8px">Expected points for that day (projected points adjusted for opponent strength and home ice). Players whose teams play more games this week score higher in the move plan above.</div></div>';
  $('#t-streams').innerHTML=h;
  chips('#stPos',['All','F','D'],ST.pos,function(v){ST.pos=v;streamsRender();});
}

function gpMoveHtml(m,i){
  return '<div class="step"><div class="num">'+(i+1)+'</div><div style="flex:1;min-width:0"><div><b>'+esc(m.day)+'</b></div>'+mvCard(m)+'</div></div>';
}
function gpTargets(list,label){
  var h='<div class="chip" style="min-width:290px"><div class="d">'+label+'</div>';
  if(!list.length)h+='<div class="m muted">None clear the role filter</div>';
  list.forEach(function(r){
    h+='<div class="m"><a class="pl" data-id="'+r.id+'">'+esc(r.n)+'</a> <span class="muted">'+esc(r.pos)+' '+esc(r.tm)+' ['+esc(r.role)+']</span> &middot; <b>'+f(r.total,1)+'</b> pts over '+r.games+' gm, from '+esc(r.first.split(' ')[0])+(r.waiver?' <span class="warn">(waivers)</span>':'')+(r.taken?' <span class="good">(in the plan)</span>':'')+'</div>';});
  return h+'</div>';
}
function gameplanRender(){
  /* The Game plan is drawn by uiGamePlan() ("This week's moves" + "See the details"). This keeps the old section empty
     so nothing from the previous layout is shown twice. */
  var el=$('#t-gameplan');if(el)el.innerHTML='';
}

/* ---------- daily lock: once the first game of a day starts, nobody can be added for that day ---------- */
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
    if(staleSince)msg+=' <span class="muted">This was made before puck drop. It updates itself within about 15 minutes of the first game, and the tabs already skip the locked day.</span>';
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
  pl=kpApply(pl);
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

/* ---------- phone app: install hint + push alerts ---------- */
var APPKEY='BIUUEZQFmDcAdIOkdRLbYzUa0dwE69zLw65PNAYcu_K_j1Hi70WwzW8yXtJG3MtBN0_qC1rZ408ec5U1ETWG0kU';
function appStandalone(){return window.navigator.standalone===true||(window.matchMedia&&window.matchMedia('(display-mode: standalone)').matches);}
function appB64(s){var p='='.repeat((4-s.length%4)%4),b=(s+p).replace(/-/g,'+').replace(/_/g,'/'),r=atob(b),o=new Uint8Array(r.length);for(var i=0;i<r.length;i++)o[i]=r.charCodeAt(i);return o;}
function appBox(html){var el=document.getElementById('appbar');if(el)el.innerHTML=html?'<div class="card" style="margin:8px 0;padding:10px 14px">'+html+'</div>':'';}
function appServerKey(){   /* on the always-on server the alert key comes from the server, and the phone is linked automatically */
  return fetch('api/push',{cache:'no-store'}).then(function(r){return r.ok?r.json():null;}).then(function(j){return j&&j.key?j.key:null;}).catch(function(){return null;});
}
function appSame(sub,key){
  try{var k=new Uint8Array(sub.options.applicationServerKey),w=appB64(key);if(k.length!==w.length)return false;for(var i=0;i<k.length;i++)if(k[i]!==w[i])return false;return true;}catch(e){return true;}
}
function appCheck(){   /* stays hidden while alerts work; says what is wrong (and offers a test) when they do not */
  var always=/[?&]alerts\b/.test(location.search);
  fetch('api/alerts',{cache:'no-store'}).then(function(r){return r.ok?r.json():null;}).then(function(j){
    if(!j)return;
    var last=(j.recent||[]).slice(-1)[0],bad=null;
    if(!j.phones)bad='This phone is not linked to the server yet. Close the app and open it again.';
    else if(!j.on)bad='Alerts are switched off on the server (SEND_ALERTS).';
    else if(last&&last.phones.some(function(p){return !p.ok;}))bad='The last alert did not reach this phone ('+last.phones.filter(function(p){return !p.ok;}).map(function(p){return p.code+' '+p.detail;}).join('; ')+').';
    if(!bad&&!always){appBox('');return;}
    appBox('<b>Alerts:</b> <span class="muted" id="appMsg">'+esc(bad||'Working. Last alert: '+(last?last.title:'none yet')+'.')+'</span> <button class="chip-btn" id="appTest" style="margin-left:6px">Send test alert</button>');
    var b=document.getElementById('appTest');
    if(b)b.addEventListener('click',function(){
      var m=document.getElementById('appMsg');if(m)m.textContent='Sending...';
      fetch('api/alerts/test',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(function(r){return r.json();}).then(function(t){
        if(m)m.textContent=t.ok?'Sent. It should appear in a few seconds.':(t.why||('Not delivered: '+(t.errors||[]).join('; ')||'unknown'));
      }).catch(function(){if(m)m.textContent='Could not reach the server.';});
    });
  }).catch(function(){});
}
function appRender(done){
  var mobile=/iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
  var canPush=('serviceWorker' in navigator)&&('PushManager' in window)&&('Notification' in window);
  if(!canPush){
    appBox(mobile&&!appStandalone()?'<b>Get this as an app:</b> tap the Share button, choose <b>Add to Home Screen</b>, then open it from your home screen to turn on alerts.':'');
    return;
  }
  navigator.serviceWorker.ready.then(function(reg){
    return appServerKey().then(function(srvKey){
      return reg.pushManager.getSubscription().then(function(sub){
        if(sub&&srvKey&&!appSame(sub,srvKey))return sub.unsubscribe().then(function(){return null;});
        return sub;
      }).then(function(sub){
        if(Notification.permission==='denied'){appBox('<span class="muted">Alerts are blocked. On iPhone: Settings, Notifications, Fantasy Hockey.</span>');return;}
        if(!sub){
          appBox('<b>Daily alerts:</b> get the day\'s best move on your phone each morning. <button class="chip-btn" id="appOn" style="margin-left:6px">Turn on alerts</button><span id="appMsg" class="muted"></span>');
          var b=document.getElementById('appOn');
          if(b)b.addEventListener('click',function(){
            var m=document.getElementById('appMsg');
            Notification.requestPermission().then(function(p){
              if(p!=='granted'){if(m)m.textContent=' Not allowed.';return;}
              return reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:appB64(srvKey||APPKEY)}).then(function(s){
                if(!srvKey)return appRender();
                return fetch('api/subscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(s)}).then(function(r){return r.json();}).then(function(j){
                  appBox(j&&j.ok?'&#128276; <b>Alerts are on.</b> <span class="muted">You\'re all set. Nothing else to do.</span>':'<span class="muted">Alerts turned on, but the server did not save this phone. Try again.</span>');
                });
              });
            }).catch(function(e){if(m)m.textContent=' Could not turn on alerts ('+(e&&e.message||e)+').';});
          });
          return;
        }
        if(srvKey){   /* quietly (re)register this phone with the server every time the app opens */
          fetch('api/subscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(sub)}).catch(function(){})
            .then(function(){return new Promise(function(r){setTimeout(r,2500);});}).then(appCheck);   /* give the confirmation push a moment, then see how it went */
          appBox('');return;
        }
        if(!/[?&]setup\b/.test(location.search)){appBox('');return;}   /* GitHub Pages: alerts already on, hide the box (add ?setup to the address to bring the phone code back) */
        var code=JSON.stringify(sub);
        appBox('&#128276; <b>Alerts are on for this phone.</b> <button class="chip-btn" id="appCopy" style="margin-left:6px">Copy phone code</button><span id="appMsg" class="muted"></span>'
          +'<div class="muted" style="margin-top:4px">The phone code is only needed once, to link this phone to the daily build.</div>'
          +'<textarea id="appCode" readonly rows="3" style="display:none;width:100%;margin-top:6px;font-size:11px">'+esc(code)+'</textarea>');
        var c=document.getElementById('appCopy');
        if(c)c.addEventListener('click',function(){
          var m=document.getElementById('appMsg'),t=document.getElementById('appCode');
          var show=function(){t.style.display='block';t.focus();t.select();if(m)m.textContent=' Select all and copy.';};
          if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(code).then(function(){if(m)m.textContent=' Copied.';},show);}else{show();}
        });
      });
    });
  }).catch(function(){});
}
function appStart(){
  if('serviceWorker' in navigator){try{navigator.serviceWorker.register('sw.js').then(appRender,appRender);}catch(e){appRender();}}else{appRender();}
}

/* ---------- UI layer: grouped tabs, headshots, collapsible cards ---------- */
var UI={view:'today',sub:{},open:{},booted:false,photos:true};
try{UI.open=JSON.parse(localStorage.getItem('fh_open')||'{}')||{};}catch(e){UI.open={};}
var ICON={
  today:'<svg viewBox="0 0 24 24"><path d="M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>',
  moves:'<svg viewBox="0 0 24 24"><path d="M7 4L3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7"/></svg>',
  roster:'<svg viewBox="0 0 24 24"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>',
  players:'<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>',
  league:'<svg viewBox="0 0 24 24"><path d="M5 21V10M12 21V3M19 21v-7"/></svg>'
};
/* each sub-view lists its cards by title: [title, startsCollapsed] */
var VIEWS=[
 {id:'today',label:'Today',subs:[{id:'main',label:'Today',cards:[['Today'],['Track record']]}]},
 {id:'moves',label:'Moves',subs:[
   {id:'plan',label:'Game plan',cards:[['This week\'s moves'],['Next week preview'],['See the details',1]]},
   {id:'swap',label:'Swap lab',cards:[['Try a swap'],['Your roster: who to look at this week']]},
   {id:'streams',label:'Streams',cards:[['Best skater streams by day'],['Best adds for the rest of this week'],['Streaming goalies by day'],['Best stream targets for the week',1]]}]},
 {id:'roster',label:'Roster',subs:[
   {id:'team',label:'My team',cards:[['My roster']]},
   {id:'week',label:'Schedule',cards:[['Schedule advantage'],['Your week at a glance']]}]},
 {id:'players',label:'Players',subs:[{id:'main',label:'Players',cards:[['Free agents and waivers']]}]},
 {id:'league',label:'League',subs:[
   {id:'games',label:'Matchups',cards:[['Matchups']]},
   {id:'table',label:'Standings',cards:[['Standings and power rankings']]},
   {id:'trade',label:'Trade lab',cards:[['On the trading block'],['Trade finder'],['Trade lab']]},
   {id:'help',label:'Help',cards:[['What the terms mean'],['Data health']]}]}
];
var VMAP={},SPEC={};
VIEWS.forEach(function(v){VMAP[v.id]=v;v.sm={};v.subs.forEach(function(s){v.sm[s.id]=s;s.cards.forEach(function(c){SPEC[c[0]]={v:v.id,s:s.id,c:c[1]||0};});});});
var HOME={overview:'today/main',roster:'roster/team',free:'players/main',trade:'league/trade',planner:'roster/week',gameplan:'moves/plan',streams:'moves/streams',league:'league/table'};
var LEGACY={overview:'today',gameplan:'moves/plan',streams:'moves/streams',planner:'roster/week',free:'players',trade:'league/trade'};

/* Pictures come from ESPN's image resizer at the size they are shown (about 3x for the iPhone screen). The full-size
   files are 20-50 times bigger, and the phone decodes them while you scroll. If the resizer ever fails, the original is
   tried once, then initials (players) or nothing (team logo). */
var ESPN_RS='https://a.espncdn.com/combiner/i?img=';
window.avErr=avErr;                      /* used by the pictures' onerror, which runs outside this script's scope */
function avErr(i){
  var f=i.getAttribute('data-full');
  if(f){i.removeAttribute('data-full');i.src=f;return;}
  if(i.className==='tl')i.style.display='none';else i.parentNode.className+=' nf';
}
function avHtml(id,tm){
  var lp='/i/teamlogos/nhl/500/'+String(tm||'').toLowerCase()+'.png',hp='/i/headshots/nhl/players/full/'+id+'.png';
  var logo=(tm&&/^[A-Za-z]{2,4}$/.test(tm)&&tm!=='FA')?'<img class="tl" src="'+ESPN_RS+lp+'&w=60&h=60&scale=crop" data-full="https://a.espncdn.com'+lp+'" loading="lazy" decoding="async" alt="" onerror="avErr(this)">':'';
  return '<span class="av"><img src="'+ESPN_RS+hp+'&w=300&h=218&scale=crop" data-full="https://a.espncdn.com'+hp+'" loading="lazy" decoding="async" alt="" onerror="avErr(this)">'+logo+'</span>';
}
var decQ=false;
function shortName(n){var s=String(n||'').trim().split(/\s+/);return s.length<2?n:s[0].charAt(0)+'. '+s.slice(1).join(' ');}
function uiDecorate(){
  decQ=false;
  var mob=window.matchMedia&&window.matchMedia('(max-width:720px)').matches;
  $$('a.pl:not([data-av])').forEach(function(a){
    a.setAttribute('data-av','1');
    var id=a.getAttribute('data-id'),p=ALL[id];
    /* no headshot for a name inside a sentence or list item: an inline circle taller than the line pushes lines apart
       and its team-logo badge overlaps the line below */
    if(!a.hasAttribute('data-noav')&&!a.closest('li,.why,p'))a.insertAdjacentHTML('beforebegin',avHtml(id,p&&p.tm));
    else a.setAttribute('data-noav','1');
    if(mob&&a.closest('td')&&!a.hasAttribute('data-noav')&&a.children.length===0){a.title=a.textContent;a.textContent=shortName(a.textContent);}
  });
}
function uiTitle(c){var h=c.querySelector('h2');return h?h.textContent.trim():'';}
function uiBuild(){
  var secs=$$('section[id^="t-"]'),last=secs[secs.length-1],wrap=last.parentNode;
  var ui=document.createElement('div');ui.id='ui';
  ui.innerHTML='<div id="snav"></div>'+VIEWS.map(function(v){
    return '<div class="uview" id="v-'+v.id+'">'+v.subs.map(function(s){return '<div class="usub" id="s-'+v.id+'-'+s.id+'"></div>';}).join('')+'</div>';}).join('');
  wrap.insertBefore(ui,last.nextSibling);
  var ft=document.createElement('div');ft.className='ufoot';
  ft.innerHTML='<button type="button" class="chip-btn" id="phBtn"></button><span class="muted">Read-only: nothing here changes anything in ESPN.</span>';
  wrap.insertBefore(ft,ui.nextSibling);
  try{UI.photos=localStorage.getItem('fh_photos')!=='off';}catch(e){}
  uiPhotos();
  glBuild();
}
function uiPhotos(){
  document.body.classList.toggle('nophoto',!UI.photos);
  var b=document.getElementById('phBtn');if(b)b.textContent='Player photos: '+(UI.photos?'on':'off');
}
function uiNext(c){
  var P=(typeof lkPlan==='function'&&D.gameplan)?lkPlan(D.gameplan):null;
  if(!P||typeof gpMoveHtml!=='function')return;
  var mv=P.moves.slice(0,2),h='<h2>Next moves</h2>';
  if(!mv.length)h+='<div class="muted">No move adds points after what you would give up right now. Streams has the best daily pickups.</div>';
  else mv.forEach(function(m,i){h+=gpMoveHtml(m,i);});
  h+='<div class="goto"><button type="button" class="chip-btn" data-go="moves/plan">Full game plan</button><button type="button" class="chip-btn" data-go="moves/swap">Try a swap</button></div>';
  c.innerHTML=h;
}
function todayTeam(mine,M){
  var t=null;D.teams.forEach(function(x){if(mine?x.me:(M&&(x.id===M.opp_id||x.name===M.opp_name)))t=x;});return t||{};
}
function uiBadge(){
  var b=document.getElementById('bn-moves');if(!b)return;
  var P=(typeof lkPlan==='function'&&D.gameplan)?lkPlan(D.gameplan):null;
  var fi=LK.first(),n=P?P.moves.filter(function(m){return m.t===fi||(m.waiver&&m.t-1===fi);}).length:0;
  var o=b.querySelector('.bdg');if(o)o.parentNode.removeChild(o);
  if(n)b.insertAdjacentHTML('beforeend','<span class="bdg">'+(n>9?'9+':n)+'</span>');
}
function uiLayout(){
  var fresh=$$('section[id^="t-"] > .card');
  fresh.forEach(function(c){
    var t=uiTitle(c),sp=SPEC[t];
    if(HIDE[t])return;
    if(!sp){var hm=(HOME[c.parentNode.id.replace('t-','')]||'today/main').split('/');sp={v:hm[0],s:hm[1],c:0};}
    var box=document.getElementById('s-'+sp.v+'-'+sp.s);
    c.setAttribute('data-ut',t);c.classList.add('collapsible');
    glWrap(c);
    var st=UI.open[t];c.classList.toggle('closed',st===undefined?!!sp.c:!st);
    if(t==='Suggested moves')uiNext(c);
    var old=null;$$('.card',box).forEach(function(x){if(x.getAttribute('data-ut')===t&&x!==c)old=x;});
    if(old)old.parentNode.replaceChild(c,old);else box.appendChild(c);
  });
  try{uiToday();}catch(e){}
  try{uiRecord();}catch(e){}
  try{uiStreams();}catch(e){}
  try{uiPlaybook();}catch(e){}
  try{uiHelp();}catch(e){}
  try{uiEdge();}catch(e){}
  try{uiMatchups();}catch(e){}
  VIEWS.forEach(function(v){v.subs.forEach(function(s){
    var box=document.getElementById('s-'+v.id+'-'+s.id);
    s.cards.forEach(function(c){$$('.card',box).forEach(function(x){if(x.getAttribute('data-ut')===c[0])box.appendChild(x);});});
  });});
  uiBadge();
  if(!decQ){decQ=true;setTimeout(uiDecorate,0);}
}
/* Open or close a section like iOS: the size changes in one step, then the sections below slide into place (transform only,
   so the GPU does it) and the body fades. Animating the height instead re-laid-out the whole page on every frame. */
function cardToggle(c){
  var closing=!c.classList.contains('closed'),t=c.getAttribute('data-ut');
  UI.open[t]=!closing;uiSaveOpen();
  clearTimeout(c._ft);c.classList.remove('closing','opening');
  if(c._fl){c._fl.forEach(function(e){e.classList.remove('flip');e.style.transform='';});c._fl=null;}
  if(RM||!c.offsetParent){c.classList.toggle('closed',closing);return;}
  var fol=[],vh=window.innerHeight||800;
  for(var n=c.nextElementSibling;n;n=n.nextElementSibling)fol.push(n);
  var ft=document.querySelector('.ufoot');if(ft)fol.push(ft);
  var before=fol.map(function(e){return e.getBoundingClientRect().top;});
  if(closing)c.classList.add('closed','closing');else{c.classList.remove('closed');c.classList.add('opening');}
  var moved=[];
  fol.forEach(function(e,i){
    var a=e.getBoundingClientRect().top,d=before[i]-a;
    if(Math.abs(d)<1||Math.min(a,before[i])>vh+40)return;               /* off screen either way: nothing to see */
    e.style.transform='translateY('+d.toFixed(1)+'px)';moved.push(e);
  });
  if(moved.length){
    void c.offsetWidth;                                                 /* start the slide from where they were */
    moved.forEach(function(e){e.classList.add('flip');e.style.transform='';});
  }
  c._fl=moved;
  c._ft=setTimeout(function(){c.classList.remove('closing','opening');moved.forEach(function(e){e.classList.remove('flip');});c._fl=null;},470);
}
/* move-row expanders: the row snaps open or shut once, the rows below slide with transforms (no per-frame layout) */
function rxToggle(x,open){
  clearTimeout(x._ft);x.classList.remove('closing','opening');
  if(x._fl){x._fl.forEach(function(e){e.classList.remove('flip');e.style.transform='';});x._fl=null;}
  if(RM||!x.offsetParent){x.classList.toggle('open',open);return;}
  var fol=[],vh=window.innerHeight||800;
  for(var el=x;el&&!el.matches('section,.wrap,body');el=el.parentElement)
    for(var n=el.nextElementSibling;n;n=n.nextElementSibling)fol.push(n);
  var ft=document.querySelector('.ufoot');if(ft)fol.push(ft);
  var before=fol.map(function(e){return e.getBoundingClientRect().top;});
  x.classList.toggle('open',open);x.classList.add(open?'opening':'closing');
  var moved=[];
  fol.forEach(function(e,i){
    var a=e.getBoundingClientRect().top,d=before[i]-a;
    if(Math.abs(d)<1||Math.min(a,before[i])>vh+40)return;
    e.style.transform='translateY('+d.toFixed(1)+'px)';moved.push(e);
  });
  if(moved.length){void x.offsetWidth;moved.forEach(function(e){e.classList.add('flip');e.style.transform='';});}
  x._fl=moved;
  x._ft=setTimeout(function(){x.classList.remove('closing','opening');moved.forEach(function(e){e.classList.remove('flip');});x._fl=null;},470);
}
/* which sections you opened or closed survives the app reloading itself */
function uiSaveOpen(){try{localStorage.setItem('fh_open',JSON.stringify(UI.open));}catch(e){}}
function showTab(n){
  n=String(n||'').replace(/^#/,'');
  var parts=n.split('/'),v=parts[0],s=parts[1];
  if(LEGACY[v]){var m=LEGACY[v].split('/');v=m[0];s=s||m[1];}
  if(!VMAP[v]){v='today';s=null;}
  var V=VMAP[v];
  if(!s||!V.sm[s])s=UI.sub[v]||V.subs[0].id;
  UI.sub[v]=s;
  var pv=UI.view,ps=UI._ps,moved=UI.booted&&(pv!==v||ps!==s);
  var dir=0;if(UI.booted&&pv===v&&ps&&ps!==s){var ix=V.subs.map(function(y){return y.id;});dir=ix.indexOf(s)>ix.indexOf(ps)?1:-1;}
  UI.view=v;UI._ps=s;
  VIEWS.forEach(function(x){
    document.getElementById('v-'+x.id).classList.toggle('on',x.id===v);
    document.getElementById('bn-'+x.id).classList.toggle('on',x.id===v);
  });
  (function(){var mi=document.getElementById('tbmini');if(mi&&v!=='players'&&SF[v]&&mi._v!==v){mi._v=v;mi.innerHTML=SF[v];}})();
  VIEWS.forEach(function(x){
    x.subs.forEach(function(y){document.getElementById('s-'+x.id+'-'+y.id).classList.toggle('on',x.id===v&&y.id===s);});
  });
  var sn=document.getElementById('snav'),same=sn.getAttribute('data-v')===v;
  if(!same){sn.setAttribute('data-v',v);sn.innerHTML=V.subs.length>1?'<div class="thumb"></div>'+V.subs.map(function(y){return '<button type="button" data-go="'+v+'/'+y.id+'">'+y.label+'</button>';}).join(''):'';}
  $$('button',sn).forEach(function(b){b.classList.toggle('on',b.getAttribute('data-go')===v+'/'+s);});
  glThumb(same&&UI.booted);
  var lt=document.getElementById('lhT'),gt=document.getElementById('gnT');if(lt)lt.textContent=V.label;if(gt)gt.textContent=V.label;
  glLens(UI.booted&&pv!==v);
  if(moved)glEnter(document.getElementById('s-'+v+'-'+s),dir);
  try{history.replaceState(null,'','#'+v+(V.subs.length>1?'/'+s:''));}catch(e){}
  if(UI.booted&&pv!==v)window.scrollTo(0,0);
  UI.booted=true;
  glScroll();
}

/* ---------- Streams (one card) + Day-by-day playbook (built from the existing data) ---------- */
var HIDE={'This week matchup':1,'Best skater streams by day':1,'Best adds for the rest of this week':1,'Best stream targets for the week':1,'Streaming goalies by day':1,
  'Goalie decisions':1,'Suggested moves':1,'Lineup alerts (today)':1,'Best use of your moves this week':1,'The moves, in the order to make them':1,
  'Your game plan for the rest of this week':1,'Day-by-day lineup check':1,'Day-by-day playbook':1,'Moves and waivers':1};
UI.st={sel:'week',pos:'All'};
function dayShort(l){var p=String(l).split(' ');return p[0]+(p[2]?' '+p[2]:'');}
function uiPut(title,html,home){
  var sp=SPEC[title]||home,box=document.getElementById('s-'+sp.v+'-'+sp.s);
  if(!box)return;
  var c=document.createElement('div');c.className='card collapsible';c.setAttribute('data-ut',title);
  var st=UI.open[title];if(st===undefined?!!sp.c:!st)c.classList.add('closed');
  c.innerHTML='<h2>'+esc(title)+'</h2>'+html;
  glWrap(c);
  var old=null;$$('.card',box).forEach(function(x){if(x.getAttribute('data-ut')===title)old=x;});
  if(old)old.parentNode.replaceChild(c,old);else box.appendChild(c);
}
function stRow(r,sub,pts,unit){
  return '<div class="srow"><div class="sm"><a class="pl" data-id="'+r.id+'">'+esc(r.n)+'</a> <span class="muted">'+esc(r.pos||'G')+' '+esc(r.tm)+(r.rl?' &middot; '+esc(rlTxt(r.rl)):'')+'</span><div class="muted">'+sub+'</div></div>'
    +'<div class="sr"><span><b>'+pts+'</b> <span class="muted">'+unit+'</span></span><button type="button" class="chip-btn" data-sw="'+r.id+'">Try swap</button></div></div>';
}
function uiStreams(){
  var S=D.streams,G=D.gameplan,Pl=D.planner;
  if(!S){return;}
  var sel=UI.st.sel,h='',open=[];
  S.days.forEach(function(d,i){if(!LK.closed(i))open.push(i);});
  if(sel!=='week'&&sel!=='goalies'&&open.indexOf(+sel)<0)sel=UI.st.sel='week';
  h+='<div class="stchips"><button type="button" class="chip-btn'+(sel==='week'?' on':'')+'" data-st="week">Week</button><button type="button" class="chip-btn'+(sel==='goalies'?' on':'')+'" data-st="goalies">Goalies</button>'
    +open.map(function(i){return '<button type="button" class="chip-btn'+(String(i)===String(sel)?' on':'')+'" data-st="'+i+'">'+esc(dayShort(S.days[i]))+'</button>';}).join('')+'</div>';
  if(!open.length){h+='<div class="muted" style="margin-top:10px">Every game day left in this matchup week has started, so there is nothing left to add for. Next week appears after the next refresh.</div>';uiPut('Streams',h,{v:'moves',s:'streams',c:0});return;}
  var inPlan={},top={};
  if(G&&G.moves)(lkPlan(G).moves||[]).forEach(function(m){inPlan[m.add.id]=1;});
  open.forEach(function(i){['F','D'].forEach(function(g){
    S.rows.filter(function(r){return r.i===i&&r.grp===g;}).sort(function(a,b){return b.e-a.e;}).slice(0,3).forEach(function(r){if(!top[r.id])top[r.id]=dayShort(S.days[i]);});});});
  if(sel==='week'){
    h+='<div class="muted" style="margin:10px 0 2px">Best pickups to hold for the rest of the week, ranked by total expected points over their remaining games.</div>';
    ['F','D'].forEach(function(g){
      var L=(S.week||[]).filter(function(r){return r.grp===g;});
      if(!L.length)return;
      h+='<div class="sgh">'+(g==='F'?'Forwards':'Defensemen')+'</div>';
      L.forEach(function(r){
        var tags=(inPlan[r.id]?' <span class="good">in your game plan</span>':'')+(top[r.id]?' <span class="muted">&middot; top pick '+esc(top[r.id])+'</span>':'')+(r.w?' <span class="warn">&middot; waivers</span>':'');
        h+=stRow(r,esc(r.opps||'')+tags,f(r.e,1),'pts / '+r.gl+' gm');
      });
    });
  }else if(sel==='goalies'){
    var T=(G&&G.targets&&G.targets.G)||[];
    h+='<div class="sgh">Best goalie pickups for the week</div>';
    if(!T.length)h+='<div class="muted">No free-agent goalie clears the starter filter right now.</div>';
    T.forEach(function(r){h+=stRow(r,esc(r.role||'')+' &middot; from '+esc(String(r.first).split(' ')[0])+(r.waiver?' <span class="warn">&middot; waivers</span>':'')+(inPlan[r.id]?' <span class="good">&middot; in your game plan</span>':''),f(r.total,1),'pts / '+r.games+' gm');});
    h+='<div class="sgh">Goalie streams by day</div>';
    open.forEach(function(i){
      var L=((Pl&&Pl.stream)||[]).filter(function(x){return x.i===i;}).sort(function(a,b){return b.e-a.e;}).slice(0,3);
      h+='<div class="muted" style="margin-top:8px"><b>'+esc(S.days[i])+'</b></div>';
      if(!L.length)h+='<div class="muted">No good options</div>';
      L.forEach(function(x){h+=stRow({id:x.id,n:x.n,pos:'G',tm:''},(x.h?'vs ':'@ ')+esc(x.o)+' &middot; win '+Math.round(x.p*100)+'%'+(x.st?' &middot; '+esc(x.st):''),sgn(x.e,1),'pts');});
    });
    h+='<div class="muted" style="margin-top:8px">Starters are only confirmed for today, so check the morning before adding.</div>';
  }else{
    var i=+sel;
    h+='<div class="controls" style="margin-top:10px"><span>'+['All','F','D'].map(function(v){return '<button type="button" class="chip-btn'+(UI.st.pos===v?' on':'')+'" data-stpos="'+v+'">'+v+'</button>';}).join(' ')+'</span></div>';
    [['F',8],['D',6]].forEach(function(gk){
      if(UI.st.pos!=='All'&&UI.st.pos!==gk[0])return;
      var L=S.rows.filter(function(r){return r.i===i&&r.grp===gk[0];}).sort(function(a,b){return b.e-a.e;}).slice(0,UI.st.pos==='All'?gk[1]:gk[1]+2);
      h+='<div class="sgh">'+(gk[0]==='F'?'Forwards':'Defensemen')+'</div>';
      if(!L.length)h+='<div class="muted">No games</div>';
      L.forEach(function(r){h+=stRow(r,(r.h?'vs ':'@ ')+esc(r.o)+' <span class="'+(r.tag==='weak'?'good':(r.tag==='strong'?'warn':'muted'))+'">'+(r.tag==='weak'?'easy opponent':(r.tag==='strong'?'hard opponent':'average opponent'))+'</span> &middot; '+r.gl+' gm left'+(r.w?' <span class="warn">&middot; waivers</span>':''),f(r.e,1),'pts');});
    });
    h+='<div class="muted" style="margin-top:8px">Expected points for that day: projected points adjusted for opponent strength and home ice.</div>';
  }
  uiPut('Streams',h,{v:'moves',s:'streams',c:0});
}
function wpPill(m){
  var t={done:['start','DONE'],due:['risky','DO TODAY'],missed:['done','MISSED'],unavailable:['bench','NOT AVAILABLE']}[m.state];
  return t?'<span class="pill '+t[0]+'">'+t[1]+'</span> ':'';
}
function wpMove(m,full){
  if(m.state==='due'||m.state==='waiting')return '<li class="mvli">'+wpPill(m)+mvCard(m)+'</li>';
  var note=(m.agree===false)?' <span class="warn">&middot; today\'s model no longer picks him</span>':'';
  var why=m.why1?'<div class="muted">'+esc(m.why1)+'</div>':((m.why&&m.why[0])?'<div class="muted">'+esc(m.why[0])+'</div>':'');
  return '<li>'+wpPill(m)+'add <a class="pl" data-id="'+m.add.id+'">'+esc(m.add.n)+'</a> <span class="muted">('+esc(m.add.pos)+', '+esc(m.add.tm)+', '+m.games+' gm)</span>, drop <a class="pl" data-id="'+m.drop.id+'">'+esc(m.drop.n)+'</a> <span class="muted">('+esc(m.drop.pos)+', '+esc(m.drop.tm)+')</span> &middot; <span class="good">'+sgn(m.gain,1)+' pts</span>'+(m.state==='done'?'':note)+why+'</li>';
}
/* ---------- Game plan: one list of moves to make (each one a "make this move"), the details behind a tap ---------- */
function gpWhy(m){return m.why1||'';}
function gpRow(m,o){
  o=o||{};var key='mv'+m.add.id+'-'+m.drop.id,open=!!(UI.exp&&UI.exp[key]),ck=o.chk?key+'@'+o.chk:'',on=ck&&TD.on(ck);
  return '<div class="row mvr gpr'+(open?' open':'')+(ck?' chk'+(on?' done':''):'')+'" data-exp="'+key+'">'
    +(ck?tdBox(ck,on):'')
    +'<span class="mvr-av">'+glAv(m.add,'add')+glAv(m.drop,'drop')+'</span>'
    +'<div class="row-m"><div class="gpr-h"><div class="row-t">Add <a class="pl" data-noav="1" data-id="'+m.add.id+'">'+esc(m.add.n)+'</a></div>'
    +'<span class="gpr-p">'+sgn(m.gain,1)+'<small>pts</small></span></div>'
    +'<div class="gpr-d">'+(m.ir?'Move ':'Drop ')+'<a class="pl" data-noav="1" data-id="'+m.drop.id+'">'+esc(m.drop.n)+'</a>'+(m.ir?' to IR':'')+'</div>'
    +(gpWhy(m)?'<div class="gpr-w">'+esc(gpWhy(m))+'</div>':'')
    +(ownLine(ALL[m.add.id]||m.add)?'<div class="gpr-o">'+ownLine(ALL[m.add.id]||m.add)+'</div>':'')+'</div>'
    +'<span class="rchev">'+SF.chev+'</span></div>'
    +'<div class="rx'+(open?' open':'')+'" id="x-'+key+'"><div class="rxi">'
    +(m.swapped?'<div class="rx-n">Instead of dropping '+esc(m.swapped)+', who you chose to keep.</div>':'')
    +(m.waiver?'<div class="rx-n warn">He is on waivers: put the claim in the day before.</div>':'')
    +'<div class="rx-n">'+sgn(m.gain,1)+' pts is what this move adds to your lineup this week.</div>'
    +((m.lt&&m.lt.lines&&m.lt.lines.length)?'<div class="rx-n gp-lt">Long term: '+esc(m.lt.lines.join(' '))+'</div>':'')
    +(((m.why_add&&m.why_add.length)||(m.why_drop&&m.why_drop.length))?'<details class="pc-det"><summary>Full reasons</summary>'+reasonsHtml(m)+'</details>':'')
    +'<div class="rx-act">'+keepBtn(m.drop)+cmpBtn(m.add,m.drop)+(o.week?'<button type="button" class="gbtn2" data-go="moves/plan">Whole week</button>':'')+'</div>'
    +'</div></div>';
}
function gpClaimRow(m,day){
  var ck=day?'cl'+m.add.id+'@'+day:'',on=ck&&TD.on(ck);
  return '<div class="row'+(ck?' chk'+(on?' done':''):'')+'">'+(ck?tdBox(ck,on):'<span class="ric">'+SF.clock+'</span>')+'<div class="row-m"><div class="row-t">Claim <a class="pl" data-noav="1" data-id="'+m.add.id+'">'+esc(m.add.n)+'</a></div>'
    +'<div class="row-s">He is on waivers. Put the claim in today so he is yours '+esc(dayShort(m.day))+' (then '+(m.ir?'move '+esc(m.drop.n)+' to IR':'drop '+esc(m.drop.n))+').</div>'+(ownLine(ALL[m.add.id]||m.add)?'<div class="gpr-o">'+ownLine(ALL[m.add.id]||m.add)+'</div>':'')+'</div></div>';
}
/* claims already in with ESPN that haven't processed yet: the plan counts them as made, this row shows the app knows */
function gpPendingRows(P){
  return ((P&&P.pending)||[]).map(function(c){
    var who=c.add_n?'<a class="pl" data-noav="1" data-id="'+c.add+'">'+esc(c.add_n)+'</a>':'your claim',
        s=c.this_week===false?'Goes through overnight, so he is yours next week.':'Goes through overnight. '+(c.drop_n?esc(c.drop_n)+' is dropped then. ':'')+'The plan already counts it.';
    return '<div class="row"><span class="ric ok">'+SF.check+'</span><div class="row-m"><div class="row-t">Claim in: '+who+'</div><div class="row-s">'+s+'</div></div></div>';
  }).join('');
}
function gpLockTxt(i){var C=D.clock,l=C&&C.lock&&C.lock[i];return l?'Before '+etTime(l):'';}
function gpBudget(P){
  if(P.unlimited)return '<div class="sec-f">Your league has no weekly move limit.</div>';
  var lim=P.limit,ml=P.moves_left,n=P.moves.length,res=Math.max(0,ml-n),dots='',note=[];
  if(lim>0&&lim<=14)for(var i=0;i<lim;i++)dots+='<i class="'+(i<lim-ml?'u':'')+'"></i>';
  if(res&&ml)note.push('More show up here as soon as they\u2019re worth it.');
  if(P.limit_known===false)note.push('Your league’s move limit couldn’t be read, so this assumes '+lim+'.');
  if(P.used_known===false)note.push('ESPN didn’t say how many you have used, so this assumes none yet.');
  if(P.season_left!=null&&P.season_left<=ml)note.push(P.season_left+' left for the season.');
  return '<div class="sec-f gp-bud">'+(dots?'<span class="mdots">'+dots+'</span>':'')+'<span>'+ml+' of '+lim+' moves left this week'+(note.length?'<br><span class="gp-bn">'+esc(note.join(' '))+'</span>':'')+'</span></div>';
}
function uiGamePlan(){
  var P=(typeof lkPlan==='function'&&D.gameplan)?lkPlan(D.gameplan):null,S=D.streams,WP=D.weekplan||{},C=D.clock;
  if(!P||!C)return;
  var h='',fi=LK.first(),n=C.labels.length,ch=WP.changes||[],M=P.matchup;
  var today=C.dates&&C.dates[fi]===etToday();
  /* summary: what the moves add and what that does to the matchup */
  if(P.moves.length){
    h+='<div class="grp gp-sum"><div class="gp-t"><div class="gp-k">'+P.moves.length+' move'+(P.moves.length===1?'':'s')+' this week</div><div class="gp-v'+(P.gain>0?' good':'')+'">'+sgn(P.gain||0,1)+'<small> pts</small></div></div>';
    if(M){var pa=M.p_win_after;
      h+='<div class="gp-t"><div class="gp-k">Win chance</div><div class="gp-v">'+Math.round(M.p_win*100)+'%'+(pa!=null&&P.moves.length&&Math.round(pa*100)!==Math.round(M.p_win*100)?'<span class="gp-ar">&rarr;</span><span class="good">'+Math.round(pa*100)+'%</span>':'')+'</div></div>';}
    h+='</div>';
  }
  /* problems first, only when there is one */
  var warns=[];
  if(P.hidden)warns.push(P.hidden+' move'+(P.hidden===1?'':'s')+' for a day that already started '+(P.hidden===1?'was':'were')+' taken off. A fresh plan builds shortly after puck drop.');
  if(P.cautious)warns.push('Line data couldn’t be loaded this update, so only moves from the last good update are shown.');
  if(WP.saved===false)warns.push('Some data was missing in this update. Double-check a move before you make it; the next good update replaces this plan.');
  var pr=gpPendingRows(P);
  if(pr)h+='<div class="grp gp-gap">'+pr+'</div>';
  if(warns.length)h+='<div class="grp gp-gap">'+warns.map(function(w){return '<div class="row"><span class="ric wn">'+SF.warn+'</span><div class="row-m"><div class="row-s" style="color:var(--label)">'+esc(w)+'</div></div></div>';}).join('')+'</div>';
  /* the moves, day by day, each with the deadline to make it */
  var any=false;
  for(var i=fi;i<n;i++){
    var mv=P.moves.filter(function(m){return m.t===i;}),cl=P.moves.filter(function(m){return m.waiver&&m.t-1===i;});
    if(!mv.length&&!cl.length)continue;
    any=true;
    var lbl=(i===fi&&today)?'Today':dayShort(C.labels[i]),lt=gpLockTxt(i);
    h+='<div class="gp-day"><div class="gp-dh"><span>'+esc(lbl)+'</span>'+(lt?'<span class="sec-r">'+SF.clock+esc(lt)+'</span>':'')+'</div><div class="grp">'
      +cl.map(gpClaimRow).join('')+mv.map(function(m){return gpRow(m);}).join('')+'</div></div>';
  }
  if(!any){
    h+='<div class="grp gp-gap"><div class="row"><span class="ric ok">'+SF.check+'</span><div class="row-m"><div class="row-t">No move to make right now</div>'
      +'<div class="row-s">Nothing available beats your lineup by enough to spend a move. The plan updates through the week as lines, injuries and goalie news change.</div></div></div></div>';
  }
  h+=gpBudget(P);
  var kh=keptHtml();if(kh)h+=kh;
  if(ch.length){
    h+='<div class="gp-day"><div class="gp-dh"><span>Changed since the last update</span></div><div class="grp">'+ch.map(function(c){
      return '<div class="row"><span class="ric gy">'+SF.swap+'</span><div class="row-m"><div class="row-t">No longer: add '+esc(c.add.n)+', drop '+esc(c.drop.n)+'</div><div class="row-s">'+esc(c.why)+'</div></div></div>';}).join('')+'</div></div>';
  }
  uiPut('This week\'s moves',h,{v:'moves',s:'plan',c:0});
  uiGamePlanDetails(P,WP,fi);
}
function uiGamePlanDetails(P,WP,fi){
  var C=D.clock,h='',done=WP.done||[],missed=WP.missed||[];
  /* day by day: your lineup's projected points with and without the moves, and empty lineup spots */
  if(P.after&&P.before){
    var rows=[];P.after.forEach(function(a,i){if(LK.closed(i))return;var b=P.before[i]||a;rows.push({d:dayShort(a.day),now:b.pts,plan:a.pts,open:a.open,was:b.open});});
    if(rows.length){
      h+='<h3>Day by day</h3><table class="gp-tb"><thead><tr><th>Day</th><th>Pts now</th><th>With moves</th><th>Empty</th></tr></thead><tbody>'
        +rows.map(function(r){var dl=r.plan-r.now;return '<tr><td><b>'+esc(r.d)+'</b></td><td>'+f(r.now,1)+'</td><td>'+f(r.plan,1)+(dl>0.05?' <span class="good">'+sgn(dl,1)+'</span>':'')+'</td><td>'
          +'<span class="'+(r.open?(r.open>=3?'bad':'warn'):'good')+'">'+r.open+'</span>'+(r.open!==r.was?' <span class="muted">(was '+r.was+')</span>':'')+'</td></tr>';}).join('')
        +'</tbody></table><div class="muted gp-fine">Empty means a lineup spot (9 F, 5 D, 1 UTIL, 2 G) with nobody who plays that day. Those days are where a pickup scores for you.</div>';
    }
  }
  /* goalie start / bench calls by day */
  var gl=[];
  (D.goalies||[]).forEach(function(g){(g.rows||[]).forEach(function(r){
    var i=C.labels.indexOf(r.day);if(i<0||LK.closed(i))return;gl.push({i:i,g:g.p,r:r});});});
  if(gl.length){
    gl.sort(function(a,b){return a.i-b.i;});
    h+='<h3>Goalies</h3><ul class="pbl">'+gl.map(function(x){
      return '<li><span class="muted">'+esc(dayShort(x.r.day))+'</span> <a class="pl" data-id="'+x.g.id+'">'+esc(x.g.n)+'</a> '+(x.r.home?'vs':'@')+' '+esc(x.r.opp)+': <span class="pill '+x.r.cls+'">'+esc(x.r.verdict)+'</span></li>';}).join('')+'</ul>';
  }
  if(done.length||missed.length){
    h+='<h3>Earlier this week</h3><ul class="pbl">'
      +done.map(function(m){return wpMove(Object.assign({},m,{state:'done'}));}).join('')
      +missed.map(function(m){return wpMove(Object.assign({},m,{state:'missed'}));}).join('')+'</ul>';
  }
  h+='<h3>How the plan works</h3><div class="muted gp-fine">One plan for the whole app: the Today screen, this page and the alerts all use these moves. '
    +'A move is on the list when it adds at least 1 point this week after anything it costs you later (0.5 in the last 3 days of the week, since unused moves don\u2019t carry over), so every move here is one to make. '
    +'Points come from games that count: a player\u2019s game only counts when he fits in your lineup that day, so a move can win even when both players have the same games. '
    +'If a player is out and you have an open IR spot, the plan moves him to IR instead of dropping him (the pickup still uses one of your moves). '
    +'The list stays put through the week and only changes for real news (an injury, a line change, a better move), and it says what changed. '
    +'Never suggested as drops: players producing for you (1.9+ pts a game this season or 2.2+ lately), stars, and anyone you tap Keep on. '
    +'Waivers clear after a day, so a player on waivers needs a claim the day before. It is a projection, not a guarantee: check late scratches and goalie news the morning of.</div>';
  uiPut('See the details',h,{v:'moves',s:'plan',c:1});
}
function uiPlaybook(){
  uiGamePlan();
  var WP=D.weekplan||{},PV=WP&&WP.preview;
  if(PV){
    var g='<div class="muted" style="margin-bottom:6px">Draft for the week starting <b>'+esc(PV.first_day||'')+'</b>: +'+f(PV.gain,1)+' projected points ('+f(PV.base,0)+' &rarr; '+f(PV.total,0)+'). Built from your roster and the real schedule as of now. It becomes the plan on the first update of the new week, with fresher news.</div>';
    var byDay={},order=[];
    PV.moves.forEach(function(m){if(!byDay[m.day]){byDay[m.day]=[];order.push(m.day);}byDay[m.day].push(m);});
    if(!order.length)g+='<div class="muted">No move clearly adds points next week yet.</div>';
    order.forEach(function(d){g+='<div class="pbh">'+esc(d)+'</div><ul class="pbl">'+byDay[d].map(function(m){return wpMove({add:m.add,drop:m.drop,games:m.games,gain:m.gain,tier:m.tier,conf:m.conf,why1:m.why1,why:m.why,state:'preview'});}).join('')+'</ul>';});
    uiPut('Next week preview',g,{v:'moves',s:'plan',c:0});
  }else{
    $$('.card[data-ut="Next week preview"]').forEach(function(x){x.parentNode.removeChild(x);});
  }
}

/* ---------- Today: what to do before the day's first puck drop (or that there is nothing to do), in one card ---------- */
function etTime(ms){try{return new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit'}).format(new Date(ms));}catch(e){return '';}}
function etToday(){try{return new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());}catch(e){return '';}}
/* =====================================================================================================
   LIQUID GLASS SHELL
   Floating glass tab bar with a sliding lens (tap or drag), minimizes on scroll; large title that
   collapses into the glass nav bar; segmented control with a sliding thumb; iOS sheet for players;
   Apple Sports style scoreboard on Today. Everything respects Reduce Motion.
   ===================================================================================================== */
var SF={
  today:'<svg viewBox="0 0 28 28"><path class="f" d="M14 3.2c.5 0 1 .2 1.4.5l9 7.6c.4.4.6.9.6 1.4v10.1c0 1.5-1.2 2.7-2.7 2.7h-4.6c-.8 0-1.4-.6-1.4-1.4v-5.4c0-.8-.6-1.4-1.4-1.4h-1.8c-.8 0-1.4.6-1.4 1.4v5.4c0 .8-.6 1.4-1.4 1.4H5.7C4.2 25.5 3 24.3 3 22.8V12.7c0-.5.2-1 .6-1.4l9-7.6c.4-.3.9-.5 1.4-.5z"/></svg>',
  moves:'<svg viewBox="0 0 28 28"><path class="s" d="M9 4.5L4.5 9 9 13.5M4.8 9h17.7M19 14.5l4.5 4.5-4.5 4.5M23.2 19H5.5"/></svg>',
  roster:'<svg viewBox="0 0 28 28"><circle class="f" cx="10.5" cy="9" r="4.3"/><path class="f" d="M2.5 22.3c0-3.9 3.6-6.8 8-6.8s8 2.9 8 6.8c0 .9-.7 1.4-1.6 1.4H4.1c-.9 0-1.6-.5-1.6-1.4z"/><circle class="f" cx="19.6" cy="10" r="3.4"/><path class="f" d="M19.4 15.6c3.6 0 6.1 2.4 6.1 5.4 0 .8-.6 1.3-1.3 1.3h-3.6c.2-.6.3-1.3.3-2 0-1.8-.7-3.4-1.9-4.6.1 0 .3-.1.4-.1z"/></svg>',
  players:'<svg viewBox="0 0 28 28"><circle class="s" cx="12.3" cy="12.3" r="7.3"/><path class="s" d="M17.6 17.6l6 6"/></svg>',
  league:'<svg viewBox="0 0 28 28"><path class="f" d="M8 3.5h12c.6 0 1 .4 1 1v1h2.6c.8 0 1.4.6 1.4 1.4v1.2c0 3-2.2 5.4-5.1 5.8-.9 1.6-2.4 2.8-4.2 3.2V20h2.6c.9 0 1.6.7 1.6 1.6v2.3c0 .3-.3.6-.6.6H8.7c-.3 0-.6-.3-.6-.6v-2.3c0-.9.7-1.6 1.6-1.6h2.6v-2.9c-1.8-.4-3.3-1.6-4.2-3.2C5.2 13.5 3 11.1 3 8.1V6.9c0-.8.6-1.4 1.4-1.4H7v-1c0-.6.4-1 1-1zm-3 4v.6c0 1.6 1 2.9 2.4 3.4-.3-1-.4-2-.4-3V7.5H5zm16 0v1c0 1-.1 2-.4 3 1.4-.5 2.4-1.8 2.4-3.4v-.6h-2z"/></svg>',
  refresh:'<svg viewBox="0 0 28 28"><path class="s" d="M22.5 14a8.5 8.5 0 1 1-2.5-6M20.6 3.6v4.8h-4.8"/></svg>',
  xmark:'<svg viewBox="0 0 28 28"><path class="s" d="M8.5 8.5l11 11M19.5 8.5l-11 11"/></svg>',
  check:'<svg viewBox="0 0 28 28"><circle class="f" cx="14" cy="14" r="12"/><path class="k" d="M8.6 14.4l3.6 3.5 7.2-7.6"/></svg>',
  warn:'<svg viewBox="0 0 28 28"><path class="f" d="M12.3 4.2c.8-1.3 2.6-1.3 3.4 0l9.2 15.9c.8 1.3-.2 3-1.7 3H4.8c-1.5 0-2.5-1.7-1.7-3z"/><path class="k" d="M14 10v5.2M14 18.6v.1"/></svg>',
  chev:'<svg viewBox="0 0 28 28"><path class="s" d="M11 7l7 7-7 7"/></svg>',
  swap:'<svg viewBox="0 0 28 28"><path class="s" d="M8 6v15M4.5 17.5L8 21l3.5-3.5M20 22V7M16.5 10.5L20 7l3.5 3.5"/></svg>',
  plus:'<svg viewBox="0 0 28 28"><path class="k" d="M14 8v12M8 14h12"/></svg>',
  minus:'<svg viewBox="0 0 28 28"><path class="k" d="M8 14h12"/></svg>',
  up:'<svg viewBox="0 0 28 28"><path class="k" d="M14 21V8M8.5 13L14 7.5l5.5 5.5"/></svg>',
  dn:'<svg viewBox="0 0 28 28"><path class="k" d="M14 7v13M8.5 15l5.5 5.5 5.5-5.5"/></svg>',
  clock:'<svg viewBox="0 0 28 28"><circle class="s" cx="14" cy="14" r="10"/><path class="s" d="M14 8.5V14l3.5 2.2"/></svg>',
  chart:'<svg viewBox="0 0 28 28"><path class="s" d="M6 22V14M12 22V8M18 22v-6M24 22V11"/></svg>',
  goals:'<svg viewBox="0 0 28 28"><path class="s" d="M5 21V9.5h18V21M5 21h18M9 9.5 7 21M19 9.5l2 11.5"/><circle cx="14" cy="17" r="2" fill="currentColor"/></svg>'
};
var RM=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function hue(s){var h=0;s=String(s||'');for(var i=0;i<s.length;i++)h=(h*31+s.charCodeAt(i))%360;return h;}
function initials(n){var w=String(n||'').replace(/[^A-Za-z0-9' ]/g,'').split(/\s+/).filter(Boolean);return ((w[0]||'?').charAt(0)+(w[1]?w[1].charAt(0):'')).toUpperCase();}

/* ---------- shell: nav bar, large title, tab bar ---------- */
function glBuild(){
  var wrap=document.querySelector('.wrap');
  /* large title */
  var lh=document.createElement('header');lh.id='lhead';
  var eye='';try{eye=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'long',month:'long',day:'numeric'}).format(new Date());}catch(e){}
  lh.innerHTML='<div class="lh-eye">'+esc(eye)+'</div><h1 class="lh-t" id="lhT">Today</h1><div class="lh-sub">'+esc(D.me)+' &middot; '+esc(D.rec)+'</div>';
  wrap.insertBefore(lh,wrap.firstChild);
  /* glass nav bar: inline title + refresh button */
  var nb=document.createElement('div');nb.id='gnav';
  nb.innerHTML='<div class="gn-edge"></div><div class="gn-row"><div class="gn-side"></div><div class="gn-t" id="gnT">Today</div><div class="gn-side gn-r"></div></div>';
  document.body.appendChild(nb);
  var rf=document.getElementById('rfbar');if(rf&&rf.parentNode!==document.body)document.body.appendChild(rf);
  var rb=document.getElementById('rfbtn');
  if(rb){rb.className='gbtn glass';rb.removeAttribute('style');rb.innerHTML=SF.refresh;rb.setAttribute('aria-label','Refresh data');nb.querySelector('.gn-r').appendChild(rb);}
  /* tab bar: capsule + detached search button (iOS 26) */
  var old=document.getElementById('bnav');if(old)old.parentNode.removeChild(old);
  var tb=document.createElement('nav');tb.id='bnav';tb.setAttribute('aria-label','Main');
  var cap=VIEWS.filter(function(v){return v.id!=='players';});
  tb.innerHTML='<div class="gn-edge bot"></div><div class="tbcap glass" id="tbcap"><div class="lens" id="lens"></div>'
    +cap.map(function(v){return '<button type="button" data-go="'+v.id+'" id="bn-'+v.id+'" aria-label="'+v.label+'">'+SF[v.id]+'<span>'+v.label+'</span></button>';}).join('')
    +'</div><button type="button" class="tbmini glass" id="tbmini" aria-label="Show tabs" tabindex="-1"></button><button type="button" class="tbsearch glass" data-go="players" id="bn-players" aria-label="Search players">'+SF.players+'</button>';
  document.body.appendChild(tb);
  (function(){var mi=document.getElementById('tbmini'),v=UI.view;if(mi&&v&&v!=='players'&&SF[v]){mi._v=v;mi.innerHTML=SF[v];}})();
  glTabDrag(tb.querySelector('#tbcap'));
  window.addEventListener('scroll',glScroll,{passive:true});
  window.addEventListener('resize',function(){glLens(false);glThumb(false);});
  glScroll();
}
function glLens(anim){
  var cap=document.getElementById('tbcap'),ln=document.getElementById('lens');if(!cap||!ln)return;
  var b=cap.querySelector('button.on');
  if(!b){ln.style.opacity='0';return;}
  ln.style.opacity='';
  if(anim===false)ln.classList.add('nt');
  ln.style.width=b.offsetWidth+'px';ln.style.transform='translateX('+b.offsetLeft+'px)';
  if(anim===false){void ln.offsetWidth;ln.classList.remove('nt');}
  else if(!RM){ln.classList.remove('pop');void ln.offsetWidth;ln.classList.add('pop');}
}
/* drag the lens across the tab bar, like iOS 26 */
function glTabDrag(cap){
  var x0=null,moved=false,ln=document.getElementById('lens'),bs;
  function at(x){var r=cap.getBoundingClientRect(),best=null,bd=1e9;bs.forEach(function(b){var c=r.left+b.offsetLeft+b.offsetWidth/2,d=Math.abs(c-x);if(d<bd){bd=d;best=b;}});return best;}
  cap.addEventListener('pointerdown',function(e){
    if(document.getElementById('bnav').classList.contains('min'))return;
    bs=[].slice.call(cap.querySelectorAll('button'));x0=e.clientX;moved=false;
    ln.classList.add('held');
  });
  window.addEventListener('pointermove',function(e){
    if(x0==null)return;
    if(!moved&&Math.abs(e.clientX-x0)<8)return;
    moved=true;ln.classList.add('drag');cap.classList.add('dragging');
    var r=cap.getBoundingClientRect(),w=ln.offsetWidth,x=Math.max(4,Math.min(r.width-w-4,e.clientX-r.left-w/2));
    ln.style.transform='translateX('+x+'px)';
    var b=at(e.clientX);bs.forEach(function(y){y.classList.toggle('hov',y===b);});
  });
  function end(e){
    if(x0==null)return;
    ln.classList.remove('held','drag');cap.classList.remove('dragging');bs.forEach(function(y){y.classList.remove('hov');});
    if(moved){var b=at(e.clientX);if(b)showTab(b.getAttribute('data-go'));else glLens();cap._sup=Date.now();}
    x0=null;
  }
  window.addEventListener('pointerup',end);window.addEventListener('pointercancel',function(){if(x0==null)return;ln.classList.remove('held','drag');x0=null;glLens();});
  cap.addEventListener('click',function(e){if(cap._sup&&Date.now()-cap._sup<400){e.stopPropagation();e.preventDefault();}},true);
}
/* iOS can leave the visible screen offset from the page the fixed bars are laid out on (after a sheet closes, the keyboard, or
   coming back to the app), so the top bar floats mid-screen. visualViewport says by how much; every fixed bar follows it. */
var PIN={y:0};
function glPin(){
  var vv=window.visualViewport,y=vv?vv.offsetTop:0,ae=document.activeElement;
  var typing=ae&&/^(INPUT|SELECT|TEXTAREA)$/.test(ae.tagName);
  if(!typing||!isFinite(y)||Math.abs(y)<1||(typeof SH!=='undefined'&&SH.open))y=0;   /* never follow a bounce or zoom, only the keyboard */
  y=Math.round(y);
  if(y===PIN.y)return;
  PIN.y=y;document.documentElement.style.setProperty('--vvy',y+'px');
}
if(window.visualViewport){window.visualViewport.addEventListener('scroll',glPin);window.visualViewport.addEventListener('resize',glPin);}

/* Page edges. The page itself never rubber-bands any more (html{overscroll-behavior:none}): on iOS that bounce is what
   dragged the fixed top bar and its blur down the screen, and sometimes left it stuck there. Instead only the content
   stretches at the top and bottom, under bars that stay put, and a fast flick into an edge gives a small spring. */
var BAND={y0:null,x0:0,ax:0,on:false,base:0,inner:false,lt:0,ly:0,v:0,t:0};
/* the page height is kept up to date by a ResizeObserver, so touches and scrolls never force a layout just to read it */
function bandMax(){if(BAND.max==null||!window.ResizeObserver)BAND.max=Math.max(0,document.documentElement.scrollHeight-window.innerHeight);return BAND.max;}
(function(){function upd(){BAND.max=null;if(typeof GS!=='undefined')GS.lim=null;}window.addEventListener('resize',upd,{passive:true});
  if(window.ResizeObserver){var ro=new ResizeObserver(upd),go=function(){var w=document.querySelector('.wrap');if(w)ro.observe(w);else setTimeout(go,200);};go();}})();
function bandOff(){return (typeof SH!=='undefined'&&(SH.open||SH.closing_busy))||document.documentElement.classList.contains('sheet-on')||document.body.classList.contains('mlock');}
function bandInner(el){
  for(;el&&el!==document.body&&el!==document.documentElement;el=el.parentElement){
    if(el.id==='modal')return true;
    var oy=getComputedStyle(el).overflowY;if((oy==='auto'||oy==='scroll')&&el.scrollHeight>el.clientHeight+1)return true;
  }
  return false;
}
function bandSet(px,mode){
  var w=document.querySelector('.wrap');if(!w)return;
  w.classList.toggle('band-back',mode==='back');w.classList.toggle('band-kick',mode==='kick');
  w.style.transform=Math.abs(px)>=0.5?'translate3d(0,'+px.toFixed(1)+'px,0)':'';
  var t=document.getElementById('lhT');if(t)t.style.transform=px>0?'scale('+Math.min(1.1,1+px/900).toFixed(4)+')':'';
  clearTimeout(BAND.t);if(mode==='back')BAND.t=setTimeout(function(){w.classList.remove('band-back');},650);
}
function bandRubber(d){var H=window.innerHeight||800,a=Math.abs(d),r=(1-1/(a*0.55/H+1))*H;return d<0?-r:r;}
document.addEventListener('touchstart',function(e){
  BAND.y0=null;if(RM||e.touches.length!==1||bandOff())return;
  BAND.y0=e.touches[0].clientY;BAND.x0=e.touches[0].clientX;BAND.ax=0;BAND.on=false;BAND.ly=BAND.y0;BAND.inner=null;BAND.tg=e.target;
},{passive:true});
document.addEventListener('touchmove',function(e){
  if(BAND.y0==null||BAND.inner===true||e.touches.length!==1)return;
  var y=e.touches[0].clientY,dy=y-BAND.y0,dx=e.touches[0].clientX-BAND.x0;
  if(!BAND.ax){if(Math.abs(dy)<6&&Math.abs(dx)<6)return;BAND.ax=Math.abs(dy)>Math.abs(dx)?1:-1;}
  if(BAND.ax<0)return;                                                  /* sideways swipe (tables, chips) */
  var sy=window.pageYOffset||0;
  if(!BAND.on){
    var down=y>BAND.ly;BAND.ly=y;
    if(sy<=0.5&&down)BAND.on=1;else if(!down&&sy>=bandMax()-1)BAND.on=-1;else return;
    if(BAND.inner==null)BAND.inner=bandInner(BAND.tg);                  /* only now: is the finger in a scroll box of its own? */
    if(BAND.inner){BAND.on=false;return;}
    BAND.base=y;return;
  }
  BAND.ly=y;var d=y-BAND.base;
  if(d*BAND.on<=0){BAND.on=false;bandSet(0);return;}                    /* finger came back past the edge: scroll normally */
  bandSet(bandRubber(d));
},{passive:true});
function bandEnd(){if(BAND.on){BAND.on=false;bandSet(0,'back');}BAND.y0=null;}
document.addEventListener('touchend',bandEnd,{passive:true});document.addEventListener('touchcancel',bandEnd,{passive:true});
/* momentum: a quick flick that runs into the top or bottom gets a short spring instead of a dead stop */
window.addEventListener('scroll',function(){
  var y=window.pageYOffset||0,now=performance.now(),dt=now-BAND.lt;
  if(dt>0&&dt<120)BAND.v=BAND.v*0.4+(y-BAND.lpy)/dt*0.6;else BAND.v=0;
  BAND.lt=now;BAND.lpy=y;
  if(RM||BAND.y0!=null||bandOff()||Math.abs(BAND.v)<0.9)return;
  var max=bandMax();
  if(y<=0.5&&BAND.v<0){bandFling(-BAND.v);BAND.v=0;}
  else if(y>=max-1&&BAND.v>0){bandFling(-BAND.v);BAND.v=0;}
},{passive:true});
/* One continuous spring that starts at the flick's own speed (no stop, jump, return). It is a damped spring
   x(t) = v*t*e^(-w*t), sampled into keyframes and run by the compositor (transform only), so it stays smooth
   even while the page is busy. v is in px/ms; positive = content moves down (hit the top). */
function bandFling(v){
  var w=document.querySelector('.wrap');if(!w||!w.animate)return;
  var a=Math.abs(v),peak=Math.min(56,a*30),om=a/(Math.E*Math.max(peak,1)),N=36,kf=[],kt=[];
  om=Math.max(om,1/140);var dur=Math.min(900,Math.max(380,7/om));
  var t=document.getElementById('lhT');
  for(var i=0;i<=N;i++){var tm=dur*i/N,x=(i===N)?0:v*tm*Math.exp(-om*tm);
    kf.push({transform:'translate3d(0,'+x.toFixed(2)+'px,0)'});
    kt.push({transform:x>0?'scale('+Math.min(1.08,1+x/900).toFixed(4)+')':'none'});}
  bandStop();
  BAND.anim=w.animate(kf,{duration:dur,easing:'linear'});
  if(t&&v>0)BAND.anim2=t.animate(kt,{duration:dur,easing:'linear'});
}
function bandStop(){if(BAND.anim){BAND.anim.cancel();BAND.anim=null;}if(BAND.anim2){BAND.anim2.cancel();BAND.anim2=null;}}
/* a touch during the spring: freeze it where it is and let it settle back, never snap */
document.addEventListener('touchstart',function(){
  if(!BAND.anim||BAND.anim.playState!=='running')return;
  var w=document.querySelector('.wrap'),m=getComputedStyle(w).transform,y=0;
  if(m&&m!=='none'){var p=m.match(/matrix(3d)?\(([^)]+)\)/);if(p){var n=p[2].split(',');y=parseFloat(p[1]?n[13]:n[5])||0;}}
  bandStop();bandSet(y);requestAnimationFrame(function(){bandSet(0,'back');});
},{passive:true});
/* scroll: collapse the large title into the nav bar; minimize the tab bar going down, restore going up */
var GS={y:0,raf:0,acc:0};
function glScroll(){
  glPin();
  if(GS.raf)return;
  GS.raf=requestAnimationFrame(function(){
    GS.raf=0;
    var y=window.pageYOffset||0,dy=y-GS.y;GS.y=y;
    var lh=document.getElementById('lhead'),nb=document.getElementById('gnav'),tb=document.getElementById('bnav');
    if(!lh||!nb||document.documentElement.classList.contains('sheet-on'))return;
    var t=document.getElementById('lhT');if(GS.lim==null||GS.limT!==t){GS.limT=t;GS.lim=t.offsetTop+t.offsetHeight-48;}var lim=GS.lim;
    nb.classList.toggle('scrolled',y>lim);
    nb.classList.toggle('edge',y>4);
    if(t.style.transform&&!BAND.on&&!(document.querySelector('.wrap')||{}).style.transform)t.style.transform='';
    /* tab bar */
    if(y<60){GS.acc=0;tb.classList.remove('min');}
    else if(dy>0){GS.acc=Math.max(0,GS.acc)+dy;if(GS.acc>40)tb.classList.add('min');}
    else if(dy<0){GS.acc=Math.min(0,GS.acc)+dy;if(GS.acc<-24)tb.classList.remove('min');}
  });
}
document.addEventListener('click',function(e){
  var tb=document.getElementById('bnav');
  if(tb&&tb.classList.contains('min')&&e.target.closest&&e.target.closest('#tbcap,#tbmini')){e.stopPropagation();e.preventDefault();tb.classList.remove('min');GS.acc=0;}
},true);

/* ---------- segmented control ---------- */
function glThumb(anim){
  var sn=document.getElementById('snav');if(!sn)return;
  var th=sn.querySelector('.thumb'),b=sn.querySelector('button.on');if(!th||!b)return;
  if(anim===false)th.classList.add('nt');
  th.style.width=b.offsetWidth+'px';th.style.transform='translateX('+b.offsetLeft+'px)';
  if(anim===false){void th.offsetWidth;th.classList.remove('nt');}
}

/* ---------- view transitions ---------- */
function glEnter(el,dir){
  if(RM||!el)return;
  el.classList.remove('enter','enter-l','enter-r');void el.offsetWidth;
  el.classList.add(dir>0?'enter-r':(dir<0?'enter-l':'enter'));
}

/* ---------- inset grouped cards: wrap the body so it can animate open and closed ---------- */
function glWrap(c){
  if(!c||c.querySelector(':scope>.cbody'))return;
  var h=c.querySelector(':scope>h2');
  var body=document.createElement('div');body.className='cbody';var inn=document.createElement('div');inn.className='cin';body.appendChild(inn);
  var kids=[].slice.call(c.childNodes);kids.forEach(function(k){if(k!==h)inn.appendChild(k);});
  c.appendChild(body);
  if(h&&!h.querySelector('.hchev'))h.insertAdjacentHTML('beforeend','<span class="hchev">'+SF.chev+'</span>');
}

/* ---------- sheet (player card) ---------- */
var SH={open:false,closing:0,dir:null};
function spSet(v){var w=document.querySelector('.wrap'),m=document.getElementById('modal');
  if(w){if(v==null)w.style.removeProperty('--sp');else w.style.setProperty('--sp',String(v));}
  if(m){if(v==null)m.style.removeProperty('--spm');else m.style.setProperty('--spm',String(v));}}
function sheetOpen(){
  var m=document.getElementById('modal'),bx=m.querySelector('.box'),de=document.documentElement;if(!bx)return;
  clearTimeout(SH.closing);SH.closing_busy=false;
  var x=bx.querySelector('#mx');if(x){x.innerHTML=SF.xmark;x.className='x gbtn glass';x.setAttribute('aria-label','Close');}
  if(!bx.querySelector('.grab'))bx.insertAdjacentHTML('afterbegin','<div class="grab"></div>');
  var wrap=document.querySelector('.wrap'),y=window.pageYOffset||0;
  if(!SH.open){wrap.style.transformOrigin='50% '+y+'px';wrap.style.setProperty('--clipy',y+'px');}
  SH.open=true;
  de.classList.add('sheet-on','sh-anim');
  if(RM){spSet(1);return;}
  /* one style flush commits both starting points (sheet below the screen, page not stepped back yet); a second flush
     here used to cost another full-page layout on every open */
  bx.style.transition='none';bx.style.transform='translateY(100%)';spSet(0);void bx.offsetWidth;
  bx.style.transition='';bx.style.transform='';
  requestAnimationFrame(function(){spSet(1);});
  if(!bx._dr){bx._dr=1;sheetDrag(bx);}
}
function sheetClose(){
  var m=document.getElementById('modal'),bx=m.querySelector('.box'),de=document.documentElement;
  if(!SH.open){m.classList.remove('open');return;}
  SH.open=false;
  de.classList.add('sh-anim');spSet(0);
  if(bx){bx.style.transition='';bx.style.transform='translateY(105%)';}
  m.classList.add('fading');
  SH.closing_busy=true;
  SH.closing=setTimeout(function(){
    SH.closing_busy=false;
    m.classList.remove('open','fading');de.classList.remove('sheet-on','sh-anim');spSet(null);
    var w=document.querySelector('.wrap');w.style.transformOrigin='';
    if(bx)bx.style.transform='';
    glPin();setTimeout(glPin,250);
  },RM?0:480);
}
/* Close the sheet at once (no slide-out) and unlock the page BEFORE the caller changes tabs or scrolls.
   Compare/Player card > "Try swap" used to start the 0.5 s close, then switch tabs and scroll while the body was still locked
   (position:fixed); when the lock released afterwards, iOS could leave the page shifted down with a dark strip above the header (2026-11-24). */
function sheetCloseNow(){
  var m=document.getElementById('modal'),bx=m&&m.querySelector('.box'),de=document.documentElement,b=document.body,w=document.querySelector('.wrap');
  clearTimeout(SH.closing);SH.open=false;SH.closing_busy=false;
  if(m)m.classList.remove('open','fading');
  de.classList.remove('sheet-on','sh-anim');spSet(null);
  if(w){w.style.transformOrigin='';w.style.removeProperty('--clipy');}
  if(bx)bx.style.transform='';
  b.classList.remove('mlock');b.style.top='';
  glPin();
}
/* iOS keeps odd state after the keyboard closes or the app is reopened: the top bar can end up shifted under the status bar,
   and a closed sheet can leave the "page stepped back" look behind. Put both back to normal. */
function glReset(){
  glPin();
  var de=document.documentElement,w=document.querySelector('.wrap'),m=document.getElementById('modal');
  if(!SH.open&&!SH.closing_busy&&de.classList.contains('sheet-on')){
    de.classList.remove('sheet-on','sh-anim');spSet(null);
    if(w){w.style.transformOrigin='';w.style.removeProperty('--clipy');}
    if(m)m.classList.remove('open','fading');
    document.body.classList.remove('mlock');document.body.style.top='';
  }
  var vv=window.visualViewport;
  if(vv&&(vv.offsetTop>1||vv.pageTop<0)&&!document.body.classList.contains('mlock'))window.scrollTo(window.pageXOffset||0,Math.max(0,window.pageYOffset||0));
}
/* Safety net: the "page stepped back" state (black backdrop, clipped page, top strip) may only exist while a sheet is open or closing.
   If anything ever leaves it behind (e.g. a sheet closed by Compare > Try swap while the tab changes), clear it within half a second. */
function sheetHeal(){var de=document.documentElement;if(!SH.open&&!SH.closing_busy&&de.classList.contains('sheet-on'))glReset();}
setInterval(sheetHeal,400);
document.addEventListener('visibilitychange',function(){if(!document.hidden)glReset();});
window.addEventListener('pageshow',glReset);
document.addEventListener('focusout',function(e){
  if(e.target&&/^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName))setTimeout(function(){glReset();window.scrollTo(window.pageXOffset||0,window.pageYOffset||0);},120);
});
function sheetDrag(bx){
  var de=document.documentElement,y0=null,x0=0,dy=0,t=[],drag=false,H=1;
  function start(y,x){y0=y;x0=x||0;dy=0;t=[[y,performance.now()]];drag=false;bx._vdrag=false;H=bx.offsetHeight||1;}
  function move(y,ev,x){
    if(y0==null)return;
    var d=y-y0;
    /* a sideways swipe (matchup paging) is not a pull-down */
    if(!drag){if(bx._swx||bx.scrollTop>0||d<=2||(x!=null&&Math.abs(x-x0)>=d))return;drag=true;bx._vdrag=true;y0=y;d=0;bx.style.transition='none';de.classList.remove('sh-anim');}
    if(ev&&ev.cancelable)ev.preventDefault();
    dy=d;t.push([y,performance.now()]);if(t.length>5)t.shift();
    var tr=dy>=0?dy:-Math.pow(-dy,0.72);
    bx.style.transform='translateY('+tr+'px)';
    spSet(Math.max(0,Math.min(1,1-Math.max(0,dy)/H)).toFixed(3));
  }
  function end(){
    if(y0==null)return;y0=null;
    if(!drag)return;drag=false;bx._vdrag=false;
    var a=t[0],b=t[t.length-1],v=(b&&a&&b[1]>a[1])?(b[0]-a[0])/(b[1]-a[1]):0;
    bx.style.transition='';de.classList.add('sh-anim');
    if(dy>H*0.28||v>0.45){sheetClose();}
    else{bx.style.transform='';spSet(1);}
  }
  bx.addEventListener('touchstart',function(e){if(e.touches.length===1)start(e.touches[0].clientY,e.touches[0].clientX);},{passive:true});
  bx.addEventListener('touchmove',function(e){move(e.touches[0].clientY,e,e.touches[0].clientX);},{passive:false});
  bx.addEventListener('touchend',end);bx.addEventListener('touchcancel',end);
  bx.addEventListener('pointerdown',function(e){if(e.pointerType==='mouse'&&e.target.closest('.grab,.mhead'))start(e.clientY);});
  window.addEventListener('pointermove',function(e){if(e.pointerType==='mouse')move(e.clientY,null);});
  window.addEventListener('pointerup',function(e){if(e.pointerType==='mouse')end();});
}

/* ---------- numbers that count up ---------- */
function glCount(root){
  $$('[data-cu]',root).forEach(function(el){
    var v=parseFloat(el.getAttribute('data-cu')),dec=+(el.getAttribute('data-dec')||0),suf=el.getAttribute('data-suf')||'';
    if(RM||isNaN(v)){el.textContent=v.toFixed(dec)+suf;return;}
    var t0=null,dur=900;
    function step(ts){if(!t0)t0=ts;var k=Math.min(1,(ts-t0)/dur),e=1-Math.pow(1-k,4);el.textContent=(v*e).toFixed(dec)+suf;if(k<1)requestAnimationFrame(step);}
    requestAnimationFrame(step);
  });
}

/* ---------- Today: Apple Sports style scoreboard + inset grouped lists ---------- */
function glAv(p,badge,ic){
  var id=p.id,tm=p.tm||(ALL[id]&&ALL[id].tm);
  return '<span class="rav">'+(typeof avHtml==='function'?avHtml(id,tm):'')+(badge?'<i class="rb '+badge+'">'+SF[ic||(badge==='add'?'plus':'minus')]+'</i>':'')+'</span>';
}
function glMoveRow(m,day){return gpRow(m,{week:1,chk:day});}

function uiToday(){
  var C=D.clock,P=(typeof lkPlan==='function'&&D.gameplan)?lkPlan(D.gameplan):null,M=D.matchup,h='';
  if(!C)return;
  var fi=LK.first(),n=C.labels.length,isToday=fi<n&&C.dates[fi]===etToday();
  var age=C.built?(Date.now()-C.built)/3600000:0,H=D.health||{};
  /* scoreboard */
  if(M){
    var pw=Math.round(M.p_win*100),me=D.me,op=M.opp_name||'Opponent',ph=pairHues(todayTeam(true),todayTeam(false,M)),h1=ph[0],h2=ph[1];
    var mp=D.gameplan&&D.gameplan.mp,lead=M.me_now>=M.opp_now,mi=muMine();
    /* tap the scoreboard for the full head-to-head sheet (same one as League > Matchups) */
    h+='<section class="sb'+(mi>=0?' tap':'')+'" style="--h1:'+h1+';--h2:'+h2+'"'
      +(mi>=0?' data-mu="'+mi+'" role="button" tabindex="0" aria-label="Open your matchup: '+esc(me)+' '+f(M.me_now,1)+', '+esc(op)+' '+f(M.opp_now,1)+'"':'')+'>'
      +'<div class="sb-top"><span class="sb-live"></span>'+(mp?'Week '+mp+' &middot; ':'')+M.days_left+' day'+(M.days_left===1?'':'s')+' left</div>'
      +'<div class="sb-row">'
      +'<div class="sb-tm"><div class="mono" style="--h:'+h1+'">'+esc(initials(me))+muImg(todayTeam(true))+'</div><div class="sb-n">'+esc(me)+'</div><div class="sb-r">'+esc(D.rec)+'</div></div>'
      +'<div class="sb-sc"><span class="num'+(lead?'':' dim')+'" data-cu="'+M.me_now+'" data-dec="1">'+f(M.me_now,1)+'</span><span class="sb-d"></span><span class="num'+(lead?' dim':'')+'" data-cu="'+M.opp_now+'" data-dec="1">'+f(M.opp_now,1)+'</span></div>'
      +'<div class="sb-tm"><div class="mono" style="--h:'+h2+'">'+esc(initials(op))+muImg(todayTeam(false,M))+'</div><div class="sb-n">'+esc(op)+'</div><div class="sb-r">'+esc(M.opp_rec||'')+'</div></div>'
      +'</div>'
      +'<div class="wp"><div class="wp-h"><span>Win probability</span></div>'
      +'<div class="wp-bar" style="'+wpVars(pw)+'"><i class="a"></i><i class="b"></i></div>'
      +'<div class="wp-l"><span><b data-cu="'+pw+'" data-suf="%">'+pw+'%</b></span><span><b>'+(100-pw)+'%</b></span></div></div>'
      +'<div class="sb-ft"><span>Projected</span><b>'+Math.round(M.proj_me)+'</b><span>&ndash;</span><b>'+Math.round(M.proj_opp)+'</b>'+(mi>=0?'<span class="sb-go" aria-hidden="true">'+SF.chev+'</span>':'')+'</div>'
      +'</section>';
  }
  h+='<div id="livebox">'+lvHtml()+'</div>';
  /* problems only: the data line is silent when everything is fine */
  var warn=age>12?'This hasn\u2019t updated in '+Math.round(age)+' hours. Tap refresh, or check ESPN before making moves.'
    :((H.level&&H.level!=='ok'&&H.items&&H.items.length)?H.items[0]+(H.level==='bad'?' Double-check a move before you make it until it is back.':''):'');
  if(fi>=n){
    h+='<div class="sec"><div class="grp"><div class="row"><span class="ric ok">'+SF.check+'</span><div class="row-m"><div class="row-t">You\'re set for this week</div><div class="row-s">Every game day has started. Next week\'s plan shows up after the next update.</div></div></div></div></div>';
    uiPut('Today',h,{v:'today',s:'main',c:0});glCount(document.getElementById('s-today-main'));return;
  }
  var lk=C.lock[fi],S=D.sb,si=S&&S.dates?S.dates.indexOf(C.dates[fi]):-1,dk=C.dates[fi];
  var all=P?P.moves.filter(function(m){return m.t===fi;}):[];
  var cl=P?P.moves.filter(function(m){return m.waiver&&m.t-1===fi;}):[];
  /* lineup changes for the same day (same list as Roster > Lineup); a move today that drops a player wins over starting him */
  var dropT={};all.forEach(function(m){dropT[m.drop.id]=1;});
  var fx=si>=0?tdFixes(si,S).filter(function(x){return !dropT[x.b.id];}):[];
  UI.exp=UI.exp||{};
  /* To do (2026-11-27): everything to do before the first puck drop, one checklist: waiver claims, moves, lineup changes */
  h+='<div class="sec"><div class="sec-h"><span>To do</span>'+(lk?'<span class="sec-r">'+SF.clock+'Before '+etTime(lk)+'</span>':'')+'</div><div class="grp">';
  if(warn)h+='<div class="row"><span class="ric wn">'+SF.warn+'</span><div class="row-m"><div class="row-t">Check the data</div><div class="row-s">'+esc(warn)+'</div></div></div>';
  h+=gpPendingRows(P);
  if(all.length||cl.length||fx.length){
    h+=cl.map(function(m){return gpClaimRow(m,dk);}).join('')+all.map(function(m){return glMoveRow(m,dk);}).join('')
      +fx.map(function(x){return tdRow(x,si,S,true);}).join('');
  }else{
    var nx=P?P.moves.filter(function(m){return m.t>fi;})[0]:null;
    h+='<button type="button" class="row" data-go="moves/plan"><span class="ric ok">'+SF.check+'</span><div class="row-m"><div class="row-t">Nothing to do '+(isToday?'today':'yet')+'</div><div class="row-s">'
      +(nx?'Next move: '+esc(dayShort(nx.day))+', add '+esc(nx.add.n)+' for '+esc(nx.drop.n):'No move planned for the rest of this week')+'</div></div><span class="rchev">'+SF.chev+'</span></button>';
  }
  h+='</div>';
  var ft='';
  if(P&&P.moves_left!=null&&!P.unlimited){
    var lim=P.limit||0,ml=P.moves_left,dots='';
    if(lim>0&&lim<=14)for(var i=0;i<lim;i++)dots+='<i class="'+(i<lim-ml?'u':'')+'"></i>';
    ft=(dots?'<span class="mdots">'+dots+'</span>':'')+'<span>'+ml+' of '+lim+' moves left this week</span>';
  }
  if(ft)h+='<div class="sec-f">'+ft+'</div>';
  h+='</div>';
  /* Lineup: a glance (how many spots play, after the changes above), goalies, problems the To do list doesn't cover */
  var gl=[];(D.goalies||[]).forEach(function(g){(g.rows||[]).forEach(function(r){if(r.day===C.labels[fi])gl.push({g:g.p,r:r});});});
  /* Goalie badges follow the To do list (user, 2026-11-28: To do said start Hellebuyck + Hill while these rows said
     Vasilevskiy + Hellebuyck). goalies.py ranks by start chance with no win check; tdGoalies adds the 50%-to-win bar.
     So for a day the To do list covers, a goalie is Start only if he is in a G spot after the changes above. */
  var gCall=null;
  if(si>=0&&S&&si>=rdT(S)&&rdKnown(si,S)){
    var gW={};((D.streams&&D.streams.whatif&&D.streams.whatif.mine)||[]).forEach(function(p){gW[p.id]=p;});
    var inG={};(D.mine||[]).forEach(function(p){if(p.grp==='G'&&rdSl(p,si,S)==='G')inG[p.id]=1;});
    fx.forEach(function(x){if(x.g){inG[x.b.id]=1;if(x.a)delete inG[x.a.id];}});
    gCall={inG:inG,win:function(p){return tdWin(p,si,S,gW);}};
  }
  gl.forEach(function(x){
    if(!gCall||!/^(START|BENCH)$/.test(x.r.verdict||''))return;
    var w=gCall.win(x.g);
    if(gCall.inG[x.g.id]){x.r=Object.assign({},x.r,{verdict:'START',conf:(w!=null?Math.round(w*100)+'% to win':x.r.conf)});x.st=1;}
    else x.r=Object.assign({},x.r,{verdict:'BENCH',conf:(w!=null&&w<TD_GW)?Math.round(w*100)+'% to win, not worth a start':'your other goalies are better bets tonight'});
  });
  gl.sort(function(a,b){return (b.st||0)-(a.st||0)||(b.r.ev||0)-(a.r.ev||0);});
  var fxN=fx.map(function(x){return x.a?x.a.n:'';}).concat(fx.map(function(x){return x.b.n;}));
  var al=(D.alerts||[]).filter(function(a){return (a.k==='bad'||/injur|not starting/i.test(a.t))&&!fxN.some(function(n){return n&&a.t.indexOf(n)>=0;});});
  h+='<div class="sec"><div class="sec-h"><span>Lineup</span></div><div class="grp">';
  if(si>=0&&S){
    var L=rdLineup(),tot=L.F+L.D+L.UTIL+L.G,on=(D.mine||[]).filter(rdAct(si,S)).filter(function(p){return rdPlays(p,si,S);}).length;
    var after=Math.min(tot,on+fx.filter(function(x){return x.why!=='lower';}).length),full=after>=tot;
    h+='<button type="button" class="row" data-go="roster/team"><span class="ric '+(fx.length?'gy':(full?'ok':'gy'))+'">'+(fx.length?SF.roster:(full?SF.check:SF.roster))+'</span><div class="row-m"><div class="row-t">'
      +(fx.length?'After the changes above':'Your lineup is set')+'</div><div class="row-s">'+after+' of '+tot+' spots have a game '+(isToday?'today':esc(dayShort(C.labels[fi])))+'</div></div><span class="rchev">'+SF.chev+'</span></button>';
  }
  al.forEach(function(a){h+='<div class="row"><span class="ric '+(a.k==='bad'?'bd':'wn')+'">'+SF.warn+'</span><div class="row-m"><div class="row-s" style="color:var(--label)">'+esc(a.t)+'</div></div></div>';});
  gl.forEach(function(x){
    var b=/bench/i.test(x.r.verdict)?'bench':(/risk/i.test(x.r.verdict)?'risky':'start'),v=x.r.verdict.replace(/\s*\(.*\)/,'').toLowerCase();
    /* a goalie today's move drops is never "Start": the plan already counts him as gone (2026-11-27, Adin Hill) */
    var dr=dropT[x.g.id];if(dr){b='bench';v='drop';}
    h+='<div class="row">'+glAv(x.g)+'<div class="row-m"><div class="row-t"><a class="pl" data-noav="1" data-id="'+x.g.id+'">'+esc(x.g.n)+'</a></div><div class="row-s">'+(x.r.home?'vs ':'@ ')+esc(x.r.opp)+(dr?' &middot; today\u2019s move drops him':(x.r.conf?' &middot; '+esc(x.r.conf):''))+'</div></div><span class="badge b-'+b+'">'+esc(v.charAt(0).toUpperCase()+v.slice(1))+'</span></div>';
  });
  if(isToday&&!gl.length)h+='<div class="row"><span class="ric gy">'+SF.clock+'</span><div class="row-m"><div class="row-s">None of your goalies play</div></div></div>';
  h+='</div><div class="sec-f">Lineup changes are made in ESPN &middot; updated '+esc(String(D.updated||'').replace(/^.*?,\s*/,''))+'</div></div>';
  uiPut('Today',h,{v:'today',s:'main',c:0});
  glCount(document.getElementById('s-today-main'));
}

/* ---------- Move cards and the "Keep him" list ---------- */
/* No Strong / Lean / Optional labels in the app (2026-11-24): every move on the plan is one to make. */
var KP=(function(){
  var K='fh_keep';
  function mp(){return D.gameplan?D.gameplan.mp:null;}
  function local(){try{var o=JSON.parse(localStorage.getItem(K)||'null');return (o&&o.mp===mp())?o:null;}catch(e){return null;}}
  function list(){
    var o=local(),built=(D.clock&&D.clock.built)||0;
    if(o&&o.at>built)return o.ids.slice();
    return ((D.gameplan&&D.gameplan.kept)||[]).slice();
  }
  function has(id){return list().indexOf(+id)>=0;}
  function pending(){var o=local(),built=(D.clock&&D.clock.built)||0;return !!(o&&o.at>built);}
  function set(ids){try{localStorage.setItem(K,JSON.stringify({mp:mp(),ids:ids,at:Date.now()}));}catch(e){}}
  function toggle(id){
    id=+id;var l=list(),i=l.indexOf(id);
    if(i>=0)l.splice(i,1);else l.push(id);
    set(l);
    var sync=(typeof window.FHRefresh==='function')?window.FHRefresh({reason:'manual-button-keep',keep:l.length?l.join(','):'none'},true):false;
    return {kept:i<0,synced:sync};
  }
  return {list:list,has:has,toggle:toggle,pending:pending};
})();
function kpApply(pl){
  if(!pl||!pl.moves||pl._kp)return pl;
  var kept={};KP.list().forEach(function(id){kept[id]=1;});
  var c={};for(var k in pl)c[k]=pl[k];c._kp=1;c.keptOut=[];
  if(!Object.keys(kept).length)return c;
  var used={};pl.moves.forEach(function(m){if(!kept[m.drop.id])used[m.drop.id]=1;});
  var delta=0;c.moves=[];
  pl.moves.forEach(function(m){
    if(!kept[m.drop.id]){c.moves.push(m);return;}
    c.keptOut.push(m);delta-=(m.marg!=null?m.marg:m.net);
    var alt=(m.alts||[]).filter(function(a){return !kept[a.drop.id]&&!used[a.drop.id];})[0];
    if(alt){used[alt.drop.id]=1;delta+=alt.net;c.moves.push(Object.assign({},alt,{swapped:m.drop.n,why_add:m.why_add}));}
  });
  c.gain=Math.max(0,(pl.gain||0)+delta);
  if(pl.matchup){var mm={};for(var q in pl.matchup)mm[q]=pl.matchup[q];mm.p_win_after=null;c.matchup=mm;}
  return c;
}
function keepBtn(p){
  var on=KP.has(p.id);
  return '<button type="button" class="kp'+(on?' on':'')+'" data-keep="'+p.id+'">'+(on?'Kept: undo':'Keep '+esc(shortName(p.n)))+'</button>';
}
/* ---------- Long term: what a stream costs after this week (same rules as longterm.py) ---------- */
var LT={SMALL:0.5,REAL:2.0,FIX:0.35,REPL:{F:1.45,D:1.5,G:1.0},
  lbl:{none:['No long-term cost','start'],small:['Small long-term cost','risky'],real:['Real long-term cost','bench']}};
function ltPg(p){var o=p.out||0;return p.grp==='G'?o*(p.sp||0.5):o;}
function ltGone(p){if(p.own==null)return 0.5;var g=(p.own-20)/60;if((p.own_chg||0)>=2)g+=0.1;return Math.max(0.05,Math.min(0.95,g));}
/* Line role in plain words: 'F2 - PP1' -> 'Line 2 · PP1', 'D1' -> 'Pair 1', 'G1' -> 'Starter' */
function rlTxt(rl){if(!rl)return '';var N={'Off lines':'Not on current lines','Not listed':'Role unknown','no role':'No set role',G1:'Starter',G2:'Backup'};if(N[rl])return N[rl];
  return String(rl).split('-').map(function(s){s=s.trim();var m=/^([FD])(\d)$/.exec(s);return m?(m[1]==='F'?'Line ':'Pair ')+m[2]:s;}).filter(Boolean).join(' · ');}
function ltRole(p){if(!p.rl||p.grp==='G')return null;var N={F1:'top line',F2:'second line',F3:'third line',F4:'fourth line',D1:'top pair',D2:'second pair',D3:'third pair',PP1:'first power play',PP2:'second power play'};
  var w=p.rl.split('-').map(function(s){return s.trim();}).filter(Boolean).map(function(s){return N[s]||s;});return w.length?w.join(' and '):null;}
function ltAssess(y,x){
  var G=D.gameplan||{},fut=G.fut;if(!fut||!y||!x)return null;
  var wk=Math.round((G.fut_days||21)/7),d=y.n.split(' ').pop(),a=x.n.split(' ').pop(),L=[];
  if(y.inj==='OUT'||y.inj==='INJURY_RESERVE'||y.inj==='SUSPENSION')return {v:'none',pts:0,lines:[d+' is '+injLabel(y.inj).toLowerCase()+', so he isn\'t scoring for you now.']};
  var py=ltPg(y),px=ltPg(x),gy=fut[y.tm]||0,gx=fut[x.tm]||0,fl=(LT.REPL[y.grp]||1.45)*(y.grp==='G'?0.5:1);
  var c=Math.max(0,py*gy-Math.max(px,fl)*gx)*(LT.FIX+(1-LT.FIX)*ltGone(y));
  if(Math.abs(py-px)<0.05)L.push('Per game from here on, they\'re about even ('+d+' '+f(py,2)+', '+a+' '+f(px,2)+'), with hot and cold streaks taken out.');
  else if(py>px)L.push(d+' is the better player per game from here on ('+f(py,2)+' vs '+f(px,2)+'), with hot and cold streaks taken out.');
  else L.push(a+' is the better player per game from here on ('+f(px,2)+' vs '+f(py,2)+'), with hot and cold streaks taken out.');
  [[x,a],[y,d]].forEach(function(q){var g=q[0].gx;if(g==null||(q[0].gp||0)<8)return;
    if(g>=2.5)L.push(q[1]+' has scored about '+Math.round(g)+' more goals than his chances usually give, so expect fewer going forward.');
    else if(g<=-2.5)L.push(q[1]+' has scored about '+Math.round(-g)+' fewer goals than his chances usually give, so he\'s due to bounce back.');});
  [[y,d],[x,a]].forEach(function(q){var r=ltRole(q[0]),tr=q[0].tr;if(!r)return;
    L.push(q[1]+': '+r+(tr!=null&&Math.abs(tr)>=1?', ice time '+(tr>0?'up':'down')+' '+f(Math.abs(tr),1)+' min lately':'')+'.');});
  L.push(y.tm===x.tm?'Next '+wk+' weeks: both play '+gy+' games ('+y.tm+').':'Next '+wk+' weeks: '+y.tm+' plays '+gy+' games, '+x.tm+' plays '+gx+'.');
  if(y.own!=null){var g2=ltGone(y),o=Math.round(y.own);
    L.push(g2>=0.6?d+' is rostered in '+o+'% of ESPN leagues, so someone will likely claim him. Don\'t count on getting him back.':
      (g2>=0.3?d+' is rostered in '+o+'% of ESPN leagues, so he may get claimed before you want him back.':
        d+' is rostered in only '+o+'% of ESPN leagues, so he\'ll likely still be there if you want him back (it costs a move).'));}
  var v=c<LT.SMALL?'none':(c<LT.REAL?'small':'real');
  L.push(v==='none'?'Bottom line: no real long-term downside.':(v==='small'?'Bottom line: a small long-term cost, about '+f(c,1)+' pts over the next '+wk+' weeks.':
    'Bottom line: a real long-term cost, about '+f(c,1)+' pts over the next '+wk+' weeks. Only worth it if this week matters a lot.'));
  return {v:v,pts:c,lines:L};
}
function ltPill(lt){var l=LT.lbl[lt.v]||LT.lbl.none;return '<span class="pill '+l[1]+'">'+l[0]+(lt.v!=='none'&&lt.pts!=null?' &middot; '+f(lt.pts,1)+' pts':'')+'</span>';}
function ltHtml(lt,open){
  if(!lt)return '';
  return '<details class="pc-det lt-det"'+(open?' open':'')+'><summary>Long term '+ltPill(lt)+'</summary><ul class="why">'
    +lt.lines.map(function(x){return '<li>'+esc(x)+'</li>';}).join('')+'</ul></details>';
}
function mvCard(m,o){
  o=o||{};
  var h='<div class="mv"><div class="mv-top"><b>'+esc(dayShort(m.day))+'</b> <span class="good">'+sgn(m.gain,1)+' pts</span></div>'
    +'<div class="mv-sw"><span class="mv-k">Add</span> <a class="pl" data-id="'+m.add.id+'">'+esc(m.add.n)+'</a> <span class="muted">'+esc(m.add.pos)+' '+esc(m.add.tm)+'</span></div>'
    +'<div class="mv-sw"><span class="mv-k">Drop</span> <a class="pl" data-id="'+m.drop.id+'">'+esc(m.drop.n)+'</a> <span class="muted">'+esc(m.drop.pos)+' '+esc(m.drop.tm)+'</span></div>';
  if(m.waiver)h+='<div class="warn" style="font-size:13px">He is on waivers: put the claim in the day before.</div>';
  if(m.swapped)h+='<div class="muted" style="font-size:13px">Instead of dropping '+esc(m.swapped)+', who you chose to keep.</div>';
  if(m.why1)h+='<div class="mv-why">'+esc(m.why1)+'</div>';
  if(m.lt)h+=ltHtml(m.lt);
  if(!o.noact){
    h+='<div class="mv-act">'+keepBtn(m.drop)+cmpBtn(m.add,m.drop);
    if((m.why_add&&m.why_add.length)||(m.why_drop&&m.why_drop.length))h+='<details class="pc-det"><summary>Full reasons</summary>'+reasonsHtml(m)+'</details>';
    h+='</div>';
  }
  return h+'</div>';
}
function keptHtml(){
  var l=KP.list();if(!l.length)return '';
  var names=l.map(function(id){var p=ALL[id];return p?'<a class="pl" data-id="'+id+'" data-noav="1">'+esc(p.n)+'</a> <button type="button" class="kp on" data-keep="'+id+'">undo</button>':'';}).filter(Boolean);
  if(!names.length)return '';
  return '<div class="why" style="margin:6px 0">Kept this week (never suggested as drops): '+names.join(' &middot; ')
    +(KP.pending()?' <span class="muted">(saved on this phone; the alerts catch up after the next update)</span>':'')+'</div>';
}
function kpClick(id){
  var r=KP.toggle(id),p=ALL[id],n=p?shortName(p.n):'He';
  try{gameplanRender();}catch(e){}
  try{uiLayout();}catch(e){}
  kpToast(r.kept?(n+' is kept for this week. '+(r.synced?'Updating the plan and alerts now.':'Saved on this phone. Tap Refresh data to update the morning alert too.')):(n+' can be suggested as a drop again.'));
}
function kpToast(t){
  var el=document.getElementById('kptoast');
  if(!el){el=document.createElement('div');el.id='kptoast';el.setAttribute('role','status');document.body.appendChild(el);}
  el.textContent=t;el.classList.add('on');clearTimeout(kpToast._t);kpToast._t=setTimeout(function(){el.classList.remove('on');},4500);
}

/* ---------- Track record: did the advice work? ---------- */
function uiRecord(){
  var R2=D.record;
  var h='';
  if(!R2){
    h='<div class="muted">Every suggested move gets scored after its games: points the player you add scores minus the player you drop, over the same days. The first results show up after the next game day.</div>';
    uiPut('Track record',h,{v:'today',s:'main',c:0});return;
  }
  var M=R2.made,S=R2.skipped,st=R2.strong;
  if(!M.n&&!S.n){
    h+='<div class="muted">Scoring starts with this week\'s next moves. Each one is scored after its games: points the player you add scores minus the player you drop, over the same days. Made and skipped moves both count, so you can see what following the advice is worth.</div>';
    if(R2.untracked)h+='<div class="muted" style="margin-top:6px">'+R2.untracked+' earlier move'+(R2.untracked===1?' was':'s were')+' suggested before scoring started, so '+(R2.untracked===1?'it isn\'t':'they aren\'t')+' counted.</div>';
  }else{
    h+='<div class="rec">'
      +'<div class="rec-t"><div class="rec-v '+(M.pts>=0?'good':'bad')+'">'+sgn(M.pts,1)+'</div><div class="rec-k">Moves you made ('+M.n+')</div><div class="rec-s">'+M.wins+' of '+M.n+' came out ahead</div></div>'
      +'<div class="rec-t"><div class="rec-v '+(S.pts>0?'warn':'muted')+'">'+sgn(S.pts,1)+'</div><div class="rec-k">Moves you skipped ('+S.n+')</div><div class="rec-s">'+(S.n?'what they would have added':'none yet')+'</div></div></div>';
    var rows=R2.moves.filter(function(r){return r.actual!=null;}).slice(0,8);
    if(rows.length){
      h+='<ul class="pbl rec-l">'+rows.map(function(r){
        return '<li><span class="pill '+(r.result==='done'?'start':'done')+'">'+(r.result==='done'?'MADE':'SKIPPED')+'</span> '
          +'<span class="muted">'+esc(dayShort(r.day||''))+'</span> '+esc(shortName(r.add.n))+' for '+esc(shortName(r.drop.n))
          +' &middot; <b class="'+(r.actual>0?'good':(r.actual<0?'bad':''))+'">'+sgn(r.actual,1)+'</b>'
          +' <span class="muted">(expected '+sgn(r.expected||0,1)+(r.final?'':', so far')+')</span></li>';}).join('')+'</ul>';
    }
    h+='<div class="muted" style="margin-top:6px">Points the added player scored minus the dropped player, from the move\'s day to the end of that week. Hockey is noisy, so judge it over a few weeks, not one move.</div>';
  }
  uiPut('Track record',h,{v:'today',s:'main',c:0});
}

/* ---------- Help: plain-English terms + what data this update had ---------- */
function uiHelp(){
  var T=[['Projected pts/game','What we expect a player to score per game from here on: his season, recent form, line and power-play role, and luck all blended. Goalies are per start.'],
    ['Games left','Games his NHL team still plays in this Monday-to-Sunday matchup (days that have started do not count).'],
    ['Line 1 / Pair 2 / PP1','His current even-strength line (forwards) or pair (defense), and power-play unit, from DailyFaceoff.com.'],
    ['UTIL','The one lineup spot that takes any forward or defenseman.'],
    ['Moves','Every move on the Game plan is one to make. It is there only when it adds at least 1 point this week after anything it costs you later (0.5 in the last 3 days, since unused moves don\'t carry over). Only games that fit in your lineup count. The plan uses your league\'s own weekly move limit and your open IR spots.'],
    ['Keep','Tap Keep on any suggested drop and that player is never suggested as a drop for the rest of the matchup week. The plan picks the next best drop instead.'],
    ['Track record','Each suggested move is scored after its games: points the added player scored minus the dropped player, from that day to the end of the week. Moves you skipped are scored too.'],
    ['Long-term cost','What a stream costs you after this week. It compares the two players per game with hot and cold streaks taken out, over their teams\' games in the next 3 weeks, and counts more when the player you drop is widely rostered (someone will likely claim him). No / Small / Real is shown on every move and in Try a swap. Every move\'s gain already has it taken off.'],
    ['Easy / hard opponent','How good the other NHL team is (from the standings). Easy opponents give a small boost.'],
    ['Strength (pts/wk)','On the League tab: what each team\'s best lineup should score per week over the next 4 weeks.'],
    ['Win chance','From both teams\' best daily lineups for the rest of the matchup. Hockey is swingy, so treat it as a lean.']];
  uiPut('What the terms mean','<div>'+T.map(function(t){return '<div class="pc-r"><div><b>'+esc(t[0])+'</b><div class="pc-n">'+esc(t[1])+'</div></div></div>';}).join('')+'</div>',{v:'league',s:'help',c:0});
  var H=D.health||{},lv={ok:['good','All data loaded'],warn:['warn','Some data is missing or old'],bad:['bad','Important data is missing']}[H.level||'ok'];
  var x='<div class="'+lv[0]+'"><b>'+lv[1]+'</b></div>';
  if(H.items&&H.items.length)x+='<ul class="pbl">'+H.items.map(function(t){return '<li>'+esc(t)+'</li>';}).join('')+'</ul>';
  x+='<div class="muted" style="margin-top:6px">Updated '+esc(D.updated)+LK.age()+'. Sources: ESPN (your league), NHL.com, MoneyPuck.com, DailyFaceoff.com.</div>';
  uiPut('Data health',x,{v:'league',s:'help',c:0});
}

/* ---------- Schedule edge: per-team games + opponents + best free agents ---------- */
UI.edgeWin=UI.edgeWin||0;
function uiEdge(){
  var E=D.edge;if(!E||!E.length)return;
  var w=E[Math.min(UI.edgeWin,E.length-1)],h='<div class="stchips">',mineBy={};
  (D.mine||[]).forEach(function(p){if(p.slot!=='IR'&&!isInj(p))mineBy[p.tm]=(mineBy[p.tm]||0)+1;});
  E.forEach(function(x,i){h+='<button type="button" class="chip-btn'+(i===UI.edgeWin?' on':'')+'" data-ew="'+i+'">'+esc(x.label)+'</button>';});
  h+='</div><div class="muted" style="margin:6px 0">Teams ranked by games and opponent strength (3 easy games beat 3 average ones). Green = weak opponent, red = strong. @ = away. Blue teams are ones you own players on. A dot marks the second game of a back-to-back. Best free-agent skaters from each team are on the right.</div>';
  /* a day with no games left for any team (today after puck drop) is an empty column: leave it out */
  var used={};w.rows.forEach(function(r){r.opps.forEach(function(o){used[o.d]=1;});});
  var days=w.days.filter(function(d){return used[d];});if(!days.length)days=w.days;
  var hd='<th>Team</th><th>GP</th>';
  days.forEach(function(d){hd+='<th>'+esc(d)+'</th>';});
  hd+='<th>Best adds</th>';
  /* pinned copy of the header row (see edgeStick): sits exactly over the real header at rest, stays under the nav bar when scrolling */
  h+='<div class="edge-wrap"><div class="edge-sent"></div><div class="edge-sh" aria-hidden="true"><div class="edge-shbg"><div class="edge-shin scroll"><table class="edge"><thead><tr>'+hd+'</tr></thead></table></div></div></div>';
  h+='<div class="scroll"><table class="edge"><thead><tr>'+hd+'</tr></thead><tbody>';
  w.rows.forEach(function(r){
    var by={};r.opps.forEach(function(o){by[o.d]=o;});
    var n=mineBy[r.tm]||0;
    h+='<tr><td><b'+(n?' class="own"':'')+'>'+esc(r.tm)+'</b></td><td><b>'+r.g+'</b></td>';
    days.forEach(function(d){var di=w.days.indexOf(d),o=by[d],b2b=o&&di>0&&by[w.days[di-1]];h+='<td>'+(o?'<span class="'+(o.t==='weak'?'good':o.t==='strong'?'bad':'muted')+'">'+(o.h?'':'@')+esc(o.o)+'</span>'+(b2b?'<i class="b2b"></i>':''):'')+'</td>';});
    h+='<td>'+(r.fa.length?r.fa.map(function(p){return '<a class="pl" data-id="'+p.id+'" data-noav="1">'+esc(shortName(p.n))+'</a> <span class="muted">'+esc(p.pos)+(p.w?' W':'')+'</span>';}).join('<br>'):'<span class="muted">none</span>')+'</td></tr>';
  });
  h+='</tbody></table></div></div>';
  uiPut('Schedule advantage',h,{v:'roster',s:'week',c:0});
  edgeStick();
}
/* Schedule advantage: the day header stays pinned while you scroll down the table.
   The table scrolls sideways, and a sideways scroller blocks a plain sticky <th>, so a copy of the header is pinned instead.
   Column widths are copied from the real header whenever the table resizes (ResizeObserver, never in a scroll handler);
   the sideways scroll position is copied on scroll (passive, one property write). */
function edgeStick(){
  if(UI.edgeRO){UI.edgeRO.disconnect();UI.edgeRO=null;}
  if(UI.edgeIO){UI.edgeIO.disconnect();UI.edgeIO=null;}
  var root=document.querySelector('.card[data-ut="Schedule advantage"] .edge-wrap');if(!root)return;
  var sc=root.querySelector(':scope>.scroll'),sh=root.querySelector('.edge-shin'),tb=sc&&sc.querySelector('table.edge'),ct=sh&&sh.querySelector('table.edge');
  if(!sc||!sh||!tb||!ct)return;
  var real=tb.querySelectorAll('thead th'),copy=ct.querySelectorAll('th');
  var sync=function(){
    var w=tb.getBoundingClientRect().width;if(!w)return;
    ct.style.width=w+'px';
    for(var i=0;i<real.length&&i<copy.length;i++)copy[i].style.width=real[i].getBoundingClientRect().width+'px';
    sh.scrollLeft=sc.scrollLeft;
    sh.classList.add('ready');root.classList.add('ready');
  };
  /* hairline under the header only once it is pinned (IntersectionObserver: no scroll handler, no layout reads while scrolling) */
  var bg=root.querySelector('.edge-shbg'),hr=root.querySelector(':scope>.edge-sent');
  if(window.IntersectionObserver&&bg&&hr){
    var pr=document.createElement('div');pr.style.cssText='position:fixed;top:0;height:calc(var(--sat) + 54px);visibility:hidden;pointer-events:none';
    document.body.appendChild(pr);var nav=Math.round(pr.getBoundingClientRect().height);pr.remove();
    UI.edgeIO=new IntersectionObserver(function(es){es.forEach(function(e){
      bg.classList.toggle('pinned',!e.isIntersecting&&e.boundingClientRect.top<nav+1);});},{rootMargin:(-nav-1)+'px 0px 0px 0px',threshold:1});
    UI.edgeIO.observe(hr);
  }
  sc.addEventListener('scroll',function(){sh.scrollLeft=sc.scrollLeft;},{passive:true});
  if(window.ResizeObserver){UI.edgeRO=new ResizeObserver(sync);UI.edgeRO.observe(tb);}
  sync();
}

var _mo=null,_msy=0;
function uiModalWatch(){
  var m=document.getElementById('modal');if(!m||_mo)return;
  _mo=new MutationObserver(function(){
    var open=m.classList.contains('open'),b=document.body;
    if(open&&!b.classList.contains('mlock')){_msy=window.pageYOffset||0;b.style.top=(-_msy)+'px';b.classList.add('mlock');}
    else if(!open&&b.classList.contains('mlock')){b.classList.remove('mlock');b.style.top='';window.scrollTo(0,_msy);}
  });
  _mo.observe(m,{attributes:true,attributeFilter:['class']});
}
function uiStart(){uiModalWatch();
  setInterval(function(){var el=document.getElementById('sub');if(el)el.textContent=D.league+' \u00b7 record '+D.rec+' \u00b7 updated '+D.updated+LK.age();},60000);
  uiBuild();uiLayout();
  var secs=$$('section[id^="t-"]'),q=false;
  var mo=new MutationObserver(function(){if(q)return;q=true;setTimeout(function(){q=false;uiLayout();},0);});
  secs.forEach(function(s){mo.observe(s,{childList:true});});
  var mo2=new MutationObserver(function(){if(!decQ){decQ=true;(window.requestAnimationFrame||setTimeout)(uiDecorate);}});
  mo2.observe(document.body,{childList:true,subtree:true});
  document.addEventListener('click',function(e){
    var t=e.target;if(!t||!t.closest)return;
    var ck=t.closest('[data-chk]');
    if(ck){tdToggle(ck);return;}
    var ex=t.closest('[data-exp]');
    if(ex&&!t.closest('a,button:not([data-exp])')){var k=ex.getAttribute('data-exp'),nx=ex.nextElementSibling,x=(nx&&nx.id==='x-'+k)?nx:document.getElementById('x-'+k);/* the same move can be on Today and the Game plan: open the one tapped */UI.exp=UI.exp||{};UI.exp[k]=!UI.exp[k];ex.classList.toggle('open',UI.exp[k]);if(x)rxToggle(x,UI.exp[k]);return;}
    var kb=t.closest('[data-keep]');
    if(kb){kpClick(kb.getAttribute('data-keep'));return;}
    var ts=t.closest('details.tsmall > summary');
    if(ts){UI.open.tsmall=!ts.parentNode.open;}
    var g=t.closest('[data-go]');
    if(g){showTab(g.getAttribute('data-go'));return;}
    if(t.closest('#phBtn')){UI.photos=!UI.photos;try{localStorage.setItem('fh_photos',UI.photos?'on':'off');}catch(x){}uiPhotos();return;}
    var b=t.closest('[data-st]');
    if(b){UI.st.sel=b.getAttribute('data-st');uiStreams();return;}
    b=t.closest('[data-stpos]');
    if(b){UI.st.pos=b.getAttribute('data-stpos');uiStreams();return;}
    b=t.closest('[data-ew]');
      if(b){UI.edgeWin=+b.getAttribute('data-ew');uiEdge();return;}
      b=t.closest('[data-sw]');
    if(b){WI.add=b.getAttribute('data-sw');WI.addQ='';if(typeof streamsRender==='function')streamsRender();showTab('moves/swap');return;}
    var h=t.closest('.card.collapsible > h2');
    if(h){cardToggle(h.parentNode);}
  });
}

/* ---------- player card (redesigned) ---------- */
function pcTrend(p){
  var c=p.own_chg;if(c==null||isNaN(c)||Math.abs(c)<0.1)return '';
  return '<span class="pc-tr '+(c>0?'u':'d')+'">'+(c>0?'\u25B2':'\u25BC')+f(Math.abs(c),1)+'</span>';
}
/* how many ESPN leagues roster and start him: a quick trust check on an add nobody knows */
function ownLine(p){
  if(!p||(p.pst==null&&p.own==null))return '';
  var c=p.own_chg,tr=(c!=null&&Math.abs(c)>=1)?' '+pcTrend(p):'';
  if(p.pst==null)return '<span>Rostered in '+f(p.own,0)+'% of ESPN leagues'+tr+'</span>';
  return '<span>Started in '+f(p.pst,0)+'% of ESPN leagues</span>'+(p.own!=null?' &middot; <span>'+f(p.own,0)+'% rostered'+tr+'</span>':'');
}
function pcTag(p){
  if(p.out==null||p.ppg==null||(p.gp!=null&&p.gp<6))return '';
  var d=p.out-p.ppg;
  return d>=0.25?'<span class="pc-vt u" title="Likely to improve">\u25B2</span>':(d<=-0.25?'<span class="pc-vt d" title="Running hot">\u25BC</span>':'');
}
function pcWeak(grp){
  var a=(D.mine||[]).filter(function(x){return x.grp===grp&&x.slot!=='IR';});
  a.sort(function(x,y){return x.out-y.out;});return a[0]||null;
}
function pcShort(n){return typeof shortName==='function'?shortName(n):n;}
function pcToday(p){
  if(!p.gt)return tile2('No game','Today');
  var now=Date.now(),t=p.gt,s;
  try{s=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit'}).format(new Date(t));}catch(e){s='';}
  return now>=t?tile2('Started','Today'):tile2(s,'Game tonight (ET)');
}
function tile2(v,k){return '<div class="pc-t"><div class="pc-tv">'+v+'</div><div class="pc-tk">'+k+'</div></div>';}
function modal(p){
  var isG=p.grp==='G',unit=isG?'pts/start':'pts/game';
  function tile(v,k){return '<div class="pc-t"><div class="pc-tv">'+v+'</div><div class="pc-tk">'+k+'</div></div>';}
  function row(k,v,note){return '<div class="pc-r"><div>'+k+(note?'<div class="pc-n">'+note+'</div>':'')+'</div><b>'+v+'</b></div>';}
  var slot=p.slot==='FA'?({FREEAGENT:'Free agent',WAIVERS:'Waivers'}[p.st]||p.st||'Free agent'):p.slot;
  var own=p.slot!=='FA'?ownerTeam(p.id):null;
  if(own&&!own.me)slot='On '+own.name;                    /* someone else's player (opened from search or a matchup) */
  var sub=[esc(p.pos),esc(p.tm),esc(slot)];if(p.own!=null)sub.push(f(p.own,0)+'% rostered'+(pcTrend(p)?' '+pcTrend(p):''));
  var h='<div class="mhead">'+(typeof avHtml==='function'?avHtml(p.id,p.tm):'')
    +'<div class="pc-id"><b>'+esc(p.n)+'</b><div class="muted">'+sub.join(' &middot; ')+'</div></div>'
    +'<button class="x" id="mx">&times;</button></div>';
  if(p.inj&&p.inj!=='ACTIVE')h+='<div class="pc-inj">Status: '+esc(injLabel(p.inj))+'</div>';
  var pct=UI.pct==='gl'?'gl':'ov';CMP.on=false;
  h+='<div class="pcseg'+(pct==='gl'?' two':'')+'" role="tablist"><i class="th"></i><button type="button" role="tab" data-pct="ov"'+(pct==='ov'?' class="on"':'')+'>Overview</button><button type="button" role="tab" data-pct="gl"'+(pct==='gl'?' class="on"':'')+'>Game log</button></div><div id="pcOv"'+(pct==='gl'?' hidden':'')+'>';

  /* headline + plain-English verdict */
  var d=(p.out!=null&&p.ppg!=null)?p.out-p.ppg:null,vc='pc-flat',vt='Producing about what we expect';
  if(p.gp!=null&&p.gp<6){vt='Small sample so far, early read';}
  else if(d!=null&&d>=0.25){vc='pc-up';vt='▲ Underperforming his role, likely to improve';}
  else if(d!=null&&d<=-0.25){vc='pc-down';vt='▼ Running hot, may cool off';}
  h+='<div class="pc-hero"><div class="pc-k">Projected '+unit+'</div><div class="pc-big">'+f(p.out)+'</div>'
    +'<div class="pc-sub">Averaging '+f(p.ppg)+' this season'+(p.rec!=null?' &middot; '+f(p.rec)+' over the last 15 days':'')+'</div>'
    +'<span class="pc-chip '+vc+'">'+vt+'</span></div>';

  /* quick tiles */
  var t='';
  if(p.gl!=null)t+=tile(p.gl,'Games left this week');else if(p.g7!=null)t+=tile(p.g7,'Games, next 7 days');
  if(p.rl&&p.rl!=='Not listed')t+=tile(esc(rlTxt(p.rl)),'Line / power play');
  if(isG){if(p.sp!=null)t+=tile(Math.round(p.sp*100)+'%','Start chance');}
  else if(p.toi!=null)t+=tile(f(p.toi,1)+' min','Ice time / game');
  t+=pcToday(p);
  if(t)h+='<div class="pc-tiles">'+t+'</div>';
  h+='<div class="pc-acts">'+cmpBtn(p,null,'Compare with…')+'</div>';

  var wk=null;
  if(p.slot==='FA'){
    wk=pcWeak(p.grp);var u=wk?p.out-wk.out:up(p);
    var wiW=(D.streams&&D.streams.whatif)||null,canSw=!!(wk&&wiW&&wiFind(wiW.fas,p.id));   /* Try swap only knows the free agents the plan scored */
    h+='<div class="pc-vs"><div>'+(wk?'Vs your weakest '+p.grp+', <b>'+esc(pcShort(wk.n))+'</b> ('+f(wk.out)+'): ':'Versus your weakest '+p.grp+': ')
      +'<b class="'+(u>=0.2?'good':(u<0?'bad':''))+'">'+sgn(u)+'</b> '+unit+'</div>'
      +(canSw?'<button type="button" class="pc-swap" id="pcSwap">Try swap</button>':'')+'</div>';
  }

  /* usage */
  var u='';
  if(!isG&&p.tr!=null)u+=row('Ice time, last 5 games',sgn(p.tr,1)+' min','Compared with his season average');
  if(!isG&&p.pp!=null)u+=row('Power-play time',f(p.pp,1)+' min / game');
  if(u)h+='<div class="pc-h">Usage</div>'+u;

  /* season */
  h+='<div class="pc-h">Season &middot; '+(p.gp==null?'-':p.gp)+' games</div><div class="pc-grid6">';
  if(isG){
    h+=tile(p.w==null?'-':p.w,'Wins')+tile(p.ga==null?'-':p.ga,'Goals against')+tile(p.svp==null?'-':f(p.svp,3),'Save %');
    if(p.qs!=null)h+=tile(f(p.qs*100,0)+'%','Quality starts');
  }else{
    h+=tile(p.g,'Goals')+tile(p.a,'Assists')+tile(p.ppp,'PP points')+tile(p.sog,'Shots')+tile(p.hit,'Hits')+tile(p.blk,'Blocks');
  }
  h+='</div>';

  /* advanced: the technical numbers, folded away */
  var a='';
  if(p.exp!=null)a+=row('Luck-adjusted',f(p.exp)+' '+unit,'What he would average if puck luck evened out');
  if(p.proj!=null)a+=row('ESPN projection',f(p.proj)+' '+unit);
  if(!isG&&p.ixg!=null)a+=row('Expected goals',f(p.ixg,1),'Goals his shot quality suggests');
  if(!isG&&p.gx!=null)a+=row('Goals vs expected',sgn(p.gx,1),p.gx>=1?'Scoring more than his chances suggest (may cool)':(p.gx<=-1?'Scoring less than his chances suggest (due to rise)':'In line with his chances'));
  if(!isG&&p.shp!=null)a+=row('Shooting %',f(p.shp*100,0)+'%');
  if(isG&&p.gsax!=null)a+=row('Goals saved vs expected',sgn(p.gsax,1));
  if(a)h+='<details class="pc-det"><summary>Advanced stats</summary>'+a+'</details>';

  if(p.fl&&p.fl.length)h+='<ul class="pc-fl">'+p.fl.map(function(x){return '<li>'+esc(x)+'</li>';}).join('')+'</ul>';
  h+='</div><div id="pcGl" data-id="'+p.id+'"'+(pct==='gl'?'':' hidden')+'></div>';
  sheetShow(h);
  if(pct==='gl')pcTabSet('gl');
  var sw=$('#pcSwap');
  if(sw&&wk)sw.addEventListener('click',function(){
    sheetCloseNow();
    if(typeof showTab==='function')showTab('moves/swap');
    if(typeof wiPick==='function'){wiPick('drop',String(wk.id));wiPick('add',String(p.id));}
    setTimeout(function(){var o=document.getElementById('wiOut');if(o&&o.scrollIntoView){try{o.scrollIntoView({block:'center'});}catch(e){}}glReset();},120);
  });
}

SF.compare='<svg viewBox="0 0 28 28"><path class="s" d="M8.5 22V12M14 22V6.5M19.5 22v-7.5"/></svg>';

/* ---------- show a sheet, or swap what an open sheet shows (no second slide-up) ---------- */
function sheetShow(h){
  var m=$('#modal'),bx=m.querySelector('.box');
  if(typeof SH!=='undefined'&&SH.open&&bx&&m.classList.contains('open')&&!m.classList.contains('fading')){
    bx.innerHTML='<div class="grab"></div>'+h;
    var x=bx.querySelector('#mx');if(x){x.innerHTML=SF.xmark;x.className='x gbtn glass';x.setAttribute('aria-label','Close');}
    var d=SH.dir||'';SH.dir=null;
    bx.scrollTop=0;bx.classList.remove('sw-in','sw-r','sw-l');void bx.offsetWidth;bx.classList.add(d==='r'?'sw-r':(d==='l'?'sw-l':'sw-in'));
  }else{
    m.innerHTML='<div class="box">'+h+'</div>';m.classList.add('open');
    if(typeof sheetOpen==='function')sheetOpen();
  }
  var mx=$('#mx');if(mx)mx.addEventListener('click',closeModal);
  return m.querySelector('.box');
}

/* ---------- game logs: recent games, loaded from gamelog.json only when a card or Compare needs them ---------- */
var GLG={d:null,p:null};
function glLoad(){
  if(GLG.p)return GLG.p;
  if(!D.gl||!D.gl.n||typeof fetch!=='function'){GLG.p=Promise.resolve(null);return GLG.p;}
  GLG.p=fetch('gamelog.json?v='+D.gl.v).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;})
    .then(function(j){GLG.d=(j&&j.p)?j:null;return GLG.d;});
  return GLG.p;
}
function glRows(id){return (GLG.d&&GLG.d.p&&GLG.d.p[String(id)])||[];}
function glAvg(rows,n){var r=rows.slice(0,n);if(!r.length)return null;return r.reduce(function(s,x){return s+x[3];},0)/r.length;}
function glFmt(ms,o){try{return new Intl.DateTimeFormat('en-US',Object.assign({timeZone:'America/New_York'},o)).format(new Date(ms));}catch(e){return '';}}
function glToi(s){if(!s)return '-';var m=Math.floor(s/60),x=s%60;return m+':'+(x<10?'0':'')+x;}
function glOpp(r){return (r[2]?'':'@')+esc(r[1]);}
function glPts(x){return (Math.round(x*10)/10).toFixed(1);}
/* bar chart of fantasy points, oldest on the left; dashed line = what we project per game */
function glChart(rows,proj,n){
  var r=rows.slice(0,n||10).reverse();if(!r.length)return '';
  var vals=r.map(function(x){return x[3];}),neg=Math.min.apply(null,vals)<0;
  var W=330,H=neg?140:128,top=18,bot=neg?36:22,ch=H-top-bot,gap=6,bw=Math.min(26,(W-gap*(r.length-1))/r.length);
  var mx=Math.max.apply(null,vals.concat([(proj||0)*1.4,1])),mn=Math.min.apply(null,vals.concat([0]));
  var span=mx-mn||1,y0=top+ch*(mx/span),sc=ch/span,x0=(W-(bw*r.length+gap*(r.length-1)))/2;
  var s='<svg class="glc" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Fantasy points in his last '+r.length+' games">';
  s+='<line x1="0" x2="'+W+'" y1="'+y0+'" y2="'+y0+'" class="glc-base"/>';
  r.forEach(function(x,i){
    var v=x[3],h=Math.max(2,Math.abs(v)*sc),X=x0+i*(bw+gap),Y=v>=0?y0-h:y0;
    var c=v<0?'neg':(proj!=null&&v>=proj?'hi':'lo');
    s+='<rect x="'+X+'" y="'+Y+'" width="'+bw+'" height="'+h+'" rx="'+Math.min(6,bw/3)+'" class="glc-'+c+'" style="animation-delay:'+(i*35)+'ms"/>';
    s+='<text x="'+(X+bw/2)+'" y="'+(v>=0?Y-5:Y+h+11)+'" class="glc-v">'+glPts(v)+'</text>';
    s+='<text x="'+(X+bw/2)+'" y="'+(H-6)+'" class="glc-d">'+esc(glFmt(x[0],{month:'numeric',day:'numeric'}))+'</text>';
  });
  if(proj!=null&&proj>0){var py=y0-proj*sc;s+='<line x1="0" x2="'+W+'" y1="'+py+'" y2="'+py+'" class="glc-proj"/>';}
  return s+'</svg>';
}
function glTable(p,rows,all){
  var isG=p.grp==='G',show=all?rows:rows.slice(0,5);
  var hd=isG?['Date','Opp','Pts','Res','GA','SV','SV%']:['Date','Opp','Pts','G','A','SOG','HIT','BLK','TOI'];
  var nx=GLG.d&&GLG.d.nx&&GLG.d.nx[p.tm],h='';
  if(nx&&nx[0]>Date.now())h+='<div class="gl-nx">'+SF.clock+'<span>Next: <b>'+(nx[2]?'vs ':'@ ')+esc(nx[1])+'</b> &middot; '+esc(glFmt(nx[0],{weekday:'short',month:'numeric',day:'numeric'}))+', '+esc(glFmt(nx[0],{hour:'numeric',minute:'2-digit'}))+' ET</span></div>';
  var cw=isG?[15,16,16,13,12,12,16]:[13,14,15,8,8,10,9,9,14];
  h+='<div class="glt-w"><table class="glt"><colgroup>'+cw.map(function(w){return '<col style="width:'+w+'%">';}).join('')+'</colgroup><thead><tr>'+hd.map(function(x){return '<th>'+x+'</th>';}).join('')+'</tr></thead><tbody>';
  show.forEach(function(r){
    var c=r[3]<0?'neg':(p.out!=null&&r[3]>=p.out?'hi':'');
    h+='<tr><td>'+esc(glFmt(r[0],{month:'numeric',day:'numeric'}))+'</td><td>'+glOpp(r)+'</td><td><span class="glp '+c+'">'+glPts(r[3])+'</span></td>';
    if(isG)h+='<td>'+(r[4]?'<b class="good">W</b>':'<span class="muted">-</span>')+(r[8]?' <span class="muted">SO</span>':'')+'</td><td>'+r[5]+'</td><td>'+r[6]+'</td><td>'+(r[7]?f(r[6]/r[7],3).replace(/^0/,''):'-')+'</td>';
    else h+='<td>'+r[4]+'</td><td>'+r[5]+'</td><td>'+r[6]+'</td><td>'+r[7]+'</td><td>'+r[8]+'</td><td>'+glToi(r[9])+'</td>';
    h+='</tr>';
  });
  h+='</tbody></table></div>';
  if(rows.length>5)h+='<button type="button" class="gbtn2 glt-more" data-glall="'+p.id+'">'+(all?'Show fewer':'Show all '+rows.length+' games')+'</button>';
  return h;
}
function glPane(p,all){
  var isG=p.grp==='G',unit=isG?'pts/start':'pts/game';
  if(!GLG.d){
    if(GLG.p&&!GLG.done)return '<div class="gl-wait"><span class="spin"></span>Loading recent games&hellip;</div>';
    return '<div class="gl-none">The game log isn’t here yet. It shows up with the next update, usually within 20 minutes.</div>';
  }
  var rows=glRows(p.id);
  if(!rows.length)return '<div class="gl-none">No games played in the last few weeks.</div>';
  var a5=glAvg(rows,5),a10=glAvg(rows,10),best=rows.reduce(function(b,r){return r[3]>b[3]?r:b;},rows[0]);
  var d=p.out!=null&&a5!=null?a5-p.out:null;
  var h='<div class="pc-tiles">'+tile2(f(a5,1),'Last '+Math.min(5,rows.length)+' games ('+unit+')')+tile2(f(a10,1),'Last '+Math.min(10,rows.length)+' games')
    +tile2('<span class="'+(d==null?'':(d>=0.2?'good':(d<=-0.2?'bad':'')))+'">'+(d==null?'-':sgn(d,1))+'</span>','Last 5 vs projection')+'</div>';
  var hot=rows.slice(0,5).filter(function(r){return p.out!=null&&r[3]>=p.out;}).length;
  var n5=Math.min(5,rows.length),say=d==null?'':(d>=0.4&&hot*2>n5?'Hot: beating his projection lately.':(d<=-0.4&&hot*2<n5?'Cold: below his projection lately.':(d>=0.4?'Streaky: a big game or two is lifting his average.':(d<=-0.4?'Up and down, and below his projection overall.':'Steady: close to his projection lately.'))));
  h+='<div class="gl-say">'+say
    +' '+hot+' of his last '+n5+' '+(isG?'appearances':'games')+' were at or above it. Best: '+glPts(best[3])+' '+glOpp(best)+' on '+esc(glFmt(best[0],{month:'short',day:'numeric'}))+'.</div>';
  h+='<div class="pc-h">Fantasy points, last '+Math.min(10,rows.length)+' '+(isG?'appearances':'games')+'</div><div class="glc-w">'+glChart(rows,p.out,10)+'<div class="glc-lg"><span><i class="sw-hi"></i>At or above projection</span><span><i class="sw-pj"></i>Projected '+f(p.out,1)+'</span></div></div>';
  h+='<div class="pc-h">Game log</div>'+glTable(p,rows,all);
  return h;
}
function pcTabSet(t){
  UI.pct=t;
  var s=$('#modal .pcseg');if(!s)return;
  s.classList.toggle('two',t==='gl');
  $$('#modal .pcseg button').forEach(function(b){var on=b.getAttribute('data-pct')===t;b.classList.toggle('on',on);b.setAttribute('aria-selected',on?'true':'false');});
  var ov=$('#pcOv'),gl=$('#pcGl');if(ov)ov.hidden=t!=='ov';if(gl)gl.hidden=t!=='gl';
  if(t==='gl'&&gl){
    var id=gl.getAttribute('data-id'),p=ALL[id];if(!p)return;
    var pr=glLoad();gl.innerHTML=glPane(p,false);
    pr.then(function(){GLG.done=true;var g=$('#pcGl');if(g&&g.getAttribute('data-id')===id&&!g.hidden)g.innerHTML=glPane(p,false);});
  }
}

/* ---------- Compare: two players side by side ---------- */
var CMP={a:null,b:null,pick:null};
function cmpMine(p){return (D.mine||[]).some(function(x){return x.id===p.id;});}
function cmpGames(p){return p.gl!=null?p.gl:(p.g7||0);}
function cmpWeek(p){return (p.out||0)*cmpGames(p)*(p.grp==='G'?(p.sp||0.5):1)*(isInj(p)?0:1);}
function cmpWho(p){
  if(cmpMine(p))return 'Your team';
  if(p.slot==='FA')return p.st==='WAIVERS'?'Waivers':'Free agent';
  var t=(typeof ownerTeam==='function')?ownerTeam(p.id):null;return t?t.name:'Rostered';
}
function cmpPlanMoves(){var P=(typeof lkPlan==='function'&&D.gameplan)?lkPlan(D.gameplan):null;return (P&&P.moves)||[];}
function cmpDefault(a){
  var mv=cmpPlanMoves(),m;
  if(cmpMine(a)){
    m=mv.filter(function(x){return x.drop.id===a.id;})[0];if(m&&ALL[m.add.id])return ALL[m.add.id];
    var fa=(D.fas||[]).filter(function(x){return x.grp===a.grp&&!isInj(x)&&x.id!==a.id;}).sort(function(x,y){return cmpWeek(y)-cmpWeek(x)||y.out-x.out;});
    return fa[0]||null;
  }
  m=mv.filter(function(x){return x.add.id===a.id;})[0];if(m&&ALL[m.drop.id])return ALL[m.drop.id];
  return pcWeak(a.grp);
}
function cmpOpen(a,b){
  if(!a)return;
  CMP.a=a;CMP.b=b||cmpDefault(a);CMP.pick=null;
  var pr=glLoad();cmpRender();
  pr.then(function(){GLG.done=true;if(CMP.on)cmpRender(true);});
}
function cmpRows(a,b){
  var G=a.grp==='G'&&b.grp==='G',L=[];
  function per(p,k){return p.gp?(p[k]||0)/p.gp:null;}
  var a5=GLG.d?glAvg(glRows(a.id),5):undefined,b5=GLG.d?glAvg(glRows(b.id),5):undefined;
  L.push(['Projected '+(G?'pts/start':'pts/game'),a.out,b.out,2,'The number every suggestion uses']);
  L.push([G?'Games left (team)':'Games left this week',cmpGames(a),cmpGames(b),0]);
  L.push(['Projected pts this week',cmpWeek(a),cmpWeek(b),1,G?'Per start x games x start chance':'Per game x games left']);
  if(a5!==undefined)L.push(['Last 5 games',a5,b5,1,'Fantasy points per game, most recent']);
  L.push(['Season',a.ppg,b.ppg,2,(G?'Pts/start':'Pts/game')+' so far']);
  L.push(['Last 15 days',a.rec,b.rec,2]);
  if(G){
    L.push(['Start chance',a.sp!=null?a.sp*100:null,b.sp!=null?b.sp*100:null,0,null,'%']);
    L.push(['Save %',a.svp,b.svp,3]);
    if(a.gsax!=null||b.gsax!=null)L.push(['Goals saved vs expected',a.gsax,b.gsax,1]);
  }else{
    L.push(['Ice time / game',a.toi,b.toi,1,null,' min']);
    L.push(['Power-play time / game',a.pp,b.pp,1,null,' min']);
    L.push(['Shots / game',per(a,'sog'),per(b,'sog'),1]);
    L.push(['Hits / game',per(a,'hit'),per(b,'hit'),1]);
    L.push(['Blocks / game',per(a,'blk'),per(b,'blk'),1]);
  }
  L.push(['Rostered in ESPN leagues',a.own,b.own,0,null,'%']);
  return L;
}
function cmpRow(r){
  var k=r[0],x=r[1],y=r[2],d=r[3],suf=r[5]||'',ok=x!=null&&y!=null&&!isNaN(x)&&!isNaN(y);
  var wa=ok&&x>y+1e-9,wb=ok&&y>x+1e-9,mx=ok?Math.max(Math.abs(x),Math.abs(y),1e-9):1;
  var fa=x==null||isNaN(x)?'-':f(x,d)+suf,fb=y==null||isNaN(y)?'-':f(y,d)+suf;
  var pa=ok&&x>0?Math.round(100*x/mx):0,pb=ok&&y>0?Math.round(100*y/mx):0;
  return '<div class="cm-r"><div class="cm-v'+(wa?' w':'')+'">'+fa+'</div><div class="cm-k">'+esc(k)+(r[4]?'<span>'+esc(r[4])+'</span>':'')+'</div><div class="cm-v r'+(wb?' w':'')+'">'+fb+'</div>'
    +'<div class="cm-bar"><i class="'+(wa?'w':'')+'" style="--w:'+pa+'%"></i><i class="'+(wb?'w b':'b')+'" style="--w:'+pb+'%"></i></div></div>';
}
function cmpSide(p,k){
  return '<div class="cm-p">'+avHtml(p.id,p.tm)+'<a class="pl cm-n" data-noav="1" data-id="'+p.id+'">'+esc(shortName(p.n))+'</a>'
    +'<div class="cm-s">'+esc(p.pos)+' &middot; '+esc(p.tm)+(p.rl&&p.rl!=='Not listed'?' &middot; '+esc(rlTxt(p.rl)):'')+'</div>'
    +'<div class="cm-tag'+(cmpMine(p)?' mine':'')+'">'+esc(cmpWho(p))+'</div>'
    +(p.inj&&p.inj!=='ACTIVE'?'<div class="cm-inj">'+esc(injLabel(p.inj))+'</div>':'')
    +'<button type="button" class="cm-chg" data-cmchg="'+k+'">Change</button></div>';
}
function cmpForm(a,b){
  if(!GLG.d)return GLG.p&&!GLG.done?'<div class="gl-wait"><span class="spin"></span>Loading recent games&hellip;</div>':'';
  var ra=glRows(a.id).slice(0,8).reverse(),rb=glRows(b.id).slice(0,8).reverse();
  if(!ra.length&&!rb.length)return '';
  var n=Math.max(ra.length,rb.length),W=330,H=118,top=14,bot=18,ch=H-top-bot;
  var all=ra.concat(rb).map(function(r){return r[3];}),mx=Math.max.apply(null,all.concat([1])),mn=Math.min.apply(null,all.concat([0])),span=mx-mn||1,y0=top+ch*mx/span,sc=ch/span;
  var slot=(W-8)/n,bw=Math.min(14,(slot-6)/2);
  var s='<svg class="glc" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Last games side by side"><line x1="0" x2="'+W+'" y1="'+y0+'" y2="'+y0+'" class="glc-base"/>';
  function bars(rr,off,cls){rr.forEach(function(r,i){var j=i+(n-rr.length),v=r[3],h=Math.max(2,Math.abs(v)*sc),X=4+j*slot+slot/2+off,Y=v>=0?y0-h:y0;
    s+='<rect x="'+X+'" y="'+Y+'" width="'+bw+'" height="'+h+'" rx="'+Math.min(5,bw/3)+'" class="'+cls+'" style="animation-delay:'+(j*30)+'ms"><title>'+glPts(v)+' '+(r[2]?'vs ':'@ ')+esc(r[1])+'</title></rect>';});}
  bars(ra,-bw-1,'cmc-a');bars(rb,1,'cmc-b');
  s+='<text x="4" y="'+(H-4)+'" class="glc-d" style="text-anchor:start">Older</text><text x="'+(W-4)+'" y="'+(H-4)+'" class="glc-d" style="text-anchor:end">Latest</text></svg>';
  return '<div class="pc-h">Last '+n+' games</div><div class="cm-lg"><span><i class="cmc-a"></i>'+esc(shortName(a.n))+' '+f(glAvg(glRows(a.id),n),1)+'/g</span><span><i class="cmc-b"></i>'+esc(shortName(b.n))+' '+f(glAvg(glRows(b.id),n),1)+'/g</span></div><div class="glc-w">'+s+'</div>';
}
function cmpVerdict(a,b){
  var wa=cmpWeek(a),wb=cmpWeek(b),dw=wa-wb,dp=(a.out||0)-(b.out||0),na=shortName(a.n),nb=shortName(b.n),ga=cmpGames(a),gb=cmpGames(b);
  var lead=Math.abs(dw)<0.5?'About even this week':(esc(dw>0?na:nb)+' <b class="good">+'+f(Math.abs(dw),1)+'</b> pts this week');
  var why=[];
  if(ga!==gb)why.push(esc(ga>gb?na:nb)+' has '+Math.max(ga,gb)+' games left to '+Math.min(ga,gb));
  if(Math.abs(dp)>=0.1)why.push(esc(dp>0?na:nb)+' is better per game by '+f(Math.abs(dp),2));
  else why.push('they are about even per game');
  var later='';
  if(Math.abs(dw)>=0.5&&Math.abs(dp)>=0.1&&(dw>0)!==(dp>0))later='<div class="cm-note">This week favors '+esc(dw>0?na:nb)+' on games, but '+esc(dp>0?na:nb)+' is the better player after this week.</div>';
  return '<div class="cm-ver"><div class="cm-vl">'+lead+'</div><div class="cm-vs">'+why.join(', ')+'.</div>'+later+'</div>';
}
function cmpPicker(k){
  var o=k==='a'?CMP.b:CMP.a;
  return '<div class="cm-pick"><input type="search" id="cmQ" placeholder="Search any player" autocomplete="off" enterkeyhint="search"><div id="cmList">'+cmpList(k,'',o)+'</div><button type="button" class="gbtn2" data-cmchg="">Cancel</button></div>';
}
function cmpList(k,q,o){
  var n=wiNorm(q).trim(),cur=k==='a'?CMP.a:CMP.b,seen={},out=[];
  Object.keys(ALL).forEach(function(id){var p=ALL[id];if(seen[p.id]||(cur&&p.id===cur.id)||(o&&p.id===o.id))return;seen[p.id]=1;
    if(n){if(wiNorm(p.n).indexOf(n)<0)return;}else if(o&&p.grp!==o.grp)return;
    out.push(p);});
  if(!n){                         /* no search yet: your players and the best free agents at his position */
    var mine=out.filter(function(p){return cmpMine(p)&&p.slot!=='IR';}).sort(function(x,y){return x.out-y.out;}).slice(0,6);
    var fa=out.filter(function(p){return p.slot==='FA'&&!isInj(p);}).sort(function(x,y){return cmpWeek(y)-cmpWeek(x);}).slice(0,6);
    return (mine.length?'<div class="cm-gh">Your team, weakest first</div>'+mine.map(cmpOpt).join(''):'')+(fa.length?'<div class="cm-gh">Best free agents this week</div>'+fa.map(cmpOpt).join(''):'');
  }
  out.sort(function(x,y){return (y.out||0)-(x.out||0);});
  return out.length?out.slice(0,12).map(cmpOpt).join(''):'<div class="muted" style="padding:10px 2px">No player matches.</div>';
}
function cmpOpt(p){
  return '<button type="button" class="cm-opt" data-cmset="'+p.id+'">'+avHtml(p.id,p.tm)+'<span class="cm-on"><b>'+esc(p.n)+'</b><span>'+esc(p.pos)+' &middot; '+esc(p.tm)+' &middot; '+esc(cmpWho(p))+'</span></span><span class="cm-ov">'+f(p.out,2)+'<i>'+(p.grp==='G'?'pts/start':'pts/gm')+'</i></span></button>';
}
function cmpRender(keep){
  var a=CMP.a,b=CMP.b;
  var h='<div class="mhead cm-head"><div class="pc-id"><b>Compare</b><div class="muted">'+(b?'This week and beyond':'Pick a second player')+'</div></div><button class="x" id="mx">&times;</button></div>';
  if(CMP.pick){h+=cmpPicker(CMP.pick);}
  else if(!b){h+='<div class="cm-top">'+cmpSide(a,'a')+'<div class="cm-vsx">vs</div><div class="cm-p cm-empty"><button type="button" class="gbtn2" data-cmchg="b">Choose a player</button></div></div>';}
  else{
    h+='<div class="cm-top">'+cmpSide(a,'a')+'<button type="button" class="cm-vsx" data-cmflip="1" aria-label="Swap sides">'+SF.swap+'</button>'+cmpSide(b,'b')+'</div>';
    h+=cmpVerdict(a,b);
    if(a.grp!==b.grp&&(a.grp==='G'||b.grp==='G'))h+='<div class="cm-note">A goalie and a skater are scored differently, so treat this as a rough guide.</div>';
    h+='<div class="cm-rows">'+cmpRows(a,b).map(cmpRow).join('')+'</div>';
    h+=cmpForm(a,b);
    var mineA=cmpMine(a),mineB=cmpMine(b),fa=mineA&&b.slot==='FA'?[b,a]:(mineB&&a.slot==='FA'?[a,b]:null);
    if(fa)h+='<div class="cm-act"><button type="button" class="pc-swap cm-try" data-cmtry="'+fa[0].id+','+fa[1].id+'">'+SF.swap+' Try add '+esc(shortName(fa[0].n))+', drop '+esc(shortName(fa[1].n))+'</button></div>';
  }
  var y=keep?($('#modal .box')||{}).scrollTop:0;
  var bx=sheetShow(h);CMP.on=true;
  if(keep&&bx&&y)bx.scrollTop=y;
  var q=$('#cmQ');
  if(q){q.addEventListener('input',function(){var l=$('#cmList');if(l)l.innerHTML=cmpList(CMP.pick,q.value,CMP.pick==='a'?CMP.b:CMP.a);});try{q.focus({preventScroll:true});}catch(e){}}
}
function cmpBtn(a,b,label){return '<button type="button" class="gbtn2 cm-btn" data-cmp="'+a.id+(b?','+b.id:'')+'">'+SF.compare+(label||'Compare')+'</button>';}
document.addEventListener('click',function(e){
  var t=e.target;if(!t||!t.closest)return;
  var b=t.closest('[data-cmp]');
  if(b){e.preventDefault();e.stopPropagation();var ids=b.getAttribute('data-cmp').split(',');cmpOpen(ALL[ids[0]],ids[1]?ALL[ids[1]]:null);return;}
  if(!$('#modal').contains(t))return;
  b=t.closest('[data-pct]');if(b){pcTabSet(b.getAttribute('data-pct'));return;}
  b=t.closest('[data-glall]');
  if(b){var g=$('#pcGl'),p=ALL[b.getAttribute('data-glall')];if(g&&p){var all=!g._all;g._all=all;g.innerHTML=glPane(p,all);}return;}
  b=t.closest('[data-cmchg]');if(b){CMP.pick=b.getAttribute('data-cmchg')||null;cmpRender();return;}
  b=t.closest('[data-cmset]');if(b){var np=ALL[b.getAttribute('data-cmset')];if(np){if(CMP.pick==='a')CMP.a=np;else CMP.b=np;}CMP.pick=null;cmpRender();return;}
  b=t.closest('[data-cmflip]');if(b){var x=CMP.a;CMP.a=CMP.b;CMP.b=x;cmpRender(true);return;}
  b=t.closest('[data-cmtry]');
  if(b){var ids=b.getAttribute('data-cmtry').split(',');sheetCloseNow();
    if(typeof showTab==='function')showTab('moves/swap');
    if(typeof wiPick==='function'){wiPick('drop',ids[1]);wiPick('add',ids[0]);}
    setTimeout(function(){var o=document.getElementById('wiOut');if(o&&o.scrollIntoView){try{o.scrollIntoView({block:'center'});}catch(x){}}glReset();},120);return;}
},true);

/* ---------- tabs + startup ---------- */
var TABS=['overview','roster','free','trade','planner','gameplan','streams','league'];
function showTabOld(n){
  if(TABS.indexOf(n)<0)n='overview';
  TABS.forEach(function(t){$('#t-'+t).style.display=(t===n)?'block':'none';$('#nav-'+t).classList.toggle('on',t===n);});
  try{history.replaceState(null,'','#'+n);}catch(e){}
}
document.addEventListener('click',function(e){
  var a=e.target.closest?e.target.closest('a.pl'):null;
  if(a){var p=ALL[a.getAttribute('data-id')];if(p)modal(p);return;}
  if(e.target.id==='modal')closeModal();
});
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeModal();
  var t=e.target;if((e.key==='Enter'||e.key===' ')&&t&&t.matches&&t.matches('[data-gp]')){e.preventDefault();gmPlayer(t.getAttribute('data-gp'));}});
TABS.forEach(function(t){$('#nav-'+t).addEventListener('click',function(){showTab(t);});});
$('#rosterQ').addEventListener('input',function(){R.q=this.value.toLowerCase();rosterRender();});
$('#faQ').addEventListener('input',function(){FA.q=this.value.toLowerCase();faRender();});
$('#faHide').addEventListener('change',function(){FA.hide=this.checked;faRender();});
$('#faGames').addEventListener('change',function(){FA.games=this.checked;faRender();});
$('#faN').addEventListener('change',function(){FA.n=+this.value;faRender();});
$('#title').textContent=D.me;
$('#sub').textContent=D.league+' \u00b7 record '+D.rec+' \u00b7 updated '+D.updated+LK.age();
overview();rosterRender();faRender();tradeInit();leagueRender();plannerRender();
gameplanRender();
/* =====================================================================================================
   MATCHUPS: every game in the league this week, and a head-to-head sheet for each one
   ===================================================================================================== */
var MU={tab:'tn',open:-1,day:null,dd:false};   /* day = index of a past matchup day being viewed (null = today); dd = day picker open */
function muTeam(id){for(var i=0;i<D.teams.length;i++)if(D.teams[i].id===id)return D.teams[i];return {id:id,name:'Team '+id,rec:'',players:[]};}
function muInit(n){var w=String(n||'?').replace(/[^A-Za-z0-9 ]/g,' ').trim().split(/\s+/).filter(Boolean);if(!w.length)return '?';return (w[0].charAt(0)+(w[1]?w[1].charAt(0):w[0].charAt(1)||'')).toUpperCase();}
/* ONE color per team, used by every card in the app (Today, matchup sheet, League > Matchups, game page).
   The server reads it from the team's logo (t.hue: the most colorful thing in the picture); a logo it can't read gets a steady color from the team id.
   pairHues() gives the two colors of a head-to-head: your team keeps its own; if the two logos are too alike the other side turns to a clear contrast. */
function teamHue(t){return t&&t.hue!=null?t.hue:(((+(t&&t.id))||1)*67+200)%360;}
function pairHues(ta,tb){
  var a=teamHue(ta),b=teamHue(tb),d=Math.abs(a-b);d=Math.min(d,360-d);
  if(d<40){
    if(ta&&ta.me)b=(b+150)%360;else if(tb&&tb.me)a=(a+150)%360;
    else if((+(tb&&tb.id)||0)>=(+(ta&&ta.id)||0))b=(b+150)%360;else a=(a+150)%360;
  }
  return [a,b];
}
function muHue(id){return teamHue(muTeam(id));}
function muImg(t){return t.logo?'<img src="'+esc(t.logo)+'" loading="lazy" alt="" onerror="this.remove()">':'';}
function muMono(t,cls){return '<span class="mono '+(cls||'')+'" style="--h:'+muHue(t.id)+'">'+esc(muInit(t.name))+muImg(t)+'</span>';}
function muMe(g){var me=null;D.teams.forEach(function(t){if(t.me)me=t.id;});return me!=null&&(g.a===me||g.b===me);}
function muDayTxt(S){var n=S.dates.length,i=Math.min(S.today,n-1);return S.done?'Final':'Day '+(i+1)+' of '+n;}
/* your own matchup uses the same win chance as the Today card (the league scoreboard's figure can differ by a point) */
function muWin(g){var a=Math.round(g.pa*100),M=D.matchup;
  if(M&&M.p_win!=null&&!(D.sb&&D.sb.done)&&muMe(g)){var me=Math.round(M.p_win*100),mi=null;D.teams.forEach(function(t){if(t.me)mi=t.id;});a=g.a===mi?me:100-me;}
  return {a:a,b:100-a};}
function muTile(g,i,S){
  var A=muTeam(g.a),B=muTeam(g.b),w=muWin(g),lead=g.as===g.bs?0:(g.as>g.bs?1:-1),mine=muMe(g);
  function row(t,sc,pr,on,left){
    return '<div class="mu-r'+(on?' lead':'')+'">'+muMono(t,'mu-mono')+'<div class="mu-n"><b>'+esc(t.name)+(t.me?' <i class="mu-you">You</i>':'')+'</b><span>'+esc(t.rec)+' &middot; '+left+' games left &middot; proj '+f(pr,0)+'</span></div><div class="mu-s">'+f(sc,1)+'</div></div>';}
  return '<button type="button" class="mu-tile'+(mine?' mine':'')+'" data-mu="'+i+'">'
    +row(A,g.as,g.ap,lead>0,g.al)+row(B,g.bs,g.bp,lead<0,g.bl)
    +'<div class="mu-wp"><div class="mu-bar" style="--a:'+pairHues(A,B)[0]+';--b:'+pairHues(A,B)[1]+'"><i style="width:'+w.a+'%"></i><i></i></div>'
    +'<div class="mu-wl"><span>'+w.a+'%</span><span class="mu-wk">'+(S.done?'Final':'Win chance')+'</span><span>'+w.b+'%</span></div></div></button>';
}
function uiMatchups(){
  var S=D.sb,h='';
  if(!S||!S.games||!S.games.length){
    uiPut('Matchups','<div class="muted">Every matchup in the league shows up here after the next data refresh.</div>',{v:'league',s:'games',c:0});return;}
  var today=S.labels[Math.min(S.today,S.labels.length-1)]||'';
  h+='<div class="mu-head"><div><div class="mu-h1">Week '+esc(S.mp)+'</div><div class="mu-h2">'+esc(today)+' &middot; '+muDayTxt(S)+'</div></div>'
    +'<div class="mu-dots">'+S.dates.map(function(d,i){return '<i class="'+(i<S.today||S.done?'p':i===S.today?'t':'')+'"></i>';}).join('')+'</div></div>';
  h+=S.games.map(function(g,i){return muTile(g,i,S);}).join('');
  h+='<div class="muted mu-ft">Tap a matchup for tonight\'s lineups, day-by-day scores and top scorers. Scores as of '+esc(D.updated)+'.</div>';
  uiPut('Matchups',h,{v:'league',s:'games',c:0});
}

/* ---- the sheet ---- */
function muStatus(p,S,k){
  if(k!=null)return muFutSt(p,S,k);
  var g=S.tn&&S.tn[p.tm];
  if(!g)return {on:false,t:'No game'};
  var opp=(g[2]?'vs ':'@')+g[1],now=Date.now();
  if(now<g[0]){
    /* a player who is out, or a goalie whose team has another goalie in net, is not going to play: no projection, not counted as playing */
    var gone=p.inj==='OUT'||p.inj==='INJURY_RESERVE'||p.inj==='SUSPENSION',ns=p.grp==='G'&&p.ns;
    var tm=etTime(g[0]).replace(':00','').replace(/\s?PM$/,'p').replace(/\s?AM$/,'a');
    return {on:true,up:true,np:!!(gone||ns),t:opp+' &middot; '+(ns?'<b class="mu-bt">Not starting</b>':tm)};
  }
  if(now<g[0]+3*3600e3)return {on:true,t:opp+' &middot; <b class="mu-live">Live</b>',live:true};
  return {on:true,t:opp+' &middot; Final'};
}
/* a later day: his game that day (from S.ws), and no projection if he is out. Goalie starts are not known yet. */
function muFutSt(p,S,k){
  var g=S.ws&&S.ws[p.tm]&&S.ws[p.tm][k];
  if(!g)return {on:false,t:'No game'};
  var gone=p.inj==='OUT'||p.inj==='INJURY_RESERVE'||p.inj==='SUSPENSION';
  var tm=etTime(g[0]).replace(':00','').replace(/\s?PM$/,'p').replace(/\s?AM$/,'a');
  return {on:true,up:true,np:gone,t:(g[2]?'vs ':'@')+g[1]+' &middot; '+tm};
}
/* a team's lineup on a later day: ESPN's own lineup for that day (S.fa) when it was read, else the current one */
function muFutKnown(T,S,k){return !!(S.fa&&S.fa[String(k)]&&S.fa[String(k)][String(T.id)]);}
function muSl(T,p,S,k){
  if(k==null)return p.slot;
  var d=S.fa&&S.fa[String(k)]&&S.fa[String(k)][String(T.id)];
  return (d&&d[String(p.id)])||p.slot;
}
/* who a team has playing on a later day and what they are projected to score */
function muFutSum(T,S,k){
  var n=0,pj=0;
  T.players.forEach(function(p){
    if(['F','D','G','UTIL'].indexOf(muSl(T,p,S,k))<0)return;
    var st=muFutSt(p,S,k);if(!st.on||st.np)return;
    n++;if(p.out!=null)pj+=p.out;
  });
  return {n:n,pj:pj};
}
function muInj(p){return (p.inj&&p.inj!=='ACTIVE')?' <i class="mu-inj">'+esc(injShort(p.inj))+'</i>':'';}
function muPts(p,st,S,k){
  var v=(k==null&&S.pt)?S.pt[p.id]:undefined;
  if(v!=null&&(st.on&&!st.up||v!==0))return muNum(p.id,v,'t');
  if(st.on&&st.up&&!st.np&&p.out!=null)return '<span class="mu-pj">'+f(p.out,1)+'</span>';
  return '<span class="mu-dash">&ndash;</span>';
}
function muCell(p,S,right,k){
  if(!p)return '<div class="mu-c empty'+(right?' r':'')+'"><span class="mu-dash">Empty</span></div>';
  var st=muStatus(p,S,k);
  return '<div class="mu-c'+(st.on&&!st.np?'':' off')+(right?' r':'')+'"><span class="mu-nm">'+(right?muInj(p):'')+'<a class="pl" data-noav="1" data-id="'+p.id+'">'+esc(shortName(p.n))+'</a>'+(right?'':muInj(p))+'</span>'
    +'<span class="mu-g">'+esc(p.pos)+' '+esc(p.tm)+' &middot; '+st.t+'</span></div>';
}
function muGroup(label,A,B,S,k){
  var n=Math.max(A.length,B.length);if(!n)return '';
  var h='<div class="mu-gh">'+label+'</div>';
  for(var i=0;i<n;i++){
    var a=A[i],b=B[i],sa=a?muStatus(a,S,k):null,sb=b?muStatus(b,S,k):null;
    h+='<div class="mu-lr">'+muCell(a,S,false,k)+'<div class="mu-p">'+(a?muPts(a,sa,S,k):'')+'</div><div class="mu-p">'+(b?muPts(b,sb,S,k):'')+'</div>'+muCell(b,S,true,k)+'</div>';
  }
  return h;
}
function muSlots(t,slot,S,k){
  return t.players.filter(function(p){return muSl(t,p,S,k)===slot;}).sort(function(x,y){
    var sx=muStatus(x,S,k),sy=muStatus(y,S,k),a=sx.on&&!sx.np?1:0,b=sy.on&&!sy.np?1:0;return (b-a)||((y.out||0)-(x.out||0));});
}
function muEtd(ms){try{return new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(ms));}catch(e){return '';}}
/* the day on screen when it is not today (a past day or a later one), or null when it is today */
function muShown(S){var t=Math.min(S.today,S.dates.length-1);return (MU.day!=null&&MU.day>=0&&MU.day<S.dates.length&&MU.day!==t&&!(S.done&&MU.day>t))?MU.day:null;}
var MU_CV='<svg viewBox="0 0 12 8" aria-hidden="true"><path d="M1.5 1.5L6 6l4.5-4.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
var MU_CK='<svg viewBox="0 0 14 11" aria-hidden="true"><path d="M1.5 5.5l3.8 3.8L12.5 1.8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
/* the day picker: every day of the matchup with both teams' points. Later days show each side's projected points in gray
   and open that day's lineups. */
function muDayMenu(g,S,t,i){
  if(!MU.dd)return '';
  var A=muTeam(g.a),B=muTeam(g.b);
  var h='<div class="mu-dd" role="listbox" aria-label="Matchup day"><div class="mu-dh"><span></span><span>'+esc(muInit(A.name))+'</span><span>'+esc(muInit(B.name))+'</span><span></span></div>';
  S.dates.forEach(function(d,k){
    var fut=k>t,a=fut?null:g.ad[k],b=fut?null:g.bd[k],tag=k===t?(S.done?'Last day':'Today'):'';
    function sc(v,o){return '<span class="mu-ds'+(v!=null&&o!=null&&v>o?' w':'')+'">'+(v==null?'&ndash;':f(v,1))+'</span>';}
    function pj(T){return '<span class="mu-ds pj">'+f(muFutSum(T,S,k).pj,1)+'</span>';}
    h+='<button type="button" class="mu-dr'+(k===i?' sel':'')+(fut?' fut':'')+'" data-mud="'+k+'"'+(fut&&S.done?' disabled':'')+' role="option" aria-selected="'+(k===i?'true':'false')+'">'
      +'<span class="mu-dn"><b>'+esc(dayShort(S.labels[k]))+'</b>'+(tag?'<i>'+tag+'</i>':'')+'</span>'+(fut?pj(A)+pj(B):sc(a,b)+sc(b,a))+'<span class="mu-ck">'+(k===i?MU_CK:'')+'</span></button>';
  });
  return h+'</div>';
}
function muTonight(g,S){
  var A=muTeam(g.a),B=muTeam(g.b),t=Math.min(S.today,S.dates.length-1),sh=muShown(S),i=sh==null?t:sh,past=sh!=null&&sh<t,fut=sh!=null&&sh>t,k=fut?i:null;
  function playing(T){return T.players.filter(function(p){var st=muStatus(p,S);return ['F','D','G','UTIL'].indexOf(p.slot)>=0&&st.on&&!st.np;}).length;}
  var pill=sh!=null?esc(dayShort(S.labels[i])):(S.done?'Last day':'Today');
  function side(T,pts,id){
    if(fut){var fs=muFutSum(T,S,k);return '<div><b class="mu-pjb">'+f(fs.pj,1)+'</b><span id="'+id+'">'+fs.n+' playing &middot; proj</span></div>';}
    return '<div><b>'+(pts==null?'0.0':f(pts,1))+'</b><span id="'+id+'">'+(past?'':playing(T)+' playing')+'</span></div>';
  }
  var h='<div class="mu-sumw"><div class="mu-sum">'+side(A,g.ad[i],'muPa')
    +'<button type="button" class="mu-sk mu-pick'+(MU.dd?' open':'')+(sh==null&&!S.done?' now':'')+'" data-mud="tg" aria-haspopup="listbox" aria-expanded="'+(MU.dd?'true':'false')+'" aria-label="Choose a day. Showing '+pill+'">'+pill+'<span class="mu-cv">'+MU_CV+'</span></button>'
    +side(B,g.bd[i],'muPb')+'</div>'+muDayMenu(g,S,t,i)+'</div>';
  if(past){return h+'<div id="muPast"><div class="gl-wait"><span class="spin"></span>Loading</div></div>';}
  h+=muGroup('Forwards',muSlots(A,'F',S,k),muSlots(B,'F',S,k),S,k)+muGroup('Defense',muSlots(A,'D',S,k),muSlots(B,'D',S,k),S,k)
    +muGroup('Utility',muSlots(A,'UTIL',S,k),muSlots(B,'UTIL',S,k),S,k)+muGroup('Goalies',muSlots(A,'G',S,k),muSlots(B,'G',S,k),S,k);
  var bn=muGroup('Bench',muSlots(A,'BN',S,k),muSlots(B,'BN',S,k),S,k);
  if(bn)h+='<details class="mu-bn"><summary>Bench</summary>'+bn.replace('<div class="mu-gh">Bench</div>','')+'</details>';
  if(fut){
    var miss=[A,B].filter(function(T){return !muFutKnown(T,S,k);}).map(function(T){return esc(T.name);});
    h+='<div class="muted mu-note">Each side\'s lineup for '+esc(dayShort(S.labels[i]))+' as set in ESPN right now. Gray numbers are projected points; goalie starts are not known yet, so every goalie with a game is counted.'
      +(miss.length?' ESPN\'s lineup for that day could not be read for '+miss.join(' and ')+', so their current lineup is shown instead.':'')+'</div>';
    return h;
  }
  var live=S.pt&&Object.keys(S.pt).length;
  h+='<div class="muted mu-note">'+(live?'Points are from the last update ('+esc(D.updated)+'). Gray numbers are projections for games that have not started. Tap a score to see how it was made.':'Gray numbers are projected points for tonight. Final points show in the day totals above and on the Week tab.')+'</div>';
  return h;
}
/* a past day: who played and what they scored. With ESPN's lineup for that day (S.dp) it also says who was on the bench, because
   bench points do not count. Without it (older data, or ESPN would not answer) it falls back to the game logs on today's rosters. */
function muPastFill(g,S,i){
  var el=document.getElementById('muPast');if(!el)return;
  var dp=S.dp&&S.dp[String(i)];
  function go(d){
    el=document.getElementById('muPast');if(!el||muShown(S)!==i||MU.tab!=='tn')return;      /* the person moved on while it loaded */
    var A=muTeam(g.a),B=muTeam(g.b),key=S.dates[i],real=!!(dp&&dp[String(g.a)]&&dp[String(g.b)]);
    function row(id){return glRows(id).filter(function(x){return muEtd(x[0])===key;})[0]||null;}
    /* one list of {p,r,pts,bench} per team */
    function played(T){
      if(real){
        return dp[String(T.id)].map(function(e){
          var k=ALL[e[0]],r=row(e[0]);
          var q=k?{id:k.id,n:k.n,pos:k.pos,tm:k.tm,grp:k.grp,inj:k.inj}:{id:e[0],n:e[3],pos:e[4],tm:e[5],grp:e[4]==='G'?'G':e[4]==='D'?'D':'F'};
          var bench=e[1]==='BN'||e[1]==='IR';
          return {p:q,r:r,pts:e[2],bench:bench,ir:e[1]==='IR'};
        }).filter(function(x){return x.pts!==0||x.r;}).sort(function(x,y){return y.pts-x.pts;});
      }
      return T.players.map(function(p){var r=row(p.id);return r?{p:p,r:r,pts:r[3],bench:false}:null;}).filter(Boolean).sort(function(x,y){return y.pts-x.pts;});
    }
    var pa=played(A),pb=played(B);
    function cnt(L){return L.filter(function(x){return !x.bench;}).length;}
    var ea=document.getElementById('muPa'),eb=document.getElementById('muPb');
    if(ea)ea.textContent=cnt(pa)+' played';if(eb)eb.textContent=cnt(pb)+' played';
    function cell(x,right){
      if(!x)return '<div class="mu-c'+(right?' r':'')+'"></div>';
      var p=x.p,tag=(x.bench&&!x.ir)?'Bench':'';
      return '<div class="mu-c'+(x.bench?' off':'')+(right?' r':'')+'"><span class="mu-nm">'+(right?muInj(p):'')+'<a class="pl" data-noav="1" data-id="'+p.id+'">'+esc(shortName(p.n))+'</a>'+(right?'':muInj(p))+'</span>'
        +'<span class="mu-g">'+esc(p.pos)+' '+esc(p.tm)+(x.r?' &middot; '+glOpp(x.r):'')+(tag?' &middot; <b class="mu-bt">'+tag+'</b>':'')+'</span></div>';
    }
    function pts(x){return '<div class="mu-p">'+(x?muNum(x.p.id,x.pts,'d'+i,x.bench?'mu-bpts':x.pts<0?'mu-neg':''):'')+'</div>';}
    function block(label,la,lb,sub){
      var n=Math.max(la.length,lb.length);if(!n)return '';
      var h='<div class="mu-gh">'+label+(sub?' <span class="mu-gs">'+sub+'</span>':'')+'</div>';
      for(var k=0;k<n;k++)h+='<div class="mu-lr">'+cell(la[k],false)+pts(la[k])+pts(lb[k])+cell(lb[k],true)+'</div>';
      return h;
    }
    var h='';
    [['F','Forwards'],['D','Defense'],['G','Goalies']].forEach(function(gr){
      function pick(L){return L.filter(function(x){return !x.bench&&x.p.grp===gr[0];});}
      h+=block(gr[1],pick(pa),pick(pb));
    });
    var ba=pa.filter(function(x){return x.bench;}),bb=pb.filter(function(x){return x.bench;});
    h+=block('Bench',ba,bb,'did not count');
    if(!h)h='<div class="muted mu-note">Nobody on these two rosters had a game on '+esc(dayShort(S.labels[i]))+'.</div>';
    var note=real?'Only players in a lineup spot that day count toward the score. Bench points are shown in gray and left out of the totals.'
      :'ESPN\'s lineup for this day is not available, so this shows each player\'s game log on today\'s rosters. Anyone who sat on a bench that day is not marked, and the points can differ from the day totals above.';
    if(!d&&!real)note='Game logs are not available right now, so player points for this day cannot be shown. The team totals above are still right.';
    el.innerHTML=h+'<div class="muted mu-note">'+note+' Tap a score to see how it was made.</div>';
  }
  if(typeof glLoad==='function'){glLoad().then(go,function(){go(null);});}else go(null);
}
function muWeek(g,S){
  var A=muTeam(g.a),B=muTeam(g.b),ph=pairHues(A,B),mx=1,h='';
  g.ad.concat(g.bd).forEach(function(v){if(v!=null&&v>mx)mx=v;});
  h+='<div class="mu-gh">Points by day</div><div class="mu-bf">';
  S.dates.forEach(function(d,i){
    var a=g.ad[i],b=g.bd[i],fut=a==null&&b==null&&i>S.today,cls=i===S.today&&!S.done?' t':'';
    var lab=String(S.labels[i]||'').split(' ')[0];
    h+='<div class="mu-bfr'+cls+(fut?' fut':'')+'"><div class="mu-bl">'+(a!=null?'<span>'+f(a,1)+'</span><i style="width:'+(a/mx*100)+'%;--h:'+ph[0]+'"></i>':'')+'</div>'
      +'<div class="mu-bd">'+esc(lab)+'</div><div class="mu-br">'+(b!=null?'<i style="width:'+(b/mx*100)+'%;--h:'+ph[1]+'"></i><span>'+f(b,1)+'</span>':'')+'</div></div>';
  });
  h+='</div>';
  h+='<div class="mu-stats"><div><b>'+f(g.ap,1)+'</b><span>Projected</span><b>'+f(g.bp,1)+'</b></div><div><b>'+g.al+'</b><span>Games left</span><b>'+g.bl+'</b></div></div>';
  h+='<div class="mu-gh">Top scorers this week</div><div id="muTop"><div class="gl-wait"><span class="spin"></span>Loading</div></div>';
  return h;
}
function muTopFill(g,S){
  var el=document.getElementById('muTop');if(!el)return;
  function draw(score){
    var A=muTeam(g.a),B=muTeam(g.b);
    function top(T){return T.players.map(function(p){return {p:p,v:score(p)};}).filter(function(x){return x.v!=null&&x.v!==0;}).sort(function(x,y){return y.v-x.v;}).slice(0,5);}
    var ta=top(A),tb=top(B),n=Math.max(ta.length,tb.length),h='';
    if(!n){el.innerHTML='<div class="muted" style="padding:8px 2px">No points scored yet this week.</div>';return;}
    for(var i=0;i<n;i++){var a=ta[i],b=tb[i];
      h+='<div class="mu-lr">'+(a?'<div class="mu-c"><a class="pl" data-noav="1" data-id="'+a.p.id+'">'+esc(shortName(a.p.n))+'</a><span class="mu-g">'+esc(a.p.pos)+' '+esc(a.p.tm)+(a.p.slot==='BN'?' &middot; bench':'')+'</span></div>':'<div class="mu-c"></div>')
        +'<div class="mu-p">'+(a?muNum(a.p.id,a.v,'w'):'')+'</div><div class="mu-p">'+(b?muNum(b.p.id,b.v,'w'):'')+'</div>'
        +(b?'<div class="mu-c r"><a class="pl" data-noav="1" data-id="'+b.p.id+'">'+esc(shortName(b.p.n))+'</a><span class="mu-g">'+esc(b.p.pos)+' '+esc(b.p.tm)+(b.p.slot==='BN'?' &middot; bench':'')+'</span></div>':'<div class="mu-c r"></div>')+'</div>';}
    el.innerHTML=h+'<div class="muted mu-note">Points on the current roster this week, bench games included. Tap a score to see how it was made.</div>';
  }
  if(S.pw&&Object.keys(S.pw).length){draw(function(p){return S.pw[p.id];});return;}
  if(typeof glLoad!=='function'){el.innerHTML='<div class="muted">Not available.</div>';return;}
  var days={};S.dates.forEach(function(d){days[d]=1;});
  function etd(ms){try{return new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(ms));}catch(e){return '';}}
  glLoad().then(function(d){
    if(!d){el.innerHTML='<div class="muted">Game logs are not available right now.</div>';return;}
    draw(function(p){var r=glRows(p.id),s=0,k=0;r.forEach(function(x){if(days[etd(x[0])]){s+=x[3];k++;}});return k?s:null;});
  });
}
function muBody(){
  var S=D.sb,g=S&&S.games[MU.open],b=document.getElementById('muBody');if(!g||!b)return;
  b.innerHTML=MU.tab==='wk'?muWeek(g,S):muTonight(g,S);
  var sg=document.getElementById('muSeg');if(sg){sg.classList.toggle('two',MU.tab==='wk');$$('button',sg).forEach(function(x){x.classList.toggle('on',x.getAttribute('data-mut')===MU.tab);});}
  if(MU.tab==='wk')muTopFill(g,S);
  else if(muShown(S)!=null&&muShown(S)<Math.min(S.today,S.dates.length-1))muPastFill(g,S,muShown(S));
}
/* ---- tap a score: how it was made ----
   Each number the sheet shows for a player (tonight, a past day, the week's top scorers) is a button. Tapping it opens a card
   under that row: every stat that scored, how many, and the points it was worth in this league's scoring (D.scoring, read from
   ESPN's league settings), from the player's game log. Anything the game log does not carry (plus/minus and the like) is added as
   "Other scoring", so the lines always add up to the number that was tapped. */
var BD_SK=[[4,'13','Goals'],[5,'14','Assists'],[6,'29','Shots on goal'],[7,'31','Hits'],[8,'32','Blocked shots'],[10,'38','Power-play points']];
var BD_GK=[[4,'1','Win'],[6,'6','Saves'],[5,'4','Goals against'],[8,'7','Shutout']];
function muNum(id,v,sc,cls){
  return '<button type="button" class="mu-nb" data-bd="'+id+'" data-bs="'+sc+'" data-bv="'+v+'" aria-expanded="false" aria-label="How these '+f(v,1)+' points were scored"><b'+(cls?' class="'+cls+'"':'')+'>'+f(v,1)+'</b></button>';
}
function bdF(x){var r=Math.round(x*100)/100;return Math.abs(r*10-Math.round(r*10))<1e-9?r.toFixed(1):r.toFixed(2);}
function bdKeys(sc,S){
  if(sc==='w')return S.dates;
  if(sc==='t')return [S.dates[Math.min(S.today,S.dates.length-1)]];
  return [S.dates[+sc.slice(1)]];
}
function bdBuild(id,v,sc){
  var S=D.sb,p=ALL[id],keys=bdKeys(sc,S);
  var rows=glRows(id).filter(function(r){return keys.indexOf(muEtd(r[0]))>=0;});
  var hasW=Object.keys(D.scoring||{}).length>0,spec=(p&&p.grp==='G')?BD_GK:BD_SK,lines=[],sum=0;
  spec.forEach(function(s){
    var n=0;rows.forEach(function(r){n+=(+r[s[0]]||0);});
    var w=hasW?lvW(s[1]):0;
    if(n&&(w||!hasW)){var pts=hasW?n*w:null;if(pts!=null)sum+=pts;lines.push({l:s[2],n:(s[2]==='Win'||s[2]==='Shutout')?1:n,pts:pts});}
  });
  if(rows.length&&hasW&&Math.abs(v-sum)>=0.05)lines.push({l:'Other scoring',n:1,pts:v-sum});
  return {p:p,rows:rows,lines:lines,hasW:hasW};
}
function bdHtml(id,v,sc,key){
  var b=bdBuild(id,v,sc),p=b.p,games=b.rows.map(function(r){return (r[2]?'vs ':'@')+r[1];}).join(', ');
  var h='<div class="mu-bk" data-bdk="'+key+'"><div class="mu-bkc"><div class="mu-bkh"><b>'+esc(p?p.n:'Player')+'</b><span>'+(sc==='w'?'This week':'')+(sc==='w'&&games?' &middot; ':'')+esc(games)+'</span></div>';
  if(!b.rows.length){
    var L=(sc==='t'&&typeof LIVE!=='undefined'&&LIVE.pts&&LIVE.pts[id])||null;
    h+='<div class="mu-bkm">'+(L&&L.s?'So far: '+esc(L.s)+'. The full breakdown shows after the next update.':'The stat line for this game is not in yet. It shows after the next update.')+'</div>';
  }else{
    h+=b.lines.map(function(l){
      return '<div class="mu-bkr"><span>'+esc(l.l)+(l.n>1?' <i>&times;'+l.n+'</i>':'')+'</span>'+(l.pts==null?'':'<b class="'+(l.pts<0?'mu-neg':'')+'">'+(l.pts>=0?'+':'&minus;')+bdF(Math.abs(l.pts))+'</b>')+'</div>';
    }).join('');
    if(!b.lines.length)h+='<div class="mu-bkm">No stats that score points.</div>';
    h+='<div class="mu-bkt"><span>Total</span><b>'+bdF(v)+'</b></div>';
  }
  return h+'</div></div>';
}
/* change the page under a row (fn), and slide everything below it into its new place instead of jumping (transforms only) */
function muFlip(anchor,fn){
  var root=anchor.closest('.mu-page')||document.body,fol=[anchor],vh=window.innerHeight||800;
  for(var el=anchor;el&&el!==root;el=el.parentElement)for(var n=el.nextElementSibling;n;n=n.nextElementSibling)fol.push(n);
  var before=fol.map(function(e){return e.getBoundingClientRect().top;});
  fn();
  if(RM)return;
  var moved=[];
  fol.forEach(function(e,i){
    if(!e.isConnected)return;
    var a=e.getBoundingClientRect().top,d=before[i]-a;
    if(Math.abs(d)<1||Math.min(a,before[i])>vh+40)return;
    e.style.transform='translateY('+d.toFixed(1)+'px)';moved.push(e);
  });
  if(!moved.length)return;
  void root.offsetWidth;
  moved.forEach(function(e){e.classList.add('flip');e.style.transform='';});
  setTimeout(function(){moved.forEach(function(e){e.classList.remove('flip');});},470);
}
function muBd(btn){
  var row=btn.closest('.mu-lr,.rd-r');if(!row)return;
  var id=btn.getAttribute('data-bd'),sc=btn.getAttribute('data-bs'),v=+btn.getAttribute('data-bv'),key=id+'|'+sc;
  var nx=row.nextElementSibling,wasOpen=!!(nx&&nx.classList&&nx.classList.contains('mu-bk')&&nx.getAttribute('data-bdk')===key);
  function go(){
    if(!row.isConnected)return;
    muFlip(row,function(){
      var pg=row.closest('.mu-page')||document;
      $$('.mu-bk',pg).forEach(function(e){e.parentNode.removeChild(e);});
      $$('.mu-nb.on',pg).forEach(function(e){e.classList.remove('on');e.setAttribute('aria-expanded','false');});
      if(!wasOpen){row.insertAdjacentHTML('afterend',bdHtml(id,v,sc,key));btn.classList.add('on');btn.setAttribute('aria-expanded','true');}
    });
  }
  if(typeof glLoad==='function')glLoad().then(go,go);else go();
}
/* win-probability bar: two full-width pills clipped by the rounded track; the split between them is laid out once at its
   final place and both pills slide in from 50/50 together (--t, translateX: compositor only, nothing stretches).
   The old version animated width, which re-laid-out the page every frame for a second each time Today opened. */
function wpVars(a){a=Math.max(0,Math.min(100,+a||0));return '--w:'+a+'%;--t:'+(50-a)+'%';}
/* your own matchup's place in the list (-1 when the league scoreboard is missing) */
function muMine(){var S=D.sb,k=-1;if(S&&S.games)S.games.forEach(function(g,i){if(k<0&&muMe(g))k=i;});return k;}
/* one matchup: the scoreboard, the Tonight / Week switch and the two lineups. This is the part that slides. */
function muPageHtml(i){
  var S=D.sb,g=S.games[i],A=muTeam(g.a),B=muTeam(g.b),w=muWin(g);
  function side(t,sc,pr){return '<div class="sb-tm">'+muMono(t)+'<div class="sb-n">'+esc(t.name)+'</div><div class="sb-r">'+esc(t.rec)+' &middot; proj '+f(pr,0)+'</div></div>';}
  var ph=pairHues(A,B),h='<div class="sb mu-sb" style="--h1:'+ph[0]+';--h2:'+ph[1]+'"><div class="sb-row">'+side(A,g.as,g.ap)
    +'<div class="sb-sc"><span class="'+(g.as<g.bs?'dim':'')+'">'+f(g.as,1)+'</span><i class="sb-d"></i><span class="'+(g.bs<g.as?'dim':'')+'">'+f(g.bs,1)+'</span></div>'+side(B,g.bs,g.bp)+'</div>'
    +'<div class="wp"><div class="wp-bar" style="'+wpVars(w.a)+'"><i class="a"></i><i class="b"></i></div><div class="wp-l"><span>'+w.a+'%</span><span>'+(S.done?'Final':'Win chance')+'</span><span>'+w.b+'%</span></div></div></div>';
  h+='<div class="pcseg mu-seg'+(MU.tab==='wk'?' two':'')+'" id="muSeg"><span class="th"></span><button type="button" data-mut="tn"'+(MU.tab==='tn'?' class="on"':'')+'>'+(S.done?'Lineups':'Tonight')+'</button><button type="button" data-mut="wk"'+(MU.tab==='wk'?' class="on"':'')+'>Week</button></div>';
  h+='<div class="mu-hh"><span>'+esc(A.name)+'</span><span>'+esc(B.name)+'</span></div><div id="muBody"></div>';
  return h;
}
/* page dots: one per matchup, yours tinted; tap one to jump */
function muDotsHtml(i){
  var S=D.sb,n=S.games.length;if(n<2)return '';
  return '<div class="mu-trk">'+S.games.map(function(g,k){
    var A=muTeam(g.a),B=muTeam(g.b);
    return '<button type="button" class="mu-pd'+(muMe(g)?' me':'')+'" data-mupg="'+k+'" aria-label="Matchup '+(k+1)+' of '+n+': '+esc(A.name)+' vs '+esc(B.name)+'"><i></i></button>';
  }).join('')+'<span class="mu-pl" id="muPill" aria-hidden="true"><i></i><i></i></span></div>';
}
/* The pill sits at "page progress" p (0 = first matchup, n-1 = last; fractions while a finger is dragging). transform only. */
var MPL={me:null};
function muPill(p,tr){
  var el=document.getElementById('muPill'),n=D.sb?D.sb.games.length:0;if(!el||n<2)return;
  p=Math.max(-0.3,Math.min(n-0.7,p));                       /* a little give past the first and last, like the page itself */
  el.style.transition=tr||'none';
  el.style.transform='translate3d('+(p*20).toFixed(1)+'px,0,0)';
  var g=D.sb.games[Math.max(0,Math.min(n-1,Math.round(p)))],me=!!(g&&muMe(g));
  if(me!==MPL.me){MPL.me=me;el.classList.toggle('me',me);}
}
/* Dots are built once per sheet. Later pages only move the pill and the labels. */
function muDotsSync(i){
  var dt=document.getElementById('muDots'),n=D.sb?D.sb.games.length:0;if(!dt)return;
  if(dt.getAttribute('data-n')!==String(n)||!document.getElementById('muPill')){dt.innerHTML=muDotsHtml(i);dt.setAttribute('data-n',n);MPL.me=null;}
  var b=dt.querySelectorAll('.mu-pd');
  for(var k=0;k<b.length;k++){if(k===i)b[k].setAttribute('aria-current','true');else b[k].removeAttribute('aria-current');}
  muPill(i);
}
function muPaint(i){
  var pg=document.getElementById('muPage');if(!pg)return;
  MU.open=i;MU.dd=false;
  pg.innerHTML=muPageHtml(i);
  muDotsSync(i);
  muBody();
}
function muOpen(i){
  var S=D.sb,g=S&&S.games[i];if(!g)return;
  if(SH.open&&document.getElementById('muPage')){muGo(i);return;}          /* already on a matchup: page over to it */
  MU.open=i;MU.day=null;MU.dd=false;MU.tab='tn';
  var h='<div class="mhead"><div class="pc-id"><b>Week '+esc(S.mp)+'</b><span class="muted">'+muDayTxt(S)+' &middot; updated '+esc(D.updated)+'</span></div><button class="x" id="mx">&times;</button></div>';
  h+='<div class="mu-pgs" id="muDots" role="group" aria-label="Matchups"></div><div class="mu-pw"><div class="mu-page" id="muPage"></div></div>';
  var bx=sheetShow(h);
  muPaint(i);
  if(bx)muSwipe(bx);
}

/* ---- swipe left / right between matchups ----
   The header and the page dots stay put; the matchup underneath follows your finger like a page in iOS. Past the first
   or last matchup it only stretches. A flick or a drag past about a quarter of the screen turns the page. */
var MSW={on:false,ax:0,x0:0,y0:0,dx:0,t:[],busy:false,g:null,gd:0};
function muRub(d,W){var a=Math.abs(d),r=(1-1/(a*0.55/W+1))*W*0.5;return d<0?-r:r;}
function muScrollsX(el,stop){
  for(;el&&el!==stop;el=el.parentElement){var ox=getComputedStyle(el).overflowX;if((ox==='auto'||ox==='scroll')&&el.scrollWidth>el.clientWidth+1)return true;}
  return false;
}
function muW(){var pg=document.getElementById('muPage'),bx=pg&&pg.closest('.box');return (bx&&bx.clientWidth)||window.innerWidth;}
/* the neighbouring matchup, drawn beside the current one so it slides in with your finger (ids renamed: display only) */
function muGhost(j){
  var pg=document.getElementById('muPage'),S=D.sb;if(!pg||!S||!S.games[j])return null;
  muGhostOff();
  var g=S.games[j],el=document.createElement('div');el.className='mu-page mu-ghost';el.setAttribute('aria-hidden','true');
  el.innerHTML=(muPageHtml(j).replace('<div id="muBody"></div>','<div>'+(MU.tab==='wk'?muWeek(g,S):muTonight(g,S))+'</div>')).replace(/ id="/g,' data-gid="');
  pg.parentNode.appendChild(el);MSW.g=el;MSW.gj=j;
  return el;
}
function muGhostOff(){if(MSW.g&&MSW.g.parentNode)MSW.g.parentNode.removeChild(MSW.g);MSW.g=null;MSW.gj=null;}
function muPlace(dx,d,tr){
  var pg=document.getElementById('muPage'),W=muW();if(!pg)return;
  muPill(MU.open-dx/W,tr);                                  /* the dots follow the page, frame for frame */
  pg.style.transform='translate3d('+dx.toFixed(1)+'px,0,0)';
  if(MSW.g)MSW.g.style.transform='translate3d('+(dx+d*W).toFixed(1)+'px,0,0)';
}
/* turn to matchup j: the current page leaves, j arrives (a drag in progress continues from where the finger let go) */
function muGo(j,from){
  var S=D.sb,pg=document.getElementById('muPage');
  if(!S||!S.games[j]||!pg||MSW.busy)return;
  var i=MU.open,bx=pg.closest('.box');
  if(j===i){muBack();return;}
  var d=j>i?1:-1,W=muW();
  if(RM){muGhostOff();muPaint(j);return;}
  MSW.busy=true;
  if(!MSW.g||MSW.gj!==j){muGhost(j);from=0;muPlace(0,d);void pg.offsetWidth;}
  var g=MSW.g,left=W-Math.abs(from||0),dur=Math.round(Math.max(220,Math.min(420,left/W*420)));
  var tr='transform '+dur+'ms cubic-bezier(.25,.9,.3,1)';
  pg.style.transition=tr;g.style.transition=tr;
  muPlace(-d*W,d,tr);
  setTimeout(function(){
    pg.style.transition='none';pg.style.transform='';
    muPaint(j);muGhostOff();
    MSW.busy=false;
    if(bx){var pgs=document.getElementById('muDots'),top=pgs?pgs.offsetTop-80:0;
      if(bx.scrollTop>Math.max(0,top)){try{bx.scrollTo({top:Math.max(0,top),behavior:'smooth'});}catch(x){bx.scrollTop=Math.max(0,top);}}}
  },dur);
}
function muBack(){
  var pg=document.getElementById('muPage');if(!pg)return;
  var g=MSW.g,d=MSW.gd||1,tr='transform .45s var(--spring)';
  pg.style.transition=tr;if(g)g.style.transition=tr;
  muPlace(0,d,tr);
  setTimeout(function(){if(!MSW.on&&!MSW.busy)muGhostOff();pg.style.transition='';},460);
}
function muSwipe(bx){
  if(bx._msw)return;bx._msw=1;
  function page(){return document.getElementById('muPage');}
  bx.addEventListener('touchstart',function(e){
    MSW.on=false;MSW.ax=0;
    if(e.touches.length!==1||MSW.busy||!page()||bx._vdrag)return;
    var t=e.target;
    if(t.closest&&t.closest('.mu-dd,input,select,textarea'))return;
    if(muScrollsX(t,bx))return;
    MSW.on=true;MSW.x0=e.touches[0].clientX;MSW.y0=e.touches[0].clientY;MSW.dx=0;MSW.t=[[MSW.x0,performance.now()]];
  },{passive:true});
  bx.addEventListener('touchmove',function(e){
    if(!MSW.on||e.touches.length!==1)return;
    var x=e.touches[0].clientX,dx=x-MSW.x0,dy=e.touches[0].clientY-MSW.y0;
    if(!MSW.ax){
      if(Math.abs(dx)<8&&Math.abs(dy)<8)return;
      if(bx._vdrag||Math.abs(dx)<=Math.abs(dy)*1.2){MSW.on=false;return;}         /* scrolling or pulling the sheet down */
      MSW.ax=1;bx._swx=true;MSW.x0=x-(dx>0?8:-8);dx=x-MSW.x0;
      if(MU.dd){MU.dd=false;muBody();}
    }
    if(e.cancelable)e.preventDefault();
    MSW.dx=dx;MSW.t.push([x,performance.now()]);if(MSW.t.length>5)MSW.t.shift();
    var pg=page();if(!pg)return;
    var n=D.sb.games.length,i=MU.open,W=muW(),d=dx<0?1:-1,j=i+d;
    pg.style.transition='none';
    if(j<0||j>=n){muGhostOff();muPlace(muRub(dx,W),d);return;}                   /* first or last: just stretch */
    if(!MSW.g||MSW.gj!==j)muGhost(j);
    MSW.gd=d;MSW.g.style.transition='none';
    muPlace(dx,d);
  },{passive:false});
  function end(){
    if(!MSW.on)return;MSW.on=false;
    if(!MSW.ax)return;
    bx._swx=false;MSW.ax=0;
    if(!page())return;
    var a=MSW.t[0],b=MSW.t[MSW.t.length-1],v=(a&&b&&b[1]>a[1])?(b[0]-a[0])/(b[1]-a[1]):0;
    var dx=MSW.dx,W=muW(),n=D.sb.games.length,i=MU.open,j=i+(dx<0?1:-1);
    var go=Math.abs(dx)>W*0.25||(Math.abs(v)>0.3&&Math.abs(dx)>20&&(v>0)===(dx>0));
    if(go&&j>=0&&j<n)muGo(j,dx);else muBack();
  }
  bx.addEventListener('touchend',end);bx.addEventListener('touchcancel',end);
}
document.addEventListener('keydown',function(e){
  if(!SH.open||!document.getElementById('muPage'))return;
  var a=document.activeElement;if(a&&/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName))return;
  var S=D.sb,j=MU.open+(e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0);
  if(j!==MU.open&&S&&S.games[j]){e.preventDefault();muGo(j);}
});
/* the Today scoreboard is a role=button section: Enter or Space opens it too */
document.addEventListener('keydown',function(e){
  var t=e.target;if((e.key==='Enter'||e.key===' ')&&t&&t.matches&&t.matches('.sb.tap[data-mu]')){e.preventDefault();muOpen(+t.getAttribute('data-mu'));}
});
document.addEventListener('click',function(e){
  var t=e.target;if(!t||!t.closest)return;
  var nb=t.closest('.mu-nb');if(nb){muBd(nb);return;}
  var pd=t.closest('[data-mupg]');if(pd){muGo(+pd.getAttribute('data-mupg'));return;}
  if(t.closest('[data-gback]')){gmBack();return;}
  var gb=t.closest('[data-gbd]');if(gb){var gi=gb.getAttribute('data-gbd');GM.bd=GM.bd===gi?null:gi;gmPaint();return;}
  var gp=t.closest('[data-gp]');if(gp){gmPlayer(gp.getAttribute('data-gp'));return;}
  var gm=t.closest('[data-gm]');if(gm){gmOpen(gm.getAttribute('data-gm'));return;}
  var a=t.closest('[data-mu]');if(a){muOpen(+a.getAttribute('data-mu'));return;}
  var b=t.closest('[data-mut]');if(b){MU.tab=b.getAttribute('data-mut');MU.dd=false;muBody();return;}
  var d=t.closest('[data-mud]');
  if(d){
    var S=D.sb,v=d.getAttribute('data-mud');
    if(v==='tg')MU.dd=!MU.dd;
    else if(S&&!d.disabled){var k=+v;MU.day=(k===Math.min(S.today,S.dates.length-1))?null:k;MU.dd=false;}
    muBody();return;
  }
  if(MU.dd&&document.getElementById('muBody')&&!t.closest('.mu-dd')){MU.dd=false;muBody();}      /* a tap anywhere else closes the picker */
});

/* ---------- Auto-update: the open app reloads itself when new data or new app code is live ---------- */
/* The published app has window.FH_CODE (see site_builder.LOADER). It asks version.json every 15 s while open and whenever it
   comes back to the screen.
   - New data never reloads the page you are reading. It is put in right after you open the app (within 2 minutes, once you
     have not touched the screen for 4 s) or while the app is in the background. Otherwise it waits for that.
   - New app code goes in at the next quiet moment (no sheet open, not typing, no touch for 5 s), or in the background.
   Before reloading it fetches what the new page needs (data.json, or the new app files), so the reload itself is instant,
   and it keeps your tab, scroll and open sections. */
var UPD={t:0,busy:false,want:null,tm:null,vis:Date.now(),going:false};
function updQuiet(){
  if(document.hidden)return true;
  var m=document.getElementById('modal');if(m&&m.classList.contains('open'))return false;
  var a=document.activeElement;if(a&&/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName))return false;
  var idle=Date.now()-UPD.t;
  if(UPD.want&&UPD.want.k==='data')return Date.now()-UPD.vis<120000&&idle>4000;
  return idle>5000;
}
function updPrep(){                                           /* fetch what the new page needs, so the reload shows it at once */
  var w=UPD.want,keep=function(txt){if(txt){try{sessionStorage.setItem('fh_pre',txt);}catch(e){}}};
  if(w.k==='data')return fetch('data.json?t='+Date.now(),{cache:'no-store'}).then(function(r){return r.ok?r.text():null;}).then(keep).catch(function(){});
  var el=document.getElementById('data');if(el&&el.textContent)keep(el.textContent);
  var c=w.v.slice(1);
  return Promise.all(['js','css'].map(function(x){return fetch('app.'+c+'.'+x).catch(function(){});})).catch(function(){});
}
function updApply(){
  if(!UPD.want||UPD.going)return;
  clearTimeout(UPD.tm);
  if(!updQuiet()){UPD.tm=setTimeout(updApply,3000);return;}
  UPD.going=true;
  var done=false,go=function(){
    if(done)return;done=true;
    if(!updQuiet()){UPD.going=false;try{sessionStorage.removeItem('fh_pre');}catch(e){}UPD.tm=setTimeout(updApply,3000);return;}   /* you touched it meanwhile */
    try{sessionStorage.setItem('fh_upd',JSON.stringify({k:UPD.want.k,v:UPD.want.v,y:window.pageYOffset||0}));}catch(e){}
    location.reload();
  };
  updPrep().then(go,go);setTimeout(go,6000);
}
function updCheck(){
  if(UPD.busy||UPD.want||!window.FH_CODE)return;            /* the one-file test page has nothing to check */
  UPD.busy=true;
  fetch('version.json?t='+Date.now(),{cache:'no-store'}).then(function(r){return r.ok?r.json():null;}).then(function(v){
    UPD.busy=false;if(!v)return;
    var tried=null;try{tried=sessionStorage.getItem('fh_tried');}catch(e){}
    var w=null;
    if(v.code&&v.code!==window.FH_CODE)w={k:'code',v:'c'+v.code};
    else if(v.data&&D.v&&v.data>D.v)w={k:'data',v:'d'+v.data};
    if(!w||w.v===tried)return;                                /* never loop on the same update */
    UPD.want=w;updApply();
  }).catch(function(){UPD.busy=false;});
}
/* the Refresh and Keep buttons: their update was asked for, so put it in now (still keeping tab and scroll) */
window.FHUpdateNow=function(){UPD.vis=Date.now();UPD.t=0;try{sessionStorage.removeItem('fh_tried');}catch(e){}UPD.want=null;UPD.busy=false;updCheck();};
function updStart(){
  ['pointerdown','touchstart','keydown','scroll'].forEach(function(ev){document.addEventListener(ev,function(){UPD.t=Date.now();},{passive:true,capture:true});});
  document.addEventListener('visibilitychange',function(){if(!document.hidden){UPD.vis=Date.now();updCheck();}else if(UPD.want)updApply();});
  setInterval(function(){if(!document.hidden)updCheck();},15000);
  setTimeout(updCheck,3000);
  var s=null;try{s=JSON.parse(sessionStorage.getItem('fh_upd')||'null');sessionStorage.removeItem('fh_upd');if(s)sessionStorage.setItem('fh_tried',s.v);}catch(e){}
  if(s){if(s.y){window.scrollTo(0,s.y);requestAnimationFrame(function(){if(Math.abs((window.pageYOffset||0)-s.y)>2)window.scrollTo(0,s.y);});}kpToast(s.k==='code'?'The app was just updated.':'Updated with the latest data.');}
}

/* ---------- Live repaint without rebuilding (2026-11-25) ----------
   Live scores, points and the game page used to be redrawn with innerHTML every refresh: every tile, logo and bar was thrown
   away and rebuilt (a flash, a tap in progress lost, bars replaying their entrance, scroll positions reset). uiMorph(el, html)
   patches the page in place instead: text and attributes that changed are changed, keyed children (data-k) keep their
   element and slide to a new place when the order changes (data-flip), new pieces fade in, and pictures (headshots, logos)
   are never touched unless the picture itself changed. A split bar whose value moved slides from where it was. */
function moAtom(n){return n.nodeType===1&&(n.tagName==='PICTURE'||n.classList.contains('av'));}
function moKey(n){var i=n.querySelector('img');return i?(i.getAttribute('src')||''):'';}
function moBar(o,st){
  var a=/--w:\s*([\d.]+)%/.exec(o.getAttribute('style')||''),b=/--w:\s*([\d.]+)%/.exec(st||'');
  if(!a||!b||RM)return;var d=+b[1]-+a[1];if(Math.abs(d)<.3||!o.animate)return;
  [].forEach.call(o.children,function(i){i.animate([{transform:'translate3d('+(-d)+'%,0,0)'},{transform:'translate3d(0,0,0)'}],{duration:700,easing:'cubic-bezier(.32,.72,0,1)'});});
}
function moAttrs(o,n){
  var i,a;
  for(i=o.attributes.length-1;i>=0;i--){a=o.attributes[i];if(!n.hasAttribute(a.name))o.removeAttribute(a.name);}
  for(i=0;i<n.attributes.length;i++){
    a=n.attributes[i];
    if(o.getAttribute(a.name)!==a.value){if(a.name==='style'&&o.classList.contains('wp-bar'))moBar(o,a.value);o.setAttribute(a.name,a.value);}
  }
}
function moNode(o,n){
  if(o.nodeType!==1){if(o.nodeValue!==n.nodeValue)o.nodeValue=n.nodeValue;return;}
  moAttrs(o,n);
  if(moAtom(o)){var k=moKey(n);if(o._ak==null)o._ak=moKey(o);if(k!==o._ak){o._ak=k;o.innerHTML=n.innerHTML;}return;}
  moKids(o,n);
}
function moMark(x){if(x.nodeType!==1)return;if(moAtom(x))x._ak=moKey(x);[].forEach.call(x.querySelectorAll('picture,.av'),function(a){a._ak=moKey(a);});}
function moKids(o,n){
  var ou=[],map={},c,k,had=o.firstChild!=null,flip=o.hasAttribute&&o.hasAttribute('data-flip'),r0={};
  for(c=o.firstChild;c;c=c.nextSibling){k=c.nodeType===1?c.getAttribute('data-k'):null;if(k)map[k]=c;else ou.push(c);}
  if(flip)for(k in map)r0[k]=map[k].getBoundingClientRect().top;
  var ui=0,prev=null,made=[];
  [].slice.call(n.childNodes).forEach(function(x){
    var key=x.nodeType===1?x.getAttribute('data-k'):null,m=null;
    if(key){m=map[key]||null;delete map[key];}
    else{var c2=ou[ui];if(c2&&c2.nodeType===x.nodeType&&(x.nodeType!==1||c2.tagName===x.tagName)){m=c2;ui++;}}
    if(m)moNode(m,x);else{m=x;made.push(x);}
    var want=prev?prev.nextSibling:o.firstChild;
    if(m!==want)o.insertBefore(m,want);
    prev=m;
  });
  for(k in map)o.removeChild(map[k]);
  for(;ui<ou.length;ui++)o.removeChild(ou[ui]);
  made.forEach(function(x){moMark(x);if(had&&x.nodeType===1&&!RM)x.classList.add('mo-in');});
  if(flip&&!RM&&o.animate)for(k in r0){
    var e=o.querySelector(':scope>[data-k="'+k+'"]');if(!e)continue;
    var d=r0[k]-e.getBoundingClientRect().top;
    if(Math.abs(d)>1)e.animate([{transform:'translate3d(0,'+d+'px,0)'},{transform:'translate3d(0,0,0)'}],{duration:480,easing:'cubic-bezier(.32,.72,0,1)'});
  }
}
function uiMorph(el,html){
  if(!el)return;
  if(el._h===html)return;el._h=html;
  var t=document.createElement('template');t.innerHTML=html;
  moKids(el,t.content);
}

/* ---------- Live: tonight's games and roughly how many points your starters have scored so far ----------
   From ESPN's public scoreboard (the NHL's own feed blocks browser apps). It refreshes every 45 s while a game you
   care about is on and the app is open. Points use your league's scoring for goals, assists, shots, hits, blocks,
   saves, goals against, wins and shutouts; power-play and short-handed points show up after the next full update. */
var LIVE={ev:[],pts:{},done:{},at:0,tm:null,err:0};
var LV_URL='https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/';
var LV_AL={LA:'LAK',NJ:'NJD',SJ:'SJS',TB:'TBL',UTAH:'UTA',WAS:'WSH',MON:'MTL',CLB:'CBJ',CLS:'CBJ',NAS:'NSH',NSH:'NSH',VEG:'VGK',WIN:'WPG'};
var LV_SK={goals:'13',assists:'14',shotsTotal:'29',hits:'31',blockedShots:'32'};
var LV_LB={goals:'Goals',assists:'Assists',shotsTotal:'Shots on goal',hits:'Hits',blockedShots:'Blocked shots'};
function lvAb(a){a=String(a||'').toUpperCase();return LV_AL[a]||a;}
function lvDay(ms){try{return new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(ms)).replace(/-/g,'');}catch(e){return '';}}
function lvStarters(list){return (list||[]).filter(function(p){return p.slot!=='BN'&&p.slot!=='IR';});}
function lvOpp(){var M=D.matchup;if(!M)return [];var t=(D.teams||[]).filter(function(x){return x.id===M.opp_id;})[0];return t?t.players:[];}
function lvW(id){var S=D.scoring||{};return +S[id]||0;}
function lvMineIn(e){var a=[e.h.ab,e.a.ab];return (D.mine||[]).filter(function(p){return a.indexOf(lvAb(p.tm))>=0;});}
function lvBox(e,sm){
  var bp=(sm&&sm.boxscore&&sm.boxscore.players)||[];
  bp.forEach(function(t){
    var ab=lvAb(t.team&&t.team.abbreviation),won=(ab===e.h.ab?e.h.w:(ab===e.a.ab?e.a.w:false))&&e.st==='post',gks=[];
    (t.statistics||[]).forEach(function(g){
      var k=g.keys||[];
      (g.athletes||[]).forEach(function(a){
        var id=+(a.athlete&&a.athlete.id),st=a.stats||[];if(!id)return;
        var val=function(n){var i=k.indexOf(n);return i<0?0:(parseFloat(st[i])||0);};
        if(g.name==='goalies'){
          var ga=val('goalsAgainst'),sv=k.indexOf('saves')>=0?val('saves'):Math.max(0,val('shotsAgainst')-ga);
          var o={id:id,ga:ga,sv:sv,f:sv+ga};gks.push(o);
          var gl=[];if(sv&&lvW('6'))gl.push({l:'Saves',n:sv,pts:sv*lvW('6')});if(ga&&lvW('4'))gl.push({l:'Goals against',n:ga,pts:ga*lvW('4')});
          LIVE.pts[id]={p:sv*lvW('6')+ga*lvW('4'),s:sv+' saves, '+ga+' GA',g:e.id,ln:gl};
        }else{
          var p=0,bits=[],ln=[];
          for(var n in LV_SK){var x=val(n),w=lvW(LV_SK[n]);p+=x*w;if(x&&w)ln.push({l:LV_LB[n],n:x,pts:x*w});if(x&&(n==='goals'||n==='assists'))bits.push(x+(n==='goals'?'G':'A'));}
          var sog=val('shotsTotal');if(sog)bits.push(sog+' SOG');
          LIVE.pts[id]={p:p,s:bits.join(' ')||'no points yet',g:e.id,ln:ln};
        }
      });
    });
    if(won&&gks.length){                     /* the win goes to the goalie who faced the most shots */
      gks.sort(function(a,b){return b.f-a.f;});var w=gks[0],L=LIVE.pts[w.id];
      if(L){L.p+=lvW('1')+(w.ga===0?lvW('7'):0);L.s+=w.ga===0?', win, shutout':', win';
        if(lvW('1'))L.ln.push({l:'Win',n:1,pts:lvW('1')});if(w.ga===0&&lvW('7'))L.ln.push({l:'Shutout',n:1,pts:lvW('7')});}
    }
  });
}
function lvSum(list){var s=0,n=0;lvStarters(list).forEach(function(p){var L=LIVE.pts[p.id];if(L){s+=L.p;n++;}});return {s:s,n:n};}
/* ---------- Tonight (Today tab): one tile per game that matters to your matchup, Apple Sports style (2026-11-25) ----------
   A sideways row of game tiles so Today stays short: both teams' logos, puck drop / live score / final, your players in
   that game with their gray projection (or live points), and the opponent's starters in the same game. The header sums
   tonight for both sides. Tapping a tile opens the matchup sheet (both full lineups). Projections and "not playing" use
   the matchup sheet's own rules (muStatus, p.out) so the two screens always agree. */
function lvMe(){var t=(D.teams||[]).filter(function(x){return x.me;})[0];return t?t.players:(D.mine||[]);}
function lvIn(list,e){var a=[e.h.ab,e.a.ab];return (list||[]).filter(function(p){return a.indexOf(lvAb(p.tm))>=0;});}
function lvSt(p){var S=D.sb;if(!S||!S.tn)return {on:true,np:false};try{return muStatus(p,S);}catch(x){return {on:true,np:false};}}
function lvOut(p){return p.inj==='OUT'||p.inj==='INJURY_RESERVE'||p.inj==='SUSPENSION'||(p.grp==='G'&&p.ns);}
function lvPlays(p){return p.slot!=='BN'&&p.slot!=='IR'&&!lvOut(p);}
function lvLogo(t){
  if(!t.lg)return '<span class="tn-lg nl"></span>';
  var lp=String(t.lg).replace(/^https?:\/\/a\.espncdn\.com/,''),rs=function(x){return ESPN_RS+x+'&w=72&h=72&scale=crop';};
  if(lp===t.lg)return '<img class="tn-lg" src="'+esc(t.lg)+'" alt="" decoding="async" onerror="this.style.visibility=\'hidden\'">';
  var dk=lp.replace('/500/','/500-dark/');
  return '<picture class="tn-lgw">'+(dk!==lp?'<source media="(prefers-color-scheme: dark)" srcset="'+rs(dk)+'">':'')
    +'<img class="tn-lg" src="'+rs(lp)+'" data-full="'+esc(t.lg)+'" alt="" decoding="async" onerror="lgErr(this)"></picture>';
}
window.lgErr=function(i){           /* dark logo missing -> light one -> the original file -> nothing (the abbreviation stays) */
  var s=i.parentNode&&i.parentNode.querySelector('source');
  if(s){s.parentNode.removeChild(s);i.src=i.src;return;}
  var f=i.getAttribute('data-full');if(f){i.removeAttribute('data-full');i.src=f;return;}
  i.style.visibility='hidden';
};
function lvLast(n){var w=String(n||'').trim().split(/\s+/);return w.length>1?w.slice(1).join(' '):n;}
function lvPts(p,e){
  var L=LIVE.pts[p.id];
  if(e.st!=='pre')return L?'<span class="tn-pv'+(L.p>0?' up':'')+'">'+(L.p>0?'+':'')+L.p.toFixed(1)+'</span>':'<span class="tn-pv z">0.0</span>';
  if(lvOut(p))return '<span class="tn-pv z">&ndash;</span>';
  return p.out!=null?'<span class="tn-pv pj">'+f(p.out,1)+'</span>':'';
}
function lvTile(e,mi){
  var mine=lvIn(lvMe(),e),theirs=lvStarters(lvIn(lvOpp(),e)),pre=e.st==='pre',fin=e.st==='post';
  var mt={};mine.forEach(function(p){mt[lvAb(p.tm)]=1;});
  mine.sort(function(a,b){return (lvPlays(b)-lvPlays(a))||((b.out||0)-(a.out||0));});
  var st=pre?etTime(e.start):(fin?'Final'+(/OT|SO/.test(e.det)?(/SO/.test(e.det)?'/SO':'/OT'):''):'<span class="sb-live"></span>'+esc(String(e.det||'Live').replace(/\s*-\s*/,' · ')));
  function tm(t,o){
    var win=fin&&t.sc>o.sc;
    return '<span class="tn-tm'+(mt[t.ab]?' my':'')+(fin&&!win?' lo':'')+'">'+lvLogo(t)+'<span class="tn-ab">'+esc(t.ab)+'</span>'+(pre?'':'<span class="tn-sc">'+t.sc+'</span>')+'</span>';
  }
  var show=mine.slice(0,3),more=mine.length-show.length;
  var ps=show.map(function(p){
    var bn=p.slot==='BN'||p.slot==='IR',off=bn||lvOut(p);
    return '<span class="tn-p'+(off?' off':'')+'"><span class="tn-av">'+avHtml(p.id,p.tm)+'</span><span class="tn-pn">'+esc(lvLast(p.n))+(bn?'<i>BN</i>':(p.grp==='G'&&p.ns?'<i>Not starting</i>':''))+'</span>'+(bn?'':lvPts(p,e))+'</span>';
  }).join('');
  if(more>0)ps+='<span class="tn-more">+'+more+' more</span>';
  if(!mine.length)ps='<span class="tn-none">None of yours</span>';
  var op='';
  if(theirs.length){
    var os=0;theirs.forEach(function(p){var L=LIVE.pts[p.id];if(L)os+=L.p;});
    op='<span class="tn-op"><b>'+(pre?'Them':'Them '+(os>0?'+':'')+os.toFixed(1))+'</b>'+esc(theirs.map(function(p){return lvLast(p.n);}).join(', '))+'</span>';
  }
  var cls='tn-g'+(e.st==='in'?' live':'')+(fin?' fin':'');
  var lbl=e.a.ab+' at '+e.h.ab+', '+(pre?etTime(e.start):(e.a.sc+' to '+e.h.sc))+'. Yours: '+mine.map(function(p){return lvLast(p.n);}).join(', ');
  return '<button type="button" class="'+cls+'" data-k="t'+esc(e.id)+'" data-gm="'+esc(e.id)+'" aria-label="'+esc(lbl)+'"><span class="tn-st">'+st+'</span>'+tm(e.a,e.h)+tm(e.h,e.a)
    +'<span class="tn-ps">'+ps+'</span>'+op+'</button>';
}
function lvHtml(){
  var me=lvMe(),them=lvStarters(lvOpp());
  var evs=LIVE.ev.filter(function(e){return lvIn(me,e).length||lvIn(them,e).length;});
  if(!evs.some(function(e){return lvIn(me,e).length;}))return '';
  var on=evs.some(function(e){return e.st==='in';}),any=evs.some(function(e){return e.st!=='pre';}),M=D.matchup;
  var mi=(typeof muMine==='function'&&D.sb)?muMine():-1;
  var o={in:0,pre:1,post:2};
  evs.sort(function(a,b){return (o[a.st]-o[b.st])||(a.start-b.start)||(lvIn(me,b).length-lvIn(me,a).length);});
  /* the head-to-head for tonight: points so far once a game is on, projected points before */
  var r='';
  if(any){var a=lvSum(me),b=lvSum(them);r='You <b>+'+a.s.toFixed(1)+'</b>'+(M?' &middot; Them <b>+'+b.s.toFixed(1)+'</b>':'');}
  else{
    var pj=function(L){var s=0;L.forEach(function(p){if(!lvPlays(p))return;if(!evs.some(function(e){return lvIn([p],e).length;}))return;var st=lvSt(p);if(st.np)return;s+=p.out||0;});return s;};
    r='Proj <b>'+f(pj(lvStarters(me)),1)+'</b>'+(M?' &ndash; <b>'+f(pj(them),1)+'</b>':'');
  }
  var h='<div class="sec tn" data-k="tn"><div class="sec-h"><span>Tonight</span><span class="sec-r tn-r">'+(on?'<span class="sb-live"></span>':'')+r+'</span></div>';
  h+='<div class="tn-car'+(evs.length<=2?' few':'')+'" id="tnCar">'+evs.map(function(e){return lvTile(e,mi);}).join('')+'</div>';
  var n=lvStarters(me).filter(function(p){return lvPlays(p)&&evs.some(function(e){return lvIn([p],e).length;});}).length;
  h+='<div class="sec-f">'+(any?'Live points are a close estimate.':n+' of yours play tonight. Tap a game for the full picture.')+'</div>';
  return h+'</div>';
}
function lvPaint(){
  var el=document.getElementById('livebox');if(!el)return;
  uiMorph(el,lvHtml());                                   /* patched in place: no flash, scroll and taps survive */
  try{rdLive();}catch(e){}
  try{gmPaint();}catch(e){}
}
/* ---------- Game page (2026-11-25): tap a Tonight tile ----------
   One NHL game through your matchup's eyes. Top to bottom: the game (logos in team colors, score or puck drop, period line
   score), what the game is worth to you (your players' projected or live points against your opponent's in the same game),
   the outlook before puck drop (who is in net from Daily Faceoff, the betting line's win chance and total), both sides'
   players in this game with role and live stat line, every goal with the fantasy points it gave each side, and the team
   stats as mirrored bars. ESPN's game summary is read when the page opens and every 30 s while the game is live; anything
   it does not have is simply left out. */
var GM={id:null,sm:null,tm:null,bd:null};
function gmEv(){for(var i=0;i<LIVE.ev.length;i++)if(LIVE.ev[i].id===GM.id)return LIVE.ev[i];return null;}
function gmHex(c){return /^[0-9a-f]{6}$/i.test(c||'')?c:'';}
function gmLum(c){var n=parseInt(c,16),r=(n>>16)/255,g=(n>>8&255)/255,b=(n&255)/255;return .2126*r+.7152*g+.0722*b;}
function gmColor(t,fb){var c=gmHex(t.c),c2=gmHex(t.c2);if(c&&gmLum(c)<.07&&c2&&gmLum(c2)>gmLum(c))c=c2;return c?'#'+c:fb;}
/* bar colors: each team's own color when it reads on both light and dark backgrounds, and never two that look alike */
function gmRgb(c){var n=parseInt(c,16);return [n>>16,n>>8&255,n&255];}
function gmDist(x,y){var a=gmRgb(x),b=gmRgb(y);return Math.sqrt(Math.pow(a[0]-b[0],2)+Math.pow(a[1]-b[1],2)+Math.pow(a[2]-b[2],2));}
function gmPair(e){
  var ok=function(t){return [t.c,t.c2].filter(function(c){c=gmHex(c);if(!c)return false;var l=gmLum(c);return l>=.05&&l<=.72;});};
  var A=ok(e.a),H=ok(e.h),ca=A[0]||'8e8e93',ch=H.filter(function(c){return gmDist(c,ca)>120;})[0];
  if(!ch){var a2=A.filter(function(c){return H.some(function(h){return gmDist(c,h)>120;});})[0];if(a2){ca=a2;ch=H.filter(function(c){return gmDist(c,ca)>120;})[0];}}
  if(!ch)ch=gmDist('8e8e93',ca)>120?'8e8e93':'c7c7cc';
  return ['#'+ca,'#'+ch];
}
function gmOpen(id,back){
  if(!back){GM.sm=null;GM.sy=0;GM.bd=null;}
  GM.id=String(id);clearTimeout(GM.tm);
  var e=gmEv();if(!e)return;
  var bx=sheetShow('<div class="mhead gm-mh"><div class="pc-id"><b>'+esc(e.a.ab+' at '+e.h.ab)+'</b><span class="muted" id="gmSub">'+esc(gmSub(e))+'</span></div><button class="x" id="mx">&times;</button></div><div id="gmBody">'+gmHtml(e)+'</div>');
  if(back&&bx)bx.scrollTop=GM.sy||0;
  gmLoad();
}
/* a player tapped on the game page slides in from the right over it, with a Back that slides it away again (like a push in iOS) */
function gmPlayer(id){
  var p=ALL[id],e=gmEv(),bx=document.querySelector('#modal .box');if(!p||!e||!bx)return;
  GM.sy=bx.scrollTop;clearTimeout(GM.tm);SH.dir='r';
  modal(p);
  var b=document.querySelector('#modal .box'),g=b&&b.querySelector('.grab');
  if(g)g.insertAdjacentHTML('afterend','<div class="gm-bk"><button type="button" class="gm-back" data-gback aria-label="Back to the game">'+SF.chev+'<span>'+esc(e.a.ab+' at '+e.h.ab)+'</span></button></div>');
}
function gmBack(){if(!gmEv()){closeModal();return;}SH.dir='l';gmOpen(GM.id,true);}
function gmSub(e){
  var gi=GM.sm&&GM.sm.gameInfo,v=gi&&gi.venue&&gi.venue.fullName;
  return (e.st==='pre'?'Tonight':(e.st==='in'?'Live':'Final'))+(v?' · '+v:'');
}
function gmLoad(){
  var id=GM.id;if(!document.getElementById('gmBody'))return;
  fetch(LV_URL+'summary?event='+encodeURIComponent(id)).then(lvJ).then(function(sm){
    if(GM.id!==id||!document.getElementById('gmBody'))return;
    GM.sm=sm;var e=gmEv();if(!e)return;
    gmMerge(e,sm);
    if(e.st!=='pre')lvBox(e,sm);
    lvPaint();
  }).catch(function(){}).then(function(){
    var e=gmEv();clearTimeout(GM.tm);
    if(GM.id===id&&document.getElementById('gmBody')&&e&&(e.st==='in'||(e.st==='pre'&&e.start-Date.now()<15*60000)))GM.tm=setTimeout(gmLoad,30000);
  });
}
/* the summary is newer than the scoreboard: take its status, scores and period line */
function gmMerge(e,sm){
  var c=sm.header&&sm.header.competitions&&sm.header.competitions[0];if(!c)return;
  var t=(c.status&&c.status.type)||{};if(t.state){e.st=t.state;e.det=t.shortDetail||e.det;}
  (c.competitors||[]).forEach(function(x){
    var s=x.homeAway==='home'?e.h:(x.homeAway==='away'?e.a:null);if(!s)return;
    if(x.score!=null&&x.score!=='')s.sc=+x.score||0;
    if(x.linescores&&x.linescores.length)s.ls=x.linescores.map(function(l){return l.displayValue!=null?l.displayValue:l.value;});
    if(!s.rec&&x.record&&x.record[0])s.rec=x.record[0].summary||x.record[0].displayValue||'';
  });
}
function gmPaint(){
  var b=document.getElementById('gmBody'),e=gmEv();if(!b||!e)return;
  uiMorph(b,gmHtml(e));var sb=document.getElementById('gmSub');if(sb)sb.textContent=gmSub(e);
}
function gmMine(e){return lvIn(lvMe(),e);}
function gmTheirs(e){return lvStarters(lvIn(lvOpp(),e));}
function gmCounts(p){return lvPlays(p)&&!lvSt(p).np;}
function gmPts(p,e){var L=LIVE.pts[p.id];return e.st==='pre'?(gmCounts(p)?(p.out||0):0):(L&&p.slot!=='BN'&&p.slot!=='IR'?L.p:0);}
function gmHero(e){
  var pre=e.st==='pre',fin=e.st==='post',ca=gmColor(e.a,'#3a3a3c'),ch=gmColor(e.h,'#3a3a3c');
  function side(t,o){
    var lo=fin&&t.sc<o.sc;
    return '<div class="gm-tm'+(lo?' lo':'')+'">'+lvLogo(t).replace(/tn-lg/g,'gm-lg')+'<b>'+esc(t.ab)+'</b><span>'+esc(t.rec||t.nm||'')+'</span></div>';
  }
  var mid;
  if(pre){
    var m=Math.round((e.start-Date.now())/60000);
    mid='<div class="gm-mid"><div class="gm-time">'+esc(etTime(e.start))+'</div><div class="gm-det">'+(m>0&&m<=120?'Puck drop in '+m+' min':(m<=0?'Starting':'Today'))+'</div></div>';
  }else{
    mid='<div class="gm-mid"><div class="gm-sc"><span class="'+(fin&&e.a.sc<e.h.sc?'dim':'')+'">'+e.a.sc+'</span><i></i><span class="'+(fin&&e.h.sc<e.a.sc?'dim':'')+'">'+e.h.sc+'</span></div>'
      +'<div class="gm-det'+(fin?'':' live')+'">'+(fin?'':'<span class="sb-live"></span>')+esc(fin?String(e.det||'Final'):String(e.det||'Live').replace(/\s*-\s*/,' · '))+'</div></div>';
  }
  var h='<section class="gm-hero" data-k="hero" style="--ca:'+ca+';--ch:'+ch+'"><div class="gm-row">'+side(e.a,e.h)+mid+side(e.h,e.a)+'</div>';
  var n=Math.max(e.a.ls?e.a.ls.length:0,e.h.ls?e.h.ls.length:0);
  if(!pre&&n){
    var hd='',ra='',rh='';
    for(var i=0;i<n;i++){hd+='<span>'+(i<3?i+1:(i===3?'OT':'SO'))+'</span>';ra+='<span>'+esc((e.a.ls||[])[i]==null?'':e.a.ls[i])+'</span>';rh+='<span>'+esc((e.h.ls||[])[i]==null?'':e.h.ls[i])+'</span>';}
    h+='<div class="gm-ls" style="--n:'+n+'"><div><span></span>'+hd+'<span>T</span></div><div><span>'+esc(e.a.ab)+'</span>'+ra+'<b>'+e.a.sc+'</b></div><div><span>'+esc(e.h.ab)+'</span>'+rh+'<b>'+e.h.sc+'</b></div></div>';
  }
  return h+'</section>';
}
/* what this game is worth: your side against your opponent's, projected before puck drop and points so far after */
function gmStake(e){
  var M=D.matchup,me=gmMine(e),th=gmTheirs(e),pre=e.st==='pre';
  var a=0,b=0,na=0,nb=0;
  me.forEach(function(p){if(p.slot==='BN'||p.slot==='IR')return;if(pre&&!gmCounts(p))return;na++;a+=gmPts(p,e);});
  th.forEach(function(p){if(pre&&!gmCounts(p))return;nb++;b+=gmPts(p,e);});
  var net=a-b,op=(M&&M.opp_name)||'Them',ph=pairHues(todayTeam(true),todayTeam(false,M)),h1=ph[0],h2=ph[1];
  var tot=a+b,w=tot>0?Math.round(a/tot*100):(na||nb?Math.round(na/(na+nb)*100):50);
  var big=Math.abs(net)<0.05?'Even':(net>0?'+':'−')+f(Math.abs(net),1);
  var lbl=pre?(Math.abs(net)<0.05?'An even game for your matchup':(net>0?'Projected edge for you in this game':'Projected edge for '+op+' in this game'))
    :(e.st==='post'?(Math.abs(net)<0.05?'Even in this game':(net>0?'You won this game':op+' won this game'))
      :(Math.abs(net)<0.05?'Even so far':(net>0?'You’re ahead in this game':op+' is ahead in this game')));
  return '<div class="sec gm-stake" data-k="stake"><div class="grp gm-sk" style="--h1:'+h1+';--h2:'+h2+'">'
    +'<div class="gm-skt"><b class="'+(net>0.05?'up':(net<-0.05?'dn':''))+'">'+big+'</b><span>'+esc(lbl)+'</span></div>'
    +'<div class="wp-bar gm-bar" style="'+wpVars(Math.max(4,Math.min(96,w)))+'"><i class="a"></i><i class="b"></i></div>'
    +'<div class="gm-skl"><span>You <b>'+(pre?f(a,1):(a>=0?'+':'')+f(a,1))+'</b></span><span>'+esc(op)+' <b>'+(pre?f(b,1):(b>=0?'+':'')+f(b,1))+'</b></span></div>'
    +'</div><div class="sec-f">'+(pre?'Projected fantasy points from the players each of you starts in this game.':(e.st==='post'?'Fantasy points from this game (close estimate until the next full update).':'Fantasy points from this game so far (close estimate).'))+'</div></div>';
}
/* before puck drop: who is in net (Daily Faceoff) and what the betting line expects */
function gmOutlook(e){
  if(e.st!=='pre')return '';
  var rows='',df=D.df||{},by={};Object.keys(df).forEach(function(k){by[lvAb(k)]=df[k];});
  var mineIds={},theirIds={};lvMe().forEach(function(p){mineIds[ALL[p.id]?p.id:p.id]=1;});lvOpp().forEach(function(p){theirIds[p.id]=1;});
  [e.a,e.h].forEach(function(t){
    var g=by[t.ab];if(!g)return;
    var nm=psNorm(g.name),p=null;Object.keys(ALL).some(function(id){var q=ALL[id];if(q&&q.grp==='G'&&psNorm(q.n)===nm){p=q;return true;}return false;});
    var conf=/confirm/i.test(g.status),tag=p&&mineIds[p.id]?'<i class="gm-tag me">Yours</i>':(p&&theirIds[p.id]?'<i class="gm-tag th">Theirs</i>':'');
    rows+='<div class="row" data-k="n'+t.ab+'"'+(p?' data-gp="'+p.id+'" role="button" tabindex="0"':'')+'>'+(p?glAv(p):'<span class="rav">'+lvLogo(t).replace(/tn-lg/g,'gm-sl')+'</span>')+'<div class="row-m"><div class="row-t">'+esc(g.name)+'</div><div class="row-s">'+esc(t.ab)+' in net'+tag+'</div></div>'
      +'<span class="badge '+(conf?'b-start':'b-optional')+'">'+(conf?'Confirmed':esc(/likely|expected/i.test(g.status)?'Likely':'Expected'))+'</span></div>';
  });
  var pc=GM.sm&&GM.sm.pickcenter&&GM.sm.pickcenter[0],odds='';
  if(pc){
    var ml=function(o){var v=o&&(o.moneyLine!=null?o.moneyLine:(o.current&&o.current.moneyLine&&o.current.moneyLine.american));v=parseFloat(v);return isNaN(v)?null:v;};
    var pr=function(v){return v<0?-v/(-v+100):100/(v+100);},am=ml(pc.awayTeamOdds),hm=ml(pc.homeTeamOdds);
    if(am!=null&&hm!=null){
      var pa=pr(am),ph=pr(hm),fa=pa/(pa+ph),fav=fa>=.5?e.a:e.h,fp=Math.round(Math.max(fa,1-fa)*100);
      var dog=fav===e.a?e.h:e.a,close=fp<=55;   // within 45-55% a game is a coin flip: never call one side "favored" (2026-11-27)
      odds+='<div class="row" data-k="fav"><span class="ric gy">'+SF.chart+'</span><div class="row-m"><div class="row-t">'+(close?'Toss-up: '+esc(fav.ab)+' '+fp+'%, '+esc(dog.ab)+' '+(100-fp)+'%':esc(fav.ab)+' favored, '+fp+'% to win')+'</div><div class="row-s">'+(close?'From the betting line. Either goalie could get the win.':'From the betting line. Winning goalies score more.')+'</div></div></div>';
    }
    if(pc.overUnder){var ou=+pc.overUnder;odds+='<div class="row" data-k="ou"><span class="ric gy">'+SF.goals+'</span><div class="row-m"><div class="row-t">'+f(ou,1)+' goals expected</div><div class="row-s">'+(ou>=6.5?'A high-scoring line: good for skaters.':(ou<=5.5?'A low-scoring line: good for goalies.':'About an average night.'))+'</div></div></div>';}
  }
  if(!rows&&!odds)return '';
  return '<div class="sec" data-k="out"><div class="sec-h"><span>Before puck drop</span></div><div class="grp">'+rows+odds+'</div></div>';
}
/* true = Daily Faceoff has him in net tonight, false = someone else, null = not known */
function gmStarter(p,e){var df=D.df||{},ab=lvAb(p.tm),g=null;Object.keys(df).forEach(function(k){if(lvAb(k)===ab)g=df[k];});
  if(!g||!g.name)return null;return psNorm(g.name)===psNorm(p.n);}
function gmPRow(p,e){
  var pre=e.st==='pre',bn=p.slot==='BN'||p.slot==='IR',st=lvSt(p),L=LIVE.pts[p.id],off=bn||st.np||lvOut(p);
  var bits=[esc(p.pos)];
  var gs=p.grp==='G'?gmStarter(p,e):null,sbn=bn&&gs===true&&pre;
  if(bn)bits.push(sbn?'<b class="gm-warn">Starts tonight, benched</b>':'Bench');
  if(p.grp==='G'&&!sbn){if(p.ns||gs===false)bits.push('Not starting');else if(gs===true)bits.push('Starting');}
  if(p.inj&&p.inj!=='ACTIVE')bits.push(esc(injShort(p.inj)));
  if((pre||!L)&&p.grp!=='G'){var r=rlTxt(p.rl);if(r)bits.push(esc(r));}
  var sub=bits.join(' &middot; ')+(pre&&!sbn?' '+rdForm(p):'');
  if(!pre&&L)sub=bits.join(' &middot; ')+' &middot; <span class="gm-line">'+esc(L.s)+'</span>';
  var v,card='';
  if(bn)v='<span class="gm-v z">&ndash;</span>';
  else if(pre)v=off?'<span class="gm-v z">&ndash;</span>':'<span class="gm-v pj">'+f(p.out||0,1)+'</span>';
  else{
    var open=GM.bd===String(p.id);
    v='<button type="button" class="gm-nb'+(open?' on':'')+'" data-gbd="'+p.id+'" aria-expanded="'+open+'" aria-label="How these points were scored"><span class="gm-v'+(L&&L.p>0?' up':(L&&L.p<0?' dn':''))+'">'+(L?(L.p>0?'+':'')+f(L.p,1):'0.0')+'</span></button>';
    card=open?gmBd(p,L,e):'';
  }
  return '<div class="row gm-pr'+(off?' off':'')+'" data-k="p'+p.id+'" data-gp="'+p.id+'" role="button" tabindex="0">'+glAv(p)+'<div class="row-m"><div class="row-t">'+esc(p.n)+'</div><div class="row-s">'+sub+'</div></div>'+v+'</div>'+card;
}
/* tap a score: how it was made. The card opens under the row (the same card the matchup sheet uses), built from the stat line
   the live game already gave us, so its lines always add up to the number that was tapped. It stays open while the game
   updates and its numbers change with it. */
function gmBd(p,L,e){
  var ln=(L&&L.ln)||[],fin=e.st==='post',h='<div class="mu-bk" data-k="b'+p.id+'"><div class="mu-bkc"><div class="mu-bkh"><b>'+esc(p.n)+'</b><span>'+esc(e.a.ab+' at '+e.h.ab)+' &middot; '+(fin?'Final':'Live')+'</span></div>';
  h+=ln.map(function(l){return '<div class="mu-bkr"><span>'+esc(l.l)+(l.n>1?' <i>&times;'+l.n+'</i>':'')+'</span><b class="'+(l.pts<0?'mu-neg':'')+'">'+(l.pts>=0?'+':'&minus;')+bdF(Math.abs(l.pts))+'</b></div>';}).join('');
  if(!ln.length)h+='<div class="mu-bkm">No stats that score points yet.</div>';
  h+='<div class="mu-bkt"><span>Total</span><b>'+bdF(L?L.p:0)+'</b></div>';
  if(lvW('38')||lvW('15'))h+='<div class="mu-bkm">'+(fin?'Power-play points and similar extras':'Power-play points and similar extras')+' are added at the next full update.</div>';
  return h+'</div></div>';
}
function gmPlayers(e){
  var M=D.matchup,me=gmMine(e),th=lvIn(lvOpp(),e),pre=e.st==='pre',h='';
  var ord=function(L){return L.slice().sort(function(a,b){var x=(a.slot==='BN'||a.slot==='IR')-(b.slot==='BN'||b.slot==='IR');return x||(gmPts(b,e)-gmPts(a,e))||((b.out||0)-(a.out||0));});};
  function sec(title,L,key){
    if(!L.length)return '';
    return '<div class="sec" data-k="pl-'+key+'"><div class="sec-h"><span>'+esc(title)+'</span><span class="sec-r">'+L.length+' in this game</span></div><div class="grp" data-flip>'+ord(L).map(function(p){return gmPRow(p,e);}).join('')+'</div></div>';
  }
  h+=sec('Your players',me,'me');
  h+=sec(M?(M.opp_name||'Opponent'):'Opponent',th,'th');
  return h;
}
/* every goal, newest first, with the fantasy points it gave each side */
function gmGoals(e){
  if(e.st==='pre'||!GM.sm)return '';
  var pl=(GM.sm.plays||[]).filter(function(p){return p.scoringPlay;});
  if(!pl.length)return '';
  var tm={};((GM.sm.header&&GM.sm.header.competitions&&GM.sm.header.competitions[0].competitors)||[]).forEach(function(c){if(c.team)tm[String(c.team.id)]=c.homeAway==='home'?e.h:e.a;});
  var mine={},them={};lvStarters(lvMe()).forEach(function(p){mine[p.id]=1;});lvStarters(lvOpp()).forEach(function(p){them[p.id]=1;});
  var wg=lvW('13'),wa=lvW('14');
  var rows=pl.slice().reverse().map(function(p){
    var t=tm[String(p.team&&p.team.id)]||null,pa=(p.participants||[]).map(function(x){return +(x.athlete&&x.athlete.id);}).filter(Boolean);
    var me=0,th=0;pa.forEach(function(id,i){var w=i===0?wg:wa;if(mine[id])me+=w;if(them[id])th+=w;});
    var per=p.period&&p.period.number,pt=(per?(per<=3?'P'+per:(per===4?'OT':'SO')):'')+(p.clock&&p.clock.displayValue?' '+p.clock.displayValue:'');
    var chips=(me?'<i class="gm-tag me">+'+f(me,1)+' you</i>':'')+(th?'<i class="gm-tag th">+'+f(th,1)+' them</i>':'');
    return '<div class="row gm-gl" data-k="g'+(per||0)+'-'+esc(p.clock&&p.clock.displayValue)+'-'+(pa[0]||0)+'">'+(t?'<span class="rav gm-glg">'+lvLogo(t).replace(/tn-lg/g,'gm-sl')+'</span>':'<span class="ric gy">'+SF.clock+'</span>')
      +'<div class="row-m"><div class="row-t gm-glt">'+esc(String(p.text||'Goal').replace(/\s*\(\d+\)/,'').split(/,? assist/i)[0])+'</div>'
      +'<div class="row-s">'+esc(pt)+(/assist/i.test(p.text||'')?' &middot; '+esc(String(p.text).replace(/^.*?assists?:?\s*/i,'').replace(/\s*\(\d+\)/g,'').replace(/^Assists?:\s*/i,'')):' &middot; Unassisted')+'</div></div>'+(chips?'<span class="gm-gch">'+chips+'</span>':'')+'</div>';
  }).join('');
  return '<div class="sec" data-k="goals"><div class="sec-h"><span>Goals</span></div><div class="grp">'+rows+'</div></div>';
}
/* team stats as mirrored bars, whichever of these ESPN gives */
var GM_ST=[['Shots',/^(shots|shots on goal|sog)$/i,/^(shotsTotal|shotsOnGoal|shots)$/],['Power play',/^(power ?play goals|ppg)$/i,/^powerPlayGoals$/],['Hits',/^hits$/i,/^hits$/],['Blocks',/^blocked shots|^blocks$/i,/^blockedShots$/],['Faceoffs',/faceoff.*%|^fo%$/i,/^faceoffPercent$/],['Takeaways',/^takeaways$/i,/^takeaways$/]];
function gmStats(e){
  if(e.st==='pre'||!GM.sm||!GM.sm.boxscore)return '';
  var T=GM.sm.boxscore.teams||[];if(T.length<2)return '';
  var side=function(x){var ab=lvAb(x.team&&x.team.abbreviation);return ab===e.h.ab?'h':(ab===e.a.ab?'a':(x.homeAway==='home'?'h':'a'));};
  var by={};T.forEach(function(x){by[side(x)]=x.statistics||[];});if(!by.a||!by.h)return '';
  function get(L,s){for(var i=0;i<L.length;i++){var q=L[i];if(s[2].test(q.name||'')||s[1].test(q.label||'')||s[1].test(q.displayName||''))return q.displayValue!=null?q.displayValue:q.value;}return null;}
  var cp=gmPair(e),ca=cp[0],ch=cp[1],rows='';
  GM_ST.forEach(function(s){
    var va=get(by.a,s),vh=get(by.h,s);if(va==null||vh==null)return;
    var na=parseFloat(va)||0,nh=parseFloat(vh)||0,t=na+nh,pa=t>0?na/t:.5;
    rows+='<div class="gm-st" data-k="s'+s[0]+'"><div class="gm-stl"><b class="'+(na>nh?'w':'')+'">'+esc(va)+'</b><span>'+s[0]+'</span><b class="'+(nh>na?'w':'')+'">'+esc(vh)+'</b></div>'
      +'<div class="wp-bar gm-stb" style="'+wpVars(Math.max(3,Math.min(97,pa*100)))+';--c1:'+ca+';--c2:'+ch+'"><i class="a"></i><i class="b"></i></div></div>';
  });
  if(!rows)return '';
  return '<div class="sec" data-k="stats"><div class="sec-h"><span>Team stats</span></div><div class="grp gm-sts"><div class="gm-sth"><span>'+lvLogo(e.a).replace(/tn-lg/g,'gm-sl')+esc(e.a.ab)+'</span><span>'+esc(e.h.ab)+lvLogo(e.h).replace(/tn-lg/g,'gm-sl')+'</span></div>'+rows+'</div></div>';
}
function gmHtml(e){
  return gmHero(e)+gmStake(e)+gmOutlook(e)+gmPlayers(e)+gmGoals(e)+gmStats(e)
    +'<div class="muted gm-ft" data-k="ft">'+(e.st==='pre'?'Gray numbers are projected fantasy points.':'Live fantasy points are a close estimate; power-play points come with the next full update.')+'</div>';
}
function lvLater(ms){clearTimeout(LIVE.tm);LIVE.tm=setTimeout(lvFetch,ms);}
function lvNext(){
  var mine=LIVE.ev.filter(function(e){return lvMineIn(e).length;}),now=Date.now();
  if(mine.some(function(e){return e.st==='in';}))return lvLater(45000);
  var pre=mine.filter(function(e){return e.st==='pre';}).map(function(e){return e.start;});
  if(pre.length){var s=Math.min.apply(null,pre);return lvLater(s-now<20*60000?90000:Math.min(15*60000,s-now-10*60000));}
  lvLater(15*60000);                                            /* nothing on: look again later (a new day's slate) */
}
function lvJ(r){if(!r.ok)throw new Error(r.status);return r.json();}
function lvFetch(){
  if(document.hidden){LIVE.wait=true;return;}
  LIVE.wait=false;
  fetch(LV_URL+'scoreboard?dates='+lvDay(Date.now()-5*3600000)).then(lvJ).then(function(s){
    LIVE.ev=(s.events||[]).map(function(e){
      var c=(e.competitions||[])[0]||{},cs=c.competitors||[];
      var side=function(w){var x=cs.filter(function(q){return q.homeAway===w;})[0]||{},T=x.team||{};return {ab:lvAb(T.abbreviation),sc:+x.score||0,w:!!x.winner,lg:T.logo||'',nm:T.shortDisplayName||T.name||'',c:T.color||'',c2:T.alternateColor||'',ls:(x.linescores||[]).map(function(l){return l.displayValue!=null?l.displayValue:l.value;}),rec:((x.records||[])[0]||{}).summary||''};};
      var t=(e.status&&e.status.type)||{};
      return {id:e.id,st:t.state||'pre',det:t.shortDetail||'',start:Date.parse(e.date),h:side('home'),a:side('away')};
    });
    var rel={};(D.mine||[]).concat(lvStarters(lvOpp())).forEach(function(p){rel[lvAb(p.tm)]=1;});
    var need=LIVE.ev.filter(function(e){return e.st!=='pre'&&!LIVE.done[e.id]&&(rel[e.h.ab]||rel[e.a.ab]);});
    return Promise.all(need.map(function(e){
      return fetch(LV_URL+'summary?event='+e.id).then(lvJ).then(function(sm){lvBox(e,sm);if(e.st==='post')LIVE.done[e.id]=1;}).catch(function(){});
    }));
  }).then(function(){LIVE.at=Date.now();LIVE.err=0;lvPaint();lvNext();})
    .catch(function(){LIVE.err++;lvLater(Math.min(10,LIVE.err)*60000);});
}
function lvStart(){
  if(!D.matchup&&!(D.mine||[]).length)return;
  document.addEventListener('visibilitychange',function(){if(!document.hidden&&(LIVE.wait||Date.now()-LIVE.at>40000)){clearTimeout(LIVE.tm);lvFetch();}});
  lvFetch();
}

/* =====================================================================================================
   SEARCH: every player in the league, whatever his status (your team, another team, free agent, waivers, injured).
   It lives at the top of the Players tab; the round search button in the tab bar opens it with the keyboard up.
   The page already has every rostered player and the top free agents. pool.json (built with the data) adds the rest
   of ESPN's list and is only loaded once you search. Recent picks are remembered on this phone.
   ===================================================================================================== */
var PS={q:'',scope:'all',more:false,ix:null,pool:null,pp:null,n:0};
var PS_SC=[['all','All'],['fa','Free agents'],['team','On a team'],['inj','Injured']];
function psNorm(x){return wiNorm(x).replace(/[^a-z0-9 ]/g,' ').replace(/\s+/g,' ').trim();}
function psOwn(){var o={};(D.teams||[]).forEach(function(t){t.players.forEach(function(p){o[p.id]=t;});});return o;}
/* who has him: {k: 'me' | 'team' | 'fa' | 'wv', t: label, team} */
function psStat(p,own){
  var t=own[p.id];
  if(t)return t.me?{k:'me',t:'Your team'+(p.slot==='BN'?' · Bench':(p.slot==='IR'?' · IR':''))}:{k:'team',t:t.name,team:t};
  return p.st==='WAIVERS'?{k:'wv',t:'Waivers'}:{k:'fa',t:'Free agent'};
}
function psIndex(){
  if(PS.ix)return PS.ix;
  var seen={},L=[],own=psOwn();
  function add(p){
    if(!p||seen[p.id])return;seen[p.id]=1;
    var nm=psNorm(p.n),w=nm.split(' ');
    L.push({p:p,nm:nm,w:w,last:w.slice(1).join(' '),tm:String(p.tm||'').toLowerCase(),s:psStat(p,own)});
  }
  (D.teams||[]).forEach(function(t){t.players.forEach(add);});
  (D.mine||[]).forEach(add);(D.fas||[]).forEach(add);
  (PS.pool||[]).forEach(add);
  PS.n=L.length;PS.ix=L;return L;
}
function psLoad(){
  if(PS.pp)return PS.pp;
  if(!D.pool||!D.pool.n||typeof fetch!=='function'||location.protocol==='file:'){PS.pp=Promise.resolve(null);return PS.pp;}   /* file: = the one-file test copy */
  PS.pp=fetch('pool.json?v='+D.pool.v).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;}).then(function(j){
    if(j&&j.p&&j.p.length){
      PS.pool=j.p;j.p.forEach(function(p){if(!ALL[p.id])ALL[p.id]=p;});
      PS.ix=null;psCount();var w=document.getElementById('psw');if(PS.q||(w&&w.classList.contains('on')))psRender();
    }
    return j;
  });
  return PS.pp;
}
function psInScope(e,sc){
  if(sc==='fa')return e.s.k==='fa'||e.s.k==='wv';
  if(sc==='team')return e.s.k==='me'||e.s.k==='team';
  if(sc==='inj')return isInj(e.p)||(e.p.inj&&e.p.inj!=='ACTIVE');
  return true;
}
/* how well a player matches: whole name > last name > a word > anywhere; an NHL team's code lists his team */
function psScore(e,q,toks){
  if(e.nm===q)return 100;
  if(e.nm.indexOf(q)===0)return 90;
  if(e.last&&e.last.indexOf(q)===0)return 85;
  if(toks.every(function(t){return e.w.some(function(w){return w.indexOf(t)===0;});}))return 75;
  if(q.length>=3&&e.nm.replace(/ /g,'').indexOf(q.replace(/ /g,''))>=0)return 50;
  if(toks.length===1&&q.length>=2&&q.length<=3&&e.tm===q)return 40;
  return 0;
}
function psFind(q){
  var toks=q.split(' ').filter(Boolean),out=[];
  psIndex().forEach(function(e){var s=psScore(e,q,toks);if(s)out.push({e:e,s:s});});
  out.sort(function(a,b){return (b.s-a.s)||((b.e.p.own||0)-(a.e.p.own||0))||((b.e.p.out||0)-(a.e.p.out||0));});   /* best-known first: per-start and per-game numbers do not compare */
  return out.map(function(x){return x.e;});
}
function psMark(name,q){
  var toks=q.split(' ').filter(Boolean),w=String(name).split(' ');
  return w.map(function(x){var n=psNorm(x),hit=toks.filter(function(t){return n.indexOf(t)===0;})[0];
    if(!hit||x.length<hit.length)return esc(x);
    return '<b>'+esc(x.slice(0,hit.length))+'</b>'+esc(x.slice(hit.length));}).join(' ');
}
function psRow(e,q){
  var p=e.p,s=e.s,inj=(p.inj&&p.inj!=='ACTIVE')?'<i class="ps-tg inj">'+esc(injShort(p.inj))+'</i>':'';
  var blk=(s.k==='team'&&s.team&&s.team.block&&s.team.block.indexOf(p.id)>=0)?'<i class="ps-tg blk">On the block</i>':'';
  var g=p.gl!=null?p.gl+' game'+(p.gl===1?'':'s')+' left':'';
  return '<button type="button" class="ps-r" data-psid="'+p.id+'">'+avHtml(p.id,p.tm)
    +'<span class="ps-m"><span class="ps-n">'+(q?psMark(p.n,q):esc(p.n))+'</span>'
    +'<span class="ps-s"><span class="ps-st ps-k'+s.k+'">'+esc(s.t)+'</span>'+inj+blk+'</span>'
    +'<span class="ps-d">'+esc(p.pos)+' &middot; '+esc(p.tm)+(g?' &middot; '+g:'')+'</span></span>'
    +'<span class="ps-v"><b>'+f(p.out,1)+'</b><span>'+(p.grp==='G'?'per start':'per game')+'</span></span></button>';
}
var PS_RK='fh_recent_search';
function psRecent(){try{return (JSON.parse(localStorage.getItem(PS_RK)||'[]')||[]).filter(function(id){return ALL[id];});}catch(e){return [];}}
function psRemember(id){try{var r=psRecent().filter(function(x){return String(x)!==String(id);});r.unshift(+id);localStorage.setItem(PS_RK,JSON.stringify(r.slice(0,8)));}catch(e){}}
function psCount(){psIndex();var i=document.getElementById('psQ');if(i&&PS.pool)i.placeholder='Search all '+PS.n.toLocaleString('en-US')+' players';}
function psHint(){psIndex();return PS.pool?'Search all '+PS.n.toLocaleString('en-US')+' players: every team, free agents and waivers':'Search every player in the league';}
function psRender(){
  var box=document.getElementById('psRes'),host=document.getElementById('s-players-main'),w=document.getElementById('psw');if(!box||!host)return;
  var q=psNorm(PS.q),focused=w&&w.classList.contains('on');
  host.classList.toggle('ps-busy',!!q||focused);
  var sc=document.getElementById('psSc');
  if(!q){
    if(sc)sc.hidden=true;
    var rc=psRecent(),own=psOwn(),h='';
    if(focused&&rc.length){
      h='<div class="ps-hd"><span>Recent</span><button type="button" class="ps-clr" data-psclr="1">Clear</button></div><div class="ps-list">'
        +rc.map(function(id){var p=ALL[id];return psRow({p:p,s:psStat(p,own)},'');}).join('')+'</div>';
    }else if(focused)h='<div class="ps-empty">'+esc(psHint())+'.<br>Try a last name, or an NHL team like <b>EDM</b>.</div>';
    box.innerHTML=h;return;
  }
  var all=psFind(q),cnt={};
  PS_SC.forEach(function(x){cnt[x[0]]=all.filter(function(e){return psInScope(e,x[0]);}).length;});
  if(sc){sc.hidden=false;sc.innerHTML=PS_SC.map(function(x){return '<button type="button" class="ps-c'+(PS.scope===x[0]?' on':'')+'" data-pssc="'+x[0]+'">'+x[1]+(cnt[x[0]]?' <i>'+cnt[x[0]]+'</i>':'')+'</button>';}).join('');}
  var rows=all.filter(function(e){return psInScope(e,PS.scope);}),lim=PS.more?200:40;
  var h2='';
  if(!rows.length)h2='<div class="ps-empty">No '+(PS.scope==='all'?'':PS_SC.filter(function(x){return x[0]===PS.scope;})[0][1].toLowerCase()+' ')+'players match &ldquo;'+esc(PS.q.trim())+'&rdquo;.'
    +(PS.scope!=='all'&&cnt.all?'<br><button type="button" class="ps-more" data-pssc="all">Show all '+cnt.all+' matches</button>':'')+'</div>';
  else{
    h2='<div class="ps-list">'+rows.slice(0,lim).map(function(e){return psRow(e,q);}).join('')+'</div>';
    if(rows.length>lim)h2+='<button type="button" class="ps-more" data-psmore="1">Show '+(Math.min(rows.length,200)-lim)+' more</button>';
  }
  if(PS.pp&&!PS.pool&&D.pool&&D.pool.n)h2+='<div class="ps-foot"><span class="spin"></span>Adding the rest of the free agents</div>';
  box.innerHTML=h2;
}
function psSet(q){PS.q=q;PS.more=false;var x=document.getElementById('psX');if(x)x.hidden=!q;psRender();}
function psFocus(){var i=document.getElementById('psQ');if(i){i.focus();psLoad();}}
function psInit(){
  var host=document.getElementById('s-players-main');if(!host||document.getElementById('psw'))return;
  var el=document.createElement('div');el.id='psbox';
  el.innerHTML='<div class="ps-w" id="psw"><label class="ps-f">'+SF.players
    +'<input id="psQ" type="search" placeholder="Search every player" autocomplete="off" autocorrect="off" autocapitalize="words" spellcheck="false" enterkeyhint="search" aria-label="Search every player in the league">'
    +'<button type="button" class="ps-x" id="psX" hidden aria-label="Clear search"><svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="10"/><path d="M6.6 6.6l6.8 6.8M13.4 6.6l-6.8 6.8"/></svg></button></label>'
    +'<button type="button" class="ps-cn" id="psCn">Cancel</button></div>'
    +'<div class="ps-sc" id="psSc" hidden></div><div id="psRes" aria-live="polite"></div>';
  host.insertBefore(el,host.firstChild);
  var i=document.getElementById('psQ'),w=document.getElementById('psw');
  i.addEventListener('focus',function(){w.classList.add('on');psLoad();psRender();});
  i.addEventListener('blur',function(){setTimeout(function(){if(document.activeElement!==i&&!PS.q){w.classList.remove('on');psRender();}},120);});
  i.addEventListener('input',function(){psSet(i.value);});
  i.addEventListener('keydown',function(e){
    if(e.key==='Enter'){e.preventDefault();var r=document.querySelector('#psRes .ps-r');if(PS.q&&r&&psNorm(PS.q).length>2&&document.querySelectorAll('#psRes .ps-r').length===1)r.click();else i.blur();}
    if(e.key==='Escape'){i.value='';psSet('');i.blur();}
  });
  document.addEventListener('click',function(e){
    var t=e.target;if(!t||!t.closest)return;
    if(t.closest('#psX')){i.value='';psSet('');i.focus();return;}
    if(t.closest('#psCn')){i.value='';PS.scope='all';w.classList.remove('on');psSet('');i.blur();return;}
    var b=t.closest('[data-pssc]');if(b){PS.scope=b.getAttribute('data-pssc');PS.more=false;psRender();return;}
    if(t.closest('[data-psmore]')){PS.more=true;psRender();return;}
    if(t.closest('[data-psclr]')){try{localStorage.removeItem(PS_RK);}catch(x){}psRender();i.focus();return;}
    b=t.closest('[data-psid]');
    if(b){var p=ALL[b.getAttribute('data-psid')];if(p){psRemember(p.id);if(document.activeElement===i)i.blur();modal(p);}return;}
    /* the round search button in the tab bar: go to Players with the keyboard up (after showTab has run) */
    if(t.closest('#bn-players'))psFocus();
  });
  psCount();
}

streamsRender();
LK.start();
/* ---------- no pinch zoom, double-tap zoom, text selection or image drag (iOS ignores the viewport tag) ---------- */
(function(){
  var stop=function(e){e.preventDefault();};
  ['gesturestart','gesturechange','gestureend'].forEach(function(t){document.addEventListener(t,stop,{passive:false});});
  document.addEventListener('dblclick',stop,{passive:false});
  document.addEventListener('selectstart',function(e){if(!(e.target.closest&&e.target.closest('input,textarea,[contenteditable=true]')))e.preventDefault();});
  document.addEventListener('dragstart',stop);
  document.addEventListener('contextmenu',function(e){if(!(e.target.closest&&e.target.closest('input,textarea')))e.preventDefault();});
})();
appStart();
uiStart();try{psInit();}catch(e){}showTab((location.hash||'').slice(1));
updStart();lvStart();
})();
