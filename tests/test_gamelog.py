import unittest

import gamelog as GL

SCHED = {"settings": {"proTeams": [
    {"id": 9, "abbrev": "DAL", "proGamesByScoringPeriod": {
        "50": [{"id": 401892737, "date": 1000, "homeProTeamId": 9, "awayProTeamId": 20}],
        "52": [{"id": 401892800, "date": 3000, "homeProTeamId": 4, "awayProTeamId": 9}],
        "60": [{"id": 401892900, "date": 9000, "homeProTeamId": 9, "awayProTeamId": 4}]}},
    {"id": 20, "abbrev": "TB", "proGamesByScoringPeriod": {
        "50": [{"id": 401892737, "date": 1000, "homeProTeamId": 9, "awayProTeamId": 20}]}},
    {"id": 4, "abbrev": "CHI", "proGamesByScoringPeriod": {}}]}}

# shapes copied from a real ESPN response (statSplitTypeId 5 = one scoring day)
SKATER = {"id": 1, "defaultPositionId": 2, "proTeamId": 9, "stats": [
    {"statSplitTypeId": 0, "id": "002027", "appliedTotal": 40, "stats": {"30": 18}},
    {"statSplitTypeId": 5, "scoringPeriodId": 50, "externalId": "401892737", "proTeamId": 9, "appliedTotal": 2.3,
     "stats": {"13": 0.0, "14": 2.0, "26": 1423.0, "29": 3.0, "30": 1.0, "31": 0.0, "32": 0.0, "38": 0.0}},
    {"statSplitTypeId": 5, "scoringPeriodId": 52, "proTeamId": 9, "appliedTotal": 4.6,
     "stats": {"13": 2.0, "14": 0.0, "26": 1100.0, "29": 5.0, "30": 1.0, "31": 1.0, "32": 0.0, "38": 1.0}},
    {"statSplitTypeId": 5, "scoringPeriodId": 51, "proTeamId": 9, "appliedTotal": 0, "stats": {"30": 0.0}}]}
GOALIE = {"id": 2, "defaultPositionId": 5, "proTeamId": 20, "stats": [
    {"statSplitTypeId": 5, "scoringPeriodId": 50, "externalId": "401892737", "proTeamId": 20, "appliedTotal": 5.0,
     "stats": {"1": 1.0, "3": 27.0, "4": 2.0, "6": 25.0, "7": 0.0, "8": 3600.0, "30": 1.0}}]}


class GameLog(unittest.TestCase):
    def setUp(self):
        self.gi, self.abbr, self.by_tp = GL.game_index(SCHED)

    def test_skater_rows_newest_first_with_opponent(self):
        rows = GL.parse_player(SKATER, self.gi, self.abbr, self.by_tp)
        self.assertEqual(len(rows), 2)                       # the day with no game is skipped
        self.assertEqual(rows[0], [3000, "CHI", 0, 4.6, 2, 0, 5, 1, 0, 1100, 1])   # found by team + day (no externalId)
        self.assertEqual(rows[1], [1000, "TB", 1, 2.3, 0, 2, 3, 0, 0, 1423, 0])

    def test_last_season_and_future_dates_dropped(self):
        old = {"id": 3, "defaultPositionId": 2, "proTeamId": 9, "stats": [
            {"statSplitTypeId": 5, "seasonId": 2026, "scoringPeriodId": 60, "proTeamId": 9, "appliedTotal": 3,
             "stats": {"30": 1}},
            {"statSplitTypeId": 5, "seasonId": 2027, "scoringPeriodId": 60, "proTeamId": 9, "appliedTotal": 3,
             "stats": {"30": 1}}]}
        self.assertEqual(GL.parse_player(old, self.gi, self.abbr, self.by_tp, 2027, 5000), [])

    def test_goalie_row(self):
        rows = GL.parse_player(GOALIE, self.gi, self.abbr, self.by_tp)
        self.assertEqual(rows, [[1000, "DAL", 0, 5, 1, 2, 25, 27, 0, 3600]])

    def test_next_game(self):
        nx = GL.next_games(SCHED, 2000)
        self.assertEqual(nx["DAL"], [3000, "CHI", 0])
        self.assertEqual(nx["CHI"], [3000, "DAL", 1])
        self.assertNotIn("TB", nx)

    def test_build_survives_espn_failure(self):
        GL_fetch = GL.fetch
        GL.fetch = lambda cfg, ids: []
        try:
            out = GL.build({"season": 2027, "league": 1}, {"schedules": SCHED}, {"mine": [{"id": 1}], "fas": [], "teams": []}, 0)
        finally:
            GL.fetch = GL_fetch
        self.assertEqual(out["p"], {})


if __name__ == "__main__":
    unittest.main()
