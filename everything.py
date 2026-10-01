#!/usr/bin/env python3
"""herdr-everything: one search across agents, spaces, tabs, panes, herdr commands, tools and plugin actions."""
import json, os, re, select, shutil, socket, subprocess, sys, termios, tty

import tools

DIM, BOLD, REV, RED, RESET = "\033[2m", "\033[1m", "\033[7m", "\033[31m", "\033[0m"
KIND_COLORS = {"agent": "\033[35m", "space": "\033[34m", "tab": "\033[36m", "pane": "\033[37m",
               "cmd": "\033[33m", "tool": "\033[32m", "action": "\033[33m"}
# Depending on the terminal, alt+space arrives as an ESC prefix or via the kitty keyboard protocol.
ALT_SPACE = ("\x1b ", "\x1b[32;3u")
ESC, ENTER = "\x1b", ("\r", "\n")
UP_KEYS = ("\x1b[A", "\x10")  # ↑, ctrl+p
DOWN_KEYS = ("\x1b[B", "\x0e")  # ↓, ctrl+n
DELETE_WORD_KEYS = ("\x1b\x7f", "\x1b\x08", "\x1b[127;3u", "\x17")  # alt+backspace (ESC prefix / kitty), ctrl+w
HERDR = os.environ.get("HERDR_BIN_PATH") or "herdr"
SOCKET = os.environ.get("HERDR_SOCKET_PATH") or os.path.expanduser("~/.config/herdr/herdr.sock")
TOOLS_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools.py")
SELF_ID = "herdr-everything"
fd = sys.stdin.fileno()


# --- herdr ------------------------------------------------------------------

def call(method, params=None):
    """One request over the herdr socket API (newline-delimited JSON)."""
    with socket.socket(socket.AF_UNIX) as s:
        s.connect(SOCKET)
        s.sendall((json.dumps({"id": "everything", "method": method, "params": params or {}}) + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    reply = json.loads(data)
    if "error" in reply:
        raise RuntimeError(reply["error"].get("message", "herdr error"))
    return reply["result"]


def herdr(*args):
    """Run a herdr CLI command; raise with herdr's own message on failure."""
    out = subprocess.run([HERDR, *args], capture_output=True, text=True)
    try:
        error = json.loads(out.stdout).get("error")
    except ValueError:
        error = None
    if out.returncode != 0 or error:
        raise RuntimeError((error or {}).get("message") or out.stderr.strip() or "herdr command failed")


def short_path(path):
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path and path.startswith(home) else path or ""


# --- Entries ----------------------------------------------------------------
# Every entry: kind, title, subtitle, run. `ask` = label of a text prompt whose answer is passed to run;
# `confirm` = ask before running (for closing things).

def entry(kind, title, subtitle, run, keywords="", ask=None, confirm=False):
    return {"kind": kind, "title": title, "subtitle": subtitle, "run": run, "ask": ask, "confirm": confirm,
            "haystack": f"{title} {subtitle} {keywords} {kind}".lower()}


def collect():
    snap = call("session.snapshot")["snapshot"]
    spaces = {w["workspace_id"]: w for w in snap["workspaces"]}
    tabs = {t["tab_id"]: t for t in snap["tabs"]}
    agent_panes = {a["pane_id"] for a in snap["agents"]}

    def where(item):
        space = spaces.get(item["workspace_id"], {}).get("label", "")
        tab = tabs.get(item.get("tab_id"), {}).get("label", "")
        return f"{space} › {tab}" if tab else space

    def focus(method, key, value):
        return lambda: call(method, {key: value})

    items = []
    for a in snap["agents"]:
        task = a.get("terminal_title_stripped") or a["agent"]
        items.append(entry("agent", task, f"{a['agent']} · {a['agent_status']} · {where(a)}",
                           focus("pane.focus", "pane_id", a["pane_id"]), short_path(a.get("cwd"))))
    for w in snap["workspaces"]:
        items.append(entry("space", w["label"], f"{w['tab_count']} tabs · {w['pane_count']} panes",
                           focus("workspace.focus", "workspace_id", w["workspace_id"])))
    for t in snap["tabs"]:
        items.append(entry("tab", t["label"], where(t), focus("tab.focus", "tab_id", t["tab_id"])))
    for p in snap["panes"]:
        if p["pane_id"] in agent_panes:
            continue  # already listed as an agent
        # Shell panes are usually titled like the prompt (user@host:~/…); the directory says more.
        cwd = short_path(p.get("foreground_cwd") or p.get("cwd"))
        items.append(entry("pane", cwd, where(p), focus("pane.focus", "pane_id", p["pane_id"]),
                           p.get("terminal_title_stripped", "")))

    current = next((p for p in snap["panes"] if p["pane_id"] == snap.get("focused_pane_id")), None)
    if current:
        items += commands(current, spaces.get(current["workspace_id"], {}), tabs.get(current["tab_id"], {}))
    items += [entry("tool", label, "tool", lambda key=key: run_tool(key), keywords)
              for key, label, _, keywords in tools.TOOLS]
    items += plugin_actions()
    return items


def commands(pane, space, tab):
    """Built-in herdr commands, applied to the pane (and its tab and workspace) that was focused on open."""
    p, t, w = pane["pane_id"], pane["tab_id"], pane["workspace_id"]
    cwd = pane.get("foreground_cwd") or pane.get("cwd") or os.path.expanduser("~")
    here, tab_name, space_name = short_path(cwd), tab.get("label", t), space.get("label", w)
    cmds = [
        entry("cmd", "New workspace", here, lambda: herdr("workspace", "create", "--cwd", cwd, "--focus")),
        entry("cmd", "Rename workspace", space_name, lambda name: herdr("workspace", "rename", w, name), ask="New name"),
        entry("cmd", "Close workspace", space_name, lambda: herdr("workspace", "close", w), confirm=True),
        entry("cmd", "New tab", f"{space_name} · {here}",
              lambda: herdr("tab", "create", "--workspace", w, "--cwd", cwd, "--focus")),
        entry("cmd", "Rename tab", tab_name, lambda name: herdr("tab", "rename", t, name), ask="New name"),
        entry("cmd", "Close tab", tab_name, lambda: herdr("tab", "close", t), confirm=True),
        entry("cmd", "Split pane right", here, lambda: herdr("pane", "split", "--pane", p, "--direction", "right",
                                                             "--cwd", cwd, "--focus"), "vertical"),
        entry("cmd", "Split pane down", here, lambda: herdr("pane", "split", "--pane", p, "--direction", "down",
                                                            "--cwd", cwd, "--focus"), "horizontal"),
        entry("cmd", "Toggle pane zoom", here, lambda: herdr("pane", "zoom", "--pane", p, "--toggle"), "maximize"),
        entry("cmd", "Rename pane", here, lambda name: herdr("pane", "rename", p, name), ask="New name"),
        entry("cmd", "Clear pane name", here, lambda: herdr("pane", "rename", p, "--clear")),
        entry("cmd", "Move pane to new tab", here, lambda: herdr("pane", "move", p, "--new-tab", "--focus")),
        entry("cmd", "Move pane to new workspace", here, lambda: herdr("pane", "move", p, "--new-workspace", "--focus")),
        entry("cmd", "Close pane", here, lambda: herdr("pane", "close", p), confirm=True),
        entry("cmd", "New worktree", here, lambda branch: herdr("worktree", "create", "--workspace", w, "--cwd", cwd,
                                                               *(["--branch", branch] if branch else []), "--focus"),
              "git branch", ask="Branch (empty = automatic)"),
    ]
    for d in ("left", "right", "up", "down"):
        cmds += [
            entry("cmd", f"Focus pane {d}", here, lambda d=d: herdr("pane", "focus", "--pane", p, "--direction", d)),
            entry("cmd", f"Swap pane {d}", here, lambda d=d: herdr("pane", "swap", "--pane", p, "--direction", d)),
            entry("cmd", f"Resize pane {d}", here, lambda d=d: herdr("pane", "resize", "--pane", p, "--direction", d)),
        ]
    return cmds


def plugin_actions():
    out = subprocess.run([HERDR, "plugin", "list", "--json"], capture_output=True, text=True)
    try:
        plugins = json.loads(out.stdout)["result"]["plugins"]
    except (ValueError, KeyError):
        return []
    return [entry("action", action["title"], plugin["name"], lambda ref=f"{plugin['plugin_id']}.{action['id']}":
                  invoke_later(ref), action.get("description", ""))
            for plugin in plugins if plugin.get("enabled") and plugin["plugin_id"] != SELF_ID
            for action in plugin.get("actions", [])]


def run_tool(key):
    """Run a tool right inside this popup."""
    termios.tcsetattr(fd, termios.TCSADRAIN, ORIGINAL)
    subprocess.run(["python3", TOOLS_SCRIPT, "--tool", key])


def invoke_later(ref):
    # Plugin actions often open a popup themselves, which only works once ours is closed.
    subprocess.Popen(["sh", "-c", 'sleep 0.3; exec "$0" plugin action invoke "$1"', HERDR, ref],
                     start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# --- Search -----------------------------------------------------------------

def score_word(word, text):
    """Fuzzy score of one search word: None = no match, higher = better."""
    i = text.find(word)
    if i >= 0:  # contiguous match, best at a word start
        return 100 + (50 if i == 0 or not text[i - 1].isalnum() else 0) - i * 0.1
    score, pos, prev = 0, 0, -2
    for ch in word:  # otherwise: all chars in order, bonus for runs and word starts
        i = text.find(ch, pos)
        if i < 0:
            return None
        score += 5 if i == prev + 1 else 0
        score += 4 if i == 0 or not text[i - 1].isalnum() else 0
        score -= min(i - pos, 10) * 0.5
        prev, pos = i, i + 1
    return score


def search(items, query):
    words = query.lower().split()
    if not words:
        return items
    ranked = []
    for order, item in enumerate(items):
        total = 0
        for word in words:
            title_hit = score_word(word, item["title"].lower())
            hit = title_hit if title_hit is not None else score_word(word, item["haystack"])
            if hit is None:
                break
            total += hit + (title_hit or 0)  # title matches count double
        else:
            ranked.append((-total, order, item))
    return [item for *_, item in sorted(ranked, key=lambda r: (r[0], r[1]))]


# --- UI ---------------------------------------------------------------------

def read_input():
    data = os.read(fd, 65536)
    while select.select([fd], [], [], 0.01)[0]:
        data += os.read(fd, 65536)
    return data.decode("utf-8", "replace")


def draw(lines, footer):
    _, rows = shutil.get_terminal_size()
    sys.stdout.write("\033[H\033[2J" + "\n".join(lines) + f"\033[{rows};1H" + footer)
    sys.stdout.flush()


def draw_results(query, results, selected, error):
    cols, rows = shutil.get_terminal_size()
    visible = max(rows - 4, 1)
    top = max(0, selected - visible + 1)
    lines = [f"{BOLD}›{RESET} {query}{REV} {RESET}", ""]
    for i, item in enumerate(results[top:top + visible], start=top):
        badge = f"{KIND_COLORS[item['kind']]}{item['kind']:<6}{RESET}"
        title = item["title"][:cols - 10]
        subtitle = item["subtitle"][:max(cols - 12 - len(title), 0)]  # never wrap
        line = f" {badge} {title}  {DIM}{subtitle}{RESET}"
        lines.append(f"{REV}{line}{RESET}" if i == selected else line)
    if not results:
        lines.append(f"  {DIM}no matches{RESET}")
    draw(lines, error or f"{DIM}↑↓ select · Enter open · Esc/alt+space close{RESET}")


def edit(text, key):
    """Apply a key to a single-line input; None if the key is not an edit."""
    if key in ("\x7f", "\x08"):
        return text[:-1]
    if key in DELETE_WORD_KEYS:
        return re.sub(r"\S*\s*$", "", text)
    if key == "\x15":  # ctrl+u
        return ""
    if key.isprintable():  # may be several chars when typing fast or pasting
        return text + key
    return None


def ask(item):
    """Prompt for the item's text input or confirmation. None = cancelled."""
    text = ""
    while True:
        if item["confirm"]:
            draw([f"{BOLD}{item['title']}{RESET}  {DIM}{item['subtitle']}{RESET}"],
                 f"{DIM}Enter confirm · Esc cancel{RESET}")
        else:
            draw([f"{BOLD}{item['title']}{RESET}  {DIM}{item['subtitle']}{RESET}", "",
                  f"{item['ask']}: {text}{REV} {RESET}"], f"{DIM}Enter confirm · Esc cancel{RESET}")
        key = read_input()
        if key in ALT_SPACE:
            raise KeyboardInterrupt
        if key == ESC:
            return None
        if key in ENTER:
            return text
        if not item["confirm"] and (new := edit(text, key)) is not None:
            text = new


def main():
    items = collect()
    query, selected, error = "", 0, ""
    while True:
        results = search(items, query)
        selected = min(selected, max(len(results) - 1, 0))
        draw_results(query, results, selected, error)
        key, error = read_input(), ""
        if key == ESC or key in ALT_SPACE:
            return
        if key in ENTER and results:
            item = results[selected]
            try:
                if item["ask"] or item["confirm"]:
                    answer = ask(item)
                    if answer is None:
                        continue
                    item["run"](answer) if item["ask"] else item["run"]()
                else:
                    item["run"]()
                return
            except RuntimeError as e:  # herdr refused, e.g. the pane was closed meanwhile
                error = f"{RED}✗ {e}{RESET}"
        elif key in UP_KEYS:
            selected = max(selected - 1, 0)
        elif key in DOWN_KEYS:
            selected = min(selected + 1, max(len(results) - 1, 0))
        elif (new := edit(query, key)) is not None:
            query, selected = new, 0


if __name__ == "__main__":
    ORIGINAL = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    sys.stdout.write("\033[?25l")
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, ORIGINAL)
        sys.stdout.write("\033[?25h")
