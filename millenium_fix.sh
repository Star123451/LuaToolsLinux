#!/usr/bin/env bash

# ==================================================
#   Millennium Fix & Install Script (Aggressive)
# ==================================================

# --- ORIGINAL CONFIGURATION ---
readonly GITHUB_ACCOUNT="SteamClientHomebrew/Millennium"
readonly RELEASES_URI="https://api.github.com/repos/${GITHUB_ACCOUNT}/releases"
readonly DOWNLOAD_URI="https://github.com/${GITHUB_ACCOUNT}/releases/download"
readonly INSTALL_DIR="/tmp/millennium"
DRY_RUN=0

log() { printf "%b\n" "$1"; }
is_root() { [ "$(id -u)" -eq 0 ]; }

# --- STEP 1: BRUTAL UNINSTALL (CLEANUP) ---
uninstall_old_version() {
    log "\n[!] Starting brutal cleanup of previous installation..."

    # 1. Kill Steam processes
    pkill -x steam 2>/dev/null; pkill -f steamwebhelper 2>/dev/null;

    # 2. Restore Steam original startup scripts
    for root in "$HOME/.local/share/Steam" "$HOME/.steam/steam" "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam"; do
        [ -d "$root" ] || continue;
        if [ -f "$root/steam.sh.bak" ]; then
            install -m 755 "$root/steam.sh.bak" "$root/steam.sh";
        else
            rm -f "$root/steam.sh";
        fi;
        rm -f "$root/steam.cfg" "$root/steam.sh.bak";
    done;

    # 3. Remove Millennium specific folders
    rm -rf "$HOME/.config/millennium" "$HOME/.local/share/millennium" "$HOME/.local/state/millennium"

    # 4. Remove System files (requires sudo)
    sudo rm -rf /usr/lib/millennium /usr/share/millennium 2>/dev/null
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null

    log "[ok] Previous traces removed."
}

# --- STEP 2: DETECT ARCH/CACHYOS AND FORCE REINSTALL ---
try_package_manager() {
    if [ -f /etc/arch-release ] || [ -f /etc/cachyos-release ]; then
        log "\n[+] Arch-based system detected."

        # We use --rebuild/--redownload to force a fresh install even if already "installed"
        if command -v paru >/dev/null; then
            log "[+] Force reinstalling via paru..."
            paru -S millennium --noconfirm --rebuild
            exit 0
        elif command -v yay >/dev/null; then
            log "[+] Force reinstalling via yay..."
            yay -S millennium --noconfirm --redownload
            exit 0
        fi
    fi
    log "[!] No AUR helper found or not an Arch system. Proceeding with manual install..."
}

# --- HELPER FUNCTIONS ---
format_size() {
    echo "$1" | awk '{ split("B KB MB GB TB PB", v); s=1; while ($1 > 1024) { $1 /= 1024; s++ } printf "%.2f %s\n", $1, v[s] }'
}

verify_platform() {
    case $(uname -sm) in
        "Linux x86_64") echo "linux-x86_64" ;;
        *) log "Unsupported platform $(uname -sm)."; exit 1 ;;
    esac
}

check_dependencies() {
    log "Resolving dependencies..."
    for cmd in curl tar jq sudo; do
        command -v "${cmd}" >/dev/null || { log "${cmd} isn't installed."; exit 1; }
    done
}

fetch_release_info() {
    local response tag size
    response=$(curl -fsSL -H 'Accept: application/vnd.github.v3+json' "${RELEASES_URI}?per_page=1") || return 1
    tag=$(echo "${response}" | jq -r '.[0].tag_name')
    size=$(echo "${response}" | jq -r ".[0].assets[] | select(.name | contains(\"${target}\")) | .size" | head -n1)
    echo "${tag#v}:${size:-0}"
}

install_millennium() {
    local extract_path="$1"
    sudo cp -r "${extract_path}"/* / || true
}

post_install() {
    # Ensure permissions and symlinks
    sudo chmod +x /opt/python-i686-3.11.8/bin/python3.11 2>/dev/null || true
    target_link="${HOME}/.steam/steam/ubuntu12_32/libXtst.so.6"
    [ -d "${HOME}/.steam/steam/ubuntu12_32" ] && ln -sf /usr/lib/millennium/libmillennium_bootstrap_86x.so "${target_link}"
}

# --- MAIN EXECUTION ---
main() {
    if is_root; then log "Do not run as root!"; exit 1; fi

    # 1. Brutal Cleanup
    uninstall_old_version

    # 2. Try Package Manager (Paru/Yay) with Force
    try_package_manager

    # 3. Fallback: Manual GitHub Installation
    target=$(verify_platform)
    check_dependencies

    release_info=$(fetch_release_info)
    tag="${release_info%%:*}"
    download_uri="${DOWNLOAD_URI}/v${tag}/millennium-v${tag}-${target}.tar.gz"

    log "\n[+] Falling back to manual download: millennium@${tag}"
    mkdir -p "${INSTALL_DIR}/files"

    curl -L "${download_uri}" | tar xz -C "${INSTALL_DIR}/files"
    install_millennium "${INSTALL_DIR}/files"
    post_install

    rm -rf "${INSTALL_DIR}"
    log "\n[ok] Done. You can now start Steam."
}

main "$@"
