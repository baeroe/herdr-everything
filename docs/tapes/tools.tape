# The tools menu (ctrl+b t in the demo config, alt+t in the README).
Output ".vhs/tools.gif"
Source "docs/tapes/config.tape"

Hide
Type '"$HERDR_DEMO" herdr' Enter
Sleep 4s
Type "clear; ls" Enter
Sleep 1s
Ctrl+B
Type "t"
Sleep 2s
Show
Sleep 300ms
Screenshot "docs/screenshots/tools.png"
