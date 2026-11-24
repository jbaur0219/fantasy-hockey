"""The Game plan list (2026-11-24): every move shown is one to make, small moves are left off (and logged privately),
the move budget follows each league's own rules, and the alerts name every planned move."""
import unittest
from unittest import mock

import analyze as A
import build as B
import core as C
import dashboard as D
import ledger as LG
import longterm as LT
import streams as STR

INF = STR.INF
DAYS = ["Mon Nov 23", "Tue Nov 24", "Wed Nov 25", "Thu Nov 26"]


def player(pid, name, grp="F", tm="EDM", out=1.0, ppg=1.0, rec=1.0, inj="ACTIVE", rl=None, ev=None, ppu=0):
    return {"id": pid, "n": name, "grp": grp, "pos": "C" if grp == "F" else grp, "tm": tm, "out": out, "ppg": ppg,
            "rec": rec, "gp": 20, "inj": inj, "slot": "C", "rl": rl, "ev": ev, "ppu": ppu}


def fake_inputs(roster, fas):
    """(entries, base, pool) like core.build_inputs, from [(player, values per day, drop bar)] lists."""
    entries, base = [], []
    for p, v, bar in roster:
        e = {"p": p, "v": v, "grp": p["grp"], "join": 0, "leave": INF}
        entries.append(e)
        base.append({"g": p["grp"], "v": v, "ok": bar is not None, "bar": bar or 1.0, "p": p, "e": e})
    pool = []
    for p, v in fas:
        x = {"p": p, "v": v, "grp": p["grp"], "waiver": False}
        pool.append({"g": p["grp"], "v": v, "waiver": False, "p": p, "x": x})
    return entries, base, pool


def roster_with_weak(weak_vals):
    """Nine solid forwards plus one weak forward you could drop (the 10th forward fills UTIL)."""
    r = [(player(100 + i, f"Solid Forward{i}", out=2.0), [2.0, 2.0, 2.0, 2.0], None) for i in range(9)]
    r.append((player(200, "Zach Benson", tm="BUF", out=1.0), weak_vals, 1.0))
    return r


class PlanList(unittest.TestCase):
    def run_plan(self, roster, fas, prev=None, moves_left=7):
        ents = fake_inputs(roster, fas)
        with mock.patch.object(C, "build_inputs", return_value=ents), \
                mock.patch.object(C, "cost", return_value=0.0), \
                mock.patch.object(LT, "assess", return_value=None):
            return C.plan([], [], None, len(DAYS), DAYS, {}, {}, moves_left, {}, prev=prev, reasons=False)

    def test_big_move_shown_small_move_left_off(self):
        # Your 5th defenseman (Benson here) plays 2 of 4 days; Brown plays all 4: +2.0, on the list.
        # Your UTIL forward (1.9 a day) could be swapped for a 2.1 forward: +0.8 over the week, a coin flip, left off.
        roster = [(player(100 + i, f"Solid Forward{i}", out=2.0), [2.0] * 4, None) for i in range(9)]
        roster.append((player(150, "Util Filler", out=1.9), [1.9] * 4, 1.0))
        roster += [(player(300 + i, f"Solid D{i}", grp="D", out=2.0), [2.0] * 4, None) for i in range(4)]
        roster.append((player(200, "Zach Benson", grp="D", tm="BUF"), [1.0, 0.0, 1.0, 0.0], 1.0))
        fas = [(player(1, "Connor Brown", grp="D", rl="D2 - PP2", ev="D2", ppu=2), [1.0] * 4),
               (player(2, "Small Upgrade"), [2.1] * 4)]
        res = self.run_plan(roster, fas)
        self.assertEqual([(m["add"]["n"], m["drop"]["n"]) for m in res["moves"]], [("Connor Brown", "Zach Benson")])
        self.assertEqual([m["add"]["n"] for m in res["small"]], ["Small Upgrade"])
        self.assertAlmostEqual(res["small"][0]["net"], 0.8, places=1)
        self.assertAlmostEqual(res["moves"][0]["net"], 2.0, places=1)
        self.assertNotEqual(res["moves"][0]["conf"], "optional")
        self.assertAlmostEqual(res["gain"], 2.0, places=1)       # the total only counts what is on the list

    def test_plain_english_reason(self):
        roster = roster_with_weak([1.0, 0.0, 1.0, 0.0])
        fas = [(player(1, "Connor Brown", rl="F2 - PP2", ev="F2", ppu=2), [1.0, 1.0, 1.0, 1.0])]
        mv = self.run_plan(roster, fas)["moves"][0]
        self.assertIn("Brown plays on EDM's second line and second power-play unit.", mv["why1"])
        self.assertIn("4 games left this week; Benson has 2.", mv["why1"])
        self.assertNotIn("About", mv["why1"])                     # the points are shown next to it, not repeated

    def test_planned_move_does_not_flip_flop_near_the_line(self):
        # +0.8: under the bar for a new move, but it was already on the plan, so it stays (HOLD_SLACK)
        roster = roster_with_weak([1.0, 1.0, 1.0, 1.0])
        fas = [(player(1, "Steady Add"), [1.2, 1.2, 1.2, 1.2])]
        self.assertEqual(self.run_plan(roster, fas)["moves"], [])
        kept = self.run_plan(roster, fas, prev=[(1, DAYS[0], 200)])["moves"]
        self.assertEqual([m["add"]["n"] for m in kept], ["Steady Add"])
        self.assertEqual(kept[0]["conf"], "lean")

    def test_late_week_bar_is_lower(self):
        # +0.6 is too small on Monday, but in the last 3 days unused moves expire, so it makes the list
        roster = roster_with_weak([1.0, 1.0, 0.0, 0.0])
        fas = [(player(1, "Late Add"), [0.0, 0.0, 0.3, 0.3])]
        res = self.run_plan(roster, fas)
        self.assertEqual([(m["add"]["n"], m["day"]) for m in res["moves"]], [("Late Add", DAYS[2])])

    def test_bench_games_are_explained(self):
        # Same games, same points a game: the edge is that the forward's games sit on your bench (forwards full)
        roster = [(player(100 + i, f"Solid Forward{i}", out=2.0), [2.0] * 4, None) for i in range(10)]
        roster.append((player(200, "Kailer Yamamoto", tm="SEA"), [1.5, 0.0, 1.5, 1.5], 1.0))
        roster += [(player(300 + i, f"Solid D{i}", grp="D", out=2.0), [2.0] * 4, None) for i in range(4)]
        fas = [(player(1, "Rasmus Andersson", grp="D", tm="CGY", rl="D1 - PP1", ev="D1", ppu=1), [1.5, 0.0, 1.5, 1.5])]
        mv = self.run_plan(roster, fas)["moves"][0]
        self.assertAlmostEqual(mv["gain"], 4.5, places=1)
        self.assertEqual((mv["ca"], mv["cd"]), (3, 0))
        self.assertIn("All 3 of Andersson's games would count in your lineup. None of Yamamoto's 3 would", mv["why1"])
        self.assertIn("forward spots are already full", mv["why1"])

    def test_injured_player_goes_to_ir_instead_of_a_drop(self):
        roster = roster_with_weak([1.0, 1.0, 1.0, 1.0])
        roster[0] = (player(100, "Hurt Star", out=3.0, inj="OUT"), [0.0] * 4, None)   # never a drop (a star)
        fas = [(player(1, "Fill In"), [1.5] * 4)]
        ents = fake_inputs(roster, fas)
        with mock.patch.object(C, "build_inputs", return_value=ents), \
                mock.patch.object(C, "cost", return_value=5.0), mock.patch.object(LT, "assess", return_value=None):
            res = C.plan([], [], None, len(DAYS), DAYS, {}, {}, 7, {}, reasons=False, ir_free=1)
        mv = res["moves"][0]
        self.assertEqual((mv["drop"]["n"], mv["ir"], mv["cost"]), ("Hurt Star", True, 0.0))
        self.assertIn("move him to your open IR spot", mv["why1"])
        with mock.patch.object(C, "build_inputs", return_value=fake_inputs(roster, fas)), \
                mock.patch.object(C, "cost", return_value=5.0), mock.patch.object(LT, "assess", return_value=None):
            res = C.plan([], [], None, len(DAYS), DAYS, {}, {}, 7, {}, reasons=False, ir_free=0)
        self.assertNotIn("Hurt Star", [m["drop"]["n"] for m in res["moves"]])   # no IR spot: a star is not dropped

    def test_nothing_worth_it(self):
        roster = roster_with_weak([1.0, 1.0, 1.0, 1.0])
        res = self.run_plan(roster, [(player(1, "Tiny"), [1.1, 1.1, 1.1, 1.1])])
        self.assertEqual(res["moves"], [])
        self.assertEqual(res["gain"], 0.0)


class LeagueMoveLimit(unittest.TestCase):
    def league(self, acq, used=None, season_used=0, mp=8):
        tc = {"acquisitions": season_used}
        if used is not None:
            tc["matchupAcquisitionTotals"] = {str(mp): used}
        return {"status": {"currentMatchupPeriod": mp},
                "settings": {"acquisitionSettings": acq, "scheduleSettings": {"matchupPeriods": {str(mp): [mp]}}},
                "teams": [{"id": 1, "transactionCounter": tc}]}

    def test_reads_the_leagues_own_limit(self):
        b = D.move_budget(self.league({"matchupAcquisitionLimit": 4}, used=1), 1)
        self.assertEqual((b["limit"], b["used"], b["left"], b["known"]), (4, 1, 3, True))
        b = D.move_budget(self.league({"matchupAcquisitionLimit": 10}, used=3), 1)
        self.assertEqual((b["limit"], b["left"]), (10, 7))

    def test_no_adds_yet_this_week(self):
        lg = self.league({"matchupAcquisitionLimit": 7}, used=None)
        lg["teams"][0]["transactionCounter"]["matchupAcquisitionTotals"] = {"7": 5}     # last week only
        b = D.move_budget(lg, 1)
        self.assertEqual((b["used"], b["left"]), (0, 7))

    def test_no_weekly_limit(self):
        b = D.move_budget(self.league({"matchupAcquisitionLimit": -1}, used=12), 1)
        self.assertTrue(b["unlimited"])
        self.assertGreater(b["left"], 50)

    def test_per_day_limit_and_season_cap(self):
        b = D.move_budget(self.league({"matchupAcquisitionLimit": 1, "matchupLimitPerScoringPeriod": True}, used=2), 1)
        self.assertEqual((b["limit"], b["left"]), (7, 5))
        b = D.move_budget(self.league({"matchupAcquisitionLimit": 7, "acquisitionLimit": 40}, used=0, season_used=38), 1)
        self.assertEqual((b["left"], b["season_left"]), (2, 2))

    def test_settings_missing_is_flagged(self):
        b = D.move_budget({"status": {"currentMatchupPeriod": 8}, "teams": []}, 1)
        self.assertFalse(b["known"])
        self.assertEqual(b["limit"], D.DEFAULT_MOVE_LIMIT)


class LedgerSplit(unittest.TestCase):
    def test_small_moves_are_reported_on_their_own(self):
        def r(result, actual):
            return {"mp": 9, "day": "Tue Nov 24", "logged": 1, "result": result, "conf": "small" if result == "hidden" else "lean",
                    "expected": 1.0, "add": {"id": 1, "n": "A B"}, "drop": {"id": 2, "n": "C D"}, "actual": actual, "final": True}
        s = LG.summarize([r("done", 3.0), r("missed", 1.0), r("hidden", -2.0)], 1)
        self.assertEqual(s["suggested"], 2)
        self.assertEqual(s["all"]["pts"], 4.0)
        self.assertEqual(s["not_shown"]["n"], 1)
        self.assertEqual(s["not_shown"]["pts"], -2.0)
        self.assertIn("not shown", LG.csv_text([r("hidden", -2.0)]))


class Alerts(unittest.TestCase):
    def test_every_planned_move_today_is_named_with_the_deadline(self):
        from datetime import datetime
        et = D.et_zone()
        now = int(datetime(2026, 11, 24, 14, 0, tzinfo=et).timestamp() * 1000)
        lock = int(datetime(2026, 11, 24, 19, 0, tzinfo=et).timestamp() * 1000)
        clock = {"built": now, "dates": ["2026-11-24", "2026-11-25"], "labels": ["Tue Nov 24", "Wed Nov 25"],
                 "lock": [lock, lock + 86400000]}

        def mv(t, a, d, gain, conf):
            return {"t": t, "day": clock["labels"][t], "add": {"n": a, "tm": "EDM"}, "drop": {"n": d}, "gain": gain,
                    "conf": conf, "waiver": False}
        site = {"clock": clock, "gameplan": {"moves": [mv(0, "Connor Brown", "Zach Benson", 1.6, "lean"),
                                                       mv(0, "Frank Nazar", "Trevor Zegras", 3.1, "strong"),
                                                       mv(1, "Kailer Yamamoto", "Tom Wilson", 2.0, "lean")],
                                             "moves_left": 5, "unlimited": False},
                "matchup": {"p_win": 0.58}}
        with mock.patch.object(D, "day_locked", return_value=False):
            morning, reminder = B.notify_texts(site, now)
        self.assertIn("Make these 2 moves today before 7:00 PM", morning["body"])
        self.assertIn("Connor Brown", morning["body"])          # a lean move is named too: every move is one to make
        self.assertIn("5 moves left this week", morning["body"])
        self.assertIn("Connor Brown", reminder["body"])
        self.assertNotIn("Yamamoto", reminder["body"])           # tomorrow's move waits for tomorrow

    def test_no_reminder_without_moves_today(self):
        from datetime import datetime
        now = int(datetime(2026, 11, 24, 14, 0, tzinfo=D.et_zone()).timestamp() * 1000)
        clock = {"built": now, "dates": ["2026-11-24"], "labels": ["Tue Nov 24"], "lock": [now + 3600000]}
        with mock.patch.object(D, "day_locked", return_value=False):
            morning, reminder = B.notify_texts({"clock": clock, "gameplan": {"moves": []}}, now)
        self.assertIsNone(reminder)
        self.assertIn("No move to make today.", morning["body"])


if __name__ == "__main__":
    unittest.main()
