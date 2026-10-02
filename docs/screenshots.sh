#!/usr/bin/env bash
# Regenerates the README screenshots in docs/screenshots/ from the VHS tapes in docs/tapes/.
#
#   bash docs/screenshots.sh            # all tapes
#   bash docs/screenshots.sh search     # only docs/tapes/search.tape
#
# Needs herdr, jq, vhs (brew install vhs; pulls ttyd and ffmpeg), optionally pngquant/oxipng. If a checkout of
# https://github.com/baeroe/herdr-tussh sits next to this repo (override with TUSSH_PLUGIN), it is linked too, so
# the search shows actions of another plugin.
#
# Nothing touches your herdr: a separate herdr server runs with its own HOME in a throwaway sandbox (its own
# config, socket and sessions) with demo workspaces, and is stopped afterwards. No real agent runs: the agent
# entry is a plain shell pane that reports an agent state via `herdr pane report-agent`.
set -euo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
tussh_plugin=${TUSSH_PLUGIN:-$repo/../herdr-tussh}
herdr_bin=$(command -v herdr || echo "$HOME/.local/bin/herdr")
cd "$repo"

# short path: herdr's unix sockets live under $HOME/.config/herdr
sandbox=$(cd "$(mktemp -d /tmp/he.XXXXXX)" && pwd -P)
cleanup() {
	[ -x "$sandbox/env.sh" ] && "$sandbox/env.sh" herdr server stop >/dev/null 2>&1 || true
	rm -rf "$sandbox"
}
trap cleanup EXIT

home="$sandbox/h"
mkdir -p "$sandbox/bin" "$home/shop"/{src,frontend,tests} "$home/api"/{src,migrations} "$home/homelab"
touch "$home/shop"/{composer.json,composer.lock,docker-compose.yml,README.md} "$home/api"/{go.mod,go.sum,main.go,Makefile} \
	"$home/homelab"/{compose.yml,.env.example}
ln -s "$herdr_bin" "$sandbox/bin/herdr"

# the environment of the sandboxed herdr (server, panes and plugin commands inherit it)
cat >"$sandbox/env.sh" <<EOF
#!/bin/sh
cd "$home/shop"
exec env -i HOME="$home" PATH="$sandbox/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \\
	TERM=xterm-256color SHELL=/bin/zsh LANG=en_US.UTF-8 "\$@"
EOF
chmod +x "$sandbox/env.sh"
h() { "$sandbox/env.sh" herdr "$@"; }

mkdir -p "$home/.config/herdr"
cat >"$home/.config/herdr/config.toml" <<'EOF'
onboarding = false

[theme]
name = "dracula"

[update]
version_check = false
manifest_check = false

[[keys.command]]
key = "prefix+e"
type = "plugin_action"
command = "herdr-everything.open"
description = "everything"

[[keys.command]]
key = "prefix+t"
type = "plugin_action"
command = "herdr-everything.tools"
description = "tools"
EOF
# a neutral prompt for the shell panes
printf "PROMPT='%%F{cyan}%%~%%f %%F{magenta}❯%%f '\n" >"$home/.zshrc"

pane_of() { jq -r '.result.root_pane.pane_id'; }

# demo workspaces: shop (server split in two, tests), api (server, logs, an agent), homelab (docker)
seed() {
	local p t
	p=$(h workspace create --cwd "$home/homelab" --label homelab --no-focus | pane_of)
	h tab rename "${p%%:*}:t1" docker >/dev/null

	p=$(h workspace create --cwd "$home/api" --label api --no-focus | pane_of)
	t=${p%%:*}
	h tab rename "$t:t1" server >/dev/null
	h tab create --workspace "$t" --cwd "$home/api" --label logs --no-focus >/dev/null
	p=$(h tab create --workspace "$t" --cwd "$home/api/src" --label agent --no-focus | pane_of)
	h pane report-agent "$p" --source demo --agent claude --state working >/dev/null
	h pane run "$p" "printf '\\033]0;Add rate limiting to the API\\007'; clear" >/dev/null

	p=$(h workspace create --cwd "$home/shop" --label shop --focus | pane_of)
	t=${p%%:*}
	h tab rename "$t:t1" server >/dev/null
	h pane split "$p" --direction right --cwd "$home/shop/frontend" >/dev/null
	h tab create --workspace "$t" --cwd "$home/shop/tests" --label tests --no-focus >/dev/null
	h pane focus --pane "$p" --direction left >/dev/null 2>&1 || true
}

start_herdr() {
	"$sandbox/env.sh" herdr server >>"$sandbox/server.log" 2>&1 &
	for _ in $(seq 50); do
		h status server 2>/dev/null | grep -q 'status: running' && break
		sleep 0.2
	done
	h plugin link "$repo" >/dev/null
	[ -f "$tussh_plugin/herdr-plugin.toml" ] && h plugin link "$tussh_plugin" >/dev/null
	seed
}
stop_herdr() {
	h server stop >/dev/null 2>&1 || true
	rm -rf "$home/.config/herdr/session.json" "$home/.config/herdr/session-snapshots"
	sleep 1
}

export HERDR_DEMO="$sandbox/env.sh"
tapes=("$@")
if [ ${#tapes[@]} -eq 0 ]; then
	for f in docs/tapes/*.tape; do
		[ "$(basename "$f")" = config.tape ] || tapes+=("$(basename "$f" .tape)")
	done
fi
for t in "${tapes[@]}"; do
	echo "== $t"
	start_herdr # a fresh herdr session per tape
	vhs "docs/tapes/$t.tape"
	stop_herdr
done
rm -rf .vhs

cd docs/screenshots
command -v pngquant >/dev/null && pngquant --force --skip-if-larger --quality 80-95 --ext .png ./*.png || true
command -v oxipng >/dev/null && oxipng -q -o 4 --strip safe ./*.png || true
ls -lh
