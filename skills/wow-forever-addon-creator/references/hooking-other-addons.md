# Extending another addon without forking it

Worked example: a Turkish translation layer for Questie (GPLv3; tested with Questie 12.11–12.13 on WoW Forever, Nov 2026), shipped first as a companion addon and later as a bundled package.

## Preference order

1. **Use a documented extension point.** Questie exposes `QUESTIE_LOCALES_OVERRIDE` (fields `locale`, `localeName`, `translations`, optional `questLookup`, `npcNameLookup`, `itemLookup`, `objectLookup`). Questie reads it during its own init, after SavedVariables load, so the companion only needs to define the global before that — no `## Dependencies` needed.
2. **Hook public functions with `hooksecurefunc`, imported defensively.**
   ```lua
   local ok, mod = pcall(QuestieLoader.ImportModule, QuestieLoader, "MapIconTooltip")
   if ok and type(mod) == "table" and type(mod.ShowOnTooltip) == "function" then
       hooksecurefunc(mod, "ShowOnTooltip", function(_, tooltip) Retouch(tooltip) end)
   end
   ```
   A renamed module upstream then fails quietly instead of throwing every load.
3. **Fork with anchored patches** only when 1 and 2 are impossible (e.g. the user wants one download).

## Etiquette inside someone else's addon

- Do not overwrite another pack's override: `if QUESTIE_LOCALES_OVERRIDE ~= nil then return end`, and mark your table (`_owner = addonName`) so your extra data attaches only to your own table.
- Change the host addon's settings only while they still hold the host's default (or a value your previous version wrote). Version your own migration so it runs once.
- Undo side effects you are responsible for: Questie's icon theme sets the CVar `questPOI=0`; if Questie is later removed, restore `questPOI=1` once and say so in chat.
- Restore anything you change on shared widgets (e.g. tooltip fonts on `OnHide`/`OnTooltipCleared`) so other addons' tooltips are untouched.
- Hook the function that actually runs: functions stored in a table and called through it are not affected by hooking the global name.

## Surviving upstream updates

- **Extract by executing, not by regex.** Run the host's locale files in a real Lua 5.1 sandbox (e.g. Python `lupa` with `os`, `io`, `load*`, `debug`, `setmetatable`, `rawset` removed, and an assertion that they are gone) and read the resulting tables. Escapes and long strings stay exact.
- **Diff, never rewrite.** After an update, compute "keys upstream now has" minus "keys already translated"; queue only the new ones; report removed ones. Exit 2 when there is work so a scheduler can flag it.
- **Gate every translation**: same printf specifiers in the same order, same counts of `|c…`, `|r`, `|T`, `|t`, `|n`, `\n`, same leading/trailing whitespace; then run every string through `string.format` with dummy arguments in a Lua sandbox. A string that errors there would break the game.
- **Never ship half a unit**: a quest is translated only if all of its objective lines are.
- **Keep proper nouns** (zones, NPCs, items) in the game language the player sees on the map; attach local suffixes with an apostrophe.

## Anchored patching (when forking)

- Every patch replaces an exact anchor that must occur **exactly once**; otherwise the build stops ("upstream changed").
- Count rewrites and fail below a floor (e.g. path rewrites ≥ N).
- The "nothing left over" check must use the **same matching rules** as the rewrite. A case-sensitive leftover check missed 69 lower-case `Interface\\Addons\\Questie` paths and the map icons were invisible; making both case-insensitive fixed it, and the gate was proven by running it against the broken release.
- Rewrite folder references (`AddOns\\Host`) and metadata calls that use the host's folder name when the package folder name differs.
- Ship the host's licence, a NOTICE listing every mechanical change, and honour asset requests in upstream licences (e.g. replacing a logo).
