"""Phone alerts: the push sender reports what happened, the welcome push retries until it really goes through,
and a new injury on your roster sends one push with the plan's answer."""
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build as B
import notify as N


class FakeErr(Exception):
    def __init__(self, code, text):
        self.response = type("R", (), {"status_code": code, "text": text})()


def fake_webpush_factory(fail=None):
    def fake(subscription_info, **kw):
        ep = subscription_info["endpoint"]
        if fail and ep in fail:
            import pywebpush
            e = pywebpush.WebPushException("boom")
            e.response = type("R", (), {"status_code": fail[ep][0], "text": fail[ep][1]})()
            raise e
        return type("R", (), {"status_code": 201})()
    return fake


class SendTests(unittest.TestCase):
    def test_reports_each_phone_and_marks_dead_links(self):
        cfg = {"vapid_private": "k", "subscriptions": [{"endpoint": "https://a"}, {"endpoint": "https://b"},
                                                         {"endpoint": "https://c"}]}
        fail = {"https://b": (410, "gone"), "https://c": (403, "BadJwtToken")}
        with mock.patch("pywebpush.webpush", fake_webpush_factory(fail)):
            res = N.send(cfg, {"title": "t"})
        self.assertEqual([r["ok"] for r in res], [True, False, False])
        self.assertTrue(res[1]["dead"])
        self.assertFalse(res[2].get("dead"))
        self.assertEqual((res[2]["code"], res[2]["detail"]), (403, "BadJwtToken"))


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["DATA_DIR"] = str(self.tmp)
        import server
        self.S = importlib.reload(server)
        self.S.SEND_ALERTS = True
        self.sub = {"endpoint": "https://web.push.apple.com/abc", "keys": {"p256dh": "x", "auth": "y"}}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_welcome_only_counts_when_it_went_through(self):
        S = self.S
        with mock.patch.object(S, "welcome"):                      # add_sub starts it on a thread; run it by hand below
            S.add_sub(self.sub)
        with mock.patch("pywebpush.webpush", fake_webpush_factory({self.sub["endpoint"]: (403, "BadJwtToken")})):
            S.welcome(self.sub["endpoint"])
        self.assertFalse(S.load_subs()[0]["welcome_ok"])
        log = json.loads(S.ALERT_LOG.read_text())
        self.assertFalse(log[-1]["phones"][0]["ok"])
        self.assertEqual(log[-1]["phones"][0]["detail"], "BadJwtToken")
        with mock.patch("pywebpush.webpush", fake_webpush_factory()):
            S.welcome(self.sub["endpoint"])
        self.assertTrue(S.load_subs()[0]["welcome_ok"])

    def test_dead_phone_is_forgotten(self):
        S = self.S
        S.write_atomic(S.DATA / "subs.json", json.dumps([dict(self.sub, welcome_ok=True)]))
        with mock.patch("pywebpush.webpush", fake_webpush_factory({self.sub["endpoint"]: (410, "gone")})):
            S.push_to(S.load_subs(), {"title": "x"})
        self.assertEqual(S.load_subs(), [])

    def test_test_alert_and_rate_limit(self):
        S = self.S
        self.assertFalse(S.send_test()["ok"])                      # no phone yet
        S.TEST["at"] = 0
        S.write_atomic(S.DATA / "subs.json", json.dumps([self.sub]))
        with mock.patch("pywebpush.webpush", fake_webpush_factory()):
            r = S.send_test()
            again = S.send_test()
        self.assertTrue(r["ok"])
        self.assertEqual(again["why"], "wait a few seconds")

    def test_injury_alert_fires_once_per_new_injury(self):
        S = self.S
        S.write_atomic(S.DATA / "subs.json", json.dumps([self.sub]))
        work = S.DATA / "work"
        work.mkdir()
        sent = []
        with mock.patch.object(S, "notify", lambda f: sent.append(json.loads(Path(f).read_text()))):
            def state(d):
                (work / "injury_state.json").write_text(json.dumps(d))
                S.injury_alerts_for(work)
            old = {"1": {"title": "t1", "body": "b1"}}
            state(old)                                             # first build: only records who is hurt
            self.assertEqual(sent, [])
            state(old)
            self.assertEqual(sent, [])
            state({**old, "2": {"title": "t2", "body": "b2"}})     # a new injury
            self.assertEqual([x["title"] for x in sent], ["t2"])
            state({**old, "2": {"title": "t2", "body": "b2"}})     # still hurt: no second push
            self.assertEqual(len(sent), 1)
            state(old)                                             # healthy again
            state({**old, "2": {"title": "t2", "body": "b2"}})     # hurt again: alerts again
            self.assertEqual(len(sent), 2)


class InjuryTextTests(unittest.TestCase):
    clock = {"lock": [1_700_000_000_000, 1_700_086_400_000], "labels": ["Wed", "Thu"], "dates": ["a", "b"]}

    def site(self, moves, slot="C", inj="OUT"):
        return {"clock": self.clock, "gameplan": {"moves": moves},
                "mine": [{"id": 7, "n": "Leo Carlsson", "inj": inj, "slot": slot},
                         {"id": 8, "n": "Healthy Guy", "inj": "ACTIVE", "slot": "C"}]}

    def test_names_the_replacement_when_the_plan_drops_him(self):
        mv = {"t": 1, "day": "Thu Nov 26", "gain": 2.4, "ir": True,
              "add": {"id": 9, "n": "Connor Brown", "tm": "EDM"}, "drop": {"id": 7, "n": "Leo Carlsson"}}
        a = B.injury_alerts(self.site([mv]), 0)
        self.assertEqual(list(a), ["7"])
        self.assertIn("Move Leo Carlsson to IR and add Connor Brown (EDM) Thu", a["7"]["body"])
        self.assertIn("+2.4 pts", a["7"]["body"])

    def test_points_to_the_next_move_otherwise(self):
        mv = {"t": 0, "day": "Wed Nov 25", "gain": 1.1, "add": {"id": 9, "n": "Connor Brown", "tm": "EDM"},
              "drop": {"id": 5, "n": "Some Guy"}}
        self.assertIn("Next move: add Connor Brown", B.injury_alerts(self.site([mv]), 0)["7"]["body"])

    def test_no_move_says_so_and_players_already_on_ir_are_skipped(self):
        self.assertIn("No pickup beats keeping him", B.injury_alerts(self.site([]), 0)["7"]["body"])
        self.assertEqual(B.injury_alerts(self.site([], slot="IR"), 0), {})
        self.assertEqual(B.injury_alerts(self.site([], inj="DAY_TO_DAY"), 0), {})


if __name__ == "__main__":
    unittest.main()
