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

install_millennium_flow() {
	info "Installing Millennium framework (Versão Fixa 2.35.0 + Limpeza)..."

	# Embutimos o script modificado do Millennium aqui dentro usando cat << 'EOF'
	# Assim você não depende de links externos.
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

# Força a versão 2.35.0
fetch_release_info() {
    echo "2.35.0:35546112"
    return 0
}

# Limpeza das versões anteriores
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
    if ! curl --fail --location --output "${dest}" "${url}"; then
        log "Download failed for ${url}"
        return 1
    fi
}

extract_package() {
    local tar_file="$1"
    local extract_dir="$2"
    mkdir -p "${extract_dir}"
    tar xzf "${tar_file}" -C "${extract_dir}"
}

install_millennium() {
    local extract_path="$1"
    if [ "${DRY_RUN}" -eq 0 ]; then
        sudo cp -r "${extract_path}"/* / || true
    else
        log "[DRY RUN] Would copy files from ${extract_path} to /"
    fi
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

    for arg in "$@"; do
        case ${arg} in
            --dry-run) DRY_RUN=1; shift ;;
            --beta) ALLOW_BETA=1; shift ;;
        esac
    done

    if is_root; then
        log "Do not run this script as root!"
        exit 1
    fi

    target=$(verify_platform)
    check_dependencies

    release_info=$(fetch_release_info)
    tag="${release_info%%:*}"
    size=$(format_size "${release_info##*:}")

    install_size_uri="${DOWNLOAD_URI}/v${tag}/millennium-v${tag}-${target}.installsize"
    download_uri="${DOWNLOAD_URI}/v${tag}/millennium-v${tag}-${target}.tar.gz"
    sha256_uri="${DOWNLOAD_URI}/v${tag}/millennium-v${tag}-${target}.sha256"

    sha256digest=$(curl -sL "${sha256_uri}")
    installed_size=$(format_size "$(curl -sL "${install_size_uri}")")

    log "\nPackages (1) millennium@${tag}-x86_64\n"
    
    # Executa a limpeza
    remove_old_installation

    log "receiving packages..."

    install_dir="${DRY_RUN:+./dry-run}"
    install_dir="${install_dir:-${INSTALL_DIR}}"
    extract_path="${install_dir}/files"
    tar_file="${install_dir}/millennium-v${tag}-${target}.tar.gz"

    rm -rf "${install_dir}"
    mkdir -p "${install_dir}"

    log "(1/4) Downloading millennium-v${tag}-${target}.tar.gz..."
    download_package "${download_uri}" "${tar_file}"
    
    log "(2/4) Verifying checksums..."
    if (cd "${install_dir}" && echo "${sha256digest}" | sha256sum -c --status); then
        echo -ne "\033[1A"
        log "(2/4) Verifying checksums... OK"
    else
        log "(2/4) Verifying checksums... FAILED"
    fi
    
    log "(3/4) Unpacking millennium-v${tag}-${target}.tar.gz..."
    extract_package "${tar_file}" "${extract_path}"
    
    log "(4/4) Installing millennium..."
    install_millennium "${extract_path}"

    log ":: Running post-install scripts..."
    log "(1/1) Setting up shared object preloader hook..."
    post_install

    cleanup "${install_dir}"

    log "Millennium 2.35.0 base install done.\n"
}

main "$@"
EOF

	# Executa o script que acabamos de gerar no /tmp
	bash /tmp/millennium_v235_installer.sh
	
	# Deleta o arquivo pra manter a máquina limpa
	rm /tmp/millennium_v235_installer.sh

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
	echo "1) Millennium (v2.35.0 + Cleanup) + LuaTools plugin"
	echo "2) (EXPERIMENTAL!) Non-Millennium (SLSsteam/ACCELA + LuaTools standalone)"
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
