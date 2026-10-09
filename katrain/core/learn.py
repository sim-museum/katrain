"""Lessons and Go problems bundled with the Serious Games Week KaTrain (katrain/learn, see SOURCES.md).

Lessons are q5Go's ten tutorial SGFs: they open as ordinary games, and their comments explain each step.
Problems open at their start position with the solution removed, so the player answers on an empty tree and
KataGo judges the move; problem_tree(..., with_solution=True) gives the original file back.
"""
import os
from typing import List, Tuple

from katrain.core.game import KaTrainSGF

LEARN_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "learn")

# q5Go's own order and titles (q5Go src/tutorial.cpp)
LESSONS: List[Tuple[str, str]] = [
    ("The rules of Go", "rules.sgf"),
    ("Life and death", "lnd.sgf"),
    ("Basic tactics", "tactics.sgf"),
    ("Connections", "connections.sgf"),
    ("Captures", "captures.sgf"),
    ("Openings", "openings.sgf"),
    ("Endgame basics", "endgame.sgf"),
    ("Advanced life and death", "lnd2.sgf"),
    ("One more rule", "bentfour.sgf"),
    ("Terminology", "terminology.sgf"),
]

PROBLEM_SETS: List[Tuple[str, str]] = [
    ("easy", "Go Game Guru: easy"),
    ("intermediate", "Go Game Guru: intermediate"),
    ("hard", "Go Game Guru: hard"),
    ("xuanxuan", "Xuanxuan Qijing (1349)"),
]


def lesson_path(index: int) -> str:
    return os.path.join(LEARN_DIR, "lessons", LESSONS[index][1])


def _number(name: str) -> Tuple[int, str]:
    digits = "".join(c for c in name if c.isdigit())
    return (int(digits) if digits else 0, name)


def problem_files(set_id: str) -> List[str]:
    """The set's SGF files in problem order (ggg-easy-2 before ggg-easy-10)."""
    d = os.path.join(LEARN_DIR, "problems", set_id)
    if not os.path.isdir(d):
        return []
    return [os.path.join(d, f) for f in sorted((f for f in os.listdir(d) if f.lower().endswith(".sgf")), key=_number)]


def problem_tree(path: str, with_solution: bool = False):
    """Parse a problem. Without the solution, the root keeps its stones and comment, gains PL (the side to move,
    read BEFORE the moves are removed -- otherwise a 'White to play' problem would start with Black), and loses
    its children."""
    root = KaTrainSGF.parse_file(path)
    if not with_solution:
        to_move = root.initial_player
        root.set_property("PL", to_move)
        root.children = []
    return root


def side_to_move_text(root) -> str:
    return "Black to play" if root.initial_player == "B" else "White to play"
