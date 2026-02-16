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

# --- Check for build tools (needed for SLSsteam) ---
if ! command -v make &>/dev/null || ! command -v gcc &>/dev/null; then
    info "Build tools (make/gcc) not found - needed for SLSsteam installation"
    echo -e "  You can install them with: ${CYAN}sudo apt install build-essential${NC}"
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
    local slssteam_dir="$HOME/.local/share/SLSsteam"
    
    # Check for required build tools
    if ! command -v make &>/dev/null; then
        warn "make not found - required to build SLSsteam"
        echo -e "  Install with: ${CYAN}sudo apt install build-essential${NC}"
        return 1
    fi
    
    # Clone and build
    local temp_dir=$(mktemp -d)
    cd "$temp_dir"
    
    if git clone https://github.com/AceSLS/SLSsteam.git; then
        cd SLSsteam
        if make; then
            mkdir -p "$slssteam_dir"
            cp SLSsteam.so "$slssteam_dir/"
            chmod +x "$slssteam_dir/SLSsteam.so"
            cd
            rm -rf "$temp_dir"
            ok "SLSsteam installed to $slssteam_dir"
            return 0
        else
            warn "SLSsteam build failed"
            cd
            rm -rf "$temp_dir"
            return 1
        fi
    else
        warn "Failed to clone SLSsteam repository"
        cd
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

# --- Detect Millennium plugins directory ---
MILLENNIUM_DIR=""

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

if [ -z "$MILLENNIUM_DIR" ]; then
    # Check if Millennium is installed at all
    if [ -d "$HOME/.local/share/millennium" ]; then
        MILLENNIUM_DIR="$HOME/.local/share/millennium/plugins"
        mkdir -p "$MILLENNIUM_DIR"
    elif [ -d "$HOME/.millennium" ]; then
        MILLENNIUM_DIR="$HOME/.millennium/plugins"
        mkdir -p "$MILLENNIUM_DIR"
    else
        warn "Millennium not found."
        echo ""
        read -rp "Install Millennium now? [Y/n] " -n 1 response
        echo ""
        if [[ ! "$response" =~ ^[Nn]$ ]]; then
            if install_millennium; then
                # Re-check for Millennium directory
                for dir in "${candidates[@]}"; do
                    if [ -d "$dir" ]; then
                        MILLENNIUM_DIR="$dir"
                        break
                    fi
                done
            fi
        fi
        
        # If still not found, use default
        if [ -z "$MILLENNIUM_DIR" ]; then
            MILLENNIUM_DIR="$HOME/.local/share/millennium/plugins"
            mkdir -p "$MILLENNIUM_DIR"
            info "Using default directory: $MILLENNIUM_DIR"
        fi
    fi
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

# --- Install/Check for SLSsteam ---
echo ""
if [ -f "$HOME/.local/share/SLSsteam/SLSsteam.so" ]; then
    ok "SLSsteam detected"
else
    warn "SLSsteam not found"
    read -rp "Install SLSsteam now? [Y/n] " -n 1 response
    echo ""
    if [[ ! "$response" =~ ^[Nn]$ ]]; then
        install_slssteam || echo -e "  ${YELLOW}Manual install:${NC} ${CYAN}https://github.com/AceSLS/SLSsteam${NC}"
    fi
fi

# --- Install/Check for ACCELA ---
ACCELA_FOUND=false
for p in "$HOME/.local/share/ACCELA" "$HOME/accela"; do
    if [ -d "$p" ]; then
        ok "ACCELA detected at $p"
        ACCELA_FOUND=true
        break
    fi
done
if [ "$ACCELA_FOUND" = false ]; then
    warn "ACCELA not found"
    read -rp "Install ACCELA now? [Y/n] " -n 1 response
    echo ""
    if [[ ! "$response" =~ ^[Nn]$ ]]; then
        install_accela || echo -e "  ${YELLOW}Manual install:${NC} ${CYAN}https://github.com/ciscosweater/enter-the-wired${NC}"
    fi
fi

# --- Done ---
echo ""
echo -e "${GREEN}${BOLD}✓ Installation complete!${NC}"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo -e "  1. Restart Steam for changes to take effect"
echo -e "  2. LuaTools will load automatically via Millennium"
echo ""
echo -e "${BOLD}Component Status:${NC}"

# Summary of what's installed
[ -d "$MILLENNIUM_DIR" ] && echo -e "  ${GREEN}✓${NC} Millennium" || echo -e "  ${RED}✗${NC} Millennium ${YELLOW}(required)${NC}"
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
