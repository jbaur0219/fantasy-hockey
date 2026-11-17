#!/usr/bin/env python3
"""
UI LAYER (cosmetic + navigation only; never changes any numbers or suggestions).

Applied LAST by build.py, after every other tab has been patched into the page. It:

  1. Replaces the 8 wrapping tab pills with 5 grouped tabs (a bottom bar on phones, a top bar on desktop):
        Today | Moves | Roster | Players | League
     Moves, Roster and League have a small second row (Moves: Game plan / Swap lab / Streams, and so on).
  2. Re-homes the existing cards into those tabs by their card title, so every card from the old tabs is still
     there. Secondary cards are collapsible (tap the card title) and start collapsed when they are long or reference-only.
  3. Adds player headshots and team logos next to every player name (ESPN's image CDN, lazy-loaded, with a switch
     in the footer to turn photos off).
  4. Raises contrast, enlarges tap targets, keeps player names pinned while wide tables scroll sideways,
     and uses 16px inputs so iPhones do not zoom when you tap a search box.

If any exact-match patch below stops matching (because another module changed the page code), the whole layer is
skipped and the page keeps the earlier layout, the same all-or-nothing approach the other modules use.
"""

CSS = r"""
/* ===== UI layer ===== */
:root{--bg:#eef1f6;--card:#fff;--text:#101828;--muted:#475467;--line:#cdd5e1;--accent:#1d4ed8;--on-accent:#fff;
--green:#15803d;--amber:#b45309;--red:#b91c1c;--gray:#4b5563;--soft:#e2eaff}
@media (prefers-color-scheme:dark){:root{--bg:#0b1020;--card:#151c2e;--text:#f1f5ff;--muted:#b0bad1;--line:#2f3a58;
--accent:#7ab0ff;--on-accent:#0b1020;--green:#4ade80;--amber:#fbbf24;--red:#f87171;--gray:#aab4cc;--soft:#1f2c50}}
body{font-size:15px;-webkit-text-size-adjust:100%}
.wrap{max-width:1040px}
h1{font-size:20px;line-height:1.2}
.sub{font-size:12px;margin:2px 0 8px}
.card{box-shadow:0 1px 2px rgba(16,24,40,.07);margin:12px 0}
.muted{font-size:13px}
.good{color:var(--green)}.warn{color:var(--amber)}.bad{color:var(--red)}
.pill{color:#fff!important}.start{background:#15803d}.risky{background:#b45309}.bench{background:#b91c1c}.done{background:#4b5563}
.step .num{color:var(--on-accent)}
.chip-btn{padding:7px 14px}
.tabs{display:none!important}
section[id^="t-"]{display:none!important}
#rfbar{margin:0 0 8px!important;gap:8px!important}
#rfbtn{padding:5px 12px!important;font-size:13px!important;border-radius:999px!important}
#appbar .card,#lockbar .card{margin:6px 0!important;padding:9px 12px!important;font-size:13px;line-height:1.35}

/* navigation */
#bnav{position:sticky;top:0;z-index:30;display:flex;gap:6px;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line);margin-bottom:8px}
#bnav button{display:flex;align-items:center;gap:7px;border:1px solid var(--line);background:var(--card);color:var(--text);
border-radius:999px;padding:8px 16px;font:600 14px/1 system-ui,-apple-system,sans-serif;cursor:pointer;position:relative}
#bnav button svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex:none}
#bnav button.on{background:var(--accent);color:var(--on-accent);border-color:var(--accent)}
.bdg{background:var(--red);color:#fff;border-radius:999px;font-size:11px;min-width:18px;height:18px;line-height:18px;text-align:center;padding:0 5px;font-weight:700}
#snav{display:flex;gap:4px;background:var(--soft);padding:4px;border-radius:12px;margin:6px 0 4px;position:sticky;top:58px;z-index:20}
#snav:empty{display:none}
#snav button{flex:1;border:0;background:none;color:var(--text);font:600 14px/1 system-ui,-apple-system,sans-serif;padding:10px 6px;border-radius:9px;cursor:pointer}
#snav button.on{background:var(--card);box-shadow:0 1px 3px rgba(16,24,40,.18);color:var(--accent)}
.uview{display:none}.uview.on{display:block}
.usub{display:none}.usub.on{display:block}
.ufoot{margin:20px 0 0;display:flex;gap:10px;align-items:center;flex-wrap:wrap}

/* collapsible cards */
.card.collapsible>h2{cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:8px;user-select:none;-webkit-user-select:none}
.card.collapsible>h2:after{content:'';width:8px;height:8px;border-right:2px solid var(--muted);border-bottom:2px solid var(--muted);
transform:rotate(45deg);margin:-4px 4px 0 0;flex:none;transition:transform .15s}
.card.collapsible.closed>h2:after{transform:rotate(-45deg);margin:0 6px 0 0}
.card.collapsible.closed>*:not(h2){display:none!important}
.card.collapsible.closed>h2{margin-bottom:0}
.goto{margin-top:10px;display:flex;gap:8px;flex-wrap:wrap}
[data-ut="Suggested moves"] .why{display:none}

/* photos */
.av{position:relative;display:inline-block;width:30px;height:30px;border-radius:50%;background:var(--soft);vertical-align:middle;margin-right:8px;flex:none}
.av>img:first-child{width:100%;height:100%;border-radius:50%;object-fit:cover;object-position:50% 12%;display:block}
.av .tl{position:absolute;right:-6px;bottom:-5px;width:16px;height:16px;border-radius:50%;background:var(--card);padding:1px;box-shadow:0 0 0 1px var(--line)}
.av.nf>img:first-child{visibility:hidden}
.mhead .av{width:52px;height:52px;margin-right:10px}.mhead .av .tl{width:22px;height:22px}
body.nophoto .av{display:none}
/* player popup: sits above the bottom nav, fits the visible screen, scrolls on its own */
#modal{z-index:60;overscroll-behavior:contain;touch-action:none}
#modal .box{max-height:calc(100vh - 28px);max-height:calc(100dvh - 28px);overflow-y:auto;overscroll-behavior:contain;-webkit-overflow-scrolling:touch;touch-action:pan-y;padding-bottom:calc(16px + env(safe-area-inset-bottom))}
#modal .mhead{position:sticky;top:-16px;background:var(--card);z-index:2;padding:12px 0 8px;margin:-16px 0 10px;align-items:center}
#modal .mhead .x{margin-left:auto;font-size:26px;line-height:1;padding:4px 12px}
body.mlock{overflow:hidden;position:fixed;left:0;right:0;width:100%}
td a.pl{white-space:nowrap}

/* tables: keep the player name pinned while the rest scrolls */
.scroll{margin:0 -4px;-webkit-overflow-scrolling:touch}
.scroll td:first-child,.scroll th:first-child{position:sticky;left:0;background:var(--card);z-index:1;box-shadow:1px 0 0 var(--line)}
.scroll td,.scroll th{padding:9px 8px}
td,th{white-space:nowrap}
td:last-child{white-space:normal;min-width:120px}
th{color:var(--muted)}

/* streams + playbook */
.stchips{display:flex;gap:6px;overflow-x:auto;padding:2px 0 6px;-webkit-overflow-scrolling:touch}
.stchips .chip-btn{white-space:nowrap;flex:none}
table.edge{width:100%;border-collapse:collapse;font-size:13px}table.edge th,table.edge td{padding:6px 5px;border-bottom:1px solid var(--line,#ddd);text-align:left;white-space:nowrap}table.edge td:last-child{white-space:nowrap;min-width:0}
.sgh{font-weight:700;font-size:13px;margin:14px 0 2px;color:var(--text)}
.srow{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:10px 0;border-top:1px solid var(--line)}
.srow .sm{min-width:0;flex:1}.srow .sr{display:flex;align-items:center;gap:10px;flex:none;text-align:right}
.srow .sr .chip-btn{padding:6px 10px;font-size:13px}
.pbh{font-weight:700;margin:14px 0 4px;padding-top:10px;border-top:1px solid var(--line)}.pbh:first-child{border-top:0;margin-top:0;padding-top:0}
.pbl{margin:0;padding-left:18px}.pbl li{margin:6px 0}
@media (max-width:720px){.srow{flex-wrap:wrap}.srow .sr{width:100%;justify-content:space-between}}

/* search combobox (Try a swap) */
.cb{position:relative;margin-top:8px;scroll-margin-top:72px}
.cb>label{display:block;font-weight:600;font-size:13px;color:var(--muted);margin-bottom:4px}
.cb .cbin{display:flex;gap:6px}
.cb input{flex:1;min-width:0;width:100%}
.cb .cbx{border:1px solid var(--line);background:var(--card);color:var(--muted);border-radius:8px;width:40px;font-size:20px;cursor:pointer}
.cbl{position:absolute;left:0;right:0;top:100%;margin-top:4px;z-index:40;background:var(--card);border:1px solid var(--line);border-radius:10px;
max-height:min(48vh,380px);overflow:auto;box-shadow:0 8px 24px rgba(16,24,40,.25);-webkit-overflow-scrolling:touch}
.cbl .gh2{position:sticky;top:0;background:var(--soft);color:var(--text);font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;padding:6px 10px}
.cbl .opt2{display:flex;align-items:center;gap:8px;padding:8px 10px;border-top:1px solid var(--line);cursor:pointer;font-size:14px}
.cbl .opt2.act,.cbl .opt2:hover{background:var(--soft)}
.cbl .opt2 .nm{flex:1;min-width:0}.cbl .opt2 .nm b{display:block;font-weight:600}
.cbl .opt2 .nm span{color:var(--muted);font-size:12px}
.cbl .opt2 .pt{font-weight:700;white-space:nowrap}
.cbl .none{padding:12px;color:var(--muted)}
.cbl .opt2 .av{width:28px;height:28px;margin:0}

@media (max-width:720px){
  .wrap{padding:10px 12px 110px}
  .card{padding:14px 12px;border-radius:14px}
  #bnav{position:fixed;top:auto;bottom:0;left:0;right:0;margin:0;padding:6px 6px calc(6px + env(safe-area-inset-bottom));gap:0;
    background:var(--card);border-top:1px solid var(--line);border-bottom:0;box-shadow:0 -2px 12px rgba(16,24,40,.12)}
  #bnav button{flex:1;flex-direction:column;gap:3px;border:0;background:none;border-radius:10px;padding:6px 0;font-size:11px;color:var(--muted)}
  #bnav button svg{width:24px;height:24px}
  #bnav button.on{background:none;color:var(--accent)}
  #bnav .bdg{position:absolute;top:0;left:55%}
  #snav{top:0;margin-top:0}
  input[type=text],select{font-size:16px;padding:9px 10px}
  table{font-size:14px}
  td a.pl+span.muted{display:none}
  .av{width:28px;height:28px;margin-right:7px}
  .scroll td .av{width:24px;height:24px;margin-right:6px}.scroll td .av .tl{display:none}
  .scroll td,.scroll th{padding:8px 6px}
  .scroll td:last-child{white-space:nowrap;min-width:0}
  .scroll td:first-child{max-width:46vw;overflow:hidden;text-overflow:ellipsis}
  table.edge td:first-child,table.edge th:first-child{max-width:none}
  .controls{gap:10px}
  .controls input[type=text]{flex:1 1 100%}
  .big{font-size:26px}
  .team .s{font-size:30px}
  .chip{min-width:0!important;flex:1 1 100%}
}
"""

JS = r"""/* ---------- UI layer: grouped tabs, headshots, collapsible cards ---------- */
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
 {id:'today',label:'Today',subs:[{id:'main',label:'Today',cards:[['This week matchup'],['Goalie decisions'],['Lineup sheet'],['Suggested moves'],['Lineup alerts (today)']]}]},
 {id:'moves',label:'Moves',subs:[
   {id:'plan',label:'Game plan',cards:[['Your game plan for the rest of this week'],['Next week preview'],['Day-by-day playbook'],['The moves, in the order to make them'],['Moves and waivers'],['Day-by-day lineup check',1],['Best use of your moves this week',1]]},
   {id:'swap',label:'Swap lab',cards:[['Try a swap'],['Your roster: who to look at this week']]},
   {id:'streams',label:'Streams',cards:[['Best skater streams by day'],['Best adds for the rest of this week'],['Streaming goalies by day'],['Best stream targets for the week',1]]}]},
 {id:'roster',label:'Roster',subs:[
   {id:'team',label:'My team',cards:[['My roster']]},
   {id:'week',label:'Schedule',cards:[['Schedule edge'],['Your week at a glance'],['Games per team, rest of this matchup',1]]}]},
 {id:'players',label:'Players',subs:[{id:'main',label:'Players',cards:[['Free agents and waivers']]}]},
 {id:'league',label:'League',subs:[
   {id:'table',label:'Standings',cards:[['Standings and power rankings']]},
   {id:'trade',label:'Trade lab',cards:[['On the trading block'],['Trade finder'],['Trade lab']]}]}
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
  var nav=document.createElement('nav');nav.id='bnav';nav.setAttribute('aria-label','Main');
  nav.innerHTML=VIEWS.map(function(v){return '<button type="button" data-go="'+v.id+'" id="bn-'+v.id+'">'+ICON[v.id]+'<span>'+v.label+'</span></button>';}).join('');
  wrap.insertBefore(nav,secs[0]);
  var ui=document.createElement('div');ui.id='ui';
  ui.innerHTML='<div id="snav"></div>'+VIEWS.map(function(v){
    return '<div class="uview" id="v-'+v.id+'">'+v.subs.map(function(s){return '<div class="usub" id="s-'+v.id+'-'+s.id+'"></div>';}).join('')+'</div>';}).join('');
  wrap.insertBefore(ui,last.nextSibling);
  var ft=document.createElement('div');ft.className='ufoot';
  ft.innerHTML='<button type="button" class="chip-btn" id="phBtn"></button><span class="muted">Read-only: nothing here changes anything in ESPN.</span>';
  wrap.insertBefore(ft,ui.nextSibling);
  try{UI.photos=localStorage.getItem('fh_photos')!=='off';}catch(e){}
  uiPhotos();
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
  var n=P?P.moves.filter(function(m){return m.tier==='make';}).length:0;
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
    var st=UI.open[t];c.classList.toggle('closed',st===undefined?!!sp.c:!st);
    if(t==='Suggested moves')uiNext(c);
    var old=null;$$('.card',box).forEach(function(x){if(x.getAttribute('data-ut')===t&&x!==c)old=x;});
    if(old)old.parentNode.replaceChild(c,old);else box.appendChild(c);
  });
  try{uiStreams();uiPlaybook();}catch(e){}
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
  var moved=UI.booted&&(UI.view!==v||UI.sub[v]!==s);
  UI.view=v;
  VIEWS.forEach(function(x){
    document.getElementById('v-'+x.id).classList.toggle('on',x.id===v);
    document.getElementById('bn-'+x.id).classList.toggle('on',x.id===v);
    x.subs.forEach(function(y){document.getElementById('s-'+x.id+'-'+y.id).classList.toggle('on',x.id===v&&y.id===s);});
  });
  document.getElementById('snav').innerHTML=V.subs.length>1?V.subs.map(function(y){return '<button type="button" data-go="'+v+'/'+y.id+'"'+(y.id===s?' class="on"':'')+'>'+y.label+'</button>';}).join(''):'';
  try{history.replaceState(null,'','#'+v+(V.subs.length>1?'/'+s:''));}catch(e){}
  if(UI.booted)window.scrollTo(0,0);
  UI.booted=true;
}

/* ---------- Streams (one card) + Day-by-day playbook (built from the existing data) ---------- */
var HIDE={'Best skater streams by day':1,'Best adds for the rest of the week':1,'Best stream targets for the week':1,'Streaming goalies by day':1};
UI.st={sel:'week',pos:'All'};
function dayShort(l){var p=String(l).split(' ');return p[0]+(p[2]?' '+p[2]:'');}
function uiPut(title,html,home){
  var sp=SPEC[title]||home,box=document.getElementById('s-'+sp.v+'-'+sp.s);
  if(!box)return;
  var c=document.createElement('div');c.className='card collapsible';c.setAttribute('data-ut',title);
  var st=UI.open[title];if(st===undefined?!!sp.c:!st)c.classList.add('closed');
  c.innerHTML='<h2>'+esc(title)+'</h2>'+html;
  var old=null;$$('.card',box).forEach(function(x){if(x.getAttribute('data-ut')===title)old=x;});
  if(old)old.parentNode.replaceChild(c,old);else box.appendChild(c);
}
function stRow(r,sub,pts,unit){
  return '<div class="srow"><div class="sm"><a class="pl" data-id="'+r.id+'">'+esc(r.n)+'</a> <span class="muted">'+esc(r.pos||'G')+' '+esc(r.tm)+(r.rl?' ['+esc(r.rl)+']':'')+'</span><div class="muted">'+sub+'</div></div>'
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
      L.forEach(function(r){h+=stRow(r,(r.h?'vs ':'@ ')+esc(r.o)+' <span class="'+(r.tag==='weak'?'good':(r.tag==='strong'?'warn':'muted'))+'">'+(r.tag==='weak'?'soft':(r.tag==='strong'?'tough':'avg'))+'</span> &middot; '+r.gl+' gm left'+(r.w?' <span class="warn">&middot; waivers</span>':''),f(r.e,1),'pts');});
    });
    h+='<div class="muted" style="margin-top:8px">Expected points for that day: outlook adjusted for opponent strength and home ice.</div>';
  }
  uiPut('Streams',h,{v:'moves',s:'streams',c:0});
}
function wpPill(m){
  var t={done:['start','DONE'],due:['risky','DO TODAY'],missed:['done','MISSED'],unavailable:['bench','NOT AVAILABLE']}[m.state];
  return t?'<span class="pill '+t[0]+'">'+t[1]+'</span> ':'';
}
function wpMove(m){
  var why=(m.why&&m.why[0])?'<div class="muted">'+esc(m.why[0])+'</div>':'';
  var note=(m.agree===false)?' <span class="warn">&middot; today\'s model no longer picks him</span>':'';
  return '<li>'+wpPill(m)+'<span class="'+(m.tier==='make'?'good':'warn')+'"><b>'+(m.tier==='make'?'Make this move':'Spare move')+'</b></span>: add <a class="pl" data-id="'+m.add.id+'">'+esc(m.add.n)+'</a> <span class="muted">('+esc(m.add.pos)+', '+esc(m.add.tm)+', '+m.games+' gm)</span>, drop <a class="pl" data-id="'+m.drop.id+'">'+esc(m.drop.n)+'</a> <span class="muted">('+esc(m.drop.pos)+', '+esc(m.drop.tm)+')</span> &middot; <span class="good">'+sgn(m.gain,1)+' pts</span>'+(m.state==='done'?'':note)+why+'</li>';
}
function uiPlaybook(){
  var P=(typeof lkPlan==='function'&&D.gameplan)?lkPlan(D.gameplan):null,S=D.streams,WP=D.weekplan;
  if(!P||!S)return;
  var locked=!!(WP&&WP.moves&&WP.moves.length),mv=locked?WP.moves:(P.moves||[]),h='';
  if(WP&&WP.moves){
    var nd=WP.moves.filter(function(m){return m.state==='done';}).length,due=WP.moves.filter(function(m){return m.state==='due';}).length;
    h+='<div class="muted" style="margin-bottom:6px">Locked plan for the week of <b>'+esc(WP.week_label||'')+'</b>: +'+f(WP.gain,1)+' projected points ('+f(WP.base,0)+' &rarr; '+f(WP.total,0)+'). It does not change during the week. Each refresh only updates each move\'s status. '+nd+' of '+WP.moves.length+' done'+(due?', '+due+' due today':'')+'.</div>';
  }
  var labels=[],seen={};
  if(locked)mv.forEach(function(m){if(S.days.indexOf(m.day)<0&&!seen[m.day]){seen[m.day]=1;labels.push(m.day);}});
  S.days.forEach(function(l){labels.push(l);});
  labels.forEach(function(lbl){
    var i=S.days.indexOf(lbl),past=i<0,closed=!past&&LK.closed(i);
    if(closed&&!mv.some(function(m){return m.day===lbl;}))return;
    var items=[];
    mv.forEach(function(m){
      if(!past&&m.waiver&&m.t-1===i&&m.state!=='done')items.push('<li><b>Claim</b> <a class="pl" data-id="'+m.add.id+'">'+esc(m.add.n)+'</a> <span class="muted">(waivers, so the claim must go in today to add him '+esc(dayShort(m.day))+')</span></li>');
      if(m.day===lbl)items.push(wpMove(m));
    });
    if(!past&&!closed){
      (D.goalies||[]).forEach(function(g){(g.rows||[]).forEach(function(r){
        if(r.day!==lbl)return;
        items.push('<li><b>Goalie</b> <a class="pl" data-id="'+g.p.id+'">'+esc(g.p.n)+'</a> '+(r.home?'vs':'@')+' '+esc(r.opp)+': <span class="pill '+r.cls+'">'+esc(r.verdict)+'</span> <span class="muted">win '+Math.round(r.p*100)+'%</span></li>');});});
      var tl=(((D.planner&&D.planner.stream)||[]).filter(function(x){return x.i===i;}).sort(function(a,b){return b.e-a.e;}))[0];
      if(tl&&tl.e>=0.8)items.push('<li><span class="muted">Optional goalie stream: <a class="pl" data-id="'+tl.id+'">'+esc(tl.n)+'</a> '+(tl.h?'vs':'@')+' '+esc(tl.o)+', win '+Math.round(tl.p*100)+'%</span></li>');
    }
    h+='<div class="pbh">'+esc(lbl)+'</div>'+(items.length?'<ul class="pbl">'+items.join('')+'</ul>':'<div class="muted">No move today. Set your lineup and check the alerts.</div>');
  });
  h+='<div class="muted" style="margin-top:10px">A projection built from lines, schedules and opponents, not a guarantee. Each step assumes the earlier ones were made. Unconfirmed starters and late scratches can change a day, so recheck the morning of. The card below, "Your game plan", is today\'s fresh model for comparison.'+((P.opt&&P.opt.changed&&P.opt.delta>=0.3)?' The optimizer found +'+f(P.opt.delta,1)+' points over simple move-by-move planning.':'')+'</div>';
  uiPut('Day-by-day playbook',h,{v:'moves',s:'plan',c:0});
  var PV=WP&&WP.preview;
  if(PV){
    var g='<div class="muted" style="margin-bottom:6px">Draft for the week starting <b>'+esc(PV.first_day||'')+'</b>: +'+f(PV.gain,1)+' projected points ('+f(PV.base,0)+' &rarr; '+f(PV.total,0)+'). Built from your roster and the real schedule as of now. It locks on the first refresh of the new week, with fresher news.</div>';
    var byDay={},order=[];
    PV.moves.forEach(function(m){if(!byDay[m.day]){byDay[m.day]=[];order.push(m.day);}byDay[m.day].push(m);});
    if(!order.length)g+='<div class="muted">No move clearly adds points next week yet.</div>';
    order.forEach(function(d){g+='<div class="pbh">'+esc(d)+'</div><ul class="pbl">'+byDay[d].map(function(m){return wpMove({add:m.add,drop:m.drop,games:m.games,gain:m.gain,tier:m.tier,why:m.why,state:'waiting'});}).join('')+'</ul>';});
    uiPut('Next week preview',g,{v:'moves',s:'plan',c:0});
  }else{
    $$('.card[data-ut="Next week preview"]').forEach(function(x){x.parentNode.removeChild(x);});
  }
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
    gl.sort(function(a,b){return b.r.e-a.r.e;});
    var tight=bench.length>0;
    if(tight)anyTight=true;
    h+='<div class="pbh">'+esc(lbl)+(i===0?' <span class="muted">(today)</span>':'')+'</div>';
    if(gl.length)h+='<div><b>Goalies</b></div><ul class="pbl">'+gl.map(function(x){
      return '<li><a class="pl" data-id="'+x.g.id+'">'+esc(x.g.n)+'</a> '+(x.r.home?'vs':'@')+' '+esc(x.r.opp)+' <span class="pill '+x.r.cls+'">'+esc(x.r.verdict)+'</span> <span class="muted">win '+Math.round(x.r.p*100)+'% &middot; '+sgn(x.r.e,1)+' pts</span></li>';}).join('')+'</ul>';
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
  uiPut('Schedule edge',h,{v:'roster',s:'week',c:0});
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
  uiBuild();uiLayout();
  var secs=$$('section[id^="t-"]'),q=false;
  var mo=new MutationObserver(function(){if(q)return;q=true;setTimeout(function(){q=false;uiLayout();},0);});
  secs.forEach(function(s){mo.observe(s,{childList:true});});
  var mo2=new MutationObserver(function(){if(!decQ){decQ=true;(window.requestAnimationFrame||setTimeout)(uiDecorate);}});
  mo2.observe(document.body,{childList:true,subtree:true});
  document.addEventListener('click',function(e){
    var t=e.target;if(!t||!t.closest)return;
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

/* ---------- tabs + startup ---------- */"""

JS_PATCHES = [
    ("function showTab(n){", "function showTabOld(n){"),
    ("/* ---------- tabs + startup ---------- */", JS),
    ("showTab((location.hash||'').slice(1));", "uiStart();showTab((location.hash||'').slice(1));"),
]
# optional patches: nice to have, skipped quietly if the code they touch changes
JS_OPTIONAL = [
    ("h='<div class=\"mhead\"><b>'+esc(p.n)+'</b>", "h='<div class=\"mhead\">'+avHtml(p.id,p.tm)+'<b>'+esc(p.n)+'</b>"),
    (r"+' \u00b7 read-only, nothing is changed in ESPN'", ""),
]
PAGE_OPTIONAL = [
    ('width=device-width,initial-scale=1"', 'width=device-width,initial-scale=1,viewport-fit=cover"'),
]


def apply(js, page, css):
    """Returns (js, page, css, ok). All-or-nothing for the required parts."""
    for old, _ in JS_PATCHES:
        if js.count(old) != 1:
            print(f"  (ui layer skipped: '{old[:45]}...' not found once)")
            return js, page, css, False
    for old, new in JS_PATCHES:
        js = js.replace(old, new)
    for old, new in JS_OPTIONAL:
        if js.count(old) == 1:
            js = js.replace(old, new)
        else:
            print(f"  (ui layer: optional patch skipped: '{old[:40]}...')")
    for old, new in PAGE_OPTIONAL:
        if page.count(old) == 1:
            page = page.replace(old, new)
    return js, page, css + CSS, True
