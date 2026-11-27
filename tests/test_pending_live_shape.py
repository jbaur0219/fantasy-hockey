"""Pending waiver claims, using the exact shape ESPN returned for the league on 2026-11-27 (view=mTransactions2):
the Ian Moore claim (add 4997137, drop Rasmus Andersson 3904186) stays status PENDING forever under the day it was made,
and ESPN adds a separate EXECUTED record pointing back to it (relatedTransactionId) under the day it processed."""
import unittest
from unittest import mock

import pending as PN

ME, MOORE, ANDERSSON = 1, 4997137, 3904186
CLAIM_ID = "161b515d-0819-4190-9e21-827a43b1ef6e"


def claim():
    return {"id": CLAIM_ID, "status": "PENDING", "type": "WAIVER", "teamId": ME, "isPending": True,
            "executionType": "EXECUTE", "scoringPeriodId": 59, "bidAmount": 0,
            "items": [{"type": "ADD", "playerId": MOORE, "fromTeamId": 0, "toTeamId": ME},
                      {"type": "DROP", "playerId": ANDERSSON, "fromTeamId": ME, "toTeamId": 0}]}


def executed():
    return {"id": "508ec841-26f9-42c3-96a9-2969187d87f3", "status": "EXECUTED", "type": "WAIVER", "teamId": ME,
            "isPending": False, "executionType": "PROCESS", "relatedTransactionId": CLAIM_ID, "scoringPeriodId": 60,
            "items": [{"type": "ADD", "playerId": MOORE, "fromTeamId": 0, "toTeamId": ME},
                      {"type": "DROP", "playerId": ANDERSSON, "fromTeamId": ME, "toTeamId": 0}]}


def lost():
    e = executed()
    e.update(id="87a6", status="FAILED_INVALIDPLAYERSOURCE")
    return e


class LiveShape(unittest.TestCase):
    def test_claim_in_flight_is_read(self):
        self.assertEqual(PN.parse({"transactions": [claim()]}, ME), [{"add": MOORE, "drop": ANDERSSON, "type": "WAIVER"}])

    def test_processed_claim_is_not_pending_any_more(self):
        self.assertEqual(PN.parse({"transactions": [claim(), executed()]}, ME), [])

    def test_failed_claim_is_not_pending_any_more(self):
        self.assertEqual(PN.parse({"transactions": [claim(), lost()]}, ME), [])

    def test_fetch_reads_today_and_two_days_back_and_merges(self):
        calls = []

        def fake(url, cookies, params=None, headers=None):
            calls.append(dict(params))
            sp = dict(params).get("scoringPeriodId")
            view = dict(params)["view"]
            if view == "mPendingTransactions":
                return {"id": 1, "scoringPeriodId": 60}                # what ESPN really answers: no transactions
            if sp is None:
                return {"scoringPeriodId": 60, "transactions": []}
            if sp == 59:
                return {"scoringPeriodId": 59, "transactions": [claim()]}
            return {"scoringPeriodId": sp, "transactions": []}

        cfg = {"season": 2027, "league": "1", "team": ME, "cookies": {}}
        with mock.patch.object(PN.A, "espn_get", side_effect=fake):
            raw = PN.fetch(cfg)
        self.assertEqual(PN.parse(raw, ME), [{"add": MOORE, "drop": ANDERSSON, "type": "WAIVER"}])
        self.assertIn(59, [c.get("scoringPeriodId") for c in calls])
        self.assertIn(58, [c.get("scoringPeriodId") for c in calls])

    def test_fetch_none_when_espn_unreadable(self):
        cfg = {"season": 2027, "league": "1", "team": ME, "cookies": {}}
        with mock.patch.object(PN.A, "espn_get", side_effect=RuntimeError("down")):
            self.assertIsNone(PN.fetch(cfg))


if __name__ == "__main__":
    unittest.main()
