import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import publish_gate as G  # noqa: E402

H = 3.6e6
NOW = 100 * H
GOOD = {"level": "ok", "core_ok": True, "at": NOW - 3 * H}
WARN = {"level": "warn", "core_ok": True, "at": NOW}
NO_PLAN = {"level": "ok", "core_ok": False, "missing": ["gameplan"], "at": NOW}
RED = {"level": "bad", "core_ok": True, "items": ["Line data missing."], "at": NOW}


class PublishGate(unittest.TestCase):
    def test_healthy_build_always_publishes(self):
        self.assertTrue(G.decide(GOOD, None, NOW)[0])
        self.assertTrue(G.decide(WARN, GOOD, NOW)[0])          # a yellow badge is not a broken build

    def test_degraded_build_held_when_live_is_good_and_recent(self):
        self.assertFalse(G.decide(NO_PLAN, GOOD, NOW)[0])
        self.assertFalse(G.decide(RED, GOOD, NOW)[0])

    def test_degraded_build_published_when_live_is_old_or_bad_or_unknown(self):
        old = dict(GOOD, at=NOW - 20 * H)
        self.assertTrue(G.decide(NO_PLAN, old, NOW)[0])
        self.assertTrue(G.decide(NO_PLAN, RED, NOW)[0])
        self.assertTrue(G.decide(NO_PLAN, None, NOW)[0])

    def test_alert_names_what_failed(self):
        self.assertIn("the move plan", G.what_failed(NO_PLAN))
        self.assertIn("Line data missing", G.what_failed(RED))


if __name__ == "__main__":
    unittest.main()
