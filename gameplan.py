#!/usr/bin/env python3
"""
GAME PLAN tab (READ-ONLY): every move to make this week, in order, to score the most points.

Why this exists
  The Streams tab only lists a move when it clears a high bar, so most weeks it says "nothing to do".
  But unused weekly moves are worth nothing, so a move that adds points after what you give up is free value.
  This tab uses ALL of your remaining moves, in two tiers:

    MAKE THESE      clears the normal bar (1.5 net points; 3.0 if the player dropped is only core through his line/pair)
    SPARE MOVES     clears a lower bar (0.5 net points), so a move that would otherwise expire still earns something

  Same protections as Streams: first power-play players, players producing for you and your stars are never dropped,
  and every add has to be on a top-six line, top-four pair or first power-play unit.

What it shows
  1. Headline: points added, projected final, win chance before and after.
  2. The moves, in the order to make them, with the full reasoning.
  3. Day-by-day lineup check: points per day before and after, and how many lineup slots are empty each day.
  4. Best weekly stream targets (forwards, defensemen, goalies) ranked by total points over the rest of the week.
"""
import math
from datetime import datetime, timedelta
from statistics import NormalDist

import analyze as A
import dashboard as D
import planner as PL
import starters as S
import streams as STR
import streams2 as S2
import streams3 as S3

INF = STR.INF
SPARE_MIN = 0.5          # lowest net gain a spare move must clear
SLOTS = {"F": 9, "D": 5, "G": 2}
TARGETS_F, TARGETS_D, TARGETS_G = 6, 6, 4


def _counts(active):
    """Lineup slots that have a player with a game today. UTIL is filled by the best leftover skater."""
    out = {}
    for g, k in SLOTS.items():
        out[g] = min(k, sum(1 for gg, v in active if gg == g and v > 0))
    extra = sum(1 for gg, v in active if gg == "F" and v > 0) - SLOTS["F"]
    extra += sum(1 for gg, v in active if gg == "D" and v > 0) - SLOTS["D"]
    out["U"] = 1 if extra > 0 else 0
    return out


def _day_rows(entries, ndays, days, game_fn):
    rows = []
    for d in range(ndays):
        act = STR._active(entries, d)
        c = _counts(act)
        open_slots = sum(SLOTS[g] - c[g] for g in SLOTS) + (1 - c["U"])
        rows.append({"day": days[d], "pts": round(STR.day_value(act), 1), "f": c["F"], "d": c["D"], "g": c["G"],
                     "u": c["U"], "open": open_slots})
    return rows


def _win_prob(m, extra):
    """Shift the matchup win chance by the points the plan adds (same normal model the Overview uses)."""
    try:
        diff = m["proj_me"] - m["proj_opp"]
        p0 = D.clamp(m["p_win"], 0.01, 0.99)
        z0 = NormalDist().inv_cdf(p0)
        if abs(z0) < 0.05 or abs(diff) < 0.5:
            sd = 14.0
        else:
            sd = abs(diff / z0)
        return round(D.clamp(D.norm_cdf((diff + extra) / sd), 0.01, 0.99), 3)
    except Exception:
        return None


def plan_full(mine, fas, game, ndays, days, standings, starters, moves_left):
    """Greedy plan. A player the plan adds is never dropped later in the same plan (that would waste two moves)."""
    keep = S2.is_droppable
    S2.is_droppable = lambda p: not p.get("_added") and keep(p)
    added = []
    try:
        return _plan_full(mine, fas, game, ndays, days, standings, starters, moves_left, added)
    finally:
        S2.is_droppable = keep
        for p in added:
            p.pop("_added", None)


def _plan_full(mine, fas, game, ndays, days, standings, starters, moves_left, added):
    entries = [{"p": p, "v": STR.values(p, game, ndays, standings, starters,
                                        lineup_goalie=(p["grp"] == "G" and p["slot"] == "G")),
                "grp": p["grp"], "join": 0, "leave": INF} for p in mine if p["slot"] != "IR"]
    pool = [{"p": p, "v": STR.values(p, game, ndays, standings, starters), "grp": p["grp"], "used": False,
             "waiver": p.get("st") == "WAIVERS"} for p in fas if S2.add_ok(p)]
    sk = sorted((x for x in pool if x["grp"] != "G"), key=lambda x: -sum(x["v"]))[:STR.SKATER_POOL]
    gk = sorted((x for x in pool if x["grp"] == "G"), key=lambda x: -sum(x["v"]))[:STR.GOALIE_POOL]
    pool = [x for x in sk + gk if sum(x["v"]) > 0]

    before_rows = _day_rows(entries, ndays, days, game)
    base_days = [STR.day_value(STR._active(entries, d)) for d in range(ndays)]
    start_total = sum(base_days)
    moves = []

    for _ in range(moves_left):
        cands = list(S3._candidates(entries, pool, ndays, base_days))
        tier_a = [c for c in cands if c[0] >= S3.need(c[3])]
        if tier_a:
            net, x, t, y, gain, pen = max(tier_a, key=lambda c: c[0])
            tier = "make"
        else:
            tier_b = [c for c in cands if c[0] >= SPARE_MIN]
            if not tier_b:
                break
            net, x, t, y, gain, pen = max(tier_b, key=lambda c: c[0])
            tier = "spare"
        mv = S3._move(entries, x, t, y, gain, pen, net, ndays, days, game, standings, S3.need(y))
        mv["tier"] = tier
        moves.append(mv)
        y["leave"] = t
        entries.append({"p": x["p"], "v": x["v"], "grp": x["grp"], "join": t, "leave": INF})
        x["used"] = True
        x["p"]["_added"] = True
        added.append(x["p"])
        base_days = [STR.day_value(STR._active(entries, d)) for d in range(ndays)]

    # order the moves by the day to make them (ties keep the order they were chosen in)
    moves = sorted(enumerate(moves), key=lambda im: (im[1]["t"], im[0]))
    moves = [m for _, m in moves]
    after_rows = _day_rows(entries, ndays, days, game)
    total = sum(base_days)

    # best weekly stream targets (what to add if you want a stream, ranked by points over the rest of the week)
    def target(x):
        p = x["p"]
        first = next((i for i in range(ndays) if x["v"][i] > 0), None)
        return {"id": p["id"], "n": p["n"], "pos": p["pos"], "tm": p["tm"], "grp": x["grp"],
                "role": S2._role_text(p), "total": round(sum(x["v"]), 1),
                "games": sum(1 for i in range(ndays) if x["v"][i] > 0),
                "first": days[first] if first is not None else "",
                "waiver": x["waiver"], "taken": x["used"]}

    ranked = sorted(pool, key=lambda x: -sum(x["v"]))
    targets = {
        "F": [target(x) for x in ranked if x["grp"] == "F"][:TARGETS_F],
        "D": [target(x) for x in ranked if x["grp"] == "D"][:TARGETS_D],
        "G": [target(x) for x in ranked if x["grp"] == "G"][:TARGETS_G],
    }
    return {"base": round(start_total, 1), "total": round(total, 1), "gain": round(total - start_total, 1),
            "moves": moves, "before": before_rows, "after": after_rows, "targets": targets}


def build(cfg, data, league, standings, now_ms, site_data):
    sp = data["roster"].get("scoringPeriodId", 1)
    abbr, games = D.schedule_maps(data["schedules"])
    m = site_data.get("matchup")
    ndays = max(1, min(int(m["days_left"]) if m else 7, 7))
    game = STR.make_game_fn(abbr, games, sp, now_ms)
    starters = S.STATE["by_team"]
    today = datetime.fromtimestamp(now_ms / 1000, D.et_zone()).date()
    days = [(today + timedelta(days=i)).strftime("%a %b %d").replace(" 0", " ") for i in range(ndays)]
    used = PL._moves_used(league, cfg["team"])
    moves_left = max(0, PL.MOVE_LIMIT - (used or 0))

    plan = plan_full(site_data["mine"], site_data["fas"], game, ndays, days, standings, starters, moves_left)
    plan["moves_left"] = moves_left
    plan["limit"] = PL.MOVE_LIMIT
    plan["used_known"] = used is not None
    plan["unused"] = max(0, moves_left - len(plan["moves"]))
    if m:
        plan["matchup"] = {"opp": m.get("opp_name"), "me_now": round(m["me_now"], 1), "opp_now": round(m["opp_now"], 1),
                           "proj_me": round(m["proj_me"], 1), "proj_opp": round(m["proj_opp"], 1),
                           "p_win": round(m["p_win"], 3), "p_win_after": _win_prob(m, plan["gain"]),
                           "days_left": m["days_left"]}
    return plan


# ---------------------------------------------------------------------------
# Website patches (exact-match, all-or-nothing)
# ---------------------------------------------------------------------------
GAMEPLAN_JS = r"""
function gpMoveHtml(m,i){
  var tag=m.tier==='make'?'<span class="good">make this move</span>':'<span class="warn">spare move</span>';
  var h='<div class="step"><div class="num"'+(m.tier==='make'?'':' style="background:var(--gray)"')+'>'+(i+1)+'</div><div>'
  +'<div><b>'+esc(m.day)+'</b> &middot; '+tag+(m.waiver?' <span class="warn">on waivers, put the claim in the day before</span>':'')+'</div>'
  +'<div>add <a class="pl" data-id="'+m.add.id+'">'+esc(m.add.n)+'</a> <span class="muted">('+esc(m.add.pos)+', '+esc(m.add.tm)+', '+m.games+' game'+(m.games===1?'':'s')+' left)</span></div>'
  +'<div>drop <a class="pl" data-id="'+m.drop.id+'">'+esc(m.drop.n)+'</a> <span class="muted">('+esc(m.drop.pos)+', '+esc(m.drop.tm)+')</span> &middot; <span class="good">'+sgn(m.gain,1)+' pts this week</span> <span class="muted">('+sgn(m.net,1)+' after what you give up)</span></div>'
  +reasonsHtml(m)+'</div></div>';
  return h;
}
function gpTargets(list,label){
  var h='<div class="chip" style="min-width:290px"><div class="d">'+label+'</div>';
  if(!list.length)h+='<div class="m muted">None clear the role filter</div>';
  list.forEach(function(r){
    h+='<div class="m"><a class="pl" data-id="'+r.id+'">'+esc(r.n)+'</a> <span class="muted">'+esc(r.pos)+' '+esc(r.tm)+' ['+esc(r.role)+']</span> &middot; <b>'+f(r.total,1)+'</b> pts over '+r.games+' gm, from '+esc(r.first.split(' ')[0])+(r.waiver?' <span class="warn">(waivers)</span>':'')+(r.taken?' <span class="good">(in the plan)</span>':'')+'</div>';});
  return h+'</div>';
}
function gameplanRender(){
  var P=D.gameplan,h='';
  if(!P){$('#t-gameplan').innerHTML='<div class="card">The game plan is not available right now.</div>';return;}
  var M=P.matchup,n=P.moves.length;
  h+='<div class="card"><h2>Your game plan for the rest of this week</h2>';
  if(M){
    var pa=M.p_win_after;
    h+='<div class="vs"><div class="team"><div class="n">'+esc(D.me)+'</div><div class="s">'+f(M.me_now,1)+'</div><div class="r">projected final '+Math.round(M.proj_me)+(P.gain>0?' &rarr; '+Math.round(M.proj_me+P.gain)+' with the plan':'')+'</div></div>'
    +'<div class="team right"><div class="n">'+esc(M.opp)+'</div><div class="s">'+f(M.opp_now,1)+'</div><div class="r">projected final '+Math.round(M.proj_opp)+'</div></div></div>'
    +'<div style="margin-top:10px"><span class="big">'+Math.round(M.p_win*100)+'%</span> <span class="muted">win chance now</span>'
    +(pa!=null&&n?' &nbsp;&rarr;&nbsp; <span class="big good">'+Math.round(pa*100)+'%</span> <span class="muted">if you make the plan</span>':'')+'</div>';
  }
  h+='<div style="margin-top:12px"><span class="big">+'+f(P.gain,1)+'</span> <span class="muted">projected points from '+n+' of your '+P.moves_left+' remaining moves ('+f(P.base,0)+' &rarr; '+f(P.total,0)+' for the rest of the matchup). Unused moves expire at the end of the week, so a move that adds points is free value.</span></div>';
  if(!n)h+='<div class="verdict">No move adds points after what you would give up. Keep your lineup and use the day-by-day check below to set it each morning.</div>';
  else{
    var mk=P.moves.filter(function(m){return m.tier==='make';}).length;
    h+='<div class="verdict">'+(mk?mk+' move'+(mk===1?'':'s')+' clear the normal bar. ':'No move clears the normal bar. ')+(n-mk?(n-mk)+' spare move'+(n-mk===1?'':'s')+' add smaller gains and are optional. ':'')+(P.unused?P.unused+' move'+(P.unused===1?'':'s')+' stay unused because nothing else adds points.':'')+'</div>';
  }
  h+='</div>';
  if(n){h+='<div class="card"><h2>The moves, in the order to make them</h2>';P.moves.forEach(function(m,i){h+=gpMoveHtml(m,i);});
    h+='<div class="muted" style="margin-top:8px">Each step assumes the earlier ones were made. First power-play players, players producing for you and your best players are never suggested as drops. Every add is on a top-six line, top-four pair or first power-play unit.</div></div>';}
  h+='<div class="card"><h2>Day-by-day lineup check</h2><div class="scroll"><table><thead><tr><th>Day</th><th>Pts now</th><th>Pts with plan</th><th>F</th><th>D</th><th>G</th><th>Empty slots</th></tr></thead><tbody>';
  P.after.forEach(function(a,i){
    var b=P.before[i],dl=a.pts-b.pts;
    h+='<tr><td><b>'+esc(a.day)+'</b></td><td>'+f(b.pts,1)+'</td><td>'+f(a.pts,1)+(dl>0.05?' <span class="good">('+sgn(dl,1)+')</span>':'')+'</td>'
    +'<td>'+a.f+'/9</td><td>'+a.d+'/5</td><td>'+a.g+'/2</td><td>'+(a.open?'<span class="'+(a.open<b.open?'warn':'bad')+'">'+a.open+'</span>':'<span class="good">0</span>')+(a.open!==b.open?' <span class="muted">(was '+b.open+')</span>':'')+'</td></tr>';});
  h+='</tbody></table></div><div class="muted" style="margin-top:8px">F, D and G show how many of your players have a game that day against the slots you can fill (9 forwards, 5 defensemen, 2 goalies, plus 1 UTIL). Empty slots are where a streamer scores for you. Points are expected fantasy points from your best lineup each day.</div></div>';
  h+='<div class="card"><h2>Best stream targets for the week</h2><div class="chips">'
  +gpTargets(P.targets.F,'Forwards')+gpTargets(P.targets.D,'Defensemen')+gpTargets(P.targets.G,'Goalies')+'</div>'
  +'<div class="muted" style="margin-top:8px">Ranked by total expected points over the rest of the matchup (games left x outlook, adjusted for opponent and home ice; goalies include their chance to start). These are the best adds if you want a stream, whether or not they made the move list above. Players already in the plan are tagged.</div></div>';
  $('#t-gameplan').innerHTML=h;
}

/* ---------- tabs + startup ---------- */"""

JS_PATCHES = [
    (",'streams','league'];", ",'gameplan','streams','league'];"),
    ("/* ---------- tabs + startup ---------- */", GAMEPLAN_JS.lstrip("\n")),
    ("\nstreamsRender();\nshowTab(", "\ngameplanRender();\nstreamsRender();\nshowTab("),
]
PAGE_PATCHES = [
    ('<button id="nav-streams">Streams</button>', '<button id="nav-gameplan">Game Plan</button><button id="nav-streams">Streams</button>'),
    ('<section id="t-streams" style="display:none"></section>',
     '<section id="t-gameplan" style="display:none"></section>\n<section id="t-streams" style="display:none"></section>'),
]


def patch_all(js, page):
    """Apply the script and page patches together, or none of them."""
    for text, pairs, label in ((js, JS_PATCHES, "page script"), (page, PAGE_PATCHES, "page layout")):
        for old, _ in pairs:
            if text.count(old) != 1:
                print(f"  (game plan patch skipped in {label}: '{old[:40]}...' not found once)")
                return js, page, False
    for old, new in JS_PATCHES:
        js = js.replace(old, new)
    for old, new in PAGE_PATCHES:
        page = page.replace(old, new)
    return js, page, True
