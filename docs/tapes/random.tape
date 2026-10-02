# The random string tool with symbols on and 40 characters, opened from the tools menu.
Output ".vhs/random.gif"
Source "docs/tapes/config.tape"

Hide
Type '"$HERDR_DEMO" herdr' Enter
Sleep 4s
Type "clear; ls" Enter
Sleep 1s
Ctrl+B
Type "t"
Sleep 2s
Type "r"
Sleep 500ms
Type "s"
Sleep 300ms
Type "40"
Sleep 1s
Show
Sleep 300ms
Screenshot "docs/screenshots/random.png"
