"""Waiver claims already in with ESPN (pending.py, 2026-11-26).

The user claimed Ian Moore for Rasmus Andersson; ESPN only moves a claimed player onto the roster when it processes
(overnight), so for a day the app still saw Moore as an open add and kept suggesting the move. A pending claim now
counts as made from the day it processes."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import core as C                                         # noqa: E402
import dashboard as D                                    # noqa: E402
import longterm as LT                                    # noqa: E402
import pending as PN                                     # noqa: E402
import streams as STR                                    # noqa: E402
from test_plan_list import DAYS, player                  # noqa: E402

ME = 1
ANDERSSON, MOORE = 4001, 5002


def espn_answer(**over):
    """The shape of ESPN's mPendingTransactions answer (read from ESPN's own format; not yet seen live)."""
    tx = {"id": "abc", "type": "WAIVER", "status": "PENDING", "teamId": ME, "bidAmount": 0,
          "items": [{"type": "ADD", "playerId": MOORE, "fromTeamId": -1, "toTeamId": ME},
                    {"type": "DROP", "playerId": ANDERSSON, "fromTeamId": ME, "toTeamId": -1}]}
    tx.update(over)
    return {"pendingTransactions": [tx]}


class Parse(unittest.TestCase):
    def test_reads_the_add_and_the_drop(self):
        self.assertEqual(PN.parse(espn_answer(), ME), [{"add": MOORE, "drop": ANDERSSON, "type": "WAIVER"}])

    def test_ignores_what_is_not_a_pending_claim_of_yours(self):
        self.assertEqual(PN.parse(espn_answer(status="EXECUTED"), ME), [])        # already processed
        self.assertEqual(PN.parse(espn_answer(status="CANCELED"), ME), [])
        self.assertEqual(PN.parse(espn_answer(teamId=7), ME), [])                 # another team's claim
        self.assertEqual(PN.parse(espn_answer(type="TRADE_PROPOSAL"), ME), [])    # trades are not claims
        self.assertEqual(PN.parse({}, ME), [])
        self.assertEqual(PN.parse(None, ME), [])
        self.assertEqual(PN.parse({"pendingTransactions": ["junk", None]}, ME), [])

    def test_claim_without_a_drop(self):
        tx = espn_answer()["pendingTransactions"][0]
        tx["items"] = tx["items"][:1]
        self.assertEqual(PN.parse({"pendingTransactions": [tx]}, ME), [{"add": MOORE, "drop": None, "type": "WAIVER"}])

    def test_resolve_names_them_and_skips_a_player_already_on_your_roster(self):
        site = {"mine": [player(ANDERSSON, "Rasmus Andersson", grp="D")], "fas": [player(MOORE, "Ian Moore")]}
        c = PN.resolve(espn_answer(), ME, site, 4)[0]
        self.assertEqual((c["add_n"], c["drop_n"], c["t"], c["this_week"]), ("Ian Moore", "Rasmus Andersson", 1, True))
        site["mine"].append(player(MOORE, "Ian Moore"))                           # processed: he is on the roster now
        self.assertEqual(PN.resolve(espn_answer(), ME, site, 4), [])

    def test_last_day_of_the_matchup_the_claim_lands_next_week(self):
        site = {"mine": [], "fas": [player(MOORE, "Ian Moore")]}
        c = PN.resolve(espn_answer(), ME, site, 1)[0]
        self.assertFalse(c["this_week"])
        self.assertEqual(PN.count_this_week([c]), 0)


class Budget(unittest.TestCase):
    LG = {"status": {"currentMatchupPeriod": 9},
          "settings": {"acquisitionSettings": {"matchupAcquisitionLimit": 4}},
          "teams": [{"id": ME, "transactionCounter": {"matchupAcquisitionTotals": {"9": 1}}}]}

    def test_a_pending_claim_uses_one_of_the_weeks_moves(self):
        self.assertEqual(D.move_budget(self.LG, ME, days=7)["left"], 3)
        b = D.move_budget(self.LG, ME, days=7, pending=1)
        self.assertEqual((b["used"], b["left"]), (2, 2))


def vals(p, *a, **k):
    return list(p["_v"])


class PlanKnowsTheClaim(unittest.TestCase):
    """Nine forwards (eight solid + Andersson here, a weak one) and a free agent who is clearly better."""

    def setUp(self):
        self.mine = [player(100 + i, f"Solid F{i}", out=2.0) for i in range(8)]
        for p in self.mine:
            p["_v"] = [2.0] * 4
        self.anders = player(ANDERSSON, "Rasmus Andersson", out=0.5)
        self.anders["_v"] = [0.5] * 4
        self.mine.append(self.anders)
        self.moore = player(MOORE, "Ian Moore", out=2.0)
        self.moore["_v"] = [2.0] * 4
        self.moore["st"] = "WAIVERS"
        self.fas = [self.moore]

    def plan(self, pending=None):
        with mock.patch.object(STR, "values", vals), mock.patch.object(STR, "add_ok", return_value=True), \
                mock.patch.object(STR, "drop_rule", return_value=(True, 1.0)), \
                mock.patch.object(C, "cost", return_value=0.0), mock.patch.object(LT, "assess", return_value=None):
            return C.plan(self.mine, self.fas, None, 4, DAYS, {}, {}, 7, {}, reasons=False, pending=pending)

    CLAIM = [{"add": MOORE, "drop": ANDERSSON, "t": 1}]

    def test_without_the_claim_the_app_suggests_the_move(self):
        res = self.plan()
        self.assertEqual([(m["add"]["n"], m["drop"]["n"]) for m in res["moves"]], [("Ian Moore", "Rasmus Andersson")])

    def test_with_the_claim_it_no_longer_suggests_it(self):
        res = self.plan(self.CLAIM)
        self.assertEqual(res["moves"], [])
        self.assertEqual(res["small"], [])

    def test_the_claim_counts_toward_the_weeks_baseline(self):
        # Moore plays days 1-3 instead of Andersson: (2.0 - 0.5) * 3 = 4.5 more than the roster as it stands today
        no, yes = self.plan(), self.plan(self.CLAIM)
        self.assertAlmostEqual(yes["base"] - no["base"], 4.5, places=3)
        self.assertAlmostEqual(yes["total"], no["total"], places=3)     # the same lineup the suggested move gave

    def test_the_claimed_player_is_never_a_drop_candidate(self):
        self.fas.append(self.better())
        res = self.plan(self.CLAIM)
        self.assertNotIn(MOORE, [m["drop"]["id"] for m in res["moves"]])
        self.assertNotIn(ANDERSSON, [m["drop"]["id"] for m in res["moves"]])

    def better(self):
        p = player(6003, "Even Better", out=3.0)
        p["_v"] = [3.0] * 4
        return p

    def test_other_moves_are_still_found(self):
        # a different weak forward is still worth a move: the claim only settles Moore and Andersson
        weak = player(300, "Other Weak", out=0.4)
        weak["_v"] = [0.4] * 4
        self.mine.append(weak)                       # now 10 forwards: Moore (joins day 1) displaces the UTIL spot too
        self.fas.append(self.better())
        res = self.plan(self.CLAIM)
        self.assertEqual([(m["add"]["n"], m["drop"]["n"]) for m in res["moves"]], [("Even Better", "Other Weak")])

    def test_claim_not_in_the_free_agent_list_still_protects_the_drop(self):
        self.fas = []
        res = self.plan([{"add": 999, "drop": ANDERSSON, "t": 1}])
        self.assertEqual(res["moves"], [])

    def test_before_and_after_rows_use_the_claim(self):
        with mock.patch.object(STR, "values", vals), mock.patch.object(STR, "add_ok", return_value=True), \
                mock.patch.object(STR, "drop_rule", return_value=(True, 1.0)):
            ents, base, pool = C.build_inputs(self.mine, self.fas, None, 4, {}, {}, pending=self.CLAIM)
        self.assertEqual(pool, [])                                         # Moore is not an add candidate any more
        by = {e["p"]["id"]: e for e in ents}
        self.assertEqual((by[ANDERSSON]["leave"], by[MOORE]["join"]), (1, 1))
        row = next(b for b in base if b["p"]["id"] == MOORE)
        self.assertEqual(row["v"], [0.0, 2.0, 2.0, 2.0])                   # only the days he is on your roster
        self.assertFalse(row["ok"])


class Projection(unittest.TestCase):
    def test_win_projection_counts_the_claimed_player_from_tomorrow(self):
        mine = [player(100, "Solid", out=2.0), player(ANDERSSON, "Rasmus Andersson", out=0.5)]
        moore = player(MOORE, "Ian Moore", out=2.0)
        by = {100: 2.0, ANDERSSON: 0.5, MOORE: 2.0}

        def v(p, *a, **k):
            return [by[p["id"]]] * 3
        with mock.patch.object(STR, "values", v):
            no = C.matchup_projection(mine, [], None, 3, {}, {}, 0.0, 0.0)
            yes = C.matchup_projection(mine, [], None, 3, {}, {}, 0.0, 0.0,
                                       pending=[{"add": MOORE, "drop": ANDERSSON, "t": 1}], fas=[moore])
        self.assertAlmostEqual(yes["rest_me"] - no["rest_me"], 2 * (2.0 - 0.5), places=3)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# weekplan.py: a claim in flight is neither "changed" nor "missed"; it is logged "done" once he is on the roster
# ---------------------------------------------------------------------------
import json                                              # noqa: E402

import weekplan as WK                                    # noqa: E402
from test_review_scoring import H, LABELS, LOCK, _Files, move   # noqa: E402


def build(now, moves, mine, pending=None):
    clock = {"labels": LABELS, "lock": LOCK, "dates": ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19"]}
    site = {"gameplan": {"moves": moves, "small": []}, "clock": clock, "mine": [{"id": i} for i in mine],
            "fas": [{"id": 1, "inj": "ACTIVE"}], "matchup": None, "pending": pending or []}
    return WK.build({}, {}, {"status": {"currentMatchupPeriod": 8}}, {}, now, site, healthy=True)


class WeeklyPlanMemory(_Files):
    CLAIM = [{"add": 1, "drop": 2, "t": 1}]

    def rows(self):
        return [json.loads(x) for x in WK.LOG_FILE.read_text().splitlines()] if WK.LOG_FILE.exists() else []

    def test_claim_in_flight_is_not_a_change_and_not_a_miss(self):
        build(1 * H, [move("Wed")], mine=(2,))                              # the plan says: add 1, drop 2 on Wednesday
        out = build(30 * H, [], mine=(2,), pending=self.CLAIM)              # you put the claim in; the plan drops the move
        self.assertEqual(out["changes"], [])
        out = build(60 * H, [], mine=(2,), pending=self.CLAIM)              # Wednesday's first puck, still waiting
        self.assertEqual(out["missed"], [])
        self.assertEqual(self.rows(), [])

    def test_claim_that_processes_is_logged_done(self):
        build(1 * H, [move("Wed")], mine=(2,))
        build(30 * H, [], mine=(2,), pending=self.CLAIM)
        out = build(50 * H, [], mine=(1,))                                  # processed overnight: he is on your roster
        self.assertEqual([r["result"] for r in self.rows()], ["done"])
        self.assertEqual(len(out["done"]), 1)

    def test_without_a_claim_a_dropped_move_is_still_missed(self):
        build(1 * H, [move("Wed")], mine=(2,))
        build(60 * H, [], mine=(2,))
        self.assertEqual([r["result"] for r in self.rows()], ["missed"])
