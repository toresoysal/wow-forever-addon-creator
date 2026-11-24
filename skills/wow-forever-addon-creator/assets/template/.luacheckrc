-- Add a name to read_globals only after confirming it exists in the target client's
-- Blizzard UI source (or API docs) for the client this addon ships to.
std = "lua51"
max_line_length = false
codes = true
exclude_files = { "Libs/", ".release/" }
ignore = { "212" }   -- unused argument (event handlers receive many)

globals = {
	"__NAME__DB", "SLASH___UPPER__1", "SlashCmdList",
}

read_globals = {
	-- Lua / WoW Lua extensions
	"date", "strtrim", "strsplit", "tinsert", "tremove", "wipe",
	-- frames and widgets
	"CreateFrame", "UIParent", "GameTooltip", "UISpecialFrames", "STANDARD_TEXT_FONT",
	-- API
	"C_AddOns", "C_Timer", "InCombatLockdown", "hooksecurefunc", "issecretvalue",
	"geterrorhandler", "seterrorhandler", "UnitHealth", "UnitHealthMax", "BreakUpLargeNumbers",
}
