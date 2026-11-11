#!/usr/bin/env python3
"""
STREAMS tab (READ-ONLY): the best use of your weekly adds, plus the best skater streams for each day.

How it values a player on a given day
  - He only scores on days his team plays (and, today, only if his game hasn't started yet).
  - Points per game = his outlook, nudged up against weak opponents / strong teams and down against strong
    opponents (a modest +/- 15% at most), plus a small home-ice bump.
  - Day-to-day players count at 75%, players ruled out at 0.
  - Goalies: expected points for the start x his chance to start (confirmed starters count 100% / 0% today).

The move plan
  Looks at every free agent, every remaining day of the matchup, and every player you could drop, and picks
  moves one at a time (each add uses one of your weekly moves) that add the most points to your best daily
  lineups (9 F, 5 D, 1 UTIL, 2 G). It stops when a move isn't worth the roster churn.
"""
from datetime import datetime, timedelta

import analyze as A
import dashboard as D
import planner as PL
import starters as S

MIN_GAIN = 1.0          # a move must add at least this many points to be suggested
SKATER_POOL = 60        # free-agent skaters considered by the optimizer
GOALIE_POOL = 15
DTD = 0.75              # day-to-day players count at 75%
INF = 99
ROWS_F, ROWS_D = 8, 6   # rows kept per day in the stream lists
PROTECT_SKATER = 1.9    # skaters this good are never suggested as drops (they matter beyond this week)
PROTECT_GOALIE = 2.0


def _mult(me, opp, home, standings):
    s_me, s_opp = D.team_strength(me, standings), D.team_strength(opp, standings)
    m = 1 + 0.6 * (0.5 - s_opp) + 0.4 * (s_me - 0.5) + (0.02 if home else -0.02)
    tag = "weak" if s_opp <= 0.46 else ("strong" if s_opp >= 0.54 else "avg")
    return D.clamp(m, 0.85, 1.15), tag


def make_game_fn(abbr, games, sp, now_ms):
    tid_of = {ab: tid for tid, ab in abbr.items()}

    def game(tm, i):
        tid = tid_of.get(tm)
        gl = games.get(tid, {}).get(str(sp + i), [])
        if not gl:
            return None
        g = gl[0]
        if i == 0 and g.get("date", 0) <= now_ms:
            return None                                  # today's game already started
        home = g.get("homeProTeamId") == tid
        opp = abbr.get(g.get("awayProTeamId") if home else g.get("homeProTeamId"), "?")
        return opp, home
    return game


def values(p, game, ndays, standings, starters, lineup_goalie=False):
    """Expected fantasy points for player p on each of the next ndays days."""
    v = [0.0] * ndays
    if p["inj"] in A.BAD_INJURY:
        return v
    fac = 1.0 if p["inj"] in ("ACTIVE", None) else DTD
    for i in range(ndays):
        g = game(p["tm"], i)
        if not g:
            continue
        opp, home = g
        if p["grp"] == "G":
            s_me = D.team_strength(p["tm"], standings)
            pw = D.log5(s_me, D.team_strength(opp, standings)) + (D.HOME_ICE if home else -D.HOME_ICE)
            if p.get("svp") and p["gp"] >= 5:
                pw += D.clamp((p["svp"] - 0.905) * 2.0, -0.05, 0.05)
            pw = D.clamp(pw, 0.15, 0.85)
            e = (p["out"] or 0) + 4 * (pw - s_me)
            st = p.get("sp") or 0.5
            if lineup_goalie:
                st = max(st, 0.5)
            s = starters.get(p["tm"]) if i == 0 else None
            if s:
                st = 1.0 if S.E.norm(s["name"]) == S.E.norm(p["n"]) else 0.0
            v[i] = max(0.0, e * st * fac)
        else:
            m, _ = _mult(p["tm"], opp, home, standings)
            v[i] = (p["out"] or 0) * m * fac
    return v


def day_value(active):
    """Best lineup score for one day. active = [(group, value)]: 9 F, 5 D, 1 UTIL, 2 G."""
    fwd = sorted((v for g, v in active if g == "F"), reverse=True)
    dfn = sorted((v for g, v in active if g == "D"), reverse=True)
    gk = sorted((v for g, v in active if g == "G"), reverse=True)
    rest = sorted(fwd[9:] + dfn[5:], reverse=True)
    return sum(fwd[:9]) + sum(dfn[:5]) + (rest[0] if rest else 0.0) + sum(gk[:2])


def _active(entries, d, skip=None):
    return [(e["grp"], e["v"][d]) for e in entries if e["join"] <= d < e["leave"] and e is not skip]


def _droppable(entries, t, x_group):
    cur = [e for e in entries if e["leave"] == INF and e["join"] <= t
           and (e["p"]["inj"] in A.BAD_INJURY or (e["p"]["out"] or 0) < (PROTECT_GOALIE if e["grp"] == "G" else PROTECT_SKATER))]
    picks = (("G", 3), ("F", 2)) if x_group == "G" else (("F", 6), ("D", 4))
    out = []
    for g, k in picks:
        out += sorted((e for e in cur if e["grp"] == g), key=lambda e: sum(e["v"][t:]))[:k]
    return out


def _brief(p):
    return {"id": p["id"], "n": p["n"], "pos": p["pos"], "tm": p["tm"]}


def plan_moves(mine, fas, game, ndays, days, standings, starters, moves_left):
    entries = [{"p": p, "v": values(p, game, ndays, standings, starters, lineup_goalie=(p["grp"] == "G" and p["slot"] == "G")),
                "grp": p["grp"], "join": 0, "leave": INF}
               for p in mine if p["slot"] != "IR"]
    sk = [{"p": p, "v": values(p, game, ndays, standings, starters), "grp": p["grp"], "used": False,
           "waiver": p.get("st") == "WAIVERS"} for p in fas if p["grp"] != "G"]
    gk = [{"p": p, "v": values(p, game, ndays, standings, starters), "grp": "G", "used": False,
           "waiver": p.get("st") == "WAIVERS"} for p in fas if p["grp"] == "G" and (p.get("sp") or 0) >= 0.3]
    pool = sorted(sk, key=lambda x: -sum(x["v"]))[:SKATER_POOL] + sorted(gk, key=lambda x: -sum(x["v"]))[:GOALIE_POOL]
    pool = [x for x in pool if sum(x["v"]) > 0]

    base_days = [day_value(_active(entries, d)) for d in range(ndays)]
    start_total = sum(base_days)
    moves = []
    for _ in range(moves_left):
        best = None
        for x in pool:
            if x["used"]:
                continue
            for t in range(ndays):
                if x["v"][t] <= 0 or (x["waiver"] and t == 0):
                    continue
                for y in _droppable(entries, t, x["grp"]):
                    gain = 0.0
                    for d in range(t, ndays):
                        act = _active(entries, d, skip=y)
                        act.append((x["grp"], x["v"][d]))
                        gain += day_value(act) - base_days[d]
                    if best is None or gain > best[0]:
                        best = (gain, x, t, y)
        if best is None or best[0] < MIN_GAIN:
            break
        gain, x, t, y = best
        y["leave"] = t
        entries.append({"p": x["p"], "v": x["v"], "grp": x["grp"], "join": t, "leave": INF})
        x["used"] = True
        base_days = [day_value(_active(entries, d)) for d in range(ndays)]
        moves.append({"t": t, "day": days[t], "add": _brief(x["p"]), "drop": _brief(y["p"]),
                      "gain": round(gain, 2), "games": sum(1 for i in range(t, ndays) if x["v"][i] > 0),
                      "waiver": x["waiver"]})
    return {"base": round(start_total, 1), "total": round(sum(base_days), 1),
            "gain": round(sum(base_days) - start_total, 1), "moves": moves}


def stream_rows(fas, game, ndays, standings, abbr_games_left):
    """Best free-agent forwards and defensemen for each day."""
    rows = []
    pool = [p for p in fas if p["grp"] != "G" and p["inj"] not in A.BAD_INJURY]
    pool = sorted(pool, key=lambda p: -(p["out"] or 0))[:80]
    for i in range(ndays):
        day = []
        for p in pool:
            g = game(p["tm"], i)
            if not g:
                continue
            opp, home = g
            m, tag = _mult(p["tm"], opp, home, standings)
            fac = 1.0 if p["inj"] in ("ACTIVE", None) else DTD
            day.append({"i": i, "id": p["id"], "n": p["n"], "pos": p["pos"], "grp": p["grp"], "tm": p["tm"],
                        "o": opp, "h": 1 if home else 0, "tag": tag, "e": round((p["out"] or 0) * m * fac, 2),
                        "gl": abbr_games_left(p["tm"], i), "w": 1 if p.get("st") == "WAIVERS" else 0})
        for grp, k in (("F", ROWS_F), ("D", ROWS_D)):
            rows += sorted((r for r in day if r["grp"] == grp), key=lambda r: -r["e"])[:k]
    return rows


def build(cfg, data, league, standings, now_ms, site_data):
    sp = data["roster"].get("scoringPeriodId", 1)
    abbr, games = D.schedule_maps(data["schedules"])
    m = site_data.get("matchup")
    ndays = max(1, min(int(m["days_left"]) if m else 7, 7))
    game = make_game_fn(abbr, games, sp, now_ms)
    starters = S.STATE["by_team"]
    today = datetime.fromtimestamp(now_ms / 1000, D.et_zone()).date()
    days = [(today + timedelta(days=i)).strftime("%a %b %d").replace(" 0", " ") for i in range(ndays)]
    used = PL._moves_used(league, cfg["team"])
    moves_left = max(0, PL.MOVE_LIMIT - (used or 0))

    def games_left(tm, i):
        return sum(1 for j in range(i, ndays) if game(tm, j))

    plan = plan_moves(site_data["mine"], site_data["fas"], game, ndays, days, standings, starters, moves_left)
    plan["moves_left"] = moves_left
    plan["used_known"] = used is not None
    return {"days": days, "rows": stream_rows(site_data["fas"], game, ndays, standings, games_left), "plan": plan}


# ---------------------------------------------------------------------------
# Website patches (exact-match, all-or-nothing)
# ---------------------------------------------------------------------------
STREAMS_JS = r"""
var ST={pos:'All'};
function streamsRender(){
  var S=D.streams,h='';
  if(!S){$('#t-streams').innerHTML='<div class="card">Streaming data is not available right now.</div>';return;}
  var pl=S.plan;
  h+='<div class="card"><h2>Best use of your moves this week</h2>';
  if(!pl.moves.length)h+='<div class="muted">No add is worth a move right now ('+pl.moves_left+' moves left). Your lineup already beats everything available.</div>';
  else{
    h+='<div><span class="big">+'+f(pl.gain,1)+'</span> <span class="muted">projected points from '+pl.moves.length+' of your '+pl.moves_left+' remaining moves (about '+f(pl.base,0)+' to '+f(pl.total,0)+' for the rest of the matchup)</span></div>';
    pl.moves.forEach(function(m,i){
      h+='<div class="step"><div class="num">'+(i+1)+'</div><div><div><b>'+esc(m.day)+'</b>: add <a class="pl" data-id="'+m.add.id+'">'+esc(m.add.n)+'</a> <span class="muted">('+esc(m.add.pos)+', '+esc(m.add.tm)+', '+m.games+' game'+(m.games===1?'':'s')+' left)</span>'+(m.waiver?' <span class="warn">on waivers, claim the day before</span>':'')+'</div>'
      +'<div>drop <a class="pl" data-id="'+m.drop.id+'">'+esc(m.drop.n)+'</a> <span class="muted">('+esc(m.drop.pos)+', '+esc(m.drop.tm)+')</span> &middot; <span class="good">'+sgn(m.gain,1)+' pts</span></div></div></div>';});
  }
  h+='<div class="muted" style="margin-top:8px">The plan checks every free agent on every remaining day against every player you could drop, then picks moves one at a time that add the most points to your best daily lineup. It accounts for how many games each team plays and how tough the opponents are, and stops when a move is not worth it. Your best players (outlook 1.9 or higher) are never suggested as drops. '+(pl.used_known?'':'ESPN did not report your adds used, so it assumes none. ')+'Later steps assume the earlier ones were made.</div></div>';
  h+='<div class="card"><h2>Best skater streams by day</h2><div class="controls"><span id="stPos"></span></div><div class="chips">';
  S.days.forEach(function(d,i){
    var list=S.rows.filter(function(r){return r.i===i&&(ST.pos==='All'||r.grp===ST.pos);}).sort(function(a,b){return b.e-a.e;}).slice(0,ST.pos==='All'?8:6);
    h+='<div class="chip" style="min-width:270px"><div class="d">'+esc(d)+'</div>';
    if(!list.length)h+='<div class="m muted">No games</div>';
    list.forEach(function(r){
      h+='<div class="m"><a class="pl" data-id="'+r.id+'">'+esc(r.n)+'</a> <span class="muted">'+esc(r.pos)+' '+esc(r.tm)+'</span> '+(r.h?'vs':'@')+' '+esc(r.o)+' <span class="'+(r.tag==='weak'?'good':(r.tag==='strong'?'warn':'muted'))+'">'+(r.tag==='weak'?'soft':(r.tag==='strong'?'tough':'avg'))+'</span> &middot; <b>'+f(r.e,1)+'</b> &middot; '+r.gl+' gm left'+(r.w?' <span class="warn">(waivers)</span>':'')+'</div>';});
    h+='</div>';});
  h+='</div><div class="muted" style="margin-top:8px">Expected points for that day (outlook adjusted for opponent strength and home ice). Players whose teams play more games this week score higher in the move plan above.</div></div>';
  $('#t-streams').innerHTML=h;
  chips('#stPos',['All','F','D'],ST.pos,function(v){ST.pos=v;streamsRender();});
}

/* ---------- tabs + startup ---------- */"""

JS_PATCHES = [
    (",'league'];", ",'streams','league'];"),
    ("/* ---------- tabs + startup ---------- */", STREAMS_JS.lstrip("\n")),
    ("\nshowTab((location.hash||'').slice(1));", "\nstreamsRender();\nshowTab((location.hash||'').slice(1));"),
]
PAGE_PATCHES = [
    ('<button id="nav-league">League</button>', '<button id="nav-streams">Streams</button><button id="nav-league">League</button>'),
    ('<section id="t-league" style="display:none">', '<section id="t-streams" style="display:none"></section>\n<section id="t-league" style="display:none">'),
]
CSS_PATCHES = [
    (".me td{font-weight:700}",
     ".me td{font-weight:700}.step{display:flex;gap:12px;padding:10px 0;border-top:1px solid var(--line)}"
     ".step .num{background:var(--accent);color:#fff;border-radius:50%;width:26px;height:26px;display:flex;"
     "align-items:center;justify-content:center;font-weight:700;flex:none}"),
]


def patch_all(js, page, css):
    """Apply the script, page and style patches together, or none of them."""
    def one(text, pairs, label):
        for old, new in pairs:
            if text.count(old) != 1:
                print(f"  (streams patch skipped in {label}: '{old[:40]}...' not found once)")
                return text
        for old, new in pairs:
            text = text.replace(old, new)
        return text
    nj, npg, nc = one(js, JS_PATCHES, "page script"), one(page, PAGE_PATCHES, "page layout"), one(css, CSS_PATCHES, "styles")
    if nj != js and npg != page and nc != css:
        return nj, npg, nc, True
    print("  streams tab skipped (page code changed)")
    return js, page, css, False
