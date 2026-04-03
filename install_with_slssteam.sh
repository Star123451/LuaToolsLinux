#!/usr/bin/env bash
set -euo pipefail

REPO_OWNER="Star123451"
REPO_NAME="LuaToolsLinux"
BRANCH="main"

INSTALL_ROOT="$HOME/.local/share/LuaToolsLinux"
VENV_DIR="$INSTALL_ROOT/.venv"
BIN_DIR="$HOME/.local/bin"
WRAPPER_PATH="$BIN_DIR/luatools"
BRIDGE_STARTER="$BIN_DIR/luatools-bridge"
UI_HEALER="$BIN_DIR/luatools-heal-ui"
TMP_DIR=""

info() { echo "[LuaTools] $*"; }
warn() { echo "[LuaTools][WARN] $*"; }
fail() { echo "[LuaTools][FAIL] $*"; exit 1; }

cleanup() {
    if [ -n "${TMP_DIR:-}" ] && [ -d "$TMP_DIR" ]; then
        rm -rf "$TMP_DIR"
    fi
}

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

    TMP_DIR="$(mktemp -d)"
    trap cleanup EXIT

    local archive="$TMP_DIR/luatools.zip"
    local src="$TMP_DIR/src"
    local zip_url="https://codeload.github.com/${REPO_OWNER}/${REPO_NAME}/zip/refs/heads/${BRANCH}"

    info "Downloading LuaTools bundle from ${REPO_OWNER}/${REPO_NAME}@${BRANCH}"
    curl -fsSL "$zip_url" -o "$archive"

    mkdir -p "$src"
    if ! extract_zip "$archive" "$src"; then
        fail "Could not extract LuaTools archive"
    fi

    local extracted
    extracted="$(find "$src" -maxdepth 1 -type d -name "${REPO_NAME}-*" | head -n 1)"
    [[ -n "$extracted" ]] || fail "Extracted content not found"

    mkdir -p "$INSTALL_ROOT"
    rm -rf "$INSTALL_ROOT/backend" "$INSTALL_ROOT/public"

    cp -r "$extracted/backend" "$INSTALL_ROOT/backend"
    cp -r "$extracted/public" "$INSTALL_ROOT/public"
    cp "$extracted/requirements.txt" "$INSTALL_ROOT/requirements.txt"
    cp "$extracted/README.md" "$INSTALL_ROOT/README.md"

    info "Installing Python dependencies"
    local python_bin="python3"
    if python3 -m venv "$VENV_DIR" >/dev/null 2>&1; then
        python_bin="$VENV_DIR/bin/python"
    else
        warn "Could not create a local virtualenv; falling back to user-site pip install."
    fi

    if ! "$python_bin" -m pip install -r "$INSTALL_ROOT/requirements.txt" >/dev/null 2>&1; then
        if [[ "$python_bin" != "python3" ]]; then
            warn "Virtualenv pip install failed; retrying with user-site pip."
            if ! python3 -m pip install --user -r "$INSTALL_ROOT/requirements.txt" >/dev/null 2>&1; then
                fail "Python dependency install failed"
            fi
            python_bin="python3"
        else
            fail "Python dependency install failed"
        fi
    fi

    mkdir -p "$BIN_DIR"
    cat > "$WRAPPER_PATH" <<EOF
#!/usr/bin/env bash
PYTHON_BIN="$VENV_DIR/bin/python"
if [[ ! -x "\$PYTHON_BIN" ]]; then
    PYTHON_BIN=python3
fi
exec "\$PYTHON_BIN" "$INSTALL_ROOT/backend/standalone_cli.py" "\$@"
EOF
    chmod +x "$WRAPPER_PATH"

    cat > "$BRIDGE_STARTER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
PYTHON_BIN="$VENV_DIR/bin/python"
if [[ ! -x "\$PYTHON_BIN" ]]; then
    PYTHON_BIN=python3
fi
BRIDGE_HOST="127.0.0.1"
BRIDGE_PORT="38495"
LOG_FILE="\${XDG_STATE_HOME:-\$HOME/.local/state}/luatools/bridge.log"
PID_FILE="\${XDG_RUNTIME_DIR:-/tmp}/luatools-bridge.pid"
mkdir -p "\$(dirname "\$LOG_FILE")"

if [[ -f "\$PID_FILE" ]]; then
    if kill -0 "\$(cat "\$PID_FILE")" >/dev/null 2>&1; then
        exit 0
    fi
    rm -f "\$PID_FILE"
fi

nohup "\$PYTHON_BIN" "$INSTALL_ROOT/backend/web_bridge_server.py" --host "\$BRIDGE_HOST" --port "\$BRIDGE_PORT" >>"\$LOG_FILE" 2>&1 &
echo "\$!" > "\$PID_FILE"

health_url="http://\$BRIDGE_HOST:\$BRIDGE_PORT/health"
for _ in 1 2 3 4 5; do
    if "\$PYTHON_BIN" - "\$health_url" <<'PY' >/dev/null 2>&1; then
import sys
import urllib.request

url = sys.argv[1]
with urllib.request.urlopen(url, timeout=1) as response:
    if response.status != 200:
        raise SystemExit(1)
PY
        echo "LuaTools bridge ready at \$health_url"
        exit 0
    fi
    sleep 1
done

echo "LuaTools bridge started but is not reachable at \$health_url" >&2
echo "Check \$LOG_FILE for details." >&2
exit 1
EOF
    chmod +x "$BRIDGE_STARTER"

    cat > "$UI_HEALER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
PYTHON_BIN="$VENV_DIR/bin/python"
if [[ ! -x "\$PYTHON_BIN" ]]; then
    PYTHON_BIN=python3
fi
export LUATOOLS_INSTALL_ROOT="$INSTALL_ROOT"
exec "\$PYTHON_BIN" "$INSTALL_ROOT/backend/ui_injector.py"
EOF
    chmod +x "$UI_HEALER"

    local ui_output=""
    if ! ui_output="$($UI_HEALER 2>&1)"; then
        warn "UI self-heal step failed"
        if [ -n "$ui_output" ]; then
            warn "$ui_output"
        fi
    elif [ -n "$ui_output" ]; then
        info "$ui_output"
    fi

    info "LuaTools standalone installed"
    info "CLI wrapper: $WRAPPER_PATH"
    info "Bridge starter: $BRIDGE_STARTER"
    info "UI healer: $UI_HEALER"
    info "Example: luatools init-apis"
}

main "$@"
