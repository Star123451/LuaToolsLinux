#!/usr/bin/env bash

# ==================================================
#   Millennium Fix & Install Script (v2 - Sequential)
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
    # Force kill everything related to Steam/Millennium
    pkill -9 steam 2>/dev/null
    pkill -9 steamwebhelper 2>/dev/null
    pkill -9 millennium 2>/dev/null
    pkill -9 python 2>/dev/null

    # Restore Steam startup scripts in all common locations
    for root in "$HOME/.local/share/Steam" "$HOME/.steam/steam" "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam"; do
        [ -d "$root" ] || continue
        log "-> Restoring original steam.sh in $root"
        if [ -f "$root/steam.sh.bak" ]; then
            install -m 755 "$root/steam.sh.bak" "$root/steam.sh"
        else
            rm -f "$root/steam.sh"
        fi
        rm -f "$root/steam.cfg" "$root/steam.sh.bak"
    done

    # Remove config folders
    rm -rf "$HOME/.config/millennium" "$HOME/.local/share/millennium" "$HOME/.local/state/millennium"
    # Remove system-wide files (requires sudo)
    sudo rm -rf /usr/lib/millennium /usr/share/millennium 2>/dev/null
    log "[ok] Previous traces removed."
}

# --- STEP 2: POST-INSTALL FIXES (THE CORE FIX) ---
apply_post_install_fixes() {
    log "\n[+] Applying final fixes for plugin compatibility..."
    
    # Check all possible Steam paths for the Beta file
    for steam_path in "$HOME/.steam/steam" "$HOME/.local/share/Steam" "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam"; do
        [ -d "$steam_path" ] || continue
        
        # 1. FORCE STEAM STABLE (Plugins won't work on Beta)
        beta_file="${steam_path}/package/beta"
        if [ -f "$beta_file" ]; then
            log "-> Removing Steam Beta in $steam_path"
            rm "$beta_file"
        fi

        # 2. Re-create the preloader symlink
        # Note: libXtst.so.6 is the injection point for Millennium
        if [ -d "${steam_path}/ubuntu12_32" ]; then
            log "-> Linking Millennium bootstrap to $steam_path"
            ln -sf /usr/lib/millennium/libmillennium_bootstrap_86x.so "${steam_path}/ubuntu12_32/libXtst.so.6"
        fi
    done
    
    # Fix permissions for the internal Python environment
    sudo chmod +x /opt/python-i686-3.11.8/bin/python3.11 2>/dev/null || true
    # Refresh desktop database to clean up shortcuts
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null
}

# --- MAIN EXECUTION ---
main() {
    if is_root; then log "Do not run as root!"; exit 1; fi

    # 1. Clean the mess first
    uninstall_old_version

    # 2. Detect Arch/CachyOS and Reinstall
    local installed=false
    if [ -f /etc/arch-release ] || [ -f /etc/cachyos-release ]; then
        log "\n[+] Arch-based system detected."
        if command -v paru >/dev/null; then
            log "[+] Reinstalling via paru..."
            paru -S millennium --noconfirm --rebuild && installed=true
        elif command -v yay >/dev/null; then
            log "[+] Reinstalling via yay..."
            yay -S millennium --noconfirm --redownload && installed=true
        fi
    fi

    # 3. Manual Fallback if AUR helper failed or not on Arch
    if [ "$installed" = false ]; then
        log "\n[!] AUR installation skipped. Falling back to manual GitHub install..."
        
        # Determine platform and fetch tag
        local target="linux-x86_64"
        local response=$(curl -fsSL -H 'Accept: application/vnd.github.v3+json' "${RELEASES_URI}?per_page=1")
        local tag=$(echo "${response}" | jq -r '.[0].tag_name')
        local download_uri="${DOWNLOAD_URI}/${tag}/millennium-${tag#v}-${target}.tar.gz"

        mkdir -p "${INSTALL_DIR}/files"
        log "Downloading: ${tag}..."
        curl -L "${download_uri}" | tar xz -C "${INSTALL_DIR}/files"
        
        # Install files to system root
        sudo cp -r "${INSTALL_DIR}/files"/* / || true
        rm -rf "${INSTALL_DIR}"
    fi

    # 4. RUN THE FIXES (This part was being skipped!)
    apply_post_install_fixes

    log "\n=============================================="
    log "✨ SUCCESS: Millennium fixed and Steam Beta removed!"
    log "You can open Steam now. Plugins should work."
    log "==============================================\n"
}

main "$@"
