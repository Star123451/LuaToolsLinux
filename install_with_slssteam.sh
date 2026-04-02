#!/usr/bin/env bash
set -euo pipefail

REPO_OWNER="Star123451"
REPO_NAME="LuaToolsLinux"
BRANCH="main"

INSTALL_ROOT="$HOME/.local/share/LuaToolsLinux"
BIN_DIR="$HOME/.local/bin"
WRAPPER_PATH="$BIN_DIR/luatools"
BRIDGE_STARTER="$BIN_DIR/luatools-bridge"
UI_HEALER="$BIN_DIR/luatools-heal-ui"

info() { echo "[LuaTools] $*"; }
warn() { echo "[LuaTools][WARN] $*"; }
fail() { echo "[LuaTools][FAIL] $*"; exit 1; }

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

extract_zip() {
    local archive="$1"
    local dest="$2"

    if command -v unzip >/dev/null 2>&1; then
        unzip -qo "$archive" -d "$dest"
        return 0
    fi

    if command -v python3 >/dev/null 2>&1; then
        python3 - "$archive" "$dest" <<'PY'
import sys
import zipfile

archive = sys.argv[1]
dest = sys.argv[2]

with zipfile.ZipFile(archive, "r") as zf:
    zf.extractall(dest)
PY
        return 0
    fi

    return 1
}

main() {
    require_cmd curl
    require_cmd python3

    local tmp
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT

    local archive="$tmp/luatools.zip"
    local src="$tmp/src"
    local zip_url="https://codeload.github.com/${REPO_OWNER}/${REPO_NAME}/zip/refs/heads/${BRANCH}"

    info "Downloading LuaTools bundle from ${REPO_OWNER}/${REPO_NAME}@${BRANCH}"
    curl -fsSL "$zip_url" -o "$archive"

    mkdir -p "$src"
    if ! extract_zip "$archive" "$src"; then
        fail "Could not extract LuaTools archive"
    fi

    local extracted
    extracted="$(find "$src" -maxdepth 1 -type d -name '${REPO_NAME}-*' | head -n 1)"
    [[ -n "$extracted" ]] || fail "Extracted content not found"

    mkdir -p "$INSTALL_ROOT"
    rm -rf "$INSTALL_ROOT/backend" "$INSTALL_ROOT/public"

    cp -r "$extracted/backend" "$INSTALL_ROOT/backend"
    cp -r "$extracted/public" "$INSTALL_ROOT/public"
    cp "$extracted/requirements.txt" "$INSTALL_ROOT/requirements.txt"
    cp "$extracted/README.md" "$INSTALL_ROOT/README.md"

    info "Installing Python dependencies"
    if ! python3 -m pip install --user -r "$INSTALL_ROOT/requirements.txt" >/dev/null 2>&1; then
        warn "pip dependency install failed. You can retry manually with:"
        warn "python3 -m pip install --user -r $INSTALL_ROOT/requirements.txt"
    fi

    mkdir -p "$BIN_DIR"
    cat > "$WRAPPER_PATH" <<EOF
#!/usr/bin/env bash
exec python3 "$INSTALL_ROOT/backend/standalone_cli.py" "\$@"
EOF
    chmod +x "$WRAPPER_PATH"

    cat > "$BRIDGE_STARTER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="\${XDG_STATE_HOME:-\$HOME/.local/state}/luatools/bridge.log"
PID_FILE="\${XDG_RUNTIME_DIR:-/tmp}/luatools-bridge.pid"
mkdir -p "\$(dirname "\$LOG_FILE")"

if [[ -f "\$PID_FILE" ]]; then
    if kill -0 "\$(cat "\$PID_FILE")" >/dev/null 2>&1; then
        exit 0
    fi
    rm -f "\$PID_FILE"
fi

nohup python3 "$INSTALL_ROOT/backend/web_bridge_server.py" --host 127.0.0.1 --port 38495 >>"\$LOG_FILE" 2>&1 &
echo "\$!" > "\$PID_FILE"
EOF
    chmod +x "$BRIDGE_STARTER"

    cat > "$UI_HEALER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export LUATOOLS_INSTALL_ROOT="$INSTALL_ROOT"
exec python3 "$INSTALL_ROOT/backend/ui_injector.py"
EOF
    chmod +x "$UI_HEALER"

    "$UI_HEALER" >/dev/null 2>&1 || warn "UI self-heal step failed"

    info "LuaTools standalone installed"
    info "CLI wrapper: $WRAPPER_PATH"
    info "Bridge starter: $BRIDGE_STARTER"
    info "UI healer: $UI_HEALER"
    info "Example: luatools init-apis"
}

main "$@"
