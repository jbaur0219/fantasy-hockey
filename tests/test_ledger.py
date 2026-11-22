import csv
import io
import tempfile
import unittest
from pathlib import Path

import ledger as LG


def mv(mp, result, actual, conf="strong", final=True, logged=1794936231350):
    return {"mp": mp, "day": "Mon Nov 16", "logged": logged, "result": result, "conf": conf, "expected": 2.0,
            "add": {"id": 1, "n": "A B"}, "drop": {"id": 2, "n": "C D"}, "actual": actual, "final": final}


class Ledger(unittest.TestCase):
    rows = [mv(8, "done", 4.0), mv(8, "missed", -1.5, "lean"), mv(9, "done", -2.0, "optional"), mv(9, "done", None, final=False)]

    def test_totals_count_misses(self):
        s = LG.summarize(self.rows, 1)
        self.assertEqual(s["suggested"], 4)
        self.assertEqual(s["scored"], 3)
        self.assertEqual(s["pending"], 1)
        self.assertEqual(s["made"]["pts"], 2.0)                     # +4.0 and -2.0: the miss is in the total
        self.assertEqual(s["made"]["n"], 2)
        self.assertEqual(s["all"]["win_pct"], 33)
        self.assertEqual(s["skipped"]["pts"], -1.5)
        self.assertEqual([w["week"] for w in s["by_week"]], [8, 9])
        self.assertEqual(s["since"], "2026-11-17")

    def test_empty_and_files(self):
        s = LG.summarize([], 1)
        self.assertEqual(s["suggested"], 0)
        d = Path(tempfile.mkdtemp())
        LG.write_files(self.rows, d, 1794936231350)
        self.assertTrue((d / "lifetime.json").exists())
        self.assertFalse((d / "stats.html").exists())
        rows = list(csv.reader(io.StringIO((d / "moves.csv").read_text())))
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[1][3], "made")
        LG.write_files([], d, 1)


if __name__ == "__main__":
    unittest.main()
