"""League settings come from the platform (platforms/espn.py -> league.py), never from constants in the model."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import analyze as A        # noqa: E402
import core as C           # noqa: E402
import gameplan as GP      # noqa: E402
import league as L         # noqa: E402
import longterm as LT      # noqa: E402
import platforms           # noqa: E402
import streams as STR      # noqa: E402
from platforms.espn import settings_from   # noqa: E402

THIS_LEAGUE = {"settings": {
    "name": "Test League",
    "rosterSettings": {"lineupSlotCounts": {"0": 0, "1": 0, "2": 0, "3": 9, "4": 5, "5": 2, "6": 1, "7": 4, "8": 1},
                       "lineupLocktimeType": "INDIVIDUAL_GAME"},
    "scoringSettings": {"scoringType": "H2H_POINTS", "scoringItems": [
        {"statId": 13, "points": 2.0}, {"statId": 14, "points": 1.0},
        {"statId": 1, "points": 4.0, "pointsOverrides": {"5": 4.0}}]},
    "acquisitionSettings": {"matchupAcquisitionLimit": 7, "acquisitionLimit": -1, "waiverHours": 24},
    "scheduleSettings": {"matchupPeriods": {"1": [1], "15": [15, 16]}}}}


def league_with(**kw):
    import copy
    lg = copy.deepcopy(THIS_LEAGUE)
    for k, v in kw.items():
        lg["settings"][k].update(v)
    return lg


class Settings(unittest.TestCase):
    def tearDown(self):
        L.reset()

    def test_this_league_reads_as_the_defaults(self):
        s = settings_from(THIS_LEAGUE, "557638258")
        self.assertEqual(s.lineup, {"F": 9, "D": 5, "UTIL": 1, "G": 2})
        self.assertEqual((s.bench, s.ir), (4, 1))
        self.assertEqual(s.lineup, L.DEFAULT.lineup)
        self.assertEqual((s.goal_points(), s.win_points()), (2.0, 4.0))
        self.assertEqual(s.moves["weekly"], 7)
        self.assertIsNone(s.moves["season"])
        self.assertEqual(s.matchup_days(15), 14)
        self.assertIsNone(s.approx)

    def test_position_slots_count_as_forwards_and_say_so(self):
        lg = league_with(rosterSettings={"lineupSlotCounts": {"0": 2, "1": 2, "2": 2, "3": 0, "4": 4, "5": 2, "6": 1,
                                                              "7": 5, "8": 2}})
        s = settings_from(lg)
        self.assertEqual(s.lineup, {"F": 6, "D": 4, "UTIL": 1, "G": 2})
        self.assertIn("C/LW/RW", s.approx)
        self.assertEqual(A.slot_name(0), "F")              # a C slot is a lineup slot, not injured reserve
        self.assertEqual(A.slot_name(2), "F")

    def test_unreadable_or_odd_lineups_are_refused(self):
        with self.assertRaises(ValueError):
            settings_from({"settings": {}})
        with self.assertRaises(ValueError):
            settings_from(league_with(rosterSettings={"lineupSlotCounts": {"3": 9, "4": 5}}))   # no goalies

    def test_scoring_overrides_by_position(self):
        lg = league_with(scoringSettings={"scoringItems": [{"statId": 13, "points": 2.0, "pointsOverrides": {"4": 3.0}}]})
        s = settings_from(lg)
        self.assertEqual(s.goal_points("F"), 2.0)
        self.assertEqual(s.goal_points("D"), 3.0)

    def test_move_limits(self):
        per_day = settings_from(league_with(acquisitionSettings={"matchupAcquisitionLimit": 1,
                                                                 "matchupLimitPerScoringPeriod": True}))
        self.assertEqual((per_day.moves["per_day"], per_day.moves["weekly"]), (1, None))
        none = settings_from(league_with(acquisitionSettings={"matchupAcquisitionLimit": -1}))
        self.assertTrue(none.moves["unlimited"])
        capped = settings_from(league_with(acquisitionSettings={"acquisitionLimit": 40}))
        self.assertEqual(capped.moves["season"], 40)

    def test_install_changes_the_lineup_everywhere(self):
        self.assertEqual(C.day_value([1.0] * 12, [1.0] * 7, [1.0] * 3), 17)
        L.install(settings_from(league_with(rosterSettings={"lineupSlotCounts": {"3": 6, "4": 4, "5": 1, "6": 2}})))
        self.assertIs(C.SLOTS, L.SLOTS)
        self.assertEqual(C.day_value([1.0] * 12, [1.0] * 7, [1.0] * 3), 6 + 4 + 2 + 1)
        self.assertEqual(STR.day_value([("F", 1.0)] * 12 + [("D", 1.0)] * 7 + [("G", 1.0)] * 3), 13)
        c = GP._counts([("F", 1.0)] * 8 + [("D", 1.0)] * 4)
        self.assertEqual((c["F"], c["D"], c["U"]), (6, 4, 2))
        L.reset()
        self.assertEqual(C.day_value([1.0] * 12, [1.0] * 7, [1.0] * 3), 17)

    def test_summary_and_page_data(self):
        L.install(settings_from(THIS_LEAGUE))
        self.assertIn("9 F, 5 D, 1 UTIL, 2 G", L.summary())
        self.assertTrue(L.page_data()["known"])
        L.install(L.DEFAULT, known=False, note="KeyError")
        self.assertFalse(L.page_data()["known"])
        self.assertIn("not read", L.summary())


class Adapters(unittest.TestCase):
    def test_espn_by_default_and_others_not_built(self):
        self.assertEqual(platforms.get({}).name, "espn")
        with self.assertRaises(NotImplementedError):
            platforms.get({"platform": "yahoo"}).fetch_all()
        with self.assertRaises(ValueError):
            platforms.get({"platform": "sleeper"})


class PerDayLimit(unittest.TestCase):
    """Leagues that allow N adds a day: the plan never stacks more than N on one day (this league: weekly limit)."""
    def test_plan_spreads_moves_over_days(self):
        from tests.test_plan_list import DAYS, fake_inputs, player
        roster = [(player(100 + i, f"Solid Forward{i}", out=2.0), [2.0] * 4, None) for i in range(9)]
        roster += [(player(200 + i, f"Weak{i}", out=0.2), [0.2] * 4, 1.0) for i in range(2)]
        roster += [(player(300 + i, f"D{i}", grp="D", out=2.0), [2.0] * 4, None) for i in range(5)]
        fas = [(player(1, "Hot One", out=3.5), [3.5] * 4), (player(2, "Hot Two", out=3.4), [3.4] * 4)]

        def run(per_day):
            with mock.patch.object(C, "build_inputs", return_value=fake_inputs(roster, fas)), \
                    mock.patch.object(C, "cost", return_value=0.0), mock.patch.object(LT, "assess", return_value=None):
                return C.plan([], [], None, 4, DAYS, {}, {}, 7, {}, reasons=False, per_day=per_day)["moves"]
        free = run(None)
        self.assertEqual([m["t"] for m in free], [0, 0])
        capped = run(1)
        self.assertEqual(len(capped), 2)
        self.assertEqual(sorted(m["t"] for m in capped), [0, 1])


if __name__ == "__main__":
    unittest.main()
