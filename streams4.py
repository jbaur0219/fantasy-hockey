#!/usr/bin/env python3
"""
STREAMS v4 (READ-ONLY): a this-week-first move plan.

Built on streams.py / streams2.py / streams3.py. It changes how drops are judged:

  1. Schedule first. A player on a team with far fewer games than the busiest teams this week is a fair drop, even
     on a top line or the first power play (a 2-game week against a tough team is a lost week).
  2. Production over role. A player who is underperforming for his role (scoring well under what his line / PP
     slot normally gives) is a fair drop. Role alone no longer protects anyone.
  3. Still protected: stars, and anyone producing for you (see KEEP_PPG / KEEP_REC in roles.py).
  4. Healthy, producing-ish top-role players can still be dropped, but only for a bigger gain (CORE_GAIN points).
  5. Watch list. Put a name in watchlist.txt (one per line:  Name | why) when you know a role is about to shrink
     (for example a top defenseman just returned from injury). Watch-listed players are fair drops and are
     valued a bit lower this week.
  6. Values blend in recent form (season + last 15 days) so a cold player stops looking like his role average.

It also adds two cards to the Streams tab: "Your roster: who to look at this week" (underperformers, light
schedules, shrinking roles, with better options) and "Best adds for the rest of this week".
"""
from datetime import datetime, timedelta
from pathlib import Path

import analyze as A
import dashboard as D
import enrich as E
import roles as R
import site_builder as SB
import streams as STR
import streams2 as S2
import streams3 as S3

INF = STR.INF

# ---------------------------------------------------------------------------
# Settings you can tune
# ---------------------------------------------------------------------------
MIN_GAIN = 1.0          # a normal move must add this many points, net of what you give up
CORE_GAIN = 2.0         # dropping a healthy top-role player that is not clearly underperforming needs this much
DEPTH_GAIN = 1.5        # dropping a depth player (3rd line, 3rd pair, etc.)
FUTURE_GAMES = 1.5      # games of future value charged for the player you drop (v3 used 3.0)
STAR_OUT = 2.5          # outlook at or above this is never dropped (unless watch-listed or injured)
FORM_WEIGHT = 0.40      # how much recent form (season + last 15 days) is blended into this week's value
MIN_GP = 6              # games needed before anyone is called an underperformer
UNDER_RATIO = 0.88      # underperforming = scoring under 88% of what his role usually gives
LIGHT_GAP = 2           # light week = this many games fewer than the busiest team
WATCH_HAIRCUT = 0.85    # watch-listed players are valued at 85% (less ice time / PP time expected)
MARGINAL_MIN = 0.5
MARGINAL_SHOWN = 5
OPTIONS_PER_PLAYER = 3
WEEK_ADDS_F, WEEK_ADDS_D = 6, 4
CAND_F, CAND_D, CAND_G = 10, 8, 3        # how many drop candidates are tried per move

WATCHLIST_FILE = Path(__file__).with_name("watchlist.txt")
STATE = {"watch": {}, "js_ok": False, "ref": 0}
PREV = {}


# ---------------------------------------------------------------------------
# Watch list
# ---------------------------------------------------------------------------
def _norm(name):
    try:
        return E.norm(name)
    except Exception:
        return " ".join(str(name or "").lower().split())


def load_watchlist():
    """watchlist.txt: one player per line, 'Name | note'. Lines starting with # are ignored."""
    out = {}
    try:
        for line in WATCHLIST_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, _, note = line.partition("|")
            if name.strip():
                out[_norm(name)] = note.strip() or "On your watch list."
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"  watchlist.txt could not be read ({type(e).__name__}: {e})")
    return out


def _watch(p):
    return STATE["watch"].get(_norm(p.get("n")))


# ---------------------------------------------------------------------------
# Form, production and role checks
# ---------------------------------------------------------------------------
def _form(p):
    """Recent scoring per game: average of season and last-15-days when both exist."""
    s, r = p.get("ppg"), p.get("rec")
    if s is not None and r is not None:
        return 0.5 * s + 0.5 * r
    return s if s is not None else r


def eff_out(p):
    """This week's outlook: the normal outlook nudged toward recent form, trimmed for watch-listed players."""
    out = p.get("out") or 0.0
    if p.get("grp") == "G":
        return out
    form = _form(p)
    if form is not None and (p.get("gp") or 0) >= MIN_GP:
        out = (1 - FORM_WEIGHT) * out + FORM_WEIGHT * form
    if _watch(p):
        out *= WATCH_HAIRCUT
    return out


def _with_eff(p):
    if p.get("grp") == "G":
        return p
    q = dict(p)
    q["out"] = eff_out(p)
    return q


def producing(p):
    return (p.get("ppg") or 0) >= R.KEEP_PPG or (p.get("rec") or 0) >= R.KEEP_REC


def underperforming(p):
    """Scoring well under what his role normally gives (or at free-agent level while holding a top role)."""
    if p.get("grp") == "G" or (p.get("gp") or 0) < MIN_GP:
        return False
    form = _form(p)
    if form is None:
        return False
    exp = p.get("rp")
    if exp and form <= UNDER_RATIO * exp:
        return True
    return p.get("cls") == "core" and form <= STR.REPLACEMENT[p["grp"]] + 0.10


def role_risk(p):
    return (p.get("cls") == "watch" or p.get("rl") == "Off lines"
            or (p.get("tr") is not None and p["tr"] <= -2.0))


def light_week(gl, ref):
    return gl <= ref - LIGHT_GAP


def drop_rule(p, gl, ref):
    """(can he be dropped?, net points a move must clear)."""
    if p["inj"] in A.BAD_INJURY:
        return True, MIN_GAIN
    if p["grp"] == "G":
        return (p["slot"] == "BN" and (p["out"] or 0) < STR.PROTECT_GOALIE), MIN_GAIN
    if _watch(p):
        return True, MIN_GAIN
    if (p.get("out") or 0) >= STAR_OUT:
        return False, 0.0
    under = underperforming(p)
    if producing(p) and not under:
        return False, 0.0
    if under or role_risk(p) or light_week(gl, ref):
        return True, MIN_GAIN
    cls = p.get("cls")
    if cls == "streamer":
        return True, MIN_GAIN
    if cls == "core":
        return True, CORE_GAIN
    return True, DEPTH_GAIN


# ---------------------------------------------------------------------------
# Wrapped values / stream rows / slim
# ---------------------------------------------------------------------------
def values4(p, game, ndays, standings, starters, lineup_goalie=False):
    v = PREV["values"](_with_eff(p), game, ndays, standings, starters, lineup_goalie=lineup_goalie)
    if p.get("grp") != "G":
        n = sum(1 for x in v if x > 0)
        p["_gl"] = n                                       # games left this week (used by the drop rules)
        if n > STATE["ref"]:
            STATE["ref"] = n                               # the busiest team's games left so far
    return v


def is_droppable4(p):
    """Same rules as drop_rule, in the one-argument form the other tabs (Game Plan) call."""
    gl = p.get("_gl")
    return drop_rule(p, STATE["ref"] if gl is None else gl, STATE["ref"])[0]


def need4(y):
    p = y["p"]
    gl = p.get("_gl")
    return drop_rule(p, STATE["ref"] if gl is None else gl, STATE["ref"])[1] or MIN_GAIN


def stream_rows4(fas, game, ndays, standings, games_left):
    return PREV["rows"]([_with_eff(p) for p in fas], game, ndays, standings, games_left)


def _slim4(p, standings):
    d = PREV["slim"](p, standings)
    if p.get("role_prior") is not None:
        d["rp"] = SB.r3(p["role_prior"])
    return d


# ---------------------------------------------------------------------------
# The move plan
# ---------------------------------------------------------------------------
def _pen(p):
    if p["inj"] in A.BAD_INJURY:
        return 0.0
    return max(0.0, eff_out(p) - STR.REPLACEMENT[p["grp"]]) * FUTURE_GAMES


def _droppable4(entries, t, x_group):
    cur = [e for e in entries if e["leave"] == INF and e["join"] <= t and e.get("ok")]
    picks = (("G", CAND_G), ("F", 2)) if x_group == "G" else (("F", CAND_F), ("D", CAND_D))
    out = []
    for g, k in picks:
        out += sorted((e for e in cur if e["grp"] == g), key=lambda e: sum(e["v"][t:]))[:k]
    return out


def _candidates4(entries, pool, ndays, base_days):
    for x in pool:
        if x["used"]:
            continue
        for t in range(ndays):
            if x["v"][t] <= 0 or (x["waiver"] and t == 0):
                continue
            for y in _droppable4(entries, t, x["grp"]):
                gain = 0.0
                for d in range(t, ndays):
                    act = STR._active(entries, d, skip=y)
                    act.append((x["grp"], x["v"][d]))
                    gain += STR.day_value(act) - base_days[d]
                pen = _pen(y["p"])
                yield gain - pen, x, t, y, gain, pen


def _drop_reasons(p, gl, ref):
    out = []
    note = _watch(p)
    if note:
        out.append(f"On your watch list: {note}")
    if underperforming(p):
        form, exp = _form(p), p.get("rp")
        txt = f"Producing {form:.2f} pts/game recently"
        if exp:
            txt += f" against about {exp:.2f} for a typical {p.get('rl') or 'player in his role'}"
        out.append(txt + ", so the role is not turning into points.")
    if p["inj"] not in A.BAD_INJURY and light_week(gl, ref):
        out.append(f"Light week: {gl} game{'s' if gl != 1 else ''} left while the busiest teams have {ref}.")
    return out


def _move4(entries, x, t, y, gain, pen, net, ndays, days, game, standings, ref):
    m = S3._move(entries, x, t, y, gain, pen, net, ndays, days, game, standings, y["bar"])
    gl = sum(1 for v in y["v"] if v > 0)
    m["why_drop"] = m["why_drop"] + _drop_reasons(y["p"], gl, ref)
    return m


def plan_moves4(mine, fas, game, ndays, days, standings, starters, moves_left):
    entries = [{"p": p, "v": STR.values(p, game, ndays, standings, starters, lineup_goalie=(p["grp"] == "G" and p["slot"] == "G")),
                "grp": p["grp"], "join": 0, "leave": INF} for p in mine if p["slot"] != "IR"]
    pool = [{"p": p, "v": STR.values(p, game, ndays, standings, starters), "grp": p["grp"], "used": False,
             "waiver": p.get("st") == "WAIVERS"} for p in fas if S2.add_ok(p)]
    sk = sorted((x for x in pool if x["grp"] != "G"), key=lambda x: -sum(x["v"]))[:STR.SKATER_POOL]
    gk = sorted((x for x in pool if x["grp"] == "G"), key=lambda x: -sum(x["v"]))[:STR.GOALIE_POOL]
    pool = [x for x in sk + gk if sum(x["v"]) > 0]

    ref = max([STATE["ref"]] + [sum(1 for v in e["v"] if v > 0) for e in entries + pool if e["grp"] != "G"])
    for e in entries:
        gl = sum(1 for v in e["v"] if v > 0)
        e["ok"], e["bar"] = drop_rule(e["p"], gl, ref)

    base_days = [STR.day_value(STR._active(entries, d)) for d in range(ndays)]
    start_total = sum(base_days)
    moves, marginal = [], []

    def margin_list(cands):
        out, seen_x, seen_y = [], set(), set()
        for net, x, t, y, gain, pen in sorted(cands, key=lambda c: -c[0]):
            if net < MARGINAL_MIN or net >= y["bar"]:
                continue
            if x["p"]["id"] in seen_x or y["p"]["id"] in seen_y:
                continue
            seen_x.add(x["p"]["id"])
            seen_y.add(y["p"]["id"])
            out.append((net, x, t, y, gain, pen))
            if len(out) >= MARGINAL_SHOWN:
                break
        return out

    def as_marginal(cands):
        return [_move4(entries, x, t, y, gain, pen, net, ndays, days, game, standings, ref)
                for net, x, t, y, gain, pen in margin_list(cands)]

    for _ in range(moves_left):
        cands = list(_candidates4(entries, pool, ndays, base_days))
        qualifying = [c for c in cands if c[0] >= c[3]["bar"]]
        if not qualifying:
            marginal = as_marginal(cands)
            break
        net, x, t, y, gain, pen = max(qualifying, key=lambda c: c[0])
        moves.append(_move4(entries, x, t, y, gain, pen, net, ndays, days, game, standings, ref))
        y["leave"] = t
        entries.append({"p": x["p"], "v": x["v"], "grp": x["grp"], "join": t, "leave": INF, "ok": False, "bar": MIN_GAIN})
        x["used"] = True
        base_days = [STR.day_value(STR._active(entries, d)) for d in range(ndays)]
    else:                                                  # used every move: still show what would be next
        marginal = as_marginal(list(_candidates4(entries, pool, ndays, base_days)))
    return {"base": round(start_total, 1), "total": round(sum(base_days), 1),
            "gain": round(sum(base_days) - start_total, 1), "moves": moves, "marginal": marginal}


# ---------------------------------------------------------------------------
# Roster audit and best adds for the week
# ---------------------------------------------------------------------------
def _week_total(p, game, ndays, standings, starters):
    v = STR.values(p, game, ndays, standings, starters)
    return sum(v), sum(1 for x in v if x > 0)


def audit4(site_data, game, ndays, days, standings, starters):
    mine = [p for p in site_data["mine"] if p["grp"] != "G" and p["slot"] != "IR" and p["inj"] not in A.BAD_INJURY]
    fas = [p for p in site_data["fas"] if p["grp"] != "G" and S2.add_ok(p)]
    tot = {}
    for p in mine + fas:
        tot[p["id"]] = _week_total(p, game, ndays, standings, starters)
    ref = max([g for _, g in tot.values()] or [0])
    options = {g: sorted((p for p in fas if p["grp"] == g), key=lambda p: -tot[p["id"]][0]) for g in ("F", "D")}

    out = []
    for p in mine:
        e, gl = tot[p["id"]]
        tags, why, sev = [], [], 0
        note = _watch(p)
        under = underperforming(p)
        stars = (p.get("out") or 0) >= STAR_OUT
        if note:
            tags.append({"k": "role", "t": "Watch list"})
            why.append(note)
            sev += 3
        if under and not stars:
            tags.append({"k": "under", "t": "Underperforming"})
            form, exp = _form(p), p.get("rp")
            txt = f"Scoring {form:.2f} pts/game"
            if p.get("ppg") is not None and p.get("rec") is not None:
                txt += f" (season {p['ppg']:.2f}, last 15 days {p['rec']:.2f})"
            if exp:
                txt += f" against about {exp:.2f} for a typical {p.get('rl') or 'player in his role'}"
            why.append(txt + ".")
            sev += 3
        if role_risk(p) and not note:
            tags.append({"k": "role", "t": "Role at risk"})
            if p.get("rl") == "Off lines":
                why.append("Not on his team's current line combinations (scratched, injured or demoted).")
            elif p.get("tr") is not None and p.get("toi5") is not None:
                why.append(f"Ice time {p['toi5']:.1f} min over his last 5 games ({p['tr']:+.1f} vs his season average).")
            sev += 2
        if light_week(gl, ref) and not stars and not (producing(p) and not under):
            tags.append({"k": "light", "t": f"{gl} game{'s' if gl != 1 else ''} left"})
            opps = S2._opps(p, 0, ndays, days, game, standings)
            why.append(f"Light week: {gl} game{'s' if gl != 1 else ''} left{(' (' + opps + ')') if opps else ''}; the busiest teams have {ref}.")
            sev += 2
        if p.get("cls") == "streamer" and not tags:
            tags.append({"k": "streamer", "t": "Replaceable role"})
            why.append(f"{p.get('rl')}: {S2._role_text(p)}.")
            sev += 1
        if not tags:
            continue
        if p.get("rl") and not any(p.get("rl") in w for w in why):
            why.insert(0, f"{p.get('rl')}: {S2._role_text(p)}.")
        repl = []
        for q in options[p["grp"]]:
            if len(repl) >= OPTIONS_PER_PLAYER:
                break
            qe, qg = tot[q["id"]]
            if qe > e + 0.5 and q["tm"] != p["tm"]:
                repl.append({"id": q["id"], "n": q["n"], "rl": q.get("rl"), "tm": q["tm"], "gl": qg, "e": round(qe, 1)})
        out.append({"id": p["id"], "n": p["n"], "pos": p["pos"], "tm": p["tm"], "slot": p["slot"], "rl": p.get("rl"),
                    "tags": tags, "why": why, "repl": repl, "sev": sev, "e": round(e, 1), "gl": gl})
    out.sort(key=lambda a: (-a["sev"], a["e"]))
    return out[:10]


def week_adds(site_data, game, ndays, days, standings, starters):
    fas = [p for p in site_data["fas"] if p["grp"] != "G" and S2.add_ok(p)]
    rows = []
    for g, k in (("F", WEEK_ADDS_F), ("D", WEEK_ADDS_D)):
        scored = []
        for p in fas:
            if p["grp"] != g:
                continue
            e, gl = _week_total(p, game, ndays, standings, starters)
            if gl:
                scored.append((e, gl, p))
        for e, gl, p in sorted(scored, key=lambda s: -s[0])[:k]:
            rows.append({"id": p["id"], "n": p["n"], "pos": p["pos"], "grp": g, "tm": p["tm"], "rl": p.get("rl"),
                         "e": round(e, 1), "gl": gl, "w": 1 if p.get("st") == "WAIVERS" else 0,
                         "opps": S2._opps(p, 0, ndays, days, game, standings)})
    return rows


def whatif_data(site_data, game, ndays, days, standings, starters):
    """Everything the page needs to try 'add this free agent, drop that player' and re-score your daily lineups."""
    def rec(p, mine):
        v = STR.values(p, game, ndays, standings, starters, lineup_goalie=(mine and p["grp"] == "G" and p["slot"] == "G"))
        d = {"id": p["id"], "n": p["n"], "pos": p["pos"], "tm": p["tm"], "grp": p["grp"], "slot": p["slot"],
             "rl": p.get("rl"), "cls": p.get("cls"), "out": round(eff_out(p), 2), "ppg": p.get("ppg"), "rec": p.get("rec"),
             "rp": p.get("rp"), "tr": p.get("tr"), "gp": p.get("gp"), "st": p.get("st"),
             "gl": sum(1 for x in v if x > 0), "e": round(sum(v), 1), "v": [round(x, 2) for x in v],
             "inj": p.get("inj")}
        d["o"] = S2._opps(p, 0, ndays, days, game, standings)
        return d
    mine = [rec(p, True) for p in site_data["mine"] if p["slot"] != "IR"]
    fa_sk = sorted((p for p in site_data["fas"] if p["grp"] != "G" and p["inj"] not in A.BAD_INJURY),
                   key=lambda p: -(p.get("out") or 0))[:250]
    fa_g = sorted((p for p in site_data["fas"] if p["grp"] == "G" and p["inj"] not in A.BAD_INJURY),
                  key=lambda p: -(p.get("sp") or 0))[:20]
    return {"days": [x.split()[0] for x in days], "mine": mine, "fas": [rec(p, False) for p in fa_sk + fa_g]}


def _build4(cfg, data, league, standings, now_ms, site_data):
    d = PREV["build"](cfg, data, league, standings, now_ms, site_data)
    if not STATE["js_ok"]:
        return d                                           # page patch did not apply: keep the earlier cards
    try:
        sp = data["roster"].get("scoringPeriodId", 1)
        abbr, games = D.schedule_maps(data["schedules"])
        m = site_data.get("matchup")
        ndays = max(1, min(int(m["days_left"]) if m else 7, 7))
        game = STR.make_game_fn(abbr, games, sp, now_ms)
        today = datetime.fromtimestamp(now_ms / 1000, D.et_zone()).date()
        days = [(today + timedelta(days=i)).strftime("%a %b %d").replace(" 0", " ") for i in range(ndays)]
        starters = STR.S.STATE["by_team"]
        d["audit"] = audit4(site_data, game, ndays, days, standings, starters)
        d["week"] = week_adds(site_data, game, ndays, days, standings, starters)
        d["whatif"] = whatif_data(site_data, game, ndays, days, standings, starters)
    except Exception as e:
        print(f"  streams v4 cards failed ({type(e).__name__}: {e})")
    return d


def install():
    STATE["watch"] = load_watchlist()
    PREV["values"], PREV["rows"], PREV["build"], PREV["slim"] = STR.values, STR.stream_rows, STR.build, SB.slim
    STR.values = values4
    STR.stream_rows = stream_rows4
    STR.plan_moves = plan_moves4
    S2.plan_moves = plan_moves4
    STR.build = _build4
    SB.slim = _slim4
    S2.is_droppable = is_droppable4                        # the Game Plan tab uses these too
    S3.need = need4
    print(f"  streams v4: this-week-first drops on, {len(STATE['watch'])} on the watch list")


# ---------------------------------------------------------------------------
# Page patches (exact-match, all-or-nothing)
# ---------------------------------------------------------------------------
NEW_NOTE = ("Stars and anyone producing for you are never suggested as drops. Players who are underperforming for their "
            "role, have a light schedule this week, or are on your watch list can be dropped for a normal gain (1+ point "
            "after allowing for what you give up). Healthy top-role players can be dropped only for a bigger gain (2+ points). "
            "Every forward or defenseman added must be on a top-six line, top-four pair or first power-play unit. "
            "Options below the bar are listed separately as marginal. ")

V4_JS = r"""
var WI={add:'',drop:'',day:0};
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
  var s='<div style="margin-top:6px"><b>'+label+':</b> <a class="pl" data-id="'+p.id+'">'+esc(p.n)+'</a> <span class="muted">('+esc(p.pos)+', '+esc(p.tm)+(p.rl?', '+esc(p.rl):'')+')</span><div class="why">'
    +p.gl+' game'+(p.gl===1?'':'s')+' left'+(p.o?' ('+esc(p.o)+')':'')+' &middot; about '+f(p.e,1)+' pts this week &middot; outlook '+f(p.out,2)+' per game';
  if(p.ppg!=null)s+=' &middot; scoring '+f(p.ppg,2)+' this season'+(p.rec!=null?', '+f(p.rec,2)+' last 15 days':'');
  if(p.rp)s+=' &middot; typical for his role: '+f(p.rp,2);
  return s+'</div></div>';
}
function wiResult(){
  var W=(D.streams&&D.streams.whatif)||null;
  if(!W)return '';
  var a=wiFind(W.fas,WI.add),d=wiFind(W.mine,WI.drop);
  if(!a||!d)return '<div class="muted" style="margin-top:8px">Pick a free agent to add and one of your players to drop.</div>';
  var n=W.days.length,st=Math.min(WI.day,n-1),base=0,aft=0,rows='';
  for(var i=0;i<n;i++){
    var act=W.mine.map(function(p){return {g:p.grp,v:p.v[i],id:p.id};});
    var b=wiDay(act);
    var c=wiDay(i>=st?act.filter(function(x){return x.id!==d.id;}).concat([{g:a.grp,v:a.v[i],id:a.id}]):act);
    base+=b;aft+=c;
    rows+='<tr><td>'+esc(W.days[i])+'</td><td>'+f(b,1)+'</td><td>'+(i>=st?f(c,1):'-')+'</td><td>'+(i>=st?sgn(c-b,1):'-')+'</td></tr>';
  }
  var diff=aft-base;
  var h='<div style="margin-top:10px"><span class="big">'+sgn(diff,1)+'</span> <span class="muted">projected points for your lineup over the rest of this week ('+f(base,1)+' to '+f(aft,1)+')</span></div>';
  h+=wiLine(a,'Add')+wiLine(d,'Drop');
  if(a.st==='WAIVERS'&&st===0)h+='<div class="why warn">He is on waivers, so he cannot be added today. Pick a later start day.</div>';
  var v=[];
  if(diff>=1)v.push('This swap helps this week.');
  else if(diff>-1)v.push('This week it is roughly a wash.');
  else v.push('This week it costs you points.');
  if(d.out>a.out+0.15)v.push(esc(d.n)+' is still the better player per game on paper ('+f(d.out,2)+' vs '+f(a.out,2)+'), so any gain here is a this-week gain, not a long-term one.');
  else if(a.out>=d.out)v.push(esc(a.n)+' is at least as good per game, so this is not a step back later either.');
  if(d.rp&&d.ppg!=null&&d.ppg<0.9*d.rp){
    if(d.cls==='watch'||d.rl==='Off lines'||(d.tr!=null&&d.tr<=-2))v.push('Bounce-back looks less likely: his role or ice time is shrinking.');
    else v.push('His role looks intact, so some bounce-back is plausible. If you would rather hold, bench him this week instead of dropping.');
  }
  v.push('Where he was drafted does not change what he scores from here.');
  h+='<ul class="why">'+v.map(function(x){return '<li>'+x+'</li>';}).join('')+'</ul>';
  h+='<div style="overflow-x:auto"><table style="margin-top:6px"><tr><th>Day</th><th>Before</th><th>After</th><th>Change</th></tr>'+rows+'</table></div>';
  return h;
}
function whatifHtml(){
  var W=(D.streams&&D.streams.whatif)||null;
  if(!W)return '';
  var h='<div class="card"><h2>Try a swap</h2><div class="muted">Pick a free agent and one of your players. It re-scores your best daily lineup for the rest of the week with and without the swap. Injured free agents are not listed.</div>';
  h+='<div style="margin-top:8px"><label>Drop <select id="wiDrop"><option value="">choose a player</option>'
    +W.mine.slice().sort(function(x,y){return x.out-y.out;}).map(function(p){return '<option value="'+p.id+'"'+(String(p.id)===String(WI.drop)?' selected':'')+'>'+esc(p.n)+' ('+esc(p.pos)+', '+esc(p.tm)+', '+p.gl+' gm)</option>';}).join('')
    +'</select></label></div>';
  h+='<div style="margin-top:6px"><label>Add <select id="wiAdd"><option value="">choose a free agent</option>'
    +W.fas.map(function(p){return '<option value="'+p.id+'"'+(String(p.id)===String(WI.add)?' selected':'')+'>'+esc(p.n)+' ('+esc(p.pos)+', '+esc(p.tm)+', '+p.gl+' gm)</option>';}).join('')
    +'</select></label></div>';
  h+='<div style="margin-top:6px"><label>Starting <select id="wiDay">'
    +W.days.map(function(x,i){return '<option value="'+i+'"'+(i===WI.day?' selected':'')+'>'+esc(x)+'</option>';}).join('')
    +'</select></label></div>';
  return h+'<div id="wiOut">'+wiResult()+'</div></div>';
}
document.addEventListener('change',function(e){
  var t=e.target;
  if(!t||!t.id||t.id.indexOf('wi')!==0)return;
  if(t.id==='wiAdd')WI.add=t.value;
  if(t.id==='wiDrop')WI.drop=t.value;
  if(t.id==='wiDay')WI.day=parseInt(t.value,10)||0;
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
      h+='<div style="margin-top:6px"><a class="pl" data-id="'+r.id+'">'+esc(r.n)+'</a> <span class="muted">'+esc(r.pos)+' '+esc(r.tm)+(r.rl?' ['+esc(r.rl)+']':'')+'</span> &middot; <b>'+f(r.e,1)+' pts</b> &middot; '+r.gl+' game'+(r.gl===1?'':'s')+(r.w?' <span class="warn">(waivers)</span>':'')+'<div class="why">'+esc(r.opps)+'</div></div>';
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
    +'<div><a class="pl" data-id="'+a.id+'">'+esc(a.n)+'</a> <span class="muted">('+esc(a.pos)+', '+esc(a.tm)+', '+esc(a.slot)+')</span> '+(a.rl?'<b>'+esc(a.rl)+'</b> ':'')
    +a.tags.map(function(t){return '<span class="'+(t.k==='under'||t.k==='role'?'warn':'muted')+'">'+esc(t.t)+'</span>';}).join(' &middot; ')+'</div>'
    +'<ul class="why">'+a.why.map(function(x){return '<li>'+esc(x)+'</li>';}).join('')+'</ul>';
    if(a.repl&&a.repl.length)h+='<div class="why"><b>Better options this week:</b> '+a.repl.map(function(r){return '<a class="pl" data-id="'+r.id+'">'+esc(r.n)+'</a> ('+esc(r.rl||'')+', '+esc(r.tm)+', '+r.gl+' gm, about '+f(r.e,1)+' pts vs '+f(a.e,1)+')';}).join(' &middot; ')+'</div>';
    h+='</div></div>';});
  h+='</div>';
  return h+whatifHtml()+weekHtml();
}
var ST={pos:'All'};"""

JS_PATCHES = [
    ("var ST={pos:'All'};", V4_JS.lstrip("\n")),
    ("h+=auditHtml();", "h+=auditHtml4();"),
]


def patch_all(js):
    for old, _ in JS_PATCHES:
        if js.count(old) != 1:
            print(f"  (streams v4 patch skipped: '{old[:45]}...' not found once)")
            return js, False
    for old, new in JS_PATCHES:
        js = js.replace(old, new)
    if js.count(S3.NEW_NOTE) == 1:                         # the explanatory note: optional
        js = js.replace(S3.NEW_NOTE, NEW_NOTE)
    STATE["js_ok"] = True
    return js, True
