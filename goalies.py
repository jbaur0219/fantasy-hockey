#!/usr/bin/env python3
"""
GOALIE CALLS (READ-ONLY): start / bench for each of your goalies on every day left in the matchup.

  - Expected points if he starts: his outlook, nudged for opponent strength and home ice (same as before).
  - Chance he starts: Daily Faceoff's confirmed / expected starter for today; otherwise his share of team starts.
  - The call compares your goalies who play that day: the best two by (points if he starts x chance he starts) are
    START, anyone else BENCH. A goalie expected to cost you points (negative) is BENCH.
  - Each row says how sure the start is: confirmed, expected, usual starter, split, or usually the backup.
"""
import analyze as A
import dashboard as D
import enrich as E
import odds as O
import starters as S


def _status(p, i, sp_chance, today=0):
    s = S.STATE["by_team"].get(p["team"]) if i == today else None
    if s:
        if E.norm(s["name"]) == E.norm(p["name"]):
            st = s.get("status") or "Unconfirmed"
            if st == "Confirmed":
                return 1.0, "confirmed starter", True
            return 1.0, ("likely starter, not confirmed yet" if st == "Likely" else "expected starter, not confirmed yet"), True
        return 0.0, f"not starting ({s['name'].split()[-1]} in net)", True
    if sp_chance >= 0.6:
        return sp_chance, "usual starter", False
    if sp_chance >= 0.4:
        return sp_chance, "splits starts", False
    return sp_chance, "usually the backup, so he may not play: check the morning of", False


def build(mine, sp, games, abbr, standings, now_ms, ndays, slots=2):
    goalies = [p for p in mine if p["group"] == "G" and A.slot_name(p["slot"]) != "IR"]
    out = {id(p): {"p": p, "rows": []} for p in goalies}
    today = D.today_index(games, sp, now_ms)               # the day Daily Faceoff's starters are for
    for i in range(ndays):
        day_rows = []
        for p in goalies:
            s_me = D.team_strength(p["team"], standings)
            for g in D.games_on(games, p["team_id"], sp + i):
                home = g.get("homeProTeamId") == p["team_id"]
                opp = abbr.get(g.get("awayProTeamId") if home else g.get("homeProTeamId"), "?")
                ln = O.p_win(p["team"], opp, home, g.get("date"))
                if ln is not None:
                    pw = D.clamp(ln, 0.15, 0.85)              # from the betting line (odds.py)
                else:
                    pw = D.log5(s_me, D.team_strength(opp, standings)) + (D.HOME_ICE if home else -D.HOME_ICE)
                    if p.get("svp") and p["gp"] >= 5:
                        pw += D.clamp((p["svp"] - 0.905) * 2.0, -0.05, 0.05)
                    pw = D.clamp(pw, 0.15, 0.85)
                e = p["outlook"] + _win_pts() * (pw - s_me)
                spc = D.start_prob(p, standings)
                st, conf, sure = _status(p, i, spc, today)
                day, tm = D.fmt_game(g.get("date", 0))
                r = {"day": day, "time": tm, "opp": opp, "home": home, "p": pw, "e": e, "sp": round(st, 2),
                     "ev": round(e * st, 2), "conf": conf, "sure": sure, "started": g.get("date", 0) <= now_ms}
                out[id(p)]["rows"].append(r)
                day_rows.append(r)
        live = sorted((r for r in day_rows if not r["started"]), key=lambda r: -r["ev"])
        elig = [r for r in live if not (r["sure"] and r["sp"] == 0) and r["e"] >= 0]
        for r in live:
            if r["sure"] and r["sp"] == 0:
                r["verdict"], r["cls"] = "NOT STARTING", "done"
            elif r["e"] < 0:
                r["verdict"], r["cls"] = "BENCH", "bench"
                r["conf"] += "; expected to cost you points"
            elif elig.index(r) < slots:
                r["verdict"], r["cls"] = "START", ("start" if r["sp"] >= 0.55 else "risky")
            else:
                r["verdict"], r["cls"] = "BENCH", "bench"
                r["conf"] += f"; {len(elig)} of your goalies play, start the best {slots}"
        for r in day_rows:
            if r["started"]:
                r["verdict"], r["cls"] = "GAME STARTED", "done"
    return [v for v in out.values()]


def _win_pts():
    """This league's points for a goalie win (league.py; 4 when the settings can't be read)."""
    import league as L
    return L.settings().win_points()
