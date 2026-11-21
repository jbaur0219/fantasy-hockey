import json
import tempfile
import unittest
from pathlib import Path

import core as C
import record as RC


class Confidence(unittest.TestCase):
    def mv(self, net, ga=3, gd=3, tier="make"):
        return {"net": net, "ga": ga, "gd": gd, "tier": tier}

    def test_levels(self):
        p = {"inj": "ACTIVE"}
        self.assertEqual(C.confidence(self.mv(3.2), p, True), "strong")
        self.assertEqual(C.confidence(self.mv(2.2, ga=4, gd=3), p, True), "strong")      # schedule-backed
        self.assertEqual(C.confidence(self.mv(2.2), p, True), "lean")                    # same games: needs 3+
        self.assertEqual(C.confidence(self.mv(1.2), p, True), "optional")
        self.assertEqual(C.confidence(self.mv(5.0, tier="optional"), p, True), "optional")

    def test_never_strong_on_bad_data(self):
        self.assertEqual(C.confidence(self.mv(5.0), {"inj": "ACTIVE"}, False), "lean")

    def test_never_strong_when_add_is_day_to_day(self):
        ok = {"inj": "ACTIVE"}
        self.assertEqual(C.confidence(self.mv(5.0), ok, True, {"inj": "DAY_TO_DAY"}), "lean")
        self.assertEqual(C.confidence(self.mv(5.0), ok, True, {"inj": "ACTIVE"}), "strong")
        self.assertEqual(C.confidence(self.mv(5.0), ok, True, None), "strong")
        self.assertEqual(C.confidence(self.mv(1.2), ok, True, {"inj": "DAY_TO_DAY"}), "optional")


class TrackRecord(unittest.TestCase):
    def test_scores_and_freezes(self):
        d = Path(tempfile.mkdtemp())
        RC.LOG_FILE, RC.RESULTS_FILE = d / "moves.jsonl", d / "results.json"
        base = {"a": [10.0, 5], "d": [20.0, 5], "at": 0}
        rows = [{"mp": 8, "result": "done", "day": "Tue Nov 17", "add": {"id": 1, "n": "A B"}, "drop": {"id": 2, "n": "C D"},
                 "net": 2.0, "conf": "strong", "base": base},
                {"mp": 8, "result": "missed", "day": "Tue Nov 17", "add": {"id": 3, "n": "E F"}, "drop": {"id": 4, "n": "G H"},
                 "net": 1.0}]
        RC.LOG_FILE.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        RC.STATE["tot"] = {1: [16.0, 8], 2: [22.0, 8]}
        r = RC.build(8)
        self.assertEqual(r["made"], {"n": 1, "pts": 4.0, "wins": 1, "expected": 2.0})
        self.assertEqual(r["untracked"], 1)
        self.assertFalse(RC.RESULTS_FILE.exists())                   # same week: not final yet
        RC.build(9)
        self.assertEqual(json.loads(RC.RESULTS_FILE.read_text())["8|1|2"]["actual"], 4.0)
        RC.STATE["tot"] = {1: [30.0, 9], 2: [22.0, 9]}               # later games no longer count
        self.assertEqual(RC.build(9)["made"]["pts"], 4.0)


if __name__ == "__main__":
    unittest.main()
