# Events, load order and performance

## One event hub, every handler guarded

The canonical implementation is `ns.On` / `ns.Guard` in `assets/template/Core.lua`: one hidden frame registers each event once, keeps a list of handlers per event, and runs every handler through `pcall`; a failure is written to the saved log and passed to `geterrorhandler()` so it still shows with `scriptErrors 1`.

Why: one failing handler must not kill the others, and the error must reach both the player and your disk log.

## Load-time order

| Moment | Safe to |
|---|---|
| File load (TOC order) | define functions and tables; create plain frames |
| `ADDON_LOADED` with `arg1 == addonName` | read SavedVariables, apply defaults and migrations |
| `PLAYER_LOGIN` | most APIs, build UI |
| `SETTINGS_LOADED` | call `Settings.GetValue/SetValue` (fails earlier) |
| `PLAYER_ENTERING_WORLD` | fires on login **and** every loading screen; re-anchor, refresh |

Define every `local function` above its first call; luacheck flags the later-defined one as an undefined global.

## Unit events

`frame:RegisterUnitEvent("UNIT_HEALTH", "player")` instead of `RegisterEvent` + filtering: less work and no events for 40 raid units.

## OnUpdate

- A script on a hidden frame does not run — hide the frame when idle instead of returning early every frame.
- Throttle with an accumulator:
```lua
local acc = 0
f:SetScript("OnUpdate", function(_, elapsed)
    acc = acc + elapsed
    if acc < 0.2 then return end
    acc = 0
    Refresh()
end)
```
- Coalesce bursts: set a pending flag and do the work once in `C_Timer.After(0, ...)`.
- Hook storms (bag keys fire several hooks per press): record the intent, decide once on the next frame, strongest intent wins.

## Build order inside a feature

1. Build the essential part.
2. Add decoration in separate guarded steps (a broken glow must not take the cast bar with it).
3. Hide the Blizzard UI you replace **last**, only after your build succeeded — or, for windows that would otherwise double-show, close Blizzard's first so a later error cannot leave both visible. Decide which failure mode is worse and write the reason in a comment.

## Performance notes

- Cache globals used in hot paths as locals (`local UnitHealth = UnitHealth`).
- Avoid creating tables or closures per frame or per event.
- Throttle tooltip and bag scans; scan on the event that changes the data, not on a timer.
- Measure before optimising. Confirm in the target client's source which profiling APIs exist (they differ between flavors) and switch any profiling CVar back off afterwards.
