#!/usr/bin/env python3
"""The past-day lineups on the matchup sheet. Run:  python -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scoreboard as SB   # noqa: E402


def entry(pid, slot_id, pts, name, pos=5, team=3):
    return {"playerId": pid, "lineupSlotId": slot_id,
            "playerPoolEntry": {"appliedStatTotal": pts, "player": {"id": pid, "fullName": name, "defaultPositionId": pos, "proTeamId": team}}}


class PastLineups(unittest.TestCase):
    cfg = {"season": 2027, "league": "1", "cookies": {}}

    def test_bench_and_starters_are_told_apart(self):
        calls = []

        def fetch(url, cookies, params=None):
            calls.append(dict(params)["scoringPeriodId"])
            return {"schedule": [
                {"matchupPeriodId": 8, "home": {"teamId": 1, "rosterForCurrentScoringPeriod": {"entries": [
                    entry(1, 5, 12.8, "D. Kuemper"), entry(2, 7, 0.0, "Idle Bench"), entry(3, 7, 4.0, "Bench Scorer", 1)]}},
                 "away": {"teamId": 2, "rosterForCurrentScoringPeriod": {"entries": [entry(9, 3, 1.5, "A. Skater", 2)]}}},
                {"matchupPeriodId": 7, "home": {"teamId": 5, "rosterForCurrentScoringPeriod": {"entries": [entry(8, 5, 1, "Other week")]}},
                 "away": {"teamId": 6}}]}

        out = SB.past_lineups(self.cfg, {}, 8, 100, 2, {3: "LA"}, fetch=fetch)
        self.assertEqual(calls, [100, 101])
        t1 = {r[0]: r for r in out["0"]["1"]}
        self.assertEqual(t1[1][1:3], ["G", 12.8])                # starting goalie counted
        self.assertEqual(t1[3][1], "BN")                         # scored on the bench: kept, marked bench
        self.assertNotIn(2, t1)                                  # bench, scored nothing: left out
        self.assertEqual(out["0"]["2"][0][1], "F")
        self.assertNotIn("5", out["0"])                          # other matchup weeks ignored

    def test_a_bad_day_is_skipped(self):
        def fetch(url, cookies, params=None):
            if dict(params)["scoringPeriodId"] == 100:
                raise RuntimeError("boom")
            return {"schedule": [{"matchupPeriodId": 8, "home": {"teamId": 1, "rosterForCurrentScoringPeriod": {"entries": [entry(1, 3, 2, "X", 2)]}}, "away": {}}]}
        out = SB.past_lineups(self.cfg, {}, 8, 100, 2, {}, fetch=fetch)
        self.assertEqual(list(out), ["1"])


if __name__ == "__main__":
    unittest.main()


class WeekGamesTest(unittest.TestCase):
    def test_each_day_of_the_matchup(self):
        import scoreboard as SBD
        games = {1: {"10": [{"date": 100, "homeProTeamId": 1, "awayProTeamId": 2}], "12": [{"date": 300, "homeProTeamId": 3, "awayProTeamId": 1}]},
                 2: {"10": [{"date": 100, "homeProTeamId": 1, "awayProTeamId": 2}]}}
        abbr = {1: "BUF", 2: "NYR", 3: "DET"}
        ws = SBD.week_games(games, abbr, 10, 12)
        self.assertEqual(ws["BUF"], [[100, "NYR", 1], 0, [300, "DET", 0]])
        self.assertEqual(ws["NYR"], [[100, "BUF", 0], 0, 0])
