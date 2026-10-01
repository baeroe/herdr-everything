# herdr-omni

herdr-Plugin im Stil von „Search Everywhere“ in JetBrains: **alt+space** öffnet ein Suchfeld, das über alles in herdr sucht. Den besten Treffer öffnest du mit **Enter**.

| Art | Enter macht |
|---|---|
| `agent` | Pane des Agents fokussieren |
| `space` | Workspace fokussieren |
| `tab` | Tab fokussieren |
| `pane` | Pane fokussieren (Titel = Ordner) |
| `tool` | Toolbox-Tool direkt im Popup starten (nur wenn das Plugin `herdr-toolbox` installiert ist) |
| `action` | Aktion eines installierten Plugins ausführen (lazydocker, Birdseye, …) |

Suche: unscharf und wortweise, z. B. `rand`, `shop front`, `docker`. Treffer im Titel zählen doppelt.

Tasten: **↑↓** oder **ctrl+p/n** wählen · **Enter** öffnen · **ctrl+u** Suche leeren · **Esc / alt+space** schließen.

Voraussetzungen: `python3` (nur Standardbibliothek). Toolbox-Einträge erscheinen nur, wenn ein Plugin `herdr-toolbox` mit `toolbox.py --list` installiert ist; sonst fehlen sie einfach.

## Installation

```sh
git clone https://github.com/baeroe/herdr-omni
herdr plugin link ./herdr-omni
```

`~/.config/herdr/config.toml`:

```toml
[[keys.command]]
key = "alt+space"
type = "plugin_action"
command = "herdr-omni.open"
description = "omni"
```

Danach `herdr server reload-config`.

Zweimal Shift geht nicht: Ein Terminal bekommt reine Shift-Drücke gar nicht mit. Das ginge nur über ein macOS-Tool wie Karabiner-Elements, das zweimal Shift auf alt+space umleitet.

## Tests

```sh
python3 test_search.py   # Suche, ohne herdr (läuft auch in CI)
python3 test_omni.py     # Bedienung im Pseudo-Terminal gegen einen laufenden herdr
```

## Lizenz

MIT, siehe [LICENSE](LICENSE).
