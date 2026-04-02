#!/usr/bin/env bash
set -euo pipefail

SELF_REPO_BASE="https://raw.githubusercontent.com/Star123451/LuaToolsLinux/main"
MILLENNIUM_INSTALL_URL="https://steambrew.app/install.sh"
LUATOOLS_MILLENNIUM_URL="$SELF_REPO_BASE/update.sh"
LUATOOLS_STANDALONE_URL="$SELF_REPO_BASE/install_with_slssteam.sh"
SLS_ACCELA_URL="https://raw.githubusercontent.com/ciscosweater/enter-the-wired/main/enter-the-wired"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

info() { echo -e "${CYAN}[INFO]${NC} $*"; }
ok() { echo -e "${GREEN}[ OK ]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

require_cmd() {
	command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

run_remote_script() {
	local url="$1"
	info "Running: $url"
	curl -fsSL "$url" | bash
}

install_millennium_flow() {
	info "Installing Millennium framework..."
	run_remote_script "$MILLENNIUM_INSTALL_URL"

	info "Installing LuaTools Millennium plugin..."
	run_remote_script "$LUATOOLS_MILLENNIUM_URL"

	ok "Millennium + LuaTools plugin install finished."
}

install_standalone_flow() {
	info "Installing SLSsteam + ACCELA prerequisites..."
	run_remote_script "$SLS_ACCELA_URL"

	info "Installing LuaTools standalone (non-Millennium)..."
	run_remote_script "$LUATOOLS_STANDALONE_URL"

	ok "SLSsteam/ACCELA + LuaTools standalone install finished."
}

print_help() {
	cat <<'EOF'
Usage: install.sh [option]

Options:
	1, --millennium      Install Millennium + LuaTools plugin
	2, --non-millennium  Install SLSsteam/ACCELA + LuaTools standalone
	3, --cancel          Exit without installing
  -h, --help          Show this help

If no option is provided, an interactive menu is shown.
EOF
}

interactive_menu() {
	echo ""
	echo -e "${BOLD}LuaTools Installer${NC}"
	echo "1) Millennium + LuaTools plugin"
	echo "2) Non-Millennium (SLSsteam/ACCELA + LuaTools standalone)"
	echo "3) Cancel"
	echo ""
	local choice=""
	if [[ -r /dev/tty ]]; then
		printf "Choose installation mode [1-3]: " > /dev/tty
		IFS= read -r choice < /dev/tty || true
	elif [[ -t 0 ]]; then
		printf "Choose installation mode [1-3]: "
		IFS= read -r choice || true
	else
		fail "No interactive TTY available. Re-run with --millennium or --non-millennium."
	fi
	choice="${choice//[[:space:]]/}"
	case "$choice" in
		1) install_millennium_flow ;;
		2) install_standalone_flow ;;
		3) info "Cancelled." ; exit 0 ;;
		*) fail "Invalid option: ${choice:-<empty>}" ;;
	esac
}

main() {
	require_cmd curl
	require_cmd bash

	case "${1:-}" in
		1|--millennium)
			install_millennium_flow
			;;
		2|--non-millennium)
			install_standalone_flow
			;;
		3|--cancel)
			info "Cancelled."
			exit 0
			;;
		-h|--help)
			print_help
			;;
		"")
			interactive_menu
			;;
		*)
			warn "Unknown argument: $1"
			print_help
			exit 1
			;;
	esac

	echo ""
	info "If you use ACCELA downloads, set your ACCELA path in LuaTools settings/flow."
}

main "${1:-}"
