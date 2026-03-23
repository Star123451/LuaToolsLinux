#!/usr/bin/env bash

# ==================================================
#   Millennium Fix & Install Script (Final English)
# ==================================================

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

    # 2. Restore Steam original startup scripts across all possible locations
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

    # 4. Remove System files
    sudo rm -rf /usr/lib/millennium /usr/share/millennium 2>/dev/null
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null

    log "[ok] Previous traces removed."
}

# --- STEP 2: POST-INSTALL LOGIC (FORCING STABLE & SYMLINKS) ---
# This matches the original script's behavior to fix plugin issues
apply_post_install_fixes() {
    log ":: Running post-install scripts..."
    
    # 1. Ensure permissions for internal python
    sudo chmod +x /opt/python-i686-3.11.8/bin/python3.11 2>/dev/null || true

    log "Setting up environment for user: '${USER}'"

    # 2. FORCE STEAM STABLE (Crucial for plugins)
    # Checks common Steam installation paths
    for steam_path in "${HOME}/.steam/steam" "${HOME}/.local/share/Steam" "${HOME}/.var/app/com.valvesoftware.Steam/.local/share/Steam"; do
        beta_file="${steam_path}/package/beta"
        target_lib="${steam_path}/ubuntu12_32/libXtst.so.6"

        if [ -f "${beta_file}" ]; then
            log "Removing Steam Beta ('$(cat "${beta_file}")') to ensure plugin compatibility."
            rm "${beta_file}"
        fi

        # 3. Create symlink for millennium bootstrap
        if [ -d "${steam_path}/ubuntu12_32" ]; then
            log "Creating bootstrap symlink in ${steam_path}"
            ln -sf /usr/lib/millennium/libmillennium_bootstrap_86x.so "${target_lib}"
        fi
    done
}

# --- STEP 3: PACKAGE MANAGER LOGIC ---
try_package_manager() {
    if [ -f /etc/arch-release ] || [ -f /etc/cachyos-release ]; then
        log "\n[+] Arch-based system detected."

        if command -v paru >/dev/null; then
            log "[+] Force reinstalling via paru..."
            paru -S millennium --noconfirm --rebuild
            apply_post_install_fixes
            exit 0
        elif command -v yay >/dev/null; then
            log "[+] Force reinstalling via yay..."
            yay -S millennium --noconfirm --redownload
            apply_post_install_fixes
            exit 0
        fi
    fi
    log "[!] No AUR helper found. Proceeding with manual install..."
}

# --- STEP 4: MANUAL FALLBACK ---
verify_platform() {
    case $(uname -sm) in
        "Linux x86_64") echo "linux-x86_64" ;;
        *) log "Unsupported platform."; exit 1 ;;
    esac
}

fetch_release_info() {
    local response tag
    response=$(curl -fsSL -H 'Accept: application/vnd.github.v3+json' "${RELEASES_URI}?per_page=1") || return 1
    tag=$(echo "${response}" | jq -r '.[0].tag_name')
    echo "${tag#v}"
}

# --- MAIN ---
main() {
    if is_root; then log "Do not run as root!"; exit 1; fi

    # 1. Clear everything
    uninstall_old_version

    # 2. Try Paru/Yay first (with post-install fixes)
    try_package_manager

    # 3. Manual Fallback
    target=$(verify_platform)
    tag=$(fetch_release_info)
    download_uri="${DOWNLOAD_URI}/v${tag}/millennium-v${tag}-${target}.tar.gz"

    log "\n[+] Falling back to manual download: millennium@${tag}"
    mkdir -p "${INSTALL_DIR}/files"
    curl -L "${download_uri}" | tar xz -C "${INSTALL_DIR}/files"
    
    sudo cp -r "${INSTALL_DIR}/files"/* / || true
    apply_post_install_fixes
    
    rm -rf "${INSTALL_DIR}"
    log "\n[ok] Done. Millennium fixed and Steam Beta removed."
    log "You can now start Steam."
}

main "$@"
