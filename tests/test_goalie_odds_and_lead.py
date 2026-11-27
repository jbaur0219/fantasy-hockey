#!/usr/bin/env python3
"""Goalie win chance from the betting line (odds.py) and the "well ahead" check on goalie adds (core.SAFE_WIN).

User, 2026-11-27, about "Add Brossoit, drop Adin Hill" next to "LAK favored, 51% to win": "I don't really love how it's
telling me to add a goalie that isn't favored to win... If I am up a lot and have a good chance to win, I don't need
to pickup a goalie and make a risky move like that." The scoreboard fixture below is the real shape ESPN returned for
LA @ ANA that day (trimmed)."""
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core as C          # noqa: E402
import odds as O          # noqa: E402
import streams as STR     # noqa: E402

ET = ZoneInfo("America/New_York")


def ms(*a):
    return int(datetime(*a, tzinfo=ET).timestamp() * 1000)


LIVE = {"events": [
    {"date": "2026-11-27T21:00Z", "shortName": "LA @ ANA", "competitions": [{
        "competitors": [{"homeAway": "home", "team": {"abbreviation": "ANA"}},
                        {"homeAway": "away", "team": {"abbreviation": "LA"}}],
        "odds": [{"details": "LA -115", "overUnder": 6.5,
                  "moneyline": {"home": {"close": {"odds": "-105"}}, "away": {"close": {"odds": "-115"}}}}]}]},
    {"date": "2026-11-27T21:00Z", "shortName": "VGK @ SJ", "competitions": [{
        "competitors": [{"homeAway": "home", "team": {"abbreviation": "SJ"}},
                        {"homeAway": "away", "team": {"abbreviation": "VGK"}}],
        "odds": [{"moneyline": {"home": {"close": {"odds": "+180"}}, "away": {"close": {"odds": "-218"}}}}]}]},
    {"date": "2026-11-27T18:00Z", "shortName": "TOR @ BOS", "competitions": [{   # under way: ESPN drops the odds
        "competitors": [{"homeAway": "home", "team": {"abbreviation": "BOS"}},
                        {"homeAway": "away", "team": {"abbreviation": "TOR"}}], "odds": []}]},
]}


class Lines(unittest.TestCase):
    def setUp(self):
        O.install(O.parse(LIVE))

    def tearDown(self):
        O.install({})

    def test_parses_the_live_shape_without_vig(self):
        self.assertEqual(len(O.STATE["by_game"]), 2)            # the game under way has no line
        ana = O.STATE["by_game"][("2026-11-27", "ANA", "LA")]
        self.assertAlmostEqual(ana, 0.489, places=3)            # LA a slight favourite, as the game page said

    def test_both_sides_and_aliases(self):
        t = ms(2026, 11, 27, 16)
        self.assertAlmostEqual(O.p_win("ANA", "LA", True, t) + O.p_win("LAK", "ANA", False, t), 1.0)
        self.assertGreater(O.p_win("VGK", "SJ", False, t), 0.65)
        self.assertIsNone(O.p_win("ANA", "LA", True, ms(2026, 11, 28, 16)))   # no line that day

    def test_bad_prices_are_skipped(self):
        self.assertIsNone(O._american("EVEN"))
        self.assertIsNone(O._american("50"))
        self.assertAlmostEqual(O._american("+100"), 0.5)

    def test_goalie_value_uses_the_line_when_there_is_one(self):
        abbr = {25: "ANA", 8: "LA"}
        games = {25: {"60": [{"date": ms(2026, 11, 27, 16), "homeProTeamId": 25, "awayProTeamId": 8}]}}
        games[8] = games[25]
        game = STR.make_game_fn(abbr, games, 60, ms(2026, 11, 27, 9))
        standings = {"ANA": {"pct": 0.60, "gp": 26}, "LAK": {"pct": 0.40, "gp": 22}}   # standings love ANA
        g = {"id": 1, "n": "Laurent Brossoit", "grp": "G", "pos": "G", "tm": "ANA", "out": 3.0, "inj": "ACTIVE",
             "sp": 1.0, "gp": 10, "svp": None, "slot": "G", "ppg": 3.0, "rec": None}
        with_line = STR._base_values(dict(g), game, 1, standings, {})[0]
        O.install({})
        without = STR._base_values(dict(g), game, 1, standings, {})[0]
        self.assertLess(with_line, without)                        # the line says coin flip, not a 60%+ favourite


class WellAhead(unittest.TestCase):
    def mv(self, gain=1.0, ca=2, cd=1, g="G", add_pg=1.0, drop_pg=1.0):
        x = {"tm": "ANA", "grp": "G", "out": add_pg, "sp": 1.0, "ppg": add_pg, "rec": None, "gp": 10}
        y = {"tm": "VGK", "grp": "G", "out": drop_pg, "sp": 1.0, "ppg": drop_pg, "rec": None, "gp": 10}
        return {"g": g, "gain": gain, "ca": ca, "cd": cd, "ir": False, "_xp": x, "_yp": y}

    def test_pure_goalie_stream_is_held_when_the_week_is_won(self):
        risk = {"lead": 25.0, "sd": 18.0, "p": 0.92}
        self.assertTrue(C.ahead_hold(self.mv(), risk, {"ANA": 10, "VGK": 10}))

    def test_close_week_keeps_it(self):
        risk = {"lead": 2.0, "sd": 18.0, "p": 0.55}
        self.assertFalse(C.ahead_hold(self.mv(), risk, {"ANA": 10, "VGK": 10}))

    def test_skater_moves_are_not_touched(self):
        risk = {"lead": 25.0, "sd": 18.0, "p": 0.92}
        self.assertFalse(C.ahead_hold(self.mv(g="F"), risk, {}))

    def test_long_term_upgrade_stays_and_says_why(self):
        risk = {"lead": 25.0, "sd": 18.0, "p": 0.92}
        m = self.mv(add_pg=1.6, drop_pg=0.9)
        fut = {"ANA": 10, "VGK": 8}
        self.assertGreaterEqual(C.lt_edge(m, fut), C.LT_EDGE)
        self.assertFalse(C.ahead_hold(m, risk, fut))
        self.assertIn("weeks after", C.ahead_note(m, risk, fut))

    def test_extra_goalie_games_lower_win_chance_when_ahead(self):
        risk = {"lead": 25.0, "sd": 18.0, "p": 0.92}
        self.assertLess(C.win_change(self.mv(gain=0.0, ca=2, cd=0), risk), 0)


if __name__ == "__main__":
    unittest.main()
