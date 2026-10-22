"""GO-SHAPE-1: katrain.core.shapes names every move exactly as Sabaki's @sabaki/boardmatcher 1.3.0 does.

tests/data/boardmatcher_cases.json was written by the JavaScript library itself: its three test boards, and for every
point and both colours the name nameMove() returned (2166 cases, null included).
"""
import json
import os
import unittest

from katrain.core.shapes import name_move

with open(os.path.join(os.path.dirname(__file__), "data", "boardmatcher_cases.json"), encoding="utf-8") as f:
    FIX = json.load(f)


class ShapeTest(unittest.TestCase):
    def test_every_case_matches_sabaki(self):
        bad = [(b, s, v, want, name_move(FIX["boards"][b], s, tuple(v))) for b, s, v, want in FIX["cases"]
               if name_move(FIX["boards"][b], s, tuple(v)) != want]
        self.assertEqual(bad[:5], [], "%d of %d differ" % (len(bad), len(FIX["cases"])))

    def test_some_named_shapes_occur(self):   # the fixture is not all None / Pass
        names = {c[3] for c in FIX["cases"]}
        for n in ("Atari", "Take", "Connect", "Hane", "4-4 Point", "Tengen"):
            self.assertIn(n, names)

    def test_library_cases(self):   # boardmatcher's own nameMove.test.js
        u, e = FIX["boards"]["unfinished"], FIX["boards"]["empty"]
        self.assertEqual(name_move(u, 1, (-1, -1)), "Pass")
        self.assertEqual(name_move(u, 1, (0, 0)), "Suicide")
        self.assertEqual(name_move(u, -1, (0, 0)), "Take")
        self.assertEqual(name_move(u, -1, (17, 15)), "Atari")
        self.assertEqual(name_move(u, -1, (0, 4)), "Fill")
        self.assertEqual(name_move(u, -1, (1, 2)), "Connect")
        self.assertEqual(name_move(u, 1, (7, 1)), "Stretch")
        self.assertEqual(name_move(u, 1, (10, 16)), "Cut")
        self.assertEqual(name_move(e, -1, (9, 9)), "Tengen")
        self.assertEqual(name_move(e, 1, (15, 15)), "4-4 Point")


if __name__ == "__main__":
    unittest.main()


class NodeShapeTest(unittest.TestCase):
    """The names reach KaTrain's move info, computed from the game tree (captures included)."""

    def test_names_along_a_game(self):
        from katrain.core.game import KaTrainSGF
        from katrain.core.shapes import node_shape_name

        root = KaTrainSGF.parse_sgf("(;GM[1]SZ[19];B[pd];W[dp];B[pq];W[dd];B[qo];W[qp];B[pp];W[rq];B[qq];W[rr];B[rp];W[qr])")
        names, n = [], root
        while n.children:
            n = n.children[0]
            names.append(node_shape_name(n))
        self.assertEqual(names, ["4-4 Point", "4-4 Point", "3-4 Point", "Nirensei Opening", "Low Enclosure", "Attachment",
                                 "Stretch", "Diagonal", "Atari", "Stretch", "Take", "Turn"])
        self.assertTrue(n.parent.comment(interactive=False).startswith("Take\n"))   # on screen, even before analysis
        self.assertNotIn("Take", n.parent.comment(sgf=True, interactive=False))   # saved SGF comments unchanged
