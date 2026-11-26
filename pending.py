#!/usr/bin/env python3
"""
PENDING WAIVER CLAIMS (READ-ONLY): claims you have already put in with ESPN that have not processed yet.

A waiver claim is not on your roster until ESPN processes it (overnight), so for a day the app saw the player as still
available and kept suggesting the move you had just made. This reads your pending claims from ESPN
(view=mPendingTransactions) so the plan can treat each one as made from the day it processes:

  - the player you claimed joins your lineup that day, the player you drop leaves it (core.apply_pending),
  - neither is suggested again, and the claim uses one of this matchup's moves (dashboard.move_budget),
  - the Game plan shows a one-line "Claim pending" row so you can see the app knows.

Never fails the build: if ESPN's answer cannot be read, the plan is exactly what it was before (no claims known).
"""
import analyze as A

CLAIM_TYPES = {"WAIVER", "FREEAGENT"}       # add/drop transactions; trades and lineup changes are not claims
PENDING_STATES = {"PENDING", "PROPOSED"}    # anything else (EXECUTED, CANCELED, FAILED_*...) is over


def fetch(cfg):
    """ESPN's raw pending-transactions answer for the league, or None when it could not be read."""
    c = cfg
    url = (f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{c['season']}"
           f"/segments/0/leagues/{c['league']}")
    try:
        return A.espn_get(url, c["cookies"], params=[("view", "mPendingTransactions"), ("forTeamId", c["team"])])
    except (Exception, SystemExit) as e:                      # SystemExit: espn_get quits on a 401/403
        print(f"  pending claims skipped ({type(e).__name__}: {e})")
        return None


def parse(raw, my_team):
    """[{"add": player id, "drop": player id or None, "type": "WAIVER"}] for your pending add/drop claims.
    Reads ESPN's `pendingTransactions` list; each entry has a status, a team, a type and `items` of ADD / DROP rows."""
    if not isinstance(raw, dict):
        return []
    rows = raw.get("pendingTransactions")
    if rows is None:
        rows = raw.get("transactions")
    out = []
    for tx in rows or []:
        if not isinstance(tx, dict):
            continue
        status = str(tx.get("status") or ("PENDING" if tx.get("isPending") else "")).upper()
        if status not in PENDING_STATES:
            continue
        if str(tx.get("type") or "").upper() not in CLAIM_TYPES:
            continue
        tid = tx.get("teamId")
        if tid is not None and tid != my_team:
            continue
        adds, drops = [], []
        for it in tx.get("items") or []:
            if not isinstance(it, dict) or it.get("playerId") is None:
                continue
            kind = str(it.get("type") or "").upper()
            if kind == "ADD" and it.get("toTeamId") in (None, my_team):
                adds.append(it["playerId"])
            elif kind == "DROP" and it.get("fromTeamId") in (None, my_team):
                drops.append(it["playerId"])
        for i, a in enumerate(adds):
            out.append({"add": a, "drop": drops[i] if i < len(drops) else None,
                        "type": str(tx.get("type")).upper()})
    return out


def resolve(raw, my_team, site_data, ndays):
    """Your pending claims with names, and the day each one counts from. Claims go through overnight, so day 1 (tomorrow);
    on the last day of the matchup that is next week, which is past `ndays` and changes nothing this week."""
    claims = parse(raw, my_team)
    names = {p["id"]: p for p in (site_data.get("mine") or []) + (site_data.get("fas") or [])}
    mine_ids = {p["id"] for p in site_data.get("mine") or []}
    out, seen = [], set()
    for c in claims:
        if c["add"] in mine_ids or c["add"] in seen:        # already yours (processed) or listed twice
            continue
        seen.add(c["add"])
        a, d = names.get(c["add"]), names.get(c["drop"])
        out.append({"add": c["add"], "drop": c["drop"], "t": 1, "type": c["type"],
                    "add_n": a["n"] if a else None, "add_tm": a.get("tm") if a else None,
                    "drop_n": d["n"] if d else None,
                    "this_week": 1 < ndays})
    return out


def count_this_week(claims):
    """Claims that process inside this matchup (they use one of its moves)."""
    return sum(1 for c in claims or [] if c.get("this_week"))
