"""GO-PROBLEM-1 (PO 10-22): go problems (tsumego) in KaTrain.

A problem file gives a position and, usually, a solution tree. KaTrain keeps only the position: the setup stones, the
side to move and the problem's instruction ("Black to play."). The supplied solution is dropped because it is often
not the best line; KaTrain's own analysis of the framed position is the solution, which is also what its hints and
teaching mode work from. The supplied first moves are kept only as `book_moves`, for checking KaTrain's answer.

No Kivy here: the GUI side is KaTrainGui._do_go_problem, which frames the position (tsumego_frame.py) so the engine
reads the local fight rather than looking for big points elsewhere on the board.
"""
import os
import re
from typing import Dict, List, Optional

from pysgf import GoGame, Move

SKIP_DIRS = {"templates", ".git"}
TO_PLAY_RE = re.compile(r"\b(black|white)\s+to\s+(play|move|live|kill|win|capture|connect|escape)", re.IGNORECASE)
CORRECT_RE = re.compile(r"\b(correct|right)\b", re.IGNORECASE)
WRONG_RE = re.compile(r"\b(wrong|incorrect|failure|fail)\b", re.IGNORECASE)


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def default_problem_root() -> str:
    """$KATRAIN_PROBLEMS (run_katrain.sh sets it), else ~/.katrain/problems."""
    return os.environ.get("KATRAIN_PROBLEMS") or os.path.join(os.path.expanduser("~"), ".katrain", "problems")


def list_collections(root: str) -> Dict[str, List[str]]:
    """{collection name: [sgf paths in natural order]}; a collection is a folder holding SGF files, named by its path
    below the root ("gogameguru/weekly-go-problems/easy")."""
    out = {}
    if not os.path.isdir(root):
        return out
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted((d for d in dirs if d not in SKIP_DIRS), key=natural_key)
        sgfs = sorted((f for f in files if f.lower().endswith(".sgf")), key=natural_key)
        if sgfs:
            name = os.path.relpath(folder, root).replace(os.sep, "/")
            out[name] = [os.path.join(folder, f) for f in sgfs]
    return out


def _leads_to(node, regex) -> bool:
    if regex.search(node.get_property("C", "") or ""):
        return True
    return any(_leads_to(c, regex) for c in node.children)


class GoProblem:
    def __init__(self, path: str):
        self.path = path
        root = GoGame.parse_file(path)
        self.size = root.board_size
        stones = {}  # sgf coord -> "B"/"W", setup nodes up to the first move
        node, comments = root, []
        while True:
            for prop, player in (("AB", "B"), ("AW", "W")):
                for c in node.get_list_property(prop, []):
                    stones[c] = player
            for c in node.get_list_property("AE", []):
                stones.pop(c, None)
            if node.get_property("C"):
                comments.append(node.get_property("C"))
            if node.move or len(node.children) != 1 or node.children[0].move:
                break
            node = node.children[0]
        self.stones = stones
        first = [c for c in node.children if c.move and not c.move.is_pass]
        self.comment = "\n".join(comments).strip()
        self.to_play = self._to_play(node, first)
        # supplied answers, for checks only: first moves whose subtree is marked correct (Go Game Guru), else the first
        # move of the main line (Xuan Xuan Qi Jing gives one line); never a move marked wrong
        marked = [c for c in first if _leads_to(c, CORRECT_RE)]
        if not marked and first and not _leads_to(first[0], WRONG_RE):
            marked = first[:1]
        self.book_moves = [c.move.sgf(self.size) for c in marked if c.move.player == self.to_play]

    def _to_play(self, node, first) -> str:
        pl = node.get_property("PL") or node.root.get_property("PL")
        if pl and pl.upper()[0] in "BW":
            return pl.upper()[0]
        m = TO_PLAY_RE.search(self.comment)
        if m:
            return "B" if m.group(1).lower() == "black" else "W"
        if first:
            return first[0].move.player
        return "B"

    @property
    def title(self) -> str:
        return os.path.splitext(os.path.basename(self.path))[0]

    @property
    def instruction(self) -> str:
        """The problem's own first line ("Black to play."), else "<Colour> to play." """
        line = self.comment.splitlines()[0].strip() if self.comment else ""
        if line and not line.lower().startswith("http"):
            return line
        return ("Black" if self.to_play == "B" else "White") + " to play."

    def sgf(self) -> str:
        """The position only, as an SGF KaTrain loads as a new game: no supplied solution."""
        sx, sy = self.size
        sz = str(sx) if sx == sy else f"{sx}:{sy}"
        ab = "".join(f"[{c}]" for c, p in sorted(self.stones.items()) if p == "B")
        aw = "".join(f"[{c}]" for c, p in sorted(self.stones.items()) if p == "W")
        text = (self.instruction + "\n" + self.title).replace("\\", "\\\\").replace("]", "\\]")
        return (
            f"(;GM[1]FF[4]CA[UTF-8]SZ[{sz}]KM[0]RU[Japanese]PL[{self.to_play}]GN[{self.title}]C[{text}]"
            + (f"AB{ab}" if ab else "")
            + (f"AW{aw}" if aw else "")
            + ")"
        )

    def move_from_sgf(self, coord: str) -> Move:
        return Move.from_sgf(coord, self.size, player=self.to_play)
