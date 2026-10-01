# herdr-omni

A "Search Everywhere" popup for [herdr](https://herdr.dev), inspired by JetBrains IDEs. Press **alt+space**, type a few letters and hit **Enter** to jump to whatever is on top.

| Kind | Enter does |
|---|---|
| `agent` | Focus the agent's pane |
| `space` | Focus the workspace |
| `tab` | Focus the tab |
| `pane` | Focus the pane (titled by its directory) |
| `tool` | Run a toolbox tool inside the popup (only if a `herdr-toolbox` plugin is installed) |
| `action` | Invoke an action of any installed plugin (lazydocker, Birdseye, …) |

Search is fuzzy and word-based, e.g. `rand`, `shop front`, `docker`. Matches in the title count double.

Keys: **↑↓** or **ctrl+p/n** select · **Enter** open · **ctrl+u** clear · **Esc / alt+space** close.

Requirements: `python3` (standard library only). Toolbox entries only show up when a `herdr-toolbox` plugin providing `toolbox.py --list` is installed; otherwise they are simply left out.

## Install

```sh
herdr plugin install baeroe/herdr-omni
```

Add a key binding to `~/.config/herdr/config.toml`:

```toml
[[keys.command]]
key = "alt+space"
type = "plugin_action"
command = "herdr-omni.open"
description = "omni"
```

Then run `herdr server reload-config`.

Why not double-Shift like JetBrains? Terminals never see a bare Shift press. If you want it anyway, use a macOS tool such as Karabiner-Elements to map double-Shift to alt+space.

## Tests

```sh
python3 test_search.py   # search ranking, no herdr needed (runs in CI)
python3 test_omni.py     # drives the UI in a pseudo-terminal against a running herdr
```

## License

MIT, see [LICENSE](LICENSE).
