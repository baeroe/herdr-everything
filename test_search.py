"""Checks search ranking without a running herdr (runs in CI). Usage: python3 test_search.py"""
import importlib.util

spec = importlib.util.spec_from_file_location("omni", "omni.py")
omni = importlib.util.module_from_spec(spec)
spec.loader.exec_module(omni)

noop = lambda: None
items = [
    omni.entry("agent", "Fix checkout bug", "claude · idle · shop › backend", noop),
    omni.entry("space", "shop", "2 tabs · 3 panes", noop),
    omni.entry("tab", "frontend", "shop › frontend", noop),
    omni.entry("pane", "~/dev/shop", "shop › frontend", noop),
    omni.entry("tool", "Random String", "Toolbox", noop, "random string password"),
    omni.entry("tool", "Format JSON", "Toolbox", noop, "json format pretty"),
    omni.entry("action", "Open lazydocker", "Lazydocker", noop),
]
top = lambda q: omni.search(items, q)[0]["title"]

assert top("rand") == "Random String"
assert top("json") == "Format JSON"
assert top("pretty") == "Format JSON"  # match via keywords
assert top("lazy") == "Open lazydocker"
assert top("checkout") == "Fix checkout bug"
assert top("shop front") == "frontend"  # several words, title match wins
assert top("rdmstr") == "Random String"  # fuzzy: letters in order
assert omni.search(items, "zzzqqq") == []
assert len(omni.search(items, "")) == len(items)  # empty query shows everything
print("ok")
