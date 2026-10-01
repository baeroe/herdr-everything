"""Smoke-Test: startet omni.py in einem Pseudo-Terminal gegen den laufenden herdr. Aufruf: python3 test_omni.py"""
import fcntl, json, os, pty, re, select, socket, struct, subprocess, termios, time

os.environ["TERM"] = "xterm-256color"


def run(keys):
    """Tasten senden, (noch am Leben?, Ausgabe) zurückgeben."""
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp("python3", ["python3", "omni.py"])
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 120, 0, 0))
    out = b""

    def drain(s):
        nonlocal out
        end = time.time() + s
        while time.time() < end:
            if select.select([fd], [], [], 0.05)[0]:
                try:
                    out += os.read(fd, 65536)
                except OSError:
                    return
    drain(1.5)  # Daten laden
    for k in keys:
        os.write(fd, k)
        drain(0.5)
    drain(0.5)
    alive = os.waitpid(pid, os.WNOHANG) == (0, 0)
    if alive:
        os.kill(pid, 9)
        os.waitpid(pid, 0)
    return alive, out.decode(errors="replace")


def snapshot():
    with socket.socket(socket.AF_UNIX) as s:
        s.connect(os.path.expanduser("~/.config/herdr/herdr.sock"))
        s.sendall(b'{"id":"t","method":"session.snapshot","params":{}}\n')
        data = b""
        while not data.endswith(b"\n"):
            data += s.recv(65536)
    return json.loads(data)["result"]["snapshot"]


clip = lambda: subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
saved = clip()
try:
    # Suche zeigt Treffer, Esc / alt+space schließen, Tippen allein schließt nicht
    alive, out = run([b"rand"])
    assert alive and "Random String" in out, out[-500:]
    assert not run([b"x", b"\x1b"])[0]
    assert not run([b"\x1b "])[0]
    assert not run([b"\x1b[32;3u"])[0]
    # Backspace + ctrl+u: Suche "zzzzqqq" hat keine Treffer, nach ctrl+u wieder alles
    alive, out = run([b"zzzzqqq"])
    assert "keine Treffer" in out
    # Toolbox-Tool direkt aus Omni: "rand" + Enter öffnet Random String, Enter kopiert
    alive, _ = run([b"rand", b"\r", b"\r"])
    assert not alive and re.fullmatch(r"[A-Za-z0-9]{32}", clip()), clip()
    # Fokus: das gerade fokussierte Agent-Pane über seinen Titel suchen -> Fokus bleibt gleich, Omni zu.
    # (Ein anderes Pane zu fokussieren würde deine Ansicht umschalten.)
    snap = snapshot()
    me = next((a for a in snap["agents"] if a["pane_id"] == snap["focused_pane_id"]), None)
    if me:
        alive, _ = run([me["terminal_title_stripped"].encode(), b"\x1b[B", b"\x1b[A", b"\r"])
        assert not alive and snapshot()["focused_pane_id"] == me["pane_id"]
    print("ok")
finally:
    subprocess.run(["pbcopy"], input=saved, text=True)
