#!/usr/bin/env python3
"""
STREAMS v2 (READ-ONLY): role-aware moves with reasons, plus a core-vs-streamer audit of your roster.

Built on streams.py and roles.py. It changes four things:
  1. Who can be dropped: never a core player (top line / top pair / first power play), never someone producing
     for you, never a player the plan can't justify. Bench depth, replaceable bottom-of-lineup roles, players
     whose role has slipped, and injured players are fair game.
  2. Who can be added: forwards must be on a top-six line or the first power-play unit; defensemen on a
     top-four pair or the first power-play unit. (No third-pair PP2 defensemen for a top-line forward.)
  3. Every suggested move explains itself: role, schedule and opponents, ice-time trend, which lineup slot it
     fills, and what you give up.
  4. A roster audit tags each skater you own and suggests better options for the weak ones.
"""
import analyze as A
import dashboard as D
import roles as R
import site_builder as SB
import streams as STR

INF = STR.INF


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------
def is_droppable(p):
    if p["inj"] in A.BAD_INJURY:
        return True
    if p["grp"] == "G":
        return p["slot"] == "BN" and (p["out"] or 0) < STR.PROTECT_GOALIE
    if (p["out"] or 0) >= STR.PROTECT_SKATER:
        return False
    if (p.get("ppg") or 0) >= R.KEEP_PPG or (p.get("rec") or 0) >= R.KEEP_REC:
        return False                                       # producing for you: keep
    cls = p.get("cls")
    if cls == "core":
        return False
    if cls in ("watch", "streamer"):
        return True
    return p["slot"] == "BN"                               # depth players only if they are on your bench


def add_ok(p):
    if p["inj"] in A.BAD_INJURY:
        return False
    if p["grp"] == "G":
        return (p.get("sp") or 0) >= 0.3
    if not R.STATE["ok"]:
        return True                                        # no line data at all: don't block everything
    if p.get("rl") in (None, "Off lines"):
        return False
    return R.is_top(p["grp"], p.get("ev"), p.get("ppu") or 0)


def _droppable(entries, t, x_group):
    cur = [e for e in entries if e["leave"] == INF and e["join"] <= t and is_droppable(e["p"])]
    picks = (("G", 3), ("F", 2)) if x_group == "G" else (("F", 6), ("D", 5))
    out = []
    for g, k in picks:
        out += sorted((e for e in cur if e["grp"] == g), key=lambda e: sum(e["v"][t:]))[:k]
    return out


# ---------------------------------------------------------------------------
# Reasons
# ---------------------------------------------------------------------------
def _role_text(p):
    if p["grp"] == "G":
        return {"G1": "starting goalie", "G2": "backup goalie"}.get(p.get("rl"), "goalie")
    if p.get("rl") == "Off lines":
        return "not on his team's current lines"
    return R.phrase(p.get("ev"), p.get("ppu") or 0)


def _opps(p, t, ndays, days, game, standings):
    parts = []
    for i in range(t, ndays):
        g = game(p["tm"], i)
        if g:
            opp, home = g
            _, tag = STR._mult(p["tm"], opp, home, standings)
            parts.append(f"{days[i].split()[0]} {'vs' if home else '@'} {opp} ({tag})")
    return ", ".join(parts)


def _fill(entries, x, y, t, ndays):
    slots = {"F": 9, "D": 5, "G": 2}[x["grp"]]
    play = fill = 0
    for d in range(t, ndays):
        if x["v"][d] <= 0:
            continue
        play += 1
        n = sum(1 for e in entries if e["join"] <= d < e["leave"] and e["grp"] == x["grp"] and e["v"][d] > 0)
        if y["grp"] == x["grp"] and y["v"][d] > 0:
            n -= 1                                          # y is leaving
        if n < slots:
            fill += 1
    return play, fill


def _why_add(x, entries, y, t, ndays, days, game, standings):
    p = x["p"]
    games = sum(1 for i in range(t, ndays) if x["v"][i] > 0)
    if p["grp"] == "G":
        out = [f"{p['n']} ({p['tm']}) starts about {int(round((p.get('sp') or 0) * 100))}% of his team's games."]
    else:
        out = [f"{p['n']} is on the {_role_text(p)} for {p['tm']} ({p.get('rl') or 'role unknown'})."]
        if y["p"]["inj"] not in A.BAD_INJURY and y["p"].get("rl"):
            out.append(f"Role change: {y['p']['rl']} out, {p.get('rl') or 'role unknown'} in.")
    out.append(f"{games} game{'s' if games != 1 else ''} left this week: {_opps(p, t, ndays, days, game, standings)}.")
    if p.get("tr") is not None and p.get("toi5") is not None:
        out.append(f"Ice time is {p['toi5']:.1f} min over his last 5 games ({p['tr']:+.1f} vs his season average).")
    play, fill = _fill(entries, x, y, t, ndays)
    if fill:
        out.append(f"Fills an empty {x['grp']} lineup slot on {fill} of the {play} days he plays.")
    else:
        out.append(f"Upgrades a {x['grp']} lineup spot you already fill (no empty slot).")
    return out


def _why_drop(y, t, ndays, penalty, game):
    p = y["p"]
    gl = sum(1 for i in range(t, ndays) if y["v"][i] > 0)
    out = []
    if p["inj"] in A.BAD_INJURY:
        out.append(f"{p['n']} is listed {p['inj'].replace('_', ' ').lower()}, so he is not scoring for you.")
    else:
        where = "on your bench" if p["slot"] == "BN" else f"in your {p['slot']} slot"
        out.append(f"{p['n']} ({p.get('rl') or 'role unknown'}, {_role_text(p)}), currently {where}.")
        if p.get("ppg") is not None:
            out.append(f"Scoring {p['ppg']:.2f} pts/game this season" + (f" ({p['rec']:.2f} over the last 15 days)" if p.get("rec") is not None else "") + ".")
        if p.get("tr") is not None and p["tr"] <= -1.5:
            out.append(f"Ice time down {abs(p['tr']):.1f} min over the last 5 games.")
    if p["inj"] not in A.BAD_INJURY:
        out.append(f"Only {gl} game{'s' if gl != 1 else ''} left this week." if gl <= 2 else f"{gl} games left this week.")
    if penalty > 0.05:
        out.append(f"Dropping him costs about {penalty:.1f} points of future value, already deducted.")
    return out


# ---------------------------------------------------------------------------
# The move plan
# ---------------------------------------------------------------------------
def plan_moves(mine, fas, game, ndays, days, standings, starters, moves_left):
    entries = [{"p": p, "v": STR.values(p, game, ndays, standings, starters, lineup_goalie=(p["grp"] == "G" and p["slot"] == "G")),
                "grp": p["grp"], "join": 0, "leave": INF} for p in mine if p["slot"] != "IR"]
    pool = []
    for p in fas:
        if add_ok(p):
            pool.append({"p": p, "v": STR.values(p, game, ndays, standings, starters), "grp": p["grp"], "used": False,
                         "waiver": p.get("st") == "WAIVERS"})
    sk = sorted((x for x in pool if x["grp"] != "G"), key=lambda x: -sum(x["v"]))[:STR.SKATER_POOL]
    gk = sorted((x for x in pool if x["grp"] == "G"), key=lambda x: -sum(x["v"]))[:STR.GOALIE_POOL]
    pool = [x for x in sk + gk if sum(x["v"]) > 0]

    base_days = [STR.day_value(STR._active(entries, d)) for d in range(ndays)]
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
                        act = STR._active(entries, d, skip=y)
                        act.append((x["grp"], x["v"][d]))
                        gain += STR.day_value(act) - base_days[d]
                    pen = 0.0 if y["p"]["inj"] in A.BAD_INJURY else \
                        max(0.0, (y["p"]["out"] or 0) - STR.REPLACEMENT[y["grp"]]) * STR.FUTURE_GAMES
                    net = gain - pen
                    if best is None or net > best[0]:
                        best = (net, x, t, y, gain, pen)
        if best is None or best[0] < STR.MIN_GAIN:
            break
        net, x, t, y, gain, pen = best
        why_add = _why_add(x, entries, y, t, ndays, days, game, standings)
        why_drop = _why_drop(y, t, ndays, pen, game)
        y["leave"] = t
        entries.append({"p": x["p"], "v": x["v"], "grp": x["grp"], "join": t, "leave": INF})
        x["used"] = True
        base_days = [STR.day_value(STR._active(entries, d)) for d in range(ndays)]
        moves.append({"t": t, "day": days[t], "add": STR._brief(x["p"]), "drop": STR._brief(y["p"]),
                      "gain": round(gain, 2), "net": round(net, 2),
                      "games": sum(1 for i in range(t, ndays) if x["v"][i] > 0), "waiver": x["waiver"],
                      "why_add": why_add, "why_drop": why_drop})
    return {"base": round(start_total, 1), "total": round(sum(base_days), 1),
            "gain": round(sum(base_days) - start_total, 1), "moves": moves}


# ---------------------------------------------------------------------------
# Stream rows and the roster audit
# ---------------------------------------------------------------------------
def stream_rows(fas, game, ndays, standings, games_left):
    rows = []
    pool = sorted((p for p in fas if p["grp"] != "G" and add_ok(p)), key=lambda p: -(p["out"] or 0))[:80]
    for i in range(ndays):
        day = []
        for p in pool:
            g = game(p["tm"], i)
            if not g:
                continue
            opp, home = g
            m, tag = STR._mult(p["tm"], opp, home, standings)
            fac = 1.0 if p["inj"] in ("ACTIVE", None) else STR.DTD
            day.append({"i": i, "id": p["id"], "n": p["n"], "pos": p["pos"], "grp": p["grp"], "tm": p["tm"],
                        "o": opp, "h": 1 if home else 0, "tag": tag, "e": round((p["out"] or 0) * m * fac, 2),
                        "gl": games_left(p["tm"], i), "w": 1 if p.get("st") == "WAIVERS" else 0, "rl": p.get("rl")})
        for grp, k in (("F", STR.ROWS_F), ("D", STR.ROWS_D)):
            rows += sorted((r for r in day if r["grp"] == grp), key=lambda r: -r["e"])[:k]
    return rows


def audit(site_data, game, ndays, standings, starters, games_left):
    mine = [p for p in site_data["mine"] if p["grp"] != "G" and p["slot"] != "IR" and p.get("cls") in ("watch", "streamer")]
    cand = {}
    for g in ("F", "D"):
        scored = sorted(((sum(STR.values(p, game, ndays, standings, starters)), p)
                         for p in site_data["fas"] if p["grp"] == g and add_ok(p)), key=lambda s: -s[0])
        cand[g] = scored[:2]
    out = []
    for p in sorted(mine, key=lambda p: (p["cls"] != "watch", p["out"] or 0)):
        why = []
        if p.get("rl") == "Off lines":
            why.append("Not on his team's current line combinations (scratched, injured or demoted).")
        else:
            why.append(f"{p.get('rl')}: {_role_text(p)}.")
        if p.get("tr") is not None and abs(p["tr"]) >= 1.5 and p.get("toi5") is not None:
            why.append(f"Ice time {p['toi5']:.1f} min over his last 5 games ({p['tr']:+.1f} vs season).")
        if p.get("ppg") is not None:
            why.append(f"Scoring {p['ppg']:.2f} pts/game this season" + (f", {p['rec']:.2f} over the last 15 days" if p.get("rec") is not None else "") + ".")
        if p["cls"] == "streamer":
            why.append("Replaceable: a first-unit player on a team with games would likely score more.")
        out.append({"id": p["id"], "n": p["n"], "pos": p["pos"], "tm": p["tm"], "slot": p["slot"], "rl": p.get("rl"),
                    "cls": p["cls"], "why": why,
                    "repl": [{"id": q["id"], "n": q["n"], "rl": q.get("rl"), "tm": q["tm"], "gl": games_left(q["tm"], 0),
                              "e": round(s, 1)} for s, q in cand[p["grp"]]]})
    return out


# ---------------------------------------------------------------------------
# Installing + page patches
# ---------------------------------------------------------------------------
_orig_build = STR.build
PREV = {}


def _build(cfg, data, league, standings, now_ms, site_data):
    d = _orig_build(cfg, data, league, standings, now_ms, site_data)
    try:
        sp = data["roster"].get("scoringPeriodId", 1)
        abbr, games = D.schedule_maps(data["schedules"])
        m = site_data.get("matchup")
        ndays = max(1, min(int(m["days_left"]) if m else 7, 7))
        game = STR.make_game_fn(abbr, games, sp, now_ms)
        gl = lambda tm, i: sum(1 for j in range(i, ndays) if game(tm, j))
        d["audit"] = audit(site_data, game, ndays, standings, STR.S.STATE["by_team"], gl)
    except Exception as e:
        print(f"  roster audit failed ({type(e).__name__}: {e})")
        d["audit"] = []
    return d


def _slim(p, standings):
    d = PREV["slim"](p, standings)
    for k in ("rl", "cls", "ev"):
        if p.get(k) is not None:
            d[k] = p[k]
    for k in ("ppu", "tr", "toi5"):
        if p.get(k) is not None:
            d[k] = SB.r3(p[k])
    return d


def install():
    PREV["slim"] = SB.slim                     # keep whatever extra columns were already added
    STR.plan_moves = plan_moves
    STR.stream_rows = stream_rows
    STR.build = _build
    SB.slim = _slim


V2_JS = r"""
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
    +'<div><a class="pl" data-id="'+a.id+'">'+esc(a.n)+'</a> <span class="muted">('+esc(a.pos)+', '+esc(a.tm)+', '+esc(a.slot)+')</span> <b>'+esc(a.rl)+'</b> <span class="'+(a.cls==='watch'?'warn':'muted')+'">'+(a.cls==='watch'?'watch: role has slipped':'streamer: replaceable role')+'</span></div>'
    +'<ul class="why">'+a.why.map(function(x){return '<li>'+esc(x)+'</li>';}).join('')+'</ul>';
    if(a.repl&&a.repl.length)h+='<div class="why"><b>Better options:</b> '+a.repl.map(function(r){return '<a class="pl" data-id="'+r.id+'">'+esc(r.n)+'</a> ('+esc(r.rl||'')+', '+esc(r.tm)+', '+r.gl+' gm left, about '+f(r.e,1)+' pts this week)';}).join(' &middot; ')+'</div>';
    h+='</div></div>';});
  return h+'</div>';
}
var ST={pos:'All'};"""

JS_PATCHES = [
    ("var ST={pos:'All'};", V2_JS.lstrip("\n")),
    ("&middot; <span class=\"good\">'+sgn(m.gain,1)+' pts</span></div></div></div>';});",
     "&middot; <span class=\"good\">'+sgn(m.gain,1)+' pts</span></div>'+reasonsHtml(m)+'</div></div>';});"),
    ("h+='<div class=\"card\"><h2>Best skater streams by day</h2>", "h+=auditHtml();\n  h+='<div class=\"card\"><h2>Best skater streams by day</h2>"),
    ("<span class=\"muted\">'+esc(r.pos)+' '+esc(r.tm)+'</span> '+(r.h?'vs':'@')",
     "<span class=\"muted\">'+esc(r.pos)+' '+esc(r.tm)+'</span>'+(r.rl?' <span class=\"muted\">['+esc(r.rl)+']</span>':'')+' '+(r.h?'vs':'@')"),
    ("Your best players (outlook 1.9 or higher) are never suggested as drops, and a move must add at least 1.5 points after allowing for what you give up. ",
     "Core players (top line, top pair or first power play) and anyone producing for you are never suggested as drops, every forward or defenseman added must be on a top-six line, top-four pair or first power-play unit, and a move must add at least 1.5 points after allowing for what you give up. "),
    ("var cFlags={", "var cRole={h:'Role',v:function(p){return p.rl||'';},r:function(p){return p.rl?('<span class=\"'+(p.cls==='core'?'good':(p.cls==='watch'?'warn':(p.cls==='streamer'?'muted':'')))+'\">'+esc(p.rl)+'</span>'+(p.cls?' <span class=\"muted\">'+esc(p.cls)+'</span>':'')):'-';}};var cFlags={"),
    ("cG7,cTOI,cPP,cXG,cFlags];", "cG7,cRole,cTOI,cPP,cXG,cFlags];"),
    ("cGP,cG7,cTOI,cPP,cXG,{h:'Owned'", "cGP,cG7,cRole,cTOI,cPP,cXG,{h:'Owned'"),
    ("cell('Games played',p.gp)+", "cell('Games played',p.gp)+(p.rl?cell('Line / PP role',esc(p.rl)):'')+(p.tr!=null?cell('Ice time, last 5 vs season',sgn(p.tr,1)+' min'):'')+"),
]
CSS_PATCHES = [
    (".me td{font-weight:700}", ".me td{font-weight:700}.why{margin:4px 0 0;font-size:13px;color:var(--muted)}.why ul{margin:2px 0 0;padding-left:18px}"),
]


def _apply_group(js, pairs, label):
    for old, _ in pairs:
        if js.count(old) != 1:
            print(f"  (streams v2 {label} skipped: '{old[:45]}...' not found once)")
            return js, False
    for old, new in pairs:
        js = js.replace(old, new)
    return js, True


def patch_all(js, css):
    """Reasons + audit patches are required (all or nothing). The roster 'Role' column is optional and separate."""
    core, columns = JS_PATCHES[:5], JS_PATCHES[5:]
    js, ok = _apply_group(js, core, "reasons and audit")
    if not ok:
        return js, css, False
    if css.count(CSS_PATCHES[0][0]) != 1:
        print("  (streams v2 style patch skipped)")
        return js, css, False
    css = css.replace(*CSS_PATCHES[0])
    js, _ = _apply_group(js, columns, "role column")
    return js, css, True
