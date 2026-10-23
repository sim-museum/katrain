"""GO-PROBLEM-1: the problem reader keeps the position and the side to move, and drops the supplied solution."""
import os
import tempfile
import unittest

from pysgf import GoGame

from katrain.core.problems import GoProblem, list_collections

GGG = """(;GM[1]FF[4]SZ[19]C[Black to play.

https://gogameguru.com/]AW[pq][qq]AB[op][pp]
(;B[rs];W[rr](;B[ns]C[Correct])(;B[ps]C[Also correct.]))
(;B[rq];W[rr];B[ns];W[rs])
(;B[ns]C[Wrong];W[rs]))"""
XXQJ = "(;GM[1]FF[3]SZ[19]AB[qq][rq]AW[pm][qm]PL[W];W[sr];B[on];W[rs])"
NO_HINT = "(;GM[1]FF[4]SZ[9]AB[cc];W[dd];B[ee])"
WHITE_COMMENT = "(;GM[1]FF[4]SZ[19]C[White to live.]AB[aa]AW[bb];W[cc])"
SETUP_TWO_NODES = "(;GM[1]FF[4]SZ[19]AB[aa][ab];AW[ba]AE[ab];B[ca])"


class TestProblems(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.dir.cleanup()

    def write(self, rel, text):
        path = os.path.join(self.dir.name, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        return path

    def test_ggg(self):
        p = GoProblem(self.write("ggg.sgf", GGG))
        self.assertEqual(p.to_play, "B")
        self.assertEqual(p.instruction, "Black to play.")
        self.assertEqual(p.stones, {"pq": "W", "qq": "W", "op": "B", "pp": "B"})
        self.assertEqual(p.book_moves, ["rs"])  # only the first move whose line is marked correct

    def test_xxqj_pl(self):
        p = GoProblem(self.write("x.sgf", XXQJ))
        self.assertEqual(p.to_play, "W")
        self.assertEqual(p.book_moves, ["sr"])
        self.assertEqual(p.instruction, "White to play.")

    def test_to_play_from_comment_and_first_move(self):
        self.assertEqual(GoProblem(self.write("w.sgf", WHITE_COMMENT)).to_play, "W")
        p = GoProblem(self.write("n.sgf", NO_HINT))
        self.assertEqual((p.to_play, p.size), ("W", (9, 9)))

    def test_setup_over_several_nodes(self):
        p = GoProblem(self.write("s.sgf", SETUP_TWO_NODES))
        self.assertEqual(p.stones, {"aa": "B", "ba": "W"})
        self.assertEqual(p.to_play, "B")

    def test_sgf_has_position_but_no_solution(self):
        p = GoProblem(self.write("ggg.sgf", GGG))
        root = GoGame.parse_sgf(p.sgf())
        self.assertEqual(root.children, [])
        self.assertEqual(root.get_property("PL"), "B")
        self.assertEqual(sorted(root.get_list_property("AB")), ["op", "pp"])
        self.assertEqual(sorted(root.get_list_property("AW")), ["pq", "qq"])
        self.assertIn("Black to play.", root.get_property("C"))

    def test_collections(self):
        self.write("ggg/easy/p10.sgf", NO_HINT)
        self.write("ggg/easy/p9.sgf", NO_HINT)
        self.write("ggg/templates/t.sgf", NO_HINT)
        self.write("xx/a.sgf", XXQJ)
        cols = list_collections(self.dir.name)
        self.assertEqual(sorted(cols), ["ggg/easy", "xx"])
        self.assertEqual([os.path.basename(f) for f in cols["ggg/easy"]], ["p9.sgf", "p10.sgf"])
        self.assertEqual(list_collections(os.path.join(self.dir.name, "missing")), {})


if __name__ == "__main__":
    unittest.main()
