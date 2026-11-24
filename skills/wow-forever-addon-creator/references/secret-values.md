# Secret values (modern Mainline: Retail Midnight 12.x, WoW Forever)

In combat, on tainted (addon) execution paths, many APIs return **secret values**: opaque values that may be displayed but not inspected. Health, power, cooldown times, aura data, spellcast spell IDs, damage-meter fields and some tooltip lines can all arrive secret.

## What a secret allows

Marked **[m]** = measured in the Forever client by this skill's authors (field-note number); **[d]** = from Blizzard's generated API docs / Warcraft Wiki, not separately measured.

| Allowed (pass the secret straight in) | Forbidden (Lua error) |
|---|---|
| `FontString:SetText`, `SetFormattedText` [m] | `==`, `<`, `>`, `<=` comparisons [m 11] |
| `StatusBar:SetValue` [m], `SetMinMaxValues` [d] | `+ - * /` arithmetic [m] |
| `Region:SetAlpha` [d — the client may refuse; wrap in pcall], `Texture:SetTexture` [m 14] | `..` concatenation, `tostring` [m] |
| `BreakUpLargeNumbers` [m, displayed in combat text] | using it as a table key [d] |
| `C_Spell.GetSpellTexture(secretID)` → `SetTexture` [m 14] | `string.find`/`gsub` on a secret string [m 18] |
| duration objects → `StatusBar:SetTimerDuration`, `Cooldown:SetCooldownFromDurationObject` [m 2] | `SetCooldown(secretStart, secretDur)` from addon code [m 2] |

Helpers: `issecretvalue(v)` [m], `canaccessvalue(v)` [d], `scrubsecretvalues(...)` and `C_Secrets.HasSecretRestrictions()` [d, Warcraft Wiki Patch 12.0.0 API changes]. Check they exist (`if issecretvalue and issecretvalue(v)`) when one codebase also targets older clients.

## Patterns

**Guard every comparison.**
```lua
local function Plain(v) return v ~= nil and not (issecretvalue and issecretvalue(v)) end
local hp = UnitHealth("player")
if Plain(hp) and hp < 1000 then ... end
bar:SetValue(hp)                      -- fine either way
```
Note: in plain Lua 5.1 `secret == 0` between different types does not call `__eq`, so offline stubs cannot catch every compare; the reviewer must check comparisons by reading.

**Format numbers through the game, not through Lua.**
```lua
text:SetFormattedText("-%s", BreakUpLargeNumbers(amount))   -- amount may be secret
-- NOT: text:SetText("-" .. amount)
```

**Thresholds without reading the value: curves.** To glow when health < 35% without comparing:
```lua
-- 1 below the threshold, 0 above it: a step built from four points.
local function StepCurve(threshold)
    local curve = C_CurveUtil.CreateCurve()
    curve:AddPoint(0, 1)
    curve:AddPoint(threshold, 1)
    curve:AddPoint(threshold + 0.001, 0)
    curve:AddPoint(1, 0)
    return curve
end
local low = StepCurve(0.35)
local alpha = UnitHealthPercent("target", true, low)        -- the game evaluates the hidden value
if not pcall(glow.SetAlpha, glow, alpha) then glow:SetAlpha(0) end   -- log once if refused
-- mana: UnitPowerPercent(unit, Enum.PowerType.Mana, false, curve)
```
Nest two frames to AND two curve-driven alphas. Colour remaining cooldown time with a colour curve:
```lua
local cc = C_CurveUtil.CreateColorCurve()
cc:AddPoint(0, CreateColor(1, 0.2, 0.2)); cc:AddPoint(5, CreateColor(1, 1, 1))
text:SetTextColor(duration:EvaluateRemainingDuration(cc):GetRGB())
```

Some flags such as cooldown `isActive` / `isOnGCD` stay plain — check per field in the API docs (`SecretArguments`, `SecretReturns`, `SecretWhen...` annotations in the generated API documentation).

**Cast bars.** Prefer the duration object (`UnitCastingDuration(unit)` → `StatusBar:SetTimerDuration`), fall back to `UnitCastingInfo` milliseconds when plain, else show a full bar. Do not end the bar on `UNIT_SPELLCAST_FAILED` while `UnitCastingInfo` still reports a cast (spamming a second spell sends FAILED for the second one).

**Auras in combat.** If aura reads are secret while tainted, track your own casts (`UNIT_SPELLCAST_SUCCEEDED`) and time them; learn durations out of combat; accept and document blind spots (resists, dispels).

**Combat text.** Use `UNIT_COMBAT` (amount is secret: display, never sum). The combat log is not available.

**Tooltips.** Tooltip line text can be secret; check before `:find`/`:gsub`. This was the cause of a Lua error in a translation addon reading minimap tooltips.

**Never store a secret.** It cannot be saved to SavedVariables or compared later. Debug probes should record `issecretvalue(x)` as text instead of the value.
