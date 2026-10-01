#!/usr/bin/env python3
"""herdr Omni: one search across agents, spaces, tabs, panes, toolbox tools and plugin actions."""
import json, os, select, shutil, socket, subprocess, sys, termios, tty

DIM, BOLD, REV, RESET = "\033[2m", "\033[1m", "\033[7m", "\033[0m"
KIND_COLORS = {"agent": "\033[35m", "space": "\033[34m", "tab": "\033[36m", "pane": "\033[37m",
               "tool": "\033[32m", "action": "\033[33m"}
# Depending on the terminal, alt+space arrives as an ESC prefix or via the kitty keyboard protocol.
CLOSE_KEYS = ("\x1b", "\x1b ", "\x1b[32;3u")
UP_KEYS = ("\x1b[A", "\x10")  # ↑, ctrl+p
DOWN_KEYS = ("\x1b[B", "\x0e")  # ↓, ctrl+n
HERDR = os.environ.get("HERDR_BIN_PATH") or "herdr"
SOCKET = os.environ.get("HERDR_SOCKET_PATH") or os.path.expanduser("~/.config/herdr/herdr.sock")
SELF_ID = "herdr-omni"
fd = sys.stdin.fileno()


# --- herdr ----------------------------------------------------------------

def call(method, params=None):
    """One request over the herdr socket API (newline-delimited JSON)."""
    with socket.socket(socket.AF_UNIX) as s:
        s.connect(SOCKET)
        s.sendall((json.dumps({"id": "omni", "method": method, "params": params or {}}) + "\n").encode())
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


def short_path(path):
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path and path.startswith(home) else path or ""


# --- Entries -------------------------------------------------------------
# Every entry: kind, title, subtitle, keywords, run (a function without arguments).

def entry(kind, title, subtitle, run, keywords=""):
    return {"kind": kind, "title": title, "subtitle": subtitle, "run": run,
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

    plugins = json.loads(subprocess.run([HERDR, "plugin", "list", "--json"], capture_output=True, text=True).stdout)
    for plugin in plugins["result"]["plugins"]:
        if not plugin.get("enabled") or plugin["plugin_id"] == SELF_ID:
            continue
        if plugin["plugin_id"] == "herdr-toolbox":
            items += toolbox_entries(plugin["plugin_root"])
        for action in plugin.get("actions", []):
            ref = f"{plugin['plugin_id']}.{action['id']}"
            items.append(entry("action", action["title"], plugin["name"], lambda ref=ref: invoke_later(ref),
                               action.get("description", "")))
    return items


def toolbox_entries(root):
    script = os.path.join(root, "toolbox.py")
    out = subprocess.run(["python3", script, "--list"], capture_output=True, text=True)
    if out.returncode != 0:
        return []
    return [entry("tool", t["label"], "Toolbox", lambda key=t["key"]: run_tool(script, key), t["keywords"])
            for t in json.loads(out.stdout)]


def run_tool(script, key):
    """Run a toolbox tool right inside this popup."""
    termios.tcsetattr(fd, termios.TCSADRAIN, ORIGINAL)
    subprocess.run(["python3", script, "--tool", key])


def invoke_later(ref):
    # Plugin actions often open a popup themselves, which only works once ours is closed.
    subprocess.Popen(["sh", "-c", 'sleep 0.3; exec "$0" plugin action invoke "$1"', HERDR, ref],
                     start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# --- Search --------------------------------------------------------------

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


def draw(query, results, selected, error=""):
    cols, rows = shutil.get_terminal_size()
    visible = max(rows - 4, 1)
    top = max(0, selected - visible + 1)
    lines = [f"{BOLD}›{RESET} {query}\033[7m \033[0m", ""]
    for i, item in enumerate(results[top:top + visible], start=top):
        badge = f"{KIND_COLORS[item['kind']]}{item['kind']:<6}{RESET}"
        title = item["title"][:cols - 10]
        subtitle = item["subtitle"][:max(cols - 12 - len(title), 0)]  # never wrap
        line = f" {badge} {title}  {DIM}{subtitle}{RESET}"
        lines.append(f"{REV}{line}{RESET}" if i == selected else line)
    if not results:
        lines.append(f"  {DIM}no matches{RESET}")
    footer = error or f"{DIM}↑↓ select · Enter open · Esc/alt+space close{RESET}"
    sys.stdout.write("\033[H\033[2J" + "\n".join(lines) + f"\033[{rows};1H" + footer)
    sys.stdout.flush()


def main():
    items = collect()
    query, selected, error = "", 0, ""
    while True:
        results = search(items, query)
        selected = min(selected, max(len(results) - 1, 0))
        draw(query, results, selected, error)
        key, error = read_input(), ""
        if key in CLOSE_KEYS:
            return
        if key in ("\r", "\n"):
            if results:
                try:
                    results[selected]["run"]()
                    return
                except Exception as e:  # e.g. the pane was closed meanwhile
                    error = f"\033[31m✗ {e}{RESET}"
        elif key in UP_KEYS:
            selected = max(selected - 1, 0)
        elif key in DOWN_KEYS:
            selected = min(selected + 1, max(len(results) - 1, 0))
        elif key in ("\x7f", "\x08"):
            query, selected = query[:-1], 0
        elif key == "\x15":  # ctrl+u
            query, selected = "", 0
        elif key.isprintable():  # may be several chars when typing fast or pasting
            query, selected = query + key, 0


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
