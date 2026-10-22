"""Backlog 55: an optional KaTrain network-game password -- a blank host password is an open game (stdlib only)."""
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


class PasswordTest(unittest.TestCase):
    def pair(self, host_pw, guest_pw):
        host_msgs, guest_msgs = [], []
        host = NetLink("Ann", host_msgs.append, password=host_pw)
        guest = NetLink("Bob", guest_msgs.append, password=guest_pw)
        host.host(0)
        guest.join("127.0.0.1", host.port)
        self.addCleanup(host.close)
        self.addCleanup(guest.close)
        return host_msgs, guest_msgs

    def joins(self, host_pw, guest_pw):
        host_msgs, guest_msgs = self.pair(host_pw, guest_pw)
        self.assertTrue(wait(lambda: any(m.get("t") == "hello" for m in host_msgs)))
        time.sleep(0.1)
        self.assertFalse(any(m.get("t") == "closed" for m in guest_msgs))

    def refused(self, host_pw, guest_pw, text):
        host_msgs, guest_msgs = self.pair(host_pw, guest_pw)
        self.assertTrue(wait(lambda: any(m.get("t") == "closed" for m in guest_msgs)))
        self.assertEqual([m["why"] for m in guest_msgs if m.get("t") == "closed"][0], text)
        self.assertFalse(any(m.get("t") == "hello" for m in host_msgs))   # the game never saw the guest

    def test_open_game_takes_anyone(self):
        self.joins("", "x")

    def test_open_game_blank_guest(self):
        self.joins("", "")

    def test_matching_password_joins(self):
        self.joins("abc", "abc")

    def test_wrong_password_is_refused(self):
        self.refused("abc", "x", "Wrong password for this game.")

    def test_missing_password_is_refused(self):
        self.refused("abc", "", "This game needs a password.")

    def test_password_never_sent_as_text(self):
        link = NetLink("Bob", lambda m: None, password="abc")
        self.assertNotIn("abc", link.pw)
        self.assertEqual(len(link.pw), 64)


if __name__ == "__main__":
    unittest.main()
