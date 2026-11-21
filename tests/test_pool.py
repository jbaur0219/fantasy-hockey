#!/usr/bin/env python3
"""The search list of every other player (pool.json). Run:  python -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pool as POOL   # noqa: E402

SCHED = {"settings": {"proTeams": [
    {"id": 9, "abbrev": "DAL", "proGamesByScoringPeriod": {"50": [{"id": 1, "date": 1000}]}},
    {"id": 20, "abbrev": "TB", "proGamesByScoringPeriod": {}}]}}
DATA = {"roster": {"scoringPeriodId": 50}, "schedules": SCHED}


def pl(pid, name, team=9, pos=2, gp=10, inj="ACTIVE"):
    return {"id": pid, "fullName": name, "defaultPositionId": pos, "proTeamId": team, "injuryStatus": inj,
            "ownership": {"percentOwned": 3.5},
            "stats": [{"id": "002027", "appliedTotal": 12.0, "stats": {"30": gp}}]}


class Pool(unittest.TestCase):
    cfg = {"season": 2027, "league": "1", "cookies": {}}
    site = {"matchup": {"days_left": 3},
            "mine": [{"id": 1}], "fas": [{"id": 2}], "teams": [{"players": [{"id": 3}]}]}

    def build(self, players):
        return POOL.build(self.cfg, DATA, self.site, {}, 0, raw={"players": players})

    def test_only_players_the_page_does_not_have(self):
        out = self.build([{"player": pl(1, "Mine")}, {"player": pl(2, "Top FA")}, {"player": pl(3, "Rostered")},
                          {"player": pl(40, "Deep Cut"), "status": "WAIVERS"}, {"player": pl(40, "Deep Cut")}])
        self.assertEqual([p["id"] for p in out["p"]], [40])          # known players and repeats are skipped
        self.assertEqual(out["n"], 1)
        p = out["p"][0]
        self.assertEqual((p["n"], p["tm"], p["slot"], p["st"]), ("Deep Cut", "DAL", "FA", "WAIVERS"))
        self.assertIn("out", p)                                       # same short keys as the page data

    def test_injured_players_are_kept_but_teamless_unknowns_are_not(self):
        out = self.build([{"player": pl(41, "Hurt Guy", inj="INJURY_RESERVE")},
                          {"player": pl(42, "No Team", team=0, gp=0)}])
        self.assertEqual([p["n"] for p in out["p"]], ["Hurt Guy"])
        self.assertEqual(out["p"][0]["inj"], "INJURY_RESERVE")

    def test_fetch_asks_espn_for_everyone_not_on_a_team(self):
        seen = {}

        def get(url, cookies, params=None, headers=None):
            seen.update(url=url, params=params, headers=headers)
            return {"players": []}
        POOL.fetch(self.cfg, get)
        self.assertIn("/leagues/1", seen["url"])
        self.assertIn('"FREEAGENT", "WAIVERS"', seen["headers"]["x-fantasy-filter"])
        self.assertIn(str(POOL.POOL_LIMIT), seen["headers"]["x-fantasy-filter"])


if __name__ == "__main__":
    unittest.main()
