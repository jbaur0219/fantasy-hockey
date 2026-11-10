#!/usr/bin/env python3
"""
Fantasy Hockey DASHBOARD  (READ-ONLY)

Run:  python3 dashboard.py        ->  writes site/index.html

Shows, at a glance:
  - Your weekly matchup: score so far, projected final, win probability
  - Goalie decisions: win probability + START / BENCH call for each upcoming game
  - Suggested add/drop moves
  - Lineup alerts (injured starters, idle starters, bench players with a game)
  - League standings, your roster, and the best free agents

It never adds, drops, trades, or changes your lineup. It only reads.
Uses analyze.py (same folder) for the player math.
"""
import html
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

import analyze as A

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
HOME_ICE = 0.03          # home-ice edge in win probability
SKATER_SD = 2.3          # typical game-to-game swing for a skater (fantasy points)
GOALIE_SD = 6.0          # typical swing for a goalie start
DEFAULT_TEAM_GP = 19     # used if NHL standings can't be loaded
GOALIE_DAYS = 3          # how many days ahead to show goalie calls
NHL_ABBR = {"NJ": "NJD", "TB": "TBL", "SJ": "SJS", "LA": "LAK"}   # ESPN -> NHL names


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def norm_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def log5(a, b):
    """Chance team A beats team B given their strengths a and b (0-1)."""
    d = a * (1 - b) + b * (1 - a)
    return a * (1 - b) / d if d else 0.5


def et_zone():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")
    except Exception:
        return timezone.utc


def fmt_game(ms):
    d = datetime.fromtimestamp(ms / 1000, et_zone())
    return d.strftime("%a %b %d").replace(" 0", " "), d.strftime("%I:%M %p").lstrip("0")


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def load_nhl_standings():
    """{NHL abbrev: {'pct': points%, 'gp': games}}  -  {} if unavailable."""
    try:
        r = requests.get("https://api-web.nhle.com/v1/standings/now", timeout=20)
        r.raise_for_status()
        rows = r.json().get("standings", [])
    except Exception as e:  # never crash because of the NHL feed
        print(f"(NHL standings unavailable: {e}; using neutral team strength)")
        return {}
    out = {}
    for s in rows:
        ab = (s.get("teamAbbrev") or {}).get("default")
        gp = s.get("gamesPlayed") or 0
        pct = s.get("pointPctg")
        if pct is None and gp:
            pct = (s.get("points") or 0) / (2 * gp)
        if ab and gp and pct is not None:
            out[ab] = {"pct": float(pct), "gp": gp}
    return out


def team_strength(abbrev, standings):
    """0.5 = average team. Built from NHL points %, shifted so the league average is 0.5."""
    if not standings:
        return 0.5
    mean = sum(v["pct"] for v in standings.values()) / len(standings)
    row = standings.get(NHL_ABBR.get(abbrev, abbrev))
    return clamp(0.5 + (row["pct"] - mean), 0.3, 0.7) if row else 0.5


def team_games_played(abbrev, standings):
    row = standings.get(NHL_ABBR.get(abbrev, abbrev))
    return row["gp"] if row else DEFAULT_TEAM_GP


def schedule_maps(schedules):
    abbr, games = {}, {}
    for t in schedules.get("settings", {}).get("proTeams", []):
        abbr[t.get("id")] = t.get("abbrev", "?")
        games[t.get("id")] = t.get("proGamesByScoringPeriod") or {}
    return abbr, games


def games_on(games, team_id, sp, now_ms=None):
    """Games for a pro team on scoring period sp. If now_ms is given, only games not yet started."""
    lst = games.get(team_id, {}).get(str(sp), [])
    if now_ms is not None:
        lst = [g for g in lst if g.get("date", 0) > now_ms]
    return lst


def roster_players(team_json, season, abbr):
    out = []
    for e in team_json.get("roster", {}).get("entries", []):
        p = A.parse_player(e["playerPoolEntry"]["player"], season, slot=e.get("lineupSlotId"))
        p["team"] = abbr.get(p["team_id"], "?")
        out.append(p)
    return out


def team_label(t):
    return t.get("name") or f"{t.get('location', '')} {t.get('nickname', '')}".strip() or f"Team {t.get('id')}"


def record_of(t):
    o = (t.get("record") or {}).get("overall") or {}
    return o.get("wins", 0), o.get("losses", 0), o.get("ties", 0), o.get("pointsFor", 0)


# ---------------------------------------------------------------------------
# Matchup + win probability
# ---------------------------------------------------------------------------
def find_matchup(league, team_id):
    mp = (league.get("status") or {}).get("currentMatchupPeriod")
    for m in league.get("schedule", []):
        if m.get("matchupPeriodId") == mp and team_id in (m["home"].get("teamId"), m["away"].get("teamId")):
            mine, theirs = (m["home"], m["away"]) if m["home"].get("teamId") == team_id else (m["away"], m["home"])
            return mp, m, mine, theirs
    return mp, None, None, None


def matchup_periods(m, mp):
    keys = [int(k) for side in (m["home"], m["away"]) for k in (side.get("pointsByScoringPeriod") or {})]
    start = min(keys) if keys else 7 * (mp - 1)
    return start, start + 6          # weekly matchups run 7 scoring periods


def side_points(side):
    return float(side.get("totalPointsLive", side.get("totalPoints", 0)) or 0)


def start_prob(p, standings):
    """Rough chance a goalie starts a given team game."""
    gp_team = team_games_played(p["team"], standings)
    w = (p["gp"] / gp_team) if p["gp"] else 0.2
    return clamp(w, 0.2, 0.9)


def expected_remaining(players, periods, games, now_ms, standings):
    """Expected points + variance for the rest of the week, using the best lineup each day."""
    mu = var = 0.0
    for sp in periods:
        avail = [p for p in players
                 if A.slot_name(p["slot"]) != "IR" and p["injury"] not in A.BAD_INJURY
                 and games_on(games, p["team_id"], sp, now_ms)]
        gks = sorted(((p["outlook"] * start_prob(p, standings), start_prob(p, standings))
                      for p in avail if p["group"] == "G"), reverse=True)[:2]
        for ev, w in gks:
            mu += ev
            var += w * GOALIE_SD ** 2
        fwd = sorted([p for p in avail if p["group"] == "F"], key=lambda p: -p["outlook"])
        dfn = sorted([p for p in avail if p["group"] == "D"], key=lambda p: -p["outlook"])
        used = fwd[:9] + dfn[:5]
        rest = fwd[9:] + dfn[5:]
        if rest:
            used.append(max(rest, key=lambda p: p["outlook"]))      # UTIL slot
        for p in used:
            mu += p["outlook"]
            var += SKATER_SD ** 2
    return mu, var


# ---------------------------------------------------------------------------
# Goalie decisions
# ---------------------------------------------------------------------------
def goalie_decisions(mine, sp, games, abbr, standings, now_ms):
    out = []
    for p in mine:
        if p["group"] != "G" or A.slot_name(p["slot"]) == "IR":
            continue
        s_me = team_strength(p["team"], standings)
        rows = []
        for d in range(sp, sp + GOALIE_DAYS):
            for g in games_on(games, p["team_id"], d):
                home = g.get("homeProTeamId") == p["team_id"]
                opp_id = g.get("awayProTeamId") if home else g.get("homeProTeamId")
                opp = abbr.get(opp_id, "?")
                pw = log5(s_me, team_strength(opp, standings)) + (HOME_ICE if home else -HOME_ICE)
                if p.get("svp") and p["gp"] >= 5:                 # his own save % nudges the odds
                    pw += clamp((p["svp"] - 0.905) * 2.0, -0.05, 0.05)
                pw = clamp(pw, 0.15, 0.85)
                exp_pts = p["outlook"] + 4 * (pw - s_me)          # opponent/home effect on a win (worth 4)
                started = g.get("date", 0) <= now_ms
                if started:
                    verdict, cls = "GAME STARTED", "done"
                elif exp_pts < 0:
                    verdict, cls = "BENCH", "bench"
                elif exp_pts < 1.0:
                    verdict, cls = "START (RISKY)", "risky"
                else:
                    verdict, cls = "START", "start"
                day, tm = fmt_game(g.get("date", 0))
                rows.append({"day": day, "time": tm, "opp": opp, "home": home, "p": pw,
                             "e": exp_pts, "verdict": verdict, "cls": cls})
        out.append({"p": p, "rows": rows})
    return out


# ---------------------------------------------------------------------------
# Lineup alerts
# ---------------------------------------------------------------------------
def lineup_alerts(mine, sp, games, now_ms):
    alerts = []
    starters = [p for p in mine if A.slot_name(p["slot"]) in ("F", "D", "G", "UTIL")]
    bench = [p for p in mine if A.slot_name(p["slot"]) == "BN"]
    for p in starters:
        if p["injury"] in A.BAD_INJURY:
            alerts.append(("bad", f"{p['name']} is in your lineup but listed {p['injury'].replace('_', ' ').title()}."))
    idle = [p for p in starters if p["injury"] not in A.BAD_INJURY and not games_on(games, p["team_id"], sp)]
    ready = [p for p in bench if p["injury"] not in A.BAD_INJURY and games_on(games, p["team_id"], sp, now_ms)]
    used = set()
    for b in sorted(ready, key=lambda p: -p["outlook"]):
        for s in sorted(idle, key=lambda p: p["outlook"]):
            if id(s) in used:
                continue
            same = (s["group"] == b["group"]) or (A.slot_name(s["slot"]) == "UTIL" and b["group"] != "G")
            if same:
                used.add(id(s))
                alerts.append(("warn", f"Start {b['name']} (has a game today) in place of {s['name']} (no game)."))
                break
    return alerts


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
CSS = """
:root{--bg:#f5f6f8;--card:#fff;--text:#1d2330;--muted:#6a7385;--line:#e4e7ee;--accent:#2563eb;
--green:#16a34a;--amber:#d97706;--red:#dc2626;--gray:#6b7280}
@media (prefers-color-scheme:dark){:root{--bg:#0f1420;--card:#171e2e;--text:#e8ecf5;--muted:#9aa5bd;
--line:#263049;--accent:#60a5fa;--green:#4ade80;--amber:#fbbf24;--red:#f87171;--gray:#9ca3af}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:18px 14px 60px}
h1{font-size:22px;margin:0}.sub{color:var(--muted);font-size:13px;margin:2px 0 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0}
.card h2{font-size:15px;margin:0 0 10px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.vs{display:flex;justify-content:space-between;gap:10px;align-items:flex-end;flex-wrap:wrap}
.team{flex:1;min-width:140px}.team .n{font-weight:600}.team .s{font-size:28px;font-weight:700}
.team .r{color:var(--muted);font-size:13px}.right{text-align:right}
.bar{height:14px;border-radius:8px;background:var(--line);overflow:hidden;margin:12px 0 6px;display:flex}
.bar i{display:block;height:100%}.bar .a{background:var(--accent)}.bar .b{background:var(--gray)}
.big{font-size:30px;font-weight:700}.muted{color:var(--muted);font-size:13px}
.g{border-top:1px solid var(--line);padding:10px 0}.g:first-of-type{border-top:0}
.gh{display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px}.gh b{font-size:16px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
.chip{border:1px solid var(--line);border-radius:10px;padding:8px 10px;min-width:150px;flex:1}
.chip .d{font-size:12px;color:var(--muted)}.chip .o{font-weight:600}.chip .m{font-size:13px}
.pill{display:inline-block;border-radius:999px;padding:2px 10px;font-size:12px;font-weight:700;color:#fff}
.start{background:var(--green)}.risky{background:var(--amber)}.bench{background:var(--red)}.done{background:var(--gray)}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600}.scroll{overflow-x:auto}
.good{color:var(--green);font-weight:600}.warn{color:var(--amber)}.bad{color:var(--red)}
ul{margin:0;padding-left:18px}li{margin:4px 0}details{margin:8px 0}summary{cursor:pointer;font-weight:600;padding:4px 0}
.me td{font-weight:700}
"""


def table(headers, rows, row_class=None):
    h = "".join(f"<th>{html.escape(x)}</th>" for x in headers)
    body = ""
    for i, r in enumerate(rows):
        cls = f" class='{row_class(i)}'" if row_class and row_class(i) else ""
        body += f"<tr{cls}>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>"
    return f"<div class='scroll'><table><tr>{h}</tr>{body}</table></div>"


def fmt(x, d=2):
    return "-" if x is None else f"{x:.{d}f}"


def player_line(p):
    return f"{p['name']} ({p['pos']}, {p['team']})"


def render(c):
    e = html.escape
    out = [f"<!doctype html><html><head><meta charset='utf-8'><meta name='robots' content='noindex'>"
           f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>Fantasy Hockey Dashboard</title><style>{CSS}</style></head><body><div class='wrap'>",
           f"<h1>{e(c['my_name'])}</h1>",
           f"<div class='sub'>{e(c['league_name'])} &middot; record {c['my_rec']} &middot; updated {e(c['updated'])} "
           f"&middot; read-only, nothing is changed in ESPN</div>"]

    # --- Matchup
    m = c["matchup"]
    if m:
        pw = m["p_win"]
        out.append(
            "<div class='card'><h2>This week's matchup</h2><div class='vs'>"
            f"<div class='team'><div class='n'>{e(c['my_name'])}</div><div class='s'>{m['me_now']:.1f}</div>"
            f"<div class='r'>projected final {m['proj_me']:.0f}</div></div>"
            f"<div class='team right'><div class='n'>{e(m['opp_name'])}</div><div class='s'>{m['opp_now']:.1f}</div>"
            f"<div class='r'>{e(m['opp_rec'])} &middot; projected final {m['proj_opp']:.0f}</div></div></div>"
            f"<div class='bar'><i class='a' style='width:{pw*100:.0f}%'></i><i class='b' style='width:{(1-pw)*100:.0f}%'></i></div>"
            f"<div><span class='big'>{pw*100:.0f}%</span> <span class='muted'>chance you win this week "
            f"({m['days_left']} scoring days left, using each team's best lineup every day)</span></div></div>")

    # --- Goalies
    out.append("<div class='card'><h2>Goalie decisions</h2>")
    if not c["goalies"]:
        out.append("<div class='muted'>No goalies found on your roster.</div>")
    for gd in c["goalies"]:
        p = gd["p"]
        svp = f" &middot; save % {p['svp']:.3f}" if p.get("svp") else ""
        out.append(f"<div class='g'><div class='gh'><b>{e(p['name'])} <span class='muted'>({e(p['team'])}, "
                   f"{A.slot_name(p['slot'])})</span></b><span class='muted'>{fmt(p['outlook'])} pts/start outlook{svp}</span></div>")
        if not gd["rows"]:
            out.append("<div class='muted'>No games in the next few days.</div>")
        else:
            out.append("<div class='chips'>")
            for r in gd["rows"]:
                at = "vs" if r["home"] else "@"
                out.append(f"<div class='chip'><div class='d'>{e(r['day'])} &middot; {e(r['time'])}</div>"
                           f"<div class='o'>{at} {e(r['opp'])}</div>"
                           f"<div class='m'>Win chance {r['p']*100:.0f}% &middot; exp. {r['e']:+.1f} pts</div>"
                           f"<div style='margin-top:6px'><span class='pill {r['cls']}'>{e(r['verdict'])}</span></div></div>")
            out.append("</div>")
        out.append("</div>")
    out.append("<div class='muted' style='margin-top:8px'>BENCH = expected points below zero. START (RISKY) = slightly "
               "positive but a big swing either way. NHL single games are close to coin flips, so treat win chances as leans, "
               "not promises. Confirmed starters are not included yet.</div></div>")

    # --- Moves
    out.append("<div class='card'><h2>Suggested moves</h2>")
    if c["moves"]:
        rows = [[player_line(mv["add"]), fmt(mv["add"]["outlook"]), mv["add"]["g7"], player_line(mv["drop"]),
                 fmt(mv["drop"]["outlook"]), f"+{mv['gain']:.2f}", f"+{mv['week_gain']:.1f}"] for mv in c["moves"]]
        out.append(table(["Add", "Outlook", "Games (7d)", "Drop", "Outlook", "Gain/game", "Gain (7d)"], rows))
        out.append("<div class='muted'>Outlook = expected fantasy points per game. Players with very few games and no ESPN "
                   "projection can look better than they are, so check small samples before acting.</div>")
    else:
        out.append("<div class='muted'>Nothing available clearly beats your weakest players.</div>")
    out.append("</div>")

    # --- Alerts
    out.append("<div class='card'><h2>Lineup alerts (today)</h2>")
    if c["alerts"]:
        out.append("<ul>" + "".join(f"<li class='{k}'>{e(t)}</li>" for k, t in c["alerts"]) + "</ul>")
    else:
        out.append("<div class='good'>No lineup problems found.</div>")
    out.append("</div>")

    # --- Standings
    rows = [[i + 1, s["name"], s["rec"], f"{s['pf']:.1f}"] for i, s in enumerate(c["standings"])]
    out.append("<div class='card'><h2>League standings</h2>"
               + table(["#", "Team", "W-L-T", "Points for"], rows,
                       row_class=lambda i: "me" if c["standings"][i]["me"] else "") + "</div>")

    # --- Roster + free agents
    mine = sorted(c["mine"], key=lambda x: (x["group"], -x["outlook"]))
    rows = [[player_line(p), A.slot_name(p["slot"]), int(p["gp"]), fmt(p["ppg"]), fmt(p["exp_ppg"]), fmt(p["proj_ppg"]),
             fmt(p["outlook"]), p["g7"], "; ".join(p["flags"])] for p in mine]
    out.append("<div class='card'><h2>Your roster</h2><details open><summary>Show / hide</summary>"
               + table(["Player", "Slot", "GP", "PPG", "Exp", "Proj", "Outlook", "G7", "Flags"], rows)
               + "<div class='muted'>PPG = actual points per game. Exp = luck-adjusted. Proj = ESPN projection. "
                 "Outlook = blend used for ranking. G7 = games in the next 7 days.</div></details></div>")
    for group, label in (("G", "Goalies"), ("D", "Defense"), ("F", "Forwards")):
        top = sorted([p for p in c["fas"] if p["group"] == group and p["injury"] not in A.BAD_INJURY],
                     key=lambda p: -p["outlook"])[:12]
        rows = [[player_line(p), fmt(p["outlook"]), fmt(p["ppg"]), fmt(p["proj_ppg"]), int(p["gp"]), p["g7"],
                 fmt(p["own"], 0) + "%", p["status"] or "", "; ".join(p["flags"])] for p in top]
        out.append(f"<div class='card'><h2>Best available - {label}</h2><details><summary>Show / hide</summary>"
                   + table(["Player", "Outlook", "PPG", "Proj", "GP", "G7", "Owned", "Status", "Flags"], rows)
                   + "</details></div>")
    out.append("</div></body></html>")
    return "".join(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def build_context(cfg, data, league, standings, now_ms):
    season, my_id = cfg["season"], cfg["team"]
    abbr, games = schedule_maps(data["schedules"])
    sp = data["roster"].get("scoringPeriodId", 1)
    mine, fas = A.build_players(data, cfg)
    moves = A.recommend(mine, fas)

    teams = {t.get("id"): t for t in league.get("teams", [])}
    me_t = teams.get(my_id, {})
    w, l, t_, _ = record_of(me_t)

    matchup = None
    mp, m, my_side, opp_side = find_matchup(league, my_id)
    if m:
        opp_id = opp_side.get("teamId")
        opp_json = next((t for t in data["roster"].get("teams", []) if t.get("id") == opp_id), None)
        start, end = matchup_periods(m, mp)
        periods = list(range(max(sp, start), end + 1))
        mu_me, var_me = expected_remaining(mine, periods, games, now_ms, standings)
        opp_players = roster_players(opp_json, season, abbr) if opp_json else []
        mu_opp, var_opp = expected_remaining(opp_players, periods, games, now_ms, standings)
        me_now, opp_now = side_points(my_side), side_points(opp_side)
        sd = math.sqrt(var_me + var_opp) or 1.0
        z = (me_now + mu_me - opp_now - mu_opp) / sd
        ow, ol, ot, _ = record_of(teams.get(opp_id, {}))
        matchup = {"me_now": me_now, "opp_now": opp_now, "proj_me": me_now + mu_me, "proj_opp": opp_now + mu_opp,
                   "p_win": clamp(norm_cdf(z), 0.01, 0.99), "days_left": len(periods),
                   "opp_name": team_label(teams.get(opp_id, {})), "opp_rec": f"{ow}-{ol}-{ot}"}

    standings_rows = []
    for tid, t in teams.items():
        tw, tl, tt, pf = record_of(t)
        standings_rows.append({"name": team_label(t), "rec": f"{tw}-{tl}-{tt}", "pf": pf, "w": tw, "me": tid == my_id})
    standings_rows.sort(key=lambda s: (-s["w"], -s["pf"]))

    return {
        "league_name": (league.get("settings") or {}).get("name", "Fantasy Hockey League"),
        "my_name": team_label(me_t) if me_t else "My Team",
        "my_rec": f"{w}-{l}-{t_}",
        "updated": datetime.now(et_zone()).strftime("%a %b %d, %I:%M %p ET").replace(" 0", " "),
        "matchup": matchup,
        "goalies": goalie_decisions(mine, sp, games, abbr, standings, now_ms),
        "moves": moves,
        "alerts": lineup_alerts(mine, sp, games, now_ms),
        "standings": standings_rows,
        "mine": mine,
        "fas": fas,
    }


def main():
    cfg = A.get_config()
    print("Reading your ESPN league...")
    data = A.fetch_all(cfg)
    base = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{cfg['season']}"
    league = A.espn_get(f"{base}/segments/0/leagues/{cfg['league']}", cfg["cookies"],
                        params=[("view", "mSettings"), ("view", "mTeam"),
                                ("view", "mMatchup"), ("view", "mMatchupScore")])
    standings = load_nhl_standings()
    ctx = build_context(cfg, data, league, standings, int(time.time() * 1000))
    if not ctx["mine"]:
        sys.exit("Couldn't find your team. Check LEAGUE_ID and TEAM_ID.")
    Path("site").mkdir(exist_ok=True)
    Path("site/index.html").write_text(render(ctx), encoding="utf-8")
    m = ctx["matchup"]
    if m:
        print(f"Matchup vs {m['opp_name']}: {m['me_now']:.1f}-{m['opp_now']:.1f}, "
              f"win chance {m['p_win']*100:.0f}%")
    for gd in ctx["goalies"]:
        for r in gd["rows"]:
            print(f"  {gd['p']['name']}: {r['day']} {'vs' if r['home'] else '@'} {r['opp']} "
                  f"win {r['p']*100:.0f}% exp {r['e']:+.1f} -> {r['verdict']}")
    print("Saved site/index.html")


if __name__ == "__main__":
    main()
