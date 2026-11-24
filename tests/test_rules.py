#!/usr/bin/env python3
"""Small checks of the rules that matter most. Run:  python -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core as C          # noqa: E402
import dashboard as D     # noqa: E402
import goalies as GL      # noqa: E402
import starters as S      # noqa: E402


def sk(n, grp="F", out=1.8, tm="AAA", inj="ACTIVE", **kw):
    p = {"id": n, "n": n, "grp": grp, "pos": grp, "tm": tm, "out": out, "inj": inj, "ppg": out, "rec": out, "gp": 20,
         "slot": "F", "sp": 0.6}
    p.update(kw)
    return p


class DayLock(unittest.TestCase):
    def test_day_locks_at_first_puck(self):
        clock = {"dates": ["2026-11-17", "2026-11-18"], "lock": [1000, None]}
        self.assertFalse(D.day_locked(clock, 0, 999))
        self.assertTrue(D.day_locked(clock, 0, 1000))

    def test_off_day_locks_when_the_date_passes(self):
        clock = {"dates": ["2000-01-01"], "lock": [None]}
        self.assertTrue(D.day_locked(clock, 0, 10 ** 13))


class Lineup(unittest.TestCase):
    def test_nine_f_five_d_one_util_two_g(self):
        v = C.day_value([1.0] * 12, [1.0] * 7, [3.0, 2.0, 1.0])
        self.assertAlmostEqual(v, 9 + 5 + 1 + 5)


class Cost(unittest.TestCase):
    def test_injured_drop_costs_nothing(self):
        self.assertEqual(C.cost(sk("a", inj="OUT", out=3.0), sk("b", out=1.0), {"AAA": 4}), 0.0)

    def test_dropping_the_better_player_costs_points(self):
        nxt = {"AAA": 10, "BBB": 10}           # games over the three weeks after this matchup
        good, stream = sk("good", out=2.4, tm="AAA"), sk("stream", out=1.5, tm="BBB")
        self.assertGreater(C.cost(good, stream, nxt), 2.0)
        self.assertEqual(C.cost(stream, good, nxt), 0.0)

    def test_next_week_schedule_counts(self):
        a, b = sk("a", out=1.8, tm="AAA"), sk("b", out=1.8, tm="BBB")
        self.assertGreater(C.cost(a, b, {"AAA": 11, "BBB": 9}), C.cost(a, b, {"AAA": 9, "BBB": 11}))

    def test_hot_streak_does_not_hide_the_long_term_cost(self):
        fut = {"AAA": 10, "BBB": 10}
        cold = sk("cold", out=1.9, tm="AAA", rec=0.7)
        hot = sk("hot", out=1.6, tm="BBB", rec=3.0)
        self.assertGreater(C.cost(cold, hot, fut), 0.5)

    def test_widely_rostered_drops_cost_more(self):
        fut = {"AAA": 10, "BBB": 10}
        b = sk("b", out=1.5, tm="BBB")
        self.assertGreater(C.cost(sk("a", out=2.0, own=90.0), b, fut), C.cost(sk("a", out=2.0, own=10.0), b, fut))


class LongTerm(unittest.TestCase):
    def test_verdict_and_plain_reasons(self):
        import longterm as LT
        fut = {"AAA": 10, "BBB": 11}
        y = sk("Trevor Zegras", out=1.73, tm="AAA", own=60.0, gx=-2.6, rl="F1 - PP1", tr=-1.5)
        x = sk("Frank Nazar", out=1.68, tm="BBB", own=25.0, gx=4.2, rl="F2 - PP1", tr=1.4)
        r = LT.assess(y, x, fut)
        self.assertIn(r["v"], ("none", "small", "real"))
        text = " ".join(r["lines"])
        self.assertIn("expect fewer", text)
        self.assertIn("bounce back", text)
        self.assertIn("60%", text)

    def test_injured_drop_has_no_long_term_cost(self):
        import longterm as LT
        r = LT.assess(sk("a", inj="OUT", out=3.0), sk("b"), {"AAA": 10})
        self.assertEqual(r["v"], "none")


class Settings(unittest.TestCase):
    def test_matchup_length_and_moves(self):
        lg = {"settings": {"scheduleSettings": {"matchupPeriods": {"8": [8], "20": [20, 21]}},
                           "acquisitionSettings": {"matchupAcquisitionLimit": 1, "matchupLimitPerScoringPeriod": True}}}
        self.assertEqual(D.matchup_length(lg, 8), 7)
        self.assertEqual(D.matchup_length(lg, 20), 14)
        self.assertEqual(D.move_limit(lg, 7), 7)
        self.assertEqual(D.move_limit(lg, 14), 14)


class Goalies(unittest.TestCase):
    def test_three_goalies_one_day_start_best_two(self):
        S.STATE["by_team"] = {}
        D.start_prob = lambda p, st: p["spx"]
        games = {i: {"50": [{"date": 10 ** 13, "homeProTeamId": i, "awayProTeamId": 99}]} for i in (1, 2, 3)}
        abbr = {1: "AAA", 2: "BBB", 3: "CCC", 99: "ZZZ"}
        mine = [{"name": n, "group": "G", "slot": 5, "team": abbr[i], "team_id": i, "outlook": o, "gp": 10, "svp": None,
                 "spx": sp} for n, i, o, sp in (("A", 1, 3.0, 0.8), ("B", 2, 2.0, 0.8), ("C", 3, 3.0, 0.3))]
        rows = {g["p"]["name"]: g["rows"][0] for g in GL.build(mine, 50, games, abbr, {}, 0, 1)}
        self.assertEqual(rows["A"]["verdict"], "START")
        self.assertEqual(rows["B"]["verdict"], "START")
        self.assertEqual(rows["C"]["verdict"], "BENCH")


class NotStarting(unittest.TestCase):
    """A goalie whose team has another goalie in net today carries a flag so the page shows no projection for him."""

    def test_flag(self):
        import starters as S
        old = S.STATE["by_team"]
        try:
            S.STATE["by_team"] = {"VGK": {"name": "Akira Schmid", "status": "Confirmed"},
                                  "EDM": {"name": "Stuart Skinner", "status": "Likely"}}
            hill = {"group": "G", "team": "VGK", "name": "Aiden Hill"}
            self.assertEqual(S.not_starting(hill), 1)                                            # other goalie confirmed
            self.assertEqual(S.not_starting({"group": "G", "team": "VGK", "name": "Akira Schmid"}), 0)
            self.assertEqual(S.not_starting({"group": "G", "team": "EDM", "name": "Tristan Jarry"}), 2)   # expected, not confirmed
            self.assertEqual(S.not_starting({"group": "G", "team": "TOR", "name": "Anyone"}), 0)  # team unknown: leave alone
            self.assertEqual(S.not_starting({"group": "D", "team": "VGK", "name": "Skater"}), 0)  # skaters never flagged
        finally:
            S.STATE["by_team"] = old


if __name__ == "__main__":
    unittest.main()
