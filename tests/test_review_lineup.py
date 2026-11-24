#!/usr/bin/env python3
"""Review B (2026-11-24): lineup and per-day value logic.

Rule tests pass today. Tests marked @unittest.expectedFailure ('BUG B<n>') assert the CORRECT behaviour for a bug that
was reproduced; see /home/claude/review/lineup.md (and the rules doc) for the fix. When a bug is fixed, remove its
decorator so the test guards it."""
import random
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core as C          # noqa: E402
import dashboard as D     # noqa: E402
import gameplan as GP     # noqa: E402
import streams as STR     # noqa: E402

ET = ZoneInfo("America/New_York")
ABBR = {1: "AAA", 2: "BBB"}


def ms(*a):
    return int(datetime(*a, tzinfo=ET).timestamp() * 1000)


def game_on(y, m, d, h=19):
    return [{"date": ms(y, m, d, h), "homeProTeamId": 1, "awayProTeamId": 2}]


def goalie(name="Goalie A", sp=0.3, slot="G", tm="AAA", out=5.0, inj="ACTIVE"):
    return {"id": name, "n": name, "grp": "G", "pos": "G", "tm": tm, "out": out, "inj": inj, "sp": sp, "gp": 10,
            "svp": None, "slot": slot, "ppg": out, "rec": None}


def skater(name, grp="F", tm="AAA", out=2.0, inj="ACTIVE", slot="F"):
    return {"id": name, "n": name, "grp": grp, "pos": grp, "tm": tm, "out": out, "inj": inj, "ppg": out, "rec": out,
            "gp": 20, "slot": slot}


def two_day_games():
    """AAA plays on scoring periods 50 (Tue Nov 24) and 51 (Wed Nov 25), both 7 PM ET."""
    g = {"50": game_on(2026, 11, 24), "51": game_on(2026, 11, 25)}
    return {1: g, 2: g}


# ---------------------------------------------------------------------------
# Rules that hold today
# ---------------------------------------------------------------------------
class LineupRules(unittest.TestCase):
    def test_core_and_streams_day_value_agree(self):
        rnd = random.Random(7)
        for _ in range(200):
            F = [round(rnd.uniform(0, 4), 2) for _ in range(rnd.randint(0, 14))]
            Dn = [round(rnd.uniform(0, 4), 2) for _ in range(rnd.randint(0, 8))]
            G = [round(rnd.uniform(0, 6), 2) for _ in range(rnd.randint(0, 4))]
            act = [("F", v) for v in F] + [("D", v) for v in Dn] + [("G", v) for v in G]
            self.assertAlmostEqual(C.day_value(F, Dn, G), STR.day_value(act), places=6)

    def test_util_takes_best_leftover_skater_never_a_goalie(self):
        act = [("F", 2.0)] * 9 + [("D", 1.0)] * 5 + [("D", 1.5), ("F", 0.5)] + [("G", 3.0)] * 3
        self.assertAlmostEqual(STR.day_value(act), 18 + 5 + 1.5 + 6)

    def test_confirmed_out_goalie_scores_nothing_and_the_other_two_start(self):
        act = [("G", 0.0), ("G", 2.0), ("G", 1.0)]          # 0.0 = another goalie confirmed in net today
        self.assertAlmostEqual(STR.day_value(act), 3.0)

    def test_no_value_once_the_days_first_puck_has_dropped(self):
        game = STR.make_game_fn(ABBR, two_day_games(), 50, ms(2026, 11, 24, 19, 5))
        v = STR._base_values(skater("a"), game, 2, {}, {})
        self.assertEqual(v[0], 0.0)                          # Tuesday is locked: nobody can be added for it
        self.assertGreater(v[1], 0.0)

    def test_day_to_day_still_projected_out_is_not(self):
        game = STR.make_game_fn(ABBR, two_day_games(), 50, ms(2026, 11, 24, 9))
        full = STR._base_values(skater("a"), game, 1, {}, {})[0]
        dtd = STR._base_values(skater("a", inj="DAY_TO_DAY"), game, 1, {}, {})[0]
        self.assertAlmostEqual(dtd, STR.DTD * full)
        for st in ("OUT", "INJURY_RESERVE", "SUSPENSION"):
            self.assertEqual(STR._base_values(skater("a", inj=st), game, 1, {}, {}), [0.0])

    def test_confirmed_other_goalie_today_means_zero(self):
        game = STR.make_game_fn(ABBR, two_day_games(), 50, ms(2026, 11, 24, 9))
        st = {"AAA": {"name": "Other Guy", "status": "Confirmed"}}
        v = STR._base_values(goalie(sp=0.8), game, 2, {}, st)
        self.assertEqual(v[0], 0.0)
        self.assertGreater(v[1], 0.0)                          # tomorrow is unknown: his usual share

    def test_ir_spots_open(self):
        lg = {"settings": {"rosterSettings": {"lineupSlotCounts": {"8": 2, "7": 4, "3": 9}}}}
        self.assertEqual(D.ir_free(lg, [{"slot": "IR"}, {"slot": "BN"}]), 1)
        self.assertEqual(D.ir_free(lg, [{"slot": "IR"}, {"slot": "IR"}, {"slot": "IR"}]), 0)
        self.assertEqual(D.ir_free({}, []), 0)

    def test_move_budget_uses_the_leagues_limit_and_says_when_it_cannot(self):
        lg = {"status": {"currentMatchupPeriod": 9},
              "settings": {"acquisitionSettings": {"matchupAcquisitionLimit": 4, "acquisitionLimit": -1}},
              "teams": [{"id": 1, "transactionCounter": {"matchupAcquisitionTotals": {"9": 1}}}]}
        b = D.move_budget(lg, 1, days=7)
        self.assertEqual((b["limit"], b["used"], b["left"], b["known"]), (4, 1, 3, True))
        lg["teams"][0]["transactionCounter"] = {}                  # count missing: the app must say it is unknown
        self.assertFalse(D.move_budget(lg, 1, days=7)["used_known"])
        self.assertFalse(D.move_budget({}, 1, days=7)["known"])
        lg["settings"]["acquisitionSettings"]["matchupAcquisitionLimit"] = -1
        self.assertTrue(D.move_budget(lg, 1, days=7)["unlimited"])

    def test_game_plan_counts_simple_day(self):
        act = [("F", 1.0)] * 8 + [("D", 1.0)] * 5 + [("G", 1.0)] * 2
        self.assertEqual(GP._counts(act), {"F": 8, "D": 5, "G": 2, "U": 0})


# ---------------------------------------------------------------------------
# Bugs (reproduced). Each asserts the correct behaviour.
# ---------------------------------------------------------------------------
class LineupBugs(unittest.TestCase):
    @unittest.expectedFailure
    def test_your_goalie_start_chance_is_not_inflated(self):
        # BUG B1: lineup_goalie floors your G-slot goalies' start chance at 50% (Hill 45% -> 50%, a 30% backup -> 50%).
        # A goalie only scores when he starts, whoever rosters him.
        game = STR.make_game_fn(ABBR, two_day_games(), 50, ms(2026, 11, 24, 9))
        mine = STR._base_values(goalie(sp=0.3), game, 1, {}, {}, lineup_goalie=True)
        fa = STR._base_values(goalie(sp=0.3, slot=None), game, 1, {}, {}, lineup_goalie=False)
        self.assertAlmostEqual(mine[0], fa[0])

    @unittest.expectedFailure
    def test_matchup_projection_is_symmetric(self):
        # BUG B1 (second effect): only your goalies get the floor, so identical rosters do not project to 50%.
        game = STR.make_game_fn(ABBR, two_day_games(), 50, ms(2026, 11, 24, 9))
        team = [goalie(sp=0.3), skater("s1"), skater("s2", grp="D")]
        r = C.matchup_projection(team, [dict(p) for p in team], game, 2, {}, {}, 0.0, 0.0)
        self.assertAlmostEqual(r["proj_me"], r["proj_opp"], places=6)
        self.assertAlmostEqual(r["p_win"], 0.5, places=3)

    @unittest.expectedFailure
    def test_todays_starters_apply_to_today_even_before_espn_rolls_over(self):
        # BUG B2: starters (today's Daily Faceoff page) only apply to day index 0. At 1 AM ET on Wed Nov 25 ESPN can
        # still be on Tuesday's scoring period (day 0, locked), so Wednesday is day 1 and the confirmed other goalie
        # is ignored: the benched goalie gets a projection the Today tab contradicts.
        game = STR.make_game_fn(ABBR, two_day_games(), 50, ms(2026, 11, 25, 1))
        st = {"AAA": {"name": "Other Guy", "status": "Confirmed"}}
        v = STR._base_values(goalie(sp=0.8, slot="BN"), game, 2, {}, st)
        self.assertEqual(v, [0.0, 0.0])

    def test_game_plan_util_counts_a_tenth_forward(self):
        # BUG B3: 10 forwards and 4 defensemen play: 9 F slots + UTIL are full, one D slot is open (1 open, not 2).
        act = [("F", 1.0)] * 10 + [("D", 1.0)] * 4 + [("G", 1.0)] * 2
        c = GP._counts(act)
        self.assertEqual(c["U"], 1)
        rows = GP._day_rows([{"grp": g, "v": [v], "join": 0, "leave": 99} for g, v in act], 1, ["Tue"], None)
        self.assertEqual(rows[0]["open"], 1)

    def test_why_add_sees_the_empty_util_slot(self):
        # BUG B4: 9 F and 5 D play, UTIL is empty; adding a forward fills it, but the reason says
        # "Upgrades a F lineup spot you already fill (no empty slot)".
        ents = [{"p": {}, "grp": "F", "v": [1.0], "join": 0, "leave": 99} for _ in range(9)]
        ents += [{"p": {}, "grp": "D", "v": [1.0], "join": 0, "leave": 99} for _ in range(5)]
        self.assertEqual(STR._fill(ents, {"grp": "F", "v": [1.0]}, {"grp": "G", "v": [0.0]}, 0, 1), (1, 1))

    def test_per_day_move_limit_counts_only_days_left(self):
        # BUG B5: with a per-day limit (1 a day), Saturday morning has 2 days left, so at most 2 adds remain;
        # move_budget says 7 (limit x full matchup) and core.plan has no per-day cap.
        lg = {"status": {"currentMatchupPeriod": 9},
              "settings": {"acquisitionSettings": {"matchupAcquisitionLimit": 1, "matchupLimitPerScoringPeriod": True}},
              "teams": [{"id": 1, "transactionCounter": {"matchupAcquisitionTotals": {"9": 0}}}]}
        self.assertEqual(D.move_budget(lg, 1, days=7, days_left=2)["left"], 2)

    @unittest.expectedFailure
    def test_matchup_days_known_before_any_points(self):
        # BUG B6 (edge, unverified against ESPN): before the first game of a matchup pointsByScoringPeriod can be
        # empty; the fallback 7 * (mp - 1) assumes 7-day matchups from period 0 (off by one if periods start at 1,
        # wrong after any 2-week matchup). The current scoring period is the start when nothing is scored yet.
        self.assertEqual(D.matchup_periods({"home": {}, "away": {}}, 9, 7, sp=57), (57, 63))


if __name__ == "__main__":
    unittest.main()
