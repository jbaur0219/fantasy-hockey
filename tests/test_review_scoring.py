#!/usr/bin/env python3
"""Review C (2026-11-24): how moves are logged and scored (record.py, weekplan.py), the long-term cost (longterm.py),
the keep list and the win-chance model. Rule tests pass today; tests marked expectedFailure pin a reproduced bug
(see /home/claude/review/scoring.md, BUG C<n>) and should pass once it is fixed."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core as C          # noqa: E402
import keep as KP         # noqa: E402
import ledger as LG       # noqa: E402
import longterm as LT     # noqa: E402
import netcache as NC     # noqa: E402
import record as RC       # noqa: E402
import weekplan as WK     # noqa: E402


def sk(n, grp="F", out=1.8, tm="AAA", inj="ACTIVE", **kw):
    p = {"id": n, "n": f"P {n}", "grp": grp, "pos": grp, "tm": tm, "out": out, "inj": inj, "ppg": out, "rec": out,
         "gp": 20, "slot": "BN", "sp": 0.6}
    p.update(kw)
    return p


def entry(result, day, add=1, drop=2, base=None, mp=8, logged=1):
    return {"mp": mp, "logged": logged, "result": result, "day": day, "add": {"id": add, "n": "A A"},
            "drop": {"id": drop, "n": "D D"}, "expected_gain": 2.0, "net": 2.0, "conf": "strong", "base": base}


class _Files(unittest.TestCase):
    """Points record.py / weekplan.py at a temp folder so tests never touch history/ or plan_state.json."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self._saved = (RC.LOG_FILE, RC.RESULTS_FILE, WK.LOG_FILE, WK.STATE_FILE, dict(RC.STATE), NC.STATE["mode"])
        RC.LOG_FILE = WK.LOG_FILE = self.dir / "moves.jsonl"
        RC.RESULTS_FILE = self.dir / "results.json"
        WK.STATE_FILE = self.dir / "plan_state.json"
        NC.STATE["mode"] = None

    def tearDown(self):
        RC.LOG_FILE, RC.RESULTS_FILE, WK.LOG_FILE, WK.STATE_FILE, st, NC.STATE["mode"] = self._saved
        RC.STATE.clear()
        RC.STATE.update(st)

    def log(self, *rows):
        RC.LOG_FILE.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


# ---------------------------------------------------------------------------
# record.py: scoring
# ---------------------------------------------------------------------------
class Scoring(_Files):
    def test_actual_is_add_minus_drop_since_the_base(self):
        RC.STATE["tot"] = {1: [30.0, 12], 2: [25.0, 11]}
        self.log(entry("done", "Thu", base={"a": [24.0, 10], "d": [24.0, 10], "at": 0}))
        r = RC.build(8, write=False)
        self.assertEqual(r["made"]["n"], 1)
        self.assertEqual(r["made"]["pts"], 5.0)                 # (30-24) - (25-24)
        self.assertEqual((r["moves"][0]["ga"], r["moves"][0]["gd"]), (2, 1))

    def test_week_freezes_once_the_next_matchup_starts(self):
        RC.STATE["tot"] = {1: [30.0, 12], 2: [25.0, 11]}
        self.log(entry("done", "Thu", base={"a": [24.0, 10], "d": [24.0, 10], "at": 0}))
        RC.build(9, write=True)
        RC.STATE["tot"] = {1: [99.0, 20], 2: [0.0, 11]}         # next week's points must not leak in
        r = RC.build(9, write=False)
        self.assertEqual(r["made"]["pts"], 5.0)
        self.assertTrue(r["moves"][0]["final"])

    def test_hidden_moves_stay_out_of_the_shown_numbers(self):
        RC.STATE["tot"] = {1: [30.0, 12], 2: [25.0, 11], 3: [10.0, 5]}
        b = {"a": [24.0, 10], "d": [24.0, 10], "at": 0}
        self.log(entry("done", "Thu", base=b), entry("hidden", "Fri", add=3, drop=2, base={"a": [5.0, 4], "d": [24.0, 10], "at": 0}))
        r = RC.build(8, write=False)
        self.assertEqual(r["hidden"]["n"], 1)
        self.assertEqual(len(r["moves"]), 1)
        s = LG.summarize(RC.STATE["rows"], 1)
        self.assertEqual(s["suggested"], 1)
        self.assertEqual(s["not_shown"]["n"], 1)

    # BUG C1: the same add/drop pair suggested twice in one week is logged twice (missed on Tue, made on Sun), and
    # record.py keeps only the first row (key mp|add|drop): the move you MADE is reported as skipped and, because the
    # first row was logged before tracking, never scored. Real case in history/moves.jsonl: Sam Rinzel for Rasmus
    # Andersson (missed Tue Nov 17, made Sun Nov 22) is missing from moves.csv as a made move.
    def test_a_made_repeat_of_a_skipped_pair_counts_as_made(self):
        RC.STATE["tot"] = {1: [30.0, 12], 2: [25.0, 11]}
        self.log(entry("missed", "Tue Nov 17", base=None),
                 entry("done", "Sun Nov 22", base={"a": [28.0, 11], "d": [25.0, 11], "at": 0}))
        r = RC.build(8, write=False)
        self.assertEqual(r["made"]["n"], 1)
        self.assertEqual(r["made"]["pts"], 2.0)

    # BUG C4: a week's score is only kept once it is frozen at the first build of the next matchup. If either player is
    # missing from that build's totals (dropped streamers fall out of the 300 most-owned free agents ESPN returns, or
    # the build fails that day), the move is never scored, although every build during the week could score it.
    def test_a_score_seen_during_the_week_survives_the_player_falling_out_of_the_feed(self):
        RC.STATE["tot"] = {1: [30.0, 12], 2: [25.0, 11]}
        self.log(entry("missed", "Thu", base={"a": [24.0, 10], "d": [24.0, 10], "at": 0}))
        RC.build(8, write=True)                                 # Sunday night: scored, not final yet
        RC.STATE["tot"] = {1: [30.0, 12]}                       # Monday: the dropped player is no longer listed
        r = RC.build(9, write=True)
        self.assertEqual(r["skipped"]["n"], 1)
        self.assertEqual(r["skipped"]["pts"], 5.0)


# ---------------------------------------------------------------------------
# weekplan.py: what gets logged, and the starting line (base) it is scored from
# ---------------------------------------------------------------------------
H = 3_600_000
LABELS = ["Mon", "Tue", "Wed", "Thu"]
LOCK = [10 * H, 34 * H, 58 * H, 82 * H]          # first puck each day


def move(day, add=1, drop=2, gain=2.0):
    return {"t": LABELS.index(day), "day": day, "add": {"id": add, "n": "A A"}, "drop": {"id": drop, "n": "D D"},
            "gain": gain, "cost": 0.0, "net": gain, "games": 2, "waiver": False, "tier": "make", "conf": "strong",
            "why1": "x"}


def run(now, moves, mine=(2,), healthy=True, tot=None):
    if tot is not None:
        RC.STATE["tot"] = tot
    clock = {"labels": LABELS, "lock": LOCK, "dates": ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19"]}
    site = {"gameplan": {"moves": moves, "small": []}, "clock": clock, "mine": [{"id": i} for i in mine],
            "fas": [{"id": 1, "inj": "ACTIVE"}], "matchup": None}
    return WK.build({}, {}, {"status": {"currentMatchupPeriod": 8}}, {}, now, site, healthy=healthy)


class Logging(_Files):
    def test_skipped_move_is_logged_once_with_the_last_base_before_its_lock(self):
        run(1 * H, [move("Wed")], tot={1: [10.0, 5], 2: [10.0, 5]})
        run(40 * H, [move("Wed")], tot={1: [12.0, 6], 2: [11.0, 6]})        # Tue night, Wed still open
        run(60 * H, [], tot={1: [15.0, 7], 2: [11.0, 7]})                   # Wed's first puck has dropped
        rows = [json.loads(x) for x in WK.LOG_FILE.read_text().splitlines()]
        self.assertEqual([r["result"] for r in rows], ["missed"])
        self.assertEqual(rows[0]["base"]["a"], [12.0, 6])                   # not Monday's line, not Wed's games

    def test_made_move_is_logged_as_done(self):
        run(1 * H, [move("Tue")], tot={1: [10.0, 5], 2: [10.0, 5]})
        run(20 * H, [move("Tue")], mine=(1, 2), tot={1: [10.0, 5], 2: [10.0, 5]})
        rows = [json.loads(x) for x in WK.LOG_FILE.read_text().splitlines()]
        self.assertEqual([r["result"] for r in rows], ["done"])

    # BUG C2: the starting line is only refreshed by healthy builds (DailyFaceoff data OK). When the last builds before a
    # move's lock are degraded (audit #1: DF blocks the server some days), the move is scored from a base taken days
    # earlier, so points both players scored BEFORE the move's day count toward its result.
    def test_base_refreshes_even_when_line_data_is_degraded(self):
        run(1 * H, [move("Wed")], tot={1: [10.0, 5], 2: [10.0, 5]})
        run(40 * H, [move("Wed")], healthy=False, tot={1: [16.0, 7], 2: [10.0, 7]})   # Tue night, degraded build
        run(60 * H, [], tot={1: [16.0, 7], 2: [10.0, 7]})
        rows = [json.loads(x) for x in WK.LOG_FILE.read_text().splitlines()]
        self.assertEqual(rows[0]["base"]["a"], [16.0, 7])                   # today: Mon's [10, 5] (+6 pts that aren't the move's)

    def test_same_pair_skipped_twice_is_logged_once(self):
        # (documented behaviour; see C1 for why the pair key matters) a second skip of the same pair is not logged again
        run(1 * H, [move("Mon")], tot={1: [10.0, 5], 2: [10.0, 5]})
        run(20 * H, [move("Wed")], tot={1: [10.0, 5], 2: [10.0, 5]})
        run(60 * H, [], tot={1: [10.0, 5], 2: [10.0, 5]})
        rows = [json.loads(x) for x in WK.LOG_FILE.read_text().splitlines()]
        self.assertEqual([(r["result"], r["day"]) for r in rows], [("missed", "Mon")])

    def test_made_after_an_earlier_skip_writes_two_rows_for_one_pair(self):
        # the logging half of BUG C1: both rows are written; record.py then keeps the wrong one
        run(1 * H, [move("Mon")], tot={1: [10.0, 5], 2: [10.0, 5]})
        run(20 * H, [move("Wed")], tot={1: [10.0, 5], 2: [10.0, 5]})
        run(50 * H, [move("Wed")], mine=(1, 2), tot={1: [10.0, 5], 2: [10.0, 5]})
        rows = [json.loads(x) for x in WK.LOG_FILE.read_text().splitlines()]
        self.assertEqual([r["result"] for r in rows], ["missed", "done"])


# ---------------------------------------------------------------------------
# longterm.py: what a drop costs after this week
# ---------------------------------------------------------------------------
class LongTerm(unittest.TestCase):
    FUT = {"AAA": 10, "BBB": 10}

    def test_no_cost_when_the_add_is_at_least_as_good(self):
        self.assertEqual(LT.cost(sk(1, out=1.5), sk(2, out=2.0, tm="BBB"), self.FUT), 0.0)

    def test_add_never_counts_below_a_typical_free_agent(self):
        weak_add = sk(2, out=0.3, tm="BBB")
        self.assertEqual(LT.cost(sk(1, out=1.45, own=50), weak_add, self.FUT), 0.0)

    def test_no_future_games_no_cost(self):
        self.assertEqual(LT.cost(sk(1, out=2.4, tm="ZZZ"), sk(2, out=1.5, tm="BBB"), self.FUT), 0.0)

    def test_claim_chance_scales_the_cost(self):
        y_lo, y_hi = sk(1, out=2.4, own=10), sk(1, out=2.4, own=95)
        x = sk(2, out=1.5, tm="BBB")
        lo, hi = LT.cost(y_lo, x, self.FUT), LT.cost(y_hi, x, self.FUT)
        gap = (2.4 - 1.5) * 10
        self.assertAlmostEqual(lo, round(gap * (LT.FIX_SHARE + (1 - LT.FIX_SHARE) * 0.05), 3))
        self.assertAlmostEqual(hi, round(gap * (LT.FIX_SHARE + (1 - LT.FIX_SHARE) * 0.95), 3))

    def test_goalie_value_is_per_team_game(self):
        g = sk(1, grp="G", out=4.0, sp=0.5)
        self.assertAlmostEqual(LT.true_pg(g), 2.0)

    # BUG C3: any player listed OUT / on injured reserve costs nothing to drop, however good he is and however soon he
    # returns. With no open IR spot the plan can drop an injured star for a one-week stream (drop_rule also lets any
    # OUT player go for a 1-point gain). ESPN's OUT includes short absences, so the 3-week horizon is not all lost.
    def test_dropping_an_injured_star_still_costs_something(self):
        star = sk(1, out=3.0, inj="OUT", own=99)
        self.assertGreater(LT.cost(star, sk(2, out=1.5, tm="BBB"), self.FUT), 2.0)


# ---------------------------------------------------------------------------
# keep.py
# ---------------------------------------------------------------------------
class Keep(unittest.TestCase):
    def setUp(self):
        self._f = KP.FILE
        KP.FILE = Path(tempfile.mkdtemp()) / "keep.json"
        self._env = os.environ.get("FH_KEEP")

    def tearDown(self):
        KP.FILE = self._f
        if self._env is None:
            os.environ.pop("FH_KEEP", None)
        else:
            os.environ["FH_KEEP"] = self._env

    def test_keep_list_is_per_matchup_and_clears(self):
        os.environ["FH_KEEP"] = "12, 7,x,-3"
        KP.apply_env(8)
        self.assertEqual(KP.load(8), {7, 12, -3})
        self.assertEqual(KP.load(9), set())
        os.environ["FH_KEEP"] = "none"
        KP.apply_env(8)
        self.assertEqual(KP.load(8), set())
        os.environ["FH_KEEP"] = ""
        KP.apply_env(8)                                   # empty leaves the saved list alone
        self.assertEqual(KP.load(8), set())


# ---------------------------------------------------------------------------
# core.matchup_projection: the win chance
# ---------------------------------------------------------------------------
class WinChance(unittest.TestCase):
    @staticmethod
    def var(n_f, n_d):
        game = lambda tm, i: ("BBB", True)             # noqa: E731  everyone plays every day
        team = [sk(i, out=1.0, slot="F") for i in range(n_f)] + [sk(100 + i, grp="D", out=1.0, slot="D") for i in range(n_d)]
        m = C.matchup_projection(team, [], game, 1, {}, {}, 0.0, 0.0)
        return round(m["sd"] ** 2 / C.D.SKATER_SD ** 2, 6)

    def test_full_lineup_counts_fifteen_skaters(self):
        self.assertEqual(self.var(10, 5), 15)

    # BUG C5: the variance counts skater slots as top 9 F + top 5 D, plus the UTIL only when those 14 are full. With
    # exactly 9 F and 5 D playing the UTIL is empty but still counted; with 12 F and 3 D a forward fills the UTIL but it
    # is not counted. It also hard-codes 9/5/1 instead of the league's slots (core.SLOTS / streams.day_value).
    def test_util_counts_only_when_someone_fills_it(self):
        self.assertEqual((self.var(9, 5), self.var(12, 3)), (14, 13))


if __name__ == "__main__":
    unittest.main()
