-- Core: event hub, guarded handlers, SavedVariables, combat queue, slash commands.
local addonName, ns = ...

ns.NAME = addonName
ns.VERSION = (C_AddOns and C_AddOns.GetAddOnMetadata and C_AddOns.GetAddOnMetadata(addonName, "Version")) or "0.0.0"
ns.MEDIA = "Interface\\AddOns\\" .. addonName .. "\\Media\\"

------------------------------------------------------------------------------------------
-- Guarded event hub: one failing handler cannot stop the others, and every error
-- reaches both the saved log and the normal error display.
------------------------------------------------------------------------------------------
local hub = CreateFrame("Frame")
local handlers = {}

function ns.Guard(label, fn, ...)
	local ok, problem = pcall(fn, ...)
	if ok then return true end
	ns.Log("ERROR %s: %s", label, tostring(problem))
	geterrorhandler()(problem)
	return false
end

function ns.On(event, fn)
	local list = handlers[event]
	if not list then
		list = {}
		handlers[event] = list
		hub:RegisterEvent(event)
	end
	list[#list + 1] = fn
end

hub:SetScript("OnEvent", function(_, event, ...)
	local list = handlers[event]
	for i = 1, #list do
		ns.Guard(event, list[i], event, ...)
	end
end)

------------------------------------------------------------------------------------------
-- Combat queue: protected work (secure frames, SetAttribute, moving/scaling secure
-- frames, override bindings) runs now if allowed, otherwise once after combat.
------------------------------------------------------------------------------------------
local afterCombat = {}

function ns.AfterCombat(key, fn, notice)
	if not InCombatLockdown() then
		return ns.Guard("now:" .. key, fn)
	end
	afterCombat[key] = fn          -- keyed: repeated requests collapse into one
	if notice then print(addonName .. ": " .. notice .. " after combat.") end   -- never fail silently
	return false
end

ns.On("PLAYER_REGEN_ENABLED", function()
	for key, fn in pairs(afterCombat) do
		afterCombat[key] = nil
		ns.Guard("after-combat:" .. key, fn)
	end
end)

------------------------------------------------------------------------------------------
-- SavedVariables: nil-checked defaults, one-way versioned migrations.
------------------------------------------------------------------------------------------
local SCHEMA = 1
local DEFAULTS = {
	enabled = true,
	scale = 1,
	point = { "CENTER", 0, -150 },
}

local function ApplyDefaults(src, dst)
	for k, v in pairs(src) do
		if type(v) == "table" then
			if type(dst[k]) ~= "table" then dst[k] = {} end
			ApplyDefaults(v, dst[k])
		elseif dst[k] == nil then           -- never `dst[k] = dst[k] or v`: it erases saved false
			dst[k] = v
		end
	end
end

-- fresh: the saved table was empty before defaults. A fresh install starts at SCHEMA and runs
-- no migration; an old save without a schema field counts as version 1 and runs all of them.
local function Migrate(db, fresh)
	local from = fresh and SCHEMA or (db.schema or 1)
	-- Example step (keep each one, add new ones below, write the reason and date):
	-- if from < 2 then db.scale = db.scale * 0.9 end   -- 2026-01-01: art was re-exported larger
	local _ = from
	db.schema = SCHEMA
end

ns.On("ADDON_LOADED", function(_, loaded)
	if loaded ~= addonName then return end
	local key = addonName .. "DB"
	_G[key] = type(_G[key]) == "table" and _G[key] or {}
	ns.db = _G[key]
	local fresh = next(ns.db) == nil
	ApplyDefaults(DEFAULTS, ns.db)
	Migrate(ns.db, fresh)
	ns.AttachLog(ns.db)
	if ns.OnReady then ns.Guard("ready", ns.OnReady) end
end)

------------------------------------------------------------------------------------------
-- Slash commands: /<addon> <command> <argument>
------------------------------------------------------------------------------------------
ns.commands = {}

function ns.Command(name, help, fn)
	ns.commands[name] = { help = help, fn = fn }
end

local function Help()
	local names = {}
	for name in pairs(ns.commands) do names[#names + 1] = name end
	table.sort(names)
	print(addonName .. " " .. ns.VERSION)
	for _, name in ipairs(names) do
		print("  /" .. addonName:lower() .. " " .. name .. " - " .. ns.commands[name].help)
	end
end

local UPPER = addonName:upper()
_G["SLASH_" .. UPPER .. "1"] = "/" .. addonName:lower()
SlashCmdList[UPPER] = function(input)
	local command, argument = strtrim(input or ""):lower():match("^(%S*)%s*(.-)$")
	local entry = ns.commands[command]
	if not entry then return Help() end
	ns.Guard("slash:" .. command, entry.fn, argument)
end
