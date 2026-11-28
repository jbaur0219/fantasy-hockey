#!/usr/bin/env python3
"""
LEAGUE SETTINGS (READ-ONLY): the rules of the league the app is advising, read from the platform (ESPN today, see
platforms/) on every build, so nothing about one league is baked into the model.

What it holds (platforms.base.LeagueSettings)
  slots        starting lineup: forwards (F), defense (D), utility skater (UTIL), goalies (G); plus bench and IR spots.
               Leagues with separate C / LW / RW slots are counted as forward slots (the model groups forwards
               together); `approx` says so, and the app shows it.
  scoring      points per stat (ESPN stat id -> points), with goalie overrides. The luck adjustment uses the goal value.
  moves        weekly add limit, per-day limit, season cap (dashboard.move_budget reads these).
  days         matchup length per matchup period.

Every module that needs a slot count reads league.SLOTS (one shared dict, updated in place by install()), so a build
for any league uses that league's lineup everywhere: the plan, the day tables, the reasons and the win chance.
Defaults match the league this app was built for (9 F / 5 D / 1 UTIL / 2 G, 2 points a goal); a build whose settings
can't be read keeps them and the health badge says so.
"""
from platforms.base import LeagueSettings

DEFAULT = LeagueSettings()
SLOTS = dict(DEFAULT.lineup)            # {"F": 9, "D": 5, "UTIL": 1, "G": 2}: shared, updated in place
STATE = {"settings": DEFAULT, "known": False, "note": None}


def install(settings, known=True, note=None):
    """Make `settings` the active league's rules for this build."""
    s = settings if isinstance(settings, LeagueSettings) else DEFAULT
    STATE.update(settings=s, known=bool(known and isinstance(settings, LeagueSettings)), note=note)
    SLOTS.clear()
    SLOTS.update(s.lineup)
    return s


def reset():
    install(DEFAULT, known=False)


def settings():
    return STATE["settings"]


def goal_points():
    """Points for a goal (skaters), used to swap real goals for expected goals in the luck adjustment."""
    return STATE["settings"].goal_points()


def win_points():
    """Points for a goalie win (used to turn a goalie's win chance into fantasy points)."""
    return STATE["settings"].win_points()


def summary():
    s = STATE["settings"]
    if not STATE["known"]:
        return "league settings: not read, using the defaults (9 F, 5 D, 1 UTIL, 2 G)"
    lim = "no weekly limit" if s.moves.get("unlimited") else (
        f"{s.moves.get('per_day')} add(s) per NHL game day, pooled for the matchup" if s.moves.get("per_day") else f"{s.moves.get('weekly')} adds a matchup")
    return (f"league settings ({s.platform}): {s.lineup['F']} F, {s.lineup['D']} D, {s.lineup['UTIL']} UTIL, "
            f"{s.lineup['G']} G, {s.bench} bench, {s.ir} IR; {lim}; goal {s.goal_points():g} pts"
            + (f"; {s.approx}" if s.approx else ""))


def page_data():
    """The small summary the app shows (and the health badge uses)."""
    s = STATE["settings"]
    return {"known": STATE["known"], "platform": s.platform, "lineup": dict(s.lineup), "bench": s.bench, "ir": s.ir,
            "approx": s.approx, "note": STATE["note"]}
