"""GO-SHAPE-1 (PO 2026-10-22): name a move's shape as Sabaki does ("Hane", "Tiger's Mouth", "Atari", "4-4 Point" ...).

A line-for-line Python port of @sabaki/boardmatcher 1.3.0 (findPatternInMove / matchPattern / helper), MIT License,
Copyright (c) 2018-2020 Yichuan Shen; its shape library is shape_library.json beside this file. The same board, colour
and point give the same name as Sabaki (tests/test_shapes.py runs the library's own nameMove cases).

Board: data[y][x] with 1 = black, -1 = white, 0 = empty, the position BEFORE the move; sign: 1 or -1; vertex: (x, y).
"""
import json
import os

_LIBRARY = None


def library():
    global _LIBRARY
    if _LIBRARY is None:
        with open(os.path.join(os.path.dirname(__file__), "shape_library.json"), encoding="utf-8") as f:
            _LIBRARY = json.load(f)
    return _LIBRARY


def _has(v, w, h):
    return 0 <= v[0] < w and 0 <= v[1] < h


def _neighbors(v, w, h):
    x, y = v
    return [n for n in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)) if _has(n, w, h)]


def _pseudo_liberties(v, data, visited=None, result=None):
    """Up to 3 liberties of the chain at v (the library only needs 0, 1, 2 or 'more')."""
    visited = [] if visited is None else visited
    result = [] if result is None else result
    h, w = len(data), len(data[0]) if data else 0
    sign = data[v[1]][v[0]]
    visited.append(tuple(v))
    for n in _neighbors(v, w, h):
        if len(result) >= 3:
            break
        s = data[n[1]][n[0]]
        if s == -sign or n in visited:
            continue
        if s == 0 and n not in result:
            result.append(n)
            continue
        _pseudo_liberties(n, data, visited, result)
    return len(result)


def _symmetries(v):
    x, y = v
    return [(x, y), (-x, y), (x, -y), (-x, -y), (y, x), (-y, x), (y, -x), (-y, -x)]


def _board_symmetries(v, w, h):
    mx, my = w - 1, h - 1
    return [s for s in ((x % mx, y % my) for x, y in _symmetries(v)) if _has(s, w, h)]


def _unnamed_hoshis(w, h):
    if min(w, h) <= 7:
        return []
    near_x, near_y = (3 if w >= 13 else 2), (3 if h >= 13 else 2)
    far_x, far_y = w - near_x - 1, h - near_y - 1
    mid_x, mid_y = (w - 1) / 2, (h - 1) / 2
    out = []
    if w % 2:
        out += [(mid_x, near_y), (mid_x, far_y)]
    if h % 2:
        out += [(near_x, mid_y), (far_x, mid_y)]
    return out


def _match_pattern(data, anchor, pattern):
    """True if `pattern` matches with the stone at `anchor` as one of its anchors (any of the 8 symmetries)."""
    h, w = len(data), len(data[0]) if data else 0
    if not _has(anchor, w, h):
        return False
    if pattern.get("size") is not None and (w != h or w != int(pattern["size"])):
        return False
    x, y = anchor
    sign = data[y][x]
    if sign == 0:
        return False
    for (ax, ay), as_ in pattern.get("anchors") or []:
        if pattern.get("type") == "corner" and tuple(anchor) not in _board_symmetries((ax, ay), w, h):
            continue
        hyp = [True] * 8
        for (vx, vy), vs in pattern["vertices"]:
            symm = _symmetries((vx - ax, vy - ay))
            for k in range(8):
                if not hyp[k]:
                    continue
                wx, wy = x + symm[k][0], y + symm[k][1]
                if not _has((wx, wy), w, h) or data[wy][wx] != vs * sign * as_:
                    hyp[k] = False
            if not any(hyp):
                break
        if any(hyp):
            return True
    return False


def name_move(data, sign, vertex):
    """The shape name Sabaki shows for `sign` playing at `vertex` on `data` (before the move), or None."""
    h, w = len(data), len(data[0]) if data else 0
    if sign == 0 or vertex is None or not _has(vertex, w, h):
        return "Pass"
    x, y = vertex
    if data[y][x] != 0:
        return None
    vertex = (x, y)
    neighbors = _neighbors(vertex, w, h)
    for nx, ny in neighbors:
        if data[ny][nx] != -sign:
            continue
        libs = _pseudo_liberties((nx, ny), data)
        if libs == 1:
            return "Take"
        if libs == 2:
            return "Atari"
    nxt = [row[:] for row in data]
    nxt[y][x] = sign
    if _pseudo_liberties(vertex, nxt) == 0:
        return "Suicide"
    friendly = [n for n in neighbors if data[n[1]][n[0]] == sign]
    if len(friendly) == len(neighbors):
        return "Fill"
    if len(friendly) >= 2:
        return "Connect"
    for pattern in library():
        if _match_pattern(nxt, vertex, pattern):
            return pattern["name"]
    if (x, y) == ((w - 1) / 2, (h - 1) / 2):
        return "Tengen"
    if any((x, y) == hp for hp in _unnamed_hoshis(w, h)):
        return "Hoshi"
    return None
