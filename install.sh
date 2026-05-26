#!/usr/bin/env bash
set -euo pipefail

SELF_REPO_BASE="https://raw.githubusercontent.com/Star123451/LuaToolsLinux/main"
LUATOOLS_LEGACY_URL="$SELF_REPO_BASE/update_legacy.sh"
ENTERTHEWIRED_REPO="https://github.com/ciscosweater/enter-the-wired.git"
# Legacy Accela repository (source-based, run.sh)
LEGACY_ACCELA_REPO="https://raw.githubusercontent.com/aglairdev/enter-the-wired/main/enter-the-wired"

# GitHub release settings for plugin zip
REPO_OWNER="Star123451"
REPO_NAME="LuaToolsLinux"
RELEASE_ASSET_NAME="ltsteamplugin.zip"
GITHUB_API_URL="https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest"
PLUGIN_NAME="luatools"

# Headcrab (SLSsteam replacement) URL
HEADCRAB_URL="https://raw.githubusercontent.com/Deadboy666/h3adcr-b/main/headcrab.sh"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

DEBUG=false
info() { echo -e "${CYAN}[INFO]${NC} $*"; }
ok() { echo -e "${GREEN}[ OK ]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }
debug() { $DEBUG && echo -e "${CYAN}[DEBUG]${NC} $*"; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"; }

# ---------- Helper: extract zip ----------
extract_zip() {
    local archive_path="$1"
    local destination="$2"
    mkdir -p "$destination"
    if command -v unzip &>/dev/null; then
        unzip -qo "$archive_path" -d "$destination"
        return 0
    fi
    if command -v python3 &>/dev/null; then
        python3 - "$archive_path" "$destination" <<'PY'
import sys, zipfile
archive = sys.argv[1]
dest = sys.argv[2]
with zipfile.ZipFile(archive, "r") as zf:
    zf.extractall(dest)
PY
        return 0
    fi
    return 1
}

# ---------- Install plugin from GitHub release ----------
install_plugin_from_release() {
    info "Installing LuaTools plugin from latest GitHub release..."
    if ! command -v python3 &>/dev/null; then
        fail "python3 is required to fetch release info"
    fi
    local tmp_dir
    tmp_dir="$(mktemp -d)"
    trap 'rm -rf "$tmp_dir"' EXIT
    local meta_file="$tmp_dir/release.json"
    if ! curl -fsSL "$GITHUB_API_URL" -o "$meta_file"; then
        fail "Failed to fetch latest release metadata"
    fi
    local latest_tag asset_url
    mapfile -t release_info < <(
        python3 - "$meta_file" "$RELEASE_ASSET_NAME" <<'PY'
import json, sys
meta_file = sys.argv[1]
asset_name = sys.argv[2]
with open(meta_file, 'r', encoding='utf-8') as f:
    data = json.load(f)
tag = str(data.get('tag_name', '')).strip()
asset_url = ''
for asset in data.get('assets', []):
    if str(asset.get('name', '')).strip() == asset_name:
        asset_url = str(asset.get('browser_download_url', '')).strip()
        break
print(tag)
print(asset_url)
PY
    )
    latest_tag="${release_info[0]}"
    asset_url="${release_info[1]}"
    if [[ -z "$asset_url" ]]; then
        fail "Release asset '$RELEASE_ASSET_NAME' not found"
    fi
    info "Latest release: ${latest_tag:-unknown}"
    local zip_file="$tmp_dir/$RELEASE_ASSET_NAME"
    info "Downloading $RELEASE_ASSET_NAME ..."
    if ! curl -fL "$asset_url" -o "$zip_file"; then
        fail "Download failed"
    fi
    local install_dir
    install_dir=$(get_plugin_install_dir)
    mkdir -p "$(dirname "$install_dir")"
    info "Installing to $install_dir"
    if [[ -d "$install_dir" ]]; then
        rm -rf "$install_dir"
    fi
    mkdir -p "$install_dir"
    if ! extract_zip "$zip_file" "$install_dir"; then
        fail "Extraction failed"
    fi
    ok "Plugin installed (version ${latest_tag:-latest})"
}

# ---------- Helper: get plugin install dir ----------
get_plugin_install_dir() {
    local millennium_dir=""
    local candidates=(
        "$HOME/.local/share/millennium/plugins"
        "$HOME/.millennium/plugins"
        "$HOME/.steam/steam/millennium/plugins"
        "$HOME/.local/share/Steam/millennium/plugins"
    )
    for dir in "${candidates[@]}"; do
        if [[ -d "$dir" ]]; then
            millennium_dir="$dir"
            break
        fi
    done
    if [[ -z "$millennium_dir" ]]; then
        millennium_dir="$HOME/.local/share/millennium/plugins"
    fi
    echo "$millennium_dir/$PLUGIN_NAME"
}

# ---------- Helper: ensure venv module is installed on the system ----------
ensure_venv_module_installed() {
    if python3 -c "import venv" &>/dev/null; then
        return 0
    fi
    
    warn "python3-venv module is not available. Attempting to install it..."
    local family=$(get_distro_family)
    case "$family" in
        debian)
            info "Installing python3-venv via apt..."
            sudo apt-get update && sudo apt-get install -y python3-venv
            ;;
        fedora)
            info "Installing python3-virtualenv via dnf..."
            sudo dnf install -y python3-virtualenv
            ;;
        arch)
            info "Installing python via pacman..."
            sudo pacman -S --noconfirm python
            ;;
        *)
            fail "Could not automatically install python3-venv. Please install the virtualenv/venv package for python3 manually."
            ;;
    esac
    
    if ! python3 -c "import venv" &>/dev/null; then
        fail "Failed to install/verify python3 venv module."
    fi
    ok "python3 venv module is ready."
}

# ---------- Helper: inject venv site-packages into main.py ----------
inject_venv_into_main_py() {
    local install_dir
    install_dir=$(get_plugin_install_dir)
    local main_py="$install_dir/backend/main.py"
    
    if [[ ! -f "$main_py" ]]; then
        warn "main.py not found at $main_py, skipping venv injection."
        return
    fi
    
    # Check if we already injected it to avoid duplicates
    if grep -q "VENV SITE-PACKAGES INJECTION" "$main_py"; then
        ok "venv injection already present in main.py."
        return
    fi
    
    info "Injecting venv site-packages into main.py..."
    local tmp_file
    tmp_file=$(mktemp)
    
    cat << 'EOF' > "$tmp_file"
# === VENV SITE-PACKAGES INJECTION ===
import sys
import os
try:
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    plugin_root = os.path.dirname(backend_dir)
    venv_path = os.path.join(plugin_root, ".venv")
    if os.path.exists(venv_path):
        lib_dir = os.path.join(venv_path, "lib")
        if os.path.exists(lib_dir):
            for py_dir in os.listdir(lib_dir):
                site_packages = os.path.join(lib_dir, py_dir, "site-packages")
                if os.path.exists(site_packages):
                    if site_packages not in sys.path:
                        sys.path.insert(0, site_packages)
                    break
except Exception as e:
    pass
# ====================================
EOF
    
    cat "$main_py" >> "$tmp_file"
    mv "$tmp_file" "$main_py"
    chmod +x "$main_py"
    ok "main.py patched successfully."
}

# ---------- Python dependency check and installation (only for plugin) ----------
check_python_dependencies() {
    info "Checking Python dependencies (httpx, beautifulsoup4, ruamel.yaml)..."
    if ! command -v python3 &>/dev/null; then
        warn "python3 not found. Cannot check dependencies."
        return 1
    fi
    if python3 -c "import httpx, bs4, ruamel.yaml" 2>/dev/null; then
        ok "All Python dependencies are already satisfied."
        return 0
    fi
    warn "Some Python dependencies are missing. Attempting to install them..."
    
    local pip_cmd=""
    if command -v pip3 &>/dev/null; then
        pip_cmd="pip3"
    elif command -v pip &>/dev/null; then
        pip_cmd="pip"
    else
        warn "pip not found. Trying to install pip via ensurepip..."
        python3 -m ensurepip --upgrade 2>/dev/null || {
            warn "Could not install pip. Please install pip manually."
            return 1
        }
        pip_cmd="python3 -m pip"
    fi
    
    local packages=("httpx==0.27.2" "beautifulsoup4" "ruamel.yaml==0.18.6")
    for pkg in "${packages[@]}"; do
        info "Installing $pkg ..."
        if $pip_cmd install --user "$pkg" &>/dev/null; then
            ok "Installed $pkg"
        else
            warn "Failed to install $pkg. Trying without --user..."
            if $pip_cmd install "$pkg" &>/dev/null; then
                ok "Installed $pkg (system-wide)"
            else
                warn "Could not install $pkg. Manual installation may be required."
            fi
        fi
    done
    
    if python3 -c "import httpx, bs4, ruamel.yaml" 2>/dev/null; then
        ok "Python dependencies successfully installed."
        return 0
    else
        warn "Python dependencies still missing. You may need to install them manually:"
        echo "  pip install httpx beautifulsoup4 ruamel.yaml"
        return 1
    fi
}

# ---------- Show status ----------
show_status() {
    echo ""
    if is_millennium_installed; then
        local mver=$(get_millennium_version)
        ok "Millennium: installed (version ${mver:-unknown})"
    else
        warn "Millennium: NOT installed"
    fi
    if is_accela_installed; then
        local atype=$(detect_accela_type)
        local fname=$(get_accela_filename)
        if [[ "$atype" == "appimage" ]]; then
            warn "Accela: installed as AppImage (file: $fname). You may need to manually set the path in LuaTools menu (point to ~/.local/share/ACCELA/$fname)."
        elif [[ "$atype" == "run.sh" ]]; then
            ok "Accela: installed as run.sh script."
        else
            ok "Accela: installed (type unknown)"
        fi
    else
        warn "Accela: NOT installed"
    fi
}

# ---------- Post-install instructions ----------
show_post_install_instructions() {
    if ! is_accela_installed; then
        return
    fi
    echo ""
    echo -e "${BOLD}${YELLOW}+----------------------------------------------------------------------+${NC}"
    echo -e "${BOLD}${YELLOW}|                    IMPORTANT: Accela Configuration                    |${NC}"
    echo -e "${BOLD}${YELLOW}+----------------------------------------------------------------------+${NC}"
    echo -e "${BOLD}${YELLOW}|${NC}  1) Open accela, config options/downloads.                           ${BOLD}${YELLOW}|${NC}"
    echo -e "${BOLD}${YELLOW}|${NC}  2) Ensure the option ${BOLD}\"Limit downloads to Steam Library\"${NC} is ${BOLD}ENABLED${NC}.              ${BOLD}${YELLOW}|${NC}"
    echo -e "${BOLD}${YELLOW}|${NC}  3) In Steam, click the Steam name at the top-left corner.          ${BOLD}${YELLOW}|${NC}"
    echo -e "${BOLD}${YELLOW}|${NC}     Open Millennium → Plugins tab → Enable ${BOLD}LuaTools${NC}.                    ${BOLD}${YELLOW}|${NC}"
    echo -e "${BOLD}${YELLOW}|${NC}  4) Go to Lua tools menu on Steam/config ${BOLD}\"External Launcher (ACCELA)\"${NC}               ${BOLD}${YELLOW}|${NC}"
    echo -e "${BOLD}${YELLOW}|${NC}     and click the folder icon.                                        ${BOLD}${YELLOW}|${NC}"
    echo -e "${BOLD}${YELLOW}|${NC}  5) Navigate to ${BOLD}~/.local/share/ACCELA${NC} and select:                                   ${BOLD}${YELLOW}|${NC}"
    echo -e "${BOLD}${YELLOW}|${NC}       - ${GREEN}run.sh${NC} (if installed as script) or                                     ${BOLD}${YELLOW}|${NC}"
    echo -e "${BOLD}${YELLOW}|${NC}       - ${GREEN}ACCELA.AppImage${NC} (if using AppImage)                                  ${BOLD}${YELLOW}|${NC}"
    echo -e "${BOLD}${YELLOW}|${NC}  6) Click the save icon (diskette).                                      ${BOLD}${YELLOW}|${NC}"
    echo -e "${BOLD}${YELLOW}|${NC}  7) You can now add your game directly from the game page.                ${BOLD}${YELLOW}|${NC}"
    echo -e "${BOLD}${YELLOW}+----------------------------------------------------------------------+${NC}"
    echo ""
}

# ---------- Pre-flight checks ----------
check_internet() {
    info "Checking internet connectivity..."
    if ! curl -fsS --head "https://github.com" >/dev/null 2>&1; then
        fail "No internet connection"
    fi
    ok "Internet reachable"
}

check_architecture() {
    if [[ "$(uname -m)" != "x86_64" ]]; then
        fail "Unsupported architecture: $(uname -m). Only x86_64 works."
    fi
    ok "Architecture x86_64 OK"
}

force_close_steam() {
    if pgrep -x "steam" >/dev/null; then
        warn "Steam is running. Closing it now..."
        pkill -x steam || true
        sleep 3
        if pgrep -x "steam" >/dev/null; then
            warn "Steam still running. Please close it manually."
        else
            ok "Steam closed"
        fi
    fi
}

start_steam() {
    info "Starting Steam..."
    nohup steam >/dev/null 2>&1 &
    ok "Steam launched"
}

# ---------- Steam compatibility ----------
detect_steam_type() {
    local steam_type="unknown"
    if command -v flatpak >/dev/null && flatpak list 2>/dev/null | grep -q "com.valvesoftware.Steam"; then
        steam_type="flatpak"
    elif command -v snap >/dev/null && snap list 2>/dev/null | grep -q "^steam "; then
        steam_type="snap"
    elif command -v steam >/dev/null && [[ -f /usr/bin/steam ]]; then
        steam_type="native"
    fi
    echo "$steam_type"
}

get_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        echo "$ID"
    else
        echo "unknown"
    fi
}

get_distro_family() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        if [[ "$ID" == "ubuntu" || "$ID" == "debian" || "$ID_LIKE" =~ (debian|ubuntu) ]]; then
            echo "debian"
        elif [[ "$ID" == "fedora" || "$ID" == "rhel" || "$ID" == "centos" || "$ID_LIKE" =~ (fedora|rhel) ]]; then
            echo "fedora"
        elif [[ "$ID" == "arch" || "$ID_LIKE" =~ arch ]]; then
            echo "arch"
        else
            echo "unknown"
        fi
    else
        echo "unknown"
    fi
}

suggest_native_steam_install() {
    local distro=$(get_distro)
    case "$distro" in
        ubuntu|debian)      echo "sudo snap remove steam && sudo apt update && sudo apt install steam" ;;
        fedora)             echo "sudo snap remove steam && sudo dnf install steam" ;;
        arch|manjaro)       echo "sudo snap remove steam && sudo pacman -S steam" ;;
        opensuse*)          echo "sudo snap remove steam && sudo zypper install steam" ;;
        *)                  echo "See your distro docs to install native Steam." ;;
    esac
}

check_steam_compatibility() {
    local steam_type=$(detect_steam_type)
    case "$steam_type" in
        flatpak)
            warn "Steam Flatpak detected. Millennium does NOT work with Flatpak."
            local cmd=$(suggest_native_steam_install)
            echo -e "${YELLOW}To fix, remove Flatpak:${NC}"
            echo "  flatpak uninstall com.valvesoftware.Steam"
            echo -e "${YELLOW}Then install native Steam:${NC}"
            echo "  $cmd"
            fail "Aborted. Use native Steam."
            ;;
        snap)
            warn "Steam Snap detected. Millennium does NOT work with Snap."
            local cmd=$(suggest_native_steam_install)
            echo -e "${YELLOW}Remove Snap and install native:${NC}"
            echo "  $cmd"
            fail "Aborted. Use native Steam."
            ;;
        native)
            ok "Native Steam detected. OK."
            ;;
        *)
            warn "Could not determine Steam type. Assuming native, be careful."
            ;;
    esac
}

check_decky_loader() {
    if [[ -d "$HOME/.local/share/decky" ]] || [[ -f "$HOME/.steam/steam/plugins/decky-loader" ]] || ( command -v systemctl >/dev/null && systemctl --user list-units 2>/dev/null | grep -q decky ); then
        warn "Decky Loader detected! May conflict with Millennium."
        echo -e "${YELLOW}Options:${NC}"
        echo "  1) Uninstall Decky Loader (recommended)"
        echo "  2) Continue anyway (risky)"
        local response=""
        printf "Choose [1/2]: " > /dev/tty
        read -r response < /dev/tty
        case "$response" in
            1)
                info "Uninstalling Decky Loader..."
                curl -fsSL https://github.com/SteamDeckHomebrew/decky-loader/raw/main/uninstall.sh | bash || warn "Uninstall failed."
                ok "Decky Loader removed"
                ;;
            *)
                warn "Continuing with Decky Loader present. Expect issues."
                ;;
        esac
    fi
}

# ---------- Millennium detection ----------
is_millennium_installed() {
    local result=""
    if command -v pacman >/dev/null; then
        result=$(pacman -Qs millennium 2>/dev/null)
    fi
    if [[ -z "$result" ]] && command -v dpkg >/dev/null; then
        result=$(dpkg -l | grep millennium 2>/dev/null)
    fi
    if [[ -z "$result" ]] && command -v rpm >/dev/null; then
        result=$(rpm -qa | grep millennium 2>/dev/null)
    fi
    if [[ -z "$result" ]] && command -v flatpak >/dev/null; then
        result=$(flatpak list | grep -i millennium 2>/dev/null)
    fi
    if [[ -z "$result" ]] && [[ -f "$HOME/.local/share/millennium/bootstrap.log" ]]; then
        result=$(grep -i "version" "$HOME/.local/share/millennium/bootstrap.log" 2>/dev/null)
    fi
    [[ -n "$result" ]] && return 0
    [[ -f "/usr/lib/millennium/libmillennium.so" ]] || [[ -f "/usr/bin/steam.millennium.bak" ]]
}

get_millennium_version() {
    local result=""
    if command -v pacman >/dev/null; then
        result=$(pacman -Qs millennium 2>/dev/null)
    fi
    if [[ -z "$result" ]] && command -v dpkg >/dev/null; then
        result=$(dpkg -l | grep millennium 2>/dev/null)
    fi
    if [[ -z "$result" ]] && command -v rpm >/dev/null; then
        result=$(rpm -qa | grep millennium 2>/dev/null)
    fi
    if [[ -z "$result" ]] && command -v flatpak >/dev/null; then
        result=$(flatpak list | grep -i millennium 2>/dev/null)
    fi
    if [[ -z "$result" ]] && [[ -f "$HOME/.local/share/millennium/bootstrap.log" ]]; then
        result=$(grep -i "version" "$HOME/.local/share/millennium/bootstrap.log" 2>/dev/null)
    fi
    if [[ -n "$result" ]]; then
        local ver=""
        if [[ "$result" =~ [v]?([0-9]+\.[0-9]+\.[0-9]+) ]]; then
            ver="${BASH_REMATCH[1]}"
        elif [[ "$result" =~ version[\"[:space:]]*:[\"[:space:]]*([0-9]+\.[0-9]+\.[0-9]+) ]]; then
            ver="${BASH_REMATCH[1]}"
        else
            ver="unknown"
        fi
        echo "$ver"
    else
        if [[ -f "/usr/lib/millennium/version.txt" ]]; then
            cat "/usr/lib/millennium/version.txt" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1
        elif [[ -f "/usr/lib/millennium/libmillennium.so" ]]; then
            strings "/usr/lib/millennium/libmillennium.so" 2>/dev/null | grep -oE 'Millennium v[0-9]+\.[0-9]+\.[0-9]+' | head -1 | sed 's/.*v//'
        else
            echo ""
        fi
    fi
}

# ---------- Accela detection ----------
is_accela_installed() {
    local accela_dir="$HOME/.local/share/ACCELA"
    [[ -d "$accela_dir" ]] || return 1
    if [[ -f "$accela_dir/run.sh" && -x "$accela_dir/run.sh" ]]; then
        return 0
    fi
    while IFS= read -r file; do
        if [[ -f "$file" && -x "$file" ]]; then
            if [[ "$(basename "$file")" == "ACCELA.AppImage" ]]; then
                return 0
            fi
            if file "$file" 2>/dev/null | grep -q "ELF.*executable"; then
                return 0
            fi
        fi
    done < <(find "$accela_dir" -maxdepth 1 -type f -executable 2>/dev/null)
    return 1
}

detect_accela_type() {
    local accela_dir="$HOME/.local/share/ACCELA"
    [[ -d "$accela_dir" ]] || { echo "none"; return; }
    if [[ -f "$accela_dir/run.sh" && -x "$accela_dir/run.sh" ]]; then
        echo "run.sh"
        return
    fi
    if [[ -f "$accela_dir/ACCELA.AppImage" && -x "$accela_dir/ACCELA.AppImage" ]]; then
        echo "appimage"
        return
    fi
    while IFS= read -r file; do
        if [[ -f "$file" && -x "$file" ]] && file "$file" 2>/dev/null | grep -q "ELF.*executable"; then
            echo "appimage"
            return
        fi
    done < <(find "$accela_dir" -maxdepth 1 -type f -executable 2>/dev/null)
    echo "unknown"
}

get_accela_filename() {
    local accela_dir="$HOME/.local/share/ACCELA"
    [[ -d "$accela_dir" ]] || { echo ""; return; }
    if [[ -f "$accela_dir/run.sh" && -x "$accela_dir/run.sh" ]]; then
        echo "run.sh"
        return
    fi
    if [[ -f "$accela_dir/ACCELA.AppImage" && -x "$accela_dir/ACCELA.AppImage" ]]; then
        echo "ACCELA.AppImage"
        return
    fi
    while IFS= read -r file; do
        if [[ -f "$file" && -x "$file" ]]; then
            basename "$file"
            return
        fi
    done < <(find "$accela_dir" -maxdepth 1 -type f -executable 2>/dev/null)
    echo ""
}

# ---------- Plugin directory cleanup ----------
clean_plugin_dir() {
    local plugin_paths=(
        "$HOME/.local/share/millennium/plugins/LuaToolsLinux"
        "$HOME/.steam/steam/millennium/plugins/LuaToolsLinux"
        "$HOME/.steam/steam/steamui/millennium/plugins/LuaToolsLinux"
    )
    for path in "${plugin_paths[@]}"; do
        if [[ -d "$path" ]]; then
            rm -rf "$path"
        fi
    done
}

# ---------- Dependency fix ----------
run_fix_deps() {
    info "Running dependency fix script (fix-deps)..."
    curl -fsSL https://raw.githubusercontent.com/ciscosweater/enter-the-wired/main/fix-deps | bash || warn "fix-deps failed, continuing..."
}

# ---------- Ubuntu/Debian libssl check ----------
check_libssl_dev() {
    local family=$(get_distro_family)
    [[ "$family" != "debian" ]] && return
    if dpkg -s libssl-dev:i386 2>/dev/null | grep -q '^Status:.*installed'; then
        ok "libssl-dev:i386 already installed."
        return
    fi
    warn "libssl-dev:i386 (32-bit dev libs) is missing."
    local response=""
    printf "Install libssl-dev:i386 now? [y/N]: " > /dev/tty
    read -r response < /dev/tty
    if [[ "$response" =~ ^[Yy]$ ]]; then
        sudo dpkg --add-architecture i386 || true
        sudo apt update || true
        sudo apt install -y libssl-dev:i386 || warn "Installation failed."
    else
        info "Skipping libssl-dev:i386."
    fi
}

# ---------- Installers ----------
install_millennium_beta() {
    info "Installing Millennium beta via steambrew.app..."
    curl -fsSL "https://steambrew.app/install.sh" | bash -s -- --beta || fail "Millennium beta installation failed."
    ok "Millennium beta installed"
}

install_millennium_legacy() {
    info "Installing Millennium Legacy (old version) + LuaTools plugin..."
    force_close_steam
    curl -fsSL "https://github.com/SteamClientHomebrew/Millennium/raw/refs/heads/legacy/scripts/install.sh" | bash || fail "Millennium Legacy installation failed."
    ok "Millennium Legacy installed"
    install_plugin_from_release
    check_python_dependencies
    start_steam
    info "Millennium Legacy + plugin installation completed. Steam started."
}

install_accela_and_slssteam() {
    info "Installing accela and slssteam via enter-the-wired (standard AppImage version)..."
    curl -fsSL https://raw.githubusercontent.com/ciscosweater/enter-the-wired/main/enter-the-wired | bash || warn "Accela installation failed."
    ok "Accela and slssteam installed"
}

install_legacy_accela_and_sls() {
    info "Installing Legacy Accela (source-based, run.sh) + SLSsteam (headcrab)..."
    info "This combination fixes AppImage compatibility issues by using the Python source version from aglairdev/enter-the-wired."
    
    # The script from aglairdev already installs both Accela (run.sh) and SLSsteam
    curl -fsSL "$LEGACY_ACCELA_REPO" | bash || fail "Legacy Accela installation failed."
    
    ok "Legacy Accela (run.sh) and SLSsteam installed successfully."
    show_post_install_instructions
}

# ---------- Option 1: Install All (beta + standard accela) ----------
install_all() {
    info "Starting FULL installation (Millennium beta + plugin + accela standard)..."
    run_fix_deps
    force_close_steam
    install_millennium_beta
    install_plugin_from_release
    check_python_dependencies
    install_accela_and_slssteam
    start_steam
    show_status
    show_post_install_instructions
    ok "Full installation complete. Steam has been started."
}

# ---------- Option 2: Only plugin (reinstall) ----------
install_millennium_flow() {
    run_fix_deps
    force_close_steam
    if is_millennium_installed; then
        local current_version=$(get_millennium_version)
        ok "Millennium already installed. Version: ${current_version:-unknown}"
    else
        info "Millennium not installed. Installing Millennium beta first..."
        install_millennium_beta
    fi
    install_plugin_from_release
    check_python_dependencies
    start_steam
    show_status
    if is_accela_installed; then
        show_post_install_instructions
    fi
    ok "Plugin installation complete. Steam has been started."
}

# ---------- Option 3: Millennium Legacy + plugin ----------
install_millennium_legacy_flow() {
    install_millennium_legacy
}

# ---------- Option 4: Only accela standard ----------
install_accela_only() {
    info "Installing accela and slssteam only (standard AppImage version)..."
    install_accela_and_slssteam
    show_status
    show_post_install_instructions
    ok "Accela installation completed."
}

# ---------- Option 5: Legacy Accela + SLSsteam ----------
install_legacy_accela_and_sls_only() {
    info "Installing Legacy Accela (source-based, run.sh) + SLSsteam only..."
    install_legacy_accela_and_sls
    show_status
    ok "Legacy Accela + SLSsteam installation completed."
}

# ---------- Informational fixes ----------
fix_missing_game_executable() {
    echo ""
    echo -e "${BOLD}${CYAN}Error: 'Missing game executable' or 'Fail on compatibility tool'${NC}"
    echo -e "${YELLOW}Troubleshooting steps:${NC}"
    echo ""
    echo "1) Right-click on the game in your Steam library."
    echo "2) Go to Properties → Compatibility."
    echo "3) Check the box 'Force the use of a specific Steam Play compatibility tool'."
    echo "4) For Linux native games: select 'Steam Linux Runtime' or 'Legacy Runtime'."
    echo "5) For Windows games: select a Proton version."
    echo "   - Check ProtonDB (https://www.protondb.com) for the best Proton version for your game."
    echo "   - 'Proton Experimental' often works well for many games."
    echo "6) Launch the game again."
    echo ""
    read -p "Press Enter to continue..." < /dev/tty
}

fix_content_still_encrypted() {
    echo ""
    echo -e "${BOLD}${CYAN}Error: 'Content Still Encrypted'${NC}"
    echo -e "${YELLOW}Troubleshooting steps:${NC}"
    echo ""
    echo "1) Right-click on the game in your Steam library."
    echo "2) Go to Properties → Compatibility."
    echo "3) Check the box 'Force the use of a specific Steam Play compatibility tool'."
    echo "4) For Linux native games: select 'Steam Linux Runtime' or 'Legacy Runtime'."
    echo "5) For Windows games: select a Proton version (check ProtonDB for best choice or use Experimental)."
    echo "6) Still in Properties, go to 'Installed Files'."
    echo "7) Click 'Verify integrity of game files'."
    echo "8) Wait for verification to complete, then launch the game."
    echo ""
    read -p "Press Enter to continue..." < /dev/tty
}

fix_online_fix_not_working() {
    echo ""
    echo -e "${BOLD}${CYAN}Error: Online Fix doesn't work${NC}"
    echo -e "${YELLOW}Troubleshooting steps:${NC}"
    echo ""
    echo "1) Apply the online fix files to the game installation folder."
    echo "2) In Steam, right-click on the game → Properties."
    echo "3) In 'Launch Options', paste the following:"
    echo ""
    echo -e "${GREEN}WINEDLLOVERRIDES=\"OnlineFix64=n;SteamOverlay64=n;winmm=n,b;dnet=n;steam_api64=n;winhttp=n,b\" %command%${NC}"
    echo ""
    echo "4) Close Properties and launch the game."
    echo ""
    read -p "Press Enter to continue..." < /dev/tty
}

fix_purchase_error() {
    info "Fixing 'Purchase error' by running headcrab script..."
    curl -fsSL "https://raw.githubusercontent.com/Deadboy666/h3adcr-b/main/headcrab.sh" | bash || warn "Headcrab script failed."
    ok "Purchase error fix attempted."
}

fix_missing_keys() {
    info "Fixing 'Missing Keys'..."
    rm -rf ~/.config/SLSsteam ~/.config/headcrab
    info "Removed ~/.config/SLSsteam and ~/.config/headcrab"
    if [[ ! -d "$HOME/enter-the-wired" ]]; then
        info "Cloning enter-the-wired repository..."
        git clone "$ENTERTHEWIRED_REPO" "$HOME/enter-the-wired" || {
            warn "Git clone failed. Trying curl..."
            mkdir -p "$HOME/enter-the-wired"
            curl -fsSL "https://raw.githubusercontent.com/ciscosweater/enter-the-wired/main/slssteam" -o "$HOME/enter-the-wired/slssteam"
            chmod +x "$HOME/enter-the-wired/slssteam"
        }
    fi
    if [[ -x "$HOME/enter-the-wired/slssteam" ]]; then
        ~/enter-the-wired/slssteam
    else
        warn "slssteam not found."
    fi
    ok "Missing Keys fix attempted."
}

fix_no_licenses_info() {
    echo ""
    echo -e "${YELLOW}No licenses error - Information${NC}"
    echo "This error usually occurs when:"
    echo "  1) You downloaded the game to the wrong folder, or"
    echo "  2) You haven't set the correct path to accela in the LuaTools menu."
    echo ""
    echo "To fix:"
    echo "  - Open Steam, go to LuaTools plugin settings."
    echo "  - Ensure the path to accela is correctly set (to ~/.local/share/ACCELA or wherever accela is located)."
    echo "  - In the accela menu, enable the option: 'Limit downloads to Steam Library'."
    echo ""
    read -p "Press Enter to continue..." < /dev/tty
}

fix_remove_piracy_blocks() {
    local theme_css_dir="$HOME/.steam/steam/millennium/themes/Steam/src/css"
    local files_to_fix=(
        "libraryroot.custom.css"
        "overlay.custom.css"
        "regular.css"
        "startupLogin.custom.css"
        "webkit.css"
        "steam/gamepage.css"
    )
    echo ""
    if [[ ! -d "$theme_css_dir" ]]; then
        warn "Theme CSS directory not found: $theme_css_dir"
        warn "Make sure Millennium and the theme are installed."
        return 1
    fi
    ok "Directory found: $theme_css_dir"
    local any_fixed=false
    for filename in "${files_to_fix[@]}"; do
        local filepath="$theme_css_dir/$filename"
        if [[ ! -f "$filepath" ]]; then
            echo "$filename -> NOT FOUND, skipping"
            continue
        fi
        echo -n "$filename ... "
        cp "$filepath" "$filepath.bak"
        sed -i '/Pls remove any piracy plugin/d' "$filepath"
        sed -i '/\[class\*="luatools"/d' "$filepath"
        sed -i '/\[data-millennium-plugin\*="luatools"/d' "$filepath"
        sed -i '/\[class\*="manilua"/d' "$filepath"
        sed -i '/\[data-millennium-plugin\*="manilua"/d' "$filepath"
        sed -i '/\[class\*="lumea"/d' "$filepath"
        sed -i '/\[data-millennium-plugin\*="lumea"/d' "$filepath"
        sed -i '/^[[:space:]]*$/d' "$filepath"
        if ! cmp -s "$filepath" "$filepath.bak"; then
            echo "✔ Removed"
            any_fixed=true
        else
            rm -f "$filepath.bak"
            echo "○ No block found"
        fi
    done
    echo ""
    if $any_fixed; then
        ok "Anti-piracy blocks removed. Restart Steam for changes."
    else
        warn "No changes made."
    fi
}

fix_reinstall_steam_clean() {
    echo ""
    echo -e "${BOLD}${RED}⚠️  WARNING: COMPLETE STEAM REINSTALL ⚠️${NC}"
    echo -e "${YELLOW}This will REMOVE ALL DOWNLOADED GAMES, configurations,"
    echo -e "Proton prefixes and any other Steam-related data (except saves"
    echo -e "that live outside Steam's folder, like Stardew Valley in ~/.config/StardewValley).${NC}"
    echo ""
    echo -e "${BOLD}To keep your downloaded games, BACKUP the following folder BEFORE proceeding:${NC}"
    echo -e "  ${GREEN}~/.local/share/Steam/steamapps/${NC}  or  ${GREEN}~/.steam/steam/steamapps/${NC}"
    echo ""
    echo -e "${BOLD}Backup example:${NC}"
    echo "  cp -r ~/.local/share/Steam/steamapps ~/backup_steamapps"
    echo ""
    echo -e "${RED}Have you backed up your games?${NC}"
    printf "Type [y/N]: " > /dev/tty
    local backup_ok; read -r backup_ok < /dev/tty
    if [[ ! "$backup_ok" =~ ^[Yy]$ ]]; then
        warn "Operation cancelled. Please backup and run again."
        return
    fi

    echo ""
    echo -e "${YELLOW}Continuing... Closing Steam if running.${NC}"
    force_close_steam

    info "Removing Steam package..."
    if command -v pacman >/dev/null; then
        sudo pacman -Rdd steam --noconfirm 2>/dev/null || warn "Steam package not installed?"
    elif command -v apt >/dev/null; then
        sudo apt remove --purge steam -y
    elif command -v dnf >/dev/null; then
        sudo dnf remove steam -y
    else
        warn "Package manager not recognized. Please remove Steam manually."
    fi

    info "Removing Steam config and data folders..."
    rm -rf ~/.steam ~/.local/share/Steam ~/.var/app/com.valvesoftware.Steam ~/.steampath ~/.steampid
    sudo rm -rf /usr/lib/steam /usr/share/steam 2>/dev/null || true

    info "Cleaning icon cache and shortcuts..."
    rm -f ~/.local/share/applications/steam*.desktop
    sudo update-desktop-database 2>/dev/null || true

    ok "Steam completely removed from system."

    echo ""
    echo -e "${BOLD}Do you want to reinstall Steam now?${NC}"
    printf "[y/N]: " > /dev/tty
    local reinstall_choice; read -r reinstall_choice < /dev/tty
    if [[ "$reinstall_choice" =~ ^[Yy]$ ]]; then
        info "Reinstalling Steam..."
        if command -v pacman >/dev/null; then
            sudo pacman -S steam --noconfirm
        elif command -v apt >/dev/null; then
            sudo apt install steam -y
        elif command -v dnf >/dev/null; then
            sudo dnf install steam -y
        else
            echo "Please install Steam manually."
        fi
        ok "Steam reinstalled."
        echo -e "${CYAN}To restore your games, copy the 'steamapps' folder back to ~/.local/share/Steam/ before launching Steam.${NC}"
    else
        info "You can reinstall Steam later with: sudo pacman -S steam"
    fi

    echo ""
    read -p "Press Enter to return to menu..." < /dev/tty
}

# ---------- Fixes menu ----------
fix_menu() {
    while true; do
        echo ""
        echo -e "${BOLD}Common Issues Fixes${NC}"
        echo "1) Purchase error or slssteam issues (headcrab)"
        echo "2) Missing Keys"
        echo "3) No licenses (information)"
        echo "4) Run fix-deps (install system dependencies)"
        echo "5) Remove anti-piracy blocks from Steam theme CSS"
        echo "6) Reinstall Steam completely (clean) - WILL DELETE GAMES!"
        echo "7) Missing game executable / Fail on compatibility tool (info)"
        echo "8) Content Still Encrypted (info)"
        echo "9) Online Fix doesn't work (info)"
        echo "10) Back to main menu"
        echo ""
        printf "Choose an option [1-10]: " > /dev/tty
        local choice; read -r choice < /dev/tty
        case "$choice" in
            1) fix_purchase_error ;;
            2) fix_missing_keys ;;
            3) fix_no_licenses_info ;;
            4) run_fix_deps ;;
            5) fix_remove_piracy_blocks ;;
            6) fix_reinstall_steam_clean ;;
            7) fix_missing_game_executable ;;
            8) fix_content_still_encrypted ;;
            9) fix_online_fix_not_working ;;
            10) break ;;
            *) warn "Invalid option." ;;
        esac
    done
}

# ---------- Uninstall ----------
uninstall_all_flow() {
    info "Uninstalling everything (Millennium, plugin, accela, slssteam)..."
    sudo rm -rf /usr/lib/millennium /usr/share/millennium \
                "${XDG_CONFIG_HOME:-$HOME/.config}/millennium" \
                "${XDG_DATA_HOME:-$HOME/.local/share}/millennium"
    if [ -f "/usr/bin/steam.millennium.bak" ]; then
        sudo mv /usr/bin/steam.millennium.bak /usr/bin/steam
    fi
    rm -f "${HOME}/.steam/steam/ubuntu12_32/libXtst.so.6"
    rm -rf "${XDG_DATA_HOME:-$HOME/.local/share}/luatools" \
           "${XDG_CONFIG_HOME:-$HOME/.config}/luatools" \
           "${HOME}/.luatools" 2>/dev/null || true
    clean_plugin_dir
    curl -fsSL https://raw.githubusercontent.com/ciscosweater/enter-the-wired/main/uninstall | bash || warn "Accela/slssteam uninstall may have failed."
    ok "Full uninstall completed."
}

# ---------- Main menu (reorganized) ----------
interactive_menu() {
    while true; do
        echo ""
        echo -e "${BOLD}LuaTools Installer${NC}"
        echo "1) Install All (Millennium beta + plugin + accela standard)"
        echo "2) Install/Reinstall LuaTools plugin only (keeps Millennium)"
        echo "3) Install Millennium Legacy + plugin (old version, fallback)"
        echo "4) Install accela and slssteam only (standard - AppImage)"
        echo "5) Install Legacy Accela (run.sh) + SLSsteam (fix for AppImage issues)"
        echo "6) Fix common issues"
        echo "7) Uninstall Everything"
        echo "8) Cancel"
        echo ""
        printf "Choose an option [1-8]: " > /dev/tty
        local choice; read -r choice < /dev/tty
        case "$choice" in
            1) install_all ; break ;;
            2) install_millennium_flow ; break ;;
            3) install_millennium_legacy_flow ; break ;;
            4) install_accela_only ; break ;;
            5) install_legacy_accela_and_sls_only ; break ;;
            6) fix_menu ;;
            7) uninstall_all_flow ; break ;;
            8) info "Cancelled." ; exit 0 ;;
            *) warn "Invalid option." ;;
        esac
    done
}

# ---------- Entry point ----------
main() {
    for arg in "$@"; do
        if [[ "$arg" == "--debug" ]]; then
            DEBUG=true
            set -x
        fi
    done
    require_cmd curl
    require_cmd bash
    if ! command -v git >/dev/null; then
        warn "git not installed. Some fix functions may fail."
    fi
    check_internet
    check_architecture
    check_steam_compatibility
    check_decky_loader
    show_status
    check_libssl_dev
    case "${1:-}" in
        1|--install-all)       install_all ;;
        2|--millennium)        install_millennium_flow ;;
        3|--legacy)            install_millennium_legacy_flow ;;
        4|--accela)            install_accela_only ;;
        5|--legacy-accela)     install_legacy_accela_and_sls_only ;;
        6|--fix)               fix_menu ;;
        7|--uninstall)         uninstall_all_flow ;;
        --cancel)              info "Cancelled." ; exit 0 ;;
        -h|--help)
            cat <<'EOF'
Usage: install.sh [option] [--debug]

Options:
    1, --install-all       Install all (Millennium beta + plugin + accela standard)
    2, --millennium        Install/Reinstall LuaTools plugin only (keeps Millennium)
    3, --legacy            Install Millennium Legacy + plugin (old version, fallback)
    4, --accela            Install accela and slssteam only (standard - AppImage)
    5, --legacy-accela     Install Legacy Accela (source-based, run.sh) + SLSsteam (FIX)
    6, --fix               Open fixes menu
    7, --uninstall         Uninstall everything
    --cancel               Exit
    --debug                Enable debug output
    -h, --help             Show this help
EOF
            exit 0
            ;;
        "")
            interactive_menu
            ;;
        *)
            warn "Unknown argument: $1"
            echo "Use -h for help."
            exit 1
            ;;
    esac
    echo ""
    read -p "Press Enter to close this terminal..." < /dev/tty
}

main "$@"
