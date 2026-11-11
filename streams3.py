#!/usr/bin/env python3
"""
STREAMS v3 (READ-ONLY): two refinements to the role-aware move plan.

  1. Second-tier swaps. First power-play players are never dropped. But a player who is "core" only through his
     line or pair (no PP1 role) can be dropped for a BIG gain (3+ points after what you give up).
  2. Marginal options. Moves that are real but below the bar are listed separately (with reasons) so you can see
     the next-best uses of a spare move.

It also replaces the Overview "Suggested moves" card with a pointer to the Streams tab, so the two never disagree.
"""
import analyze as A
import roles as R
import streams as STR
import streams2 as S2

INF = STR.INF
BIG_GAIN = 3.0          # what a second-tier player's replacement must add (after what you give up)
MARGINAL_MIN = 0.5      # smallest net gain worth listing as a marginal option
MARGINAL_SHOWN = 4


def second_tier(p):
    """Core through his line or pair only: no first power-play role."""
    return p.get("cls") == "core" and (p.get("ppu") or 0) != 1 and p["grp"] != "G"


def is_droppable(p):
    if p["inj"] in A.BAD_INJURY:
        return True
    if p["grp"] == "G":
        return p["slot"] == "BN" and (p["out"] or 0) < STR.PROTECT_GOALIE
    if p.get("ppu") == 1 and p.get("rl") != "Off lines":
        return False                                       # first power-play unit: never
    if (p["out"] or 0) >= STR.PROTECT_SKATER:
        return False                                       # stars: never
    if (p.get("ppg") or 0) >= R.KEEP_PPG or (p.get("rec") or 0) >= R.KEEP_REC:
        return False                                       # producing for you: keep
    cls = p.get("cls")
    if cls in ("watch", "streamer"):
        return True
    if cls == "core":
        return second_tier(p)                              # allowed, but only for a big gain (see need())
    return p["slot"] == "BN"


def need(y):
    """The net gain a move must clear, given who is being dropped."""
    if y["p"]["inj"] in A.BAD_INJURY:
        return STR.MIN_GAIN                                # an injured player costs you nothing to move on from
    return BIG_GAIN if second_tier(y["p"]) else STR.MIN_GAIN


def _candidates(entries, pool, ndays, base_days):
    for x in pool:
        if x["used"]:
            continue
        for t in range(ndays):
            if x["v"][t] <= 0 or (x["waiver"] and t == 0):
                continue
            for y in S2._droppable(entries, t, x["grp"]):
                gain = 0.0
                for d in range(t, ndays):
                    act = STR._active(entries, d, skip=y)
                    act.append((x["grp"], x["v"][d]))
                    gain += STR.day_value(act) - base_days[d]
                pen = 0.0 if y["p"]["inj"] in A.BAD_INJURY else \
                    max(0.0, (y["p"]["out"] or 0) - STR.REPLACEMENT[y["grp"]]) * STR.FUTURE_GAMES
                yield gain - pen, x, t, y, gain, pen


def _move(entries, x, t, y, gain, pen, net, ndays, days, game, standings, bar):
    return {"t": t, "day": days[t], "add": STR._brief(x["p"]), "drop": STR._brief(y["p"]),
            "gain": round(gain, 2), "net": round(net, 2), "need": bar,
            "games": sum(1 for i in range(t, ndays) if x["v"][i] > 0), "waiver": x["waiver"],
            "why_add": S2._why_add(x, entries, y, t, ndays, days, game, standings),
            "why_drop": S2._why_drop(y, t, ndays, pen, game)}


def plan_moves(mine, fas, game, ndays, days, standings, starters, moves_left):
    entries = [{"p": p, "v": STR.values(p, game, ndays, standings, starters, lineup_goalie=(p["grp"] == "G" and p["slot"] == "G")),
                "grp": p["grp"], "join": 0, "leave": INF} for p in mine if p["slot"] != "IR"]
    pool = [{"p": p, "v": STR.values(p, game, ndays, standings, starters), "grp": p["grp"], "used": False,
             "waiver": p.get("st") == "WAIVERS"} for p in fas if S2.add_ok(p)]
    sk = sorted((x for x in pool if x["grp"] != "G"), key=lambda x: -sum(x["v"]))[:STR.SKATER_POOL]
    gk = sorted((x for x in pool if x["grp"] == "G"), key=lambda x: -sum(x["v"]))[:STR.GOALIE_POOL]
    pool = [x for x in sk + gk if sum(x["v"]) > 0]

    base_days = [STR.day_value(STR._active(entries, d)) for d in range(ndays)]
    start_total = sum(base_days)
    moves, marginal = [], []

    def margin_list(cands):
        out, seen_x, seen_y = [], set(), set()
        for net, x, t, y, gain, pen in sorted(cands, key=lambda c: -c[0]):
            if net < MARGINAL_MIN or net >= need(y):
                continue
            if x["p"]["id"] in seen_x or y["p"]["id"] in seen_y:
                continue
            seen_x.add(x["p"]["id"])
            seen_y.add(y["p"]["id"])
            out.append((net, x, t, y, gain, pen))
            if len(out) >= MARGINAL_SHOWN:
                break
        return out

    for _ in range(moves_left):
        cands = list(_candidates(entries, pool, ndays, base_days))
        qualifying = [c for c in cands if c[0] >= need(c[3])]
        if not qualifying:
            marginal = [_move(entries, x, t, y, gain, pen, net, ndays, days, game, standings, need(y))
                        for net, x, t, y, gain, pen in margin_list(cands)]
            break
        net, x, t, y, gain, pen = max(qualifying, key=lambda c: c[0])
        moves.append(_move(entries, x, t, y, gain, pen, net, ndays, days, game, standings, need(y)))
        y["leave"] = t
        entries.append({"p": x["p"], "v": x["v"], "grp": x["grp"], "join": t, "leave": INF})
        x["used"] = True
        base_days = [STR.day_value(STR._active(entries, d)) for d in range(ndays)]
    else:                                                  # used every move: still show what would be next
        cands = list(_candidates(entries, pool, ndays, base_days))
        marginal = [_move(entries, x, t, y, gain, pen, net, ndays, days, game, standings, need(y))
                    for net, x, t, y, gain, pen in margin_list(cands)]
    return {"base": round(start_total, 1), "total": round(sum(base_days), 1),
            "gain": round(sum(base_days) - start_total, 1), "moves": moves, "marginal": marginal}


def install():
    S2.is_droppable = is_droppable
    S2.plan_moves = plan_moves
    STR.plan_moves = plan_moves


# ---------------------------------------------------------------------------
# Page patches (exact-match, all-or-nothing)
# ---------------------------------------------------------------------------
OLD_NOTE = ("Core players (top line, top pair or first power play) and anyone producing for you are never suggested as drops, "
            "every forward or defenseman added must be on a top-six line, top-four pair or first power-play unit, and a move "
            "must add at least 1.5 points after allowing for what you give up. ")
NEW_NOTE = ("First power-play players and anyone producing for you are never suggested as drops. Players who are core only "
            "through their line or pair can be dropped only for a big gain (3+ points). Every forward or defenseman added must "
            "be on a top-six line, top-four pair or first power-play unit, and a normal move must add at least 1.5 points after "
            "allowing for what you give up. Options below the bar are listed separately as marginal. ")
MARGINAL_JS = r"""function marginalHtml(pl){
  var M=pl.marginal||[];
  if(!M.length)return '';
  var h='<div style="margin-top:14px"><b>Marginal options</b> <span class="muted">(real but below the bar; use a spare move only if you want to)</span></div>';
  M.forEach(function(m,i){
    h+='<div class="step"><div class="num" style="background:var(--gray)">'+(i+1)+'</div><div><div><b>'+esc(m.day)+'</b>: add <a class="pl" data-id="'+m.add.id+'">'+esc(m.add.n)+'</a> <span class="muted">('+esc(m.add.pos)+', '+esc(m.add.tm)+', '+m.games+' game'+(m.games===1?'':'s')+' left)</span>'+(m.waiver?' <span class="warn">on waivers, claim the day before</span>':'')+'</div>'
    +'<div>drop <a class="pl" data-id="'+m.drop.id+'">'+esc(m.drop.n)+'</a> <span class="muted">('+esc(m.drop.pos)+', '+esc(m.drop.tm)+') &middot; '+sgn(m.gain,1)+' pts this week, '+sgn(m.net,1)+' after what you give up (bar: '+f(m.need,1)+')</span></div>'+reasonsHtml(m)+'</div></div>';});
  return h;
}
function reasonsHtml(m){"""
JS_PATCHES = [
    ("function reasonsHtml(m){", MARGINAL_JS),
    ("h+='<div class=\"muted\" style=\"margin-top:8px\">The plan checks every free agent",
     "h+=marginalHtml(pl);\n  h+='<div class=\"muted\" style=\"margin-top:8px\">The plan checks every free agent"),
    (OLD_NOTE, NEW_NOTE),
    ("Nothing available clearly beats your weakest players.",
     "The role-aware plan is on the Streams tab. It accounts for lines, power plays, schedules and opponents."),
]


def patch_all(js):
    for old, _ in JS_PATCHES:
        if js.count(old) != 1:
            print(f"  (streams v3 patch skipped: '{old[:45]}...' not found once)")
            return js, False
    for old, new in JS_PATCHES:
        js = js.replace(old, new)
    return js, True
