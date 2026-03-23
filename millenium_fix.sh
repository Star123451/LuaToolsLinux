#!/usr/bin/env bash

# ==================================================
#   Millennium Fix & Install Script (Mirroring Original)
# ==================================================

readonly GITHUB_ACCOUNT="SteamClientHomebrew/Millennium"
readonly RELEASES_URI="https://api.github.com/repos/${GITHUB_ACCOUNT}/releases"
readonly DOWNLOAD_URI="https://github.com/${GITHUB_ACCOUNT}/releases/download"
readonly INSTALL_DIR="/tmp/millennium"

log() { printf "%b\n" "$1"; }
is_root() { [ "$(id -u)" -eq 0 ]; }

# --- STEP 1: BRUTAL UNINSTALL (YOUR ISOLATED CODE) ---
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

# --- STEP 2: ORIGINAL POST_INSTALL LOGIC ---
# Copied exactly from the official Millennium installer
apply_post_install() {
    sudo chmod +x /opt/python-i686-3.11.8/bin/python3.11 2>/dev/null || true

    log "installing for '${USER}'"

    # We check multiple paths to be safer than the original
    for steam_path in "${HOME}/.steam/steam" "${HOME}/.local/share/Steam" "${HOME}/.var/app/com.valvesoftware.Steam/.local/share/Steam"; do
        [ -d "$steam_path" ] || continue
        
        beta_file="${steam_path}/package/beta"
        target_lib="${steam_path}/ubuntu12_32/libXtst.so.6"

        # Force Steam Stable (Crucial for plugins)
        if [ -f "${beta_file}" ]; then
            log "removing beta '$(cat "${beta_file}")' in favor for stable."
            rm "${beta_file}"
        fi

        # Create symlink for millenniums preload bootstrap
        if [ -d "${steam_path}/ubuntu12_32" ]; then
            log "Creating bootstrap symlink in ${steam_path}"
            ln -sf /usr/lib/millennium/libmillennium_bootstrap_86x.so "${target_lib}"
        fi
    done
}

# --- STEP 3: INSTALLATION LOGIC ---
main() {
    if is_root; then log "Do not run as root!"; exit 1; fi

    uninstall_old_version

    # Check if we are on Arch/CachyOS to use paru/yay
    installed_aur=false
    if [ -f /etc/arch-release ] || [ -f /etc/cachyos-release ]; then
        log "\n[+] Arch-based system detected."
        if command -v paru >/dev/null; then
            log "[+] Force reinstalling via paru..."
            paru -S millennium --noconfirm --rebuild && installed_aur=true
        elif command -v yay >/dev/null; then
            log "[+] Force reinstalling via yay..."
            yay -S millennium --noconfirm --redownload && installed_aur=true
        fi
    fi

    # Fallback to manual if not on Arch or AUR failed
    if [ "$installed_aur" = false ]; then
        log "\n[!] Using manual GitHub installation method..."
        local target="linux-x86_64"
        local response=$(curl -fsSL -H 'Accept: application/vnd.github.v3+json' "${RELEASES_URI}?per_page=1")
        local tag=$(echo "${response}" | jq -r '.[0].tag_name')
        local download_uri="${DOWNLOAD_URI}/${tag}/millennium-${tag#v}-${target}.tar.gz"

        mkdir -p "${INSTALL_DIR}/files"
        curl -L "${download_uri}" | tar xz -C "${INSTALL_DIR}/files"
        sudo cp -r "${INSTALL_DIR}/files"/* / || true
        rm -rf "${INSTALL_DIR}"
    fi

    # MANDATORY: Run the original post_install logic after the package manager finishes
    apply_post_install

    log "\ndone.\n"
    log "You can now start Steam."
    log "https://docs.steambrew.app/users/installing#post-installation."
}

main "$@"
