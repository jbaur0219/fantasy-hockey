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
td a.pl{white-space:nowrap}

/* tables: keep the player name pinned while the rest scrolls */
.scroll{margin:0 -4px;-webkit-overflow-scrolling:touch}
.scroll td:first-child,.scroll th:first-child{position:sticky;left:0;background:var(--card);z-index:1;box-shadow:1px 0 0 var(--line)}
.scroll td,.scroll th{padding:9px 8px}
td,th{white-space:nowrap}
td:last-child{white-space:normal;min-width:120px}
th{color:var(--muted)}

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
 {id:'today',label:'Today',subs:[{id:'main',label:'Today',cards:[['This week matchup'],['Goalie decisions'],['Suggested moves'],['Lineup alerts (today)']]}]},
 {id:'moves',label:'Moves',subs:[
   {id:'plan',label:'Game plan',cards:[['Your game plan for the rest of this week'],['The moves, in the order to make them'],['Moves and waivers'],['Day-by-day lineup check',1],['Best use of your moves this week',1]]},
   {id:'swap',label:'Swap lab',cards:[['Try a swap'],['Your roster: who to look at this week']]},
   {id:'streams',label:'Streams',cards:[['Best skater streams by day'],['Best adds for the rest of this week'],['Streaming goalies by day'],['Best stream targets for the week',1]]}]},
 {id:'roster',label:'Roster',subs:[
   {id:'team',label:'My team',cards:[['My roster']]},
   {id:'week',label:'Schedule',cards:[['Your week at a glance'],['Games per team, rest of this matchup',1]]}]},
 {id:'players',label:'Players',subs:[{id:'main',label:'Players',cards:[['Free agents and waivers']]}]},
 {id:'league',label:'League',subs:[
   {id:'table',label:'Standings',cards:[['Standings and power rankings']]},
   {id:'trade',label:'Trade lab',cards:[['Trade lab']]}]}
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
function uiDecorate(){
  decQ=false;
  $$('a.pl:not([data-av])').forEach(function(a){
    a.setAttribute('data-av','1');
    var id=a.getAttribute('data-id'),p=ALL[id];
    a.insertAdjacentHTML('beforebegin',avHtml(id,p&&p.tm));
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
    if(!sp){var hm=(HOME[c.parentNode.id.replace('t-','')]||'today/main').split('/');sp={v:hm[0],s:hm[1],c:0};}
    var box=document.getElementById('s-'+sp.v+'-'+sp.s);
    c.setAttribute('data-ut',t);c.classList.add('collapsible');
    var st=UI.open[t];c.classList.toggle('closed',st===undefined?!!sp.c:!st);
    if(t==='Suggested moves')uiNext(c);
    var old=null;$$('.card',box).forEach(function(x){if(x.getAttribute('data-ut')===t&&x!==c)old=x;});
    if(old)old.parentNode.replaceChild(c,old);else box.appendChild(c);
  });
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
function uiStart(){
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
