# Taint and combat lockdown

## The model in five sentences

1. Blizzard code runs "secure"; addon code is "tainted".
2. Execution becomes tainted the moment it reads a value or calls a function written by addon code — including SavedVariables and any global or table field an addon wrote.
3. Tainted execution cannot call protected functions (`UseAction`, `CastSpell`, `TargetUnit`, `ClearTarget`, ...) and, in combat, cannot change protected frames (`SetAttribute`, `SetPoint`, `Show`/`Hide`, `SetScale` on secure frames).
4. Taint spreads through shared state: if an addon puts its frame into a Blizzard list, every Blizzard frame processed after it in that loop is tainted.
5. Taint persists until `/reload`, so one stray write can break Blizzard UI for the whole session, far from the line that caused it.

The symptoms: "Interface action failed because of an AddOn", `ADDON_ACTION_BLOCKED` (a protected call was refused), `ADDON_ACTION_FORBIDDEN` (a protected call is never allowed for addons), and errors deep inside Blizzard files that mention secret values.

## Rules measured in game (WoW Forever, Nov 2026 — field-note numbers in brackets)

**Never wrap methods of secure buttons.** A "combat-safe" wrapper around `SetAttribute` on action buttons turned every later click into `UseAction FORBIDDEN`. Blizzard's own code calls those methods; routing the call through addon code taints the click. Removing the wrapper took FORBIDDEN errors to zero. [3]

**Never write fields on Blizzard frames.** `button.myGlow = tex` or setting `lockColor` on a Blizzard bar taints whoever reads that table later. Keep a side table [1]:

```lua
local glows = {}            -- [blizzardButton] = ourTexture
glows[button] = tex
```

**Re-apply visuals with `hooksecurefunc`, not by replacing functions.** To keep a Blizzard texture hidden even when Blizzard resets it:

```lua
hooksecurefunc(region, "SetVertexColor", function(self) self:SetAlpha(0) end)
hooksecurefunc(region, "SetAlpha", function(self, a) if a ~= 0 then self:SetAlpha(0) end end)
```

(`SetVertexColor` with an alpha argument resets `SetAlpha(0)` — that was the bug. [9])

**Keep addon-made buttons out of Blizzard's shared event lists.** Addon action buttons built from Blizzard templates register into `ActionBarButtonEventsFrame.frames` / `ActionBarActionEventsFrame.frames`. Blizzard's loop then reads them and every Blizzard button after them fails on secret cooldowns in combat. Remove them from the lists, relay the events to them from your own frame, and hook `RegisterFrame` because Blizzard re-adds them. [1]

**In combat, update only what is not protected.** A slot change calls Blizzard's `Update()`, which writes press-and-hold and ping attributes — blocked in combat on addon buttons. Update the icon immediately; run the full `Update()` once at `PLAYER_REGEN_ENABLED`. Hovering triggered the same attribute writes through Blizzard's `OnEnter`; guarding that path took 164 BLOCKED lines per session to 0. [4, 5]

**Right-click can taint.** Blizzard's `OnClick` reads `self.action`, which addon code wrote. Registering left clicks only (`RegisterForClicks("LeftButtonUp", "LeftButtonDown")`) removed the forbidden `UseAction`. [6]

**Send spellcast events only to the matching button**, not to every button, or every icon plays the cast animation. [7]

**For protected actions from addon UI, put secure buttons on top.** Item-on-item use from addon bag buttons was blocked. Out of combat, place `SecureActionButtonTemplate` covers at the same screen position with the needed attributes; hide them at `PLAYER_REGEN_DISABLED` (the last moment they can still be hidden). [13]

## Patterns used in shipped code, not separately measured

These run in our released addons without reported errors, but no in-game measurement isolated them. Treat them as strong defaults, not proof.

- **Move secure frames with animations, not anchors**, when they must move in combat: a `Translation` animation moves the frame without touching anchors.
- **Silence keys per session with override bindings**: `SetOverrideBinding(owner, false, key, "")` out of combat. Never write the player's saved bindings.
- **Stop a Blizzard bar by its own API**, e.g. `PlayerCastingBarFrame:SetUnit(nil)`, not `SetAlpha(0)` — Blizzard's fades undo plain alpha.

## Combat queue pattern

The canonical implementation is `ns.AfterCombat(key, fn)` in `assets/template/Core.lua`: run now if allowed, otherwise store under a key (repeated requests collapse into one) and run each once, guarded, at `PLAYER_REGEN_ENABLED`.

Use it for: creating secure frames or children of Blizzard protected frames, `SetAttribute`, scaling or moving secure buttons, override bindings, Blizzard `Update()` calls on addon buttons. Refuse user commands that need it in combat with a clear chat line instead of silently failing.

## Finding the cause

1. `/console taintLog 1` (2 for more detail), reproduce, `/reload`, read `Logs/taint.log`. Look for "tainted by <Addon>" and the field that was read (e.g. "reading field action - ActionButton.lua:1404").
2. Log `ADDON_ACTION_BLOCKED` / `ADDON_ACTION_FORBIDDEN` with context to your own SavedVariables log (cap per combat to avoid floods).
3. `/fstack` identifies frames under the cursor; `/etrace` shows events as they fire.
4. Fix the read, not the symptom. The line in the error is usually Blizzard's; the cause is the earlier addon write.
