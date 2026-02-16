#!/usr/bin/env bash
set -euo pipefail

# ============================================
#  LuaTools (Linux) Installer
#  By StarWarsK & geovanygrdt
# ============================================

REPO_URL="https://github.com/Star123451/LuaToolsLinux"
BRANCH="main"
PLUGIN_NAME="luatools"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[  OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   LuaTools (Linux) Installer         ║${NC}"
echo -e "${BOLD}║   by StarWarsK & geovanygrdt         ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""

# --- Check for required tools ---
for cmd in git python3; do
    if ! command -v "$cmd" &>/dev/null; then
        fail "'$cmd' is not installed. Please install it first."
    fi
done
ok "Required tools found (git, python3)"

# --- Check for curl (needed for installers) ---
if ! command -v curl &>/dev/null; then
    warn "curl not found, some auto-installers may fail"
    echo -e "  Install with: ${CYAN}sudo apt install curl${NC}"
fi

# --- Check for 7zip (needed for SLSsteam extraction) ---
if ! command -v 7z &>/dev/null; then
    warn "7zip not found, will install when needed for SLSsteam"
    echo -e "  You can pre-install with: ${CYAN}sudo apt install 7zip${NC}"
fi

# --- Check and install build tools (needed for SLSsteam) ---
if ! command -v make &>/dev/null || ! command -v gcc &>/dev/null; then
    if command -v sudo &>/dev/null && command -v apt &>/dev/null; then
        info "Installing build-essential..."
        sudo apt update -qq && sudo apt install -y build-essential
        ok "Build tools installed"
    else
        warn "Build tools (make/gcc) not found - needed for SLSsteam"
        echo -e "  Install with: ${CYAN}sudo apt install build-essential${NC}"
    fi
fi

# --- Check for 32-bit support and enable if needed ---
if ! dpkg --print-foreign-architectures 2>/dev/null | grep -q "i386"; then
    if command -v sudo &>/dev/null && command -v dpkg &>/dev/null; then
        info "Enabling 32-bit architecture support..."
        sudo dpkg --add-architecture i386 && sudo apt update -qq
    fi
fi

# --- Install Millennium if not found ---
install_millennium() {
    info "Installing Millennium..."
    if command -v curl &>/dev/null; then
        if curl -fsSL https://raw.githubusercontent.com/SteamClientHomebrew/Millennium/main/scripts/install.sh | bash; then
            ok "Millennium installed successfully"
            return 0
        else
            warn "Millennium installation failed"
            return 1
        fi
    else
        warn "curl not available, cannot auto-install Millennium"
        echo -e "  Please install manually from: ${CYAN}https://steambrew.app${NC}"
        return 1
    fi
}

# --- Install SLSsteam if not found ---
install_slssteam() {
    info "Installing SLSsteam..."
    
    # Check if 7z is available
    if ! command -v 7z &>/dev/null; then
        warn "7z is required to extract SLSsteam"
        if command -v sudo &>/dev/null && command -v apt &>/dev/null; then
            info "Installing 7zip..."
            sudo apt update -qq && sudo apt install -y 7zip
        else
            fail "Please install 7zip: sudo apt install 7zip"
        fi
    fi
    
    # Create temp directory for download
    local temp_dir=$(mktemp -d)
    info "  Downloading SLSsteam..."
    
    # Download latest SLSsteam release
    cd "$temp_dir"
    if curl -fsSL -o SLSsteam-Any.7z "https://github.com/AceSLS/SLSsteam/releases/download/20260122094411/SLSsteam-Any.7z" 2>&1; then
        ok "Downloaded SLSsteam"
        
        # Extract
        info "  Extracting..."
        if 7z x SLSsteam-Any.7z > /dev/null 2>&1; then
            ok "Extracted SLSsteam"
            
            # Run setup.sh install
            if [ -d "SLSsteam" ]; then
                cd SLSsteam
                info "  Running SLSsteam setup..."
                
                if bash setup.sh install; then
                    ok "SLSsteam installed successfully"
                    cd /
                    rm -rf "$temp_dir"
                    return 0
                else
                    warn "SLSsteam setup.sh install failed"
                    cd /
                    rm -rf "$temp_dir"
                    return 1
                fi
            else
                warn "SLSsteam directory not found after extraction"
                cd /
                rm -rf "$temp_dir"
                return 1
            fi
        else
            warn "Failed to extract SLSsteam"
            cd /
            rm -rf "$temp_dir"
            return 1
        fi
    else
        warn "Failed to download SLSsteam - check your internet connection"
        echo -e "  Manual install: ${CYAN}https://github.com/AceSLS/SLSsteam/releases${NC}"
        cd /
        rm -rf "$temp_dir"
        return 1
    fi
}

# --- Install ACCELA if not found ---
install_accela() {
    info "Installing ACCELA..."
    local accela_dir="$HOME/.local/share/ACCELA"
    
    if git clone https://github.com/ciscosweater/enter-the-wired.git "$accela_dir"; then
        ok "ACCELA installed to $accela_dir"
        return 0
    else
        warn "Failed to clone ACCELA repository"
        return 1
    fi
}

# --- Detect and Install Millennium ---
MILLENNIUM_DIR=""
MILLENNIUM_INSTALLED=false

# Check for actual Millennium installation (not just directories)
# Millennium installs core files in Steam directory and creates ext_storage
if [ -d "$HOME/.local/share/Steam/steamui/skins" ] || [ -d "$HOME/.steam/steam/steamui/skins" ]; then
    MILLENNIUM_INSTALLED=true
fi

# Also check for Millennium ext_storage which indicates successful setup
if [ -d "$HOME/.local/share/millennium/ext_storage" ] || [ -d "$HOME/.millennium/ext_storage" ]; then
    MILLENNIUM_INSTALLED=true
fi

if [ "$MILLENNIUM_INSTALLED" = false ]; then
    warn "Millennium not properly installed or detected."
    info "Installing/Reinstalling Millennium..."
    echo -e "  ${YELLOW}Note: Steam must be closed for Millennium installation!${NC}"
    echo ""
    
    # Check if Steam is running
    if pgrep -x "steam" > /dev/null || pgrep -x "steamwebhelper" > /dev/null; then
        warn "Steam is currently running!"
        echo -e "  ${YELLOW}Please close Steam completely before continuing.${NC}"
        read -rp "Press Enter once Steam is closed..."
    fi
    
    if install_millennium; then
        ok "Millennium installation completed"
        echo -e "  ${CYAN}Please start Steam after this script finishes${NC}"
    else
        fail "Millennium installation failed. Please install manually from https://steambrew.app"
    fi
fi

# Now find the plugins directory
candidates=(
    "$HOME/.local/share/millennium/plugins"
    "$HOME/.millennium/plugins"
    "$HOME/.steam/steam/millennium/plugins"
    "$HOME/.local/share/Steam/millennium/plugins"
)

for dir in "${candidates[@]}"; do
    if [ -d "$dir" ]; then
        MILLENNIUM_DIR="$dir"
        break
    fi
done

# If still not found, create default directory
if [ -z "$MILLENNIUM_DIR" ]; then
    MILLENNIUM_DIR="$HOME/.local/share/millennium/plugins"
    mkdir -p "$MILLENNIUM_DIR"
    info "Created plugins directory: $MILLENNIUM_DIR"
fi

INSTALL_DIR="$MILLENNIUM_DIR/$PLUGIN_NAME"
info "Install directory: $INSTALL_DIR"

# --- Install or update ---
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Existing installation found — updating..."
    cd "$INSTALL_DIR"
    git pull --ff-only origin "$BRANCH" || {
        warn "Fast-forward pull failed. Doing a clean re-clone..."
        cd ..
        rm -rf "$INSTALL_DIR"
        git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    }
    ok "Updated to latest version"
elif [ -d "$INSTALL_DIR" ]; then
    warn "Directory exists but is not a git repo. Backing up and re-installing..."
    mv "$INSTALL_DIR" "${INSTALL_DIR}.bak.$(date +%s)"
    git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    ok "Fresh install complete (old files backed up)"
else
    info "Cloning LuaTools..."
    git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    ok "Cloned successfully"
fi

ok "LuaTools installation complete"

# --- Install/Reinstall SLSsteam ---
echo ""
if [ -f "$HOME/.local/share/SLSsteam/SLSsteam.so" ]; then
    info "SLSsteam detected - reinstalling to ensure it's working..."
    rm -rf "$HOME/.local/share/SLSsteam"
else
    info "SLSsteam not found - installing..."
fi
install_slssteam || echo -e "  ${YELLOW}Manual install:${NC} ${CYAN}https://github.com/AceSLS/SLSsteam${NC}"

# --- Install/Reinstall ACCELA ---
ACCELA_FOUND=false
for p in "$HOME/.local/share/ACCELA" "$HOME/accela"; do
    if [ -d "$p" ]; then
        info "ACCELA detected at $p - reinstalling to ensure it's working..."
        rm -rf "$p"
        ACCELA_FOUND=true
        break
    fi
done
if [ "$ACCELA_FOUND" = false ]; then
    info "ACCELA not found - installing..."
fi
install_accela || echo -e "  ${YELLOW}Manual install:${NC} ${CYAN}https://github.com/ciscosweater/enter-the-wired${NC}"

# --- Done ---
echo ""
echo -e "${GREEN}${BOLD}✓ Installation complete!${NC}"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo -e "  1. ${CYAN}Make sure Steam is COMPLETELY closed${NC} (check with: ${CYAN}pkill steam${NC})"
echo -e "  2. ${CYAN}Start Steam${NC} - Millennium will load automatically"
echo -e "  3. In Steam, open ${CYAN}Settings > Millennium${NC} to verify it's working"
echo -e "  4. LuaTools plugin will be available in Millennium plugins list"
echo ""
echo -e "${BOLD}Component Status:${NC}"

# Summary of what's installed
# Check for actual Millennium installation
if [ -d "$HOME/.local/share/Steam/steamui/skins" ] || [ -d "$HOME/.steam/steam/steamui/skins" ] || [ -d "$HOME/.local/share/millennium/ext_storage" ] || [ -d "$HOME/.millennium/ext_storage" ]; then
    echo -e "  ${GREEN}✓${NC} Millennium"
else
    echo -e "  ${RED}✗${NC} Millennium ${YELLOW}(required - please restart Steam after install)${NC}"
fi
[ -f "$HOME/.local/share/SLSsteam/SLSsteam.so" ] && echo -e "  ${GREEN}✓${NC} SLSsteam" || echo -e "  ${RED}✗${NC} SLSsteam ${YELLOW}(required for patching)${NC}"

ACCELA_STATUS=false
for p in "$HOME/.local/share/ACCELA" "$HOME/accela"; do
    if [ -d "$p" ]; then
        echo -e "  ${GREEN}✓${NC} ACCELA (at $p)"
        ACCELA_STATUS=true
        break
    fi
done
[ "$ACCELA_STATUS" = false ] && echo -e "  ${RED}✗${NC} ACCELA ${YELLOW}(required for downloads)${NC}"

echo ""
