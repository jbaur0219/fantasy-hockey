"""
PLATFORM ADAPTER INTERFACE: what the model needs from any fantasy platform, so ESPN is one adapter among several.

The model (core, streams, goalies, planner...) works on plain player records and a LeagueSettings. An adapter's job is
to read a platform's league, rosters, free agents and NHL schedule, and translate them. Only ESPN is built today
(platforms/espn.py); Yahoo and Fantrax are listed so the shape is clear, and raise NotImplementedError.

Every adapter is READ-ONLY: it never adds, drops, trades or changes anything on the platform.
"""
from dataclasses import dataclass, field

STAT_GOAL, STAT_WIN = "13", "1"          # ESPN stat ids; other adapters translate their own ids to these
GROUP_SLOT = {"F": "3", "D": "4", "G": "5"}   # ESPN lineup slot used for per-position scoring overrides


@dataclass
class LeagueSettings:
    """A league's rules, in the model's terms. Defaults = the league this app was built for."""
    platform: str = "espn"
    league_id: str = ""
    name: str = ""
    lineup: dict = field(default_factory=lambda: {"F": 9, "D": 5, "UTIL": 1, "G": 2})
    bench: int = 4
    ir: int = 1
    # points per stat (string stat id -> points) and per-slot overrides ({slot id: {stat id: points}})
    scoring: dict = field(default_factory=lambda: {STAT_GOAL: 2.0, STAT_WIN: 4.0})
    overrides: dict = field(default_factory=dict)
    scoring_type: str = "H2H_POINTS"
    # adds: weekly (per matchup) limit, per-day limit, season cap; unlimited = no weekly cap
    moves: dict = field(default_factory=lambda: {"weekly": 7, "per_day": None, "season": None, "unlimited": False})
    waiver_hours: int = None
    matchup_weeks: dict = field(default_factory=dict)      # {matchup period: number of NHL weeks}
    lock: str = None                                         # the platform's lineup lock rule, as it names it
    approx: str = None                                       # anything the model approximates for this league

    def points(self, stat, grp=None):
        stat = str(stat)
        if grp and stat in (self.overrides.get(GROUP_SLOT.get(grp, ""), {}) or {}):
            return float(self.overrides[GROUP_SLOT[grp]][stat])
        return float(self.scoring.get(stat, 0.0) or 0.0)

    def goal_points(self, grp="F"):
        return self.points(STAT_GOAL, grp)

    def win_points(self):
        return self.points(STAT_WIN, "G")

    def matchup_days(self, mp):
        return 7 * max(1, int(self.matchup_weeks.get(str(mp)) or 1))


class Platform:
    """One fantasy platform. Subclasses fill these in; the build only calls them."""
    name = "?"

    def __init__(self, cfg):
        self.cfg = cfg

    def fetch_all(self):
        """{'roster': ..., 'schedules': ..., 'free_agents': ...} in the shapes analyze.py reads (ESPN's today)."""
        raise NotImplementedError

    def fetch_league(self):
        """The league record: settings, teams, matchups, status."""
        raise NotImplementedError

    def settings(self, league):
        """LeagueSettings from the league record, or raise ValueError if they can't be read."""
        raise NotImplementedError


class NotBuilt(Platform):
    def fetch_all(self):
        raise NotImplementedError(f"{self.name} is not supported yet (ESPN only for now)")

    fetch_league = fetch_all

    def settings(self, league):
        raise NotImplementedError(f"{self.name} is not supported yet (ESPN only for now)")


class Yahoo(NotBuilt):
    name = "yahoo"          # needs Yahoo Fantasy API OAuth app approval (see claude/railway-setup.md roadmap)


class Fantrax(NotBuilt):
    name = "fantrax"
