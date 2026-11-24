-- Example feature: a movable player-health readout that is safe with secret values.
-- Replace with the real feature; keep the patterns.
local _, ns = ...

local frame

local function Build()
	frame = CreateFrame("Frame", nil, UIParent)
	frame:SetSize(160, 24)
	local p = ns.db.point
	frame:SetPoint(p[1], UIParent, p[1], p[2], p[3])
	frame:SetScale(ns.db.scale)

	frame.text = frame:CreateFontString(nil, "OVERLAY", "GameFontNormal")
	frame.text:SetAllPoints()

	frame:SetMovable(true)
	frame:SetClampedToScreen(true)
	frame:RegisterForDrag("LeftButton")
	frame:SetScript("OnDragStart", function(self)
		if not InCombatLockdown() then self:StartMoving() end
	end)
	frame:SetScript("OnDragStop", function(self)
		self:StopMovingOrSizing()
		local point, _, _, x, y = self:GetPoint()
		ns.db.point = { point or "CENTER", x or 0, y or 0 }
	end)
end

local function Plain(v)
	return v ~= nil and not (issecretvalue and issecretvalue(v))
end

local function Refresh()
	if not frame then return end
	local hp = UnitHealth("player")
	-- The game formats a secret number itself; never `"HP " .. hp` or `hp < x` on a secret.
	frame.text:SetFormattedText("HP %s", BreakUpLargeNumbers(hp))
	if Plain(hp) and hp == 0 then
		frame.text:SetTextColor(1, 0.2, 0.2)
	else
		frame.text:SetTextColor(1, 1, 1)
	end
end

function ns.OnReady()
	Build()                                   -- essential part first
	Refresh()
	frame:SetShown(ns.db.enabled)
end

local unitFrame = CreateFrame("Frame")
unitFrame:RegisterUnitEvent("UNIT_HEALTH", "player")
unitFrame:RegisterUnitEvent("UNIT_MAXHEALTH", "player")
unitFrame:SetScript("OnEvent", function() ns.Guard("refresh", Refresh) end)
ns.On("PLAYER_ENTERING_WORLD", function() Refresh() end)   -- fires on every loading screen

ns.Command("toggle", "show or hide the readout", function()
	ns.db.enabled = not ns.db.enabled
	if frame then frame:SetShown(ns.db.enabled) end
end)

ns.Command("scale", "set scale, e.g. 1.2", function(arg)
	local v = tonumber(arg)
	if not v then return print("usage: scale <0.5-3>") end
	v = math.floor(math.max(0.5, math.min(3, v)) * 100 + 0.5) / 100
	ns.db.scale = v
	-- This frame is not secure, so SetScale is allowed in combat. For a secure frame (action
	-- button, unit button) use: ns.AfterCombat("scale", function() frame:SetScale(v) end, "scale applies")
	if frame then frame:SetScale(v) end
end)
