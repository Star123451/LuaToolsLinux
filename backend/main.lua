--!nocheck
--^ lets not have the IDE scream in our faces as we develop this

local millennium = require("millennium") -- https://docs.steambrew.app/plugins/lua/millennium
local logger = require("logger") -- https://docs.steambrew.app/plugins/lua/logger
local fs = require("fs") -- https://docs.steambrew.app/plugins/lua/fs
local utils = require("utils") -- https://docs.steambrew.app/plugins/lua/utils

local function load_luatools_script()
	local steam_path = millennium.steam_path()
	local steamui_path = fs.join(steam_path, "steamui")
	local luatools_ui_path = fs.join(steamui_path, "LuaTools")

	local backend_path = utils.get_backend_path()
	local plugin_path = fs.parent_path(backend_path)
	local public_path = fs.join(plugin_path, "public")

	logger:info("steam: " .. steam_path)
	logger:info("steam ui: " .. steamui_path)
	logger:info("luatools ui: " .. luatools_ui_path)
	logger:info("backend: " .. backend_path)
	logger:info("plugin: " .. plugin_path)
	logger:info("public: " .. public_path)

	if not fs.exists(steamui_path) then
		logger:info(steamui_path .. " could not be found, creating it now..")

		local ok, err = fs.create_directory(steamui_path)
		if not ok then
			logger:error("Failed to create directory " .. steam_path .. " " .. err)
		end
	end

	local ok = fs.copy(fs.join(public_path, "luatools.js"), fs.join(luatools_ui_path, "luatools.js"))
	if not ok then
		logger:error("Failed to copy luatools.js script to steamui")
	end

	if not fs.exists(luatools_ui_path) then
		logger:info(luatools_ui_path .. " could not be found, creating it now..")

		local ok, err = fs.create_directory(luatools_ui_path)
		if not ok then
			logger:error("Failed to create directory " .. steam_path .. " " .. err)
		end
	end

	local module_id = millennium.add_browser_js("LuaTools/luatools.js")
	if module_id == 0 then
		logger:error("luatools.js script failed to load")
	else
		logger:info("luatools.js script loaded successfully (id: " .. module_id .. ")")
	end
end

local function on_load()
	logger:info("") -- little debug line, just separates the logs by each reload for easier readability

	load_luatools_script()

	millennium.ready()
end

return {
	on_load = on_load,
}
