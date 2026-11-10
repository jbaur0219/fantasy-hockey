#!/usr/bin/env python3
"""
Fantasy Hockey Assistant  (READ-ONLY)

Run:  python3 analyze.py

What it does
  1. Reads your ESPN league (roster, free agents, NHL schedule) using your login cookies.
  2. Scores every player in YOUR league's points system.
  3. Estimates how "lucky" each player has been (shooting % luck) and blends that with
     ESPN's own projection to get an "outlook" in points per game.
  4. Flags underperformers / overperformers on your roster.
  5. Suggests add/drop moves and ranks the best free agents.
  6. Writes report.html (open it in your browser) and prints a summary.

It NEVER adds, drops, trades or changes your lineup. It only reads.
"""
import html
import json
import os
import sys
from datetime import date
from pathlib import Path

import requests

# ----------------------------------------------------------------------------
# SETTINGS you might want to tweak
# ----------------------------------------------------------------------------
LEAGUE_SHOOTING_PCT = 0.10   # typical NHL shooting percentage
SHOT_PRIOR = 80              # "how many shots before I trust a player's own shooting %"
GAMES_PRIOR_SKATER = 15      # how much weight ESPN's projection gets (in games)
GAMES_PRIOR_GOALIE = 8
MIN_GAIN_SKATER = 0.20       # only suggest a swap if it gains >= this many pts/game
MIN_GAIN_GOALIE = 0.60
MAX_SUGGESTIONS = 5
FREE_AGENT_LIMIT = 300       # how many free agents/waiver players to look at
DAYS_AHEAD = 7               # "games in the next N days"

# ESPN lineup slot numbers (verified against this league)
SLOT_NAMES = {3: "F", 4: "D", 5: "G", 6: "UTIL", 7: "BN"}
IR_SLOTS = {8, 9, 10}        # injured reserve (anything not in SLOT_NAMES is treated as IR)
# ESPN position ids
POS = {1: "C", 2: "LW", 3: "RW", 4: "D", 5: "G"}
BAD_INJURY = {"OUT", "INJURY_RESERVE", "SUSPENSION"}

# ESPN stat ids (verified against real data)
S_G, S_A, S_PPP, S_GWG, S_SOG, S_HIT, S_BLK, S_GP = 13, 14, 37, 22, 29, 31, 32, 30
S_GW, S_GA, S_SA, S_SV = 1, 4, 3, 6


# ----------------------------------------------------------------------------
# Setup helpers
# ----------------------------------------------------------------------------
def load_env(path=".env"):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def get_config():
    load_env()
    s2, swid = os.environ.get("ESPN_S2", ""), os.environ.get("SWID", "")
    if not s2 or not swid or "paste" in s2.lower() or "paste" in swid.lower():
        sys.exit(
            "Missing login cookies.\n"
            "Open the .env file in this folder and fill in ESPN_S2 and SWID.\n"
            "See README.md, step 3."
        )
    return {
        "league": os.environ.get("LEAGUE_ID", "557638258"),
        "team": int(os.environ.get("TEAM_ID", "1")),
        "season": int(os.environ.get("SEASON", "2027")),
        "cookies": {"espn_s2": s2, "SWID": swid},
    }


def espn_get(url, cookies, params=None, headers=None):
    r = requests.get(url, cookies=cookies, params=params, headers=headers, timeout=30)
    if r.status_code in (401, 403):
        sys.exit(
            "ESPN rejected your login cookies (they probably expired).\n"
            "Copy fresh ESPN_S2 and SWID values into .env (README step 3) and run again."
        )
    r.raise_for_status()
    return r.json()


# ----------------------------------------------------------------------------
# Fetch from ESPN
# ----------------------------------------------------------------------------
def fetch_all(cfg):
    season, league, cookies = cfg["season"], cfg["league"], cfg["cookies"]
    base = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{season}"
    league_url = f"{base}/segments/0/leagues/{league}"

    roster = espn_get(league_url, cookies, params=[("view", "mRoster"), ("view", "mTeam")])
    schedules = espn_get(base, cookies, params=[("view", "proTeamSchedules_wl")])

    ffilter = {
        "players": {
            "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
            "filterSlotIds": {"value": list(range(0, 26))},
            "limit": FREE_AGENT_LIMIT,
            "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
            "sortDraftRanks": {"sortPriority": 100, "sortAsc": True, "value": "STANDARD"},
        }
    }
    fa = espn_get(
        league_url, cookies,
        params=[("view", "kona_player_info")],
        headers={"x-fantasy-filter": json.dumps(ffilter)},
    )
    return {"roster": roster, "schedules": schedules, "free_agents": fa}


# ----------------------------------------------------------------------------
# Turn raw ESPN data into simple player records
# ----------------------------------------------------------------------------
def num(d, key):
    try:
        return float(d.get(str(key), 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def parse_player(pl, season, slot=None, status=None):
    pos = POS.get(pl.get("defaultPositionId"), "?")
    group = "G" if pos == "G" else ("D" if pos == "D" else "F")
    by_id = {s.get("id"): s for s in pl.get("stats", [])}
    cur = by_id.get(f"00{season}", {})
    proj = by_id.get(f"10{season}", {})
    l15 = by_id.get(f"02{season}", {})
    cs, ps, rs = cur.get("stats", {}), proj.get("stats", {}), l15.get("stats", {})

    gp = num(cs, S_GP)
    applied = float(cur.get("appliedTotal", 0) or 0)
    ppg = applied / gp if gp else None
    proj_gp = num(ps, S_GP)
    proj_ppg = float(proj.get("appliedTotal", 0) or 0) / proj_gp if proj_gp else None
    r_gp = num(rs, S_GP)
    recent_ppg = float(l15.get("appliedTotal", 0) or 0) / r_gp if r_gp else None

    p = {
        "id": pl.get("id"), "name": pl.get("fullName", "?"), "pos": pos, "group": group,
        "team_id": pl.get("proTeamId"), "slot": slot, "status": status,
        "own": (pl.get("ownership") or {}).get("percentOwned"),
        "injury": pl.get("injuryStatus", "ACTIVE"),
        "gp": gp, "applied": applied, "ppg": ppg, "proj_ppg": proj_ppg,
        "recent_ppg": recent_ppg, "recent_gp": r_gp, "flags": [],
    }

    if group == "G":
        sa, sv = num(cs, S_SA), num(cs, S_SV)
        p.update({"wins": num(cs, S_GW), "ga": num(cs, S_GA),
                  "svp": (sv / sa) if sa else None, "exp_ppg": ppg})
        prior = GAMES_PRIOR_GOALIE
    else:
        g, sog = num(cs, S_G), num(cs, S_SOG)
        # Regress shooting % toward the league average: few shots -> trust the average more.
        exp_g = (g + SHOT_PRIOR * LEAGUE_SHOOTING_PCT) / (sog + SHOT_PRIOR) * sog if sog or g else 0
        exp_pts = applied - 2 * (g - exp_g)          # swap real goals for "expected" goals
        p.update({"g": g, "a": num(cs, S_A), "sog": sog, "hit": num(cs, S_HIT),
                  "blk": num(cs, S_BLK), "ppp": num(cs, S_PPP),
                  "sh_pct": (g / sog) if sog else None,
                  "exp_ppg": (exp_pts / gp) if gp else None})
        prior = GAMES_PRIOR_SKATER

    # OUTLOOK = what we expect going forward, per game.
    # Start from ESPN's projection, then move toward the player's "luck-adjusted" results
    # as he plays more games.
    base_ppg = p["exp_ppg"]
    if base_ppg is not None and proj_ppg is not None:
        p["outlook"] = (gp * base_ppg + prior * proj_ppg) / (gp + prior)
    elif proj_ppg is not None:
        p["outlook"] = proj_ppg
    elif base_ppg is not None:
        p["outlook"] = base_ppg
    else:
        p["outlook"] = 0.0

    p["flags"] = make_flags(p)
    return p


def make_flags(p):
    out = []
    gp, ppg, proj = p["gp"], p["ppg"], p["proj_ppg"]
    if p["group"] == "G":
        if gp >= 5 and p["svp"] is not None:
            if p["svp"] < 0.890:
                out.append(f"Poor save % ({p['svp']:.3f}) - likely to bounce back, but risky")
            elif p["svp"] > 0.925:
                out.append(f"Hot save % ({p['svp']:.3f}) - may cool off")
    else:
        if gp >= 8 and p.get("sog", 0) >= 25 and p.get("sh_pct") is not None:
            if p["sh_pct"] >= 0.16:
                out.append(f"Shooting hot ({p['sh_pct']:.0%}) - goals likely to cool")
            elif p["sh_pct"] <= 0.05:
                out.append(f"Shooting cold ({p['sh_pct']:.0%}) - goals due to rise")
    if gp >= 8 and ppg is not None and proj is not None:
        if ppg - proj <= -0.5:
            out.append("Well below ESPN projection")
        elif ppg - proj >= 0.5:
            out.append("Well above ESPN projection")
    if p["recent_gp"] >= 4 and p["recent_ppg"] is not None and ppg is not None:
        if p["recent_ppg"] - ppg >= 0.6:
            out.append("Hot last 15 days")
        elif p["recent_ppg"] - ppg <= -0.6:
            out.append("Cold last 15 days")
    if p["injury"] not in ("ACTIVE", None):
        out.append(f"Injury: {p['injury']}")
    return out


def team_info(schedules, sp, days):
    """Returns ({team_id: abbrev}, {team_id: games in next `days` days})."""
    abbr, games = {}, {}
    for t in schedules.get("settings", {}).get("proTeams", []):
        tid = t.get("id")
        abbr[tid] = t.get("abbrev", "?")
        gbp = t.get("proGamesByScoringPeriod") or {}
        games[tid] = sum(len(gbp.get(str(sp + i), [])) for i in range(days))
    return abbr, games


def build_players(data, cfg):
    season = cfg["season"]
    sp = data["roster"].get("scoringPeriodId", 1)
    abbr, games = team_info(data["schedules"], sp, DAYS_AHEAD)

    mine = []
    for t in data["roster"].get("teams", []):
        if t.get("id") == cfg["team"]:
            for e in t.get("roster", {}).get("entries", []):
                mine.append(parse_player(e["playerPoolEntry"]["player"], season,
                                         slot=e.get("lineupSlotId")))
    fas = []
    for e in data["free_agents"].get("players", []):
        fas.append(parse_player(e["player"], season, status=e.get("status")))

    for p in mine + fas:
        p["team"] = abbr.get(p["team_id"], "?")
        p["g7"] = games.get(p["team_id"], 0)
        p["week_pts"] = p["outlook"] * p["g7"]
    return mine, fas


# ----------------------------------------------------------------------------
# Recommendations
# ----------------------------------------------------------------------------
def slot_name(s):
    return SLOT_NAMES.get(s, "IR")


def recommend(mine, fas):
    moves = []
    for group, min_gain in (("G", MIN_GAIN_GOALIE), ("D", MIN_GAIN_SKATER), ("F", MIN_GAIN_SKATER)):
        # Drop candidates: your active (non-IR) players in this group, weakest first.
        # Only the bottom 3 are considered, so we never suggest dropping a core player.
        drops = sorted([p for p in mine if p["group"] == group and slot_name(p["slot"]) != "IR"],
                       key=lambda p: p["outlook"])[:3]
        adds = sorted([p for p in fas
                       if p["group"] == group and p["injury"] not in BAD_INJURY and p["g7"] > 0],
                      key=lambda p: p["outlook"], reverse=True)
        for add, drop in zip(adds, drops):
            gain = add["outlook"] - drop["outlook"]
            if gain >= min_gain:
                moves.append({"add": add, "drop": drop, "gain": gain,
                              "week_gain": add["week_pts"] - drop["week_pts"]})
    moves.sort(key=lambda m: m["week_gain"], reverse=True)
    return moves[:MAX_SUGGESTIONS]


# ----------------------------------------------------------------------------
# Output
# ----------------------------------------------------------------------------
def f(x, d=2):
    return "-" if x is None else f"{x:.{d}f}"


def player_line(p):
    return f"{p['name']} ({p['pos']}, {p['team']})"


def console_report(mine, fas, moves):
    print(f"\nFANTASY HOCKEY REPORT - {date.today():%b %d, %Y}  (read-only, no changes made)\n")
    print("YOUR ROSTER (outlook = expected points per game going forward)")
    print(f"{'Player':<30}{'Slot':<6}{'GP':>4}{'PPG':>6}{'Exp':>6}{'Proj':>6}{'Outlk':>7}{'G7':>4}  Flags")
    for p in sorted(mine, key=lambda x: (x["group"], -x["outlook"])):
        print(f"{player_line(p):<30}{slot_name(p['slot']):<6}{int(p['gp']):>4}{f(p['ppg']):>6}"
              f"{f(p['exp_ppg']):>6}{f(p['proj_ppg']):>6}{f(p['outlook']):>7}{p['g7']:>4}  "
              f"{'; '.join(p['flags'])}")
    print("\nSUGGESTED MOVES")
    if not moves:
        print("  None - nothing available clearly beats your weakest players.")
    for m in moves:
        a, d = m["add"], m["drop"]
        print(f"  ADD {player_line(a)}  outlook {f(a['outlook'])}, {a['g7']} games   |   "
              f"DROP {player_line(d)}  outlook {f(d['outlook'])}   "
              f"=> +{m['gain']:.2f}/game, +{m['week_gain']:.1f} pts next {DAYS_AHEAD} days")
    print("\nTOP FREE AGENTS BY POSITION")
    for group in ("G", "D", "F"):
        top = sorted([p for p in fas if p["group"] == group and p["injury"] not in BAD_INJURY],
                     key=lambda p: p["outlook"], reverse=True)[:8]
        print(f"  {group}:")
        for p in top:
            print(f"    {player_line(p):<30} outlook {f(p['outlook'])}  games {p['g7']}  "
                  f"owned {f(p['own'], 0)}%  {p['status'] or ''}")


def table(headers, rows):
    h = "".join(f"<th>{html.escape(x)}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><tr>{h}</tr>{body}</table>"


def html_report(mine, fas, moves, path="report.html"):
    css = ("body{font-family:system-ui,sans-serif;margin:24px;color:#222}"
           "h1{margin-bottom:0}h2{margin-top:32px}table{border-collapse:collapse;margin:8px 0}"
           "th,td{border:1px solid #ddd;padding:6px 10px;text-align:left;font-size:14px}"
           "th{background:#f3f3f3}.note{color:#666;font-size:13px}")
    roster_rows = [[player_line(p), slot_name(p["slot"]), int(p["gp"]), f(p["ppg"]), f(p["exp_ppg"]),
                    f(p["proj_ppg"]), f(p["outlook"]), p["g7"], "; ".join(p["flags"])]
                   for p in sorted(mine, key=lambda x: (x["group"], -x["outlook"]))]
    move_rows = [[player_line(m["add"]), f(m["add"]["outlook"]), m["add"]["g7"],
                  player_line(m["drop"]), f(m["drop"]["outlook"]),
                  f"+{m['gain']:.2f}", f"+{m['week_gain']:.1f}"] for m in moves]
    parts = [f"<html><head><meta charset='utf-8'><title>Fantasy Hockey Report</title>"
             f"<style>{css}</style></head><body>",
             f"<h1>Fantasy Hockey Report</h1><p class='note'>{date.today():%A, %B %d, %Y} - "
             "read-only: nothing has been changed in ESPN.</p>",
             "<h2>Suggested moves</h2>",
             table(["Add", "Outlook", f"Games ({DAYS_AHEAD}d)", "Drop", "Outlook", "Gain/game",
                    f"Gain ({DAYS_AHEAD}d)"], move_rows) if move_rows
             else "<p>None - nothing available clearly beats your weakest players.</p>",
             "<h2>Your roster</h2>",
             "<p class='note'>PPG = actual points/game. Exp = luck-adjusted (shooting % regressed to "
             "average). Proj = ESPN projection. Outlook = blend, what to expect going forward. "
             "G7 = games in the next 7 days.</p>",
             table(["Player", "Slot", "GP", "PPG", "Exp", "Proj", "Outlook", "G7", "Flags"], roster_rows)]
    for group, label in (("G", "Goalies"), ("D", "Defense"), ("F", "Forwards")):
        top = sorted([p for p in fas if p["group"] == group and p["injury"] not in BAD_INJURY],
                     key=lambda p: p["outlook"], reverse=True)[:12]
        rows = [[player_line(p), f(p["outlook"]), f(p["ppg"]), f(p["proj_ppg"]), int(p["gp"]),
                 p["g7"], f(p["own"], 0) + "%", p["status"] or "", "; ".join(p["flags"])] for p in top]
        parts += [f"<h2>Best free agents - {label}</h2>",
                  table(["Player", "Outlook", "PPG", "Proj", "GP", "G7", "Owned", "Status", "Flags"], rows)]
    parts.append("</body></html>")
    Path(path).write_text("".join(parts), encoding="utf-8")
    return path


def markdown_report(mine, fas, moves):
    """Plain-text-friendly version of the report (shown on GitHub's run page)."""
    def row(cells):
        return "| " + " | ".join(str(c) for c in cells) + " |"
    L = [f"# Fantasy Hockey Report - {date.today():%A, %B %d, %Y}",
         "_Read-only: nothing was changed in ESPN._", "", "## Suggested moves"]
    if moves:
        L += [row(["Add", "Outlook", "Games", "Drop", "Outlook", "Gain/game", f"Gain ({DAYS_AHEAD}d)"]),
              row(["---"] * 7)]
        for m in moves:
            a, d = m["add"], m["drop"]
            L.append(row([player_line(a), f(a["outlook"]), a["g7"], player_line(d), f(d["outlook"]),
                          f"+{m['gain']:.2f}", f"+{m['week_gain']:.1f}"]))
    else:
        L.append("None - nothing available clearly beats your weakest players.")
    L += ["", "## Your roster",
          row(["Player", "Slot", "GP", "PPG", "Exp", "Proj", "Outlook", "G7", "Flags"]), row(["---"] * 9)]
    for p in sorted(mine, key=lambda x: (x["group"], -x["outlook"])):
        L.append(row([player_line(p), slot_name(p["slot"]), int(p["gp"]), f(p["ppg"]), f(p["exp_ppg"]),
                      f(p["proj_ppg"]), f(p["outlook"]), p["g7"], "; ".join(p["flags"])]))
    for group, label in (("G", "Goalies"), ("D", "Defense"), ("F", "Forwards")):
        top = sorted([p for p in fas if p["group"] == group and p["injury"] not in BAD_INJURY],
                     key=lambda p: p["outlook"], reverse=True)[:10]
        L += ["", f"## Best free agents - {label}",
              row(["Player", "Outlook", "PPG", "Proj", "GP", "G7", "Owned", "Status", "Flags"]), row(["---"] * 9)]
        for p in top:
            L.append(row([player_line(p), f(p["outlook"]), f(p["ppg"]), f(p["proj_ppg"]), int(p["gp"]),
                          p["g7"], f(p["own"], 0) + "%", p["status"] or "", "; ".join(p["flags"])]))
    return "\n".join(L) + "\n"


def main():
    cfg = get_config()
    print("Reading your ESPN league...")
    data = fetch_all(cfg)
    mine, fas = build_players(data, cfg)
    if not mine:
        sys.exit("Couldn't find your team. Check LEAGUE_ID and TEAM_ID in .env.")
    moves = recommend(mine, fas)
    console_report(mine, fas, moves)
    path = html_report(mine, fas, moves)
    summary = markdown_report(mine, fas, moves)
    Path("report.md").write_text(summary, encoding="utf-8")
    # When running on GitHub, this puts the report right on the run's page.
    gh = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh:
        with open(gh, "a", encoding="utf-8") as fh:
            fh.write(summary)
    print(f"\nSaved {path} (and report.md) - open report.html in your browser for the full report.")


if __name__ == "__main__":
    main()
