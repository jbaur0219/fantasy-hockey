"""Accounts, sign-in and the server's access rules (auth.py + server.Handler)."""
import http.client
import importlib
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import auth as A  # noqa: E402


class Clock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


class AuthUnit(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.clock = Clock()
        self.au = A.Auth(self.tmp, now=self.clock)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_password_is_hashed_never_stored(self):
        self.au.add_user("jake", "correct horse")
        raw = (self.tmp / "users.json").read_text()
        self.assertNotIn("correct horse", raw)
        self.assertTrue(A.check_password("correct horse", json.loads(raw)["jake"]["pw"]))
        self.assertFalse(A.check_password("wrong", json.loads(raw)["jake"]["pw"]))

    def test_login_and_session(self):
        self.au.add_user("Jake", "correct horse")
        tok, why = self.au.login("jake", "correct horse")
        self.assertIsNone(why)
        self.assertEqual(self.au.session(tok)["name"], "jake")
        self.assertNotIn(tok, (self.tmp / "sessions.json").read_text())      # only a hash of the token is kept
        self.assertEqual(self.au.login("jake", "nope"), (None, "bad"))
        self.assertEqual(self.au.login("nobody", "correct horse"), (None, "bad"))
        self.au.logout(tok)
        self.assertIsNone(self.au.session(tok))

    def test_sessions_expire_unless_used(self):
        self.au.add_user("jake", "correct horse")
        tok, _ = self.au.login("jake", "correct horse")
        self.clock.t += 170 * 86400                  # used again inside 180 days: renewed
        self.assertIsNotNone(self.au.session(tok))
        self.clock.t += 170 * 86400
        self.assertIsNotNone(self.au.session(tok))
        self.clock.t += 181 * 86400                  # not used for 181 days: gone
        self.assertIsNone(self.au.session(tok))

    def test_wrong_passwords_are_rate_limited(self):
        self.au.add_user("jake", "correct horse")
        for _ in range(A.MAX_FAILS):
            self.assertEqual(self.au.login("jake", "guess", ip="1.2.3.4")[1], "bad")
        self.assertEqual(self.au.login("jake", "correct horse", ip="9.9.9.9")[1], "slow down")   # per account too
        self.clock.t += A.FAIL_WINDOW + 1
        self.assertIsNone(self.au.login("jake", "correct horse", ip="1.2.3.4")[1])

    def test_invite_is_single_use(self):
        self.au.ensure_owner("jake", "owner password")
        code = self.au.invite("jake")
        tok, msg = self.au.signup(code, "friend", "friend password")
        self.assertIsNone(msg)
        self.assertEqual(self.au.session(tok)["role"], "member")
        self.assertEqual(self.au.signup(code, "other", "other password")[1], "That invite code isn't valid.")

    def test_invite_expires(self):
        code = self.au.invite("jake")
        self.clock.t += (A.INVITE_DAYS + 1) * 86400
        self.assertIsNotNone(self.au.signup(code, "friend", "friend password")[1])

    def test_owner_password_change_signs_devices_out(self):
        self.au.ensure_owner("jake", "first password")
        tok, _ = self.au.login("jake", "first password")
        self.au.ensure_owner("jake", "second password")
        self.assertIsNone(self.au.session(tok))
        self.assertIsNotNone(self.au.login("jake", "second password")[0])

    def test_bad_names_and_short_passwords(self):
        for name, pw in (("ab", "long enough"), ("../etc", "long enough"), ("ok_name", "short")):
            with self.assertRaises(ValueError):
                self.au.add_user(name, pw)


class ServerAccess(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        os.environ["DATA_DIR"] = str(cls.tmp)
        import server
        cls.S = importlib.reload(server)
        cls.S.SEND_ALERTS = False
        cls.S.request_refresh = lambda reason, keep, force: {"ok": True, "reason": reason}
        site = cls.tmp / "sites" / "1"
        site.mkdir(parents=True)
        (site / "index.html").write_text("<!doctype html>app")
        (site / "data.json").write_text('{"team": "secret roster"}')
        (site / "manifest.webmanifest").write_text("{}")
        (site / "icon-192-v4.png").write_bytes(b"png")
        (cls.tmp / "live").symlink_to(site)
        (cls.tmp / "history").mkdir()
        (cls.tmp / "history" / "backtest.md").write_text("# Backtest")
        cls.S.AU = A.Auth(cls.tmp)
        cls.S.AU.ensure_owner("jake", "owner password")
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), cls.S.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.S.AUTH_ON = True

    def req(self, method, path, body=None, cookie=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=5)
        h = dict(headers or {})
        if body is not None:
            h.setdefault("Content-Type", "application/json")
        if cookie:
            h["Cookie"] = cookie
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        data = r.read()
        c.close()
        return r, data

    def sign_in(self, name="jake", pw="owner password"):
        r, _ = self.req("POST", "/api/login", {"name": name, "password": pw})
        self.assertEqual(r.status, 200)
        sc = r.getheader("Set-Cookie")
        self.assertIn("HttpOnly", sc)
        self.assertIn("SameSite=Lax", sc)
        return sc.split(";")[0]

    def test_auth_off_works_as_before(self):
        self.S.AUTH_ON = False
        self.assertEqual(self.req("GET", "/data.json")[0].status, 200)
        self.assertEqual(self.req("GET", "/")[0].status, 200)
        r, b = self.req("POST", "/api/refresh", {"reason": "open"})
        self.assertEqual((r.status, json.loads(b)["ok"]), (200, True))

    def test_auth_on_locks_data_and_apis(self):
        r, _ = self.req("GET", "/")
        self.assertEqual((r.status, r.getheader("Location")), (303, "/login"))
        r, b = self.req("GET", "/data.json")
        self.assertEqual(r.status, 401)
        self.assertNotIn(b"secret", b)
        self.assertEqual(self.req("GET", "/api/status")[0].status, 401)
        self.assertEqual(self.req("POST", "/api/refresh", {"reason": "x"})[0].status, 401)
        self.assertEqual(self.req("POST", "/api/subscribe", {})[0].status, 401)

    def test_home_screen_pieces_stay_open(self):
        for p in ("/login", "/manifest.webmanifest", "/icon-192-v4.png"):
            self.assertEqual(self.req("GET", p)[0].status, 200, p)

    def test_signed_in_sees_the_app(self):
        ck = self.sign_in()
        r, b = self.req("GET", "/data.json", cookie=ck)
        self.assertEqual((r.status, b), (200, b'{"team": "secret roster"}'))
        self.assertEqual(self.req("POST", "/api/refresh", {"reason": "x"}, cookie=ck)[0].status, 200)
        r, b = self.req("GET", "/api/me", cookie=ck)
        self.assertEqual(json.loads(b)["user"], {"name": "jake", "role": "owner"})
        r, _ = self.req("POST", "/api/logout", {}, cookie=ck)
        self.assertIn("Max-Age=0", r.getheader("Set-Cookie"))
        self.assertEqual(self.req("GET", "/data.json", cookie=ck)[0].status, 401)

    def test_wrong_password(self):
        r, b = self.req("POST", "/api/login", {"name": "jake", "password": "nope nope"})
        self.assertEqual(r.status, 401)
        self.assertIsNone(r.getheader("Set-Cookie"))

    def test_other_sites_cannot_post_with_your_cookie(self):
        ck = self.sign_in()
        r, _ = self.req("POST", "/api/refresh", {"reason": "x"}, cookie=ck,
                        headers={"Origin": "https://evil.example", "Content-Type": "application/json"})
        self.assertEqual(r.status, 403)
        r, _ = self.req("POST", "/api/refresh", {"reason": "x"}, cookie=ck, headers={"Content-Type": "text/plain"})
        self.assertEqual(r.status, 403)
        port = self.srv.server_address[1]
        r, _ = self.req("POST", "/api/refresh", {"reason": "x"}, cookie=ck,
                        headers={"Origin": f"http://127.0.0.1:{port}", "Content-Type": "application/json"})
        self.assertEqual(r.status, 200)

    def test_owner_pages_are_owner_only_even_with_auth_off(self):
        self.S.AUTH_ON = False
        self.assertEqual(self.req("GET", "/admin/backtest")[0].status, 404)
        self.assertEqual(self.req("GET", "/admin/invite")[0].status, 404)
        code = self.S.AU.invite("jake")
        r, _ = self.req("POST", "/api/signup", {"code": code, "name": "pal", "password": "pal password"})
        member = r.getheader("Set-Cookie").split(";")[0]
        self.assertEqual(self.req("GET", "/admin/backtest", cookie=member)[0].status, 404)
        self.assertEqual(self.req("POST", "/api/invite", {}, cookie=member)[0].status, 403)
        owner = self.sign_in()
        r, b = self.req("GET", "/admin/backtest", cookie=owner)
        self.assertEqual((r.status, b), (200, b"# Backtest"))
        self.assertEqual(self.req("GET", "/admin/invite", cookie=owner)[0].status, 200)
        r, b = self.req("POST", "/api/invite", {}, cookie=owner)
        self.assertRegex(json.loads(b)["code"], r"^[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}$")

    def test_security_headers(self):
        r, _ = self.req("GET", "/login")
        self.assertEqual(r.getheader("X-Content-Type-Options"), "nosniff")
        self.assertEqual(r.getheader("X-Frame-Options"), "DENY")
        r, _ = self.req("GET", "/login", headers={"X-Forwarded-Proto": "https"})
        self.assertIn("max-age", r.getheader("Strict-Transport-Security"))

    def test_no_path_escape(self):
        ck = self.sign_in()
        for p in ("/../users.json", "/%2e%2e/users.json", "/../history/backtest.md"):
            self.assertEqual(self.req("GET", p, cookie=ck)[0].status, 404, p)


if __name__ == "__main__":
    unittest.main()
