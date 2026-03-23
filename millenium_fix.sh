#!/usr/bin/env bash

# ==================================================
#   _____ _ _ _             _
#  |     |_| | |___ ___ ___|_|_ _ _____
#  | | | | | | | -_|   |   | | | |     |
#  |_|_|_|_|_|_|___|_|_|_|_|_|___|_|_|_|
#
# ==================================================
#   Millennium Fix & Install Script (Official Logic)
# ==================================================

readonly GITHUB_ACCOUNT="SteamClientHomebrew/Millennium"
readonly RELEASES_URI="https://api.github.com/repos/${GITHUB_ACCOUNT}/releases"
readonly DOWNLOAD_URI="https://github.com/${GITHUB_ACCOUNT}/releases/download"
readonly INSTALL_DIR="/tmp/millennium"

log() { printf "%b\n" "$1"; }
is_root() { [ "$(id -u)" -eq 0 ]; }

# --- STEP 1: THE BRUTAL CLEANUP (FIRST STEP) ---
uninstall_brutal() {
    log "\n[!] Starting brutal cleanup..."
    
    # Kill all related processes
    pkill -9 steam 2>/dev/null
    pkill -9 steamwebhelper 2>/dev/null
    pkill -9 millennium 2>/dev/null
    pkill -9 python 2>/dev/null

    # Restore Steam startup scripts in all common locations
    for root in "$HOME/.local/share/Steam" "$HOME/.steam/steam" "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam"; do
        [ -d "$root" ] || continue
        log "-> Restoring steam.sh in $root"
        if [ -f "$root/steam.sh.bak" ]; then
            install -m 755 "$root/steam.sh.bak" "$root/steam.sh"
        else
            rm -f "$root/steam.sh"
        fi
        rm -f "$root/steam.cfg" "$root/steam.sh.bak"
    done

    # Remove Millennium data and system files
    rm -rf "$HOME/.config/millennium" "$HOME/.local/share/millennium" "$HOME/.local/state/millennium"
    sudo rm -rf /usr/lib/millennium /usr/share/millennium 2>/dev/null
    log "[ok] System is now clean."
}

# --- STEP 2: ORIGINAL POST_INSTALL LOGIC ---
post_install() {
    sudo chmod +x /opt/python-i686-3.11.8/bin/python3.11 2>/dev/null || true

    log "installing for '${USER}'"

    # Iterate through Steam paths to remove Beta and link the bootstrap
    for steam_path in "${HOME}/.steam/steam" "${HOME}/.local/share/Steam" "${HOME}/.var/app/com.valvesoftware.Steam/.local/share/Steam"; do
        [ -d "$steam_path" ] || continue
        
        beta_file="${steam_path}/package/beta"
        target="${steam_path}/ubuntu12_32/libXtst.so.6"

        # Force Steam Stable (Required for plugins)
        if [ -f "${beta_file}" ]; then
            log "removing beta '$(cat "${beta_file}")' in favor for stable."
            rm "${beta_file}"
        fi

        # Create symlink for millennium's preload bootstrap
        # Detects if it's the AUR version (x86.so) or Binary version (bootstrap_86x.so)
        if [ -d "${steam_path}/ubuntu12_32" ]; then
            if [ -f "/usr/lib/millennium/libmillennium_x86.so" ]; then
                ln -sf /usr/lib/millennium/libmillennium_x86.so "${target}"
            else
                ln -sf /usr/lib/millennium/libmillennium_bootstrap_86x.so "${target}"
            fi
        fi
    done
}

# --- STEP 3: MAIN INSTALLATION FLOW ---
main() {
    if is_root; then
        log "Do not run this script as root!"
        exit 1
    fi

    # ALWAYS start with the cleanup
    uninstall_brutal

    # Check for Arch/CachyOS (AUR version)
    installed_aur=false
    if [ -f /etc/arch-release ] || [ -f /etc/cachyos-release ]; then
        log "\n[+] Arch-based system detected."
        if command -v paru >/dev/null; then
            log "[+] Reinstalling millennium-git via paru..."
            paru -S millennium-git --noconfirm --rebuild && installed_aur=true
        elif command -v yay >/dev/null; then
            log "[+] Reinstalling millennium-git via yay..."
            yay -S millennium-git --noconfirm --redownload && installed_aur=true
        fi
    fi

    # Manual Fallback if not on Arch or AUR failed
    if [ "$installed_aur" = false ]; then
        log "\n[!] Using manual binary installation method..."
        target="linux-x86_64"
        release_info=$(curl -fsSL -H 'Accept: application/vnd.github.v3+json' "${RELEASES_URI}?per_page=1" | jq -r '.[0].tag_name')
        tag="${release_info#v}"
        download_uri="${DOWNLOAD_URI}/v${tag}/millennium-v${tag}-${target}.tar.gz"

        mkdir -p "${INSTALL_DIR}/files"
        curl -L "${download_uri}" | tar xz -C "${INSTALL_DIR}/files"
        sudo cp -r "${INSTALL_DIR}/files"/* / || true
        rm -rf "${INSTALL_DIR}"
    fi

    # Final logic (Beta removal and Hooks)
    log ":: Running post-install scripts..."
    post_install

    log "done.\n"
    log "You can now start Steam."
    log "https://docs.steambrew.app/users/installing#post-installation."
}

main "$@"
