"""Taking more chances when you're behind (core.BEHIND) and counting the opponent's streams in the matchup read
(scout.opponent_upside -> gameplan risk). User, 2026-11-27, after the Scout tab was dropped: "I like the idea of having
it on the back end helping it with the risk idea and taking more chances when im behind." """
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core as C          # noqa: E402


def mv(**o):
    m = {"g": "F", "ir": False, "net": 0.6, "gain": 0.6, "ca": 2, "cd": 0}
    m.update(o)
    return m


class Behind(unittest.TestCase):
    def test_small_move_that_adds_games_is_kept_when_well_behind(self):
        risk = {"lead": -15.0, "sd": 15.0, "p": 0.16, "p_show": 0.16}
        self.assertTrue(C.behind_keep(mv(), risk))
        self.assertIn("16% to win", C.behind_note(mv(), risk))

    def test_nearly_lost_week_a_half_point_move_cannot_save(self):
        # 25 points down: 0.6 points and two games move the win chance under a point, so nothing is added
        self.assertFalse(C.behind_keep(mv(), {"lead": -25.0, "sd": 15.0, "p": 0.05}))

    def test_not_when_the_week_is_close_or_won(self):
        self.assertFalse(C.behind_keep(mv(), {"lead": -2.0, "sd": 15.0, "p": 0.45}))
        self.assertFalse(C.behind_keep(mv(), {"lead": 25.0, "sd": 15.0, "p": 0.95}))

    def test_too_small_ir_or_no_read(self):
        risk = {"lead": -15.0, "sd": 15.0, "p": 0.16}
        self.assertFalse(C.behind_keep(mv(net=0.2), risk))
        self.assertFalse(C.behind_keep(mv(ir=True), risk))
        self.assertFalse(C.behind_keep(mv(), None))

    def test_a_move_that_only_swaps_games_does_not_help(self):
        # same games in as out and almost no points: no extra swing, win chance barely moves
        risk = {"lead": -15.0, "sd": 15.0, "p": 0.16}
        self.assertFalse(C.behind_keep(mv(ca=1, cd=1, gain=0.3, net=0.3), risk))

    def test_note_quotes_the_number_today_shows(self):
        risk = {"lead": -25.0, "sd": 15.0, "p": 0.04, "p_show": 0.07}
        self.assertIn("7% to win", C.behind_note(mv(), risk))


if __name__ == "__main__":
    unittest.main()
