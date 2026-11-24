"""
ESPN ADAPTER (READ-ONLY): reads an ESPN fantasy hockey league and translates its settings for the model.

Settings come from the league's mSettings view (already fetched by build.py):
  settings.rosterSettings.lineupSlotCounts   {slot id: count}; hockey slot ids 0 C, 1 LW, 2 RW, 3 F, 4 D, 5 G,
                                             6 UTIL, 7 bench, 8+ IR
  settings.scoringSettings.scoringItems      [{statId, points, pointsOverrides: {slot id: points}}]
  settings.acquisitionSettings               matchupAcquisitionLimit (-1 none), matchupLimitPerScoringPeriod,
                                             acquisitionLimit (season, -1 none), waiverHours
  settings.scheduleSettings.matchupPeriods   {matchup period: [NHL weeks]}
  settings.rosterSettings.lineupLocktimeType the lock rule, as ESPN names it (kept for display only)
"""
from platforms.base import LeagueSettings, Platform

SLOT = {0: "C", 1: "LW", 2: "RW", 3: "F", 4: "D", 5: "G", 6: "UTIL", 7: "BN"}   # anything 8+ is IR
FWD_POS = ("C", "LW", "RW")


def _int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def settings_from(league, league_id=""):
    """LeagueSettings from ESPN's league JSON. Raises ValueError when the lineup can't be read or looks wrong."""
    st = (league or {}).get("settings") or {}
    rs = st.get("rosterSettings") or {}
    counts = rs.get("lineupSlotCounts") or {}
    if not counts:
        raise ValueError("no lineup slots in the league settings")
    lineup = {"F": 0, "D": 0, "UTIL": 0, "G": 0}
    pos_slots, bench, ir = 0, 0, 0
    for k, v in counts.items():
        sid, n = _int(k), _int(v, 0) or 0
        if sid is None or n <= 0:
            continue
        name = SLOT.get(sid, "IR")
        if name in FWD_POS:
            lineup["F"] += n
            pos_slots += n
        elif name in lineup:
            lineup[name] += n
        elif name == "BN":
            bench += n
        else:
            ir += n
    skaters = lineup["F"] + lineup["D"] + lineup["UTIL"]
    if not (6 <= skaters <= 30) or not (1 <= lineup["G"] <= 4):
        raise ValueError(f"lineup looks wrong ({lineup})")

    scoring, overrides = {}, {}
    sc = st.get("scoringSettings") or {}
    for it in sc.get("scoringItems") or []:
        sid = it.get("statId")
        if sid is None:
            continue
        scoring[str(sid)] = float(it.get("points") or 0)
        for slot, pts in (it.get("pointsOverrides") or {}).items():
            overrides.setdefault(str(slot), {})[str(sid)] = float(pts or 0)

    acq = st.get("acquisitionSettings") or {}
    wk = _int(acq.get("matchupAcquisitionLimit"))
    season = _int(acq.get("acquisitionLimit"))
    moves = {"weekly": None, "per_day": None, "season": season if season is not None and season >= 0 else None,
             "unlimited": wk is not None and wk < 0, "known": wk is not None}
    if wk is not None and wk >= 0:
        if acq.get("matchupLimitPerScoringPeriod"):
            moves["per_day"] = wk
        else:
            moves["weekly"] = wk

    weeks = {}
    for mp, wl in ((st.get("scheduleSettings") or {}).get("matchupPeriods") or {}).items():
        weeks[str(mp)] = max(1, len(wl or [1]))

    s = LeagueSettings(platform="espn", league_id=str(league_id), name=st.get("name") or "", lineup=lineup,
                       bench=bench, ir=ir, scoring=scoring or LeagueSettings().scoring, overrides=overrides,
                       scoring_type=sc.get("scoringType") or "H2H_POINTS", moves=moves,
                       waiver_hours=_int(acq.get("waiverHours")), matchup_weeks=weeks,
                       lock=rs.get("lineupLocktimeType") or rs.get("rosterLocktimeType"))
    notes = []
    if pos_slots:
        notes.append(f"{pos_slots} C/LW/RW slots counted as forward slots")
    if s.scoring_type and "POINTS" not in str(s.scoring_type).upper():
        notes.append(f"{s.scoring_type} scoring: the model is built for points leagues")
    s.approx = "; ".join(notes) or None
    return s


class ESPN(Platform):
    name = "espn"

    def fetch_all(self):
        import analyze as A
        return A.fetch_all(self.cfg)

    def fetch_league(self):
        import analyze as A
        c = self.cfg
        base = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{c['season']}"
        return A.espn_get(f"{base}/segments/0/leagues/{c['league']}", c["cookies"],
                          params=[("view", "mSettings"), ("view", "mTeam"), ("view", "mMatchup"),
                                  ("view", "mMatchupScore")])

    def settings(self, league):
        return settings_from(league, self.cfg.get("league", ""))
