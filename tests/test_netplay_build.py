"""Backlog 28: a KaTrain network host refuses a guest from a different build and says why (stdlib only)."""
import time
import unittest

from katrain.core.netplay import NetLink


def wait(cond, timeout=5.0):
    t = time.time()
    while time.time() - t < timeout:
        if cond():
            return True
        time.sleep(0.02)
    return False


class BuildTest(unittest.TestCase):
    def run_pair(self, host_build, guest_build):
        host_msgs, guest_msgs = [], []
        host, guest = NetLink("Ann", host_msgs.append), NetLink("Bob", guest_msgs.append)
        host.build, guest.build = host_build, guest_build
        host.host(0)
        guest.join("127.0.0.1", host.port)
        return host, guest, host_msgs, guest_msgs

    def test_different_build_is_refused_with_both_builds_named(self):
        host, guest, host_msgs, guest_msgs = self.run_pair("aaaa11112222", "bbbb33334444")
        self.assertTrue(wait(lambda: any(m.get("t") == "closed" for m in guest_msgs)))
        why = [m["why"] for m in guest_msgs if m.get("t") == "closed"][0]
        self.assertIn("aaaa11112222", why)
        self.assertIn("bbbb33334444", why)
        self.assertTrue(wait(lambda: any(m.get("t") == "closed" for m in host_msgs)))
        self.assertFalse(any(m.get("t") == "hello" for m in host_msgs))   # the game never saw the guest

    def test_same_build_joins(self):
        host, guest, host_msgs, guest_msgs = self.run_pair("aaaa11112222", "aaaa11112222")
        self.assertTrue(wait(lambda: any(m.get("t") == "hello" for m in host_msgs)))
        self.assertFalse(any(m.get("t") == "closed" for m in guest_msgs))


if __name__ == "__main__":
    unittest.main()
