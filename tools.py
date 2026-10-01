#!/usr/bin/env python3
"""herdr-everything tools: small dev tools in a popup; the result goes to the clipboard."""
import os, random, secrets, select, shutil, string, subprocess, sys, termios, tty, uuid

RED, GREEN, DIM, BOLD, RESET = "\033[31m", "\033[32m", "\033[2m", "\033[1m", "\033[0m"
# alt+space and alt+t close the popup; depending on the terminal they arrive as an ESC prefix or via the kitty keyboard protocol.
CLOSE_KEYS = ("\x1b ", "\x1b[32;3u", "\x1bt", "\x1b[116;3u")
ESC, ENTER = "\x1b", ("\n", "\r")
UP, DOWN = "\x1b[A", "\x1b[B"
LESSKEY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lesskey")
fd = sys.stdin.fileno()


class Close(Exception):
    pass


def read_input(burst=0.03):
    """One key press or a whole paste burst (ends once nothing arrives for `burst` seconds)."""
    data = os.read(fd, 65536)
    while select.select([fd], [], [], burst)[0]:
        data += os.read(fd, 65536)
    text = data.decode("utf-8", "replace")
    if text in CLOSE_KEYS:
        raise Close
    return text


def screen(*lines):
    sys.stdout.write("\033[H\033[2J" + "\n".join(lines) + "\n")
    sys.stdout.flush()


# First available clipboard command: macOS, Wayland, X11.
CLIPBOARD = next(([*cmd] for cmd in (("pbcopy",), ("wl-copy",), ("xclip", "-selection", "clipboard")) if shutil.which(cmd[0])), None)
PASTE = next(([*cmd] for cmd in (("pbpaste",), ("wl-paste", "-n"), ("xclip", "-selection", "clipboard", "-o")) if shutil.which(cmd[0])), None)


def copy(text):
    if CLIPBOARD:
        subprocess.run(CLIPBOARD, input=text, text=True)


def paste():
    return subprocess.run(PASTE, capture_output=True, text=True).stdout if PASTE else ""


def help_line(*items):
    return f"\n{DIM}" + " · ".join(items) + RESET


# --- JSON -----------------------------------------------------------------

def json_tool():
    error = ""
    while True:
        screen(f"{BOLD}Format JSON{RESET}", "", "Paste JSON.", error,
               help_line("Enter = use clipboard", "Esc = back", "alt+space = close"))
        text = read_input(burst=0.15)  # long pastes arrive in several chunks
        if text == ESC:
            return False
        if not text.strip():
            text = paste()
        plain = subprocess.run(["jq", "."], input=text, capture_output=True, text=True)
        if plain.returncode != 0:
            error = f"\n{RED}✗ {plain.stderr.strip() or 'invalid JSON'}{RESET}"
            continue
        copy(plain.stdout)
        color = subprocess.run(["jq", "-C", "."], input=text, capture_output=True, text=True).stdout
        header = f"{GREEN}✓ formatted & copied to clipboard{RESET} {DIM}(q = close){RESET}\n\n"
        with cooked():
            subprocess.run(["less", "-R", f"--lesskey-src={LESSKEY}"], input=header + color, text=True)
        return True


# --- Random String --------------------------------------------------------

def random_tool():
    classes = {  # key: [enabled, label, characters]
        "u": [True, "Uppercase", string.ascii_uppercase],
        "l": [True, "Lowercase", string.ascii_lowercase],
        "d": [True, "Digits", string.digits],
        "s": [False, "Symbols", string.punctuation],
    }
    length, typing = 32, False

    def generate():
        pool = "".join(chars for on, _, chars in classes.values() if on)
        return "".join(secrets.choice(pool) for _ in range(length)) if pool else ""

    value = generate()
    while True:
        rows = [f"  [{'x' if on else ' '}] {key}  {label}" for key, (on, label, _) in classes.items()]
        screen(f"{BOLD}Random String{RESET}", "", *rows, "", f"  Length: {BOLD}{length}{RESET}", "",
               f"  {GREEN}{value}{RESET}" if value else f"  {RED}enable at least one character class{RESET}",
               help_line("u/l/d/s = toggle", "type a number / +- / ↑↓ = length", "Space = new",
                         "Enter = copy", "Esc = back"))
        key = read_input()
        was_typing, typing = typing, False
        if key == ESC:
            return False
        if key in ENTER and value:
            copy(value)
            return True
        if key in classes:
            classes[key][0] = not classes[key][0]
        elif key.isdigit():
            length = int(f"{length}{key}") if was_typing else int(key)
            typing = True
        elif key in ("+", "="):
            length += 1
        elif key == "-":
            length -= 1
        elif key == UP:
            length += 8
        elif key == DOWN:
            length -= 8
        elif key != " ":
            continue
        length = max(1, min(length, 4096))
        value = generate()


# --- UUID -----------------------------------------------------------------

def uuid_tool():
    value = str(uuid.uuid4())
    while True:
        screen(f"{BOLD}UUID v4{RESET}", "", f"  {GREEN}{value}{RESET}",
               help_line("Space = new", "Enter = copy", "Esc = back"))
        key = read_input()
        if key == ESC:
            return False
        if key in ENTER:
            copy(value)
            return True
        if key == " ":
            value = str(uuid.uuid4())


# --- Lorem Ipsum ----------------------------------------------------------

LOREM_START = "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
LOREM_WORDS = """lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut
labore et dolore magna aliqua enim ad minim veniam quis nostrud exercitation ullamco laboris nisi aliquip ex ea
commodo consequat duis aute irure in reprehenderit voluptate velit esse cillum fugiat nulla pariatur excepteur
sint occaecat cupidatat non proident sunt culpa qui officia deserunt mollit anim id est laborum""".split()


def lorem_sentence():
    words = random.choices(LOREM_WORDS, k=random.randint(6, 14))
    if len(words) > 8:
        words[random.randint(3, len(words) - 4)] += ","
    return " ".join(words).capitalize() + "."


def lorem(paragraphs):
    out = []
    for i in range(paragraphs):
        sentences = [lorem_sentence() for _ in range(random.randint(4, 7))]
        if i == 0:
            sentences[0] = LOREM_START
        out.append(" ".join(sentences))
    return "\n\n".join(out)


def lorem_tool():
    count = 1
    value = lorem(count)
    while True:
        screen(f"{BOLD}Lorem Ipsum{RESET}", "", f"  Paragraphs: {BOLD}{count}{RESET}", "", value,
               help_line("+- / number = paragraphs", "Space = new", "Enter = copy", "Esc = back"))
        key = read_input()
        if key == ESC:
            return False
        if key in ENTER:
            copy(value)
            return True
        if key in ("+", "="):
            count = min(count + 1, 20)
        elif key == "-":
            count = max(count - 1, 1)
        elif key in "123456789" and len(key) == 1:
            count = int(key)
        elif key != " ":
            continue
        value = lorem(count)


# --- Menu -----------------------------------------------------------------

TOOLS = [  # key, label, function, extra search keywords
    ("j", "Format JSON", json_tool, "json format pretty beautify jq"),
    ("r", "Random String", random_tool, "random string password secret token generator"),
    ("u", "UUID", uuid_tool, "uuid guid id v4"),
    ("l", "Lorem Ipsum", lorem_tool, "lorem ipsum placeholder dummy text"),
]


class cooked:
    """Temporarily restore the normal terminal mode (for less)."""

    def __enter__(self):
        termios.tcsetattr(fd, termios.TCSADRAIN, ORIGINAL)

    def __exit__(self, *_):
        tty.setcbreak(fd)


def main(start=None):
    """`start` = a tool key: open that tool directly; Esc then closes instead of showing the menu."""
    for shortcut, _, tool, _ in TOOLS:
        if shortcut == start:
            tool()
            return
    while True:
        rows = [f"  {i + 1}  {key}  {label}" for i, (key, label, _, _) in enumerate(TOOLS)]
        screen(f"{BOLD}Tools{RESET}", "", *rows, help_line("press a key or number", "Esc/alt+space = close"))
        key = read_input()
        if key in (ESC, "q"):
            return
        for i, (shortcut, _, tool, _) in enumerate(TOOLS):
            if key in (shortcut, str(i + 1)) and tool():
                return


if __name__ == "__main__":
    start = sys.argv[2] if sys.argv[1:2] == ["--tool"] and len(sys.argv) > 2 else None
    ORIGINAL = termios.tcgetattr(fd)
    tty.setcbreak(fd)  # read keys immediately, no 1024-byte line limit when pasting
    sys.stdout.write("\033[?25l")  # hide cursor
    try:
        main(start)
    except (Close, KeyboardInterrupt):
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, ORIGINAL)
        sys.stdout.write("\033[?25h")
