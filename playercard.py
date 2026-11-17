"""
PLAYER CARD data (READ-ONLY): games left this matchup and today's game time for every player, used by the player
card popup and the lists. (The card itself is in web/app.js.)
"""


def annotate(site_data, data, now_ms):
    """Adds p['gl'] = games each player's team has left in the current Monday-Sunday matchup (not-yet-started games only)."""
    import dashboard as D
    abbr, games = D.schedule_maps(data["schedules"])
    tid_of = {ab: tid for tid, ab in abbr.items()}
    sp = data["roster"].get("scoringPeriodId", 1)
    m = site_data.get("matchup")
    nd = max(1, min(int(m["days_left"]) if m else 7, D.MAX_DAYS))
    cache = {}

    def left(tm):
        if tm not in cache:
            tid = tid_of.get(tm)
            cache[tm] = None if tid is None else sum(len(D.games_on(games, tid, sp + i, now_ms)) for i in range(nd))
        return cache[tm]

    def today(tm):
        tid = tid_of.get(tm)
        gl = games.get(tid, {}).get(str(sp), []) if tid is not None else []
        dates = [g.get("date") for g in gl if g.get("date")]
        return min(dates) if dates else None

    lists = [site_data.get("mine", []), site_data.get("fas", [])] + [t.get("players", []) for t in site_data.get("teams", [])]
    for lst in lists:
        for p in lst:
            g = left(p.get("tm"))
            if g is not None:
                p["gl"] = g
            t = today(p.get("tm"))
            if t:
                p["gt"] = t
