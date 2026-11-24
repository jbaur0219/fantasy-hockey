"""The backtest only moves a bar when the moves next to it say so clearly (backtest.py)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backtest as BT   # noqa: E402


def entry(i, net, day="Tue Nov 24", result="missed", pos="C", mp=9, **kw):
    e = {"mp": mp, "logged": 1795600000000 + i, "result": result, "day": day,
         "add": {"id": 1000 + i, "n": f"Add {i}", "pos": pos}, "drop": {"id": 2000 + i, "n": f"Drop {i}", "pos": pos},
         "expected_gain": net, "net": net}
    e.update(kw)
    return e


def scored(log, actual):
    return {f"{e['mp']}|{e['add']['id']}|{e['drop']['id']}": (actual(e) if callable(actual) else actual) for e in log}


def run(log, actual):
    return BT.analyze(BT.rows(log, scored(log, actual)))


def verdict(a, start):
    return next(v for v in a["verdicts"] if v["bar"].startswith(start))


class Bars(unittest.TestCase):
    def test_small_sample_never_moves_a_bar(self):
        log = [entry(i, 0.8, result="hidden") for i in range(5)]
        v = verdict(run(log, 3.0), "SHOW_NET")
        self.assertEqual(v["call"], "wait")
        self.assertEqual(v["move"], 0.0)

    def test_moves_under_the_bar_that_clearly_help_lower_it(self):
        log = [entry(i, 0.75, result="hidden") for i in range(BT.MIN_N)]
        v = verdict(run(log, lambda e: 1.0 + (e["logged"] % 3) * 0.2), "SHOW_NET")
        self.assertEqual(v["call"], "lower")
        self.assertAlmostEqual(v["to"], 1.0 - BT.STEP)

    def test_moves_over_the_bar_that_clearly_lose_raise_it(self):
        log = [entry(i, 1.2) for i in range(BT.MIN_N)]
        v = verdict(run(log, lambda e: -1.0 - (e["logged"] % 2) * 0.5), "SHOW_NET")
        self.assertEqual(v["call"], "raise")
        self.assertAlmostEqual(v["to"], 1.0 + BT.STEP)

    def test_noisy_results_hold(self):
        log = [entry(i, 1.2) for i in range(BT.MIN_N)]
        v = verdict(run(log, lambda e: 4.0 if e["logged"] % 2 else -3.5), "SHOW_NET")
        self.assertEqual(v["call"], "hold")

    def test_late_moves_are_judged_against_the_late_bar(self):
        log = [entry(i, 0.3, day="Sat Nov 28", result="hidden") for i in range(BT.MIN_N)]
        a = run(log, 2.0)
        self.assertEqual(verdict(a, "LATE_NET")["call"], "lower")
        self.assertEqual(verdict(a, "SHOW_NET")["call"], "wait")

    def test_logged_day_index_beats_the_day_name(self):
        e = entry(1, 1.0, day="Sat Nov 28", t=2, nd=14)      # a two-week matchup: Saturday of week one is not late
        self.assertFalse(BT.rows([e])[0]["late"])

    def test_goalie_moves_are_their_own_group(self):
        log = [entry(i, 2.0, pos="G") for i in range(4)]
        a = run(log, -3.0)
        self.assertEqual(a["calibration"]["goalies"]["n"], 4)
        self.assertEqual(a["calibration"]["skaters"]["n"], 0)
        self.assertIn("higher bar", verdict(a, "Goalie")["why"])


class Rows(unittest.TestCase):
    def test_same_pair_on_another_day_is_its_own_move_but_scored_once(self):
        a = entry(1, 2.0, day="Tue Nov 17")
        b = dict(entry(1, 2.4, day="Sun Nov 22", result="done"))
        rs = BT.rows([a, b], scored([a], 3.0))
        self.assertEqual(len(rs), 2)
        self.assertEqual([r["actual"] for r in rs], [3.0, None])

    def test_calibration_uses_this_week_gain_not_net(self):
        e = entry(1, 1.0, expected_gain=2.0)
        a = run([e], 2.0)
        self.assertEqual(a["calibration"]["all"]["expected"], 2.0)
        self.assertEqual(a["calibration"]["all"]["net"], 1.0)

    def test_write_files_and_offline_csv(self):
        d = Path(tempfile.mkdtemp())
        log = [entry(i, 1.5) for i in range(3)]
        (d / "moves.jsonl").write_text("\n".join(json.dumps(e) for e in log) + "\n")
        (d / "moves.csv").write_text("matchup_week,day,logged_date,status,rating,add,drop,expected_pts,actual_pts,final,scored\n"
                                     "9,Tue Nov 24,2026-11-24,skipped,,Add 0,Drop 0,1.5,2.5,no,yes\n")
        a = BT.write_files([], d, 1)
        self.assertEqual(a["scored"], 1)
        self.assertTrue((d / "backtest.md").read_text().startswith("# Backtest"))
        self.assertIn("verdicts", json.loads((d / "backtest.json").read_text()))

    def test_repo_history_runs(self):
        hist = Path(__file__).resolve().parent.parent / "history"
        a = BT.analyze(BT.rows(BT.read_log(hist / "moves.jsonl"), None, BT.actuals_offline(hist)))
        self.assertGreaterEqual(a["moves"], a["scored"])
        self.assertEqual(len(a["verdicts"]), 3)


if __name__ == "__main__":
    unittest.main()
