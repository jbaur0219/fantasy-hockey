"""Opponent scouting for the matchup sheet (scout.py, roadmap #2, 2026-11-27): games that count by day, open spots,
adds left, and the best pickups for the other side's open spots. Display only; the plan is never touched."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import league as L            # noqa: E402
import scout as SC            # noqa: E402

NOW = 1_000_000_000_000
H = 3600_000
SP = 50                       # today's scoring period
ME, OPP = 1, 2
ABBR = {10: "TOR", 20: "BOS", 30: "CHI", 40: "VAN"}


def games(plan):
    """plan: {team abbrev: [day offsets from today it plays]} -> ESPN-style proGamesByScoringPeriod (games at 7 PM-ish)."""
    tid = {v: k for k, v in ABBR.items()}
    out = {k: {} for k in ABBR}
    for ab, days in plan.items():
        for d in days:
            out[tid[ab]].setdefault(str(SP + d), []).append({"date": NOW + 6 * H + d * 24 * H,
                                                               "homeProTeamId": tid[ab], "awayProTeamId": 0})
    return out


def pl(i, grp, tm, out=2.0, slot="F", inj="ACTIVE", sp=None):
    p = {"id": i, "n": f"P{i}", "pos": {"F": "C", "D": "D", "G": "G"}[grp], "grp": grp, "tm": tm, "slot": slot,
         "out": out, "inj": inj}
    if sp is not None:
        p["sp"] = sp
    return p


def league(used=None):
    teams = [{"id": ME, "transactionCounter": {"matchupAcquisitionTotals": {"3": 1}}},
             {"id": OPP, "transactionCounter": {"matchupAcquisitionTotals": {"3": used if used is not None else 2}}}]
    return {"status": {"currentMatchupPeriod": 3}, "teams": teams,
            "settings": {"acquisitionSettings": {"matchupAcquisitionLimit": 1, "matchupLimitPerScoringPeriod": True}}}


def sb(today=0, n=3):
    return {"today": today, "dates": [f"d{i}" for i in range(today + n)], "done": False,
            "games": [{"a": ME, "b": OPP, "al": 99, "bl": 99}]}


class Fill(unittest.TestCase):
    def setUp(self):
        L.reset()

    def test_extra_players_are_bench_games_and_util_takes_one(self):
        sk, osk, g, og, _ = SC._fill(12, 3, 3, L.SLOTS)        # 9 F + 1 UTIL, 3 D, 2 G
        self.assertEqual((sk, osk, g, og), (13, 2, 2, 0))

    def test_open_spots(self):
        self.assertEqual(SC._fill(4, 2, 1, L.SLOTS)[:4], (6, 9, 1, 1))


class Streams(unittest.TestCase):
    def test_fills_open_spots_and_respects_one_add_a_day(self):
        days = [0, 1, 2]
        opn = {0: [1, 0, 0, 0], 1: [1, 0, 0, 0], 2: [0, 0, 0, 0]}
        a, b = pl(100, "F", "TOR", out=2.0), pl(101, "F", "BOS", out=1.5)
        plays = lambda p, d: (p["tm"] == "TOR" and d in (0, 1, 2)) or (p["tm"] == "BOS" and d in (0, 1))
        st = SC.streams_for(opn, plays, [a, b], days, {}, 3, 1)
        self.assertEqual(st[0]["id"], 100)                     # TOR fills both open days: 4.0 (day 2 has no spot)
        self.assertEqual((st[0]["i"], st[0]["g"], st[0]["v"]), (0, 2, 4.0))
        self.assertEqual(len(st), 1)                           # nothing open is left for BOS

    def test_util_spot_is_used_when_the_group_is_full(self):
        opn = {0: [0, 0, 1, 0]}
        st = SC.streams_for(opn, lambda p, d: True, [pl(5, "D", "TOR", out=1.6)], [0], {}, 2, 1)
        self.assertEqual(st[0]["g"], 1)

    def test_locked_days_and_small_pickups_are_skipped(self):
        opn = {0: [1, 0, 0, 0], 1: [1, 0, 0, 0]}
        plays = lambda p, d: True
        st = SC.streams_for(opn, plays, [pl(1, "F", "TOR", out=0.6)], [0, 1], {0: True}, 2, 1)
        self.assertEqual(st, [])                               # only day 1 is open: 0.6 is under the 1.0 bar
        st = SC.streams_for(opn, plays, [pl(1, "F", "TOR", out=1.2)], [0, 1], {0: True}, 2, 1)
        self.assertEqual((st[0]["i"], st[0]["g"]), (1, 1))

    def test_no_moves_no_pickups(self):
        self.assertEqual(SC.streams_for({0: [3, 0, 0, 0]}, lambda p, d: True, [pl(1, "F", "TOR")], [0], {}, 0, 1), [])

    def test_goalie_is_worth_his_start_chance(self):
        st = SC.streams_for({0: [0, 0, 0, 1]}, lambda p, d: True, [pl(9, "G", "TOR", out=4.0, sp=0.5)], [0], {}, 1, 1)
        self.assertEqual(st[0]["v"], 2.0)

    def test_an_off_day_still_takes_an_add(self):
        opn = {1: [1, 0, 0, 0]}
        st = SC.streams_for(opn, lambda p, d: d == 1, [pl(1, "F", "TOR", out=2.0)], [1], {}, 1, 1, add_days=[0, 1])
        self.assertEqual((st[0]["i"], st[0]["g"]), (0, 1))


class AddedToday(unittest.TestCase):
    def tx(self, **o):
        t = {"teamId": OPP, "scoringPeriodId": SP, "status": "EXECUTED", "type": "FREEAGENT",
             "items": [{"type": "ADD", "playerId": 1}, {"type": "DROP", "playerId": 2}]}
        t.update(o)
        return {"transactions": [t]}

    def test_seen(self):
        self.assertTrue(SC.added_today(self.tx(), OPP, SP))
        self.assertTrue(SC.added_today(self.tx(type="WAIVER"), OPP, SP))

    def test_not_today_not_theirs_not_done(self):
        self.assertFalse(SC.added_today(self.tx(scoringPeriodId=SP - 1), OPP, SP))
        self.assertFalse(SC.added_today(self.tx(teamId=7), OPP, SP))
        self.assertFalse(SC.added_today(self.tx(status="PENDING"), OPP, SP))
        self.assertFalse(SC.added_today(None, OPP, SP))


class Build(unittest.TestCase):
    def setUp(self):
        L.reset()
        self.gm = games({"TOR": [0, 1, 2], "BOS": [1], "CHI": [0, 2], "VAN": [2]})
        mine = [pl(1, "F", "TOR"), pl(2, "D", "BOS", slot="D"), pl(3, "G", "CHI", slot="G", sp=0.6),
                pl(4, "F", "VAN", inj="OUT")]
        theirs = [pl(11, "F", "TOR"), pl(12, "F", "TOR", slot="IR")]
        self.site = {"teams": [{"id": ME, "players": mine}, {"id": OPP, "players": theirs}],
                     "fas": [pl(100, "F", "CHI", out=2.5, slot="FA"), pl(101, "D", "BOS", out=0.4, slot="FA")],
                     "gameplan": {"moves_left": 2, "moves": [{"add": {"id": 100}}]}}

    def run_(self, **kw):
        return SC.build(league(**kw.pop("lg", {})), self.site, kw.pop("sb", sb()), self.gm, ABBR, SP, NOW, ME, **kw)

    def test_games_that_count_by_day(self):
        sc = self.run_()
        me, them = sc[str(ME)], sc[str(OPP)]
        # me: day 0 TOR F + CHI G; day 1 TOR F + BOS D; day 2 TOR F + CHI G (VAN player is OUT)
        self.assertEqual([r[:5] for r in me["d"]], [[0, 1, 14, 1, 1], [1, 2, 13, 0, 2], [2, 1, 14, 1, 1]])
        self.assertEqual(me["n"], 6)
        self.assertEqual(them["n"], 3)                         # the IR player doesn't count
        self.assertEqual(me["pos"]["F"], [3, 27])

    def test_your_side_uses_the_game_plan_and_gets_no_stream_list(self):
        sc = self.run_()
        self.assertEqual(sc[str(ME)]["mv"]["left"], 2)
        self.assertNotIn("st", sc[str(ME)])

    def test_their_pickups_and_the_overlap_with_your_plan(self):
        them = self.run_()[str(OPP)]
        self.assertEqual(them["mv"], {"left": 3, "used": 2, "known": True, "today": False})
        self.assertEqual([s["id"] for s in them["st"]], [100])     # the 0.4 defenseman isn't worth listing
        self.assertEqual(them["st"][0]["mine"], 1)
        self.assertEqual(them["up"], 5.0)                          # CHI plays day 0 and day 2

    def test_an_add_already_made_today_spends_today(self):
        raw = {"transactions": [{"teamId": OPP, "scoringPeriodId": SP, "status": "EXECUTED", "type": "FREEAGENT",
                                 "items": [{"type": "ADD", "playerId": 5}]}]}
        them = self.run_(raw_tx=raw)[str(OPP)]
        self.assertEqual((them["mv"]["left"], them["mv"]["today"]), (2, True))

    def test_apply_sets_games_left_everywhere(self):
        s = sb()
        sc = self.run_(sb=s)
        SC.apply(s, sc)
        self.assertEqual((s["games"][0]["al"], s["games"][0]["bl"]), (6, 3))
        self.assertNotIn("sc", s)                              # back end only: no Scout tab

    def test_week_over(self):
        s = sb()
        s["done"] = True
        self.assertIsNone(self.run_(sb=s))
        self.assertIsNone(SC.build(league(), self.site, None, self.gm, ABBR, SP, NOW, ME))


class OpponentUpside(unittest.TestCase):
    def setUp(self):
        L.reset()

    def test_counts_their_best_streams_for_open_spots(self):
        sched = {"TOR": {0, 1, 2}, "CHI": {1, 2}}
        game = lambda tm, i: ("X", True) if i in sched.get(tm, ()) else None
        opp = [pl(1, "F", "TOR")]
        fas = [pl(100, "F", "CHI", out=2.0, slot="FA"), pl(101, "F", "TOR", out=1.5, slot="FA")]
        up, picks = SC.opponent_upside(opp, fas, game, 3, moves_left=1, per_day=1)
        self.assertEqual((up, picks[0]["id"]), (4.5, 101))   # TOR plays 3 days (4.5) beats CHI 2 days (4.0)
        up2, _ = SC.opponent_upside(opp, fas, game, 3, moves_left=0, per_day=1)
        self.assertEqual(up2, 0)

    def test_no_add_on_a_locked_day(self):
        game = lambda tm, i: ("X", True) if i == 1 else None   # day 0 locked: nobody can be added for it
        up, picks = SC.opponent_upside([], [pl(100, "F", "CHI", out=2.0, slot="FA")], game, 2, 2, per_day=1)
        self.assertEqual([p["i"] for p in picks], [1])


if __name__ == "__main__":
    unittest.main()
