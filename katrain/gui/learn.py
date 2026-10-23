"""Learn: q5Go's lessons and two sets of Go problems, inside the Serious Games Week KaTrain (sim-museum fork).

Main menu -> Learn: lessons and problems. A lesson opens as a game whose comments explain each step (use the arrow
keys or the move buttons). A problem opens at its start position with the solution hidden: place your answer on the
board and KataGo's evaluation shows how good it is; Book solution opens the original file with all its variations.
GO-PROBLEM-1 (PO 10-22): a problem is a local fight, not a whole-board position, so it opens inside KaTrain's tsumego
frame (the rest of the board walled off) and every query avoids moves outside the problem's region (root.problem_region,
see engine.py). KaTrain makes its own solution -- a deep reading of the start position -- because the supplied ones
are often not the best line; the player is taught (teaching mode undoes a bad move), KaTrain answers as the opponent,
hints show its candidates, and KaTrain's solution adds its line as a variation.
Test hooks: KATRAIN_LEARN_OPEN=lesson:<n> | problem:<set>:<n> (1-based) and KATRAIN_LEARN_SHOT=<file.png>.
"""
import os

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from pysgf import Move

from katrain.core import learn
from katrain.core.constants import (AI_DEFAULT, MODE_PLAY, PLAYER_AI, PLAYER_HUMAN, PLAYING_NORMAL,
                                    PLAYING_TEACHING, STATUS_INFO)
from katrain.core.tsumego_frame import tsumego_frame_from_katrain_game

FRAME_MARGIN = 4  # the Tsumego frame popup's default wall distance
SOLUTION_VISITS = 4  # x the engine's max visits for the start position: KaTrain's own solution
SOLUTION_MOVES = 12
SOLVED_POINTS = 1.5  # the solver's moves may lose this much in all against KaTrain's reading and still count as solved


def solution_line(start):
    """KaTrain's solution from the start position's analysis: the best move's line, up to a pass or the first move
    outside the problem's region (the region binds each position's first move only, so a line can wander into the
    frame's walls once the fight is settled)."""
    cands = start.candidate_moves
    if not cands:
        return []
    xmin, xmax, ymin, ymax = getattr(start.root, "problem_region", None) or (0, 99, 0, 99)
    line = []
    for gtp in cands[0]["pv"][:SOLUTION_MOVES]:
        c = Move.from_gtp(gtp).coords
        if c is None or not (xmin <= c[0] <= xmax and ymin <= c[1] <= ymax):
            break
        line.append(gtp)
    return line


class LearnMixin:
    learn_set = "easy"
    learn_index = 0  # 0-based within learn_set
    learn_start = None  # the framed start node of the open problem

    def _learn_load(self, tree, path, status):
        self._do_new_game(move_tree=tree, sgf_filename=path)  # a file name makes both players human, as on any load
        self.game.sgf_filename = None  # ...but a Save must never write into the bundled file
        for bw in "BW":
            self.update_player(bw, player_type=PLAYER_HUMAN, player_subtype=PLAYING_NORMAL)
        self.controls.set_status(status, STATUS_INFO)

    def learn_open_lesson(self, index):
        title, _name = learn.LESSONS[index]
        path = learn.lesson_path(index)
        self._learn_load(learn.problem_tree(path, with_solution=True), path,
                         "Lesson %d of %d: %s. Step through it with the arrow keys." % (index + 1, len(learn.LESSONS), title))

    def learn_open_problem(self, set_id=None, index=None, with_solution=False):
        set_id = set_id or self.learn_set
        files = learn.problem_files(set_id)
        if not files:
            return
        index = max(0, min(len(files) - 1, self.learn_index if index is None else index))
        self.learn_set, self.learn_index = set_id, index
        name = dict(learn.PROBLEM_SETS)[set_id]
        tree = learn.problem_tree(files[index], with_solution=with_solution)
        what = ("the book solution and variations" if with_solution else
                "%s. Play your answer: KaTrain replies, and takes back a bad move. Hints show its candidates; "
                "Learn -> KaTrain's solution shows its line" % learn.side_to_move_text(tree))
        self._learn_load(tree, files[index], "%s, problem %d of %d: %s." % (name, index + 1, len(files), what))
        self.learn_start = None
        if not with_solution:
            self._learn_frame_problem()

    def _learn_frame_problem(self):
        root = self.game.root
        to_play = root.initial_player
        node, region = tsumego_frame_from_katrain_game(self.game, self.game.komi, to_play == "B", ko_p=False,
                                                       margin=FRAME_MARGIN)
        if region:
            (x1, x2), (y1, y2) = region
            root.problem_region = [min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)]
        self.game.set_current_node(node)
        self.learn_start = node
        self.update_player(to_play, player_type=PLAYER_HUMAN, player_subtype=PLAYING_TEACHING)
        self.update_player("W" if to_play == "B" else "B", player_type=PLAYER_AI, player_subtype=AI_DEFAULT)
        # play mode, so KaTrain answers: after the load's own (scheduled) switch to analysis mode
        Clock.schedule_once(lambda _dt: self.play_mode.play.trigger_action(duration=0))
        engine = self.game.engines[to_play]
        node.analyze(engine, visits=SOLUTION_VISITS * engine.config["max_visits"], time_limit=False)
        self.update_state(redraw_board=True)

    def learn_after_ai_move(self):
        """KaTrain passing in a problem means the local fight is settled: say how the solver did."""
        start, cn = self.learn_start, self.game.current_node
        if start is None or start.root is not self.game.root or not cn.is_pass:
            return
        solver, lost, node = start.next_player, 0.0, cn
        while node is not None and node is not start:
            if node.player == solver and node.points_lost is not None:
                lost += max(0.0, node.points_lost)
            node = node.parent
        if node is None:
            return  # not a line from the problem's start
        if lost <= SOLVED_POINTS:
            msg = "Solved. KaTrain passes: the fight is settled, and your moves match its reading."
        else:
            msg = ("KaTrain passes: the fight is settled, but your moves lost %.1f points against its solution "
                   "(Learn -> KaTrain's solution)." % lost)
        self.controls.set_status(msg, STATUS_INFO, check_level=False)

    def learn_show_solution(self):
        """KaTrain's own solution of the open problem, added as a variation from the start position."""
        start = self.learn_start
        if start is None or start.root is not self.game.root:
            self.controls.set_status("Open a problem first (Learn: lessons and problems).", STATUS_INFO,
                                     check_level=False)
            return
        line = solution_line(start) if start.analysis_complete else []
        if not line:
            self.controls.set_status("KaTrain is still reading this problem; ask again in a moment.", STATUS_INFO,
                                     check_level=False)
            return
        if self.play_analyze_mode == MODE_PLAY:  # analysis mode, so KaTrain does not answer the moves it shows
            self.play_mode.analyze.trigger_action(duration=0)
        self.game.set_current_node(start)
        player = start.next_player
        for gtp in line:
            self.game.play(Move.from_gtp(gtp, player=player))
            player = "W" if player == "B" else "B"
        first = next(c for c in start.children if c.move and c.move.gtp() == line[0])
        self.game.set_current_node(first)
        text = "  ".join("%s %s" % ("BW"[(i + (start.next_player == "W")) % 2], m) for i, m in enumerate(line))
        self.controls.set_status("KaTrain's solution: %s. Step through it with the arrow keys." % text, STATUS_INFO,
                                 check_level=False)
        self.update_state(redraw_board=True)

    def _do_learn_popup(self):
        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))

        def lbl(text, **kw):
            return Label(text=text, halign="left", valign="middle", markup=True, **kw)

        root.add_widget(lbl("[b]Lessons[/b]  (q5Go's tutorial: each step is explained in the comments)",
                            size_hint_y=None, height=dp(28), text_size=(dp(600), None)))
        grid = GridLayout(cols=2, spacing=dp(4), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        popup = Popup(title="Learn: lessons and problems", content=root, size_hint=(None, None), size=(dp(640), dp(560)))
        for i, (title, _name) in enumerate(learn.LESSONS):
            b = Button(text="%d. %s" % (i + 1, title), size_hint_y=None, height=dp(34))
            b.bind(on_release=lambda _b, i=i: (popup.dismiss(), self.learn_open_lesson(i)))
            grid.add_widget(b)
        root.add_widget(grid)

        root.add_widget(lbl("[b]Problems[/b]  (KaTrain reads each one as a local fight; its solution and the book's "
                            "are hidden until you ask)",
                            size_hint_y=None, height=dp(28), text_size=(dp(600), None)))
        names = [n for _s, n in learn.PROBLEM_SETS]
        ids = [s for s, _n in learn.PROBLEM_SETS]
        spinner = Spinner(text=dict(learn.PROBLEM_SETS)[self.learn_set], values=names, size_hint_x=0.5)
        number = TextInput(text=str(self.learn_index + 1), multiline=False, input_filter="int", size_hint_x=0.15)
        count = lbl("of %d" % len(learn.problem_files(self.learn_set)), size_hint_x=0.15)
        row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
        for w in (spinner, number, count):
            row.add_widget(w)
        root.add_widget(row)

        def chosen():
            set_id = ids[names.index(spinner.text)]
            try:
                n = int(number.text or "1") - 1
            except ValueError:
                n = 0
            return set_id, n

        def on_set(_s, text):
            set_id = ids[names.index(text)]
            count.text = "of %d" % len(learn.problem_files(set_id))
            number.text = "1"

        spinner.bind(text=on_set)
        buttons = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
        for text, action in (
            ("Open", lambda: self.learn_open_problem(*chosen())),
            ("Previous", lambda: self.learn_open_problem(chosen()[0], chosen()[1] - 1)),
            ("Next", lambda: self.learn_open_problem(chosen()[0], chosen()[1] + 1)),
            ("KaTrain's solution", lambda: self.learn_show_solution()),
            ("Book solution", lambda: self.learn_open_problem(*chosen(), with_solution=True)),
        ):
            b = Button(text=text)
            b.bind(on_release=lambda _b, a=action: (popup.dismiss(), a()))
            buttons.add_widget(b)
        root.add_widget(buttons)
        root.add_widget(lbl("Problems: Go Game Guru's Weekly Go Problems (CC BY-NC-SA 4.0) and the Xuanxuan Qijing "
                            "(1349) from MyGoGrinder. Lessons: q5Go by Bernd Schmidt (GPL-2). Details: learn/SOURCES.md.",
                            font_size="11sp", size_hint_y=None, height=dp(40), text_size=(dp(600), None)))
        close = Button(text="Close", size_hint_y=None, height=dp(36))
        close.bind(on_release=lambda _b: popup.dismiss())
        root.add_widget(close)
        popup.open()

    def learn_env_start(self, _dt=None):
        """KATRAIN_LEARN_OPEN=lesson:<n> | problem:<set>:<n> | popup, then KATRAIN_LEARN_SHOT=<png> and exit."""
        what = os.environ.get("KATRAIN_LEARN_OPEN")
        if not what:
            return
        parts = what.split(":")
        if parts[0] == "lesson":
            self.learn_open_lesson(int(parts[1]) - 1)
        elif parts[0] == "problem":
            self.learn_open_problem(parts[1], int(parts[2]) - 1, with_solution=len(parts) > 3 and parts[3] == "solution")
        elif parts[0] == "popup":
            self("learn-popup")
        print("[learn] opened %s: next player %s, %d move(s) in the tree, status: %s" % (
            what, self.game.root.initial_player, len(list(self.game.root.nodes_in_tree)) - 1,
            getattr(self.controls.status, "text", "?")), flush=True)
        if self.learn_start is not None and (os.environ.get("KATRAIN_LEARN_PLAY") or os.environ.get("KATRAIN_LEARN_SOLVE")):
            self._learn_env_problem()
            return
        shot = os.environ.get("KATRAIN_LEARN_SHOT")
        if shot:
            from kivy.core.window import Window

            Clock.schedule_once(lambda _dt: (print("[learn] screenshot", Window.screenshot(name=shot), flush=True),
                                             os._exit(0)), 5)

    def _learn_env_problem(self):
        """KATRAIN_LEARN_PLAY=<gtp> plays the solver's move and prints KaTrain's reply; KATRAIN_LEARN_SOLVE=1 then shows
        KaTrain's solution; KATRAIN_LEARN_SHOT=<png> screenshots the end; exits. Prints [learn] lines."""
        from kivy.core.window import Window

        start, region = self.learn_start, self.game.root.problem_region
        state = {"played": None, "solved": False, "t": 0.0}
        play = os.environ.get("KATRAIN_LEARN_PLAY")

        def inside(gtp):
            c = Move.from_gtp(gtp).coords
            return c is not None and region[0] <= c[0] <= region[1] and region[2] <= c[1] <= region[3]

        def finish(_dt=None):
            shot = os.environ.get("KATRAIN_LEARN_SHOT")
            if shot:
                print("[learn] screenshot", Window.screenshot(name=shot), flush=True)
            os._exit(0)

        def tick(dt):
            state["t"] += dt
            cn = self.game.current_node
            if state["t"] > 240:
                print("[learn] timeout at %s: complete=%s auto_undo=%s children=%d mode=%s players=%s popup=%s drawer=%s "
                      "end=%s" % (cn.move, cn.analysis_complete, cn.auto_undo, len(cn.children), self.play_analyze_mode,
                                  {bw: (p.player_type, p.player_subtype) for bw, p in self.players_info.items()},
                                  self.popup_open, self.nav_drawer.state, self.game.end_result), flush=True)
                os._exit(2)
            if play and state["played"] is None and start.analysis_complete:
                cands = start.candidate_moves
                print("[learn] start read: region=%s top=%s lead=%.1f visits=%d" % (
                    region, cands[0]["move"], start.analysis["root"]["scoreLead"], start.analysis["root"]["visits"]),
                    flush=True)
                state["played"] = self.game.current_node
                self("play", Move.from_gtp(play).coords)
                return
            if play and state["played"] is not None and not state["solved"]:
                mine = next((c for c in start.children if c.move and c.move.gtp() == play), None)
                if mine is not None and mine.children:
                    reply = mine.children[0].move.gtp()
                    print("[learn] you %s (lost %.1f) -> KaTrain replies %s (%s); status: %s" % (
                        play, mine.points_lost or 0.0, reply,
                        "pass" if reply == "pass" else "inside the region" if inside(reply) else "OUTSIDE",
                        getattr(self.controls.status, "text", "?")), flush=True)
                    state["solved"] = True
                elif self.game.current_node is start and start.children and start.children[0].auto_undo:
                    print("[learn] you %s -> teaching undo: %s" % (play, getattr(self.controls.status, "text", "?")),
                          flush=True)
                    state["solved"] = True
                return
            if os.environ.get("KATRAIN_LEARN_SOLVE") and start.analysis_complete:
                self.learn_show_solution()
                print("[learn] %s (all inside: %s)" % (getattr(self.controls.status, "text", "?"),
                                                      all(inside(m) for m in solution_line(start))), flush=True)
                Clock.schedule_once(finish, 3)
                return False
            if not os.environ.get("KATRAIN_LEARN_SOLVE") and (state["solved"] or not play):
                Clock.schedule_once(finish, 2)
                return False

        Clock.schedule_interval(tick, 0.5)

