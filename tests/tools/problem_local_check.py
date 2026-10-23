"""GO-PROBLEM-1 engine check (needs KataGo; not a unit test).

For each problem: KataGo's top move on the bare position, as Learn opened problems before (whole-board analysis), and
on the framed position alone, and framed with moves outside the region avoided (KaTrain's Tsumego frame). Reports whether the top move
is inside the problem area and whether it is a supplied correct first move.
usage: problem_local_check.py katago model cfg set:first-last [set:first-last ...] [--visits N]
"""
import json
import subprocess
import sys

from pysgf import Move

from katrain.core import learn
from katrain.core.tsumego_frame import tsumego_frame

MARGIN = 4  # the tsumego frame popup's default wall distance


def book_moves(path, size):
    """First moves the file marks correct (Go Game Guru), else the main line's first move (Xuanxuan Qijing)."""
    root = learn.problem_tree(path, with_solution=True)
    marked = []

    def leads(n):
        return "correct" in (n.get_property("C", "") or "").lower() or any(leads(c) for c in n.children)

    first = [c for c in root.children if c.move]
    marked = [c for c in first if leads(c)] or first[:1]
    return {c.move.gtp() for c in marked}


def main():
    katago, model, cfg = sys.argv[1:4]
    visits = int(sys.argv[sys.argv.index("--visits") + 1]) if "--visits" in sys.argv else 500
    specs = [a for a in sys.argv[4:] if ":" in a]
    proc = subprocess.Popen([katago, "analysis", "-model", model, "-config", cfg], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    totals = {"bare_local": 0, "bare_book": 0, "frameonly_local": 0, "frameonly_book": 0, "framed_local": 0,
              "framed_book": 0, "n": 0}
    for spec in specs:
        set_id, rng = spec.split(":")
        lo, hi = (int(x) for x in rng.split("-"))
        for idx in range(lo, hi + 1):
            path = learn.problem_files(set_id)[idx - 1]
            root = learn.problem_tree(path)
            sx, sy = root.board_size
            player = root.initial_player
            stones = [(m.player, m.coords) for m in root.placements]
            board = [["-"] * sx for _ in range(sy)]
            for p, (x, y) in stones:
                board[y][x] = p
            xs, ys = [c[0] for _p, c in stones], [c[1] for _p, c in stones]
            area = (min(xs) - 2, max(xs) + 2, min(ys) - 2, max(ys) + 2)
            blacks, whites, region = tsumego_frame(board, 0, player == "B", False, MARGIN)
            framed = stones + [("B", (j, i)) for i, j in blacks] + [("W", (j, i)) for i, j in whites]
            (imin, imax), (jmin, jmax) = region
            avoid = [Move((x, y)).gtp() for x in range(sx) for y in range(sy)
                     if not (jmin <= x <= jmax and imin <= y <= imax)]
            res = {}
            for tag, st, extra in (("bare", stones, {}), ("frameonly", framed, {}),
                                   ("framed", framed, {"avoidMoves": [{"player": player, "moves": avoid,
                                                                       "untilDepth": 1}]})):
                q = {"id": tag, "initialStones": [[p, Move(c).gtp()] for p, c in st], "moves": [],
                     "initialPlayer": player, "rules": "japanese", "komi": 0, "boardXSize": sx, "boardYSize": sy,
                     "maxVisits": visits, **extra}
                proc.stdin.write(json.dumps(q) + "\n")
                proc.stdin.flush()
                ans = json.loads(proc.stdout.readline())
                top = min(ans["moveInfos"], key=lambda m: m["order"])
                res[tag] = (top["move"], " ".join(top["pv"][:6]), top["scoreLead"])
            book = book_moves(path, root.board_size)
            line = [f"{set_id}:{idx} {player} book={','.join(sorted(book))}"]
            totals["n"] += 1
            for tag in ("bare", "frameonly", "framed"):
                mv, pv, sc = res[tag]
                c = Move.from_gtp(mv).coords
                local = c is not None and area[0] <= c[0] <= area[1] and area[2] <= c[1] <= area[3]
                totals[tag + "_local"] += local
                totals[tag + "_book"] += mv in book
                line.append(f"{tag}: {mv} {'local' if local else 'ELSEWHERE'}{' =book' if mv in book else ''} "
                            f"lead {sc:+.1f} pv {pv}")
            print("  ".join(line), flush=True)
    proc.stdin.close()
    proc.wait(timeout=30)
    n = totals["n"]
    print(f"[problems] n={n} bare: local {totals['bare_local']} book {totals['bare_book']}  "
          f"frame only: local {totals['frameonly_local']} book {totals['frameonly_book']}  "
          f"framed + region: local {totals['framed_local']} book {totals['framed_book']}")


if __name__ == "__main__":
    main()
