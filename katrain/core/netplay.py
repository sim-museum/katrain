"""Two-player network Go for KaTrain (sim-museum fork): one TCP connection, one JSON object per line.

The host listens and starts each game (board size, komi, rules, handicap and colours come from the host); the guest
connects. Both run KaTrain, so both boards check every move: moves travel as GTP coordinates with their move number,
and a move the board cannot play ends the connection instead of letting the two games silently diverge.

  guest -> host   {"t":"hello", "name":..., "version":...}
  host  -> guest  {"t":"start", "name":..., "you":"B"|"W", "size":[x, y], "komi":..., "rules":..., "handicap":...}
  either way      {"t":"move", "n":<moves played before it>, "gtp":"Q16"|"pass"}
                  {"t":"resign"}  {"t":"chat", "text":...}  {"t":"bye"}

Sockets run on background threads; every message is handed to `on_message(dict)` on that thread, and KaTrain turns
it into a message-loop action, so game state is only ever touched from KaTrain's own message loop.
"""
import json
import socket
import threading

DEFAULT_PORT = 47830
PROTOCOL = 1


class NetLink:
    def __init__(self, name, on_message):
        self.name = name
        self.on_message = on_message
        self.is_host = False
        self.port = 0
        self.peer_name = ""
        self._srv = None
        self._sock = None
        self._wlock = threading.Lock()
        self._closing = False

    @property
    def connected(self):
        return self._sock is not None

    # ---- host ----
    def host(self, port=DEFAULT_PORT):
        self.is_host = True
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen(2)
        self._srv, self.port = srv, srv.getsockname()[1]
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while not self._closing:
            try:
                s, _addr = self._srv.accept()
            except OSError:
                return
            if self._sock is not None:            # a two-player game: one guest at a time
                try:
                    s.sendall(b'{"t":"bye","why":"this game is full"}\n')
                    s.close()
                except OSError:
                    pass
                continue
            self._attach(s)

    # ---- guest ----
    def join(self, host, port=DEFAULT_PORT, timeout=10):
        s = socket.create_connection((host, port), timeout=timeout)
        s.settimeout(None)
        self._attach(s)
        self.send(t="hello", name=self.name, version=PROTOCOL)

    # ---- both ----
    def _attach(self, s):
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock = s
        threading.Thread(target=self._read_loop, args=(s,), daemon=True).start()

    def _read_loop(self, s):
        buf = b""
        why = "the other player left"
        try:
            while True:
                data = s.recv(65536)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        msg = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(msg, dict):
                        continue
                    if msg.get("t") == "bye":
                        why = msg.get("why") or "%s left" % (self.peer_name or "the other player")
                        raise ConnectionError
                    if msg.get("t") in ("hello", "start"):
                        self.peer_name = str(msg.get("name", "Guest" if self.is_host else "Host"))[:24]
                    self.on_message(msg)
        except (OSError, ConnectionError):
            pass
        if self._sock is s:
            self._sock = None
            try:
                s.close()
            except OSError:
                pass
            if not self._closing:
                self.on_message({"t": "closed", "why": why})

    def send(self, **msg):
        s = self._sock
        if s is None:
            return False
        try:
            with self._wlock:
                s.sendall((json.dumps(msg) + "\n").encode())
            return True
        except OSError:
            return False

    def drop_peer(self, why=""):
        """Close the current connection (a host keeps listening for the next guest)."""
        s, self._sock = self._sock, None
        if s is not None:
            try:
                s.sendall((json.dumps({"t": "bye", "why": why}) + "\n").encode())
                s.close()
            except OSError:
                pass

    def close(self):
        self._closing = True
        self.drop_peer()
        if self._srv is not None:
            try:
                self._srv.close()
            except OSError:
                pass
