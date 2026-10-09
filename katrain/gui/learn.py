"""Learn: q5Go's lessons and two sets of Go problems, inside the Serious Games Week KaTrain (sim-museum fork).

Main menu -> Learn: lessons and problems. A lesson opens as a game whose comments explain each step (use the arrow
keys or the move buttons). A problem opens at its start position with the solution hidden: place your answer on the
board and KataGo's evaluation shows how good it is; Show solution opens the original file with all its variations.
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

from katrain.core import learn
from katrain.core.constants import PLAYER_HUMAN, PLAYING_NORMAL, STATUS_INFO


class LearnMixin:
    learn_set = "easy"
    learn_index = 0  # 0-based within learn_set

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
        what = ("solution and variations" if with_solution else
                "%s. Place your answer; KataGo shows how good it is" % learn.side_to_move_text(tree))
        self._learn_load(tree, files[index], "%s, problem %d of %d: %s." % (name, index + 1, len(files), what))

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

        root.add_widget(lbl("[b]Problems[/b]  (the solution is hidden until you ask for it)",
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
            ("Show solution", lambda: self.learn_open_problem(*chosen(), with_solution=True)),
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
        shot = os.environ.get("KATRAIN_LEARN_SHOT")
        if shot:
            from kivy.core.window import Window

            Clock.schedule_once(lambda _dt: (print("[learn] screenshot", Window.screenshot(name=shot), flush=True),
                                             os._exit(0)), 5)
