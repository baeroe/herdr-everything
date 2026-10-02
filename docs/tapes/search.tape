# Search everywhere with a query that hits every kind (ctrl+b e in the demo config, alt+space in the README).
Output ".vhs/search.gif"
Source "docs/tapes/config.tape"

Hide
Type '"$HERDR_DEMO" herdr' Enter
Sleep 4s
Type "clear; ls" Enter
Sleep 1s
Ctrl+B
Type "e"
Sleep 2s
Type "api"
Sleep 1s
Show
Sleep 300ms
Screenshot "docs/screenshots/search.png"
