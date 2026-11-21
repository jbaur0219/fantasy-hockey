
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
  cPPG,cProj,cGP,cG7,cRole,cTOI,cPP,cXG,{h:'Owned',v:function(p){return p.own;},num:1,r:function(p){return p.own==null?'-':f(p.own,0)+'%';}},{h:'Adds',v:function(p){return p.own_chg;},num:1,r:function(p){return pcTrend(p)||'<span class="muted">-</span>';}},
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

/* ---------- roster ---------- */
var R={pos:'All',q:'',view:'list'};
var SLOTN={F:'Forward slot',D:'Defense slot',G:'Goalie slot',UTIL:'UTIL slot',BN:'Bench',IR:'Injured reserve'};
function rosterRow(p){
  var bits=[esc(p.pos)+' '+esc(p.tm),esc(SLOTN[p.slot]||p.slot)];
  if(p.rl&&p.rl!=='Not listed')bits.push(esc(rlTxt(p.rl)));
  if(p.gl!=null)bits.push(p.gl+' game'+(p.gl===1?'':'s')+' left this week');
  var trend=(p.rec!=null&&p.ppg!=null&&p.gp>=6)?(p.rec-p.ppg>=0.4?' <span class="good">hot</span>':(p.rec-p.ppg<=-0.4?' <span class="warn">cold</span>':'')):'';
  var inj=(p.inj&&p.inj!=='ACTIVE')?' <span class="bad">'+esc(p.inj.replace(/_/g,' ').toLowerCase())+'</span>':'';
  var av=(typeof avHtml==='function')?avHtml(p.id,p.tm):'';
  return '<div class="srow"><div class="sm rrow">'+av+'<div class="rtx"><a class="pl" data-id="'+p.id+'">'+esc(p.n)+'</a>'+inj+trend+'<div class="muted">'+bits.join(' &middot; ')+'</div></div></div>'
    +'<div class="sr"><span><b>'+f(p.out,1)+'</b> <span class="muted">'+(p.grp==='G'?'pts/start':'pts/game')+'</span></span></div></div>';
}
function rosterList(rows){
  var bench=function(p){return p.slot==='BN'?1:0;},by=function(a,b){return (bench(a)-bench(b))||(b.out-a.out);};
  var secs=[['Forwards',function(p){return p.grp==='F'&&p.slot!=='IR';}],['Defense',function(p){return p.grp==='D'&&p.slot!=='IR';}],
            ['Goalies',function(p){return p.grp==='G'&&p.slot!=='IR';}],['Injured reserve',function(p){return p.slot==='IR';}]];
  return secs.map(function(sc){
    var rs=rows.filter(sc[1]).sort(by);
    return rs.length?'<div class="rsec">'+sc[0]+' <span class="muted">'+rs.length+'</span></div>'+rs.map(rosterRow).join(''):'';
  }).join('');
}
function rosterRender(){
  chips('#rosterPos',['All','F','D','G'],R.pos,function(v){R.pos=v;rosterRender();});
  var rows=D.mine.filter(function(p){return (R.pos==='All'||p.grp===R.pos)&&(!R.q||p.n.toLowerCase().indexOf(R.q)>=0);});
  var tg='<div class="controls"><button type="button" class="chip-btn'+(R.view==='list'?' on':'')+'" data-rv="list">Simple</button><button type="button" class="chip-btn'+(R.view==='table'?' on':'')+'" data-rv="table">All stats</button></div>';
  if(R.view==='list'){$('#rosterTbl').innerHTML=tg+rosterList(rows)+'<div class="muted" style="margin-top:8px">Projected points per game going forward (per start for goalies). Tap a name for the full card.</div>';return;}
  $('#rosterTbl').innerHTML=tg+mkTable(rosterCols,rows);wireSort($('#rosterTbl'));
}
document.addEventListener('click',function(e){var b=e.target.closest?e.target.closest('[data-rv]'):null;if(b){R.view=b.getAttribute('data-rv');rosterRender();}});

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
    return '<label class="opt"><input type="checkbox" value="'+p.id+'"> '+esc(p.n)+' <span class="muted">'+esc(p.pos)+' &middot; '+f(p.out)+(p.slot==='IR'?' &middot; IR':'')+'</span>'+(onBlock(p)?' <span class="tag">on block</span>':'')+'</label>';}).join('');
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
  var b1=lineupWithFA(mine,1),a1=lineupWithFA(myAfter,1+Math.max(0,give.length-get.length)),b2=lineupWithFA(theirs,1),a2=lineupWithFA(thAfter,1+Math.max(0,get.length-give.length));
  var d1=a1-b1,d2=a2-b2,v;
  if(d1>0.5&&d2>0.5)v='Win-win: it helps both lineups, so they might accept.';
  else if(d1>0.5&&d2<=0.5)v='Helps you but costs them about '+f(-d2,1)+' pts/week, so they may decline.';
  else if(d1<=0.5&&d2>0.5)v='Helps them more than you. You would lose about '+f(Math.max(0,-d1),1)+' pts/week.';
  else v='Little change for either side.';
  var size=myAfter.length,note='';
  if(size>22)note='<div class="warn">You would have '+size+' players and need to drop '+(size-22)+'.</div>';
  else if(size<22)note='<div class="muted">You would have '+(22-size)+' open roster spot(s).</div>';
  out.innerHTML='<div class="res">'+box('You: weekly points',f(b1,1)+' to '+f(a1,1)+' '+delta(d1))+box(esc(t.name)+': weekly points',f(b2,1)+' to '+f(a2,1)+' '+delta(d2))+'</div><div class="verdict">'+esc(v)+'</div>'+note
  +'<div class="muted" style="margin-top:8px">Points per week over the next 4 weeks: each player\'s projected points per game times his team\'s games, using each team\'s best lineup (9 F, 5 D, 1 UTIL, 2 G). It does not know what a manager actually needs, so treat it as a starting point.</div>';
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
  var rows=D.teams.map(function(t){return {id:t.id,name:t.name,rec:t.rec,w:t.w,pf:t.pf,me:t.me,power:lineup(t.players)};});
  rows.sort(function(a,b){return b.power-a.power;});rows.forEach(function(r,i){r.pr=i+1;});
  rows.sort(function(a,b){return (b.w-a.w)||(b.pf-a.pf);});
  $('#leagueTbl').innerHTML=mkTable([{h:'Team',v:function(r){return r.name;}},{h:'W-L-T',v:function(r){return r.w;},num:1,r:function(r){return esc(r.rec);}},
    {h:'Points for',v:function(r){return r.pf;},num:1,fmt:function(x){return f(x,1);}},
    {h:'Strength (pts/wk)',v:function(r){return r.power;},num:1,fmt:function(x){return f(x,0);}},
    {h:'Strength rank',v:function(r){return r.pr;},num:1}],rows);
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
  if(p.inj&&p.inj!=='ACTIVE')h+='<div class="warn" style="margin-top:8px">Status: '+esc(p.inj)+'</div>';
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
    if(LK.closed(i))return;
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
    h+='<div class="step"><div class="num" style="background:'+(a.sev>=3?'var(--amber)':'var(--gray)')+'">'+(i+1)+'</div><div>'
    +'<div><a class="pl" data-id="'+a.id+'">'+esc(a.n)+'</a> <span class="muted">('+esc(a.pos)+', '+esc(a.tm)+', '+esc(a.slot)+')</span> '+(a.rl?'<b>'+esc(rlTxt(a.rl))+'</b> ':'')
    +a.tags.map(function(t){return '<span class="'+(t.k==='under'||t.k==='role'?'warn':'muted')+'">'+esc(t.t)+'</span>';}).join(' &middot; ')+'</div>'
    +'<ul class="why">'+a.why.map(function(x){return '<li>'+esc(x)+'</li>';}).join('')+'</ul>';
    if(a.repl&&a.repl.length)h+='<div class="why"><b>Better options this week:</b> '+a.repl.map(function(r){return '<a class="pl" data-id="'+r.id+'">'+esc(r.n)+'</a> ('+esc(r.rl||'')+', '+esc(r.tm)+', '+r.gl+' gm, about '+f(r.e,1)+' pts vs '+f(a.e,1)+')';}).join(' &middot; ')+'</div>';
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
  return '<div class="step"><div class="num"'+(cfOf(m)==='strong'?'':' style="background:var(--gray)"')+'>'+(i+1)+'</div><div style="flex:1;min-width:0"><div><b>'+esc(m.day)+'</b></div>'+mvCard(m)+'</div></div>';
}
function gpTargets(list,label){
  var h='<div class="chip" style="min-width:290px"><div class="d">'+label+'</div>';
  if(!list.length)h+='<div class="m muted">None clear the role filter</div>';
  list.forEach(function(r){
    h+='<div class="m"><a class="pl" data-id="'+r.id+'">'+esc(r.n)+'</a> <span class="muted">'+esc(r.pos)+' '+esc(r.tm)+' ['+esc(r.role)+']</span> &middot; <b>'+f(r.total,1)+'</b> pts over '+r.games+' gm, from '+esc(r.first.split(' ')[0])+(r.waiver?' <span class="warn">(waivers)</span>':'')+(r.taken?' <span class="good">(in the plan)</span>':'')+'</div>';});
  return h+'</div>';
}
function gameplanRender(){
  var P=lkPlan(D.gameplan),h='';
  if(!P){$('#t-gameplan').innerHTML='<div class="card">The game plan is not available right now.</div>';return;}
  var M=P.matchup,n=P.moves.length;
  h+='<div class="card"><h2>Your game plan for the rest of this week</h2>'+lkNote(P)+keptHtml()+(P.cautious?'<div class="why warn" style="margin-bottom:8px">Line data could not be loaded this update, so only moves from the last good update are shown. New suggestions return with the next good update.</div>':'');
  if(M){
    var pa=M.p_win_after;
    h+='<div class="vs"><div class="team"><div class="n">'+esc(D.me)+'</div><div class="s">'+f(M.me_now,1)+'</div><div class="r">projected final '+Math.round(M.proj_me)+(P.gain>0?' &rarr; '+Math.round(M.proj_me+P.gain)+' with the plan':'')+'</div></div>'
    +'<div class="team right"><div class="n">'+esc(M.opp)+'</div><div class="s">'+f(M.opp_now,1)+'</div><div class="r">projected final '+Math.round(M.proj_opp)+'</div></div></div>'
    +'<div style="margin-top:10px"><span class="big">'+Math.round(M.p_win*100)+'%</span> <span class="muted">win chance now</span>'
    +(pa!=null&&n?' &nbsp;&rarr;&nbsp; <span class="big good">'+Math.round(pa*100)+'%</span> <span class="muted">if you make the plan</span>':'')+'</div>';
  }
  h+='<div style="margin-top:12px"><span class="big">+'+f(P.gain,1)+'</span> <span class="muted">projected points from '+n+' of your '+P.moves_left+' remaining moves ('+f(P.base,0)+' &rarr; '+f(P.total,0)+' for the rest of the matchup). Each move\'s gain already has its long-term cost taken off (what you lose next week and later by not keeping the player you drop).</span></div>';
  if(!n)h+='<div class="verdict">No move adds points after what you would give up. Keep your lineup and use the day-by-day check below to set it each morning.</div>';
  else{
    var cnt={strong:0,lean:0,optional:0};P.moves.forEach(function(m){cnt[cfOf(m)]++;});
    h+='<div class="verdict">'+(cnt.strong?cnt.strong+' Strong move'+(cnt.strong===1?'':'s')+' (do '+(cnt.strong===1?'it':'them')+'). ':'No Strong move this week. ')
      +(cnt.lean?cnt.lean+' Lean (worth it if you have moves to spare). ':'')+(cnt.optional?cnt.optional+' Optional (small gain, fine to skip). ':'')
      +(P.unused?P.unused+' move'+(P.unused===1?'':'s')+' stay unused because nothing else adds points.':'')+'</div>';
  }
  h+='</div>';
  if(n){h+='<div class="card"><h2>The moves, in the order to make them</h2>';P.moves.forEach(function(m,i){h+=gpMoveHtml(m,i);});
    h+='<div class="muted" style="margin-top:8px">Each step assumes the earlier ones were made. Never suggested as drops: players producing for you (1.9+ pts/game this season or 2.2+ over the last 15 days) and stars (projected 2.5+). Top-line and power-play players can be suggested when they are scoring well under what their role usually gives, have a light week, or are on your watch list, but only when the add clearly pays off after the long-term cost. Every add is on a top-six line, top-four pair or first power-play unit.</div></div>';}
  h+='<div class="card"><h2>Day-by-day lineup check</h2><div class="scroll"><table><thead><tr><th>Day</th><th>Pts now</th><th>Pts with plan</th><th>F</th><th>D</th><th>G</th><th>Empty slots</th></tr></thead><tbody>';
  P.after.forEach(function(a,i){
    if(LK.closed(i))return;
    var b=P.before[i],dl=a.pts-b.pts;
    h+='<tr><td><b>'+esc(a.day)+'</b></td><td>'+f(b.pts,1)+'</td><td>'+f(a.pts,1)+(dl>0.05?' <span class="good">('+sgn(dl,1)+')</span>':'')+'</td>'
    +'<td>'+a.f+'/9</td><td>'+a.d+'/5</td><td>'+a.g+'/2</td><td>'+(a.open?'<span class="'+(a.open<b.open?'warn':'bad')+'">'+a.open+'</span>':'<span class="good">0</span>')+(a.open!==b.open?' <span class="muted">(was '+b.open+')</span>':'')+'</td></tr>';});
  h+='</tbody></table></div><div class="muted" style="margin-top:8px">F, D and G show how many of your players have a game that day against the slots you can fill (9 forwards, 5 defensemen, 2 goalies, plus 1 UTIL). Empty slots are where a streamer scores for you. Points are expected fantasy points from your best lineup each day.</div></div>';
  h+='<div class="card"><h2>Best stream targets for the week</h2><div class="chips">'
  +gpTargets(P.targets.F,'Forwards')+gpTargets(P.targets.D,'Defensemen')+gpTargets(P.targets.G,'Goalies')+'</div>'
  +'<div class="muted" style="margin-top:8px">Ranked by total expected points over the rest of the matchup (games left x projected points per game, adjusted for opponent and home ice; goalies include their chance to start). These are the best adds if you want a stream, whether or not they made the move list above. Players already in the plan are tagged.</div></div>';
  $('#t-gameplan').innerHTML=h;
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
function appRender(){
  var mobile=/iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
  var canPush=('serviceWorker' in navigator)&&('PushManager' in window)&&('Notification' in window);
  if(!canPush){
    appBox(mobile&&!appStandalone()?'<b>Get this as an app:</b> tap the Share button, choose <b>Add to Home Screen</b>, then open it from your home screen to turn on alerts.':'');
    return;
  }
  navigator.serviceWorker.ready.then(function(reg){
    return reg.pushManager.getSubscription().then(function(sub){
      if(Notification.permission==='denied'){appBox('<span class="muted">Alerts are blocked. On iPhone: Settings, Notifications, Fantasy Hockey.</span>');return;}
      if(!sub){
        appBox('<b>Daily alerts:</b> get the day\'s best move on your phone each morning. <button class="chip-btn" id="appOn" style="margin-left:6px">Turn on alerts</button><span id="appMsg" class="muted"></span>');
        var b=document.getElementById('appOn');
        if(b)b.addEventListener('click',function(){
          var m=document.getElementById('appMsg');
          Notification.requestPermission().then(function(p){
            if(p!=='granted'){if(m)m.textContent=' Not allowed.';return;}
            return reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:appB64(APPKEY)}).then(appRender);
          }).catch(function(e){if(m)m.textContent=' Could not turn on alerts ('+(e&&e.message||e)+').';});
        });
        return;
      }
      if(!/[?&]setup\b/.test(location.search)){appBox('');return;}   /* alerts already on: hide the box (add ?setup to the address to bring the phone code back) */
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
  }).catch(function(){});
}
function appStart(){
  if('serviceWorker' in navigator){try{navigator.serviceWorker.register('sw.js').then(appRender,appRender);}catch(e){appRender();}}else{appRender();}
}

/* ---------- UI layer: grouped tabs, headshots, collapsible cards ---------- */
var UI={view:'today',sub:{},open:{},booted:false,photos:true};
var ICON={
  today:'<svg viewBox="0 0 24 24"><path d="M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>',
  moves:'<svg viewBox="0 0 24 24"><path d="M7 4L3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7"/></svg>',
  roster:'<svg viewBox="0 0 24 24"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>',
  players:'<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>',
  league:'<svg viewBox="0 0 24 24"><path d="M5 21V10M12 21V3M19 21v-7"/></svg>'
};
/* each sub-view lists its cards by title: [title, startsCollapsed] */
var VIEWS=[
 {id:'today',label:'Today',subs:[{id:'main',label:'Today',cards:[['Today'],['Track record'],['Lineup sheet',1]]}]},
 {id:'moves',label:'Moves',subs:[
   {id:'plan',label:'Game plan',cards:[['Your game plan for the rest of this week'],['Day-by-day playbook'],['Next week preview'],['Moves and waivers',1],['Day-by-day lineup check',1]]},
   {id:'swap',label:'Swap lab',cards:[['Try a swap'],['Your roster: who to look at this week']]},
   {id:'streams',label:'Streams',cards:[['Best skater streams by day'],['Best adds for the rest of this week'],['Streaming goalies by day'],['Best stream targets for the week',1]]}]},
 {id:'roster',label:'Roster',subs:[
   {id:'team',label:'My team',cards:[['My roster']]},
   {id:'week',label:'Schedule',cards:[['Schedule advantage'],['Your week at a glance'],['Games per team, rest of this matchup',1]]}]},
 {id:'players',label:'Players',subs:[{id:'main',label:'Players',cards:[['Free agents and waivers']]}]},
 {id:'league',label:'League',subs:[
   {id:'table',label:'Standings',cards:[['Standings and power rankings']]},
   {id:'trade',label:'Trade lab',cards:[['On the trading block'],['Trade finder'],['Trade lab']]},
   {id:'help',label:'Help',cards:[['What the terms mean'],['Data health']]}]}
];
var VMAP={},SPEC={};
VIEWS.forEach(function(v){VMAP[v.id]=v;v.sm={};v.subs.forEach(function(s){v.sm[s.id]=s;s.cards.forEach(function(c){SPEC[c[0]]={v:v.id,s:s.id,c:c[1]||0};});});});
var HOME={overview:'today/main',roster:'roster/team',free:'players/main',trade:'league/trade',planner:'roster/week',gameplan:'moves/plan',streams:'moves/streams',league:'league/table'};
var LEGACY={overview:'today',gameplan:'moves/plan',streams:'moves/streams',planner:'roster/week',free:'players',trade:'league/trade'};

function avHtml(id,tm){
  var logo=(tm&&/^[A-Za-z]{2,4}$/.test(tm)&&tm!=='FA')?'<img class="tl" src="https://a.espncdn.com/i/teamlogos/nhl/500/'+String(tm).toLowerCase()+'.png" loading="lazy" alt="" onerror="this.style.display=\'none\'">':'';
  return '<span class="av"><img src="https://a.espncdn.com/i/headshots/nhl/players/full/'+id+'.png" loading="lazy" alt="" onerror="this.parentNode.className+=\' nf\'">'+logo+'</span>';
}
var decQ=false;
function shortName(n){var s=String(n||'').trim().split(/\s+/);return s.length<2?n:s[0].charAt(0)+'. '+s.slice(1).join(' ');}
function uiDecorate(){
  decQ=false;
  var mob=window.matchMedia&&window.matchMedia('(max-width:720px)').matches;
  $$('a.pl:not([data-av])').forEach(function(a){
    a.setAttribute('data-av','1');
    var id=a.getAttribute('data-id'),p=ALL[id];
    if(!a.hasAttribute('data-noav'))a.insertAdjacentHTML('beforebegin',avHtml(id,p&&p.tm));
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
function uiBadge(){
  var b=document.getElementById('bn-moves');if(!b)return;
  var P=(typeof lkPlan==='function'&&D.gameplan)?lkPlan(D.gameplan):null;
  var fi=LK.first(),n=P?P.moves.filter(function(m){return (m.t===fi||(m.waiver&&m.t-1===fi))&&cfOf(m)==='strong';}).length:0;
  var o=b.querySelector('.bdg');if(o)o.parentNode.removeChild(o);
  if(n)b.insertAdjacentHTML('beforeend','<span class="bdg">'+n+'</span>');
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
  try{uiStreams();uiPlaybook();}catch(e){}
  try{uiHelp();}catch(e){}
  try{uiLineup();}catch(e){}
  try{uiEdge();}catch(e){}
  VIEWS.forEach(function(v){v.subs.forEach(function(s){
    var box=document.getElementById('s-'+v.id+'-'+s.id);
    s.cards.forEach(function(c){$$('.card',box).forEach(function(x){if(x.getAttribute('data-ut')===c[0])box.appendChild(x);});});
  });});
  uiBadge();
  if(!decQ){decQ=true;setTimeout(uiDecorate,0);}
}
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
  'Goalie decisions':1,'Suggested moves':1,'Lineup alerts (today)':1,'Best use of your moves this week':1,'The moves, in the order to make them':1};
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
  return '<li>'+wpPill(m)+cfPill(m)+' add <a class="pl" data-id="'+m.add.id+'">'+esc(m.add.n)+'</a> <span class="muted">('+esc(m.add.pos)+', '+esc(m.add.tm)+', '+m.games+' gm)</span>, drop <a class="pl" data-id="'+m.drop.id+'">'+esc(m.drop.n)+'</a> <span class="muted">('+esc(m.drop.pos)+', '+esc(m.drop.tm)+')</span> &middot; <span class="good">'+sgn(m.gain,1)+' pts</span>'+(m.state==='done'?'':note)+why+'</li>';
}
function uiPlaybook(){
  var P=(typeof lkPlan==='function'&&D.gameplan)?lkPlan(D.gameplan):null,S=D.streams,WP=D.weekplan||{};
  if(!P||!S)return;
  var h='',fi=LK.first(),done=WP.done||[],missed=WP.missed||[],ch=WP.changes||[];
  h+='<div class="muted" style="margin-bottom:6px">One plan for the whole site: the Today screen, this page and the morning alert (Strong moves only) all use these moves. '
    +'Each update keeps a planned move unless a clearly better one comes up, and says what changed.</div>';
  if(WP.saved===false)h+='<div class="why warn" style="margin-bottom:6px">Some data was missing in this update, so this plan was not saved as the week\'s plan. The next good update replaces it.</div>';
  if(ch.length)h+='<div class="pbh">Changed since the last update</div><ul class="pbl">'+ch.map(function(c){
    return '<li><span class="muted">No longer suggested ('+esc(dayShort(c.day))+'):</span> add '+esc(c.add.n)+', drop '+esc(c.drop.n)+'. <span class="muted">'+esc(c.why)+'</span></li>';}).join('')+'</ul>';
  S.days.forEach(function(lbl,i){
    if(LK.closed(i))return;
    var items=[];
    P.moves.forEach(function(m){
      if(m.waiver&&m.t-1===i)items.push('<li><b>Claim</b> <a class="pl" data-id="'+m.add.id+'">'+esc(m.add.n)+'</a> <span class="muted">(he is on waivers, so put the claim in today to have him '+esc(dayShort(m.day))+')</span></li>');
      if(m.t===i)items.push(wpMove(Object.assign({},m,{state:i===fi?'due':'waiting'}),true));
    });
    (D.goalies||[]).forEach(function(g){(g.rows||[]).forEach(function(r){
      if(r.day!==lbl||r.cls==='done'&&r.verdict==='GAME STARTED')return;
      items.push('<li><b>Goalie</b> <a class="pl" data-id="'+g.p.id+'">'+esc(g.p.n)+'</a> '+(r.home?'vs':'@')+' '+esc(r.opp)+': <span class="pill '+r.cls+'">'+esc(r.verdict)+'</span> <span class="muted">'+esc(r.conf||'')+'</span></li>');});});
    var tl=(((D.planner&&D.planner.stream)||[]).filter(function(x){return x.i===i;}).sort(function(a,b){return b.e-a.e;}))[0];
    if(tl&&tl.e>=0.8)items.push('<li><span class="muted">Optional goalie stream: <a class="pl" data-id="'+tl.id+'">'+esc(tl.n)+'</a> '+(tl.h?'vs':'@')+' '+esc(tl.o)+', win '+Math.round(tl.p*100)+'%</span></li>');
    h+='<div class="pbh">'+esc(lbl)+(i===fi?' <span class="muted">(next day you can add)</span>':'')+'</div>'+(items.length?'<ul class="pbl">'+items.join('')+'</ul>':'<div class="muted">No move. Set your lineup and check the alerts.</div>');
  });
  if(done.length||missed.length){
    h+='<div class="pbh">Earlier this week</div><ul class="pbl">'
      +done.map(function(m){return wpMove(Object.assign({},m,{state:'done'}));}).join('')
      +missed.map(function(m){return wpMove(Object.assign({},m,{state:'missed'}));}).join('')+'</ul>';
  }
  h+='<div class="muted" style="margin-top:10px">A projection built from lines, schedules and opponents, not a guarantee. Each step assumes the earlier ones were made. Recheck the morning of: late scratches and goalie news can change a day.</div>';
  uiPut('Day-by-day playbook',h,{v:'moves',s:'plan',c:0});
  var PV=WP&&WP.preview;
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
function lsChanges(i){
  var S=D.streams,W=S&&S.whatif,P=D.planner;
  if(!W||!P)return null;
  var gm={};P.teams.forEach(function(t){gm[t.tm]=t.g;});
  var act=W.mine.filter(function(p){return p.slot!=='IR'&&!isInj(p)&&p.grp!=='G';});
  var playing=act.filter(function(p){var g=gm[p.tm];return !!(g&&g[i]);});
  var F=playing.filter(function(p){return p.grp==='F';}).sort(function(a,b){return lsVal(b,i)-lsVal(a,i);});
  var Dn=playing.filter(function(p){return p.grp==='D';}).sort(function(a,b){return lsVal(b,i)-lsVal(a,i);});
  var rest=F.slice(9).concat(Dn.slice(5)).sort(function(a,b){return lsVal(b,i)-lsVal(a,i);});
  var start=F.slice(0,9).concat(Dn.slice(0,5)).concat(rest.slice(0,1)),ids={};start.forEach(function(p){ids[p.id]=1;});
  var into=start.filter(function(p){return p.slot==='BN';});
  var out=act.filter(function(p){return p.slot!=='BN'&&!ids[p.id];});
  return {into:into,out:out,playing:playing.length};
}
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
  clock:'<svg viewBox="0 0 28 28"><circle class="s" cx="14" cy="14" r="10"/><path class="s" d="M14 8.5V14l3.5 2.2"/></svg>'
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
  var rb=document.getElementById('rfbtn');
  if(rb){rb.className='gbtn glass';rb.removeAttribute('style');rb.innerHTML=SF.refresh;rb.setAttribute('aria-label','Refresh data');nb.querySelector('.gn-r').appendChild(rb);}
  /* tab bar: capsule + detached search button (iOS 26) */
  var old=document.getElementById('bnav');if(old)old.parentNode.removeChild(old);
  var tb=document.createElement('nav');tb.id='bnav';tb.setAttribute('aria-label','Main');
  var cap=VIEWS.filter(function(v){return v.id!=='players';});
  tb.innerHTML='<div class="gn-edge bot"></div><div class="tbcap glass" id="tbcap"><div class="lens" id="lens"></div>'
    +cap.map(function(v){return '<button type="button" data-go="'+v.id+'" id="bn-'+v.id+'" aria-label="'+v.label+'">'+SF[v.id]+'<span>'+v.label+'</span></button>';}).join('')
    +'</div><button type="button" class="tbsearch glass" data-go="players" id="bn-players" aria-label="Players">'+SF.players+'</button>';
  document.body.appendChild(tb);
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
/* scroll: collapse the large title into the nav bar; minimize the tab bar going down, restore going up */
var GS={y:0,raf:0,acc:0};
function glScroll(){
  if(GS.raf)return;
  GS.raf=requestAnimationFrame(function(){
    GS.raf=0;
    var y=window.pageYOffset||0,dy=y-GS.y;GS.y=y;
    var lh=document.getElementById('lhead'),nb=document.getElementById('gnav'),tb=document.getElementById('bnav');
    if(!lh||!nb||document.documentElement.classList.contains('sheet-on'))return;
    var t=document.getElementById('lhT'),lim=t.offsetTop+t.offsetHeight-48;
    nb.classList.toggle('scrolled',y>lim);
    nb.classList.toggle('edge',y>4);
    if(!RM&&y<0)t.style.transform='scale('+Math.min(1.12,1-y/700)+')';else t.style.transform='';
    /* tab bar */
    if(y<60){GS.acc=0;tb.classList.remove('min');}
    else if(dy>0){GS.acc=Math.max(0,GS.acc)+dy;if(GS.acc>40)tb.classList.add('min');}
    else if(dy<0){GS.acc=Math.min(0,GS.acc)+dy;if(GS.acc<-24)tb.classList.remove('min');}
  });
}
document.addEventListener('click',function(e){
  var tb=document.getElementById('bnav');
  if(tb&&tb.classList.contains('min')&&e.target.closest&&e.target.closest('#tbcap')){e.stopPropagation();e.preventDefault();tb.classList.remove('min');GS.acc=0;}
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
var SH={open:false,closing:0};
function sheetOpen(){
  var m=document.getElementById('modal'),bx=m.querySelector('.box'),de=document.documentElement;if(!bx)return;
  clearTimeout(SH.closing);
  var x=bx.querySelector('#mx');if(x){x.innerHTML=SF.xmark;x.className='x gbtn glass';x.setAttribute('aria-label','Close');}
  if(!bx.querySelector('.grab'))bx.insertAdjacentHTML('afterbegin','<div class="grab"></div>');
  var wrap=document.querySelector('.wrap'),y=window.pageYOffset||0;
  if(!SH.open){wrap.style.transformOrigin='50% '+y+'px';wrap.style.setProperty('--clipy',y+'px');}
  SH.open=true;
  de.classList.add('sheet-on','sh-anim');
  if(RM){de.style.setProperty('--sp','1');return;}
  bx.style.transition='none';bx.style.transform='translateY(100%)';void bx.offsetWidth;
  bx.style.transition='';bx.style.transform='';
  de.style.setProperty('--sp','0');void bx.offsetWidth;requestAnimationFrame(function(){de.style.setProperty('--sp','1');});
  if(!bx._dr){bx._dr=1;sheetDrag(bx);}
}
function sheetClose(){
  var m=document.getElementById('modal'),bx=m.querySelector('.box'),de=document.documentElement;
  if(!SH.open){m.classList.remove('open');return;}
  SH.open=false;
  de.classList.add('sh-anim');de.style.setProperty('--sp','0');
  if(bx){bx.style.transition='';bx.style.transform='translateY(105%)';}
  m.classList.add('fading');
  SH.closing=setTimeout(function(){
    m.classList.remove('open','fading');de.classList.remove('sheet-on','sh-anim');
    var w=document.querySelector('.wrap');w.style.transformOrigin='';
    if(bx)bx.style.transform='';
  },RM?0:480);
}
function sheetDrag(bx){
  var de=document.documentElement,y0=null,dy=0,t=[],drag=false,H=1;
  function start(y){y0=y;dy=0;t=[[y,performance.now()]];drag=false;H=bx.offsetHeight||1;}
  function move(y,ev){
    if(y0==null)return;
    var d=y-y0;
    if(!drag){if(bx.scrollTop>0||d<=2)return;drag=true;y0=y;d=0;bx.style.transition='none';de.classList.remove('sh-anim');}
    if(ev&&ev.cancelable)ev.preventDefault();
    dy=d;t.push([y,performance.now()]);if(t.length>5)t.shift();
    var tr=dy>=0?dy:-Math.pow(-dy,0.72);
    bx.style.transform='translateY('+tr+'px)';
    de.style.setProperty('--sp',String(Math.max(0,Math.min(1,1-Math.max(0,dy)/H))));
  }
  function end(){
    if(y0==null)return;y0=null;
    if(!drag)return;drag=false;
    var a=t[0],b=t[t.length-1],v=(b&&a&&b[1]>a[1])?(b[0]-a[0])/(b[1]-a[1]):0;
    bx.style.transition='';de.classList.add('sh-anim');
    if(dy>H*0.28||v>0.45){sheetClose();}
    else{bx.style.transform='';de.style.setProperty('--sp','1');}
  }
  bx.addEventListener('touchstart',function(e){if(e.touches.length===1)start(e.touches[0].clientY);},{passive:true});
  bx.addEventListener('touchmove',function(e){move(e.touches[0].clientY,e);},{passive:false});
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
function glAv(p,badge){
  var id=p.id,tm=p.tm||(ALL[id]&&ALL[id].tm);
  return '<span class="rav">'+(typeof avHtml==='function'?avHtml(id,tm):'')+(badge?'<i class="rb '+badge+'">'+SF[badge==='add'?'plus':'minus']+'</i>':'')+'</span>';
}
function glMoveRow(m,open){
  var c=cfOf(m),key='mv'+m.add.id+'-'+m.drop.id;
  var sub=esc(dayShort(m.day))+' &middot; '+sgn(m.gain,1)+' pts this week';
  return '<div class="row mvr'+(open?' open':'')+'" data-exp="'+key+'">'
    +'<span class="mvr-av">'+glAv(m.add,'add')+glAv(m.drop,'drop')+'</span>'
    +'<div class="row-m"><div class="row-t">Add <a class="pl" data-noav="1" data-id="'+m.add.id+'">'+esc(shortName(m.add.n))+'</a>, drop <a class="pl" data-noav="1" data-id="'+m.drop.id+'">'+esc(shortName(m.drop.n))+'</a></div><div class="row-s">'+sub+'</div></div>'
    +'<span class="badge b-'+c+'">'+CONF[c][0]+'</span><span class="rchev">'+SF.chev+'</span></div>'
    +'<div class="rx'+(open?' open':'')+'" id="x-'+key+'"><div class="rxi">'
    +(m.swapped?'<div class="rx-n">Instead of dropping '+esc(m.swapped)+', who you chose to keep.</div>':'')
    +(m.waiver?'<div class="rx-n warn">He is on waivers: put the claim in the day before.</div>':'')
    +'<p class="rx-why">'+esc(m.why1||'')+'</p>'
    +'<div class="rx-act">'+keepBtn(m.drop)+cmpBtn(m.add,m.drop)+'<button type="button" class="gbtn2" data-go="moves/plan">Whole week</button></div>'
    +'</div></div>';
}
function uiToday(){
  var C=D.clock,P=(typeof lkPlan==='function'&&D.gameplan)?lkPlan(D.gameplan):null,M=D.matchup,h='';
  if(!C)return;
  var fi=LK.first(),n=C.labels.length,isToday=fi<n&&C.dates[fi]===etToday();
  var age=C.built?(Date.now()-C.built)/3600000:0,H=D.health||{};
  /* scoreboard */
  if(M){
    var pw=Math.round(M.p_win*100),me=D.me,op=M.opp_name||'Opponent',h1=215,h2=hue(op);
    if(Math.abs(h2-h1)<40)h2=(h2+150)%360;
    var mp=D.gameplan&&D.gameplan.mp,lead=M.me_now>=M.opp_now;
    h+='<section class="sb" style="--h1:'+h1+';--h2:'+h2+'">'
      +'<div class="sb-top"><span class="sb-live"></span>'+(mp?'Week '+mp+' &middot; ':'')+M.days_left+' day'+(M.days_left===1?'':'s')+' left</div>'
      +'<div class="sb-row">'
      +'<div class="sb-tm"><div class="mono" style="--h:'+h1+'">'+esc(initials(me))+'</div><div class="sb-n">'+esc(me)+'</div><div class="sb-r">'+esc(D.rec)+'</div></div>'
      +'<div class="sb-sc"><span class="num'+(lead?'':' dim')+'" data-cu="'+M.me_now+'" data-dec="1">'+f(M.me_now,1)+'</span><span class="sb-d"></span><span class="num'+(lead?' dim':'')+'" data-cu="'+M.opp_now+'" data-dec="1">'+f(M.opp_now,1)+'</span></div>'
      +'<div class="sb-tm"><div class="mono" style="--h:'+h2+'">'+esc(initials(op))+'</div><div class="sb-n">'+esc(op)+'</div><div class="sb-r">'+esc(M.opp_rec||'')+'</div></div>'
      +'</div>'
      +'<div class="wp"><div class="wp-h"><span>Win probability</span></div>'
      +'<div class="wp-bar"><i class="a" style="--w:'+pw+'%"></i><i class="b"></i></div>'
      +'<div class="wp-l"><span><b data-cu="'+pw+'" data-suf="%">'+pw+'%</b></span><span><b>'+(100-pw)+'%</b></span></div></div>'
      +'<div class="sb-ft"><span>Projected</span><b>'+Math.round(M.proj_me)+'</b><span>&ndash;</span><b>'+Math.round(M.proj_opp)+'</b></div>'
      +'</section>';
  }
  /* problems only: the data line is silent when everything is fine */
  var warn=age>12?'The automatic update may have failed ('+Math.round(age)+' h old). Tap refresh, or check ESPN before making moves.'
    :((H.level&&H.level!=='ok'&&H.items&&H.items.length)?H.items[0]+(H.level==='bad'?' Nothing is marked Strong until it is back.':''):'');
  if(fi>=n){
    h+='<div class="sec"><div class="grp"><div class="row"><span class="ric ok">'+SF.check+'</span><div class="row-m"><div class="row-t">You\'re set for this week</div><div class="row-s">Every game day has started. Next week\'s plan shows up after the next update.</div></div></div></div></div>';
    uiPut('Today',h,{v:'today',s:'main',c:0});glCount(document.getElementById('s-today-main'));return;
  }
  var lk=C.lock[fi],when=isToday?'Today':esc(dayShort(C.labels[fi]));
  var all=P?P.moves.filter(function(m){return m.t===fi;}):[];
  var strong=all.filter(function(m){return cfOf(m)==='strong';}),small=all.filter(function(m){return cfOf(m)!=='strong';});
  var cl=P?P.moves.filter(function(m){return m.waiver&&m.t-1===fi;}):[];
  UI.exp=UI.exp||{};
  h+='<div class="sec"><div class="sec-h"><span>Moves</span>'+(lk?'<span class="sec-r">'+SF.clock+'Moves lock '+etTime(lk)+'</span>':'')+'</div><div class="grp">';
  if(warn)h+='<div class="row"><span class="ric wn">'+SF.warn+'</span><div class="row-m"><div class="row-t">Check the data</div><div class="row-s">'+esc(warn)+'</div></div></div>';
  if(strong.length||cl.length){
    h+=strong.map(function(m){return glMoveRow(m,UI.exp['mv'+m.add.id+'-'+m.drop.id]);}).join('');
    h+=cl.map(function(m){return '<div class="row"><span class="ric">'+SF.clock+'</span><div class="row-m"><div class="row-t">Claim <a class="pl" data-noav="1" data-id="'+m.add.id+'">'+esc(m.add.n)+'</a></div><div class="row-s">To add him '+esc(dayShort(m.day))+', dropping '+esc(m.drop.n)+'</div></div><span class="badge b-'+cfOf(m)+'">'+CONF[cfOf(m)][0]+'</span></div>';}).join('');
  }else{
    var nx=P?P.moves.filter(function(m){return m.t>fi&&cfOf(m)==='strong';})[0]:null;
    h+='<button type="button" class="row" data-go="moves/plan"><span class="ric ok">'+SF.check+'</span><div class="row-m"><div class="row-t">Nothing to do '+(isToday?'today':'yet')+'</div><div class="row-s">'
      +(nx?'Next: '+esc(dayShort(nx.day))+', add '+esc(shortName(nx.add.n))+' for '+esc(shortName(nx.drop.n)):'No Strong move left this week')+'</div></div><span class="rchev">'+SF.chev+'</span></button>';
  }
  if(small.length){
    var tot=small.reduce(function(s2,m){return s2+(m.net||0);},0),so=!!UI.exp.small;
    h+='<div class="row'+(so?' open':'')+'" data-exp="small"><span class="ric gy">'+SF.swap+'</span><div class="row-m"><div class="row-t">'+small.length+' smaller move'+(small.length===1?'':'s')+'</div><div class="row-s">'+sgn(tot,1)+' pts &middot; only if you have moves to spare</div></div><span class="rchev">'+SF.chev+'</span></div>'
      +'<div class="rx'+(so?' open':'')+'" id="x-small"><div class="rxi nest">'+small.map(function(m){return glMoveRow(m,UI.exp['mv'+m.add.id+'-'+m.drop.id]);}).join('')+'</div></div>';
  }
  h+='</div>';
  var ml=(P&&P.moves_left!=null)?P.moves_left:null,lim=(P&&P.limit)||7;
  if(ml!=null){
    var dots='';for(var i=0;i<lim;i++)dots+='<i class="'+(i<lim-ml?'u':'')+'"></i>';
    h+='<div class="sec-f"><span class="mdots">'+dots+'</span>'+ml+' of '+lim+' moves left this week</div>';
  }
  h+='</div>';
  /* lineup */
  var lc=isToday?lsChanges(fi):null;
  if(lc){var ng=function(p){return p.gl===0||!p.v||!(p.v[fi]>0);};
    lc={into:lc.into,playing:lc.playing,out:lc.out.slice().sort(function(a,b){return ng(b)-ng(a);}).slice(0,lc.into.length)};}
  var gl=[];(D.goalies||[]).forEach(function(g){(g.rows||[]).forEach(function(r){if(r.day===C.labels[fi])gl.push({g:g.p,r:r});});});
  gl.sort(function(a,b){return (b.r.ev||0)-(a.r.ev||0);});
  var al=(D.alerts||[]).filter(function(a){return a.k==='bad'||/injur|not starting/i.test(a.t);});
  h+='<div class="sec"><div class="sec-h"><span>Lineup</span></div><div class="grp">';
  if(!isToday)h+='<div class="row"><span class="ric gy">'+SF.clock+'</span><div class="row-m"><div class="row-t">Set it '+esc(dayShort(C.labels[fi]))+' morning</div></div></div>';
  else if(lc&&(lc.into.length||lc.out.length)){
    h+=lc.into.map(function(p){return '<div class="row">'+glAv(p)+'<div class="row-m"><div class="row-t"><a class="pl" data-noav="1" data-id="'+p.id+'">'+esc(p.n)+'</a></div><div class="row-s">On your bench, has a game</div></div><span class="badge b-start">Start</span></div>';}).join('')
      +lc.out.map(function(p){return '<div class="row">'+glAv(p)+'<div class="row-m"><div class="row-t"><a class="pl" data-noav="1" data-id="'+p.id+'">'+esc(p.n)+'</a></div><div class="row-s">'+(p.gl===0||!p.v||!(p.v[fi]>0)?'No game today':'Lower projection than the player replacing him')+'</div></div><span class="badge b-bench">Bench</span></div>';}).join('');
  }else h+='<div class="row"><span class="ric ok">'+SF.check+'</span><div class="row-m"><div class="row-t">Skaters are set</div><div class="row-s">'+(lc?lc.playing+' play today':'')+'</div></div></div>';
  al.forEach(function(a){h+='<div class="row"><span class="ric '+(a.k==='bad'?'bd':'wn')+'">'+SF.warn+'</span><div class="row-m"><div class="row-s" style="color:var(--label)">'+esc(a.t)+'</div></div></div>';});
  gl.forEach(function(x){
    var b=/bench/i.test(x.r.verdict)?'bench':(/risk/i.test(x.r.verdict)?'risky':'start');
    h+='<div class="row">'+glAv(x.g)+'<div class="row-m"><div class="row-t"><a class="pl" data-noav="1" data-id="'+x.g.id+'">'+esc(x.g.n)+'</a></div><div class="row-s">'+(x.r.home?'vs ':'@ ')+esc(x.r.opp)+(x.r.conf?' &middot; '+esc(x.r.conf):'')+'</div></div><span class="badge b-'+b+'">'+esc(x.r.verdict.replace(/\s*\(.*\)/,''))+'</span></div>';
  });
  if(isToday&&!gl.length)h+='<div class="row"><span class="ric gy">'+SF.clock+'</span><div class="row-m"><div class="row-s">None of your goalies play</div></div></div>';
  h+='</div><div class="sec-f">Updated '+esc(String(D.updated||'').replace(/^.*?,\s*/,''))+'</div></div>';
  uiPut('Today',h,{v:'today',s:'main',c:0});
  glCount(document.getElementById('s-today-main'));
}

/* ---------- Confidence, move cards and the "Keep him" list ---------- */
var CONF={strong:['Strong','Do it'],lean:['Lean','Worth it if you have moves to spare'],optional:['Optional','Small gain, fine to skip']};
function cfOf(m){return m.conf||(m.tier==='make'?'lean':'optional');}
function cfPill(m){var c=cfOf(m);return '<span class="cf cf-'+c+'">'+CONF[c][0]+'</span>';}
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
  if(y.inj==='OUT'||y.inj==='INJURY_RESERVE'||y.inj==='SUSPENSION')return {v:'none',pts:0,lines:[d+' is '+y.inj.replace('_',' ').toLowerCase()+', so he isn\'t scoring for you now.']};
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
  o=o||{};var c=cfOf(m);
  var h='<div class="mv mv-'+c+'"><div class="mv-top">'+cfPill(m)+' <span class="muted">'+esc(CONF[c][1])+'</span>'
    +(o.day?' <span class="mv-day">'+esc(dayShort(m.day))+'</span>':'')+'</div>'
    +'<div class="mv-sw"><span class="mv-k">Add</span> <a class="pl" data-id="'+m.add.id+'">'+esc(m.add.n)+'</a> <span class="muted">'+esc(m.add.pos)+' '+esc(m.add.tm)+'</span></div>'
    +'<div class="mv-sw"><span class="mv-k">Drop</span> <a class="pl" data-id="'+m.drop.id+'">'+esc(m.drop.n)+'</a> <span class="muted">'+esc(m.drop.pos)+' '+esc(m.drop.tm)+'</span></div>';
  if(m.waiver)h+='<div class="warn" style="font-size:13px">He is on waivers: put the claim in the day before.</div>';
  if(m.swapped)h+='<div class="muted" style="font-size:13px">Instead of dropping '+esc(m.swapped)+', who you chose to keep.</div>';
  h+='<div class="mv-why">'+esc(m.why1||(sgn(m.gain,1)+' pts this week'))+'</div>';
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
    var cf=[['Strong',st],['Lean',R2.lean],['Optional',R2.optional]].filter(function(c){return c[1]&&c[1].n;});
    if(cf.length)h+='<div class="muted" style="margin:6px 0">By rating: '+cf.map(function(c){return c[0]+' '+c[1].wins+' of '+c[1].n+' ahead ('+sgn(c[1].pts,1)+' pts)';}).join(' &middot; ')+'</div>';
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
    ['Strong / Lean / Optional','How sure the plan is about a move. Strong = do it: a clear gain, usually backed by extra games. Lean = a real gain, worth it if you have moves to spare. Optional = a small gain, fine to skip. Only Strong moves go in the morning alert.'],
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

/* ---------- Lineup sheet: goalies each day, and skater priorities only on days with more skaters than spots ---------- */
function lsVal(p,i){var v=(p.v&&p.v[i]>0)?p.v[i]:(p.out||0)*((p.inj&&p.inj!=='ACTIVE')?0.75:1);return v;}
function lsLine(p,i,tag){
  return '<li><a class="pl" data-id="'+p.id+'">'+esc(p.n)+'</a> <span class="muted">'+esc(p.pos)+' '+esc(p.tm)+' &middot; '+f(lsVal(p,i),1)+' pts</span>'+(tag?' '+tag:'')+'</li>';
}
function uiLineup(){
  var S=D.streams,W=S&&S.whatif,P=D.planner;
  if(!S||!W||!P)return;
  var gm={};P.teams.forEach(function(t){gm[t.tm]=t.g;});
  var act=W.mine.filter(function(p){return p.slot!=='IR'&&!isInj(p)&&p.grp!=='G';});
  var h='<div class="muted" style="margin-bottom:4px">Goalies each day, and skater start order only on days when more of your skaters play than you have spots (9 F, 5 D, 1 UTIL). On other days everyone with a game starts.</div>';
  var anyTight=false;
  S.days.forEach(function(lbl,i){
    var playing=act.filter(function(p){var g=gm[p.tm];return !!(g&&g[i]);});
    var F=playing.filter(function(p){return p.grp==='F';}).sort(function(a,b){return lsVal(b,i)-lsVal(a,i);});
    var Dn=playing.filter(function(p){return p.grp==='D';}).sort(function(a,b){return lsVal(b,i)-lsVal(a,i);});
    var startF=F.slice(0,9),startD=Dn.slice(0,5),rest=F.slice(9).concat(Dn.slice(5)).sort(function(a,b){return lsVal(b,i)-lsVal(a,i);});
    var util=rest[0]||null,bench=rest.slice(1);
    var gl=[];
    (D.goalies||[]).forEach(function(g){(g.rows||[]).forEach(function(r){if(r.day===lbl)gl.push({g:g.p,r:r});});});
    gl.sort(function(a,b){return (b.r.ev||0)-(a.r.ev||0);});
    var tight=bench.length>0;
    if(tight)anyTight=true;
    h+='<div class="pbh">'+esc(lbl)+(i===0?' <span class="muted">(today)</span>':'')+'</div>';
    if(gl.length)h+='<div><b>Goalies</b></div><ul class="pbl">'+gl.map(function(x){
      return '<li><a class="pl" data-id="'+x.g.id+'">'+esc(x.g.n)+'</a> '+(x.r.home?'vs':'@')+' '+esc(x.r.opp)+' <span class="pill '+x.r.cls+'">'+esc(x.r.verdict)+'</span> <span class="muted">'+esc(x.r.conf||'')+' &middot; win '+Math.round(x.r.p*100)+'% &middot; '+sgn(x.r.e,1)+' pts if he starts</span></li>';}).join('')+'</ul>';
    else h+='<div class="muted">No goalie of yours plays.</div>';
    if(!tight){
      h+='<div class="muted" style="margin-top:6px">Skaters: '+playing.length+' play and all fit your lineup. Start everyone with a game.</div>';
      return;
    }
    var now=function(p,want){
      if(i!==0)return '';
      var onBench=p.slot==='BN';
      if(want==='start'&&onBench)return '<span class="warn">move into lineup</span>';
      if(want==='bench'&&!onBench)return '<span class="warn">move to bench</span>';
      return '';
    };
    h+='<div style="margin-top:8px"><b>Skaters: '+playing.length+' play for '+(9+5+1)+' spots. Bench '+bench.length+'.</b></div>';
    h+='<div class="muted" style="margin-top:4px">Start</div><ul class="pbl">'
      +startF.map(function(p){return lsLine(p,i,now(p,'start'));}).join('')
      +startD.map(function(p){return lsLine(p,i,now(p,'start'));}).join('')
      +(util?lsLine(util,i,'<span class="muted">UTIL</span> '+now(util,'start')):'')+'</ul>';
    h+='<div class="muted">Bench (lowest value first to sit)</div><ul class="pbl">'+bench.slice().reverse().map(function(p){return lsLine(p,i,now(p,'bench'));}).join('')+'</ul>';
  });
  if(!anyTight)h+='<div class="muted" style="margin-top:10px">No day this week has more skaters playing than lineup spots, so there are no skater sit/start decisions. Goalies are the only calls.</div>';
  uiPut('Lineup sheet',h,{v:'today',s:'main',c:0});
}

/* ---------- Schedule edge: per-team games + opponents + best free agents ---------- */
UI.edgeWin=UI.edgeWin||0;
function uiEdge(){
  var E=D.edge;if(!E||!E.length)return;
  var w=E[Math.min(UI.edgeWin,E.length-1)],h='<div class="stchips">';
  E.forEach(function(x,i){h+='<button type="button" class="chip-btn'+(i===UI.edgeWin?' on':'')+'" data-ew="'+i+'">'+esc(x.label)+'</button>';});
  h+='</div><div class="muted" style="margin:6px 0">Teams ranked by games and opponent strength (3 easy games beat 3 average ones). Green = weak opponent, red = strong. @ = away. Best free-agent skaters from each team are on the right.</div>';
  h+='<div class="scroll"><table class="edge"><thead><tr><th>Team</th><th>GP</th>';
  w.days.forEach(function(d){h+='<th>'+esc(d)+'</th>';});
  h+='<th>Best adds</th></tr></thead><tbody>';
  w.rows.forEach(function(r){
    var by={};r.opps.forEach(function(o){by[o.d]=o;});
    h+='<tr><td><b>'+esc(r.tm)+'</b></td><td><b>'+r.g+'</b></td>';
    w.days.forEach(function(d){var o=by[d];h+='<td>'+(o?'<span class="'+(o.t==='weak'?'good':o.t==='strong'?'bad':'muted')+'">'+(o.h?'':'@')+esc(o.o)+'</span>':'')+'</td>';});
    h+='<td>'+(r.fa.length?r.fa.map(function(p){return '<a class="pl" data-id="'+p.id+'" data-noav="1">'+esc(shortName(p.n))+'</a> <span class="muted">'+esc(p.pos)+(p.w?' W':'')+'</span>';}).join('<br>'):'<span class="muted">none</span>')+'</td></tr>';
  });
  h+='</tbody></table></div>';
  uiPut('Schedule advantage',h,{v:'roster',s:'week',c:0});
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
    var ex=t.closest('[data-exp]');
    if(ex&&!t.closest('a,button:not([data-exp])')){var k=ex.getAttribute('data-exp'),x=document.getElementById('x-'+k);UI.exp=UI.exp||{};UI.exp[k]=!UI.exp[k];ex.classList.toggle('open',UI.exp[k]);if(x)x.classList.toggle('open',UI.exp[k]);return;}
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
    if(h){var c=h.parentNode;c.classList.toggle('closed');UI.open[c.getAttribute('data-ut')]=!c.classList.contains('closed');}
  });
}

/* ---------- player card (redesigned) ---------- */
function pcTrend(p){
  var c=p.own_chg;if(c==null||isNaN(c)||Math.abs(c)<0.1)return '';
  return '<span class="pc-tr '+(c>0?'u':'d')+'">'+(c>0?'\u25B2':'\u25BC')+f(Math.abs(c),1)+'</span>';
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
  var sub=[esc(p.pos),esc(p.tm),esc(slot)];if(p.own!=null)sub.push(f(p.own,0)+'% rostered'+(pcTrend(p)?' '+pcTrend(p):''));
  var h='<div class="mhead">'+(typeof avHtml==='function'?avHtml(p.id,p.tm):'')
    +'<div class="pc-id"><b>'+esc(p.n)+'</b><div class="muted">'+sub.join(' &middot; ')+'</div></div>'
    +'<button class="x" id="mx">&times;</button></div>';
  if(p.inj&&p.inj!=='ACTIVE')h+='<div class="pc-inj">Status: '+esc(p.inj)+'</div>';
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
    h+='<div class="pc-vs"><div>'+(wk?'Vs your weakest '+p.grp+', <b>'+esc(pcShort(wk.n))+'</b> ('+f(wk.out)+'): ':'Versus your weakest '+p.grp+': ')
      +'<b class="'+(u>=0.2?'good':(u<0?'bad':''))+'">'+sgn(u)+'</b> '+unit+'</div>'
      +(wk?'<button type="button" class="pc-swap" id="pcSwap">Try swap</button>':'')+'</div>';
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
    closeModal();
    if(typeof showTab==='function')showTab('moves/swap');
    if(typeof wiPick==='function'){wiPick('drop',String(wk.id));wiPick('add',String(p.id));}
    setTimeout(function(){var o=document.getElementById('wiOut');if(o&&o.scrollIntoView){try{o.scrollIntoView({block:'center'});}catch(e){}}},120);
  });
}

SF.compare='<svg viewBox="0 0 28 28"><path class="s" d="M8.5 22V12M14 22V6.5M19.5 22v-7.5"/></svg>';

/* ---------- show a sheet, or swap what an open sheet shows (no second slide-up) ---------- */
function sheetShow(h){
  var m=$('#modal'),bx=m.querySelector('.box');
  if(typeof SH!=='undefined'&&SH.open&&bx&&m.classList.contains('open')&&!m.classList.contains('fading')){
    bx.innerHTML='<div class="grab"></div>'+h;
    var x=bx.querySelector('#mx');if(x){x.innerHTML=SF.xmark;x.className='x gbtn glass';x.setAttribute('aria-label','Close');}
    bx.scrollTop=0;bx.classList.remove('sw-in');void bx.offsetWidth;bx.classList.add('sw-in');
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
    return '<div class="gl-none">The game log isn’t in this build yet. It shows up after the next data refresh.</div>';
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
    +(p.inj&&p.inj!=='ACTIVE'?'<div class="cm-inj">'+esc(p.inj)+'</div>':'')
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
  if(b){var ids=b.getAttribute('data-cmtry').split(',');closeModal();
    if(typeof showTab==='function')showTab('moves/swap');
    if(typeof wiPick==='function'){wiPick('drop',ids[1]);wiPick('add',ids[0]);}
    setTimeout(function(){var o=document.getElementById('wiOut');if(o&&o.scrollIntoView){try{o.scrollIntoView({block:'center'});}catch(x){}}},120);return;}
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
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeModal();});
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
streamsRender();
LK.start();
appStart();
uiStart();showTab((location.hash||'').slice(1));
})();
