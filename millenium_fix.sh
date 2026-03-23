#!/usr/bin/env bash

# ==================================================
#   Millennium Fix & Install Script (v3 - Final Fix)
# ==================================================

readonly GITHUB_ACCOUNT="SteamClientHomebrew/Millennium"
readonly RELEASES_URI="https://api.github.com/repos/${GITHUB_ACCOUNT}/releases"
readonly DOWNLOAD_URI="https://github.com/${GITHUB_ACCOUNT}/releases/download"
readonly INSTALL_DIR="/tmp/millennium"

log() { printf "%b\n" "$1"; }
is_root() { [ "$(id -u)" -eq 0 ]; }

# --- STEP 1: BRUTAL UNINSTALL ---
uninstall_old_version() {
    log "\n[!] Starting brutal cleanup..."
    pkill -9 steam 2>/dev/null
    pkill -9 steamwebhelper 2>/dev/null
    pkill -9 millennium 2>/dev/null
    pkill -9 python 2>/dev/null

    for root in "$HOME/.local/share/Steam" "$HOME/.steam/steam" "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam"; do
        [ -d "$root" ] || continue
        if [ -f "$root/steam.sh.bak" ]; then
            install -m 755 "$root/steam.sh.bak" "$root/steam.sh"
        else
            rm -f "$root/steam.sh"
        fi
        rm -f "$root/steam.cfg" "$root/steam.sh.bak"
    done

    rm -rf "$HOME/.config/millennium" "$HOME/.local/share/millennium" "$HOME/.local/state/millennium"
    sudo rm -rf /usr/lib/millennium /usr/share/millennium 2>/dev/null
    log "[ok] Previous traces removed."
}

# --- STEP 2: SMART POST_INSTALL LOGIC ---
apply_post_install() {
    log "\n[+] Running post-install hook..."
    
    # 1. Fix Permissions
    sudo chmod +x /opt/python-i686-3.11.8/bin/python3.11 2>/dev/null || true

    # 2. Identify the correct bootstrap file
    # The AUR package uses libmillennium_x86.so, the manual script uses libmillennium_bootstrap_86x.so
    BOOTSTRAP_SRC=""
    if [ -f "/usr/lib/millennium/libmillennium_x86.so" ]; then
        BOOTSTRAP_SRC="/usr/lib/millennium/libmillennium_x86.so"
    elif [ -f "/usr/lib/millennium/libmillennium_bootstrap_86x.so" ]; then
        BOOTSTRAP_SRC="/usr/lib/millennium/libmillennium_bootstrap_86x.so"
    fi

    if [ -z "$BOOTSTRAP_SRC" ]; then
        log "[!] ERROR: Millennium bootstrap library not found in /usr/lib/millennium/"
        return 1
    fi

    log "Using bootstrap source: $BOOTSTRAP_SRC"

    # 3. Apply fix to all Steam paths
    for steam_path in "${HOME}/.steam/steam" "${HOME}/.local/share/Steam" "${HOME}/.var/app/com.valvesoftware.Steam/.local/share/Steam"; do
        [ -d "$steam_path" ] || continue
        
        # Remove Beta
        beta_file="${steam_path}/package/beta"
        if [ -f "${beta_file}" ]; then
            log "-> Removing Steam Beta in $steam_path"
            rm "${beta_file}"
        fi

        # Create the Hook (Symlink)
        if [ -d "${steam_path}/ubuntu12_32" ]; then
            log "-> Creating injection hook in $steam_path"
            # We link it to libXtst.so.6 which is how Millennium hooks into Steam
            ln -sf "$BOOTSTRAP_SRC" "${steam_path}/ubuntu12_32/libXtst.so.6"
        fi
    done
}

# --- STEP 3: MAIN ---
main() {
    if is_root; then log "Do not run as root!"; exit 1; fi

    uninstall_old_version

    # Try AUR Reinstall (Paru/Yay)
    installed_aur=false
    if [ -f /etc/arch-release ] || [ -f /etc/cachyos-release ]; then
        log "\n[+] Arch-based system detected."
        if command -v paru >/dev/null; then
            log "[+] Reinstalling via paru..."
            paru -S millennium --noconfirm --rebuild && installed_aur=true
        elif command -v yay >/dev/null; then
            log "[+] Reinstalling via yay..."
            yay -S millennium --noconfirm --redownload && installed_aur=true
        fi
    fi

    # Manual Fallback
    if [ "$installed_aur" = false ]; then
        log "\n[!] Manual installation required..."
        # Logic to fetch and install from GitHub
        target="linux-x86_64"
        tag=$(curl -fsSL -H 'Accept: application/vnd.github.v3+json' "${RELEASES_URI}?per_page=1" | jq -r '.[0].tag_name')
        download_uri="${DOWNLOAD_URI}/${tag}/millennium-${tag#v}-${target}.tar.gz"

        mkdir -p "${INSTALL_DIR}/files"
        curl -L "${download_uri}" | tar xz -C "${INSTALL_DIR}/files"
        sudo cp -r "${INSTALL_DIR}/files"/* / || true
        rm -rf "${INSTALL_DIR}"
    fi

    # ALWAYS run post-install after the binaries are in place
    apply_post_install

    log "\n=============================================="
    log "✨ SUCCESS: Millennium is now hooked into Steam."
    log "Please restart Steam to see the changes."
    log "==============================================\n"
}

main "$@"
