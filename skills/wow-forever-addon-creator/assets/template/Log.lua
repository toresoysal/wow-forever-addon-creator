-- Rolling log kept in SavedVariables. Readable in WTF/Account/<acct>/SavedVariables/<Addon>.lua
-- after /reload or logout (SavedVariables reach disk only then).
local addonName, ns = ...

local MAX_LINES = 300
local buffer = {}          -- lines written before SavedVariables are available
local seen = {}            -- error messages already logged this session

function ns.Log(fmt, ...)
	local ok, line = pcall(string.format, fmt, ...)
	if not ok then line = tostring(fmt) end
	line = date("%H:%M:%S ") .. line
	local db = ns.db
	local list = db and db.log or buffer
	list[#list + 1] = line
	while #list > MAX_LINES do table.remove(list, 1) end
end

-- Called by Core once SavedVariables are loaded.
function ns.AttachLog(db)
	db.log = db.log or {}
	for i = 1, #buffer do db.log[#db.log + 1] = buffer[i] end
	buffer = {}
	ns.Log("session start %s %s", addonName, tostring(ns.VERSION))
end

-- Log each distinct Lua error once, skip secret messages, then pass it on.
-- Not measured with error-catcher addons (BugGrabber/BugSack may own the handler); errors from
-- this addon's own handlers are logged by ns.Guard either way.
local previous = geterrorhandler()
seterrorhandler(function(message, ...)
	if not (issecretvalue and issecretvalue(message)) and type(message) == "string" and not seen[message] then
		seen[message] = true
		ns.Log("LUA %s", message)
	end
	if previous then return previous(message, ...) end
end)
