#!/usr/bin/env bash
set -uo pipefail

# ============================================
#  LuaTools Update Script (Plugin Only)
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
echo -e "${BOLD}║   LuaTools Update Script             ║${NC}"
echo -e "${BOLD}║   (Plugin Only)                      ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""

# Check for git
if ! command -v git &>/dev/null; then
    fail "'git' is not installed. Please install it first."
fi
ok "Git found"

# Find the plugins directory
candidates=(
    "$HOME/.local/share/millennium/plugins"
    "$HOME/.millennium/plugins"
    "$HOME/.steam/steam/millennium/plugins"
    "$HOME/.local/share/Steam/millennium/plugins"
)

MILLENNIUM_DIR=""
for dir in "${candidates[@]}"; do
    if [ -d "$dir" ]; then
        MILLENNIUM_DIR="$dir"
        break
    fi
done

if [ -z "$MILLENNIUM_DIR" ]; then
    fail "Could not find Millennium plugins directory. Is Millennium installed?"
fi

INSTALL_DIR="$MILLENNIUM_DIR/$PLUGIN_NAME"
info "LuaTools directory: $INSTALL_DIR"

if [ ! -d "$INSTALL_DIR" ]; then
    fail "LuaTools not found at $INSTALL_DIR. Please run install.sh first."
fi

# --- Update LuaTools ---
echo ""
info "Updating LuaTools..."
cd "$INSTALL_DIR"

if [ -d ".git" ]; then
    if git pull --ff-only origin "$BRANCH"; then
        ok "Updated to latest version"
    else
        warn "Fast-forward pull failed. Doing a clean re-clone..."
        cd ..
        rm -rf "$INSTALL_DIR"
        if git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"; then
            ok "Clean re-clone complete"
        else
            fail "Failed to clone repository"
        fi
    fi
else
    warn "Not a git repository. Backing up and re-installing..."
    cd ..
    mv "$INSTALL_DIR" "${INSTALL_DIR}.bak.$(date +%s)"
    if git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"; then
        ok "Fresh install complete (old files backed up)"
    else
        fail "Failed to clone repository"
    fi
fi

echo ""
echo -e "${GREEN}${BOLD}✓ Update complete!${NC}"
echo ""
echo -e "${BOLD}Next step:${NC}"
echo -e "  ${CYAN}Restart Steam${NC} for changes to take effect"
echo ""
