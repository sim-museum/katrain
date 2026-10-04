"""Two-player network Go, found through squeak (the Serious Games Week matchmaker) -- sim-museum fork of KaTrain.

A mixin for KaTrainGui: hosting and joining, the Network popup, and the message-loop actions that keep the two
boards in step. Both players are human on both screens (KaTrain's AI never moves for the remote colour, and
teaching auto-undo is off), and `net_tip` is the last move of the network game: you can browse the move tree and
analyse freely, but you play, and remote moves land, at the tip.

Test hooks (each instance needs its own HOME): KATRAIN_NET_HOST=<port> [KATRAIN_NET_COLOUR=B|W],
KATRAIN_NET_JOIN=<host:port>|squeak, KATRAIN_NET_NAME, KATRAIN_NET_SCRIPT="D4 Q16 ..." (the whole game; each side
plays the entries that fall on its turns), KATRAIN_NET_EXIT_PLIES=<n> (print the game and exit once n moves are
played) and KATRAIN_NET_TIMEOUT=<s> (exit regardless).
"""
import atexit
import os
import random
import sys
import threading

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from pysgf import Move

from katrain.core import squeak
from katrain.core.constants import MODE_ANALYZE, PLAYER_HUMAN, PLAYING_NORMAL, STATUS_ERROR, STATUS_INFO, VERSION
from katrain.core.netplay import DEFAULT_PORT, NetLink


def _other(colour):
    return "W" if colour == "B" else "B"


def _trace(text):
    print("[net] " + text, flush=True)


class NetGameMixin:
    def net_init(self):
        self.net = None                 # NetLink while hosting or joined
        self.net_colour = None          # our colour in the current network game, else None
        self.net_tip = None             # last node of the network game
        self.net_ply = 0                # moves played in it
        self.net_host_colour = "B"
        self.net_announcer = None
        self.net_popup = None
        self.net_colour_seen = None

    @property
    def net_in_game(self):
        return self.net is not None and self.net_colour is not None

    def net_status(self, text, error=False):
        _trace(text)
        if self.controls:
            Clock.schedule_once(lambda _dt: self.controls.set_status(text, STATUS_ERROR if error else STATUS_INFO,
                                                                     check_level=False), -1)

    # ---------------- hosting / joining (main thread) ----------------
    def net_host(self, name, port=DEFAULT_PORT, colour="B"):
        self.net_leave()
        link = NetLink(name or "Host", self._net_received)
        try:
            link.host(int(port))
        except OSError as e:
            self.net_status("Could not host on TCP %s: %s" % (port, e), error=True)
            return False
        self.net, self.net_host_colour = link, colour
        self._net_announce()
        listed = self.net_announcer and self.net_announcer.proc
        why = "" if listed or not squeak.configured() else " (not on squeak: %s)" % self.net_announcer.last_message
        self.net_status("Hosting a Go game on TCP %d%s -- waiting for an opponent" % (
            link.port, " (listed on squeak)" if listed else why))
        return True

    def _net_announce(self):
        if self.net_announcer is None:
            self.net_announcer = squeak.Announcer()
            atexit.register(self.net_announcer.stop)
        sz = self.config("game/size")
        self.net_announcer.start(self.net.port, "%s's Go game (%s)" % (self.net.name, sz), name=self.net.name,
                                 max_players=2, version=VERSION)

    def net_join(self, name, host, port=DEFAULT_PORT):
        self.net_leave()
        link = NetLink(name or "Guest", self._net_received)
        try:
            link.join(host, int(port))
        except OSError as e:
            self.net_status("Could not reach %s:%s: %s" % (host, port, e), error=True)
            return False
        self.net = link
        self.net_status("Connected to %s:%s -- waiting for the host to start the game" % (host, port))
        return True

    def net_leave(self):
        if self.net_announcer:
            self.net_announcer.stop()
        if self.net:
            self.net.close()
        self.net, self.net_colour = None, None

    def _net_received(self, msg):
        """Socket thread -> KaTrain's message loop (net_message is never dropped as 'outdated')."""
        if self.game:
            self.message_queue.put([self.game.game_id, "net_message", (msg,), {}])

    # ---------------- message-loop actions ----------------
    def _do_net_message(self, msg):
        t = msg.get("t")
        if self.net is None:
            return
        if t == "hello" and self.net.is_host:
            if self.net_announcer:
                self.net_announcer.stop()             # a two-player game is full: off the list
            colour = self.net_host_colour
            if colour not in ("B", "W"):
                colour = random.choice("BW")
            self._net_start(colour)
        elif t == "start" and not self.net.is_host:
            self._net_new_game("W" if msg.get("you") == "W" else "B", msg.get("size", 19), msg.get("komi", 6.5),
                               msg.get("rules", "japanese"), int(msg.get("handicap") or 0))
        elif t == "move":
            self._net_remote_move(msg)
        elif t == "resign" and self.net_in_game and self.net_tip is not None:
            self.net_tip.end_state = "%s+R" % self.net_colour
            self.net_status("%s resigns -- you win" % self.net.peer_name)
        elif t == "chat":
            self.net_status("%s: %s" % (self.net.peer_name, str(msg.get("text", ""))[:300]))
        elif t == "closed":
            why = msg.get("why") or "the other player left"
            self.net_colour = None
            if self.net.is_host:
                self._net_announce()                  # back on the list
                self.net_status("%s -- waiting for another opponent" % why)
            else:
                self.net = None
                self.net_status(why)

    def _net_start(self, colour):
        """Host: start a network game (settings from the host's own new-game settings)."""
        size, komi = self.config("game/size"), self.config("game/komi")
        rules, handicap = self.config("game/rules"), int(self.config("game/handicap") or 0)
        self.net.send(t="start", name=self.net.name, you=_other(colour), size=size, komi=komi, rules=rules,
                      handicap=handicap)
        self._net_new_game(colour, size, komi, rules, handicap)

    def _net_new_game(self, colour, size, komi, rules, handicap):
        from katrain.core.game import Game
        from katrain.core.game_node import GameNode

        self.pondering = False
        if self.play_analyze_mode == MODE_ANALYZE:
            self.play_mode.switch_ui_mode()
        self.board_gui.animating_pv = None
        self.engine.on_new_game()
        names = {colour: self.net.name, _other(colour): self.net.peer_name or "Opponent"}
        # the root is built here, not from this player's New Game settings: size, komi, rules and handicap are the
        # host's on both screens (Game places the HA stones itself for a move tree)
        props = {**Game.DEFAULT_PROPERTIES, "SZ": size, "KM": komi, "RU": rules, "PB": names["B"], "PW": names["W"]}
        if handicap >= 2:
            props["HA"] = handicap
        self.game = Game(self, self.engine, move_tree=GameNode(properties=props))
        for bw in "BW":
            self.update_player(bw, player_type=PLAYER_HUMAN, player_subtype=PLAYING_NORMAL)
        self.net_colour, self.net_tip, self.net_ply = colour, self.game.root, 0
        self.net_colour_seen = colour   # survives the end of the connection (for the test hook's report)
        self.controls.graph.initialize_from_game(self.game.root)
        self.update_state(redraw_board=True)
        self.net_status("start you=%s size=%s komi=%s rules=%s handicap=%d -- playing %s with %s" % (
            colour, size, komi, rules, handicap, "Black" if colour == "B" else "White", self.net.peer_name))

    def net_check_local_play(self):
        """Called by _do_play in a network game: may the person here play now? (message loop)"""
        if not self.net.connected:
            self.net_status("Not connected -- this network game is over", error=True)
            return False
        if self.game.current_node is not self.net_tip:
            self.net_status("Go to the latest move to play", error=True)
            return False
        if self.game.end_result or self.net_tip.end_state:
            return False
        if self.net_tip.next_player != self.net_colour:
            self.net_status("Waiting for %s" % self.net.peer_name)
            return False
        return True

    def net_after_local_play(self):
        node = self.game.current_node
        n = self.net_ply
        self.net_tip, self.net_ply = node, n + 1
        gtp = node.move.gtp()
        self.net.send(t="move", n=n, gtp=gtp)
        _trace("sent %d %s" % (n, gtp))

    def _net_remote_move(self, msg):
        from katrain.core.game import IllegalMoveException

        if not self.net_in_game:
            return
        n, gtp = msg.get("n"), str(msg.get("gtp", ""))
        remote = _other(self.net_colour)
        ok = n == self.net_ply and self.net_tip.next_player == remote and not self.net_tip.end_state
        if ok:
            try:
                self.game.set_current_node(self.net_tip)
                self.game.play(Move.from_gtp(gtp, player=remote))
            except (IllegalMoveException, ValueError, IndexError, KeyError):
                ok = False
        if not ok:
            self.net.drop_peer("move %s at %s could not be played on the other board" % (gtp, n))
            self.net_colour = None
            self.net_status("%s sent a move this board cannot play (%s at move %s); disconnected" % (
                self.net.peer_name, gtp, n), error=True)
            return
        self.net_tip, self.net_ply = self.game.current_node, self.net_ply + 1
        _trace("got %d %s" % (n, gtp))
        Clock.schedule_once(self._play_stone_sound, 0)

    def net_resign(self):
        if self.net_tip is not None and not self.net_tip.end_state:
            self.net_tip.end_state = "%s+R" % _other(self.net_colour)
            self.net.send(t="resign")
            self.net_status("You resigned")

    def net_new_game_requested(self):
        """A new game while in a network game: the host starts one with colours swapped; the guest cannot."""
        if self.net.is_host and self.net.connected:
            self._net_start(_other(self.net_colour))
        else:
            self.net_status("In a network game only the host starts games -- leave it from the Network menu first")

    def net_chat(self, text):
        if self.net and self.net.send(t="chat", text=text[:300]):
            self.net_status("%s: %s" % (self.net.name, text[:300]))

    # ---------------- the Network popup (main thread) ----------------
    def _do_network_popup(self):
        default_name = (os.environ.get("SGW_NAME") or os.environ.get("USER") or "Player")[:24]
        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))

        def row(*widgets, h=36):
            b = BoxLayout(size_hint_y=None, height=dp(h), spacing=dp(6))
            for w in widgets:
                b.add_widget(w)
            root.add_widget(b)
            return b

        def lbl(text, **kw):
            return Label(text=text, halign="left", valign="middle", **kw)

        state = ("Not in a network game." if self.net is None else
                 "Playing %s." % self.net.peer_name if self.net_in_game else
                 "Hosting on TCP %d, waiting for an opponent." % self.net.port if self.net.is_host else
                 "Connected, waiting for the host.")
        row(lbl("[b]%s[/b]" % state, markup=True))
        name = TextInput(text=self.net.name if self.net else default_name, multiline=False)
        row(lbl("Your name", size_hint_x=0.35), name)
        hport = TextInput(text=str(DEFAULT_PORT), multiline=False, input_filter="int", size_hint_x=0.25)
        colour = Spinner(text="Black", values=("Black", "White", "Random"), size_hint_x=0.3)
        host_btn = Button(text="Host", size_hint_x=0.25)
        row(lbl("Host: TCP port", size_hint_x=0.3), hport, colour, host_btn)
        row(lbl("Board size, komi, rules and handicap come from the host's New Game settings. "
                + ("Hosted games are listed on squeak while they wait." if squeak.configured() else
                   "No squeak matchmaker is set up (sgw url ...): give your opponent this computer's address."),
                font_size="12sp", text_size=(dp(560), None)), h=44)
        games = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(2))
        games.bind(minimum_height=games.setter("height"))
        sv = ScrollView(size_hint_y=None, height=dp(110))
        sv.add_widget(games)
        if squeak.configured():
            refresh = Button(text="Refresh", size_hint_x=0.25)
            row(lbl("Games on squeak"), refresh)
            root.add_widget(sv)
        jhost = TextInput(text="127.0.0.1", multiline=False)
        jport = TextInput(text=str(DEFAULT_PORT), multiline=False, input_filter="int", size_hint_x=0.25)
        join_btn = Button(text="Join", size_hint_x=0.25)
        row(lbl("Join: address", size_hint_x=0.3), jhost, jport, join_btn)
        chat = TextInput(hint_text="Say something to your opponent, then Enter", multiline=False)
        row(chat)
        leave_btn = Button(text="Leave the network game", disabled=self.net is None)
        close_btn = Button(text="Close")
        row(leave_btn, close_btn)
        popup = Popup(title="Network game (squeak)", content=root, size_hint=(None, None), size=(dp(620), dp(560)))
        self.net_popup = popup

        def fill(found):
            games.clear_widgets()
            for g in found:
                b = Button(text="%s  --  %s:%d" % (g.get("title") or "Go game", g["host"], g["port"]),
                           size_hint_y=None, height=dp(32))
                b.bind(on_release=lambda _b, g=g: (setattr(jhost, "text", g["host"]),
                                                   setattr(jport, "text", str(g["port"]))))
                games.add_widget(b)
            if not found:
                games.add_widget(Label(text="(no open games on squeak right now)", size_hint_y=None, height=dp(32)))
            elif self.net is None:
                jhost.text, jport.text = found[0]["host"], str(found[0]["port"])

        def do_refresh(*_a):
            threading.Thread(target=lambda: (lambda f: Clock.schedule_once(lambda _dt: fill(f), 0))(
                squeak.list_tables()), daemon=True).start()

        if squeak.configured():
            refresh.bind(on_release=do_refresh)
            do_refresh()
        host_btn.bind(on_release=lambda *_a: (popup.dismiss(), self.net_host(
            name.text.strip(), hport.text or DEFAULT_PORT, {"Black": "B", "White": "W"}.get(colour.text, "R"))))
        join_btn.bind(on_release=lambda *_a: (popup.dismiss(), threading.Thread(
            target=self.net_join, args=(name.text.strip(), jhost.text.strip(), jport.text or DEFAULT_PORT),
            daemon=True).start()))
        chat.bind(on_text_validate=lambda ti: (self.net_chat(ti.text.strip()) if ti.text.strip() else None,
                                               setattr(ti, "text", "")))
        leave_btn.bind(on_release=lambda *_a: (self.net_leave(), self.net_status("Left the network game"),
                                               popup.dismiss()))
        close_btn.bind(on_release=lambda *_a: popup.dismiss())
        popup.open()

    # ---------------- test hooks ----------------
    def net_env_start(self, _dt=None):
        name = os.environ.get("KATRAIN_NET_NAME", "")
        shot = os.environ.get("KATRAIN_NET_POPUP_SHOT")
        if shot:  # open the Network popup, screenshot it, exit
            from kivy.core.window import Window

            self("network-popup")
            Clock.schedule_once(lambda _dt: (_trace("popup screenshot " + str(Window.screenshot(name=shot))),
                                             os._exit(0)), 6)
            return
        if os.environ.get("KATRAIN_NET_HOST"):
            self.net_host(name or "Host", int(os.environ["KATRAIN_NET_HOST"]), os.environ.get("KATRAIN_NET_COLOUR", "B"))
        elif os.environ.get("KATRAIN_NET_JOIN"):
            target = os.environ["KATRAIN_NET_JOIN"]
            if target == "squeak":
                found = squeak.list_tables()
                if not found:
                    _trace("join: no games on squeak")
                    os._exit(3)
                host, port = found[0]["host"], found[0]["port"]
                _trace("join: squeak lists %d game(s); joining %s at %s:%d" % (len(found), found[0].get("title"),
                                                                               host, port))
            else:
                host, port = target.rsplit(":", 1)
            self.net_join(name or "Guest", host, int(port))
        else:
            return
        script = os.environ.get("KATRAIN_NET_SCRIPT", "").split()
        exit_plies = int(os.environ.get("KATRAIN_NET_EXIT_PLIES", "0") or 0)
        timeout = float(os.environ.get("KATRAIN_NET_TIMEOUT", "0") or 0)

        def tick(_dt):
            if self.net_in_game and self.net_tip is not None:
                if (self.net_ply < len(script) and self.game.current_node is self.net_tip
                        and self.net_tip.next_player == self.net_colour):
                    coords = Move.from_gtp(script[self.net_ply]).coords
                    if getattr(self, "_net_script_sent", None) != self.net_ply:
                        self._net_script_sent = self.net_ply
                        self("play", coords)
            if self.net_tip is not None and self.net_colour_seen:
                if exit_plies and self.net_ply >= exit_plies:
                        moves, node = [], self.net_tip
                        while node.parent is not None:
                            moves.append(node.move.gtp())
                            node = node.parent
                        pr = self.game.prisoner_count
                        _trace("final you=%s moves=%s prisoners=B%d/W%d" % (self.net_colour_seen, " ".join(reversed(moves)),
                                                                            pr["B"], pr["W"]))
                        self.net_leave()
                        os._exit(0)

        Clock.schedule_interval(tick, 0.3)
        if timeout:
            Clock.schedule_once(lambda _dt: (_trace("timeout"), self.net_leave(), os._exit(2)), timeout)
