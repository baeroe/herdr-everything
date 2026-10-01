"""Suche ohne laufenden herdr prüfen (läuft auch in CI). Aufruf: python3 test_search.py"""
import importlib.util

spec = importlib.util.spec_from_file_location("omni", "omni.py")
omni = importlib.util.module_from_spec(spec)
spec.loader.exec_module(omni)

noop = lambda: None
items = [
    omni.entry("agent", "Fix checkout bug", "claude · idle · shop › backend", noop),
    omni.entry("space", "shop", "2 Tabs · 3 Panes", noop),
    omni.entry("tab", "frontend", "shop › frontend", noop),
    omni.entry("pane", "~/dev/shop", "shop › frontend", noop),
    omni.entry("tool", "Random String", "Toolbox", noop, "random string password"),
    omni.entry("tool", "JSON formatieren", "Toolbox", noop, "json format pretty"),
    omni.entry("action", "Open lazydocker", "Lazydocker", noop),
]
top = lambda q: omni.search(items, q)[0]["title"]

assert top("rand") == "Random String"
assert top("json") == "JSON formatieren"
assert top("pretty") == "JSON formatieren"  # Treffer über Keywords
assert top("lazy") == "Open lazydocker"
assert top("checkout") == "Fix checkout bug"
assert top("shop front") == "frontend"  # mehrere Wörter, Titel-Treffer gewinnt
assert top("rdmstr") == "Random String"  # unscharf: Buchstaben in Reihenfolge
assert omni.search(items, "zzzqqq") == []
assert len(omni.search(items, "")) == len(items)  # leere Suche zeigt alles
print("ok")
