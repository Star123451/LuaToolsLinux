local millennium = require("millennium")
local fs = require("fs")
local logger = require("logger")

local function write_file(path, content)
    local f = io.open(path, "w")
    if not f then
        logger:warn("LuaTools: failed to write " .. path)
        return false
    end
    f:write(content)
    f:close()
    return true
end

local function find_plugin_dir()
    local home = os.getenv("HOME") or ""
    local candidates = {
        fs.join(home, ".local", "share", "millennium", "plugins", "luatools"),
        fs.join(millennium.get_install_path(), "plugins", "luatools"),
    }
    for _, dir in ipairs(candidates) do
        if fs.exists(fs.join(dir, "public", "luatools.js")) then
            return dir
        end
    end
    return candidates[1]
end

local function on_load()
    local steam_path = millennium.steam_path():gsub("/+$", "")
    local plugin_dir = find_plugin_dir()
    logger:info("LuaTools: plugin_dir=" .. plugin_dir)

    local dest_dir = fs.join(steam_path, "steamui", "LuaTools")
    if not fs.exists(dest_dir) then
        local ok, err = fs.create_directories(dest_dir)
        if not ok then
            logger:warn("LuaTools: failed to create " .. dest_dir .. ": " .. (err or "unknown"))
        end
    end

    local src_js = fs.join(plugin_dir, "public", "luatools.js")
    local dst_js = fs.join(dest_dir, "luatools.js")
    if fs.exists(src_js) then
        local ok2, err2 = fs.copy(src_js, dst_js, false)
        if not ok2 then
            logger:warn("LuaTools: copy failed: " .. (err2 or "unknown"))
        end
    end

    local src_icon = fs.join(plugin_dir, "public", "luatools-icon.png")
    local dst_icon = fs.join(dest_dir, "luatools-icon.png")
    if fs.exists(src_icon) then
        fs.copy(src_icon, dst_icon, false)
    end

    local src_themes = fs.join(plugin_dir, "public", "themes")
    local dst_themes = fs.join(dest_dir, "themes")
    if fs.exists(src_themes) then
        fs.copy_recursive(src_themes, dst_themes, false)
    end

    local bridge_path = fs.join(dest_dir, "luatools_bridge.js")
    local bridge_js = [[
(function(){
    if (typeof window === 'undefined') return;
    window.Millennium = window.Millennium || {};
    window.Millennium.callServerMethod = function(plugin, method, args) {
        var payload = {
            method: String(method || ''),
            args: (args && typeof args === 'object') ? args : {}
        };
        return fetch('http://127.0.0.1:38495/rpc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(function(res) {
            if (!res || !res.ok) {
                throw new Error('LuaTools bridge unavailable');
            }
            return res.json();
        }).then(function(body) {
            if (!body || body.success !== true) {
                throw new Error((body && body.error) ? String(body.error) : 'RPC failed');
            }
            return body.result;
        });
    };
})();
]]
    write_file(bridge_path, bridge_js)

    millennium.add_browser_js("LuaTools/luatools_bridge.js")
    millennium.add_browser_js("LuaTools/luatools.js")

    local venv_dir = fs.join(plugin_dir, ".venv")
    local venv_python = fs.join(venv_dir, "bin", "python3")
    if not fs.exists(venv_python) then
        logger:info("LuaTools: creating venv...")
        os.execute("python3 -m venv " .. venv_dir .. " 2>&1")
    end
    if fs.exists(venv_python) then
        local requirements = fs.join(plugin_dir, "requirements.txt")
        if fs.exists(requirements) then
            local pip_cmd = venv_python .. " -m pip install -r " .. requirements .. " --quiet --disable-pip-version-check 2>&1"
            local pip_rc = os.execute(pip_cmd)
            if not pip_rc then
                logger:warn("LuaTools: pip install failed: " .. tostring(pip_rc))
            end
        end
    end

    local bridge_py = fs.join(plugin_dir, "backend", "web_bridge_server.py")
    if fs.exists(bridge_py) then
        local python_exe = fs.exists(venv_python) and venv_python or "python3"
        local cmd = python_exe .. " " .. bridge_py .. " > /dev/null 2>&1 &"
        os.execute(cmd)
        logger:info("LuaTools bridge started with " .. python_exe .. ", Millennium " .. millennium.version())
    else
        logger:warn("LuaTools: bridge script not found at " .. bridge_py)
    end

    millennium.ready()
end

local function on_unload()
    os.execute("pkill -f web_bridge_server.py 2>/dev/null || true")
    logger:info("LuaTools unloaded")
end

return {
    on_load = on_load,
    on_unload = on_unload
}
