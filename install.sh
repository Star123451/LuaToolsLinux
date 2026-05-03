#!/usr/bin/env bash
set -euo pipefail

SELF_REPO_BASE="https://raw.githubusercontent.com/Star123451/LuaToolsLinux/main"
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

ask_headcrab() {
	echo ""
	info "Optional: Do you want to run headcrab?"
	info "(Recommended to run if you haven't already)"
	echo ""
	local response=""
	if [[ -r /dev/tty ]]; then
		printf "Run headcrab? [y/N]: " > /dev/tty
		IFS= read -r response < /dev/tty || true
	elif [[ -t 0 ]]; then
		printf "Run headcrab? [y/N]: "
		IFS= read -r response || true
	else
		warn "No interactive TTY available. Skipping headcrab question."
		return
	fi
	response="${response//[[:space:]]/}"
	case "$response" in
		y|Y|yes|YES) 
			info "Running headcrab..."
			curl -fsSL https://raw.githubusercontent.com/ciscosweater/enter-the-wired/main/enter-the-wired | bash || warn "Headcrab installation failed or was interrupted."
			ok "Headcrab completed."
			;;
		*) info "Skipping headcrab." ;;
	esac
}

ask_millennium() {
	echo ""
	info "Required: Do you want to run the Millennium installer?"
	info "(required for use of LuaToolsLinux, say Yes if you haven't installed it yet)"
	echo ""
	local response=""
	if [[ -r /dev/tty ]]; then
		printf "Run Millennium installer? [y/N]: " > /dev/tty
		IFS= read -r response < /dev/tty || true
	elif [[ -t 0 ]]; then
		printf "Run Millennium installer? [y/N]: "
		IFS= read -r response || true
	else
		warn "No interactive TTY available. Skipping Millennium installer question."
		return
	fi
	response="${response//[[:space:]]/}"
	case "$response" in
		y|Y|yes|YES) 
			info "Running Millennium installer..."
			curl -fsSL https://raw.githubusercontent.com/SteamClientHomebrew/Millennium/main/scripts/install.sh | bash || warn "Millennium installation failed or was interrupted."
			ok "Millennium installer completed."
			;;
		*) warn "Skipping Millennium installer. LuaToolsLinux requires Millennium."; return 1 ;;
	esac
}

uninstall_all_flow() {
    info "Uninstalling everything..."
    
    # 1. Cleanup Millennium (Option 1)
    info "Removing Millennium Framework files..."
    sudo rm -rf /usr/lib/millennium \
                /usr/share/millennium \
                "${XDG_CONFIG_HOME:-$HOME/.config}/millennium" \
                "${XDG_DATA_HOME:-$HOME/.local/share}/millennium"

    # Restore Steam Binary
    if [ -f "/usr/bin/steam.millennium.bak" ]; then
        info "Restoring original Steam executable..."
        sudo mv /usr/bin/steam.millennium.bak /usr/bin/steam
    fi

    # Remove symlink hooks
    info "Removing preloader hooks..."
    rm -f "${HOME}/.steam/steam/ubuntu12_32/libXtst.so.6"
    
    # 2. Cleanup Standalone/Experimental (Option 2)
    # Removing typical LuaTools/SLS paths
    info "Removing LuaTools Standalone/Experimental components..."
    rm -rf "${XDG_DATA_HOME:-$HOME/.local/share}/luatools" \
           "${XDG_CONFIG_HOME:-$HOME/.config}/luatools" \
           "${HOME}/.luatools" 2>/dev/null || true

    ok "Uninstall finished. Your system is clean."
}

install_millennium_flow() {
	ask_headcrab
	ask_millennium || fail "Millennium is required for LuaToolsLinux installation."

	info "Installing Millennium framework (Versão Fixa 2.35.0 + Limpeza)..."

	cat << 'EOF' > /tmp/millennium_v235_installer.sh
#!/usr/bin/env bash

readonly GITHUB_ACCOUNT="SteamClientHomebrew/Millennium"
readonly RELEASES_URI="https://api.github.com/repos/${GITHUB_ACCOUNT}/releases"
readonly DOWNLOAD_URI="https://github.com/${GITHUB_ACCOUNT}/releases/download"
readonly INSTALL_DIR="/tmp/millennium"
DRY_RUN=0
ALLOW_BETA=0

log() { printf "%b\n" "$1"; }
is_root() { [ "$(id -u)" -eq 0 ]; }
format_size() {
    echo "$1" | awk '{ split("B KB MB GB TB PB", v); s=1; while ($1 > 1024) { $1 /= 1024; s++ } printf "%.2f %s\n", $1, v[s] }'
}

verify_platform() {
    case $(uname -sm) in
        "Linux x86_64") echo "linux-x86_64" ;;
        *) log "Unsupported platform $(uname -sm). x86_64 is the only available platform."; exit 1 ;;
    esac
}

check_dependencies() {
    log "resolving dependencies..."
    for cmd in curl tar jq sudo; do
        command -v "${cmd}" >/dev/null || {
            log "${cmd} isn't installed. Install it from your package manager." >&2
            exit 1
        }
    done
}

fetch_release_info() {
    echo "2.35.0:35546112"
    return 0
}

remove_old_installation() {
    log ":: Cleaning up previous Millennium installations..."
    sudo rm -rf /usr/lib/millennium \
                /usr/share/millennium \
                "${XDG_CONFIG_HOME:-$HOME/.config}/millennium" \
                "${XDG_DATA_HOME:-$HOME/.local/share}/millennium"

    if [ -f "/usr/bin/steam.millennium.bak" ]; then
        log "   Restoring original steam executable..."
        sudo mv /usr/bin/steam.millennium.bak /usr/bin/steam
    fi
}

download_package() {
    local url="$1"
    local dest="$2"
    curl --fail --location --output "${dest}" "${url}"
}

extract_package() {
    local tar_file="$1"
    local extract_dir="$2"
    mkdir -p "${extract_dir}"
    tar xzf "${tar_file}" -C "${extract_dir}"
}

install_millennium() {
    local extract_path="$1"
    sudo cp -r "${extract_path}"/* / || true
}

post_install() {
    [ -f /opt/python-i686-3.11.8/bin/python3.11 ] && sudo chmod +x /opt/python-i686-3.11.8/bin/python3.11
    log "installing for '${USER}'"
    beta_file="${HOME}/.steam/steam/package/beta"
    target="${HOME}/.steam/steam/ubuntu12_32/libXtst.so.6"
    if [ -f "${beta_file}" ]; then
        log "removing beta '$(cat "${beta_file}")' in favor for stable."
        rm "${beta_file}"
    fi
    [ -d "${HOME}/.steam/steam/ubuntu12_32" ] && ln -sf /usr/lib/millennium/libmillennium_bootstrap_86x.so "${target}"
}

cleanup() {
    local dir="$1"
    log "cleaning up temporary files..."
    rm -rf "${dir}"
}

main() {
    local target release_info tag size download_uri install_dir extract_path tar_file
    if is_root; then log "Do not run as root!"; exit 1; fi
    target=$(verify_platform)
    check_dependencies
    release_info=$(fetch_release_info)
    tag="${release_info%%:*}"
    download_uri="${DOWNLOAD_URI}/v${tag}/millennium-v${tag}-${target}.tar.gz"
    remove_old_installation
    install_dir="${INSTALL_DIR}"
    extract_path="${install_dir}/files"
    tar_file="${install_dir}/millennium-v${tag}-${target}.tar.gz"
    rm -rf "${install_dir}"
    mkdir -p "${install_dir}"
    log "Downloading package..."
    download_package "${download_uri}" "${tar_file}"
    log "Unpacking..."
    extract_package "${tar_file}" "${extract_path}"
    log "Installing..."
    install_millennium "${extract_path}"
    log "Post-install..."
    post_install
    cleanup "${install_dir}"
    log "Millennium 2.35.0 base install done.\n"
}
main "$@"
EOF

	bash /tmp/millennium_v235_installer.sh
	rm /tmp/millennium_v235_installer.sh

	info "Installing LuaTools Millennium plugin..."
	run_remote_script "$LUATOOLS_MILLENNIUM_URL"

	ok "Millennium + LuaTools plugin install finished."
}



print_help() {
	cat <<'EOF'
Usage: install.sh [option]

Options:
	1, --millennium      Install Millennium + LuaTools plugin
	2, --uninstall       Uninstall everything (Millennium & Standalone)
	3, --cancel          Exit without installing
  -h, --help           Show this help

EOF
}

interactive_menu() {
	echo ""
	echo -e "${BOLD}LuaTools Installer${NC}"
	echo "1) Millennium (v2.35.0 + Cleanup) + LuaTools plugin"
	echo "2) Uninstall Everything (Full Cleanup)"
	echo "3) Cancel"
	echo ""
	local choice=""
	if [[ -r /dev/tty ]]; then
		printf "Choose an option [1-3]: " > /dev/tty
		IFS= read -r choice < /dev/tty || true
	elif [[ -t 0 ]]; then
		printf "Choose an option [1-3]: "
		IFS= read -r choice || true
	else
		fail "No interactive TTY available."
	fi
	choice="${choice//[[:space:]]/}"
	case "$choice" in
		1) install_millennium_flow ;;
		2) uninstall_all_flow ;;
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
		2|--uninstall)
			uninstall_all_flow
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
}

main "${1:-}"
