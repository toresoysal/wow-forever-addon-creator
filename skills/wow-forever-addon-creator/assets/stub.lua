-- wow-forever-addon-creator offline stub.
-- A hand-written stand-in for a small part of the WoW client API. It is NOT the client:
-- it only lets an addon's own Lua run outside the game. Passing here never proves that an
-- API exists or behaves this way in game. Lua 5.1.
--
-- Returns `harness`:
--   harness.combat        set true to simulate combat (InCombatLockdown, secret returns)
--   harness.fire(ev, ...) deliver an event to every frame registered for it
--   harness.update(dt)    run OnUpdate on shown frames
--   harness.flush()       run queued C_Timer callbacks
--   harness.slash(name, msg) run a slash command by its SlashCmdList key
--   harness.errors        list of captured error messages
--   harness.printed       list of printed lines
--   harness.SECRET        the secret sentinel

local harness = {
	combat = false,
	errors = {},
	printed = {},
	frames = {},
	named = {},
	timers = {},
	locale = "enUS",
	build = { "0.0.0", "00000", "Jan 1 2026", 0 },
	toc = {},          -- [field] = value, used by C_AddOns.GetAddOnMetadata
}

local function noop() end

------------------------------------------------------------------------------------------
-- Secret sentinel: every operator raises, like a secret value on a tainted path.
------------------------------------------------------------------------------------------
local function refuse()
	error("secret value used in a forbidden operation", 2)
end
local SECRET = setmetatable({}, {
	__eq = refuse, __lt = refuse, __le = refuse, __concat = refuse, __len = refuse,
	__add = refuse, __sub = refuse, __mul = refuse, __div = refuse, __mod = refuse,
	__pow = refuse, __unm = refuse, __tostring = refuse, __index = refuse, __newindex = refuse,
	__call = refuse,
})
harness.SECRET = SECRET

function issecretvalue(v) return rawequal(v, SECRET) end
function canaccessvalue(v) return not rawequal(v, SECRET) end
function scrubsecretvalues(...)
	local t = { ... }
	for i = 1, select("#", ...) do if rawequal(t[i], SECRET) then t[i] = nil end end
	return unpack(t, 1, select("#", ...))
end

local function maybeSecret(v)
	if harness.combat then return SECRET end
	return v
end

------------------------------------------------------------------------------------------
-- Output and errors
------------------------------------------------------------------------------------------
local function joinArgs(...)
	local out = {}
	for i = 1, select("#", ...) do
		local v = select(i, ...)
		out[#out + 1] = rawequal(v, SECRET) and "<secret>" or tostring(v)
	end
	return table.concat(out, " ")
end

function print(...) harness.printed[#harness.printed + 1] = joinArgs(...) end

local errorHandler = function(msg) harness.errors[#harness.errors + 1] = tostring(msg) end
function seterrorhandler(fn) errorHandler = fn end
function geterrorhandler() return errorHandler end
function debugstack() return "" end

local function report(msg)
	harness.errors[#harness.errors + 1] = tostring(msg)
end

------------------------------------------------------------------------------------------
-- Widget objects: known methods behave, unknown Capitalised methods are no-ops.
------------------------------------------------------------------------------------------
local Object = {}

-- Default return for a call nobody stubbed, guessed from its name.
local function defaultFor(key)
	if key:match("^GetNum") or key:match("Count$") then return 0 end
	if key:match("^Is") or key:match("^Has") or key:match("^Can") then return false end
	if key:match("^Create") then return harness.auto(key) end   -- C_CurveUtil.CreateCurve() etc.
	return nil
end

-- A permissive stand-in for things the stub does not know: callable like a method
-- (returns a name-based default) and indexable like a child created by an XML
-- template's parentKey (frame.Sheet:SetVertexColor(...) keeps running).
local autoMeta
local function auto(key)
	return setmetatable({ _autoKey = key }, autoMeta)
end
autoMeta = {
	__call = function(self) return defaultFor(self._autoKey) end,
	__index = function(t, k)
		if type(k) ~= "string" then return nil end
		local v = auto(k)
		rawset(t, k, v)
		return v
	end,
}
harness.auto = auto

local ObjectMeta = {
	__index = function(t, key)
		local m = Object[key]
		if m ~= nil then return m end
		if type(key) == "string" and key:match("^[A-Z]") then
			local v = auto(key)
			rawset(t, key, v)
			return v
		end
		return nil
	end,
}

local function newObject(kind, name, parent)
	local o = setmetatable({
		_kind = kind, _name = name, _parent = parent, _shown = true, _scripts = {},
		_events = {}, _w = 100, _h = 20, _scale = 1, _alpha = 1, _text = "", _value = 0,
	}, ObjectMeta)
	return o
end

function Object:GetObjectType() return self._kind end
function Object:IsObjectType(t) return self._kind == t end
function Object:GetName() return self._name end
function Object:GetParent() return self._parent end
function Object:SetParent(p) self._parent = p end
function Object:Show() harness.protectedChange(self, "Show") self._shown = true end
function Object:Hide() harness.protectedChange(self, "Hide") self._shown = false end
function Object:SetShown(v) self._shown = not not v end
function Object:IsShown() return self._shown end
function Object:IsVisible() return self._shown end
function Object:SetSize(w, h) self._w, self._h = w, h end
function Object:SetWidth(w) self._w = w end
function Object:SetHeight(h) self._h = h end
function Object:GetWidth() return self._w end
function Object:GetHeight() return self._h end
function Object:GetSize() return self._w, self._h end
function Object:SetScale(s) harness.protectedChange(self, "SetScale") self._scale = s end
function Object:GetScale() return self._scale end
function Object:GetEffectiveScale() return self._scale end
function Object:SetAlpha(a) self._alpha = a end
function Object:GetAlpha() return self._alpha end
function Object:SetText(t) self._text = t end
function Object:GetText() return self._text end
function Object:SetFormattedText(fmt, ...)
	local ok, res = pcall(string.format, fmt, ...)
	self._text = ok and res or fmt
end
function Object:GetStringWidth() return 50 end
function Object:SetValue(v) self._value = v end
function Object:GetValue() return self._value end
function Object:SetMinMaxValues(a, b) self._min, self._max = a, b end
function Object:GetMinMaxValues() return self._min or 0, self._max or 1 end
function Object:GetNumPoints() return 0 end
function Object:GetPoint() return "CENTER", UIParent, "CENTER", 0, 0 end
function Object:GetCenter() return 0, 0 end
function Object:GetLeft() return 0 end
function Object:GetRight() return 100 end
function Object:GetTop() return 20 end
function Object:GetBottom() return 0 end
function Object:SetFrameLevel(l) self._level = l end
function Object:GetFrameLevel() return self._level or 1 end
function Object:SetFrameStrata(s) self._strata = s end
function Object:GetFrameStrata() return self._strata or "MEDIUM" end
function Object:SetFont(path, size, flags) self._font = { path, size, flags } return true end
function Object:GetFont()
	local f = self._font or { STANDARD_TEXT_FONT, 12, "" }
	return f[1], f[2], f[3]
end
function Object:GetTitleText()
	self._title = self._title or newObject("FontString", nil, self)
	return self._title
end
function Object:GetID() return self._id or 0 end
function Object:SetID(id) self._id = id end
function Object:GetAttribute(k) return self._attr and self._attr[k] end
function Object:SetAttribute(k, v)
	harness.protectedChange(self, "SetAttribute(" .. tostring(k) .. ")")
	self._attr = self._attr or {}
	self._attr[k] = v
end

function Object:SetScript(kind, fn) self._scripts[kind] = fn end
function Object:GetScript(kind) return self._scripts[kind] end
function Object:HookScript(kind, fn)
	local old = self._scripts[kind]
	self._scripts[kind] = function(...)
		if old then old(...) end
		fn(...)
	end
end
function Object:RegisterEvent(ev) self._events[ev] = true end
function Object:RegisterUnitEvent(ev) self._events[ev] = true end
function Object:UnregisterEvent(ev) self._events[ev] = nil end
function Object:UnregisterAllEvents() self._events = {} end
function Object:IsEventRegistered(ev) return self._events[ev] == true end

local function child(self, kind)
	local c = newObject(kind, nil, self)
	return c
end
function Object:CreateTexture() return child(self, "Texture") end
function Object:CreateMaskTexture() return child(self, "MaskTexture") end
function Object:CreateFontString() return child(self, "FontString") end
function Object:CreateLine() return child(self, "Line") end
function Object:CreateAnimationGroup() return child(self, "AnimationGroup") end
function Object:CreateAnimation(kind) return child(self, kind or "Animation") end
function Object:GetStatusBarTexture()
	self._bar = self._bar or child(self, "Texture")
	return self._bar
end
function Object:GetRegions() return end
function Object:GetChildren() return end

-- Taint model (coarse): Blizzard-owned frames record any field an addon writes on them, and
-- secure frames record SetAttribute / protected changes made while harness.combat is true.
harness.blizzWrites = {}
harness.protectedInCombat = {}

local function protectedChange(self, what)
	if harness.combat and self._secure then
		harness.protectedInCombat[#harness.protectedInCombat + 1] =
			tostring(self._name or self._kind) .. ":" .. what .. " in combat"
	end
end

local function blizzardObject(kind, name, secure)
	local store = newObject(kind, name, UIParent)
	store._secure = secure
	store._blizzard = true
	local proxy = {}
	setmetatable(proxy, {
		__index = function(_, k)
			local v = rawget(store, k)
			if v ~= nil then return v end
			return ObjectMeta.__index(store, k)
		end,
		__newindex = function(_, k, v)
			if type(k) == "string" and k:sub(1, 1) ~= "_" then
				harness.blizzWrites[#harness.blizzWrites + 1] = name .. "." .. k
			end
			rawset(store, k, v)
		end,
	})
	_G[name] = proxy
	return proxy
end
harness.blizzardObject = blizzardObject
harness.protectedChange = protectedChange

function CreateFrame(kind, name, parent, template)
	local f = newObject(kind or "Frame", name, parent)
	if type(template) == "string" and template:find("Secure") then f._secure = true end
	harness.frames[#harness.frames + 1] = f
	if name then
		_G[name] = f
		harness.named[name] = true
	end
	return f
end

UIParent = newObject("Frame", "UIParent")
WorldFrame = newObject("Frame", "WorldFrame")
UIParent._w, UIParent._h = 1920, 1080
GameTooltip = newObject("GameTooltip", "GameTooltip")
DEFAULT_CHAT_FRAME = newObject("ScrollingMessageFrame", "DEFAULT_CHAT_FRAME")
function DEFAULT_CHAT_FRAME:AddMessage(msg) harness.printed[#harness.printed + 1] = tostring(msg) end
ChatFrame1 = DEFAULT_CHAT_FRAME
UISpecialFrames = {}
-- Blizzard-owned frames an addon is likely to touch. Writes onto them are recorded.
for i = 1, 12 do
	blizzardObject("CheckButton", "ActionButton" .. i, true)
	blizzardObject("CheckButton", "MultiBarBottomLeftButton" .. i, true)
	blizzardObject("CheckButton", "MultiBarBottomRightButton" .. i, true)
end
blizzardObject("Button", "PlayerFrame", true)
blizzardObject("Button", "TargetFrame", true)
blizzardObject("Frame", "MainMenuBar", false)
SlashCmdList = {}
STANDARD_TEXT_FONT = "Fonts\\FRIZQT__.TTF"

------------------------------------------------------------------------------------------
-- Event delivery, timers, updates
------------------------------------------------------------------------------------------
function harness.fire(ev, ...)
	for _, f in ipairs(harness.frames) do
		if f._events[ev] then
			local fn = f._scripts.OnEvent
			if fn then
				local ok, err = pcall(fn, f, ev, ...)
				if not ok then report(err) end
			end
		end
	end
end

function harness.update(dt)
	for _, f in ipairs(harness.frames) do
		local fn = f._scripts.OnUpdate
		if fn and f._shown then
			local ok, err = pcall(fn, f, dt or 0.1)
			if not ok then report(err) end
		end
	end
end

C_Timer = {}
function C_Timer.After(_, fn) harness.timers[#harness.timers + 1] = fn end
function C_Timer.NewTimer(_, fn)
	harness.timers[#harness.timers + 1] = fn
	return { Cancel = noop, IsCancelled = function() return false end }
end
function C_Timer.NewTicker(_, fn)
	harness.timers[#harness.timers + 1] = fn
	return { Cancel = noop, IsCancelled = function() return false end }
end
function harness.flush()
	for _ = 1, 10 do                       -- timers may queue more timers
		local list = harness.timers
		if #list == 0 then return end
		harness.timers = {}
		for _, fn in ipairs(list) do
			local ok, err = pcall(fn)
			if not ok then report(err) end
		end
	end
end

function harness.slash(key, msg)
	local fn = SlashCmdList[key]
	if not fn then return false end
	local ok, err = pcall(fn, msg or "", DEFAULT_CHAT_FRAME)
	if not ok then report(err) end
	return true
end

------------------------------------------------------------------------------------------
-- Combat and taint helpers
------------------------------------------------------------------------------------------
function InCombatLockdown() return harness.combat end
function issecure() return false end
function securecall(fn, ...) if type(fn) == "function" then return fn(...) end end
function securecallfunction(fn, ...) return fn(...) end

function hooksecurefunc(a, b, c)
	local tbl, name, hook = a, b, c
	if type(a) == "string" then tbl, name, hook = _G, a, b end
	local orig = tbl[name]
	if type(orig) ~= "function" then
		error("hooksecurefunc: " .. tostring(name) .. " is not a function", 2)
	end
	tbl[name] = function(...)
		local r = { orig(...) }
		hook(...)
		return unpack(r)
	end
end

------------------------------------------------------------------------------------------
-- Game API stand-ins (values are placeholders)
------------------------------------------------------------------------------------------
function GetBuildInfo() return unpack(harness.build) end
function GetLocale() return harness.locale end
function GetTime() return os.clock() end
function GetServerTime() return os.time() end
time = os.time
date = os.date
function GetFramerate() return 60 end
function GetNetStats() return 0, 0, 20, 20 end
function IsLoggedIn() return true end
function GetCVar() return "0" end
function SetCVar() end

C_AddOns = {}
function C_AddOns.GetAddOnMetadata(_, field) return harness.toc[field] end
function C_AddOns.IsAddOnLoaded() return false end
function C_AddOns.GetAddOnInfo(name) return name, name, "", true, "INSECURE", false end
C_CVar = { GetCVar = function() return "0" end, SetCVar = noop, GetCVarBool = function() return false end }

function UnitExists(u) return u == "player" or u == "pet" or u == "target" end
function UnitName() return "Tester", nil end
function GetUnitName() return "Tester" end
function UnitGUID(u) return "Player-0000-00000000" .. tostring(u) end
function UnitClass() return "Warlock", "WARLOCK", 9 end
function UnitRace() return "Orc", "Orc", 2 end
function UnitLevel() return 60 end
function UnitIsDeadOrGhost() return false end
function UnitCanAttack(a, b) return a == "player" and b == "target" end
function UnitIsFriend(a, b) return not (a == "player" and b == "target") end
function UnitAffectingCombat() return harness.combat end
function UnitOnTaxi() return false end
function UnitHealth() return maybeSecret(800) end
function UnitHealthMax() return maybeSecret(1000) end
function UnitPower() return maybeSecret(500) end
function UnitPowerMax() return maybeSecret(1000) end
function UnitPowerType() return 0, "MANA" end
function UnitHealthPercent() return maybeSecret(0.8) end
function UnitPowerPercent() return maybeSecret(0.5) end
function UnitCastingInfo() return nil end
function UnitChannelInfo() return nil end
function UnitCastingDuration() return nil end
function UnitChannelDuration() return nil end
function GetSpecialization() return 1 end
function BreakUpLargeNumbers(v) if rawequal(v, SECRET) then return SECRET end return tostring(v) end
function AbbreviateNumbers(v) return BreakUpLargeNumbers(v) end

C_Spell = {}
function C_Spell.GetSpellInfo(id) return { name = "Spell" .. tostring(id), spellID = id, iconID = 136243, castTime = 0 } end
function C_Spell.GetSpellName(id) return "Spell" .. tostring(id) end
function C_Spell.GetSpellTexture() return 136243 end
function C_Spell.GetSpellCooldown()
	return { startTime = maybeSecret(0), duration = maybeSecret(0), isEnabled = true, modRate = 1, isActive = false, isOnGCD = false }
end
function C_Spell.GetSpellCooldownDuration() return nil end
C_UnitAuras = {}
function C_UnitAuras.GetAuraDataByIndex(_, i)
	if i ~= 1 then return nil end
	return { name = maybeSecret("Aura"), spellId = maybeSecret(1), duration = maybeSecret(10),
		expirationTime = maybeSecret(100), applications = maybeSecret(1), icon = 136243 }
end
C_UnitAuras.GetBuffDataByIndex = function(u, i) return C_UnitAuras.GetAuraDataByIndex(u, i) end
C_UnitAuras.GetDebuffDataByIndex = function(u, i) return C_UnitAuras.GetAuraDataByIndex(u, i) end

function CreateColor(r, g, b, a)
	return { r = r, g = g, b = b, a = a or 1, GetRGB = function(s) return s.r, s.g, s.b end,
		GetRGBA = function(s) return s.r, s.g, s.b, s.a end }
end

------------------------------------------------------------------------------------------
-- WoW Lua globals that are not in plain Lua 5.1
------------------------------------------------------------------------------------------
strfind, strsub, strlen, strupper, strlower, strrep, strbyte, strchar, strmatch, gsub, format =
	string.find, string.sub, string.len, string.upper, string.lower, string.rep, string.byte,
	string.char, string.match, string.gsub, string.format
strtrim = function(s, chars)
	chars = chars or "%s"
	return (s:gsub("^[" .. chars .. "]+", ""):gsub("[" .. chars .. "]+$", ""))
end
strsplit = function(sep, s, n)
	local out, pattern, i = {}, "([^" .. sep .. "]*)", 0
	for piece in (s .. sep):gmatch("([^" .. sep .. "]*)" .. sep) do
		i = i + 1
		out[i] = piece
		if n and i == n - 1 then break end
	end
	return unpack(out)
end
strjoin = function(sep, ...) return table.concat({ ... }, sep) end
tinsert, tremove, wipe = table.insert, table.remove, function(t) for k in pairs(t) do t[k] = nil end return t end
tContains = function(t, v) for _, x in pairs(t) do if x == v then return true end end return false end
CopyTable = function(t)
	local c = {}
	for k, v in pairs(t) do c[k] = type(v) == "table" and CopyTable(v) or v end
	return c
end
Mixin = function(o, ...) for i = 1, select("#", ...) do for k, v in pairs((select(i, ...))) do o[k] = v end end return o end
CreateFromMixins = function(...) return Mixin({}, ...) end
floor, ceil, abs, min, max, sqrt, random = math.floor, math.ceil, math.abs, math.min, math.max, math.sqrt, math.random

------------------------------------------------------------------------------------------
-- Unknown C_* namespaces and Enum: return permissive placeholders so logic runs.
-- API existence is checked by a different gate (against the client source), not here.
------------------------------------------------------------------------------------------
local function autoNamespace()
	return setmetatable({}, {
		__index = function(t, k)
			local v = type(k) == "string" and auto(k) or nil
			rawset(t, k, v)
			return v
		end,
	})
end
Enum = setmetatable({}, {
	__index = function(t, k)
		local sub = setmetatable({}, { __index = function(s, kk) rawset(s, kk, 0) return 0 end })
		rawset(t, k, sub)
		return sub
	end,
})
Settings = autoNamespace()
EditModeManagerFrame = newObject("Frame", "EditModeManagerFrame")
PlayerCastingBarFrame = newObject("StatusBar", "PlayerCastingBarFrame")

setmetatable(_G, {
	__index = function(t, k)
		if type(k) == "string" and k:match("^C_%u") then
			local ns = autoNamespace()
			rawset(t, k, ns)
			harness.autoNamespaces = harness.autoNamespaces or {}
			harness.autoNamespaces[k] = true
			return ns
		end
		return nil
	end,
})

return harness
