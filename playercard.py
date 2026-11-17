"""
Player card redesign (cosmetic only, read-only).

Replaces the popup that opens when you tap a player. Instead of 16+ boxes with jargon, it shows:
  1. one headline number (projected points per game) with a plain-English verdict
  2. three quick tiles (games this week, line/power-play role, ice time)
  3. usage and season stats as clean rows/tiles
  4. everything technical (luck-adjusted, expected goals, ESPN projection) folded under "Advanced stats"

Applied LAST in build.py so it overrides earlier versions of the popup. If the marker it hooks onto is not
found exactly once, it is skipped and the old popup stays, so it can never break the build.
"""

MARKER = "/* ---------- tabs + startup ---------- */"

CSS = r"""
/* player card */
#modal .pc-id{display:flex;flex-direction:column;min-width:0;gap:2px}
#modal .pc-id b{font-size:20px;line-height:1.15}
#modal .pc-id .muted{font-size:13px}
.pc-hero{margin:6px 0 4px}
.pc-k{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;font-weight:600}
.pc-big{font-size:48px;font-weight:800;line-height:1.05;margin:2px 0 4px}
.pc-sub{font-size:14px;color:var(--muted)}
.pc-chip{display:inline-block;margin-top:10px;padding:6px 12px;border-radius:999px;font-size:13px;font-weight:700}
.pc-up{background:rgba(74,222,128,.16);color:var(--green)}
.pc-down{background:rgba(251,191,36,.16);color:var(--amber)}
.pc-flat{background:var(--soft);color:var(--muted)}
.pc-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(92px,1fr));gap:8px;margin:14px 0 4px}
.pc-t{border:1px solid var(--line);border-radius:12px;padding:10px 8px;text-align:center}
.pc-tv{font-size:18px;font-weight:800;line-height:1.2}
.pc-tk{font-size:11px;color:var(--muted);margin-top:2px}
.pc-h{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:700;margin:20px 0 4px}
.pc-r{display:flex;justify-content:space-between;align-items:baseline;gap:14px;padding:10px 0;border-bottom:1px solid var(--line);font-size:15px}
.pc-r:last-child{border-bottom:0}
.pc-r b{white-space:nowrap}
.pc-n{font-size:12px;color:var(--muted);margin-top:2px;font-weight:400}
.pc-grid6{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.pc-det{margin-top:18px;border-top:1px solid var(--line)}
.pc-det>summary{cursor:pointer;list-style:none;padding:14px 0 6px;font-size:13px;font-weight:700;color:var(--accent);display:flex;align-items:center;gap:6px}
.pc-det>summary::-webkit-details-marker{display:none}
.pc-det>summary:before{content:'\25B8';font-size:12px;transition:transform .15s}
.pc-det[open]>summary:before{transform:rotate(90deg)}
.pc-vs{margin-top:14px;padding:10px 12px;border-radius:12px;background:var(--soft);font-size:14px}
.pc-fl{margin:14px 0 0;padding-left:18px;font-size:14px}
.pc-fl li{margin:3px 0}
.pc-inj{margin-top:10px;padding:8px 12px;border-radius:10px;background:rgba(248,113,113,.14);color:var(--red);font-size:13px;font-weight:700}
"""

JS = r"""/* ---------- player card (redesigned) ---------- */
function modal(p){
  var isG=p.grp==='G',unit=isG?'pts/start':'pts/game';
  function tile(v,k){return '<div class="pc-t"><div class="pc-tv">'+v+'</div><div class="pc-tk">'+k+'</div></div>';}
  function row(k,v,note){return '<div class="pc-r"><div>'+k+(note?'<div class="pc-n">'+note+'</div>':'')+'</div><b>'+v+'</b></div>';}
  var slot=p.slot==='FA'?(p.st||'Free agent'):p.slot;
  var sub=[p.pos,p.tm,slot];if(p.own!=null)sub.push(f(p.own,0)+'% rostered');
  var h='<div class="mhead">'+(typeof avHtml==='function'?avHtml(p.id,p.tm):'')
    +'<div class="pc-id"><b>'+esc(p.n)+'</b><div class="muted">'+sub.map(function(x){return esc(x);}).join(' &middot; ')+'</div></div>'
    +'<button class="x" id="mx">&times;</button></div>';
  if(p.inj&&p.inj!=='ACTIVE')h+='<div class="pc-inj">Status: '+esc(p.inj)+'</div>';

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
  if(p.rl&&p.rl!=='Not listed')t+=tile(esc(p.rl),'Line / power play');
  if(isG){if(p.sp!=null)t+=tile(Math.round(p.sp*100)+'%','Start chance');}
  else if(p.toi!=null)t+=tile(f(p.toi,1)+' min','Ice time / game');
  if(t)h+='<div class="pc-tiles">'+t+'</div>';

  if(p.slot==='FA')h+='<div class="pc-vs">Versus your weakest '+p.grp+': <b class="'+(up(p)>=0.2?'good':(up(p)<0?'bad':''))+'">'+sgn(up(p))+'</b> '+unit+'</div>';

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
  var m=$('#modal');m.innerHTML='<div class="box">'+h+'</div>';m.classList.add('open');
  $('#mx').addEventListener('click',closeModal);
}

"""


def annotate(site_data, data, now_ms):
    """Adds p['gl'] = games each player's team has left in the current Monday-Sunday matchup (not-yet-started games only)."""
    import dashboard as D
    abbr, games = D.schedule_maps(data["schedules"])
    tid_of = {ab: tid for tid, ab in abbr.items()}
    sp = data["roster"].get("scoringPeriodId", 1)
    m = site_data.get("matchup")
    nd = max(1, min(int(m["days_left"]) if m else 7, 7))
    cache = {}

    def left(tm):
        if tm not in cache:
            tid = tid_of.get(tm)
            cache[tm] = None if tid is None else sum(len(D.games_on(games, tid, sp + i, now_ms)) for i in range(nd))
        return cache[tm]

    lists = [site_data.get("mine", []), site_data.get("fas", [])] + [t.get("players", []) for t in site_data.get("teams", [])]
    for lst in lists:
        for p in lst:
            g = left(p.get("tm"))
            if g is not None:
                p["gl"] = g


def apply(js, css):
    """Returns (js, css, ok). Adds the new popup just before the startup block; the later declaration wins."""
    if js.count(MARKER) != 1:
        print("  (player card skipped: startup marker not found once)")
        return js, css, False
    return js.replace(MARKER, JS + MARKER), css + CSS, True
