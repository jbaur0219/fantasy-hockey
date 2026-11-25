"""Review of the move optimizer (core.py), 2026-11-24, reviewer A.

Two kinds of tests:
  - rule tests that pass today and lock in the product rules (claude/product-rules.md);
  - bug tests marked @unittest.expectedFailure ("BUG A<n>", see the review notes) that assert the CORRECT behaviour.
    Remove the decorator when the fix lands.
"""
import random
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import core as C                                         # noqa: E402
import longterm as LT                                    # noqa: E402
from test_plan_list import DAYS, fake_inputs, player     # noqa: E402


def run(roster, fas, prev=None, moves_left=7, keep_ids=(), ir_free=0, cost=0.0, days=None):
    days = days or DAYS
    ents = fake_inputs(roster, fas)
    with mock.patch.object(C, "build_inputs", return_value=ents), \
            mock.patch.object(C, "cost", return_value=cost), \
            mock.patch.object(LT, "assess", return_value=None):
        return C.plan([], [], None, len(days), days, {}, {}, moves_left, {}, prev=prev, reasons=False,
                      keep_ids=keep_ids, ir_free=ir_free)


def pairs(res):
    return [(m["add"]["n"], m["drop"]["n"]) for m in res["moves"]]


def solid_f(n, vals=None):
    return [(player(100 + i, f"Solid F{i}", out=2.0), list(vals or [2.0] * 4), None) for i in range(n)]


def solid_d(n, vals=None):
    return [(player(300 + i, f"Solid D{i}", grp="D", out=2.0), list(vals or [2.0] * 4), None) for i in range(n)]


class Bars(unittest.TestCase):
    def test_bar_values(self):
        self.assertEqual((C.SHOW_NET, C.LATE_NET, C.LATE_DAYS, C.HOLD_SLACK), (1.0, 0.5, 3, 0.5))
        self.assertEqual([C.show_bar(t, 7) for t in range(7)], [1.0, 1.0, 1.0, 1.0, 0.5, 0.5, 0.5])   # Mon..Sun
        self.assertEqual(C.show_bar(0, 1), 0.5)                    # one day left: the late bar

    def test_every_shown_move_clears_its_bar_and_is_never_optional(self):
        rnd = random.Random(7)
        for _ in range(150):
            ro = solid_f(8, [rnd.choice([0, 2.0]) for _ in range(4)])
            ro += [(player(200 + j, f"Weak{j}", out=0.5), [rnd.choice([0, 0.4]) for _ in range(4)],
                    rnd.choice([1.0, 1.5, 2.0])) for j in range(3)]
            ro += solid_d(5)
            fas = [(player(1 + k, f"Stream{k}"), [rnd.choice([0, 1.0, 2.0, 2.6]) for _ in range(4)]) for k in range(4)]
            res = run(ro, fas, moves_left=rnd.choice([1, 2, 7]))
            bars = {b[0]["id"]: b[2] for b in ro}
            for m in res["moves"]:
                bar = C.show_bar(m["t"], 4)
                need = bars[m["drop"]["id"]] if bars[m["drop"]["id"]] > 1.0 else bar
                self.assertGreaterEqual(round(m["net"], 1), max(bar, need) - 1e-9, m)
                self.assertNotEqual(m["conf"], "optional")
            self.assertLessEqual(len(res["moves"]), 7)
            adds = [m["add"]["id"] for m in res["moves"]]
            drops = [m["drop"]["id"] for m in res["moves"]]
            self.assertEqual(len(adds), len(set(adds)))
            self.assertEqual(len(drops), len(set(drops)))


class Limits(unittest.TestCase):
    def setUp(self):
        self.ro = solid_f(8) + [(player(200, "Weak One", out=0.1), [0.1] * 4, 1.0),
                                (player(201, "Weak Two", out=0.1), [0.1] * 4, 1.0)]
        self.fas = [(player(1, "Add One"), [2.0] * 4), (player(2, "Add Two"), [1.9] * 4)]

    def test_no_moves_left_no_moves(self):
        self.assertEqual(run(self.ro, self.fas, moves_left=0)["moves"], [])

    def test_move_limit_is_respected_even_with_a_longer_previous_plan(self):
        prev = [(1, DAYS[0], 200), (2, DAYS[0], 201)]
        self.assertEqual(len(run(self.ro, self.fas, prev=prev, moves_left=1)["moves"]), 1)

    def test_no_moves_when_every_day_is_locked(self):
        fas = [(player(1, "Add One"), [0.0] * 4)]            # locked days have no value for anyone
        self.assertEqual(run(self.ro, fas)["moves"], [])


class Stickiness(unittest.TestCase):
    """Suspicion (3): a planned move is not kept when its drop is now on your Keep list or its day has locked."""

    def setUp(self):
        self.ro = solid_f(8) + [(player(200, "Zach Benson", out=1.0), [1.0] * 4, 1.0)]
        self.fas = [(player(1, "Steady Add"), [1.2] * 4)]        # +0.8: only on the list by HOLD_SLACK

    def test_kept_move_dropped_when_the_player_is_now_kept(self):
        prev = [(1, DAYS[0], 200)]
        self.assertEqual(pairs(run(self.ro, self.fas, prev=prev)), [("Steady Add", "Zach Benson")])
        self.assertEqual(run(self.ro, self.fas, prev=prev, keep_ids={200})["moves"], [])

    def test_kept_move_not_held_on_a_locked_day(self):
        days = ["Mon Nov 23", "Tue Nov 24", "Wed Nov 25", "Thu Nov 26", "Fri Nov 27", "Sat Nov 28", "Sun Nov 29"]
        ro = solid_f(8, [2.0] * 7) + [(player(200, "Zach Benson", out=1.0), [1.0] * 7, 1.0)]
        fas = [(player(1, "Steady Add"), [0.0] + [1.1] * 6)]       # Monday has locked; +0.6 from Tuesday on
        self.assertEqual(pairs(run(ro, [(player(1, "Steady Add"), [1.1] * 7)], prev=[(1, days[0], 200)], days=days)),
                         [("Steady Add", "Zach Benson")])          # held by HOLD_SLACK while Monday is open
        self.assertEqual(run(ro, fas, prev=[(1, days[0], 200)], days=days)["moves"], [])


class InjuredReserve(unittest.TestCase):
    def test_ir_move_costs_nothing_and_uses_a_move(self):
        ro = solid_f(8) + [(player(150, "Hurt Star", out=3.0, inj="OUT"), [0.0] * 4, None)]
        fas = [(player(1, "Fill In"), [1.5] * 4), (player(2, "Second"), [1.4] * 4)]
        res = run(ro, fas, ir_free=1, cost=5.0, moves_left=1)
        self.assertEqual(len(res["moves"]), 1)
        self.assertEqual((res["moves"][0]["drop"]["n"], res["moves"][0]["ir"], res["moves"][0]["cost"]),
                         ("Hurt Star", True, 0.0))

    def test_kept_injured_player_can_still_go_to_ir(self):
        # Keep means "never drop him"; moving him to IR is not a drop, so the Keep list does not block it.
        ro = solid_f(8) + [(player(150, "Hurt Star", out=3.0, inj="OUT"), [0.0] * 4, None)]
        res = run(ro, [(player(1, "Fill In"), [1.5] * 4)], ir_free=1, keep_ids={150})
        self.assertEqual([(m["drop"]["n"], m["ir"]) for m in res["moves"]], [("Hurt Star", True)])

    def test_only_as_many_ir_moves_as_open_spots(self):
        ro = solid_f(7) + [(player(150 + i, f"Hurt{i}", out=3.0, inj="OUT"), [0.0] * 4, None) for i in range(2)]
        fas = [(player(1, "Fill A"), [1.5] * 4), (player(2, "Fill B"), [1.5] * 4)]
        self.assertEqual(sum(1 for m in run(ro, fas, ir_free=1)["moves"] if m["ir"]), 1)


class Bugs(unittest.TestCase):
    def test_goalie_add_can_replace_a_spare_defenseman(self):
        # BUG A1: drop_options() lets a goalie add drop a G or an F, never a D. Here your 6th defenseman sits on the
        # bench every day (5 D slots full, UTIL taken by a forward) and one goalie slot is empty all week: adding a
        # 3.0-a-day goalie for him is worth +12, but the plan suggests nothing.
        ro = solid_f(10) + solid_d(5) + [(player(310, "Spare D", grp="D", out=0.3), [0.3] * 4, 1.0),
                                         (player(400, "Only Goalie", grp="G"), [2.0] * 4, None)]
        res = run(ro, [(player(1, "Free Goalie", grp="G"), [3.0] * 4)])
        self.assertEqual(pairs(res), [("Free Goalie", "Spare D")])

    @unittest.expectedFailure
    def test_streamer_can_be_dropped_for_a_later_stream(self):
        # BUG A2: drops only come from your current roster, so the plan can never stream a spot twice (add A Monday,
        # drop A for B on Wednesday). One open spot, A plays Mon/Tue, B plays Wed/Thu: the chain is worth +8, the
        # plan finds +4 and leaves a move unused.
        ro = solid_f(8) + [(player(200, "Weak", out=0.5), [0.0] * 4, 1.0)]
        fas = [(player(1, "Stream A"), [2.0, 2.0, 0, 0]), (player(2, "Stream B"), [0, 0, 2.0, 2.0])]
        res = run(ro, fas)
        self.assertAlmostEqual(res["gain"], 8.0, places=1)
        self.assertIn(("Stream B", "Stream A"), pairs(res))

    def test_benched_player_is_considered_as_a_drop(self):
        # BUG A3: drop_options() keeps the DROPS_PER cheapest drops by raw value (his own points), not by what he adds
        # to your lineup. Yama's 3 points all sit on the bench (forwards full on his days), but nine cheaper
        # players who DO play for you rank ahead of him, so he is never tried: the plan drops a one-game forward
        # (+1.6) instead of Yama (+2.0).
        ro = solid_f(8, [0, 0, 2.0, 2.0])
        ro += [(player(120 + i, f"Tue Only{i}", out=2.4), [0, 0, 2.4, 0], 1.0) for i in range(2)]
        ro += [(player(130 + i, f"Thu Only{i}", out=2.4), [0, 0, 0, 2.4], 1.0) for i in range(2)]
        ro += [(player(200, "Kailer Yamamoto", out=1.5), [0, 0, 1.5, 1.5], 1.0)]
        ro += [(player(300 + i, f"Cheap D{i}", grp="D", out=0.3), [0, 0, 0.3, 0.3], 1.0) for i in range(5)]
        res = run(ro, [(player(1, "Upgrade", out=3.0), [0, 0, 3.0, 3.0])], moves_left=1)
        self.assertEqual(pairs(res), [("Upgrade", "Kailer Yamamoto")])
        self.assertAlmostEqual(res["moves"][0]["net"], 2.0, places=1)

    def test_reason_never_shows_identical_per_game_numbers(self):
        # BUG A4: headline() quotes per_game() (season outlook), not the per-game values the plan used (opponent
        # strength and home ice included). Two 1.5 players, same 3 games, Brown's opponents are weak: +1.8, and the
        # reason reads "Brown projects 1.5 pts a game to Smith's 1.5" (the rule: never explain a move with stats
        # that make the two players look identical).
        ro = solid_f(8) + [(player(200, "Will Smith", tm="SJ", out=1.5, ppg=1.5, rec=1.5), [1.2, 0, 1.2, 1.2], 1.0)]
        fas = [(player(1, "Connor Brown", tm="NJ", out=1.5, ppg=1.5, rec=1.5), [1.8, 0, 1.8, 1.8])]
        mv = run(ro, fas)["moves"][0]
        self.assertAlmostEqual(mv["net"], 1.8, places=1)
        self.assertNotIn("1.5 pts a game to Smith's 1.5", mv["why1"])
        self.assertIn("1.8", mv["why1"])


if __name__ == "__main__":
    unittest.main()
