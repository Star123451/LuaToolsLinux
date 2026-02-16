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
for cmd in git python3 pip; do
    if ! command -v "$cmd" &>/dev/null; then
        fail "'$cmd' is not installed. Please install it first."
    fi
done
ok "Required tools found (git, python3, pip)"

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
        warn "Millennium plugins directory not found."
        echo ""
        echo -e "  Is Millennium installed? Install it first:"
        echo -e "  ${CYAN}curl -fsSL https://raw.githubusercontent.com/SteamClientHomebrew/Millennium/main/scripts/install.sh | bash${NC}"
        echo ""
        read -rp "Enter your Millennium plugins path (or press Enter to use default): " custom_path
        if [ -n "$custom_path" ]; then
            MILLENNIUM_DIR="$custom_path"
        else
            MILLENNIUM_DIR="$HOME/.local/share/millennium/plugins"
        fi
        mkdir -p "$MILLENNIUM_DIR"
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

# --- Install Python dependencies ---
REQ_FILE="$INSTALL_DIR/requirements.txt"
if [ -f "$REQ_FILE" ]; then
    info "Installing Python dependencies..."
    pip install --user -r "$REQ_FILE" 2>/dev/null || pip install -r "$REQ_FILE"
    ok "Dependencies installed"
else
    warn "requirements.txt not found — skipping dependency install"
fi

# --- Check for SLSsteam ---
echo ""
if [ -f "$HOME/.local/share/SLSsteam/SLSsteam.so" ]; then
    ok "SLSsteam detected"
else
    warn "SLSsteam not found at ~/.local/share/SLSsteam/"
    echo -e "  Get it from: ${CYAN}https://github.com/AceSLS/SLSsteam${NC}"
fi

# --- Check for ACCELA ---
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
    echo -e "  Get it from: ${CYAN}https://github.com/ciscosweater/enter-the-wired${NC}"
fi

# --- Done ---
echo ""
echo -e "${GREEN}${BOLD}✓ LuaTools installed successfully!${NC}"
echo ""
echo -e "  Restart Steam for LuaTools to load."
echo -e "  If Millennium is not yet installed:"
echo -e "  ${CYAN}curl -fsSL https://raw.githubusercontent.com/SteamClientHomebrew/Millennium/main/scripts/install.sh | bash${NC}"
echo ""
