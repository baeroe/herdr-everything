"""Smoke test: runs tools.py in a pseudo-terminal and replays keys (macOS clipboard). Usage: python3 test_tools.py"""
import fcntl, json, os, pty, re, select, string, struct, subprocess, termios, time, uuid

os.environ["TERM"] = "xterm-256color"


def run(keys):
    """Send keys, return (still running?, output)."""
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp("python3", ["python3", "tools.py"])
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
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
    for k in keys:
        drain(0.4)
        os.write(fd, k)
    drain(1.0)
    alive = os.waitpid(pid, os.WNOHANG) == (0, 0)
    if alive:
        os.kill(pid, 9)
        os.waitpid(pid, 0)
    return alive, out.decode(errors="replace")


def clip():
    return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout


saved = clip()
try:
    # JSON: broken -> error, then a large single-line JSON -> formatted, less open, alt+space closes
    big = json.dumps({"items": [{"id": i, "name": "x" * 20} for i in range(200)]}).encode()
    alive, out = run([b"j", b"{broken", big, b"\x1b "])
    assert not alive and "✗" in out, out[-400:]
    assert json.loads(clip())["items"][199]["id"] == 199 and clip().count("\n") > 100

    # Random String: digits only (u, l off), length 12, copy
    alive, _ = run([b"r", b"u", b"l", b"1", b"2", b"\r"])
    assert not alive and re.fullmatch(r"\d{12}", clip()), clip()
    # Random String: symbols on, length + to 33
    alive, _ = run([b"2", b"s", b"+", b"\r"])
    assert not alive and len(clip()) == 33 and set(clip()) <= set(string.ascii_letters + string.digits + string.punctuation)

    # UUID
    alive, _ = run([b"u", b" ", b"\r"])
    assert not alive and uuid.UUID(clip()).version == 4

    # Lorem: 3 paragraphs
    alive, _ = run([b"l", b"3", b"\r"])
    assert not alive and clip().startswith("Lorem ipsum dolor sit amet") and clip().count("\n\n") == 2

    # Esc in a tool -> back to the menu (still running), Esc in the menu -> closed, alt+space/alt+t close anywhere
    assert run([b"u", b"\x1b"])[0]
    assert not run([b"u", b"\x1b", b"\x1b"])[0]
    assert not run([b"r", b"\x1b[32;3u"])[0]
    assert not run([b"r", b"\x1b[116;3u"])[0]
    print("ok")
finally:
    subprocess.run(["pbcopy"], input=saved, text=True)
