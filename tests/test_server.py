"""The always-on server's build queue, post-game wait, ESPN sign-in detection and HTTP caching."""
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        os.environ["DATA_DIR"] = str(cls.tmp)
        os.environ["SETTLE_S"] = "1"
        import importlib
        import server
        cls.S = importlib.reload(server)
        cls.S.SEND_ALERTS = False
        site = cls.tmp / "sites" / "1"
        site.mkdir(parents=True)
        (site / "index.html").write_text("<!doctype html>" + "x" * 3000)
        (site / "version.json").write_text('{"code":"a","data":1}')
        (cls.tmp / "live").symlink_to(site)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        S = self.S
        S.ST.update(building=None, queued=None, pending={}, last_start=0.0, login=False, login_alert_day=None)
        self.ran = []
        self.release = threading.Event()

        def fake_build(reason, keep):
            self.ran.append((reason, keep))
            self.release.wait(5)
            return True
        S.do_build = fake_build

    def wait_idle(self):
        for _ in range(100):
            if not self.S.ST["building"] and not self.S.ST["queued"]:
                return
            time.sleep(0.05)

    def test_keep_survives_a_scheduled_build(self):
        S = self.S
        self.assertEqual(S.request_build("auto-fresh"), "started")
        self.assertEqual(S.request_build("keep 1", "123,456", settle=False), "queued")
        self.assertEqual(S.request_build("pre-game 2026-11-22"), "queued")
        self.assertEqual(S.ST["queued"], ("pre-game 2026-11-22", "123,456"))
        self.release.set()
        self.wait_idle()
        self.assertIn(("pre-game 2026-11-22", "123,456"), self.ran)

    def test_on_open_does_not_rename_a_queued_morning_build(self):
        S = self.S
        S.request_build("auto-fresh")
        S.request_build("morning 2026-11-22")
        S.request_build("on-open x")
        self.assertEqual(S.ST["queued"][0], "morning 2026-11-22")
        self.release.set()
        self.wait_idle()

    def test_post_game_waits_without_holding_the_slot(self):
        S = self.S
        self.assertEqual(S.request_build("post-game 2026-11-22"), "waiting")
        self.assertIsNone(S.ST["building"])
        self.assertIn("Daily (post-game 2026-11-22)", S.sched_titles())
        self.assertEqual(S.request_build("post-game 2026-11-22"), "waiting")      # asked twice: still one wait
        self.release.set()
        time.sleep(1.5)
        self.wait_idle()
        self.assertEqual([r for r, _ in self.ran].count("post-game 2026-11-22"), 1)

    def test_login_failure_is_detected(self):
        S = self.S
        S.login_failed("... ESPN rejected your login cookies (they probably expired).")
        self.assertTrue(S.ST["login"])
        self.assertTrue(S.status()["login_expired"])
        S.ST["login"] = False
        S.login_failed("Some other error")
        self.assertFalse(S.ST["login"])

    def test_keep_alive_gzip_and_304(self):
        S = self.S
        from http.server import ThreadingHTTPServer
        srv = ThreadingHTTPServer(("127.0.0.1", 0), S.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
            c.request("GET", "/", headers={"Accept-Encoding": "gzip"})
            r = c.getresponse()
            r.read()
            self.assertEqual(r.status, 200)
            self.assertEqual(r.getheader("Content-Encoding"), "gzip")
            tag = r.getheader("ETag")
            c.request("GET", "/", headers={"Accept-Encoding": "gzip", "If-None-Match": tag})   # same connection
            r = c.getresponse()
            r.read()
            self.assertEqual(r.status, 304)
            c.request("POST", "/api/subscribe", body=json.dumps({"endpoint": "nope"}),
                      headers={"Content-Type": "application/json"})
            r = c.getresponse()
            self.assertEqual(json.loads(r.read()), {"ok": False})
            c.request("GET", "/api/status")
            r = c.getresponse()
            self.assertTrue(json.loads(r.read())["ok"])
            c.close()
        finally:
            srv.shutdown()
            srv.server_close()

    def test_hot_update_checks_files_and_keeps_live_code_on_failure(self):
        S = self.S
        web = ROOT / "web"
        good = {f: (web / f).read_bytes() for f in ("page.html", "app.css", "app.js")}
        self.assertIsNone(S.hot_ok(good))
        self.assertIsNotNone(S.hot_ok(dict(good, **{"app.js": good["app.js"][:5000]})))       # cut-off download
        self.assertIsNotNone(S.hot_ok(dict(good, **{"page.html": b"<html></html>"})))          # slots gone
        S.HOT.update(web=None, sha=None)
        new = dict(good, **{"app.js": good["app.js"] + b"\n;"})
        orig = S.shell_update
        try:
            def boom(why):
                raise RuntimeError("bad page")
            S.shell_update = boom
            self.assertFalse(S.hot_apply("a" * 40, new))
            self.assertIsNone(S.HOT["web"])                                                     # builds keep the last good code
            S.shell_update = lambda why: True
            self.assertTrue(S.hot_apply("b" * 40, new))
            self.assertEqual(S.HOT["sha"], "b" * 40)
            self.assertFalse(S.hot_apply("c" * 40, new))                                       # nothing changed: nothing to do
        finally:
            S.shell_update = orig
            S.HOT.update(web=None, sha=None)


if __name__ == "__main__":
    unittest.main()
