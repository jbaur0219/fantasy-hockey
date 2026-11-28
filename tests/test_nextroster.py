"""Once today is locked, the plan uses tomorrow's ESPN roster (nextroster.py).

Case from the live league, 2026-11-27: after Friday's first puck the user moved Martin Necas (OUT) to IR and added
Colton Sissons. ESPN filed both for Saturday, so Friday's roster still had Necas in a forward spot and no Sissons, and
the app suggested "Add Jake McCabe, move Necas to IR" again."""
import unittest

import analyze as A
import dashboard as D
import nextroster as NR

ME = 1
SLOT = {"F": 3, "D": 4, "G": 5, "UTIL": 6, "BN": 7, "IR": 8}


def ent(pid, name, slot, pos=3, inj="ACTIVE"):
    return {"playerId": pid, "lineupSlotId": SLOT[slot],
            "playerPoolEntry": {"player": {"id": pid, "fullName": name, "defaultPositionId": pos, "proTeamId": 1,
                                           "injuryStatus": inj, "stats": []}}}


def data_with(entries):
    return {"roster": {"scoringPeriodId": 60, "teams": [{"id": ME, "roster": {"entries": entries}},
                                                        {"id": 2, "roster": {"entries": [ent(9, "Other Guy", "F")]}}]},
            "schedules": {}, "free_agents": {"players": []}}


def slim(p, standings):
    return {"id": p["id"], "n": p["name"], "grp": p["group"], "slot": A.slot_name(p["slot"]), "inj": p["injury"]}


TODAY = [ent(1, "Martin Necas", "F", inj="OUT"), ent(2, "Jason Robertson", "F"), ent(3, "Adin Hill", "G", pos=5),
         ent(4, "Leo Carlsson", "IR", inj="INJURY_RESERVE"), ent(5, "Dropped Tonight", "BN")]
TOMORROW = [ent(1, "Martin Necas", "IR", inj="OUT"), ent(2, "Jason Robertson", "F"), ent(3, "Adin Hill", "BN", pos=5),
            ent(4, "Leo Carlsson", "IR", inj="INJURY_RESERVE"), ent(6, "Colton Sissons", "F")]


class PlanRosterTests(unittest.TestCase):
    def run_plan(self, tomorrow):
        data = data_with(TODAY)
        site = {"mine": [slim(p, None) for p in A.build_players(data, {"season": 2027, "team": ME})[0]]}
        calls = []

        def fetch(url, cookies, params=None):
            calls.append(dict(params))
            return {"teams": [{"id": ME, "roster": {"entries": tomorrow}}]} if tomorrow is not None else {"teams": []}
        plan, why = NR.plan_roster({"season": 2027, "league": 5, "team": ME, "cookies": {}}, data, site, None, slim,
                                   fetch_fn=fetch)
        return plan, why, site, calls

    def test_ir_move_and_add_made_after_the_lock_count_as_made(self):
        plan, why, site, calls = self.run_plan(TOMORROW)
        self.assertEqual(calls[0]["scoringPeriodId"], 61)
        self.assertEqual(calls[0]["forTeamId"], ME)
        by = {p["n"]: p for p in plan}
        self.assertEqual(by["Martin Necas"]["slot"], "IR")          # no second "move Necas to IR"
        self.assertIn("Colton Sissons", by)                         # the add is on the roster
        self.assertNotIn("Dropped Tonight", by)
        self.assertEqual(by["Adin Hill"]["slot"], "G")              # only IR moves carry over
        self.assertEqual(D.ir_free({"settings": {"rosterSettings": {"lineupSlotCounts": {"8": 3}}}}, plan), 1)
        self.assertEqual(D.ir_free({"settings": {"rosterSettings": {"lineupSlotCounts": {"8": 3}}}}, site["mine"]), 2)
        self.assertIn("Colton Sissons", why)

    def test_page_list_keeps_today_and_gains_tomorrows_players(self):
        plan, why, site, calls = self.run_plan(TOMORROW)
        by = {p["n"]: p for p in site["mine"]}
        self.assertEqual(by["Martin Necas"]["slot"], "F")           # live views read today's spot
        self.assertEqual(by["Martin Necas"].get("irn"), 1)          # no injury push: he's in IR from tomorrow
        self.assertEqual(by["Colton Sissons"].get("nx"), 1)
        self.assertIn("Dropped Tonight", by)

    def test_unreadable_tomorrow_changes_nothing(self):
        plan, why, site, calls = self.run_plan(None)
        self.assertIsNone(plan)
        self.assertEqual(len(site["mine"]), 5)
        self.assertFalse(any(p.get("irn") or p.get("nx") for p in site["mine"]))


if __name__ == "__main__":
    unittest.main()
