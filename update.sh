#!/usr/bin/env bash
set -euo pipefail

# ============================================
#  LuaTools Update Script (Plugin Only)
#  By StarWarsK & geovanygrdt
# ============================================

REPO_OWNER="Star123451"
REPO_NAME="LuaToolsLinux"
RELEASE_ASSET_NAME="ltsteamplugin.zip"
GITHUB_API_URL="https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest"
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

cleanup() {
    if [ -n "${TMP_DIR:-}" ] && [ -d "$TMP_DIR" ]; then
        rm -rf "$TMP_DIR"
    fi
}

extract_zip() {
    local archive_path="$1"
    local destination="$2"

    if command -v unzip &>/dev/null; then
        unzip -qo "$archive_path" -d "$destination"
        return 0
    fi

    if command -v python3 &>/dev/null; then
        python3 - "$archive_path" "$destination" <<'PY'
import sys
import zipfile

archive = sys.argv[1]
destination = sys.argv[2]

with zipfile.ZipFile(archive, "r") as zf:
    zf.extractall(destination)
PY
        return 0
    fi

    return 1
}

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   LuaTools Update Script             ║${NC}"
echo -e "${BOLD}║   (Plugin Only)                      ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""

# Check for required tools
if ! command -v curl &>/dev/null; then
    fail "'curl' is not installed. Please install it first."
fi

if ! command -v python3 &>/dev/null; then
    fail "'python3' is required to parse release metadata. Please install it first."
fi

ok "Required tools found"

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
    # Allow plugin-only install without prior setup by creating the default path.
    MILLENNIUM_DIR="$HOME/.local/share/millennium/plugins"
    mkdir -p "$MILLENNIUM_DIR"
    warn "Millennium plugins directory not detected; created $MILLENNIUM_DIR"
fi

INSTALL_DIR="$MILLENNIUM_DIR/$PLUGIN_NAME"
info "LuaTools directory: $INSTALL_DIR"

if [ ! -d "$INSTALL_DIR" ]; then
    warn "LuaTools not found at $INSTALL_DIR. Doing a fresh plugin-only install from latest release."
fi

# --- Update LuaTools from latest release ---
echo ""
info "Checking latest GitHub release..."

TMP_DIR="$(mktemp -d)"
trap cleanup EXIT
RELEASE_META_FILE="$TMP_DIR/release.json"
RELEASE_ARCHIVE_FILE="$TMP_DIR/$RELEASE_ASSET_NAME"

if ! curl -fsSL "$GITHUB_API_URL" -o "$RELEASE_META_FILE"; then
    fail "Failed to fetch latest release metadata"
fi

mapfile -t RELEASE_INFO < <(
    python3 - "$RELEASE_META_FILE" "$RELEASE_ASSET_NAME" <<'PY'
import json
import sys

meta_file = sys.argv[1]
asset_name = sys.argv[2]

with open(meta_file, "r", encoding="utf-8") as f:
    data = json.load(f)

tag = str(data.get("tag_name", "")).strip()
asset_url = ""

for asset in data.get("assets", []):
    if str(asset.get("name", "")).strip() == asset_name:
        asset_url = str(asset.get("browser_download_url", "")).strip()
        break

print(tag)
print(asset_url)
PY
)

LATEST_TAG="${RELEASE_INFO[0]:-}"
ASSET_URL="${RELEASE_INFO[1]:-}"

if [ -z "$ASSET_URL" ]; then
    fail "Could not find release asset '$RELEASE_ASSET_NAME' in latest release"
fi

if [ -n "$LATEST_TAG" ]; then
    info "Latest release: $LATEST_TAG"
fi

info "Downloading release asset: $RELEASE_ASSET_NAME"
if ! curl -fL "$ASSET_URL" -o "$RELEASE_ARCHIVE_FILE"; then
    fail "Failed to download release asset"
fi

BACKUP_DIR=""
if [ -d "$INSTALL_DIR" ]; then
    BACKUP_DIR="${INSTALL_DIR}.bak.$(date +%s)"
    mv "$INSTALL_DIR" "$BACKUP_DIR"
    warn "Backed up existing plugin to: $BACKUP_DIR"
fi

mkdir -p "$INSTALL_DIR"

if ! extract_zip "$RELEASE_ARCHIVE_FILE" "$INSTALL_DIR"; then
    rm -rf "$INSTALL_DIR"
    if [ -n "$BACKUP_DIR" ] && [ -d "$BACKUP_DIR" ]; then
        mv "$BACKUP_DIR" "$INSTALL_DIR"
        warn "Restore complete from backup due to extraction failure"
    fi
    fail "Failed to extract release archive (install aborted)"
fi

ok "Installed latest release successfully"

echo ""
echo -e "${GREEN}${BOLD}✓ Update complete!${NC}"
echo ""
echo -e "${BOLD}Next step:${NC}"
echo -e "  ${CYAN}Restart Steam${NC} for changes to take effect"
echo ""
