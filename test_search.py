"""Checks search ranking without a running herdr (runs in CI). Usage: python3 test_search.py"""
import importlib.util

spec = importlib.util.spec_from_file_location("everything", "everything.py")
everything = importlib.util.module_from_spec(spec)
spec.loader.exec_module(everything)

noop = lambda: None
items = [
    everything.entry("agent", "Fix checkout bug", "claude · idle · shop › backend", noop),
    everything.entry("space", "shop", "2 tabs · 3 panes", noop),
    everything.entry("tab", "frontend", "shop › frontend", noop),
    everything.entry("pane", "~/dev/shop", "shop › frontend", noop),
    everything.entry("tool", "Random String", "Toolbox", noop, "random string password"),
    everything.entry("tool", "Format JSON", "Toolbox", noop, "json format pretty"),
    everything.entry("action", "Open lazydocker", "Lazydocker", noop),
]
items += everything.commands({"pane_id": "w:p", "tab_id": "w:t", "workspace_id": "w", "cwd": "/tmp"},
                             {"label": "shop"}, {"label": "frontend"})
top = lambda q: everything.search(items, q)[0]["title"]

assert top("rand") == "Random String"
assert top("json") == "Format JSON"
assert top("pretty") == "Format JSON"  # match via keywords
assert top("lazy") == "Open lazydocker"
assert top("checkout") == "Fix checkout bug"
assert top("shop front") == "frontend"  # several words, title match wins
assert top("rdmstr") == "Random String"  # fuzzy: letters in order
assert everything.search(items, "zzzqqq") == []
assert len(everything.search(items, "")) == len(items)  # empty query shows everything
assert top("new tab") == "New tab"
assert top("split right") == "Split pane right"
assert top("rename tab") == "Rename tab"
assert top("close pane") == "Close pane"
assert top("worktree") == "New worktree"
cmds = {i["title"]: i for i in items if i["kind"] == "cmd"}
assert cmds["Close workspace"]["confirm"] and cmds["Rename pane"]["ask"]  # destructive asks, renames prompt
# line editing: backspace, alt+backspace (ESC prefix and kitty), ctrl+w, ctrl+u
assert everything.edit("foo bar", "\x7f") == "foo ba"
assert everything.edit("foo bar", "\x1b\x7f") == "foo "
assert everything.edit("foo bar ", "\x1b[127;3u") == "foo "
assert everything.edit("foo", "\x17") == ""
assert everything.edit("foo bar", "\x15") == ""
assert everything.edit("foo", "\x1b[A") is None  # arrows are not edits
print("ok")
