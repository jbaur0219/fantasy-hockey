import unittest
import build


def mv(t, add, drop, g="G", cda=(0, 1)):
    return {"t": t, "add": {"n": add}, "drop": {"n": drop}, "g": g, "cda": list(cda)}


ALERT = ("Connor Hellebuyck is not starting today (Jake Allen is in net). "
         "Swap in Adin Hill, who is listed to start.")


class ReconcileAlerts(unittest.TestCase):
    def run_it(self, moves):
        sd = {"gameplan": {"moves": moves}, "alerts": [{"k": "warn", "t": ALERT}, {"k": "bad", "t": "Other"}]}
        build.reconcile_alerts(sd)
        return [a["t"] for a in sd["alerts"]]

    def test_goalie_add_playing_today_takes_the_spot(self):
        t = self.run_it([mv(0, "Laurent Brossoit", "Adin Hill")])
        self.assertEqual(t[0], "Connor Hellebuyck is not starting today (Jake Allen is in net). "
                               "Today's move drops Adin Hill: add Laurent Brossoit and start him there instead.")
        self.assertEqual(t[1], "Other")

    def test_add_without_a_game_today(self):
        t = self.run_it([mv(0, "Laurent Brossoit", "Adin Hill", cda=(1, 2))])
        self.assertTrue(t[0].endswith("Today's move drops Adin Hill, so he can't fill in."))

    def test_move_on_a_later_day_changes_nothing(self):
        self.assertEqual(self.run_it([mv(1, "Laurent Brossoit", "Adin Hill")])[0], ALERT)

    def test_no_plan(self):
        sd = {"alerts": [{"k": "warn", "t": ALERT}]}
        build.reconcile_alerts(sd)
        self.assertEqual(sd["alerts"][0]["t"], ALERT)


if __name__ == "__main__":
    unittest.main()
